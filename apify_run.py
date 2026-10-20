#!/usr/bin/env python3
"""Режим запуска Apify для mitracore: артефакт агента → подписанный вердикт.

Действие акта: принять артефакт (JSON или текст) и, по желанию, JSON-схему;
проверка идёт через публичный attest (четыре слоя: схема, пустота, provenance,
полномочия), ответ — вердикт с подписью Ed25519.

Вход прогона читается из KV-хранилища по `ACTOR_INPUT_KEY`, результат
пишется в dataset прогона и в KV-запись `OUTPUT`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.apify.com/v2"
UA = "apify-actor/1.0"


def _api(method: str, url: str, payload=None, timeout: int = 30):
    """Запрос к Apify API. Токен платформа внедряет в контейнер (APIFY_TOKEN)."""
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": UA,
                                          "Authorization": f"Bearer {os.environ.get('APIFY_TOKEN', '')}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400].decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def read_input() -> dict:
    """Вход прогона: из ACTOR_INPUT, иначе из KV-хранилища по ACTOR_INPUT_KEY."""
    raw = os.environ.get("ACTOR_INPUT")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if not (os.environ.get("APIFY_TOKEN") and os.environ.get("ACTOR_INPUT_KEY")
            and os.environ.get("ACTOR_DEFAULT_KEY_VALUE_STORE_ID")):
        return {}
    store = os.environ["ACTOR_DEFAULT_KEY_VALUE_STORE_ID"]
    key = os.environ["ACTOR_INPUT_KEY"]
    status, body = _api("GET", f"{API}/key-value-stores/{store}/records/{key}")
    if status != 200 or not isinstance(body, dict):
        return {}
    value = body.get("value")
    return value if isinstance(value, dict) else {}


def write_output(item: dict) -> None:
    """Результат — в dataset прогона и в KV-запись OUTPUT."""
    if os.environ.get("APIFY_TOKEN") and os.environ.get("ACTOR_DEFAULT_DATASET_ID"):
        status, body = _api("POST", f"{API}/datasets/{os.environ['ACTOR_DEFAULT_DATASET_ID']}/items", [item])
        print(f"apify_run: dataset -> {status} {str(body)[:120]}", flush=True)
    if os.environ.get("APIFY_TOKEN") and os.environ.get("ACTOR_DEFAULT_KEY_VALUE_STORE_ID"):
        status, body = _api("PUT", f"{API}/key-value-stores/{os.environ['ACTOR_DEFAULT_KEY_VALUE_STORE_ID']}/records/OUTPUT", item)
        print(f"apify_run: KV OUTPUT -> {status} {str(body)[:120]}", flush=True)


def serve() -> None:
    """Нет входа — работаем как MCP-сервер на порту платформы."""
    port = os.environ.get("ACTOR_WEB_SERVER_PORT") or os.environ.get("PORT") or "8192"
    here = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(here, "mcp_server.py"), "--http", str(port),
           "--http-path", "/mcp", "--host", "0.0.0.0"]
    print(f"apify_run: входа нет -> MCP-сервер на порту {port}", flush=True)
    os.chdir(here)
    os.execv(cmd[0], cmd)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


ATTEST = os.environ.get("ATTEST_URL", "https://rta.lat/attest")
ENT_HEADER = "X-ATTEST-ENTITLEMENT"
UA = "mitracore-apify/1.0"


def _post_verify(payload: dict, timeout: int = 40) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json", "User-Agent": UA}
    ent = os.environ.get("ATTEST_ENTITLEMENT")
    if ent:
        headers[ENT_HEADER] = ent
    req = urllib.request.Request(f"{ATTEST}/verify", data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "detail": e.read()[:400].decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def run_action(inp: dict) -> dict:
    raw = inp.get("artifact")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ValueError("нужно поле artifact — текст или JSON артефакта агента")
    text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    try:
        art = json.loads(text) if isinstance(raw, str) else raw
    except Exception:
        art = text

    payload: dict = {"artifact": art, "source": inp.get("source") or "apify"}
    schema = inp.get("schema")
    if isinstance(schema, str) and schema.strip():
        try:
            payload["schema"] = json.loads(schema)
        except Exception as e:
            raise ValueError(f"поле schema не является JSON: {e}") from e
    elif isinstance(schema, dict) and schema:
        payload["schema"] = schema

    res = _post_verify(payload)
    if not res.get("ok", True) and res.get("error"):
        return {"error": res["error"], "detail": res.get("detail", ""),
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    att = res.get("attestation") or {}
    return {
        "verdict": res.get("verdict", "reject"),
        "trust_score": res.get("trust_score", 0),
        "content_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "violations": res.get("violations", []),
        "signals": res.get("signals", []),
        "reason": res.get("reason", ""),
        "attestation": {
            "algorithm": att.get("algorithm", ""),
            "signature": att.get("signature", ""),
            "public_key": att.get("public_key", ""),
        },
        "source": payload["source"],
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    inp = read_input()
    if not inp:
        serve()
        return 0
    try:
        item = run_action(inp)
    except Exception as e:  # noqa: BLE001
        item = {"error": f"{type(e).__name__}: {e}"}
    print(json.dumps(item, ensure_ascii=False, indent=2, default=str), flush=True)
    write_output(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
