# mitracore — listing copy and price rationale

**Rule from the tablets:** the brand is second, the task is first. Nobody searches for "mitracore"; people search for "verify AI agent output", "LLM cost tracking", "agent permission gate".

## Price: $49 per environment / month (prepaid, no auto-renewal), 20 verifications/day free, 0.005 USDC per call, 9 USDC / 30 days

### Why this number (facts, with sources)

1. **Category anchor.** Spend on agent state/memory runs $19–399/mo (Mem0 Pro $249, Zep Flex $125 / Flex Plus $375, supermemory Scale $399); durable execution $75–1,000/mo (Restate); enterprise SLA starts at $500/mo (Temporal). $49 sits in the middle of the self-serve band and well below enterprise. Source: `research/2026/СПРОС-ПАМЯТЬ-АГЕНТОВ.md` (primary pricing pages, 08.10.2026).
2. **The buyer.** The budget that exists for this job is an engineer's: ShopMy $145–225k/yr, Moment $200–400k/yr for someone who builds and owns agent memory/durability — $15–35k/mo of human budget for that function. $49/mo is 0.1–0.3% of it. We are not selling API calls, we are selling engineering confidence.
3. **Price of the error.** One "reported done, actually empty" artifact means the work is redone: from an engineer-hour to several days ≈ $100–2,000. A $49/month subscription pays for itself with **one** prevented rework. This is the formula the tablets ask for: price of verification vs price of error.
4. **Our cost.** Verification is local (SQLite + Swiss Ephemeris, no GPU). $0.001–0.01 per call → margin above 95% at $0.005/call on top of the free tier.
5. **Deliberate dumping on entry.** 20/day free with no card and no account removes all friction; $9 for 30 days is the one-off trial; $49/mo is the standing price. We buy logos and case studies first, not maximum margin on the first hundred customers.
6. **The risk, stated plainly.** "Teams will pay for private verification of agent work" is a **hypothesis** in our own methodology, not a fact. Test: 3 paying customers within 30 days at the free tier. If they don't come: drop to $29 (dump price) or sell enterprise contracts ($25–50k/yr) — do not build a new product.
7. **Market context.** Gartner: 40% of agentic projects will be cancelled by end-2027 (cost, unclear value, weak risk control); Stack Overflow 2026: 7% of developers trust AI output for important decisions; Gartner: only 26% of organisations see AI costs in real time. We sell the reduction of those three risks, not features.

## Listing titles (task first, brand second)

| Channel | Title |
|---|---|
| Glama / Smithery / mcp.so | `mitracore — verify AI agent output, meter its cost, enforce its mandate (MCP)` |
| api.market | `Artifact verification + cost metering + mandate enforcement for AI agents` |
| Product Hunt | `Prove an agent did the work — before you pay for it` |
| Dev.to / HN article | `Seven percent of developers trust AI output. Here's the layer that fixes it.` |

## Short description (all channels)

```
Three risks, one call. Verify the artifact (schema, emptiness, provenance, authority), meter what the run actually cost, and keep the agent inside its mandate. Receipts are Ed25519-signed and verify offline — no trust in us required.

20 verifications/day free, no card. 0.005 USDC per call, 9 USDC/30 days, or $49 per environment per month.

Locales: en, hi. India (Bharata) is supported from day one.
```

## Long description (marketplaces)

```
A team that ships agent work usually discovers three separate problems, and solves each with a different tool: the agent says it finished, but the artifact is empty or unprovable; the LLM bill is a surprise; the agent can do what it was not allowed to do.

mitracore is one endpoint for all three.

1. verify — four layers over the artifact: schema conformance, emptiness (uniform lists, stub values, truncations), generation provenance, and authority (was the action permitted at all). A JSON Schema validator passes five identical stubs; this does not.
2. quote — send what the call actually consumed (tokens, CPU seconds, bytes out, storage writes, external calls) and get the price from a published rate card, with the breakdown attached, so both sides see the same arithmetic.
3. mandates — limits, allowlist and kill switch for what an agent is allowed to do.

Every verdict carries an Ed25519-signed receipt. The key fingerprint is published, so a buyer can verify any completion locally, without an account and without trusting this service.

Pricing: 20 verifications per day free with no card, 0.005 USDC per verification, 9 USDC for 30 days prepaid, or $49 per environment per month. No auto-renewal: we do not pretend a payment rail can do recurring charges it cannot do.

Locales: en, hi. India (Bharata) is covered in pricing, docs and launch from day one.
```

## Channels and status

| Channel | State | Owner step |
|---|---|---|
| Glama / Smithery / mcp.so | manifests ready in `listing/` | submit (GitHub login) |
| api.market | attest already in review; mitracore next | — |
| Apify | actor packaging after mitracore | link GitHub repo |
| Agensi | skill for drift, $29 | owner: Google login + KYC |
| Product Hunt | text ready | owner: submit |
| Dev.to / HN | text ready | publish via API / owner post |

## Facts to state as facts, everything else as hypothesis

- Signed receipts, offline verification, no account needed: **implemented and tested**.
- 40% agentic project cancellations (Gartner, 2027), 7% developer trust (Stack Overflow 2026), 26% cost visibility (Gartner 2026): **third-party figures, dated**.
- Willingness to pay $49/mo: **hypothesis** until three customers pay.
