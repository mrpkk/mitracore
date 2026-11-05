"""Журнал расходов: JSONL, каждая запись подписана Ed25519 и сцеплена с прошлой.

Ключ — `guard.key` (raw 32 байта, 0600), публичный — `guard.pub` рядом.
Канонизация и проверка подписи берутся у trust_check: одна реализация на
репозиторий, иначе квитанция Suite и запись журнала перестанут совпадать.

Сцепка `seq` + `prev` нужна против удаления строки: без неё «дорогую» запись
можно вычеркнуть и бюджет на день снова полон.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import trust_check as _tc

# JCS-подмножество репозитория (ASCII-ключи, sort_keys): квитанции и журнал
# подписываются одинаково.
canonical = _tc._canonical
verify_signature = _tc.verify_signature

_SIGNATURE_FIELDS = ("signature", "public_key", "algorithm")
PRIVATE_NAME, PUBLIC_NAME = "guard.key", "guard.pub"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_day(ts: float | None = None) -> str:
    """Сутки считаются по UTC: день не зависит от часового пояса процесса."""
    stamp = time.time() if ts is None else ts
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")


class Ledger:
    def __init__(self, path: str | Path, key_dir: str | Path):
        self.path = Path(path)
        self.key_dir = Path(key_dir)
        self._lock = threading.Lock()

    # ── ключ ──────────────────────────────────────────────────────────────

    def _private(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key_file = self.key_dir / PRIVATE_NAME
        if not key_file.exists():
            self.key_dir.mkdir(parents=True, exist_ok=True)
            key = Ed25519PrivateKey.generate()
            key_file.write_bytes(key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()))
            key_file.chmod(0o600)
        return Ed25519PrivateKey.from_private_bytes(key_file.read_bytes())

    def public_b64(self) -> str:
        """Публичный ключ лежит рядом с приватным — проверить может кто угодно."""
        from cryptography.hazmat.primitives import serialization

        pub_file = self.key_dir / PUBLIC_NAME
        if pub_file.exists():
            return pub_file.read_text("utf-8").strip()
        raw = self._private().public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        value = base64.b64encode(raw).decode("ascii")
        self.key_dir.mkdir(parents=True, exist_ok=True)
        pub_file.write_text(value + "\n", "utf-8")
        return value

    # ── замок ─────────────────────────────────────────────────────────────

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Один писатель за раз: бюджет читается и пишется под этим замком.

        Без замка два процесса видят «потрачено 4.0» и оба разрешают по 0.9
        при бюджете 5 — деньги уходят дважды.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.with_suffix(self.path.suffix + ".lock")
        with self._lock, open(lock_file, "a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # ── чтение ────────────────────────────────────────────────────────────

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text("utf-8", "replace").splitlines()

    def records(self) -> list[dict]:
        rows: list[dict] = []
        for line in self._lines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def spent(self, day: str) -> float:
        """Сколько уже разрешено за сутки: считаются только allow.

        shortcut: строки берутся как есть, без проверки подписи (дорого на
        каждый вызов); правку журнала ловит verify(). Вверх подделать не
        страшно — это лишний отказ, вниз мешает только правка файла руками,
        а кто правит журнал, тот правит и политику.
        """
        total = 0.0
        for row in self.records():
            if row.get("decision") != "allow" or row.get("day") != day:
                continue
            amount = row.get("amount_usd")
            if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                total += float(amount)
        return round(total, 6)

    # ── запись ────────────────────────────────────────────────────────────

    def append(self, body: dict) -> dict:
        """Дописывает подписанную запись. `seq` и `prev` ставит сам."""
        rows = self.records()
        last = rows[-1] if rows else {}
        seq = last.get("seq") if isinstance(last.get("seq"), int) else len(rows)
        unsigned = {"seq": seq + 1, "prev": last.get("digest"),
                    "at": iso(time.time()), **body}
        digest = "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()
        signed = {**unsigned, "digest": digest}
        row = dict(signed)
        row["signature"] = base64.b64encode(
            self._private().sign(canonical(signed))).decode("ascii")
        row["public_key"] = self.public_b64()
        row["algorithm"] = "ed25519"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    # ── проверка ──────────────────────────────────────────────────────────

    def verify(self, public_key: str | None = None) -> dict:
        """Подпись каждой строки + сцепка. Ключ по умолчанию — из guard.pub.

        Ключ из самой записи не годится: подделыватель подпишет свой журнал
        своим ключом, и «всё сойдётся».
        """
        pub = public_key or self.public_b64()
        broken: list[dict] = []
        total, prev_digest, expected = 0, None, 1
        for lineno, line in enumerate(self._lines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                broken.append({"line": lineno, "reason": "not JSON"})
                continue
            if not isinstance(row, dict):
                broken.append({"line": lineno, "reason": "not a JSON object"})
                continue
            total += 1
            unsigned = {k: v for k, v in row.items()
                        if k not in _SIGNATURE_FIELDS + ("digest",)}
            body = {k: v for k, v in row.items() if k not in _SIGNATURE_FIELDS}
            if row.get("seq") != expected:
                broken.append({"line": lineno,
                               "reason": f"seq {row.get('seq')} where {expected} expected"})
            elif row.get("prev") != prev_digest:
                broken.append({"line": lineno, "reason": "prev does not match the chain"})
            elif row.get("digest") != "sha256:" + hashlib.sha256(
                    canonical(unsigned)).hexdigest():
                broken.append({"line": lineno, "reason": "digest does not match the body"})
            elif not verify_signature(canonical(body), row.get("signature"), pub):
                broken.append({"line": lineno, "reason": "signature does not match"})
            prev_digest, expected = row.get("digest"), expected + 1
        return {"records": total, "ok": total - len(broken), "broken": broken,
                "public_key": pub, "algorithm": "ed25519"}
