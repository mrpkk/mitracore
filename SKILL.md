---
name: mitracore
description: Use when an agent's work must be checked before it counts as done, when the cost of an agent run must be attributed, or when an agent must be kept inside its mandate. Verifies artifacts, meters real consumption, exposes signed receipts.
---

# mitracore

Trust layer for agent work. Three capabilities that teams otherwise assemble by hand.

## When to use
- A teammate or client says "the agent finished" and you need proof the artifact is not empty, and is not something else.
- The LLM bill is a surprise and per-request cost has to be attributed to real consumption.
- An agent holds keys or funds and you need limits, an allowlist, and a kill switch.

## Tools
- `verify_work(artifact, schema?)` — four layers: schema, emptiness, generation provenance, authority. Returns verdict, trust score, violations, and an Ed25519-signed receipt that verifies offline.
- `check_skill(path)` — private lint of a SKILL.md: structure, trigger, dead instructions, secret-shaped literals, prompt-injection markers, broken references, unbounded autonomy. Nothing leaves the machine; returns verdict, score and sha256.
- `quote_cost(tokens, cpu_seconds, bytes_out, storage_writes, external_calls)` — price the call from a published rate card, with the breakdown attached.
- `trust_report(artifact, schema?)` — verification + cost + mandate availability in one answer.
- `suite_status()` — live state of every layer.

## How to use it
1. Call `verify_work` on the artifact before accepting the work.
2. If the verdict is `reject`, read `violations` — they name the layer and the exact defect (uniform list, stub value, missing provenance, unauthorised action).
3. If the artifact is paid work, attach the receipt: the buyer verifies it locally, no trust in this service needed.
4. For recurring cost, call `quote_cost` per run and report the breakdown next to the verdict.
5. For agents with keys, enforce the mandate with `drift` (limits, allowlist, kill switch).

## Pricing
20 verifications/day free (no card, no account) · 0.005 USDC per verification · 9 USDC / 30 days prepaid · 49 USD per environment per month.

## Notes
- Signed receipts use Ed25519; the key fingerprint is public, so verification is possible offline.
- `check_skill` is private by construction: it inspects locally and returns only a verdict and a hash.
- Locales: `en`, `hi`. India (Bharata) is supported from day one; legal claims about India require official sources, otherwise report `pending`.
