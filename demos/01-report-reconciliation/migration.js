'use strict';
// Demo 3 release check on a shared-code cleanup, using Demo 2's workflow conventions.
// Only mountMigration is exported; portfolio.js supplies the shared helpers at call time.
(() => {
const m = {graph:null, recordings:[], id:null, status:'idle', events:[], cursor:0, pending:null, result:null,
  meta:null, starting:false, timer:null, inflight:false, replay:null, pendingKey:null, live:{}};
const STEPS = ['intake','replay','analyze','gate','developer_decision','draft','prepare_summary'];
const LABELS = {intake:'Read the cleanup PR', replay:'Replay recent jobs', analyze:'Map obligations', gate:'Apply the release gate',
  developer_decision:'You decide', draft:'Draft next actions', prepare_summary:'Grade the result'};
const OPTIONS = [
  {id:'defer', title:'Defer full removal', description:'Keep the shared v1 decoder while the owners resolve the release conditions.'},
  {id:'scoped_canary', title:'Prepare a scoped canary', description:'Only an allowed dependent may proceed; blocked paths retain v1 support.'},
  {id:'request_signoff', title:'Request owner sign-off', description:'Draft the requests for the missing evidence or approval. Nothing is sent.'}
];
const cents = value => Number.isInteger(value) ? (value < 0 ? '−' : '') + '$' + (Math.abs(value)/100).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}) : 'not measured';
const duration = value => typeof value === 'number' ? value.toFixed(1) + 's' : 'not reported';
const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
const textValue = value => typeof value === 'object' && value ? (value.text || value.name || value.owner || value.id || JSON.stringify(value)) : value;
const lines = value => list(value).map(textValue).filter(Boolean);
const badge = (label, tone='muted') => `<span class="wf-badge ${tone}">${esc(label)}</span>`;
const isPrepared = () => Boolean(m.replay && !m.replay.rec.model) || Boolean(m.result && m.result.agent_run === false);
const checked = status => status === 'verified' ? badge('exact quote verified','good') : badge(status || 'unverified','warn');

