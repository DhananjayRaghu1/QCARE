"""Portable presentation of executed, synthetic deterministic results; no network assets."""
from html import escape

from catalog import cases, documents
from reconcile import reconcile_case
from demo import money


def render():
    options, panels = [], []
    for index, (case_id, case) in enumerate(cases().items()):
        report = reconcile_case(case, documents())
        options.append(f'<option value="{case_id}">{escape(case_id + " · " + case["title"])}</option>')
        stats = ''.join(f'<div class="stat"><span>{label}</span><strong>{money(value)}</strong></div>' for label, value in (
            ('Current report', report['reported_total_cents']), ('Customer claim', report['customer_claim_cents']),
            ('Approved-rule result', report['expected_total_cents'])))
        rows = ''.join(f'<tr class="{"error" if row["difference_cents"] else ""}"><td>{escape(row["row_id"])}</td>'
            f'<td>{money(row["raw_amount_cents"])}</td><td>{money(row["observed_cents"])}</td>'
            f'<td>{money(row["expected_cents"])}</td><td>{escape(row["feed_source"])}</td><td>{escape(row["reason"].replace("_", " "))}</td></tr>'
            for row in report['ledger'])
        ledger = ('<div class="table-wrap"><table><thead><tr><th>Row</th><th>Raw</th><th>Current</th>'
                  '<th>Correct</th><th>Format contract</th><th>Period / inclusion</th></tr></thead><tbody>' + rows + '</tbody></table></div>') if rows else (
                  '<div class="stop">Calculation stopped: the evidence does not support an authoritative total.</div>')
        sources = []
        for source_id, snapshot in report['source_snapshots'].items():
            doc = snapshot['document']
            sources.append(f'<details><summary><b>{escape(source_id)}</b> · {escape(doc["title"])}</summary>'
                f'<div class="source"><p class="metadata">{escape(doc["system"])} · {escape(doc["status"])} · '
                f'{escape(doc["owner"])} · effective {escape(doc["effective_from"])} to {escape(doc["effective_to"] or "open-ended")} (end exclusive)</p>'
                f'<p>{escape(doc["body"])}</p><small>SHA256 {snapshot["sha256"]}</small></div></details>')
        messages = ''.join(f'<p class="message">{escape(message)}</p>' for message in report['messages'])
        row_status = ', '.join(report['problem_rows']) or ('none' if report['ledger'] else 'not established')
        raw_rows = ''.join(f'<tr><td>{escape(row["id"])}</td><td>{escape(row["kind"])}</td><td>{escape(row["schema_version"])}</td>'
            f'<td>{money(row["amount_cents"])}</td><td>{escape(row["invoice_on"])}</td><td>{escape(row["posted_on"])}</td></tr>' for row in case['rows'])
        panels.append(f'<section id="{case_id}" {"hidden" if index else ""}><div class="eyebrow">{escape(case["customer"])} / {case["month"]} / USD</div>'
            f'<h2>{escape(case["title"])}</h2><p class="ticket">{escape(case["ticket"])}</p>'
            f'<div class="stats">{stats}</div><div class="decision">{escape(report["decision"].replace("_", " "))}</div>'
            f'<h3>Trace the result to each row</h3>{ledger}{messages}'
            f'<p><b>Problem rows:</b> {escape(row_status)}</p>'
            f'<div class="action"><b>Next action</b><p>{escape(report["next_action"])}</p></div>'
            f'<h3>Inspect the business evidence</h3>{"".join(sources)}'
            f'<details><summary>Raw input and deployed configuration</summary><div class="source"><p>Assigned profile: {escape(case["report_profile"])}. '
            f'Deployed date basis: {escape(case["deployed_config"]["date_basis"])}. Included types: {escape(", ".join(case["deployed_config"]["included_kinds"]))}.</p>'
            f'<div class="table-wrap"><table><thead><tr><th>Row</th><th>Type</th><th>Schema</th><th>Amount</th><th>Invoice</th><th>Posted</th></tr></thead><tbody>{raw_rows}</tbody></table></div></div></details></section>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Report reconciliation · Data Honey demo</title><style>
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172e30;background:#f4f6f2}*{box-sizing:border-box}body{margin:0}
header{background:#183e3c;color:#fff;padding:36px max(24px,calc((100vw - 1080px)/2))}header p{max-width:760px;color:#d9e7de;line-height:1.6}h1{font-size:clamp(28px,4vw,40px);margin:10px 0}main{max-width:1128px;margin:auto;padding:28px 24px}h2{font-size:28px;margin:12px 0}h3{margin-top:28px;font-size:18px}.eyebrow{font-size:12px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:#64786c}header .eyebrow{color:#b9d9cc}
label{display:block;font-size:13px;font-weight:700;margin-bottom:8px}select{width:100%;background:#fff;border:1px solid #bbcbc0;border-radius:8px;padding:14px;font:inherit;color:inherit;margin-bottom:28px}
section{background:#fff;border:1px solid #dce4dc;border-radius:16px;padding:28px}.ticket{line-height:1.6;color:#586963}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}.stat{background:#f1f5ef;border:1px solid #e1e9df;border-radius:10px;padding:18px}.stat span{display:block;font-size:13px}.stat strong{display:block;font-size:clamp(21px,3vw,30px);margin-top:8px}.decision{display:inline-block;background:#dcebe0;border-radius:100px;padding:8px 14px;font-size:13px;font-weight:700;text-transform:capitalize}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}th,td{text-align:left;padding:12px;border-bottom:1px solid #e2e8e0}th{background:#f3f6f0;color:#53655c;font-size:12px}tr.error{background:#fff1df}tr.error td:first-child{font-weight:800}.action{border-left:4px solid #247364;background:#edf6f0;padding:18px;margin:24px 0}.action p{line-height:1.6;margin:8px 0 0}.stop,.message{padding:16px;background:#fff1df;border-radius:8px;line-height:1.6}
details{border:1px solid #dce4dc;border-radius:8px;margin:10px 0}summary{padding:16px;cursor:pointer;font-size:14px}.source{padding:0 18px 18px;line-height:1.7}.metadata{font-size:12px;color:#52675c}small{font-size:10px;overflow-wrap:anywhere;color:#6a796f}footer{font-size:12px;line-height:1.7;color:#65736b;margin:24px 0 40px}section[hidden]{display:none}@media(max-width:650px){.stats{grid-template-columns:1fr}section{padding:18px}main{padding:18px 12px}}
</style></head><body><header><div class="eyebrow">Demo 1 · synthetic evidence</div><h1>Which total can we defend?</h1><p>A report discrepancy becomes a decision, a row-by-row explanation, and a justified next action using approved business rules, source contracts, Jira context, and application behavior.</p></header><main><label for="case">Choose a support case</label><select id="case">''' + ''.join(options) + '</select>' + ''.join(panels) + '''<footer>Executed deterministic workflow with hand-authored, structured policies. No model calls or live Jira/Docs connection. Human review pending.<br>These ten synthetic cases demonstrate behavior; they do not measure employee productivity or prove AI outperforms an analyst.</footer></main><script>document.getElementById('case').addEventListener('change',function(){document.querySelectorAll('section').forEach(s=>s.hidden=s.id!==this.value)});</script></body></html>'''
