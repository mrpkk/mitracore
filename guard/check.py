"""authorize(request) — одно решение и одна подписанная запись на него.

Порядок: kill-switch → сумма → потолок вызова → получатель → сеть → дневной
бюджет. В журнал пишется и allow, и deny: журнал решений, а не только трат —
иначе нечем доказать, что агент остановлен.
"""
from __future__ import annotations

from typing import Any

from .ledger import Ledger, utc_day
from .policy import Policy

ALLOW, DENY = "allow", "deny"


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decide(request: dict, policy: Policy, amount: float | None,
            spent: float) -> tuple[str, str]:
    if policy.killed():
        return DENY, f"kill switch engaged: {policy.kill_switch}"
    if amount is None:
        return DENY, "amount_usd missing or not a number"
    if amount < 0:
        return DENY, f"amount {amount:g} is negative"
    if amount > policy.max_per_call_usd:
        return DENY, (f"amount {amount:g} exceeds the per-call cap "
                      f"{policy.max_per_call_usd:g}")
    payee = str(request.get("payee") or "").strip()
    if not payee:
        return DENY, "payee missing"
    if not policy.allows_payee(payee):
        return DENY, f"payee {payee} is not in the allowlist of {len(policy.payees)}"
    network = str(request.get("network") or "").strip()
    if policy.networks:
        if not network:
            return DENY, ("network missing while the policy allows only "
                          + ", ".join(policy.networks))
        if network.lower() not in {x.lower() for x in policy.networks}:
            return DENY, f"network {network} is not in the allowlist of {len(policy.networks)}"
    if spent + amount > policy.daily_budget_usd + 1e-9:
        return DENY, (f"daily budget {policy.daily_budget_usd:g} exceeded: "
                      f"spent {spent:g}, request {amount:g}")
    return ALLOW, (f"{amount:g} USD to {payee} is within "
                   f"{policy.daily_budget_usd:g}/day and {policy.max_per_call_usd:g}/call")


def authorize(request: Any, policy: Policy,
              ledger: Ledger | None = None) -> dict[str, Any]:
    """allow | deny + причина + подписанная запись. Решение никогда не «может быть»."""
    request = request if isinstance(request, dict) else {}
    ledger = ledger or Ledger(policy.ledger, policy.keys)
    day = utc_day()
    amount = _num(request.get("amount_usd"))

    with ledger.locked():
        spent = ledger.spent(day)
        decision, reason = _decide(request, policy, amount, spent)
        record = ledger.append({
            "agent_id": request.get("agent_id") or policy.agent_id,
            "decision": decision,
            "reason": reason,
            "amount_usd": amount,
            "day": day,
            "action": request.get("action"),
            "payee": request.get("payee"),
            "network": request.get("network"),
            "cmd": request.get("cmd"),
            "spent_before_usd": spent,
            "budget_usd": policy.daily_budget_usd,
            "max_per_call_usd": policy.max_per_call_usd,
        })

    spent_after = spent + (amount if decision == ALLOW and amount else 0.0)
    return {
        "decision": decision,
        "reason": reason,
        "spent_today_usd": round(spent_after, 6),
        "remaining_usd": round(max(0.0, policy.daily_budget_usd - spent_after), 6),
        "ledger": str(ledger.path),
        "record": record,
    }
