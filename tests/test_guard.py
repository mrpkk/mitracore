"""guard: бюджет, allowlist, kill-switch, подписанный журнал.

Запуск: python3 -m pytest tests/ -q

Проверяется то, что нельзя увидеть глазами: что отказ НЕ запускает команду и
НЕ тратит бюджет, что правка журнала видна проверкой подписи, что удалённая
строка видна по сцепке, и что битая политика — отказ, а не «на всякий случай».
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from guard import check as guard_check  # noqa: E402
from guard.ledger import Ledger, canonical, utc_day  # noqa: E402
from guard.policy import Policy, PolicyError  # noqa: E402

PAYEE = "0x1111111111111111111111111111111111111111"
OTHER = "0x9999999999999999999999999999999999999999"


def make_policy(tmp_path: Path, **over) -> tuple[Policy, Path]:
    data = {"agent_id": "agent-1", "daily_budget_usd": 5.0, "max_per_call_usd": 1.0,
            "payees": [PAYEE], "networks": ["base"], "kill_switch": "KILL",
            "ledger": "ledger.jsonl", "keys": "keys"}
    data.update(over)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data), "utf-8")
    return Policy.load(path), path


def make_request(**over) -> dict:
    request = {"agent_id": "agent-1", "payee": PAYEE, "amount_usd": 0.5,
               "network": "base", "action": "pay"}
    request.update(over)
    return request


def authorize(policy: Policy, **over) -> dict:
    return guard_check.authorize(make_request(**over), policy)


def ledger_of(policy: Policy) -> Ledger:
    return Ledger(policy.ledger, policy.keys)


# ── allow ─────────────────────────────────────────────────────────────────

def test_allow_is_signed_counted_and_verifiable(tmp_path):
    policy, _ = make_policy(tmp_path)
    result = authorize(policy)

    assert result["decision"] == "allow", result["reason"]
    assert result["spent_today_usd"] == 0.5
    assert result["remaining_usd"] == 4.5
    assert result["record"]["signature"] and result["record"]["algorithm"] == "ed25519"

    report = ledger_of(policy).verify()
    assert (report["records"], report["ok"], report["broken"]) == (1, 1, [])

    key = tmp_path / "keys" / "guard.key"
    assert key.exists() and (tmp_path / "keys" / "guard.pub").exists()
    assert oct(key.stat().st_mode)[-3:] == "600"


# ── дневной бюджет ────────────────────────────────────────────────────────

def test_daily_budget_denies_and_deny_does_not_spend(tmp_path):
    policy, _ = make_policy(tmp_path)
    decisions = [authorize(policy, amount_usd=0.9)["decision"] for _ in range(7)]

    assert decisions == ["allow"] * 5 + ["deny"] * 2
    extra = authorize(policy, amount_usd=0.9)
    assert "daily budget" in extra["reason"]
    assert ledger_of(policy).spent(utc_day()) == 4.5
    assert len([r for r in ledger_of(policy).records() if r["decision"] == "allow"]) == 5


def test_per_call_cap_denies_even_within_budget(tmp_path):
    policy, _ = make_policy(tmp_path, daily_budget_usd=5.0, max_per_call_usd=1.0)
    result = authorize(policy, amount_usd=2.0)
    assert result["decision"] == "deny"
    assert "per-call cap" in result["reason"]
    assert result["spent_today_usd"] == 0


# ── получатель и сеть ─────────────────────────────────────────────────────

def test_payee_outside_allowlist_denies(tmp_path):
    policy, _ = make_policy(tmp_path)
    result = authorize(policy, payee=OTHER)
    assert result["decision"] == "deny"
    assert "allowlist" in result["reason"]
    assert ledger_of(policy).spent(utc_day()) == 0


def test_network_outside_allowlist_denies(tmp_path):
    policy, _ = make_policy(tmp_path)
    assert authorize(policy, network="ethereum")["decision"] == "deny"
    assert authorize(policy, network="")["decision"] == "deny"
    # Пустой allowlist сетей = сеть не ограничена, но получатель всё равно проверяется.
    loose_dir = tmp_path / "loose"
    loose_dir.mkdir()
    loose, _ = make_policy(loose_dir, networks=[])
    assert authorize(loose, network="ethereum")["decision"] == "allow"


def test_missing_amount_denies(tmp_path):
    policy, _ = make_policy(tmp_path)
    result = authorize(policy, amount_usd=None)
    assert result["decision"] == "deny"
    assert "amount_usd" in result["reason"]


# ── kill-switch ───────────────────────────────────────────────────────────

def test_kill_switch_denies_and_stays_denied(tmp_path):
    policy, _ = make_policy(tmp_path)
    assert authorize(policy)["decision"] == "allow"

    policy.kill_switch.touch()
    for _ in range(2):  # повторный запуск — снова отказ
        blocked = authorize(policy)
        assert blocked["decision"] == "deny"
        assert "kill switch" in blocked["reason"]

    records = ledger_of(policy).records()
    assert [r["decision"] for r in records] == ["allow", "deny", "deny"]
    assert ledger_of(policy).spent(utc_day()) == 0.5
    assert ledger_of(policy).verify()["broken"] == []


# ── журнал ────────────────────────────────────────────────────────────────

def test_tampered_amount_is_caught_by_the_signature(tmp_path):
    policy, _ = make_policy(tmp_path)
    authorize(policy)
    authorize(policy)
    assert ledger_of(policy).verify()["ok"] == 2

    lines = policy.ledger.read_text("utf-8").splitlines()
    row = json.loads(lines[-1])  # последняя запись: сцепку вниз не рвёт
    row["amount_usd"] = 0.01
    # Подделыватель пересчитал digest, но подписать не может — ключа нет.
    unsigned = {k: v for k, v in row.items()
                if k not in ("signature", "public_key", "algorithm", "digest")}
    row["digest"] = "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()
    lines[-1] = json.dumps(row)
    policy.ledger.write_text("\n".join(lines) + "\n", "utf-8")

    report = ledger_of(policy).verify()
    assert report["ok"] == 1
    assert len(report["broken"]) == 1
    assert "signature" in report["broken"][0]["reason"]


def test_deleted_record_is_caught_by_the_chain(tmp_path):
    policy, _ = make_policy(tmp_path)
    for _ in range(3):
        authorize(policy)
    assert ledger_of(policy).verify()["ok"] == 3

    lines = policy.ledger.read_text("utf-8").splitlines()
    (tmp_path / "cut.jsonl").write_text("\n".join([lines[0], lines[2]]) + "\n", "utf-8")

    report = Ledger(tmp_path / "cut.jsonl", policy.keys).verify()
    assert report["ok"] == 1 and len(report["broken"]) == 1
    assert "seq" in report["broken"][0]["reason"]


# ── политика ──────────────────────────────────────────────────────────────

def test_broken_policy_is_an_error_not_a_default(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"payees": [PAYEE]}), "utf-8")
    with pytest.raises(PolicyError):
        Policy.load(bad)
    with pytest.raises(PolicyError):
        Policy.load(tmp_path / "missing.json")


# ── CLI ───────────────────────────────────────────────────────────────────

def run_proxy(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", "guard.proxy", *args],
                          cwd=cwd, env=env, capture_output=True, text=True)


def test_proxy_runs_the_command_only_when_allowed(tmp_path):
    _, path = make_policy(tmp_path)
    base = ("--policy", str(path), "--amount", "0.5", "--network", "base")

    allowed = run_proxy(tmp_path, *base, "--payee", PAYEE, "--cmd", "touch marker")
    assert allowed.returncode == 0, allowed.stderr
    assert (tmp_path / "marker").exists()

    denied = run_proxy(tmp_path, *base, "--payee", OTHER, "--cmd", "touch blocked")
    assert denied.returncode == 2
    assert denied.stderr.startswith("deny:")
    assert not (tmp_path / "blocked").exists()

    verified = run_proxy(tmp_path, "--policy", str(path), "--verify")
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["ok"] == 2


def test_proxy_denies_over_budget_without_running(tmp_path):
    _, path = make_policy(tmp_path, daily_budget_usd=1.0)
    common = ("--policy", str(path), "--amount", "0.8", "--payee", PAYEE,
              "--network", "base")

    assert run_proxy(tmp_path, *common, "--cmd", "touch first").returncode == 0
    second = run_proxy(tmp_path, *common, "--cmd", "touch second")
    assert second.returncode == 2
    assert "daily budget" in second.stderr
    assert not (tmp_path / "second").exists()


def test_proxy_kill_switch_blocks_every_retry(tmp_path):
    policy, path = make_policy(tmp_path)
    policy.kill_switch.touch()
    common = ("--policy", str(path), "--amount", "0.1", "--payee", PAYEE,
              "--network", "base")

    for name in ("a", "b"):
        result = run_proxy(tmp_path, *common, "--cmd", f"touch {name}")
        assert result.returncode == 2
        assert "kill switch" in result.stderr
        assert not (tmp_path / name).exists()


def test_proxy_broken_policy_runs_nothing(tmp_path):
    bad = tmp_path / "policy.json"
    bad.write_text(json.dumps({"daily_budget_usd": "five",
                               "max_per_call_usd": 1.0}), "utf-8")
    result = run_proxy(tmp_path, "--policy", str(bad), "--amount", "0.1",
                       "--payee", PAYEE, "--cmd", "touch never")
    assert result.returncode == 2
    assert "daily_budget_usd" in result.stderr
    assert not (tmp_path / "never").exists()
