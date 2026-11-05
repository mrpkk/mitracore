# mitracore

**Trust layer for agent work: verify the artifact, meter what it cost, enforce the mandate.**

Three risks, one call:

1. **verify** - four layers over an agent artifact: schema conformance, emptiness (uniform lists, stub values, truncations), generation provenance, authority (was the action permitted). Ed25519-signed receipt, verifiable offline, no trust in this service required.
2. **quote** - price what the call actually consumed (tokens, CPU seconds, bytes out, storage writes, external calls) from a published rate card, with the breakdown attached.
3. **mandates** - limits, allowlist and kill switch for what an agent may do.

## Use it

MCP (recommended):

```bash
npx -y mcp-remote https://rta.lat/mitracore/mcp   # hosted
python3 mcp_server.py                              # stdio
python3 mcp_server.py --http 8192                  # streamable http
```

Public endpoints: `POST https://rta.lat/mitracore/mcp` (JSON-RPC 2.0), plus `/v1/verify`, `/v1/quote`, `/v1/trust-report`, `/v1/skills/lint`, `/health`.

## Guard a paying agent (before the call, not after)

`guard/` sits in front of the agent and decides before the money moves: daily
budget, per-call cap, payee and network allowlists, kill switch. Every decision —
allow and deny — is an Ed25519-signed journal line, chained so a deleted record
is visible.

```bash
cp guard/policy.example.json guard/policy.json    # budget, caps, allowlists
python -m guard.proxy --policy guard/policy.json --amount 0.25 \
  --payee 0x1111111111111111111111111111111111111111 --network base \
  --cmd "<the call you are buying>"
python -m guard.proxy --policy guard/policy.json --verify   # signatures + chain
touch guard/KILL                                            # stop everything now
```

Exit codes: `0` allowed and the command ran, `2` denied (the command never ran,
the refusal is in the journal), `3` journal does not verify.

Python:

```python
from guard import Policy, authorize
decision = authorize({"amount_usd": 0.25, "payee": "0x1111…", "network": "base"},
                     Policy.load("guard/policy.json"))
assert decision["decision"] == "allow"
```

The key is generated on first run at `guard/keys/guard.key` (0600), the public
half sits next to it at `guard/keys/guard.pub`. Nothing is spent and nothing is
sent anywhere: the decision is local.

## Tools

`verify_work(artifact, schema?)` | `check_skill(path)` | `quote_cost(tokens, cpu_seconds, bytes_out, storage_writes, external_calls)` | `trust_report(artifact, schema?)` | `suite_status()`

## Pricing

- 20 verifications per day - free, no card, no account
- 0.005 USDC per verification (x402), or 9 USDC for 30 days prepaid
- 49 USD per environment per month (prepaid, no auto-renewal)

## Locales

`en`, `hi` - Hindi is a first-class interface, not a translation afterthought. India (Bharata) is included in pricing, docs and launch from day one; legal claims about India are taken only from official repositories, anything unverified is reported as pending.

## Trust

Receipts are Ed25519-signed and the key fingerprint is published: any buyer can verify a completion locally, offline, without an account.

License: MIT
