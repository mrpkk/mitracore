"""python -m guard.proxy — обёртка вызова: политика решает, запускать ли команду.

    python -m guard.proxy --policy guard/policy.json --amount 0.25 \
        --payee 0x1111111111111111111111111111111111111111 --network base \
        --cmd "curl -s https://example/a"

allow  → команда запускается без shell (shlex.split), запись в журнале, код возврата;
         пайпы и редиректы намеренно не поддерживаются: shell=True дал бы инъекцию;
deny   → команда НЕ запускается, подписанный отказ в журнале, код 2;
битая политика → код 2 и ни одного запуска;
--verify → только проверка журнала подписью, код 0 (сходится) или 3 (нет).
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys

from .check import authorize
from .ledger import Ledger
from .policy import Policy, PolicyError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m guard.proxy",
        description="Run a command only if the agent policy allows it, and log the decision.")
    ap.add_argument("--policy", default="policy.json")
    ap.add_argument("--amount", type=float, help="what the call costs, USD")
    ap.add_argument("--payee", default="", help="recipient address")
    ap.add_argument("--network", default="", help="network the money moves on")
    ap.add_argument("--agent", default="", help="agent id, for the journal")
    ap.add_argument("--action", default="call")
    ap.add_argument("--cmd", help="command to wrap")
    ap.add_argument("--verify", action="store_true", help="verify the journal, run nothing")
    ap.add_argument("--json", action="store_true", help="print the whole decision record")
    args = ap.parse_args(argv)

    try:
        policy = Policy.load(args.policy)
    except PolicyError as exc:
        print(f"deny: {exc}", file=sys.stderr)
        return 2

    ledger = Ledger(policy.ledger, policy.keys)

    if args.verify:
        report = ledger.verify()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not report["broken"] else 3

    if not args.cmd:
        print("nothing to run: pass --cmd or --verify", file=sys.stderr)
        return 2

    result = authorize({
        "agent_id": args.agent or None,
        "payee": args.payee,
        "network": args.network,
        "amount_usd": args.amount,
        "action": args.action,
        "cmd": args.cmd,
    }, policy, ledger)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        line = f"{result['decision']}: {result['reason']}"
        print(line, file=sys.stderr if result["decision"] != "allow" else sys.stdout)

    if result["decision"] != "allow":
        return 2
    return subprocess.run(shlex.split(args.cmd), check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
