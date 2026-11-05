#!/usr/bin/env python3
"""Шесть проверок доверия к действию агента — один вердикт.

Срез 1 из 24 проверок Agent Trust Suite (SPEC 05.11.2026 §2): мандат,
получатель, актив/сеть, сумма, подпись квитанции, повтор.

Правило §2: каждая проверка возвращает pass | fail | unknown и одну строку
причины. Никаких «частично»: сомнение — это unknown, а unknown — это
needs_human, а не молчаливое «да».
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

REPLAY_FILE = Path(os.environ.get(
    "MITRACORE_REPLAY_FILE",
    Path.home() / ".local" / "share" / "mitracore" / "trust_replay.jsonl"))
KEY_FILE = Path(os.environ.get(
    "MITRACORE_RECEIPT_KEY",
    Path.home() / ".local" / "share" / "mitracore" / "receipt.key"))


# ── мелочи ────────────────────────────────────────────────────────────────

def _obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(value: Any) -> float | None:
    """Время из ISO-8601 или эпохи. None — «не разобрали», а не «сейчас»."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _short(value: Any, width: int = 10) -> str:
    text = str(value)
    return text if len(text) <= width else text[:6] + "…" + text[-4:]


# ── хроника повторов ──────────────────────────────────────────────────────

class ReplayStore:
    """Локальный журнал исполненных транзакций: файл, не база, не сервис.

    Запись — только по вердикту allow: отказ денег не двигает, повторять
    там нечего.
    """

    def __init__(self, path: Path | None = None):
        self.path = Path(path or REPLAY_FILE)
        self._lock = threading.Lock()
        self._seen: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text("utf-8", "replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("tx_hash"):
                self._seen[str(row["tx_hash"])] = row

    def get(self, tx_hash: str) -> dict | None:
        with self._lock:
            return self._seen.get(tx_hash)

    def record(self, tx_hash: str, verdict: str, agent_id: Any) -> dict:
        row = {"tx_hash": tx_hash, "verdict": verdict,
               "agent_id": agent_id, "at": _iso(time.time())}
        with self._lock:
            self._seen[tx_hash] = row
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


_STORE: ReplayStore | None = None
_STORE_LOCK = threading.Lock()


def default_store() -> ReplayStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ReplayStore()
        return _STORE


# ── подпись квитанции (Ed25519, как в attest) ─────────────────────────────

def _private_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    path = Path(KEY_FILE)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        path.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()))
        path.chmod(0o600)
    return Ed25519PrivateKey.from_private_bytes(path.read_bytes())


def _public_b64() -> str:
    from cryptography.hazmat.primitives import serialization
    raw = _private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def _sign(payload: bytes) -> str:
    return base64.b64encode(_private_key().sign(payload)).decode("ascii")


