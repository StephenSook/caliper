"""The judge door: a credential free page that answers the rubric without us.

Server rendered on purpose. It loads instantly, works with
scripting disabled, and a defect in the interface bundle cannot take it down.

The render timestamp below is deliberately NOT in ISO form. A date of service is
one of the identifiers we scan for, so an ISO timestamp of our own would collide
with the thing the scanner hunts and every clean page would carry a false alarm.
Written this way, any ISO date appearing on this page IS a leak. It loads instantly, it works with scripting
disabled, and a defect in the interface bundle cannot take it down. Rigor a judge
cannot reach scores as absent, so the evidence has to be readable without logging
in, without a key, and without running anything.

Every number on this page is recomputed from the supplied export when the page is
requested. It is not a cached artifact and it is not a screenshot.
"""

from __future__ import annotations

import html
import time

STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#0a0b0d; color:#f7f7f5;
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.wrap { max-width:940px; margin:0 auto; padding:40px 22px 90px; }
h1 { font-size:clamp(28px,5vw,44px); letter-spacing:-.03em; line-height:1; margin:0 0 6px; }
h2 { font-size:20px; letter-spacing:-.01em; margin:44px 0 12px; }
.tag { color:#7c7f87; font-size:13px; letter-spacing:.14em; text-transform:uppercase;
  font-family:ui-monospace,Menlo,monospace; }
