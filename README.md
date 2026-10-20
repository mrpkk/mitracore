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
