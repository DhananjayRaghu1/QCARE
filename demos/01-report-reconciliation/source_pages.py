"""Read-only, linkable source pages for the synthetic demo records."""
from html import escape
import json
import re

from catalog import documents, get_document

STATUS_HELP = {
    "approved": "Approved. Check that its customer, file version and effective dates apply to the ticket.",
    "draft": "A proposal only. It does not authorize a reporting rule or define a supported file format.",
    "pending_approval": "Someone requested a change, but the business owner has not approved it.",
    "done": "This Jira task is complete. That does not mean every customer switched formats or that older rules disappeared.",
}


def scope_text(doc):
    scope = doc["scope"]
    if "feed" in scope:
        return "ATLAS transaction exports" + (" · file version " + scope["schema_version"] if "schema_version" in scope else " · all file versions")
    customer = "Customers using the standard reporting profile" if scope.get("customer") == "*" else scope.get("customer", "Unspecified customer")
    return customer + " · net sales"


def linked_text(text):
    pattern = r"\b(" + "|".join(re.escape(key) for key in sorted(documents(), key=len, reverse=True)) + r")\b"
    return re.sub(pattern, lambda match: '<a href="/documents/' + match[0] + '">' + match[0] + '</a>', escape(text))


def render_document(document_id):
    snapshot = get_document(document_id)
    if snapshot["status"] != "ok":
        return None
    doc = snapshot["document"]
    e = escape
    end = "No end date is specified." if not doc["effective_to"] else "Stops applying on " + doc["effective_to"] + " (that date is excluded)."
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(doc['title'])} · Demo source</title>
<style>body{{font:16px/1.75 system-ui,sans-serif;background:#f5f4ee;color:#193b38;margin:0}}main{{max-width:850px;margin:auto;padding:32px 24px}}a{{color:#276648}}article{{background:#fffefb;border:1px solid #dce2d7;border-radius:14px;padding:28px;margin-top:22px}}h1{{font-size:30px;line-height:1.3}}h2{{font-size:18px}}.note{{background:#edf3e6;padding:14px;border-radius:8px}}.meta{{font-size:14px}}.body{{white-space:pre-wrap}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace}}small{{overflow-wrap:anywhere}}dt{{font-weight:700}}dd{{margin:0 0 12px}}</style></head><body><main>
<a href="/">← Back to the live demo</a><article><p class="meta">SYNTHETIC SOURCE · {e(doc['system'].replace('_', ' '))} · {e(doc['id'])}</p><h1>{e(doc['title'])}</h1>
<p class="note">{e(STATUS_HELP[doc['status']])}</p><dl class="meta"><dt>Owner</dt><dd>{e(doc['owner'])}</dd><dt>Applies to</dt><dd>{e(scope_text(doc))}</dd><dt>Effective period</dt><dd>From {e(doc['effective_from'])}, inclusive. {e(end)}</dd><dt>Record version</dt><dd>{e(doc['version'])}</dd></dl>
<h2>Complete original source text</h2><p class="body">{linked_text(doc['body'])}</p>
<p class="note"><b>What is ATLAS?</b> The fictional upstream system that supplies transaction export files in this demo. It is separate from the reporting application and the AI. These are local sample documents, not records from a live company account.</p>
<details><summary>Underlying fixture record and verification hash</summary><p>The guided calculator uses the hand-authored <code>rules</code> mapping below. Raw docs mode receives the prose and metadata, without that mapping.</p><pre>{e(json.dumps(doc, indent=2))}</pre><small>SHA256: {snapshot['sha256']}</small></details></article></main></body></html>'''
