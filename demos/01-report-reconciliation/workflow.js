'use strict';
// Demo 2 engineering workflow (LangGraph). Uses portfolio.js helpers ($, esc, api, download, demo, config) at call time.
// Wrapped so its names cannot collide with portfolio.js globals such as poll(); only mountWorkflow is exported.
(() => {
const wf = {graph:null, recordings:[], run:null, events:[], cursor:0, status:'idle', pending:null, result:null, meta:null, replay:null,
  starting:false, pendingKey:null, summaryKey:null, cards:new Map(), lazy:new Map(), timer:null, inflight:false, follow:true, live:{}};
const STRIP = ['intake','analyze','ask_developer','implement','review','check_requirements','developer_review','finalize'];
const PERSON = new Set(['ask_developer','developer_review']);
const LOOP = new Set(['implement','review','check_requirements']);
const HIDDEN_STEPS = new Set(['prepare_summary']);
const SPEED = 8;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const money = value => value == null ? '' : '$' + Number(value).toFixed(2);
const secs = value => value == null ? '' : value >= 90 ? `${Math.floor(value / 60)}m ${Math.round(value % 60)}s` : `${Number(value).toFixed(1)}s`;
const workspacePath = path => String(path || '').replace(/^.*?(datahoney-(workflow|review)-[^/]+\/repo|datahoney-(workflow|review)-[^/]+|<workspace>\/repo|<workspace>)\/?/, '');

function srcChip(id){
  if(!id) return '';
  if(id === 'developer-note') return '<span class="wf-src developer">Developer note</span>';
  const source = wf.graph?.sources?.[id];
  if(!source) return `<span class="wf-src code">${esc(id)}</span>`;
  const title = `${source.title} · ${source.status} · ${source.owner}`;
  if(id === 'DH-401') return `<span class="wf-src jira" title="${esc(title)}">${esc(id)}</span>`;
  const dialog = demo.documents.some(doc => doc.id === id);
  return `<a class="wf-src ${esc(source.system)} ${esc(source.status)}" href="/documents/${encodeURIComponent(id)}" ${dialog ? `data-source="${esc(id)}"` : 'target="_blank" rel="noopener"'} title="${esc(title)}">${esc(id)}</a>`;
}
function linkIds(root){
  const ids = Object.keys(wf.graph?.sources || {}).sort((a, b) => b.length - a.length);
  if(!ids.length || !root) return;
  const regex = new RegExp('\\b(' + ids.map(id => id.replace(/[-]/g, '\\-')).join('|') + ')\\b', 'g');
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), nodes = [];
  let node;
  while(node = walker.nextNode()) if(!node.parentElement.closest('a,button,textarea,pre,code,summary,.wf-src,label')) nodes.push(node);
  for(const item of nodes){
    regex.lastIndex = 0;
    if(!regex.test(item.textContent)) continue;
    const span = document.createElement('span');
    span.innerHTML = esc(item.textContent).replace(regex, match => srcChip(match));
    item.replaceWith(...span.childNodes);
  }
}
function badge(text, tone){ return `<span class="wf-badge ${tone}">${esc(text)}</span>`; }
// Large sections (prompts, raw JSON, full activity) are built only when someone opens them.
function lazy(key, summary, html){ wf.lazy.set(key, html); return `<details data-key="${esc(key)}" data-lazy="${esc(key)}"><summary>${summary}</summary><div class="wf-lazy"></div></details>`; }
function fillLazy(details){
  const slot = details.querySelector(':scope > .wf-lazy');
  if(details.open && slot && !slot.childElementCount && wf.lazy.has(details.dataset.lazy)){ slot.innerHTML = wf.lazy.get(details.dataset.lazy); linkIds(slot); }
}

function skeleton(){
  return `<span class="eyebrow">ENGINEERING WORKFLOW · LIVE CLAUDE SESSIONS</span>
<h2>From a Jira ticket to a reviewed pull request, with you in the loop</h2>
<p>Claude reads the business records, writes the change and has it reviewed. Rules in code decide when it is done, and you make every decision. Nothing is merged or deployed.</p>
<ol class="wf-strip" id="wfStrip"></ol>
<details class="wf-engineer"><summary>For engineers: the compiled LangGraph, tools and limits <span class="small">(at most <span id="wfMaxRounds">3</span> build rounds)</span></summary><div id="wfGraphDetail"></div></details>
<div class="grid two wf-inputs"><article id="wfTicket"></article><article id="wfStart"></article></div>
<div id="wfStatus" class="wf-status hidden" role="status" aria-live="polite"></div>
<div id="wfPending"></div>
<div id="wfTimeline" class="wf-timeline"></div>
<div id="wfSummary"></div>`;
}

function renderGraphDetail(){
  const g = wf.graph;
  const tools = {intake:'No model. Code fetches the ticket and its linked issue, clones the repository onto a new branch.', analyze:'Read, Glob, Grep + Jira and Confluence lookups (read-only MCP). A re-check after your input returns only what changed.', ask_developer:'No model. LangGraph interrupt() waits for you; the recommended option or “I don’t know” applies in code.', implement:'Read, Glob, Edit, Write; shell limited to python3, ls, git status/diff/log/show/add/commit/push, and gh pr create/view/list only when a PR was requested.', review:'Read, Glob, Grep; shell limited to python3, ls and read-only git, in a disposable copy with no remote. Judges every requirement.', check_requirements:'No model. Rules in code: tests pass, every requirement met, no high or medium finding, branch pushed, PR rules.', prepare_summary:'No model. Builds the summary and runs the demo-only grading.', developer_review:'No model. LangGraph interrupt() waits for you.', finalize:'No model. Marks the draft PR ready for review if there is one. Never merges.'};
  $('#wfGraphDetail').innerHTML = `<p class="small">Orchestrated with LangGraph and drawn from the compiled graph (<code>engineering_workflow.build_graph()</code>). Every Claude step uses <b>${esc(g.model)}</b>, a JSON schema for its output, a per-step budget and timeout, and a $${g.budget_cap} cap for the whole workflow.</p>
<div class="table-wrap"><table class="wf-table"><thead><tr><th>Step</th><th>Tools</th><th>Limit</th></tr></thead><tbody>${g.nodes.map(n => `<tr><td><b>${esc(n.title)}</b><br><code>${esc(n.id)}</code></td><td>${esc(tools[n.id] || '')}</td><td>${g.limits[n.id] ? `$${g.limits[n.id].budget_usd} · ${g.limits[n.id].timeout_seconds}s` : '—'}</td></tr>`).join('')}</tbody></table></div>
<p class="small">Edges: ${g.edges.filter(e => !e.source.startsWith('__') && !e.target.startsWith('__')).map(e => `${esc(e.source)} → ${esc(e.target)}${e.conditional ? ' (conditional)' : ''}`).join(' · ')}</p>
<p class="small">Retrieval: the ticket and its explicit links are fetched by code. The analyst then searches all ${Object.keys(g.sources).length} synthetic Jira and Confluence records (from all three demos) and must open a complete record before citing it. Every quoted requirement is checked word-for-word against a record the workflow actually opened, using the record's SHA256. No vector index is needed at this size.</p>`;
}

function recordingLabel(r){
  const h = r.headline || {};
  return `${r.developer_note ? '“' + r.developer_note + '”' : 'no note'}${h.pr ? ' · PR' : ''} · ${new Date(r.recorded_at).toLocaleString([], {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'})}`;
}
function renderInputs(){
  const t = wf.graph.ticket, rows = JSON.parse(demo.files['sample.json']);
  $('#wfTicket').innerHTML = `<span class="eyebrow">INPUT 1 · JIRA TICKET (SYNTHETIC)</span><h3>${srcChip(t.id)} ${esc(t.title)}</h3>
<p class="small">${esc(t.issue_type)} · ${esc(t.status.replaceAll('_', ' '))} · owner ${esc(t.owner)} · reported by ${esc(t.reporter)}</p>
<p>The one-paragraph request shown at the top of this page. <a href="#request">Read it</a>.</p>
<p class="small"><b>Links:</b> ${t.links.map(link => esc(link.type) + ' ' + srcChip(link.id)).join(', ')} · <b>Attachment:</b> sample.json (${rows.length} transactions)<br><b>Repository:</b> ${wf.graph.sandbox_repo ? `<a href="https://github.com/${esc(wf.graph.sandbox_repo)}" target="_blank" rel="noopener">${esc(wf.graph.sandbox_repo)}</a> (private sandbox)` : 'local sandbox remote'}; a new branch per run.</p>`;
  const recordings = [...wf.recordings].sort((a, b) => String(b.recorded_at).localeCompare(String(a.recorded_at)));
  $('#wfStart').innerHTML = `<span class="eyebrow">INPUT 2 · YOU</span>
<label class="wf-label" for="wfNote">Developer note (optional). Treated as guidance, not business approval.</label>
<textarea id="wfNote" maxlength="2000" placeholder="For example: Use UTC to keep it simple. Open a draft PR when it’s ready."></textarea>
<div class="actions"><button id="wfRun">Run workflow →</button><button id="wfStop" class="secondary hidden">Stop</button></div>
${recordings.length ? `<div class="wf-replay"><select id="wfRecording" aria-label="Recorded run">${recordings.map(r => `<option value="${esc(r.name)}">${esc(recordingLabel(r))}</option>`).join('')}</select><button id="wfReplay" class="secondary">Replay</button></div>` : ''}
<p class="small">Live: real Claude sessions using your login · ${esc(wf.graph.model)} · at most ${wf.graph.max_rounds} build rounds · $${wf.graph.budget_cap} cap. Replay: saved events from a real run, no model called.</p>
<p id="wfError" class="error" role="alert"></p>`;
  $('#wfRun').onclick = startWorkflow;
  $('#wfStop').onclick = stopWorkflow;
  if($('#wfReplay')) $('#wfReplay').onclick = () => startReplay($('#wfRecording').value);
  linkIds($('#wfTicket'));
}

function viewModel(events){
  const steps = [], byId = new Map();
  const view = {steps, grading:null, status:null, errors:[], finished:null, waiting:null, handoff:null};
  for(const e of events){
    if(e.kind === 'step_started'){ const s = {id:e.step, node:e.node, title:e.title, purpose:e.purpose, round:e.round, started:e.seconds, notes:[], lookups:[], tools:[], messages:[], status:'running'}; steps.push(s); byId.set(e.step, s); continue; }
    const s = e.step ? byId.get(e.step) : null;
    if(s && typeof e.seconds === 'number') s.last = e.seconds;
    switch(e.kind){
      case 'note': s?.notes.push(e); break;
      case 'prompt': if(s) s.prompt = e; break;
      case 'session': if(s) s.model = e.model; break;
      case 'lookup': s?.lookups.push({...e, result:null}); break;
      case 'lookup_result': { const item = s?.lookups.find(l => l.tool_id === e.tool_id); if(item) item.result = e.text; break; }
      case 'tool_call': s?.tools.push({...e, result:null}); break;
      case 'tool_result': { const item = s?.tools.find(t => t.tool_id === e.tool_id); if(item) item.result = e; break; }
      case 'message': s?.messages.push(e.text); break;
      case 'grounding': if(s) s.grounding = e; break;
      case 'tests': if(s) s.tests = e; break;
      case 'git': if(s) s.git = e; break;
      case 'denied': if(s) (s.denied ||= []).push(e); break;
      case 'developer_response': if(s) s.response = e.texts; break;
      case 'step_finished': if(s) Object.assign(s, {status:e.status, output:e.output, metric:e.metric, finished:e.seconds, diff:e.diff, files:e.files, errors:e.errors}); break;
      case 'route': if(s) s.route = e; break;
      case 'handoff': view.handoff = e.git; break;
      case 'grading': view.grading = e; break;
      case 'waiting': view.waiting = e; break;
      case 'resumed': view.waiting = null; break;
      case 'status': view.status = e.text; break;
      case 'error': view.errors.push(e.text); break;
      case 'finished': view.finished = e; break;
    }
  }
  return view;
}

function renderStrip(view){
  const counts = {}, done = new Set();
  let current = null;
  for(const s of view?.steps || []){ counts[s.node] = (counts[s.node] || 0) + 1; if(s.status === 'running') current = s.node; else done.add(s.node); }
  if(view?.waiting) current = view.waiting.payload?.kind === 'review' ? 'developer_review' : 'ask_developer';
  if(current === 'prepare_summary') current = 'developer_review';
  const finished = Boolean(view?.finished);
  const handoff = view?.handoff ? (view.handoff.pr ? (view.handoff.pr.isDraft ? 'draft PR' : 'PR ready for review') : 'branch pushed') : '';
  const html = STRIP.map((id, index) => {
    const node = wf.graph.nodes.find(n => n.id === id);
    const state = id === current && !finished ? (PERSON.has(id) ? 'waiting' : 'active') : done.has(id) ? 'done' : (finished || done.has('implement')) && id === 'ask_developer' && !counts[id] ? 'skipped' : '';
    const extra = LOOP.has(id) && counts[id] > 1 ? `<em>round ${counts[id]}</em>` : id === 'ask_developer' && state === 'skipped' ? '<em>not needed</em>'
      : id === 'ask_developer' && !counts[id] ? '<em>only if blocked</em>' : id === 'finalize' && handoff ? `<em>${esc(handoff)}</em>` : '';
    return `<li class="wf-node ${state} ${PERSON.has(id) ? 'person' : ''} ${LOOP.has(id) ? 'loop' : ''}" title="${esc(node?.purpose)}"><span class="wf-dot">${state === 'done' ? '✓' : index + 1}</span><b>${esc(node?.title)}</b>${extra}</li>`;
  }).join('');
  if(html !== wf.stripHtml){ $('#wfStrip').innerHTML = html; wf.stripHtml = html; }
}

function friendlyTool(tool){
  const input = tool.input || {};
  switch(tool.name){
    case 'Read': return 'Read ' + workspacePath(input.file_path);
    case 'Edit': case 'MultiEdit': return 'Edited ' + workspacePath(input.file_path);
    case 'Write': return 'Wrote ' + workspacePath(input.file_path);
    case 'Bash': return 'Ran ' + (input.description ? input.description + ': ' : '') + String(input.command || '').replace(/\S*datahoney-(workflow|review)-[^/\s]+\/(repo\/?)?/g, '').slice(0, 160);
    case 'Glob': return 'Listed files matching ' + (input.pattern || '');
    case 'Grep': return 'Searched the code for “' + (input.pattern || '') + '”';
    default: return tool.name;
  }
}
function lookupList(s){
  if(!s.lookups.length) return '';
  return `<ul class="wf-lookups">${s.lookups.map(l => `<li><span class="wf-sys ${esc(l.system)}">${l.system === 'jira' ? 'Jira' : 'Confluence'}</span><span>${esc(l.text)}${l.result ? `<span class="wf-result"> → ${esc(l.result)}</span>` : ' <span class="wf-spinner">…</span>'}</span></li>`).join('')}</ul>`;
}
function toolList(s){
  if(!s.tools.length) return '';
  const recent = s.tools.slice(-6);
  return `<ul class="wf-tools">${s.tools.length > recent.length ? `<li class="small">${s.tools.length - recent.length} earlier actions in the activity log below</li>` : ''}${recent.map(t => `<li class="${t.result?.error ? 'bad' : ''}">${esc(friendlyTool(t))}${t.result ? (t.result.error ? ' — failed' : '') : ' <span class="wf-spinner">…</span>'}</li>`).join('')}</ul>`;
}
function citationBadge(status){
  return {verified:badge('quote verified', 'good'), inferred:badge('inferred', 'warn'), not_found:badge('quote not found', 'bad'), not_read:badge('record not opened', 'bad'), unknown_source:badge('unknown source', 'bad')}[status] || '';
}
function conflictList(conflicts){
  return `<ul class="wf-conflicts">${conflicts.map(c => `<li class="wf-conflict ${esc(c.status)}">${badge(c.status === 'blocking' ? 'needs a decision' : 'resolved', c.status === 'blocking' ? 'bad' : 'good')} <b>${esc(c.summary)}</b><ul>${c.sides.map(side => `<li>${srcChip(side.source_id)} ${esc(side.says)}</li>`).join('')}</ul><p class="small">${esc(c.resolution)}${c.owner ? ' · Rule owner: ' + esc(c.owner) : ''}</p></li>`).join('')}</ul>`;
}
function requirementTable(requirements, cites){
  return `<div class="table-wrap"><table class="wf-table"><thead><tr><th>ID</th><th>Requirement and its acceptance test</th><th>Source</th><th>Exact words in the source</th></tr></thead><tbody>${requirements.map(r => `<tr><td>${esc(r.id)}</td><td>${esc(r.text)}<br><small>Test: ${esc(r.acceptance)}</small></td><td>${srcChip(r.source_id)}<br>${badge(r.authority, r.authority === 'approved' ? 'good' : 'warn')}</td><td>${r.quote ? `<q>${esc(r.quote)}</q><br>` : ''}${citationBadge(cites[r.id]?.status)}</td></tr>`).join('')}</tbody></table></div>`;
}
function analysisView(s){
  const a = s.output, cites = Object.fromEntries((s.grounding?.results || []).map(r => [r.requirement, r]));
  if(a.added) return deltaView(s, cites);
  return `<p class="wf-plain">${esc(a.plain_summary)}</p>
${s.grounding ? `<p class="wf-ground ${s.grounding.verified === s.grounding.checkable ? 'good' : 'warn'}">${s.grounding.verified === s.grounding.checkable ? '✓' : '!'} ${esc(s.grounding.text)}</p>` : ''}
<h4>Requirements it established</h4>${requirementTable(a.requirements, cites)}
${a.conflicts.length ? `<h4>Conflicts it checked</h4>${conflictList(a.conflicts)}` : '<p class="small">No conflicts found.</p>'}
${a.current_behavior.length ? `<details data-key="${s.id}-today"><summary>What the code does today</summary><ul>${a.current_behavior.map(line => `<li>${esc(line)}</li>`).join('')}</ul></details>` : ''}
${a.out_of_scope.length ? `<details data-key="${s.id}-scope"><summary>Deliberately out of scope (${a.out_of_scope.length})</summary><ul>${a.out_of_scope.map(o => `<li>${esc(o.item)} ${srcChip(o.source_id)} — ${esc(o.reason)}</li>`).join('')}</ul></details>` : ''}`;
}
function deltaView(s, cites){
  const d = s.output, changes = [...d.added.map(r => ({...r, change:'added'})), ...d.changed.map(r => ({...r, change:'changed'}))];
  return `${s.grounding ? `<p class="wf-ground ${s.grounding.verified === s.grounding.checkable ? 'good' : 'warn'}">${s.grounding.verified === s.grounding.checkable ? '✓' : '!'} ${esc(s.grounding.text)}</p>` : ''}
${changes.length ? `<h4>What changed</h4>${requirementTable(changes, cites)}` : '<p class="small">No requirement changed.</p>'}
${d.removed.length ? `<p class="small">Removed: ${d.removed.map(esc).join(', ')}</p>` : ''}
${d.conflicts.length ? `<h4>Conflicts</h4>${conflictList(d.conflicts)}` : ''}`;
}
function gitLine(git){
  if(!git) return '';
  const branch = git.branch_url ? `<a href="${esc(git.branch_url)}" target="_blank" rel="noopener"><code>${esc(git.branch)}</code></a>` : `<code>${esc(git.branch)}</code>`;
  const pr = git.pr ? ` · <a href="${esc(git.pr.url)}" target="_blank" rel="noopener">${git.pr.isDraft ? 'Draft ' : ''}PR #${git.pr.number}</a> opened by the agent` : '';
  const commits = (git.commits || []).map(c => `<li><code>${esc(c.sha)}</code> ${esc(c.subject)}</li>`).join('');
  return `<p class="wf-ground ${git.pushed && git.clean && git.main_unchanged ? 'good' : 'bad'}">${git.pushed && git.clean ? '✓' : '✗'} ${esc(git.text)}<br><small>Branch ${branch}${pr}</small></p>${commits ? `<details data-key="git-${esc(git.head)}"><summary>Commits on the branch (${(git.commits || []).length})</summary><ul>${commits}</ul></details>` : ''}`;
}
function deniedLine(s){
  if(!s.denied?.length) return '';
  return `<ul class="wf-denied">${s.denied.map(d => `<li>${esc(d.text)}</li>`).join('')}</ul>`;
}
function testsLine(tests, key){
  if(!tests) return '';
  const passed = tests.total - tests.failed;
  return `<p class="wf-ground ${tests.passed ? 'good' : 'bad'}">${tests.passed ? '✓' : '✗'} ${esc(tests.text || `${passed} of ${tests.total} tests passed`)}</p>${tests.cases?.length ? `<details data-key="${key}-tests"><summary>Test names</summary><ul class="wf-cases">${tests.cases.map(c => `<li class="${c.status === 'passed' ? '' : 'bad'}">${c.status === 'passed' ? '✓' : '✗'} <code>${esc(c.name)}</code>${c.existing ? ' <small>existing</small>' : ''}</li>`).join('')}</ul></details>` : ''}`;
}
function implementView(s){
  const o = s.output;
  return `<p class="wf-plain">${esc(o.summary)}</p>
<ul>${o.changes.map(c => `<li><code>${esc(c.file)}</code> ${esc(c.change)} <small>${c.requirement_ids.map(esc).join(', ')}</small></li>`).join('')}</ul>
${testsLine(s.tests, s.id)}
${gitLine(s.git)}
${s.diff ? `<details data-key="${s.id}-diff"><summary>The change (${(s.files || []).map(esc).join(', ')})</summary><pre>${esc(s.diff)}</pre></details>` : ''}
${o.assumptions.length ? `<details data-key="${s.id}-assume"><summary>Assumptions it made (${o.assumptions.length})</summary><ul>${o.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></details>` : ''}
${o.not_done.length ? `<p class="notice"><b>Not done:</b> ${o.not_done.map(esc).join(' · ')}</p>` : ''}`;
}
function findingList(findings){
  return `<ul class="wf-findings">${findings.map(f => `<li>${badge(f.severity, f.severity === 'high' ? 'bad' : f.severity === 'medium' ? 'warn' : 'muted')} <b>${esc(f.id)}</b> <span class="small">${esc(f.category.replaceAll('_', ' '))} · ${esc(f.location)}</span><p>${esc(f.evidence)}</p>${f.suggested_fix ? `<p class="small">Suggested fix: ${esc(f.suggested_fix)}</p>` : ''}${f.needs_owner_decision ? ' ' + badge('needs the rule owner', 'person') : ''}</li>`).join('')}</ul>`;
}
function statusGrid(requirements){
  return `<div class="wf-reqs">${requirements.map(r => `<span class="wf-req ${esc(r.status)}" title="${esc(r.evidence)}">${esc(r.id)} · ${esc(r.status)}</span>`).join('')}</div>`;
}
function reviewView(s){
  const o = s.output;
  return `<p>${badge(o.verdict === 'approve' ? 'approve' : 'changes required', o.verdict === 'approve' ? 'good' : 'warn')} ${esc(o.summary)}</p>
${statusGrid(o.requirements)}
${o.findings.length ? findingList(o.findings) : '<p class="small">No findings.</p>'}
<details data-key="${s.id}-evidence"><summary>Evidence for each requirement</summary><ul>${o.requirements.map(r => `<li><b>${esc(r.id)}</b> ${esc(r.status)} — ${esc(r.evidence)}</li>`).join('')}</ul></details>
<details data-key="${s.id}-claims"><summary>Engineer's claims it checked (${o.verified_claims.length})</summary><ul>${o.verified_claims.map(c => `<li>${c.verified ? '✓' : '✗'} ${esc(c.claim)} <span class="small">— ${esc(c.how)}</span></li>`).join('')}</ul></details>`;
}
function checkView(s){
  const o = s.output;
  return `<p>${badge(o.decision === 'accept' ? 'accepted' : 'sent back', o.decision === 'accept' ? 'good' : 'warn')} <span class="small">Decided by rules in code, not by a model.</span></p>
${statusGrid(o.requirements)}
${o.guard.length ? `<h4>Rules not yet met</h4><ol>${o.guard.map(item => `<li>${esc(item)}</li>`).join('')}</ol>` : ''}`;
}
function found(s){
  if(s.status === 'failed') return `<p class="notice">${(s.errors || []).map(esc).join(' ')}</p>`;
  if(s.response) return `<p class="wf-response">${s.response.map(esc).join('<br>')}</p>`;
  if(!s.output) return '';
  return {analyze:analysisView, implement:implementView, review:reviewView, check_requirements:checkView}[s.node]?.(s) || '';
}
function idleLine(s){
  // Long quiet stretches are the model writing its structured answer; say so instead of looking stuck.
  const now = wf.replay ? null : wf.meta?.elapsed_seconds;
  if(now == null || s.last == null || now - s.last < 4 || !s.prompt) return '';
  const doing = {analyze:'Writing up the requirements and conflicts', implement:'Working on the code and tests', review:'Testing the change and judging each requirement'}[s.node] || 'Working';
  return `<p class="small wf-idle"><span class="wf-spinner">●</span> ${esc(doing)} · ${Math.round(now - s.last)}s since its last action</p>`;
}
const noteItem = n => `<li class="${n.tone === 'warning' ? 'warn' : n.tone === 'control' ? 'control' : ''}">${esc(n.text)}</li>`;
function stepCard(s){
  const meta = [s.round ? 'Round ' + s.round : '', s.model || s.metric?.models?.[0] || '', secs(s.metric?.seconds), money(s.metric?.cost_usd)].filter(Boolean).join(' · ');
  const activity = s.lookups.length + s.tools.length + s.messages.length;
  const more = [
    activity ? lazy(`${s.id}-activity`, `Everything it did (${plural(s.lookups.length, 'lookup')}, ${plural(s.tools.length, 'tool call')})`,
      `<ol class="wf-activity">${s.lookups.map(l => `<li>${esc(l.text)} → ${esc(l.result || '…')}</li>`).join('')}${s.tools.map(t => `<li>${esc(friendlyTool(t))}${t.result ? `<pre>${esc(typeof t.result.content === 'string' ? t.result.content : JSON.stringify(t.result.content, null, 2))}</pre>` : ''}</li>`).join('')}${s.messages.map(m => `<li class="small">“${esc(m)}”</li>`).join('')}</ol>`) : '',
    s.prompt ? lazy(`${s.id}-prompt`, 'Exact prompt and permissions', `<p class="small">Tools: ${s.prompt.tools.map(esc).join(', ') || 'none'} · budget $${s.prompt.budget_usd} · timeout ${s.prompt.timeout_seconds}s · model ${esc(s.prompt.model)}</p><pre>${esc(s.prompt.text)}</pre>`) : '',
    s.output && s.prompt ? lazy(`${s.id}-json`, 'Raw structured output (JSON)', `<pre>${esc(JSON.stringify(s.output, null, 2))}</pre>`) : ''].join('');
  return `<article class="wf-step ${esc(s.status)} ${PERSON.has(s.node) ? 'person' : ''}" id="step-${esc(s.id)}" data-step="${esc(s.id)}">
<div class="wf-head"><span class="wf-step-no">${STRIP.indexOf(s.node) + 1}</span><div><h3>${esc(s.title)}</h3><p class="small">${esc(s.purpose)}</p></div><span class="wf-meta">${esc(meta)}${s.status === 'running' ? ' <span class="wf-spinner">working…</span>' : ''}</span></div>
${s.notes.length ? `<ul class="wf-notes">${s.notes.slice(0, 3).map(noteItem).join('')}</ul>${s.notes.length > 3 ? lazy(`${s.id}-notes`, `${s.notes.length - 3} more notes`, `<ul class="wf-notes">${s.notes.slice(3).map(noteItem).join('')}</ul>`) : ''}` : ''}
${lookupList(s)}${deniedLine(s)}${s.status === 'running' ? toolList(s) + idleLine(s) : ''}
${found(s)}
${s.route ? `<p class="wf-route"><b>Next: ${esc(s.route.to_title)}.</b> ${esc(s.route.reason)}</p>` : ''}
${more ? `<div class="wf-more">${more}</div>` : ''}
</article>`;
}

function renderTimeline(view, running, current){
  // Keyed update: only cards whose content changed are replaced, so open sections and scroll position survive polling.
  const timeline = $('#wfTimeline');
  let changedCurrent = false;
  for(const s of view.steps.filter(step => !HIDDEN_STEPS.has(step.node))){
    const html = stepCard(s);
    if(wf.cards.get(s.id) === html) continue;
    wf.cards.set(s.id, html);
    const existing = timeline.querySelector(`[data-step="${CSS.escape(s.id)}"]`);
    const open = existing ? new Set([...existing.querySelectorAll('details[data-key][open]')].map(d => d.dataset.key)) : new Set();
    const holder = document.createElement('div');
    holder.innerHTML = html;
    const card = holder.firstElementChild;
    card.querySelectorAll('details[data-key]').forEach(d => { if(open.has(d.dataset.key)){ d.open = true; fillLazy(d); } });
    existing ? existing.replaceWith(card) : timeline.append(card);
    linkIds(card);
    if(current && s.id === current.id) changedCurrent = true;
  }
  if(running && current && changedCurrent && wf.follow) document.getElementById('step-' + current.id)?.scrollIntoView({block:'nearest', behavior:'smooth'});
}

function questionsPanel(payload, replay){
  const sources = payload.conflicts.map(c => `<li class="wf-conflict blocking"><b>${esc(c.summary)}</b><ul>${c.sides.map(side => `<li>${srcChip(side.source_id)} ${esc(side.says)}</li>`).join('')}</ul>${c.owner ? `<p class="small">Rule owner: ${esc(c.owner)}</p>` : ''}</li>`).join('');
  const questions = payload.questions.map(q => `<fieldset class="wf-question" data-question="${esc(q.id)}"><legend>${esc(q.question)}</legend><p class="small">Why it matters: ${esc(q.why)} · Rule owner: ${esc(q.owner)}</p>${q.options.map(o => `<label class="wf-option ${o.id === '__unknown__' ? 'unknown' : ''}"><input type="radio" name="wfq-${esc(q.id)}" value="${esc(o.id)}" ${(replay ? replay.choices?.[q.id] === o.id : o.id === q.recommended_option) ? 'checked' : ''} ${replay ? 'disabled' : ''}><span><b>${esc(o.label)}</b>${o.id === q.recommended_option ? ' ' + badge('recommended', 'good') : ''}<br><small>${esc(o.consequence)}</small></span></label>`).join('')}</fieldset>`).join('');
  return `<section class="wf-needs"><span class="eyebrow">THE WORKFLOW NEEDS YOU</span><h3>${esc(payload.title)}</h3><p>${esc(payload.summary)}</p>${sources ? `<ul class="wf-conflicts">${sources}</ul>` : ''}${questions || '<p>The analyst could not settle the requirements. Tell the workflow how to proceed.</p>'}
<label class="wf-label">Note to the workflow (optional)<textarea id="wfAnswerNote" maxlength="2000" ${replay ? 'disabled' : ''}>${esc(replay?.message || '')}</textarea></label>
<div class="actions">${replay ? '<button id="wfContinue">Continue replay ▸</button><span class="small">Replaying the recorded answer.</span>' : '<button id="wfAnswer">Send my decision →</button><span class="small">The recommended option or “I don’t know” applies straight away. Another option or a note gets a short re-check first.</span>'}</div></section>`;
}

const clipText = (text, n = 150) => { text = String(text || ''); return text.length > n ? text.slice(0, n - 1).trimEnd() + '…' : text; };
function tldr(summary, opts){
  // Built from the result fields in code, never written by a model.
  const trace = summary.trace || [], met = trace.filter(r => r.status === 'met').length, t = summary.tests || {total:0, failed:0};
  const git = opts.finalGit || summary.git || {};
  const pr = git.pr ? `PR #${git.pr.number}` : null;
  const escalated = (summary.review?.findings || []).find(f => f.needs_owner_decision && f.severity !== 'low');
  const first = opts.final ? `Approved. ${pr ? pr + ' is ready for the team’s review' : 'The branch is pushed for the team’s review'}; nothing was merged.`
    : summary.outcome === 'accepted' ? `Done: the agents accepted the change after ${plural(summary.rounds_used, 'round')}${pr ? `; draft ${pr} is waiting for your approval` : '; the branch is waiting for your approval'}.`
    : summary.outcome === 'needs_decision' ? `Stopped for a rule owner: ${clipText(escalated?.evidence || 'a requirement can only be settled by its owner')}`
    : `Not accepted after ${plural(summary.rounds_used, 'round')}: it needs your direction.`;
  const second = `${met}/${trace.length} requirements met · ${t.total - t.failed}/${t.total} tests passing · ${summary.citations.verified}/${summary.citations.checkable} source quotes verified`;
  const third = summary.decisions?.length ? 'You decided: ' + summary.decisions.map(d => clipText(String(d).split(' → ').pop(), 110)).join('; ')
    : summary.risks?.length ? 'Check before merging: ' + clipText(summary.risks[0])
    : 'No decisions were needed.';
  return `<div class="wf-tldr"><span class="eyebrow">TL;DR</span><ul><li><b>${esc(first)}</b></li><li>${esc(second)}</li><li>${esc(third)}</li></ul></div>`;
}
function summaryPanel(summary, opts){
  const trace = summary.trace || [], met = trace.filter(r => r.status === 'met').length, t = summary.tests;
  const kpis = [[`${met}/${trace.length}`, 'requirements met'], [`${t.total - t.failed}/${t.total}`, 'tests passing'], [String(summary.rounds_used), summary.rounds_used === 1 ? 'build round' : 'build rounds'], [secs(summary.model_seconds), 'model time'], [money(summary.cost_usd), 'model cost']];
  const rounds = summary.rounds.map(r => `<li><b>Round ${r.round}:</b> tests ${r.tests.total - r.tests.failed}/${r.tests.total} · review ${plural(r.findings.length, 'finding')}${r.findings.length ? ' (' + r.findings.map(f => f.severity).join(', ') + ')' : ''} → <b>${r.decision === 'accept' ? 'accepted' : 'sent back'}</b>${r.guard.length ? `<ul>${r.guard.map(b => `<li>${esc(b)}</li>`).join('')}</ul>` : ''}</li>`).join('');
  const git = opts.finalGit || summary.git;
  const decide = opts.live ? `<div class="wf-decide"><h4>Your decision</h4><div class="actions"><button id="wfApprove">${summary.git?.pr ? 'Approve: mark the PR ready for review' : 'Approve'}</button><button class="secondary" id="wfShowRevise">Send it back…</button></div><div id="wfReviseBox" class="hidden"><label class="wf-label">What should change?<textarea id="wfRevise" maxlength="2000" placeholder="For example: Also test a refund that settles in a different month from the sale"></textarea></label><button class="secondary" id="wfSendBack">Send back with instructions →</button></div></div>` : '';
  const grading = opts.grading ? `<details data-key="sum-grading"><summary>Demo grading: hidden acceptance checks</summary><p class="small">${esc(opts.grading.label)}</p><p class="wf-ground ${opts.grading.passed ? 'good' : 'bad'}">${opts.grading.passed ? '✓' : '✗'} ${opts.grading.hidden_passed} of ${opts.grading.hidden_total} hidden acceptance checks passed${opts.grading.repository_passed ? ', and all repository tests passed' : ', but repository tests failed'}.</p></details>` : '';
  const where = git ? `<p class="wf-ground good">${git.branch_url ? `<a href="${esc(git.branch_url)}" target="_blank" rel="noopener"><code>${esc(git.branch)}</code></a>` : `<code>${esc(git.branch)}</code> (local sandbox)`}${git.pr ? ` · <a href="${esc(git.pr.url)}" target="_blank" rel="noopener">${git.pr.isDraft ? 'Draft ' : ''}PR #${git.pr.number}</a>` : git.pr_requested ? ' · PR requested but not open' : ' · no PR requested'}</p>` : '';
  const escalations = summary.review.findings.filter(f => f.needs_owner_decision && f.severity !== 'low').map(f => `<p class="notice"><b>Decision needed (${esc(f.id)}):</b> ${esc(f.evidence)}<br><small>${esc(f.suggested_fix)}</small></p>`).join('');
  return `<section class="wf-summary"><span class="eyebrow">RESULT</span>
${tldr(summary, opts)}
<div class="wf-kpis">${kpis.map(([value, label]) => `<div><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('')}</div>
${where}${escalations}
<h4>Each requirement, where it came from, and whether it is met</h4><div class="table-wrap"><table class="wf-table"><thead><tr><th>Requirement</th><th>Source</th><th>Status</th></tr></thead><tbody>${trace.map(r => `<tr><td><b>${esc(r.id)}</b> ${esc(r.text)}</td><td>${srcChip(r.source_id)} ${citationBadge(r.citation)}</td><td><span class="wf-req ${esc(r.status)}" title="${esc(r.evidence)}">${esc(r.status)}</span></td></tr>`).join('')}</tbody></table></div>
${decide}
<details class="wf-full" data-key="sum-full"><summary>Full details</summary>
<div class="grid two"><article><h4>In plain English</h4><p>${esc(summary.business)}</p></article><article><h4>For engineers</h4><ul>${summary.engineers.map(item => `<li>${esc(item)}</li>`).join('')}</ul></article></div>
<details data-key="sum-trace"><summary>Exact source quotes, code changes and evidence</summary><div class="table-wrap"><table class="wf-table"><thead><tr><th>Requirement and its test</th><th>Source and exact words</th><th>Code change</th><th>Evidence</th></tr></thead><tbody>${trace.map(r => `<tr><td><b>${esc(r.id)}</b> ${esc(r.text)}<br><small>${esc(r.acceptance || '')}</small></td><td>${srcChip(r.source_id)}${r.quote ? `<br><q>${esc(r.quote)}</q>` : ''}</td><td>${r.changes.map(esc).join('<br>') || '—'}</td><td><small>${esc(r.evidence)}</small></td></tr>`).join('')}</tbody></table></div></details>
${summary.overrides.length || summary.assumptions.length ? `<details data-key="sum-assume"><summary>Overrides and assumptions (${summary.overrides.length + summary.assumptions.length})</summary>${summary.overrides.length ? `<p class="notice"><b>Developer overrides that need sign-off:</b> ${summary.overrides.map(o => esc(o.summary) + ' — ' + esc(o.resolution)).join(' · ')}</p>` : ''}${summary.assumptions.length ? `<ul>${summary.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul>` : ''}</details>` : ''}
<details data-key="sum-conflicts"><summary>Conflicts, decisions and rounds</summary><div class="grid two"><article><h4>Conflicts and decisions</h4><ul>${summary.conflicts.map(c => `<li>${badge(c.status === 'blocking' ? 'was blocking' : 'resolved', c.status === 'blocking' ? 'warn' : 'good')} ${esc(c.summary)} <small>${esc(c.resolution)}</small></li>`).join('')}${summary.decisions.map(d => `<li>${badge('your decision', 'person')} ${esc(d)}</li>`).join('')}</ul></article><article><h4>How it got here</h4><ol>${rounds}</ol></article></div></details>
${summary.risks.length ? `<details data-key="sum-risks"><summary>Look at before merging (${summary.risks.length})</summary><ul>${summary.risks.map(r => `<li>${esc(r)}</li>`).join('')}</ul></details>` : ''}
<details data-key="sum-diff"><summary>The change: ${summary.files.map(esc).join(', ')}</summary><pre>${esc(summary.diff)}</pre><button class="secondary" id="wfPatch">Download patch</button></details>
<details data-key="sum-tests"><summary>Tests run by the workflow (${t.total})</summary><ul class="wf-cases">${t.cases.map(c => `<li class="${c.status === 'passed' ? '' : 'bad'}">${c.status === 'passed' ? '✓' : '✗'} <code>${esc(c.name)}</code>${c.existing ? ' <small>existing</small>' : ''}</li>`).join('')}</ul></details>
<details data-key="sum-review"><summary>Latest independent review (${plural(summary.review.findings.length, 'finding')})</summary><p>${esc(summary.review.summary)}</p>${findingList(summary.review.findings)}</details>
<details data-key="sum-cost"><summary>Time and cost by step</summary><table class="wf-table"><thead><tr><th>Step</th><th>Runs</th><th>Model time</th><th>Cost</th></tr></thead><tbody>${summary.steps.map(s => `<tr><td>${esc(s.title)}</td><td>${s.runs}</td><td>${secs(s.seconds)}</td><td>${money(s.cost_usd)}</td></tr>`).join('')}</tbody></table><p class="small">Model: ${summary.models.map(esc).join(', ')}. CLI-reported cost; the rules check is code and costs nothing. Time excludes your review.</p></details>
${grading}
${opts.download ? '<div class="actions"><button class="secondary" id="wfRecord">Download run record</button></div>' : ''}
</details>
<p class="small">Nothing is merged or deployed by this workflow.</p></section>`;
}

function keepOpen(root){ return new Set([...root.querySelectorAll('details[data-key][open]')].map(d => d.dataset.key)); }
function restoreOpen(root, open){ root.querySelectorAll('details[data-key]').forEach(d => { if(open.has(d.dataset.key)){ d.open = true; fillLazy(d); } }); }

function renderAll(){
  const replay = wf.replay;
  const events = replay ? replay.events : wf.events;
  const view = viewModel(events);
  renderStrip(view);
  const status = replay ? (replay.done ? 'replayed' : 'replaying') : wf.status;
  const running = !replay && (status === 'running' || status === 'stopping');
  const waiting = replay ? view.waiting : (status === 'waiting_for_developer' ? {payload: wf.pending?.payload, interrupt_id: wf.pending?.id} : null);
  const spentNow = view.steps.reduce((sum, s) => sum + (s.metric?.cost_usd || 0), 0);
  const modelTime = view.steps.reduce((sum, s) => sum + (s.metric?.seconds || 0), 0);
  const elapsed = replay ? (events.at(-1)?.seconds || 0) : (wf.meta?.elapsed_seconds || 0);
  const current = [...view.steps].reverse().find(s => s.status === 'running');
  const control = replay ? replay.rec.context === false : wf.meta?.context === false;
  const tag = control ? ' · <span class="wf-badge warn">control: no business context</span>' : '';
  const line = replay ? `<b>${replay.done ? 'Replay finished' : 'Replaying a recorded run'}</b>${tag} · recorded ${esc(new Date(replay.rec.recorded_at).toLocaleString())} · ${esc(replay.rec.model)} · ${SPEED}× speed · no model is called`
    : running ? `<b>Running</b>${tag} · ${current ? esc(current.title) : esc(view.status || 'Starting…')} · ${secs(elapsed)} · ${money(spentNow)} so far`
    : status === 'waiting_for_developer' ? `<b>Waiting for you</b>${tag} · model time ${secs(modelTime)} + your time · ${money(spentNow)} so far`
    : status === 'idle' ? '' : `<b>${esc(status === 'completed' ? 'Finished' : status)}</b>${tag} · model time ${secs(modelTime)} + your time = ${secs(wf.result?.elapsed_seconds)} · ${money(wf.result?.spent_usd ?? spentNow)}`;
  $('#wfStatus').classList.toggle('hidden', !line);
  const statusHtml = line + view.errors.map(e => `<p class="error">${esc(e)}</p>`).join('');
  if(statusHtml !== wf.statusHtml){ $('#wfStatus').innerHTML = statusHtml; wf.statusHtml = statusHtml; }
  renderTimeline(view, running, current);
  // The decision panel is rebuilt only when the question changes, so typing is never lost.
  const key = waiting ? (waiting.interrupt_id || 'replay') + ':' + (replay ? replay.i : '') : null;
  if(key !== wf.pendingKey){
    wf.pendingKey = key;
    const recorded = replay && waiting ? replay.rec.events.slice(replay.i).find(e => e.kind === 'resumed')?.response : null;
    $('#wfPending').innerHTML = waiting?.payload?.kind === 'questions' ? questionsPanel(waiting.payload, replay ? (recorded || {}) : null) : '';
    linkIds($('#wfPending'));
    if($('#wfAnswer')) $('#wfAnswer').onclick = sendAnswer;
    if($('#wfContinue')) $('#wfContinue').onclick = continueReplay;
    if(waiting?.payload?.kind === 'questions') $('#wfPending').scrollIntoView({block:'start', behavior:'smooth'});
  }
  const reviewWaiting = waiting?.payload?.kind === 'review';
  const summary = reviewWaiting ? waiting.payload.summary : (!replay ? wf.result?.summary : (replay.done ? replay.summary : null));
  const sumRoot = $('#wfSummary');
  const final = !replay ? wf.result?.outcome === 'approved' : replay.done && replay.approved;
  const summaryKey = summary ? JSON.stringify([reviewWaiting, final, Boolean(view.grading), status, Boolean(view.handoff)]) : null;
  if(summaryKey !== wf.summaryKey){
    wf.summaryKey = summaryKey;
    const sumOpen = keepOpen(sumRoot);
    sumRoot.innerHTML = summary ? summaryPanel(summary, {live: reviewWaiting && !replay, grading: view.grading || (!replay && wf.result?.grading), final,
      finalGit: view.handoff || (!replay && wf.result?.git), download: !replay && Boolean(wf.result)}) : '';
    restoreOpen(sumRoot, sumOpen);
    linkIds(sumRoot);
    if($('#wfApprove')) $('#wfApprove').onclick = () => sendReview('approve');
    if($('#wfSendBack')) $('#wfSendBack').onclick = () => sendReview('revise');
    if($('#wfShowRevise')) $('#wfShowRevise').onclick = () => { $('#wfReviseBox').classList.remove('hidden'); $('#wfRevise').focus(); };
    if($('#wfPatch')) $('#wfPatch').onclick = () => download('DH-401-workflow.patch', summary.diff);
    if($('#wfRecord')) $('#wfRecord').onclick = () => download('DH-401-workflow-' + wf.run + '.json', JSON.stringify({result:wf.result, events:wf.events}, null, 2));
    if(reviewWaiting && replay){ sumRoot.insertAdjacentHTML('beforeend', `<div class="actions"><button id="wfContinue2">Continue replay ▸</button><span class="small">Recorded answer: ${esc({approve:'approved', revise:'sent back'}[replay.rec.events.slice(replay.i).find(e => e.kind === 'resumed')?.response?.action] || 'stopped here, not approved')}</span></div>`); $('#wfContinue2').onclick = continueReplay; }
    if(reviewWaiting) sumRoot.scrollIntoView({block:'start', behavior:'smooth'});
  }
  const busy = wf.starting || running || status === 'waiting_for_developer' || (replay && !replay.done);
  $('#wfRun').disabled = busy;
  $('#wfNote').disabled = busy;
  if($('#wfReplay')) $('#wfReplay').disabled = Boolean(busy);
  $('#wfStop').classList.toggle('hidden', !(running || status === 'waiting_for_developer'));
}

function reset(){
  if(wf.replay?.timer) clearTimeout(wf.replay.timer);
  clearTimeout(wf.timer);
  Object.assign(wf, {replay:null, run:null, events:[], cursor:0, status:'idle', pending:null, result:null, meta:null, pendingKey:null, summaryKey:null, statusHtml:null, stripHtml:null, follow:true});
  wf.cards.clear(); wf.lazy.clear();
  $('#wfTimeline').innerHTML = ''; $('#wfPending').innerHTML = ''; $('#wfSummary').innerHTML = '';
}
function schedule(ms){ clearTimeout(wf.timer); wf.timer = setTimeout(poll, ms); }
async function poll(){
  // One poller at a time: stop, respond and start all funnel through schedule().
  const id = wf.run;
  if(!id || wf.inflight) return;
  wf.inflight = true;
  try{
    const value = await api('/api/workflows/' + id + '?after=' + wf.cursor);
    if(id !== wf.run) return;
    wf.events.push(...value.events);
    Object.assign(wf, {cursor:value.cursor, status:value.status, pending:value.pending, result:value.result, meta:value});
    $('#wfError').textContent = '';
    renderAll();
    if(value.status === 'running' || value.status === 'stopping') schedule(850);
  }catch(error){
    $('#wfError').textContent = 'Connection interrupted: ' + error.message + '. Reconnecting; the workflow may still be running.';
    schedule(2000);
  }finally{ wf.inflight = false; }
}
async function startWorkflow(){
  reset(); wf.starting = true; renderAll();
  try{
    const value = await api('/api/workflows', {case_id:'DH-401', developer_note:$('#wfNote').value.trim(), business_context:true});
    wf.run = value.id; wf.status = 'running';
    schedule(0);
  }catch(error){ $('#wfError').textContent = error.message; }
  finally{ wf.starting = false; renderAll(); }
}
async function stopWorkflow(){
  try{ if(wf.run) await api('/api/workflows/' + wf.run + '/cancel', {}); schedule(300); }
  catch(error){ $('#wfError').textContent = error.message; }
}
async function respond(body){
  try{
    await api('/api/workflows/' + wf.run + '/respond', {interrupt_id:wf.pending.id, ...body});
    wf.status = 'running'; wf.pending = null; wf.pendingKey = null; wf.summaryKey = null; wf.follow = true;
    $('#wfPending').innerHTML = '';
    renderAll(); schedule(0);
  }catch(error){ $('#wfError').textContent = error.message; document.getElementById('wfError').scrollIntoView({block:'center'}); }
}
function sendAnswer(){
  const choices = {};
  document.querySelectorAll('.wf-question').forEach(set => { const picked = set.querySelector('input:checked'); if(picked) choices[set.dataset.question] = picked.value; });
  respond({action:'answer', choices, message:$('#wfAnswerNote').value.trim()});
}
function sendReview(action){
  const message = action === 'revise' ? $('#wfRevise').value.trim() : '';
  if(action === 'revise' && !message){ $('#wfRevise').focus(); $('#wfError').textContent = 'Write an instruction before sending the work back.'; return; }
  respond({action, message});
}

async function startReplay(name){
  reset();
  try{
    const rec = await api('/api/workflows/recordings/' + encodeURIComponent(name));
    wf.replay = {rec, i:0, events:[], done:false, timer:null};
    replayStep();
  }catch(error){ $('#wfError').textContent = error.message; }
}
function replayStep(){
  const r = wf.replay;
  if(!r) return;
  if(r.i >= r.rec.events.length){
    r.done = true;
    const last = [...r.rec.events].reverse().find(e => e.kind === 'waiting' && e.payload?.kind === 'review');
    r.summary = last?.payload.summary; r.approved = r.rec.outcome === 'approved';
    renderAll(); return;
  }
  const event = r.rec.events[r.i++];
  r.events.push(event);
  renderAll();
  if(event.kind === 'waiting') return; // Pause until the presenter continues.
  const next = r.rec.events[r.i];
  const delay = next && typeof next.seconds === 'number' && typeof event.seconds === 'number' ? Math.min(Math.max((next.seconds - event.seconds) * 1000 / SPEED, 25), 1400) : 25;
  r.timer = setTimeout(replayStep, delay);
}
function continueReplay(){ if(wf.replay){ wf.pendingKey = null; wf.summaryKey = null; wf.follow = true; replayStep(); } }

async function mountWorkflow(){
  const root = $('#workflowSection');
  if(!root) return;
  root.innerHTML = skeleton();
  try{
    [wf.graph, wf.recordings] = await Promise.all([api('/api/workflows/graph'), api('/api/workflows/recordings').then(value => value.recordings.filter(r => r.context !== false))]);
  }catch(error){ root.insertAdjacentHTML('beforeend', `<p class="error">Could not load the workflow: ${esc(error.message)}</p>`); return; }
  $('#wfMaxRounds').textContent = wf.graph.max_rounds;
  renderGraphDetail(); renderInputs(); renderStrip(null);
  root.addEventListener('toggle', event => { if(event.target.matches?.('details[data-lazy]')) fillLazy(event.target); }, true);
  const latest = (config.workflows || []).filter(flow => !flow.case_id || flow.case_id === 'DH-401').at(-1);
  if(latest){ wf.run = latest.id; wf.status = latest.status; schedule(0); }
  window.addEventListener('wheel', () => { wf.follow = false; }, {passive:true});
  window.addEventListener('touchmove', () => { wf.follow = false; }, {passive:true});
}

window.mountWorkflow = mountWorkflow;
})();