def verify_signature(payload: bytes, signature: Any, public: Any) -> bool:
    """Проверка без доверия к нам: публичный ключ приходит вместе с подписью."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(
            base64.b64decode(str(public))).verify(
            base64.b64decode(str(signature)), payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ── шесть проверок ────────────────────────────────────────────────────────

def check_mandate(p: dict) -> tuple[str, str]:
    mandate = p.get("mandate")
    if not isinstance(mandate, dict):
        return UNKNOWN, "mandate not provided"
    expires = _time(mandate.get("expires_at"))
    if expires is None:
        return UNKNOWN, "expires_at missing or not ISO-8601"
    if expires <= time.time():
        return FAIL, f"mandate expired at {_iso(expires)}"
    owner = mandate.get("agent_id")
    if owner and p.get("agent_id") and str(owner) != str(p.get("agent_id")):
        return FAIL, f"mandate belongs to {owner}"
    return PASS, f"expires {_iso(expires)}"


def check_payee(p: dict) -> tuple[str, str]:
    payee = _obj(p.get("action")).get("payee")
    allowed = _obj(p.get("limits")).get("payees")
    if not isinstance(allowed, list) or not allowed:
        return UNKNOWN, "limits.payees not provided"
    if not payee:
        return UNKNOWN, "action.payee not provided"
    if str(payee).lower() in {str(x).lower() for x in allowed}:
        return PASS, f"payee {_short(payee)} is in the allowlist"
    return FAIL, f"payee {_short(payee)} is not in the allowlist of {len(allowed)}"


def check_asset_network(p: dict) -> tuple[str, str]:
    action, limits = _obj(p.get("action")), _obj(p.get("limits"))
    asset, network = action.get("asset"), action.get("network")
    assets, networks = limits.get("assets"), limits.get("networks")
    if not isinstance(assets, list) and not isinstance(networks, list):
        return UNKNOWN, "limits.assets / limits.networks not provided"
    if not asset or not network:
        return UNKNOWN, "action.asset / action.network not provided"
    if isinstance(assets, list) and assets and \
            str(asset).lower() not in {str(x).lower() for x in assets}:
        return FAIL, f"asset {asset} is not allowed"
    if isinstance(networks, list) and networks and \
            str(network).lower() not in {str(x).lower() for x in networks}:
        return FAIL, f"network {network} is not allowed"
    return PASS, f"{asset} on {network} is allowed"


def check_amount(p: dict) -> tuple[str, str]:
    action, limits = _obj(p.get("action")), _obj(p.get("limits"))
    amount = _num(action.get("amount_usd"))
    cap = _num(limits.get("max_amount_usd"))
    if amount is None:
        return UNKNOWN, "action.amount_usd not provided"
    if cap is None:
        return UNKNOWN, "limits.max_amount_usd not provided"
    if amount < 0:
        return FAIL, f"amount {amount:g} is negative"
    if amount > cap:
        return FAIL, f"amount {amount:g} exceeds the per-call limit {cap:g}"
    return PASS, f"amount {amount:g} within the per-call limit {cap:g}"


def check_receipt(p: dict) -> tuple[str, str]:
    """Условная проверка: нет квитанции — нечего сверять, но и не отказ."""
    receipt = p.get("receipt")
    if receipt is None:
        return PASS, "no receipt supplied, nothing to verify"
    receipt = _obj(receipt)
    body = receipt.get("payload")
    if body is None or not receipt.get("signature") or not receipt.get("public_key"):
        return UNKNOWN, "receipt needs payload, signature and public_key"
    if receipt.get("algorithm") not in (None, "ed25519"):
        return FAIL, f"algorithm {receipt.get('algorithm')} is not ed25519"
    if verify_signature(_canonical(body), receipt.get("signature"),
                        receipt.get("public_key")):
        return PASS, f"signature valid ({_short(receipt.get('public_key'), 16)})"
    return FAIL, "signature does not match the payload"


def check_replay(p: dict, store: ReplayStore) -> tuple[str, str]:
    tx = _obj(p.get("action")).get("tx_hash") or _obj(p.get("receipt")).get("tx_hash")
    if not tx:
        return PASS, "no tx_hash supplied, nothing to replay"
    seen = store.get(str(tx))
    if seen:
        return FAIL, f"tx {_short(tx)} already used at {seen.get('at')}"
    return PASS, f"tx {_short(tx)} is new"


CHECKS = (
    (7, "mandate active", check_mandate),
    (8, "payee allowed", check_payee),
    (9, "asset and network allowed", check_asset_network),
    (10, "amount within limit", check_amount),
    (19, "receipt signature", check_receipt),
    (24, "receipt not reused", None),  # нужен store, вызывается отдельно
)


def _receipt(p: dict, checks: list[dict]) -> dict:
    body = {
        "receipt_id": "",  # заполняется ниже, чтобы идентификатор был от тела
        "agent_id": p.get("agent_id"),
        "action": p.get("action"),
        "verdict": "allow",
        "decided_at": _iso(time.time()),
        "checks": checks,
    }
    body["receipt_id"] = "trc_" + hashlib.sha256(_canonical(body)).hexdigest()[:24]
    out = dict(body)
    out["digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    try:
        out["signature"] = _sign(_canonical(body))
        out["public_key"] = _public_b64()
        out["algorithm"] = "ed25519"
    except Exception as exc:  # noqa: BLE001 — честно, а не молча без подписи
        out["signature"] = None
        out["signature_error"] = f"{type(exc).__name__}: {exc}"
    return out


def check(payload: Any, store: ReplayStore | None = None) -> dict:
    """Один вход, один ответ. Неизвестные поля не читаются, пустые — unknown."""
    p = _obj(payload)
    store = store or default_store()
    checks: list[dict] = []
    for cid, name, fn in CHECKS:
        result, reason = (check_replay(p, store) if fn is None else fn(p))
        checks.append({"id": cid, "name": name, "result": result, "reason": reason})

    results = [c["result"] for c in checks]
    if FAIL in results:
        verdict = "deny"
    elif UNKNOWN in results:
        verdict = "needs_human"
    else:
        verdict = "allow"

    out: dict[str, Any] = {"verdict": verdict, "checks": checks,
                           "checks_total": 6, "suite_total": 24}
    if verdict == "allow":
        tx = _obj(p.get("action")).get("tx_hash") or _obj(p.get("receipt")).get("tx_hash")
        if tx:
            store.record(str(tx), verdict, p.get("agent_id"))
        out["receipt"] = _receipt(p, checks)
    return out
