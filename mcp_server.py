#!/usr/bin/env python3
"""MITRACORE — единый слой доверия для агентной работы.

Отдельный продукт: НЕ меняет и НЕ перемещает attest, drift, agentpay, skilllint —
он вызывает их по их же HTTP-контрактам и отдаёт один вердикт.

Состав:
  attest  — проверка артефакта (4 слоя: форма, пустота, provenance, право)
  skilllint — приватная проверка скилла (структура, триггеры, инъекции, секреты)
  agentpay — цена по фактическому расходу
  drift   — мандаты и лимиты (доступен как отдельный MCP на :8095/mcp)

Запуск:  python3 mcp_server.py            # stdio
         python3 mcp_server.py --http 8192
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
try:  # установленный пакет (pip/uvx) — иначе соседний каталог
    import skilllint  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.join(HERE, "..", "skilllint"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

mcp = MCPServer("mitracore", version="1.0.0")

ATTEST = os.environ.get("ATTEST_URL", "http://127.0.0.1:8185")
AGENTPAY = os.environ.get("AGENTPAY_URL", "http://127.0.0.1:8187")
DRIFT = os.environ.get("DRIFT_URL", "http://127.0.0.1:8095")
UA = "mitracore/1.0"


def _post(url: str, payload: dict, timeout: int = 20) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "detail": e.read()[:300].decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        return json.loads(raw)
    except Exception:
        return {"ok": True, "raw": raw[:4000]}


def _get(url: str, timeout: int = 8) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        try:
            return {"ok": True, "data": json.loads(raw)}
        except Exception:
            return {"ok": True, "raw": raw[:400]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _as_json(value: str | None, field: str) -> object:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception as e:
        raise ValueError(f"{field} не является JSON: {e}") from e


@mcp.tool(name="verify_work", description="Проверить артефакт агента (4 слоя: схема, пустота, provenance, полномочия). Возвращает вердикт attest.")
async def verify_work(artifact: str, schema: str = "") -> str:
    art = _as_json(artifact, "artifact")
    sch = _as_json(schema, "schema")
    payload: dict = {"artifact": art}
    if sch is not None:
        payload["schema"] = sch
    res = _post(f"{ATTEST}/verify", payload)
    return json.dumps(res, ensure_ascii=False, default=str)


@mcp.tool(name="check_skill", description="Приватно проверить SKILL.md: структура, триггеры, секреты, prompt-injection, битые ссылки. Возвращает вердикт, балл и sha256 (готово к подписи).")
async def check_skill(path: str) -> str:
    from skilllint.linter import lint_skill  # локальный импорт: путь уже в sys.path
    rep = lint_skill(path)
    out = rep.as_dict()
    out["signature_ready"] = {"artifact": {"skill": out.get("skill", ""), "sha256": out.get("sha256", ""),
                                          "score": out.get("score", 0), "verdict": out.get("verdict", "")},
                              "hint": "передай этот artifact в verify_work — получишь подписанный вердикт"}
    return json.dumps(out, ensure_ascii=False)


@mcp.tool(name="quote_cost", description="Посчитать цену по фактическому расходу (токены, CPU, байты, записи, внешние вызовы) — вместо прайсовой таблицы.")
async def quote_cost(tokens: float = 0, cpu_seconds: float = 0, bytes_out: float = 0,
                     storage_writes: float = 0, external_calls: float = 0) -> str:
    res = _post(f"{AGENTPAY}/quote", {"tokens": tokens, "cpu_seconds": cpu_seconds,
                                      "bytes_out": bytes_out, "storage_writes": storage_writes,
                                      "external_calls": external_calls})
    return json.dumps(res, ensure_ascii=False, default=str)


@mcp.tool(name="trust_report", description="Сводный вердикт по артефакту агента: проверка работы (attest) + цена по факту (agentpay) + доступность мандатов (drift).")
async def trust_report(artifact: str, schema: str = "") -> str:
    art = _as_json(artifact, "artifact")
    sch = _as_json(schema, "schema")
    payload: dict = {"artifact": art}
    if sch is not None:
        payload["schema"] = sch
    attest = _post(f"{ATTEST}/verify", payload)
    agentpay = _post(f"{AGENTPAY}/quote", {})
    drift = _get(f"{DRIFT}/health")
    return json.dumps({
        "artifact_verdict": attest,
        "cost_quote": agentpay,
        "mandates_available": bool(drift.get("ok")),
        "mandates_endpoint": f"{DRIFT}/mcp",
        "layers": ["attest:verify", "agentpay:quote", "drift:mandates"],
    }, ensure_ascii=False, default=str)


@mcp.tool(name="suite_status", description="Живое состояние слоёв Suite: attest, agentpay, drift, skilllint.")
async def suite_status() -> str:
    from skilllint.linter import RULES
    return json.dumps({
        "attest": _get(f"{ATTEST}/health"),
        "agentpay": _get(f"{AGENTPAY}/health"),
        "drift": _get(f"{DRIFT}/health"),
        "skilllint": {"ok": True, "rules": len(RULES)},
    }, ensure_ascii=False, default=str)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", type=int, default=0)
    ap.add_argument("--http-path", default="/mcp",
                    help="путь MCP внутри HTTP-сервера (туннель не срезает префикс)")
    ap.add_argument("--port", type=int, default=0, help="порт (перекрывает --http); $PORT — для PaaS")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="bind-адрес (0.0.0.0 в контейнерах)")
    args = ap.parse_args()
    port = args.port or args.http or int(os.environ.get("PORT", "0") or 0)
    if port:
        # mcp.run() сам поднимает свой event loop (anyio.run) — звать без await и вне asyncio.run
        from mcp.server.transport_security import TransportSecuritySettings
        if os.environ.get("MCP_ALLOW_ANY_HOST") == "1":
            security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
            mcp.run(transport="streamable-http", port=port, host=args.host,
                    streamable_http_path=args.http_path, transport_security=security)
            return
        security = TransportSecuritySettings(
            allowed_hosts=["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*",
                           "rta.lat", "*.rta.lat", "rta.ailegal.legal", "*.ailegal.legal"],
            allowed_origins=["http://127.0.0.1:%d" % port, "http://localhost:%d" % port,
                             "https://rta.lat", "https://*.rta.lat",
                             "https://rta.ailegal.legal", "https://*.ailegal.legal"],
        )
        mcp.run(transport="streamable-http", port=port, host=args.host,
                streamable_http_path=args.http_path, transport_security=security)
    else:
        asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