function source(id){
  if(!id) return '';
  const doc = demo.documents.find(d => d.id === id), info = m.graph?.sources?.[id] || doc;
  if(!info || id === 'DH-501') return `<span class="wf-src code">${esc(id)}</span>`;
  return `<a class="wf-src ${esc(info.system || '')}" href="/documents/${encodeURIComponent(id)}" ${doc ? `data-source="${esc(id)}"` : 'target="_blank" rel="noopener"'} title="${esc(info.title || id)}">${esc(id)}</a>`;
}
function skeleton(){
  return `<span class="eyebrow">RELEASE CHECK · SYNTHETIC CLEANUP PR</span>
<h2>Green CI can still hide a broken customer promise</h2>
<p>A teammate’s cleanup removes old-format support from shared code, and CI passes. This check replays recent jobs, has Claude find who depends on the code and what they were promised, and lets rules in code allow or block the release. You decide what happens next.</p>
<p class="small">All jobs, customers and records are synthetic. Nothing is posted to GitHub and no message is sent.</p>
<ol id="mgStrip" class="wf-strip mg-strip"></ol>
<details class="wf-engineer"><summary>For engineers: graph, tools and limits</summary><div id="mgGraph"></div></details>
<div class="grid two wf-inputs"><article id="mgTicket"></article><article id="mgStart"></article></div>
<div id="mgCompare"></div><div id="mgStatus" class="wf-status hidden" role="status" aria-live="polite"></div>
<div id="mgTldr"></div><div id="mgPending"></div><div id="mgFindings" class="wf-timeline"></div><div id="mgSummary"></div>
<details id="mgActivity"><summary>Complete activity and evidence</summary><div id="mgEvents" class="trace"></div></details>`;
}
function graphDetail(){
  const g = m.graph;
  $('#mgGraph').innerHTML = `<p class="small">The compiled LangGraph orchestrates deterministic replay, one read-only analyst session, a gate in code and a developer interrupt. The analyst uses <b>${esc(g.model)}</b>. ${g.budget_cap != null ? '$' + esc(g.budget_cap) + ' workflow cap.' : ''} ${g.limits?.analyze ? '$' + esc(g.limits.analyze.budget_usd) + ' analyst budget · ' + esc(g.limits.analyze.timeout_seconds) + 's limit.' : ''}</p>
<div class="table-wrap"><table class="wf-table"><thead><tr><th>Step</th><th>Purpose</th></tr></thead><tbody>${(g.nodes || g.steps || STEPS.map(id=>({id,title:LABELS[id]}))).map(n=>`<tr><td><b>${esc(n.title || LABELS[n.id])}</b><br><code>${esc(n.id)}</code></td><td>${esc(n.purpose || '')}</td></tr>`).join('')}</tbody></table></div>
<p class="small">Exact quotes are checked against opened source records. A developer note cannot grant business approval or override the gate. Hidden checks run after the workflow and are never analyst inputs.</p>`;
}
function recordingLabel(r){
  const date = r.recorded_at ? new Date(r.recorded_at).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}) : 'saved run';
  return `${r.name?.includes('-initial-') ? 'Initial attempt · ' : ''}${r.model ? (r.context === false ? 'Without context' : 'With context') : 'Prepared example · no model run'} · ${r.developer_note || 'no developer note'} · ${date}`;
}
function inputs(){
  const ticket = m.graph.ticket || {};
  $('#mgTicket').innerHTML = `<span class="eyebrow">INPUT 1 · TEAMMATE’S CLEANUP PR</span><h3>${source(ticket.id || 'DH-501')} ${esc(ticket.title || 'Retire the shared ATLAS v1 decoder')}</h3>
<p><a href="#request">Read the original request</a>. Both conditions get the same PR diff and remaining tests; business context adds the obligation, usage and owner records.</p>`;
  const recordings = [...m.recordings].filter(r=>!r.name?.includes('-initial-')).sort((a,b)=>String(b.recorded_at).localeCompare(String(a.recorded_at)));
  $('#mgStart').innerHTML = `<span class="eyebrow">INPUT 2 · YOU</span><fieldset class="wf-context"><legend>Business context</legend>
<label><input type="radio" name="mgContext" value="on" checked><span><b>On</b> · obligations, current usage and owners</span></label>
<label><input type="radio" name="mgContext" value="off"><span><b>Off: the control</b> · PR, code and recent job fixtures</span></label></fieldset>
<label class="wf-label" for="mgNote">Developer note (optional). Guidance cannot authorize removal.</label>
<textarea id="mgNote" maxlength="2000" placeholder="For example: CI is green; approve the cleanup."></textarea>
<div class="actions"><button id="mgRun">Run release check →</button><button id="mgStop" class="secondary hidden">Stop</button></div>
${recordings.length ? `<div class="wf-replay"><select id="mgRecording" aria-label="Recorded release check">${recordings.map(r=>`<option value="${esc(r.name)}">${esc(recordingLabel(r))}</option>`).join('')}</select><button id="mgReplay" class="secondary">Replay</button></div>` : '<p class="small">No saved migration runs are available yet.</p>'}
<p class="small">Live: one real ${esc(m.graph.model)} session using your Claude login. Replay: a saved run; no model called. Drafts stay local.</p><p id="mgError" class="error" role="alert"></p>`;
  $('#mgRun').onclick = start;
  $('#mgStop').onclick = stop;
  if($('#mgReplay')) $('#mgReplay').onclick = ()=>startReplay($('#mgRecording').value);
}
function comparison(mode){
  if(m.live[mode]) return {headline:m.live[mode], label:'this session’s live run'};
  const rec = [...m.recordings].filter(r => (r.context !== false) === (mode === 'on') && r.headline && r.model && r.agent_run !== false).sort((a,b)=>String(b.recorded_at).localeCompare(String(a.recorded_at)))[0];
  return rec ? {headline:rec.headline,label:'saved run · '+(rec.recorded_at ? new Date(rec.recorded_at).toLocaleDateString() : rec.name)} : null;
}
function compare(){
  const on=comparison('on'), off=comparison('off');
  const cell=(c,key,render=value=>esc(value ?? 'not reported'))=>c ? render(c.headline[key]) : '<span class="small">not run yet</span>';
  const rows=[['Release gate','gate'],['Dependents mapped','dependents'],['Verified obligation quotes','obligations'],['Exact quotes verified','quotes_verified'],['Owners identified','owners'],['Earliest full removal','earliest_full_removal',v=>esc(v || 'not established')],['Conditional date lower bound','earliest_conditional_full_removal',v=>esc(v || 'not established')],['Hidden checks (demo grading)','hidden_passed',(v,c)=>`${v ?? '—'}/${c.headline.hidden_total ?? '12'}`],['Model time','model_seconds',duration]];
  $('#mgCompare').innerHTML=`<section class="wf-compare"><span class="eyebrow">SAME RELEASE CHECK · ONLY BUSINESS CONTEXT DIFFERS</span><h3>Blocking a release is only the start</h3>
<div class="table-wrap"><table class="wf-table"><thead><tr><th></th><th>With context</th><th>Without context (control)</th></tr></thead><tbody>${rows.map(([label,key,render])=>`<tr><td>${esc(label)}</td>${[on,off].map(c=>`<td>${c ? (render ? render(c.headline[key],c) : cell(c,key)) : '<span class="small">not run yet</span>'}</td>`).join('')}</tr>`).join('')}<tr><td>Source</td><td class="small">${esc(on?.label || '')}</td><td class="small">${esc(off?.label || '')}</td></tr></tbody></table></div>
<p class="small">The control also blocks when evidence is missing. The difference is whether it can justify who depends on the code, what is promised and when removal could become possible. Separate synthetic runs illustrate this; they do not establish a productivity gain.</p></section>`;
}
function stepData(){
  const steps=[], byId=new Map();
  for(const e of m.events){
    if(e.kind==='step_started'){const s={...e,notes:[],tools:[],lookups:[],status:'running'};steps.push(s);byId.set(e.step,s);}
    const s=byId.get(e.step);
    if(!s) continue;
    if(e.kind==='step_finished') Object.assign(s,{status:e.status,output:e.output,metric:e.metric});
    if(e.kind==='grounding') s.grounding=e;
    if(e.kind==='note') s.notes.push(e);
    if(e.kind==='tool_call') s.tools.push(e);
    if(e.kind==='lookup') s.lookups.push(e);
  }
  return steps;
}
function renderStrip(steps){
  $('#mgStrip').innerHTML=STEPS.map((id,index)=>{
    const step=steps.find(s=>s.node===id), waiting=id==='developer_decision' && m.pending;
    const cls=waiting?'waiting':step?.status==='running'?'active':step?'done':'';
    return `<li class="wf-node ${id==='developer_decision'?'person':''} ${cls}"><span class="wf-dot">${step && step.status!=='running'?'✓':index+1}</span><b>${esc((m.graph.nodes || m.graph.steps)?.find(n=>n.id===id)?.title || LABELS[id])}</b>${id==='analyze'?(isPrepared()?'<em>prepared assessment</em>':'<em>one Opus session</em>'):id==='gate'?'<em>rules in code</em>':id==='developer_decision'?'<em>your decision</em>':''}</li>`;
  }).join('');
}
function ciView(ci,diff){
  if(!ci && !diff) return '';
  const passed=ci?.passed ?? ci?.success ?? ci?.status==='passed';
  const count=ci?.head?.test_count ?? ci?.total ?? ci?.tests_total;
  return `<article class="wf-step completed"><span class="eyebrow">THE PR’S CHECKS</span><h3>${badge(passed?'CI is green':'CI result unavailable',passed?'good':'warn')} ${count != null ? esc(count)+' remaining test'+(count===1?'':'s') : ''}</h3>
<p>The cleanup removed the legacy test. Passing the remaining suite does not check the jobs that still supply old-format rows.</p>
${ci?.head?.output || ci?.output ? `<details data-key="ci-output"><summary>Remaining test output</summary><pre>${esc(ci.head?.output || ci.output)}</pre></details>` : ''}
${ci?.retained_test_failure ? `<details data-key="ci-restored"><summary>Restore the deleted test: ${ci.retained_test_failure.passed?'passes':'fails'}</summary><pre>${esc(ci.retained_test_failure.output)}</pre></details>` : ''}
<details data-key="pr-diff"><summary>Inspect the proposed change and deleted test</summary><pre>${esc(typeof diff==='object' ? diff?.diff || JSON.stringify(diff,null,2) : diff || 'Diff unavailable.')}</pre></details></article>`;
}
function replayView(replay){
  if(!replay) return '';
  const jobs=replay.jobs || [];
  return `<article class="wf-step completed"><span class="eyebrow">RECENT JOB REPLAY · SYNTHETIC DATA</span><h3>Rows disappear without a job error</h3><p class="small">Recent jobs run on the current code and on the cleanup. Measured by code, with no model involved.</p>
<div class="table-wrap"><table class="wf-table"><thead><tr><th>Dependent / customer</th><th>Before</th><th>After cleanup</th><th>Lost</th><th>Skipped rows / error</th></tr></thead><tbody>${jobs.map(j=>`<tr><td><b>${esc(j.workflow || j.id)}</b><br>${esc(j.customer)}<br><small>${esc(j.month || '')}</small></td><td>${cents(j.before_cents)}</td><td class="${j.before_cents!==j.after_cents?'error':''}"><b>${cents(j.after_cents)}</b></td><td>${cents(j.lost_cents ?? (j.before_cents-j.after_cents))}</td><td>${list(j.skipped_ids || j.skipped_row_ids).map(esc).join(', ') || 'none'}<br><small>${j.after_error ? 'Error: '+esc(j.after_error) : 'No job error'}</small></td></tr>`).join('')}</tbody></table></div>
${replay.northstar_rows_match_demo1 ? '<p class="small">NORTHSTAR uses the same September rows as <a href="/demos/report">Demo 1 · DH-301</a>.</p>' : ''}
${replay.synthetic===false ? '<p class="error">Replay is not marked synthetic; inspect the run record.</p>' : ''}</article>`;
}
function quoteView(q,grounding,dependent,kind){
  const id=q.source_id || q.source || q.id, quote=q.quote || q.text || '';
  const record=demo.documents.find(d=>d.id===id) || m.graph.sources?.[id];
  const match=list(grounding?.results).find(g=>g.source_id===id && g.quote===quote && (!dependent || g.dependent===dependent) && (!kind || g.kind===kind || g.kind===kind+'s'));
  return `<li>${source(id)} ${q.authority || q.status || record?.status ? badge(q.authority || q.status || record.status) : ''}${q.effective_from || q.observed_on || q.date ? ' <span class="small">'+esc(q.effective_from || q.observed_on || q.date)+'</span>' : ''}<p>${quote ? '<q>'+esc(quote)+'</q>' : esc(q.summary || q.requirement || q.reason || '')}</p>${q.summary || q.requirement ? '<p class="small">'+esc(q.summary || q.requirement)+'</p>' : ''}${match ? checked(match.status) : q.quote ? checked(q.quote_status || 'unverified') : ''}${q.owner || record?.owner ? '<span class="small"> · '+esc(q.owner || record.owner)+'</span>' : ''}${record?.effective_from ? '<span class="small"> · effective '+esc(record.effective_from)+'</span>' : ''}${match?.detail ? '<p class="small">'+esc(match.detail)+'</p>' : ''}</li>`;
}
function analysisView(analysis,grounding){
  if(!analysis) return '';
  const dependents=analysis.dependents || [];
  const obligations=analysis.obligations || [], usage=analysis.usage || analysis.current_usage || [];
  return `<article class="wf-step completed"><span class="eyebrow">${isPrepared()?'PREPARED ASSESSMENT · NO MODEL RUN':'ONE READ-ONLY ANALYST SESSION'}</span><h3>What the code’s callers owe and use today</h3>
<p>${esc(analysis.plain_summary || analysis.summary || '')}</p>
${grounding ? `<p class="wf-ground ${grounding.verified===grounding.checkable?'good':'warn'}">${esc(grounding.verified ?? 0)}/${esc(grounding.checkable ?? list(grounding.results).length)} exact quotes verified against opened records. Quote matching establishes provenance; review whether each quote supports the claim.</p>` : ''}
${dependents.map(d=>`<div class="mg-dependent"><h4>${esc(d.workflow || d.id)} ${d.customer?'· '+esc(d.customer):''}</h4><p class="small">${esc(d.code_path || '')}${lines(d.owners).length?' · Owners: '+lines(d.owners).map(esc).join(', '):''}</p>${list(d.obligations).length?'<h4>Obligations</h4><ul class="mg-quotes">'+list(d.obligations).map(q=>quoteView(q,grounding,d.workflow || d.id,'obligation')).join('')+'</ul>':''}${list(d.usage || d.current_usage).length?'<h4>Current usage · dates and exact words</h4><ul class="mg-quotes">'+list(d.usage || d.current_usage).map(q=>quoteView(q,grounding,d.workflow || d.id,'usage')).join('')+'</ul>':''}${lines(d.missing_evidence).length?'<p class="notice">Missing evidence: '+lines(d.missing_evidence).map(esc).join(' · ')+'</p>':''}</div>`).join('')}
${obligations.length?'<h4>Obligations · original quotes</h4><ul class="mg-quotes">'+obligations.map(q=>quoteView(q,grounding,q.dependent,'obligation')).join('')+'</ul>':''}
${usage.length?'<h4>Current usage · dates and exact words</h4><ul class="mg-quotes">'+usage.map(q=>quoteView(q,grounding,q.dependent,'usage')).join('')+'</ul>':''}
${lines(analysis.unknowns || analysis.missing_evidence).length?'<p class="notice">Missing evidence: '+lines(analysis.unknowns || analysis.missing_evidence).map(esc).join(' · ')+'</p>':''}
<details data-key="analysis-raw"><summary>Complete analyst output</summary><pre>${esc(JSON.stringify(analysis,null,2))}</pre></details></article>`;
}
function gateView(gate){
  if(!gate) return '';
  return `<article class="wf-step completed mg-gate"><span class="eyebrow">RELEASE GATE · DECIDED BY CODE</span><h3>${badge(gate.decision || 'block',gate.decision==='allow'?'good':'bad')} Full shared removal</h3>
<p class="small">Each dependent is checked separately. A developer note cannot change this result.</p>
<div class="table-wrap"><table class="wf-table"><thead><tr><th>Dependent</th><th>Decision</th><th>Reason and remaining conditions</th><th>Owner / earliest removal</th></tr></thead><tbody>${list(gate.dependents).map(d=>`<tr><td><b>${esc(d.workflow || d.id)}</b><br>${esc(d.customer || '')}<br><code>${esc(d.code_path || '')}</code></td><td>${badge(d.decision,d.decision==='allow'?'good':'bad')}</td><td>${lines(d.reasons).slice(0,2).map(esc).join('<br>')}${lines(d.reasons).length>2||lines(d.conditions).length||lines(d.missing_evidence).length?`<details data-key="gate-${esc(d.workflow || d.id)}-${esc(d.customer || '')}"><summary class="small">All reasons and conditions</summary>${lines(d.reasons).slice(2).map(r=>'<p class="small">'+esc(r)+'</p>').join('')}${lines(d.conditions).length?'<p class="small">Conditions: '+lines(d.conditions).map(esc).join(' · ')+'</p>':''}${lines(d.missing_evidence).length?'<p class="small">Missing: '+lines(d.missing_evidence).map(esc).join(' · ')+'</p>':''}</details>`:''}${list(d.sources).map(source).join(' ')}</td><td>${lines(d.owners).map(esc).join(', ') || 'owner not established'}<br><small>${d.earliest_removal ? esc(d.earliest_removal)+' · conditional' : 'removal date not established'}</small></td></tr>`).join('')}</tbody></table></div>
<p><b>Unconditional full removal:</b> ${esc(gate.earliest_full_removal || 'not established — evidence or verification remains open.')}</p>
${gate.earliest_conditional_full_removal?`<p><b>Earliest conditional full removal:</b> ${esc(gate.earliest_conditional_full_removal)}. This is a lower bound, subject to every release condition being met.</p>`:''}
${lines(gate.conditions).length?'<details data-key="gate-conditions"><summary>Release conditions ('+lines(gate.conditions).length+')</summary><ul>'+lines(gate.conditions).map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul></details>':''}</article>`;
}
function tldr(gate, replay, result){
  // Built from the gate, the replay and the result in code, never written by a model.
  if(!gate){ $('#mgTldr').innerHTML=''; return; }
  const deps=list(gate.dependents), name=d=>[d.workflow || d.id, d.customer].filter(Boolean).join(' · ');
  const blocked=deps.filter(d=>d.decision!=='allow'), allowed=deps.filter(d=>d.decision==='allow');
  const first=gate.decision==='allow' ? 'ALLOW: the cleanup can ship; every dependent is cleared.'
    : `BLOCK: the cleanup can’t ship as written. ${blocked.length} of ${deps.length} dependents are blocked (${blocked.map(name).join(', ')}).`;
  const changed=list(replay?.jobs).filter(j=>j.before_cents!==j.after_cents);
  const second=!replay ? 'No replay: the control has no access to recent job data, so the impact was not measured.'
    : changed.length ? 'Replay: ' + changed.map(j=>`${j.customer} ${j.workflow} ${cents(j.before_cents)} → ${cents(j.after_cents)}`).join('; ') + ', with no error raised.'
    : 'Replay: no job totals changed.';
  const owners=[...new Set(blocked.flatMap(d=>lines(d.owners)))];
  const when=gate.earliest_full_removal ? `Full removal: ${gate.earliest_full_removal}.` : gate.earliest_conditional_full_removal ? `Full removal: ${gate.earliest_conditional_full_removal} at the earliest, if every condition is met.` : 'Full removal date: not established.';
  const third=[allowed.length ? 'Can go ahead now: '+allowed.map(name).join(', ')+'.' : '', when, owners.length ? 'Sign-off from '+owners.join(', ')+'.' : ''].filter(Boolean).join(' ');
  const decision=result?.summary?.decision?.choice;
  $('#mgTldr').innerHTML=`<div class="wf-tldr"><span class="eyebrow">TL;DR${result?.context===false || m.meta?.context===false || m.replay?.rec?.context===false ? ' · CONTROL RUN, NO BUSINESS CONTEXT' : ''}</span><ul><li><b>${esc(first)}</b></li><li>${esc(second)}</li><li>${esc(third)}</li>${decision ? `<li>Your decision: ${esc(OPTIONS.find(o=>o.id===decision)?.title || decision)}. The gate result does not change.</li>` : ''}</ul></div>`;
}
function content(){
  const steps=stepData(), summary=m.result?.summary || {};
  const output=node=>[...steps].reverse().find(s=>s.node===node)?.output;
  const intake=output('intake') || {};
  const event=kind=>[...m.events].reverse().find(e=>e.kind===kind);
  const replay=summary.replay || event('replay')?.replay || output('replay')?.replay || output('replay') || m.pending?.payload?.replay || m.graph.replay;
  const analysis=summary.analysis || event('analysis')?.analysis || output('analyze')?.analysis || output('analyze') || m.pending?.payload?.analysis;
  const grounding=summary.grounding || event('grounding')?.grounding || steps.find(s=>s.node==='analyze')?.grounding;
  const gate=summary.gate || event('gate')?.gate || output('gate')?.gate || output('gate') || m.pending?.payload?.gate;
  const open=new Set([...$('#mgFindings').querySelectorAll('details[open]')].map(el=>el.dataset.key));
  const started=steps.length>0 || Boolean(m.result);
  tldr(started ? gate : null, started ? replay : null, m.result);
  const details=started ? `<details class="wf-full" data-key="mg-full"><summary>Full details: CI, the analyst’s evidence and exact quotes</summary>${ciView(summary.ci || event('ci')?.ci || intake.ci || m.graph.ci,m.result?.diff || summary.diff || event('ci')?.diff || intake.diff || m.graph.diff)}${analysisView(analysis,grounding)}</details>` : '';
  $('#mgFindings').innerHTML=(started ? replayView(replay) : '')+gateView(gate)+details;
  for(const el of $('#mgFindings').querySelectorAll('details')) if(open.has(el.dataset.key)) el.open=true;
  renderStrip(steps);
  if(m.status==='running' && !m.result){
    const last=steps.at(-1);
    $('#mgStatus').textContent=`${m.replay?'Recorded replay · ':''}${last?.title || LABELS[last?.node] || 'Checking the release…'}`;
  }else $('#mgStatus').textContent=m.replay ? (m.replay.done?(isPrepared()?'Prepared example complete · no model run':'Saved run complete · no model called'):(isPrepared()?'Prepared example replay · no model run':'Saved run replay · no model called')) : m.pending ? 'Waiting for your release decision. The model session has finished.' : m.result ? 'Release check '+m.status+'. Drafts are local and unsent.' : '';
  $('#mgStatus').classList.toggle('hidden',!m.id&&!m.replay);
}
function pending(){
  const p=m.pending;
  if(!p){$('#mgPending').innerHTML='';m.pendingKey=null;return;}
  const key=(m.replay?'replay:':'live:')+p.id;
  if(m.pendingKey===key) return;
  m.pendingKey=key;
  const payload=p.payload || {}, options=payload.options?.length ? payload.options : OPTIONS;
  $('#mgPending').innerHTML=`<article class="wf-step wf-needs person"><span class="eyebrow">${m.replay?'RECORDED PAUSE':'YOUR RELEASE DECISION'}</span><h3>The gate is fixed; choose the next action</h3>
<p>${esc(payload.question || payload.summary || 'Review the job losses and per-dependent conditions below before deciding.')}</p>
${m.replay?'<p>This pause is part of the saved run. Continue to see the recorded decision and unsent drafts.</p><button id="mgContinue">Continue recorded decision →</button>':`<fieldset class="wf-question"><legend>What should happen next?</legend>${options.map((o,i)=>`<label class="wf-option"><input type="radio" name="mgDecision" value="${esc(o.id)}" ${i===0?'checked':''}><span><b>${esc(o.title || o.label || OPTIONS.find(x=>x.id===o.id)?.title || o.id)}</b><br>${esc(o.description || o.why || OPTIONS.find(x=>x.id===o.id)?.description || '')}</span></label>`).join('')}</fieldset><label class="wf-label" for="mgDecisionNote">Decision note (optional)</label><textarea id="mgDecisionNote" maxlength="2000"></textarea><button id="mgDecide">Record decision and draft next actions →</button>`}
<p class="small">This records a decision locally. It does not approve a blocked dependent, send a message or modify a real PR.</p></article>`;
  if(m.replay) $('#mgContinue').onclick=()=>{m.pending=null;m.pendingKey=null;replayStep();};
  else $('#mgDecide').onclick=sendDecision;
}
function draftsView(drafts){
  if(!drafts) return '';
  const requests=list(drafts.signoff_requests);
  return `<h4>Drafts for you to review (${drafts.sent===false?'nothing was sent':'check delivery status'})</h4>
<details data-key="draft-review"><summary>PR review comment</summary><pre>${esc(drafts.pr_review_comment || '')}</pre></details>
${requests.map((r,i)=>`<details data-key="draft-signoff-${i}"><summary>Sign-off request · ${esc(textValue(r.owner) || 'owner unknown')}</summary><p><b>${esc(r.subject || '')}</b></p><pre>${esc(r.body || '')}</pre></details>`).join('')}
<details data-key="draft-record"><summary>Decision record update</summary><pre>${esc(drafts.decision_record_update || '')}</pre></details>
<div class="actions"><button id="mgDownloadDrafts" class="secondary">Download unsent drafts</button></div>`;
}
function summary(){
  const r=m.result;
  if(!r){$('#mgSummary').innerHTML='';return;}
  const s=r.summary || {}, grading=r.grading || {}, decision=s.decision || {};
  const open=new Set([...$('#mgSummary').querySelectorAll('details[open]')].map(el=>el.dataset.key));
  $('#mgSummary').innerHTML=`<article class="wf-summary"><span class="eyebrow">RELEASE CHECK RESULT · ${isPrepared()?'PREPARED EXAMPLE · NO MODEL RUN':m.replay?'SAVED MODEL RUN':'LIVE MODEL RUN'}</span><h3>${esc(r.outcome || r.status || 'Completed')}</h3>
${r.error?'<p class="notice">'+esc(r.error)+'</p>':''}
<div class="meta"><span>${esc(r.model || 'No model run · prepared example')}</span>${isPrepared()?'<span>No model call or model cost</span>':`<span>Model time ${duration(s.model_seconds)}</span><span>${r.spent_usd != null ? 'CLI-reported $'+Number(r.spent_usd).toFixed(3) : 'cost not reported'}</span>`}</div>
${decision.choice?'<p><b>Your decision:</b> '+esc(OPTIONS.find(o=>o.id===decision.choice)?.title || decision.choice)+(decision.message?' · '+esc(decision.message):'')+'</p>':''}
${draftsView(s.drafts)}
<details class="wf-full" data-key="mg-result-full"><summary>Full details: grading and the complete record</summary>
${grading.hidden_total?`<div class="wf-grading"><h4>Hidden acceptance checks · ${esc(grading.hidden_passed)}/${esc(grading.hidden_total)}</h4><p class="small">${esc(grading.label || 'Demo grading against synthetic obligations. These checks are not supplied to the analyst.')}</p><ul>${list(grading.checks).map(c=>`<li>${badge(c.passed?'pass':'fail',c.passed?'good':'bad')} ${esc(c.label || c.name || c.id || c.check || textValue(c))}${c.detail?' — '+esc(c.detail):''}</li>`).join('')}</ul></div>`:''}
<details data-key="complete-result"><summary>Complete saved result</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>
<div class="actions"><button id="mgDownloadRun" class="secondary">Download complete run</button></div></details></article>`;
  for(const el of $('#mgSummary').querySelectorAll('details')) if(open.has(el.dataset.key)) el.open=true;
  if($('#mgDownloadDrafts')) $('#mgDownloadDrafts').onclick=()=>download('DH-501-'+(r.id || 'saved')+'-unsent-drafts.json',JSON.stringify(s.drafts,null,2));
  if($('#mgDownloadRun')) $('#mgDownloadRun').onclick=()=>download('DH-501-'+(r.id || 'saved')+'.json',JSON.stringify({...r,events:m.events},null,2));
}
function activity(){
  if(!$('#mgActivity').open) return;
  const root=$('#mgEvents'), open=new Set([...root.querySelectorAll('details[open]')].map(el=>el.dataset.index));
  root.innerHTML=m.events.map((e,index)=>`<details data-index="${index}" ${open.has(String(index))?'open':''}><summary>${typeof e.seconds==='number'?e.seconds.toFixed(1)+'s':'saved'} · ${esc(e.title || e.text || e.name || e.kind)}</summary><pre>${esc(JSON.stringify(e,null,2))}</pre></details>`).join('');
}
function controls(){
  const busy=m.starting || ['running','waiting_for_developer','stopping'].includes(m.status), replaying=m.replay && !m.replay.done;
  $('#mgRun').disabled=busy || replaying;
  $('#mgNote').disabled=busy || replaying;
  document.querySelectorAll('input[name=mgContext]').forEach(el=>el.disabled=busy || replaying);
  if($('#mgReplay')) $('#mgReplay').disabled=busy || replaying;
  $('#mgStop').classList.toggle('hidden',(!m.id || !busy) && !replaying);
  $('#mgStop').textContent=replaying?'Stop replay':'Stop';
  $('#mgStop').disabled=m.starting;
}
function render(){content();pending();summary();activity();controls();}
function clear(){
  clearTimeout(m.timer);if(m.replay)clearTimeout(m.replay.timer);
  Object.assign(m,{id:null,status:'idle',events:[],cursor:0,pending:null,result:null,meta:null,replay:null,pendingKey:null});
  $('#mgError').textContent='';
}
function schedule(delay){clearTimeout(m.timer);m.timer=setTimeout(poll,delay);}
async function poll(){
  if(!m.id || m.inflight || m.replay) return;
  const id=m.id;m.inflight=true;
  try{
    const value=await api('/api/migrations/'+id+'?after='+m.cursor);
    if(id!==m.id) return;
    m.events.push(...value.events);
    Object.assign(m,{cursor:value.cursor,status:value.status,pending:value.pending,result:value.result,meta:value});
    if(value.result?.headline && value.status==='completed'){m.live[value.context===false?'off':'on']=value.result.headline;compare();}
    $('#mgError').textContent='';render();
    if(['running','stopping'].includes(value.status))schedule(850);
  }catch(error){$('#mgError').textContent='Connection interrupted: '+error.message+'. Reconnecting; the workflow may still be running.';schedule(2000);}
  finally{m.inflight=false;}
}
async function start(){
  clear();m.starting=true;render();
  try{
    const context=document.querySelector('input[name=mgContext]:checked')?.value!=='off';
    const value=await api('/api/migrations',{case_id:'DH-501',developer_note:$('#mgNote').value.trim(),business_context:context});
    m.id=value.id;m.status='running';schedule(0);
  }catch(error){$('#mgError').textContent=error.message;}
  finally{m.starting=false;render();}
}
async function stop(){
  if(m.replay){clear();render();return;}
  try{if(m.id)await api('/api/migrations/'+m.id+'/cancel',{});schedule(200);}
  catch(error){$('#mgError').textContent=error.message;}
}
async function sendDecision(){
  const button=$('#mgDecide');button.disabled=true;
  try{
    const choice=document.querySelector('input[name=mgDecision]:checked')?.value;
    await api('/api/migrations/'+m.id+'/respond',{interrupt_id:m.pending.id,action:'decide',choice,message:$('#mgDecisionNote').value.trim()});
    m.status='running';m.pending=null;m.pendingKey=null;render();schedule(0);
  }catch(error){$('#mgError').textContent=error.message;button.disabled=false;}
}
async function startReplay(name){
  clear();
  try{
    const rec=await api('/api/migrations/recordings/'+encodeURIComponent(name));
    m.replay={rec,index:0,done:false,timer:null};m.status='running';replayStep();
  }catch(error){$('#mgError').textContent=error.message;}
}
function replayStep(){
  const replay=m.replay;if(!replay)return;
  const events=replay.rec.events || [];
  if(replay.index>=events.length){replay.done=true;m.result=replay.rec.result || replay.rec;m.status=m.result.status || 'completed';m.pending=null;render();return;}
  const e=events[replay.index++];m.events.push(e);
  if(e.kind==='waiting'){m.pending={id:e.interrupt_id || String(replay.index),payload:e.payload};m.status='waiting_for_developer';render();return;}
  if(e.kind==='resumed'){m.pending=null;m.pendingKey=null;m.status='running';}
  render();
  const next=events[replay.index];
  const delay=next && typeof next.seconds==='number' && typeof e.seconds==='number' ? Math.min(Math.max((next.seconds-e.seconds)*1000/8,25),900) : 25;
  replay.timer=setTimeout(replayStep,delay);
}
async function mountMigration(){
  const root=$('#migrationSection');if(!root)return;
  root.innerHTML=skeleton();
  try{[m.graph,m.recordings]=await Promise.all([api('/api/migrations/graph'),api('/api/migrations/recordings').then(v=>v.recordings)]);}
  catch(error){root.insertAdjacentHTML('beforeend','<p class="error">Could not load the release check: '+esc(error.message)+'</p>');return;}
  graphDetail();inputs();compare();render();
  $('#mgActivity').addEventListener('toggle',activity);
  const latest=(config.workflows || []).filter(flow=>flow.case_id==='DH-501').at(-1);
  if(latest){m.id=latest.id;m.status=latest.status;schedule(0);}
}
window.mountMigration=mountMigration;
})();