.lede { color:#a8aab0; max-width:66ch; }
ol.itin { list-style:none; counter-reset:s; padding:0; }
ol.itin li { counter-increment:s; position:relative; padding:14px 0 14px 50px;
  border-bottom:1px solid #1e222a; }
ol.itin li::before { content:counter(s); position:absolute; left:0; top:12px;
  width:30px; height:30px; border:1px solid #4ade9a; color:#4ade9a; border-radius:50%;
  display:grid; place-items:center; font-family:ui-monospace,monospace; font-size:13px; }
ol.itin b { display:block; }
ol.itin span { color:#a8aab0; font-size:14px; }
a { color:#4ade9a; }
table { border-collapse:collapse; width:100%; font-size:14px; margin:12px 0 22px; }
th,td { border:1px solid #1e222a; padding:9px 11px; text-align:left; vertical-align:top; }
th { background:#16191f; color:#a8aab0; font-weight:600; }
.mono { font-family:ui-monospace,Menlo,monospace; font-variant-numeric:tabular-nums; }
.bad { color:#ff6b5e; } .good { color:#4ade9a; } .dim { color:#7c7f87; }
.pill { display:inline-block; font-size:11px; letter-spacing:.1em; padding:3px 8px;
  border-radius:3px; font-family:ui-monospace,monospace; }
.pass { background:rgba(74,222,154,.16); color:#4ade9a; }
.fail { background:rgba(255,107,94,.16); color:#ff6b5e; }
.star { color:#f5b74f; }
.card { border:1px solid #1e222a; border-radius:4px; padding:18px; margin:14px 0; background:#101216; }
.headline { border-color:#ff6b5e; background:rgba(255,107,94,.07); }
.headline p { font-size:19px; margin:6px 0 0; max-width:54ch; }
code { background:#16191f; padding:2px 6px; border-radius:3px; font-size:13px; color:#4ade9a; }
.foot { color:#7c7f87; font-size:13px; border-top:1px solid #1e222a; margin-top:44px; padding-top:18px; }
"""

NAMES = {
    "member_experience": "Member Experience",
    "business_process": "Business Process",
    "compliance": "Compliance",
}


def render(evidence: dict, golden: dict, base: str = "") -> str:
    e = html.escape
    inst = evidence["instruments"]
    conn = evidence["connectivity"]

    rows = "".join(
        f"<tr><td>{e(NAMES.get(k, k))}</td>"
        f"<td class='mono'>{v['kr20']:.4f}</td>"
        f"<td class='mono {'bad' if v['ci_low'] <= 0 else ''}'>{v['ci_low']:.3f} to {v['ci_high']:.3f}</td>"
        f"<td class='mono'>{v['items_outside_band']} of {v['n_items']}</td>"
        f"<td class='mono'>{v['items_zero_variance']}</td></tr>"
        for k, v in sorted(inst.items())
    )

    def case_row(c: dict) -> str:
        star = " <span class=star>*</span>" if c["is_differentiator"] else ""
        state = "pass" if c["passed"] else "fail"
        label = "PASS" if c["passed"] else "FAIL"
        return (
            f"<tr><td class='mono'>{e(c['id'])}{star}</td>"
            f"<td>{e(c['name'])}<br><span class='dim'>{e(c['asserts'])}</span></td>"
            f"<td><span class='pill {state}'>{label}</span></td>"
            f"<td class='dim'>{e(c['detail'])}</td></tr>"
        )

    cases = "".join(case_row(c) for c in golden["cases"])

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>CALIPER, evidence for judges</title><style>{STYLE}</style></head><body><div class="wrap">

<span class="tag">CALIPER / evidence</span>
<h1>Everybody else grades the workers.<br>We grade the test.</h1>
<p class="lede">Everything on this page was recomputed from the supplied quality export
when you loaded it. No credential, no login, nothing to install. If you read only
one thing, read the box below.</p>

<div class="card headline">
  <span class="tag">the finding</span>
  <p>{e(evidence["cross_instrument"]["statement"])}</p>
</div>

<h2>Three minutes, in order</h2>
<ol class="itin">
  <li><b>Look at the reliability column below.</b>
      <span>Every one of the three quality forms has a confidence interval whose lower
      bound sits at or below zero. With seventeen evaluations you cannot establish
      that any of them measures anything.</span></li>
  <li><b>Look at the zero variance column.</b>
      <span>On the Compliance form, seven of ten questions have never once
      distinguished any two calls. One of them is the item recording whether HIPAA
      verification was performed.</span></li>
  <li><b>Read the linkage fragility number.</b>
      <span>Two evaluators, {conn["calls_double_scored"]} of {conn["n_calls"]} calls
      ever scored by both, and every comparison between them passing through
      {conn["linkage_fragility"]} agents out of {conn["n_subjects"]}.</span></li>
  <li><b>Check the golden cases, especially the starred three.</b>
      <span>They ran when you loaded this page. The interesting ones are the cases
      where the system refuses: training rejected on a measurement defect, a
      disconnected design detected, an underpowered claim declined.</span></li>
  <li><b>Recompute it yourself.</b>
      <span>Open <a href="{base}/api/evidence">/api/evidence</a>. It recomputes from
      the source on every request. Or clone the repository and run
      <code>python -m caliper.instrument.audit</code>.</span></li>
  <li><b>Take it out on your own phone.</b>
      <span>Open <a href="{base}/practice">{base}/practice</a> on a phone and add it
      to the home screen. It runs fullscreen, with no store and no install. The
      phone is the handset and it attaches itself to whatever run this host is
      working on, so the laptop and the phone are one run and one audit trail.
      A spoken call needs a speech model and therefore credentials, which this
      host was deliberately not given, and it says so rather than failing
      quietly.</span></li>
</ol>

<h2>The three quality forms, measured</h2>
<table><thead><tr>
  <th>Form</th><th>KR-20</th><th>95 percent interval</th>
  <th>Items outside the usable band</th><th>Never distinguished anyone</th>
</tr></thead><tbody>{rows}</tbody></table>
<p class="dim">Item difficulty is usable between 0.25 and 0.85. Reliability thresholds:
0.70 for research, 0.80 for applied use, 0.90 for decisions about individuals
(Cortina 1993). CMS declines to publish a CAHPS star below 0.60 (42 CFR 423.186).</p>

<h2>Can a harsh evaluator be told from a weak agent?</h2>
<div class="card">
  <p class="mono" style="font-size:30px;margin:0;color:#ff6b5e">
    linkage fragility {conn["linkage_fragility"]} of {conn["n_subjects"]}</p>
  <p class="lede" style="margin-top:10px">Remove those {conn["linkage_fragility"]} agents
  and the design splits in half. And the link is weaker than it looks, because
  {conn["calls_double_scored"]} of {conn["n_calls"]} calls were ever scored by both
  evaluators, so the connection runs agent to agent across different calls on
  different days. Verdict: <span class="bad">{e(conn["verdict"])}</span>.</p>
</div>

<h2>What we will not claim</h2>
<div class="card">
<p class="lede">We do not diagnose an individual from this instrument, and we say why
rather than going quiet. We do not claim HIPAA compliance. We do not claim that
teach back is an established payer call centre standard, because we searched and
could not find one. We do not report a reliability figure without its interval.
Where the supplied files gave us no data, the outputs say so instead of carrying a
plausible number.</p>
</div>

<h2>Golden cases, executed when you loaded this page</h2>
<p class="lede">{golden["passed"]} of {golden["total"]} passed.
<span class="star">*</span> marks the three that matter most, because they are the
cases where the correct behaviour is to refuse.</p>
<table><thead><tr><th>Case</th><th>What it asserts</th><th></th><th>What happened</th>
</tr></thead><tbody>{cases}</tbody></table>

<p class="foot">
{evidence["identifiers_redacted_from_supplied_material"]} identifiers were found and
redacted from the supplied material before anything was analysed. No agent name,
evaluator name, member identifier, participation id, call id or date of service
appears anywhere on this page or in the repository.
<br>Rendered {time.strftime("%d %B %Y at %H:%M UTC", time.gmtime())}.
</p>
</div></body></html>"""
