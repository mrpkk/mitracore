"""Шесть проверок /api/trust/check. Запуск: python3 -m pytest tests/ -q

Проверяется то, что нельзя увидеть глазами в ответе: что просроченный мандат
не проходит, что чужой получатель не проходит, что перерасход не проходит,
что неизвестное даёт needs_human, а не «да», и что та же транзакция второй
раз не проходит.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trust_check as tc  # noqa: E402

PAYEE = "0x1111111111111111111111111111111111111111"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Ни ключ, ни журнал повторов не трогают домашний каталог."""
    monkeypatch.setattr(tc, "KEY_FILE", tmp_path / "receipt.key")
    return tmp_path


def payload(**over):
    p = {
        "agent_id": "agent-1",
        "action": {"type": "payment", "amount_usd": 12.5, "payee": PAYEE,
                   "asset": "USDC", "network": "base"},
        "mandate": {"mandate_id": "m-1", "agent_id": "agent-1",
                    "expires_at": "2099-01-01T00:00:00Z"},
        "limits": {"payees": [PAYEE], "assets": ["USDC"], "networks": ["base"],
                   "max_amount_usd": 50},
    }
    p.update(over)
    return p


def result(report, cid):
    return next(c for c in report["checks"] if c["id"] == cid)["result"]


def test_allow_carries_signed_receipt(tmp_path):
    report = tc.check(payload(), store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "allow"
    assert [c["result"] for c in report["checks"]] == ["pass"] * 6
    assert report["checks_total"] == 6 and report["suite_total"] == 24

    receipt = report["receipt"]
    body = {k: v for k, v in receipt.items()
            if k not in ("signature", "public_key", "algorithm", "digest")}
    assert tc.verify_signature(tc._canonical(body), receipt["signature"],
                               receipt["public_key"])


def test_unknown_fields_are_ignored(tmp_path):
    p = payload(extra="x", action={**payload()["action"], "note": "ignore me"})
    report = tc.check(p, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "allow"


def test_empty_input_is_needs_human_not_crash(tmp_path):
    report = tc.check({}, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "needs_human"
    assert len(report["checks"]) == 6
    # Правило и мандат — unknown; квитанции и tx нет, сверять нечего.
    assert [result(report, i) for i in (7, 8, 9, 10)] == ["unknown"] * 4
    assert [result(report, i) for i in (19, 24)] == ["pass", "pass"]
    assert tc.check("not a dict", store=tc.ReplayStore(tmp_path / "r.jsonl"))["verdict"] \
        == "needs_human"


def test_expired_mandate_denies(tmp_path):
    p = payload(mandate={"mandate_id": "m-1", "agent_id": "agent-1",
                         "expires_at": "2020-01-01T00:00:00Z"})
    report = tc.check(p, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "deny"
    assert result(report, 7) == "fail"


def test_payee_not_in_allowlist_denies(tmp_path):
    p = payload(action={**payload()["action"],
                         "payee": "0x9999999999999999999999999999999999999999"})
    report = tc.check(p, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "deny"
    assert result(report, 8) == "fail"


def test_amount_over_limit_denies(tmp_path):
    p = payload(action={**payload()["action"], "amount_usd": 500})
    report = tc.check(p, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "deny"
    assert result(report, 10) == "fail"


def test_asset_and_network_are_checked(tmp_path):
    p = payload(action={**payload()["action"], "network": "ethereum"})
    report = tc.check(p, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "deny"
    assert result(report, 9) == "fail"


def test_missing_limits_is_needs_human(tmp_path):
    report = tc.check({"agent_id": "agent-1", "action": {"amount_usd": 1}},
                      store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "needs_human"
    assert result(report, 8) == "unknown"


def test_receipt_signature_is_verified(tmp_path):
    key = tmp_path / "signer.key"
    signed = {"agent_id": "agent-1", "amount_usd": 5}
    tc.KEY_FILE = key
    sig = tc._sign(tc._canonical(signed))
    pub = tc._public_b64()

    good = payload(receipt={"payload": signed, "signature": sig,
                            "public_key": pub, "algorithm": "ed25519"})
    assert result(tc.check(good, store=tc.ReplayStore(tmp_path / "r.jsonl")), 19) == "pass"

    bad = payload(receipt={"payload": {**signed, "amount_usd": 500},
                           "signature": sig, "public_key": pub})
    report = tc.check(bad, store=tc.ReplayStore(tmp_path / "r.jsonl"))
    assert report["verdict"] == "deny"
    assert result(report, 19) == "fail"


def test_replay_of_same_tx_denies(tmp_path):
    store = tc.ReplayStore(tmp_path / "r.jsonl")
    p = payload(action={**payload()["action"], "tx_hash": "0xabc123"})
    first = tc.check(p, store=store)
    assert first["verdict"] == "allow"
    second = tc.check(p, store=store)
    assert second["verdict"] == "deny"
    assert result(second, 24) == "fail"

    # Тот же журнал, поднятый с диска после рестарта, помнит транзакцию.
    assert tc.ReplayStore(tmp_path / "r.jsonl").get("0xabc123")["verdict"] == "allow"
    assert json.dumps(second, default=str)  # ответ сериализуется целиком
