"""Страница /scan — оффер аудита агентских интеграций (EN)."""
PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent integration scan — RTA</title>
  <meta name="description" content="We read the code and tell you where an agent can be made to move money it shouldn't. $99 per repository, 48 hours.">
  <style>
    :root{--ink:#1b1b1b;--muted:#5b5b5b;--line:#e6e0d6;--paper:#f7f4ee;--accent:#1f4d3a;}
    body{margin:0;font:17px/1.6 ui-serif,Georgia,serif;color:var(--ink);background:var(--paper);}
    main{max-width:720px;margin:0 auto;padding:48px 20px 64px;}
    h1{font-size:34px;line-height:1.15;margin:0 0 12px;}
    h2{font-size:22px;margin:36px 0 8px;}
    p.lead{font-size:20px;color:var(--muted);margin:0 0 28px;}
    table{width:100%;border-collapse:collapse;margin:12px 0 20px;}
    th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top;}
    th{color:var(--muted);font-weight:600;font-size:14px;}
    ul{padding-left:20px;}
    .cta{margin-top:32px;padding:18px 20px;border:1px solid var(--line);background:#fff;}
    a{color:var(--accent);}
    .note{color:var(--muted);font-size:15px;}
  </style>
</head>
<body><main>
  <h1>Agent integration scan</h1>
  <p class="lead">Your agent can move money. We read the code and tell you where it can be made to move money it shouldn't.</p>

  <h2>What you get</h2>
  <p>A written report, 48 hours after we receive the repository.</p>
  <ul>
    <li><b>Entry points</b> — every place your agent accepts a command, a tool call, or a payment (<code>x402</code>, <code>pay_to</code>, MCP tools).</li>
    <li><b>Leaks</b> — keys, tokens, private keys, secrets committed to the repository.</li>
    <li><b>Logic</b> — whether spending is bounded: budget, per-call cap, payee allowlist, kill-switch, signed journal. Where it isn't, we say so.</li>
    <li><b>Findings with levels</b> — <i>confirmed</i> (we point at the line), <i>likely</i> (pattern present, context unclear), <i>hypothesis</i> (no defence found, needs manual review).</li>
  </ul>
  <p>Every finding includes the file and line. No vague “consider improving security”.</p>

  <h2>Price</h2>
  <table>
    <tr><th>Scope</th><th>Price</th><th>Time</th></tr>
    <tr><td>One repository</td><td><b>$99</b></td><td>48 hours</td></tr>
    <tr><td>Contour: repository + MCP server + payment policy</td><td><b>$299</b></td><td>72 hours, includes a 40-minute call</td></tr>
  </table>
  <p class="note">Payment in USDC on Base or by invoice. No subscription.</p>

  <h2>What we do not do</h2>
  <ul>
    <li>We do not exploit findings or touch anyone else's systems.</li>
    <li>We do not replace a formal audit or a pentest.</li>
    <li>We do not claim your system is secure. We report what we found and what we did not check.</li>
  </ul>

  <h2>Why us</h2>
  <p>We build the same controls we check for. Our guard layer — daily budget, per-call cap, payee allowlist, kill-switch, Ed25519-chained journal — is open source, and our own scan found a command-injection path in it. We fixed it and published the fix. That is the standard we hold your report to.</p>

  <div class="cta">
    <b>Start:</b> send the repository URL to <a href="mailto:hello@rta.lat?subject=scan">hello@rta.lat</a> with the subject <code>scan</code>. You get a one-line confirmation, then the report.
    <p class="note">Private code? We sign an NDA first.</p>
  </div>
</main></body></html>
'''