#!/usr/bin/env python3
"""Страница /agents — один экран (SPEC §6).

Три цифры и живая форма: человек вводит действие, видит вердикт и шесть
проверок. Честность: 24 проверки — это весь Suite, здесь живут 6; на
странице это сказано, а не спрятано.
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Trust Suite — one check before the money moves</title>
<meta name="description" content="Mandate, payee, asset, amount, receipt, replay: one verdict before an agent spends. Allow, deny, or a human.">
<style>
:root{--bg:#0b0d12;--card:#141821;--line:#232a38;--ink:#e8ecf4;--dim:#8d97ad;
--accent:#6ea8fe;--warn:#f0a35e;--ok:#5fd08a;--bad:#f07171;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:48px 24px 96px}
h1{font-size:34px;line-height:1.2;margin:0 0 10px}
h2{font-size:21px;margin:44px 0 12px;padding-top:20px;border-top:1px solid var(--line)}
.kicker{color:var(--dim);font-size:13px;letter-spacing:.08em;text-transform:uppercase;margin:0 0 14px}
.lede{color:var(--dim);font-size:18px;margin:0 0 28px}
.stats{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0 8px}
.stat{flex:1 1 180px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.stat b{display:block;font-size:30px;line-height:1.1}
.stat span{color:var(--dim);font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:12px 0}
.card b{color:var(--accent)}
.muted{color:var(--dim);font-size:14px}
code{font-family:var(--mono);font-size:13px;background:#0e1219;padding:1px 5px;border-radius:4px}
a{color:var(--accent)}
form{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin:18px 0 6px}
label{flex:1 1 200px;font-size:13px;color:var(--dim)}
input{width:100%;margin-top:5px;padding:10px 12px;border-radius:8px;border:1px solid var(--line);
background:#0e1219;color:var(--ink);font:15px var(--mono)}
button{cursor:pointer;padding:11px 18px;border-radius:8px;border:1px solid #2f5e9e;
background:#17325a;color:#dce9ff;font-size:15px;font-weight:600}
button:hover{background:#1c3d6d}
.verdict{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:600;font-size:15px;margin:20px 0 8px}
.v-allow{background:#12301f;color:var(--ok);border:1px solid #1f5136}
.v-deny{background:#33161a;color:var(--bad);border:1px solid #5c2329}
.v-needs_human{background:#2c2313;color:var(--warn);border:1px solid #5a4520}
table{width:100%;border-collapse:collapse;margin:8px 0 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:500}
td.r{font-family:var(--mono);font-size:12px;white-space:nowrap}
.pass{color:var(--ok)}.fail{color:var(--bad)}.unknown{color:var(--warn)}
pre{background:#0e1219;border:1px solid var(--line);border-radius:8px;padding:14px 16px;
overflow-x:auto;font-family:var(--mono);font-size:12px;line-height:1.5}
</style></head><body><div class="wrap">

<p class="kicker">mitracore · Agent Trust Suite</p>
<h1>Your agent spends without a limit. We fix that.</h1>
<p class="lede">One call before the money moves. Mandate, payee, asset, amount,
receipt, replay — one answer: allow, deny, or a human.</p>

<div class="stats">
  <div class="stat"><b>24</b><span>checks in the Suite</span></div>
  <div class="stat"><b>1</b><span>verdict per action</span></div>
  <div class="stat"><b>$99</b><span>per month</span></div>
</div>

<h2>Four layers, one door</h2>
<div class="card"><b>Input — skilllint.</b> Signed skill and publisher, permissions
(files, network, processes), secret access, prompt injection in the description,
tool description vs code, skill changed after install. 6 checks.</div>
<div class="card"><b>Rule — drift.</b> Mandate exists and has not expired, payee is
allowed, asset and network are allowed, amount is within the per-call limit, day
and month limits hold, no replay. 6 checks.</div>
<div class="card"><b>Enforcement — KARTA.</b> Human approval threshold, rate limit,
kill switch, idempotency, cascade stop, every block written down with a reason. 6 checks.</div>
<div class="card"><b>Evidence — attest.</b> Receipt signature and key, transaction
exists, amount and payee match the mandate, time inside the mandate, no double
counting. 6 checks.</div>
<p class="muted">The demo below runs six of the 24 — the rule layer plus the receipt
check: mandate, payee, asset and network, amount, signature, replay. The other 18
are the next slices, and this page will say so until they are live.</p>

<h2>Check a test action</h2>
<form id="f">
  <label>agent_id<input id="agent" value="agent-demo-1" autocomplete="off"></label>
  <label>amount, USDC<input id="amount" type="number" step="0.01" min="0" value="12.5"></label>
  <label>payee<input id="payee" value="0x1111111111111111111111111111111111111111" autocomplete="off" spellcheck="false"></label>
  <button type="submit">Check the agent</button>
</form>
<p class="muted">Test mandate on this page: USDC on Base, one payee
<code>0x1111111111111111111111111111111111111111</code>, cap $50 per call, valid
until 31 Dec 2026. Set the amount to 500 or change the payee to see a deny.</p>
<div id="out"></div>

<h2>API</h2>
<pre>POST https://rta.lat/mitracore/api/trust/check
{"agent_id":"…","action":{"type":"payment","amount_usd":12.5,"payee":"0x…",
 "asset":"USDC","network":"base","tx_hash":"0x…"},
 "mandate":{"mandate_id":"…","agent_id":"…","expires_at":"2026-12-31T00:00:00Z"},
 "limits":{"payees":["0x…"],"assets":["USDC"],"networks":["base"],"max_amount_usd":50},
 "receipt":{"payload":{},"signature":"…","public_key":"…"}}
→ {"verdict":"allow|deny|needs_human",
   "checks":[{"id":7,"name":"mandate active","result":"pass","reason":"expires …"}],
   "receipt":{…}}</pre>
<p class="muted">No key, no account. Missing field is <code>unknown</code>, never a
crash; a deny carries the reason. MCP tools:
<a href="https://rta.lat/mitracore/mcp">rta.lat/mitracore/mcp</a>.</p>

</div><script>
const LIMITS = {payees:["0x1111111111111111111111111111111111111111"],
  assets:["USDC"], networks:["base"], max_amount_usd:50};
const form = document.getElementById("f"), out = document.getElementById("out");

function row(c){
  const tr = document.createElement("tr");
  const cell = (text, cls) => {
    const td = document.createElement("td");
    td.textContent = text;
    if (cls) td.className = cls;
    return td;
  };
  tr.append(cell(String(c.id), "r"), cell(c.name), cell(c.result, c.result),
            cell(c.reason || ""));
  return tr;
}

function render(data){
  out.textContent = "";
  const chip = document.createElement("div");
  chip.className = "verdict v-" + data.verdict;
  chip.textContent = data.verdict;
  out.append(chip);

  const table = document.createElement("table");
  const head = document.createElement("tr");
  ["#", "check", "result", "reason"].forEach(h => {
    const th = document.createElement("th");
    th.textContent = h;
    head.append(th);
  });
  table.append(head);
  (data.checks || []).forEach(c => table.append(row(c)));
  out.append(table);

  if (data.receipt){
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Receipt " + data.receipt.receipt_id + " · "
      + (data.receipt.signature ? "signed, " + data.receipt.algorithm : "unsigned");
    out.append(p);
  }
}

form.addEventListener("submit", async e => {
  e.preventDefault();
  const agent_id = document.getElementById("agent").value.trim();
  const body = {
    agent_id,
    action: {type:"payment", amount_usd: Number(document.getElementById("amount").value),
             payee: document.getElementById("payee").value.trim(),
             asset:"USDC", network:"base"},
    mandate: {mandate_id:"demo-mandate-1", agent_id, expires_at:"2026-12-31T23:59:59Z"},
    limits: LIMITS
  };
  out.textContent = "checking…";
  try {
    const r = await fetch("api/trust/check", {method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
    render(await r.json());
  } catch (err) {
    out.textContent = "request failed: " + err;
  }
});
</script></body></html>"""
