/* Reader-only explanations. Nothing in this file is sent to model sessions. */
const reader = {documents: new Map(), current: null, history: [], walkthroughs: new Map()};
const sourceNotes = {
  'FEED-ATLAS-1': ['ATLAS format v1: keep the sign', 'Explains why a negative return subtracts sales and a positive return can undo a refund.'],
  'FEED-ATLAS-2': ['ATLAS format v2: use the transaction type', 'Amounts are nonnegative sizes. The type tells us whether to add or subtract; a negative size is invalid.'],
  'FEED-ATLAS-3-DRAFT': ['ATLAS format v3: a proposal, not an approved rule', 'Shows what the team is considering. It cannot establish what version 3 transactions mean today.'],
  'REPORT-STD-SEP': ['Default sales rules through September', 'Defines the month and transaction types used before the October policy change.'],
  'REPORT-STD-OCT': ['Default sales rules from October', 'Changes the reporting date starting in October; it does not rewrite September.'],
  'REPORT-BLUEBIRD': ['Bluebird’s customer-specific agreement', 'Explains why Bluebird can use a different date from customers on the default September rules.'],
  'REPORT-CEDAR-A': ['Cedar agreement A: use invoice dates', 'One approved customer rule. It does not say that it replaces agreement B.'],
  'REPORT-CEDAR-B': ['Cedar agreement B: use recorded dates', 'Another approved customer rule. It conflicts with agreement A without resolving which should win.'],
  'DH-204': ['Jira request: Northstar wants transfers included', 'A requested change awaiting approval, not permission to change the existing definition of sales.'],
  'DH-188': ['Jira history: old and new ATLAS formats coexist', 'Explains the rollout and who owns code defects versus invalid export data. “Done” does not mean all files use v2.']
};
const caseSources = {
  'DH-301': ['REPORT-STD-SEP','FEED-ATLAS-1','FEED-ATLAS-2','DH-188'],
  'DH-302': ['REPORT-BLUEBIRD','REPORT-STD-SEP','FEED-ATLAS-2'],
  'DH-303': ['REPORT-STD-SEP','DH-204','FEED-ATLAS-2'],
  'DH-304': ['FEED-ATLAS-3-DRAFT','REPORT-STD-SEP'],
  'DH-305': ['REPORT-CEDAR-A','REPORT-CEDAR-B','REPORT-STD-SEP','FEED-ATLAS-2'],
  'DH-306': ['REPORT-STD-SEP','REPORT-STD-OCT','FEED-ATLAS-2'],
  'DH-307': ['REPORT-STD-OCT','REPORT-STD-SEP','FEED-ATLAS-2'],
  'DH-308': ['FEED-ATLAS-2','REPORT-STD-SEP','DH-188'],
  'DH-309': ['FEED-ATLAS-1','REPORT-STD-SEP','DH-188'],
  'DH-310': ['FEED-ATLAS-1','REPORT-STD-SEP']
};
const terms = {
  ATLAS: ['ATLAS — the fictional source system', 'ATLAS is the name given to the upstream system supplying transaction export files in this demo. It is not the AI, the reporting application, or a live connection to a vendor. The files contain rows for sales, returns and transfers. Different export versions encode those rows differently.', ['FEED-ATLAS-1','FEED-ATLAS-2','FEED-ATLAS-3-DRAFT','DH-188']],
  NORTHSTAR: ['Northstar — a fictional customer', 'Northstar receives the monthly sales report and challenges its result. Its tickets use the standard reporting profile. Northstar is separate from ATLAS, the system supplying the underlying rows.', ['REPORT-STD-SEP','REPORT-STD-OCT','DH-204']],
  BLUEBIRD: ['Bluebird — a fictional customer with an exception', 'Bluebird has its own approved reporting agreement. A customer-specific agreement can change which reporting date applies, without changing how ATLAS encodes amounts.', ['REPORT-BLUEBIRD']],
  CEDAR: ['Cedar — a fictional customer with conflicting agreements', 'Cedar has two approved reporting documents that disagree about which date to use. The demo illustrates why someone must resolve that conflict before an authoritative total is confirmed.', ['REPORT-CEDAR-A','REPORT-CEDAR-B']],
  Jira: ['Jira — the issue and work tracker', 'Here, Jira means two synthetic snapshots of work records: DH-188 describes a completed rollout, and DH-204 records a request awaiting approval. The demo does not connect to a live Jira account. DH-301 through DH-310 are the separate customer cases being investigated.', ['DH-188','DH-204']],
  'net sales': ['Net sales — what the report is measuring', 'The sum of sales and applicable adjustments for a reporting month. It is not simply “sum every amount”: the agreed reporting definition controls dates and included transaction types, while the export contract controls the sign of each amount.', ['REPORT-STD-SEP','REPORT-STD-OCT']],
  schema_version: ['Schema version — which file rules apply to a row', 'A schema is a file format. This field selects the rules for interpreting that row: ATLAS v1 preserves signed amounts, while v2 supplies nonnegative sizes. Old and new formats can coexist in one report. The newest format does not automatically apply to older rows.', ['FEED-ATLAS-1','FEED-ATLAS-2','DH-188']],
  amount_cents: ['amount_cents — money stored as whole cents', 'The source stores $200.00 as 20000, not 200.00. Integer cents avoid rounding errors. A minus sign is part of the supplied data; whether it is valid and how it affects sales depends on the export version.', ['FEED-ATLAS-1','FEED-ATLAS-2']],
  posted_on: ['posted_on — the recorded date', 'The date a transaction entered the source system. It can be later than the invoice date. If the report uses recorded dates, a sale invoiced in August but recorded in September belongs to September.', ['REPORT-STD-SEP']],
  invoice_on: ['invoice_on — the invoice date', 'The date on the sales invoice. If the report uses invoice dates, a September invoice belongs to September even if it enters the system in October. Bluebird uses this rule in September; the standard profile switches to it in October.', ['REPORT-BLUEBIRD','REPORT-STD-OCT']],
  RETURN: ['RETURN — a transaction label that needs context', 'A return usually reduces sales. In the signed v1 format, however, a positive RETURN reverses an earlier return and adds money back. In v2 the amount is a nonnegative size and the RETURN label tells the report to subtract it.', ['FEED-ATLAS-1','FEED-ATLAS-2']],
  SALE: ['SALE — a sales transaction', 'A record representing a sale. It counts only if the approved date and transaction-type rules include it in the reporting month.', ['REPORT-STD-SEP','REPORT-STD-OCT']],
  TRANSFER: ['TRANSFER — an internal movement, not automatically a sale', 'These rows represent internal movement. The demo’s approved sales rules exclude them. Northstar has asked to include them, but that request is still awaiting business approval.', ['REPORT-STD-SEP','DH-204']],
  'return reversal': ['Return reversal — undoing a previous refund', 'If a $50 refund is reversed, sales increase by $50. In ATLAS v1 this appears as a positive RETURN. Forcing every RETURN to be negative would count the reversal as another refund.', ['FEED-ATLAS-1']],
  profile: ['Reporting profile — the customer’s selected rule set', 'The standard profile uses the general sales definition. The Bluebird and Cedar profiles refer to customer-specific agreements. A profile is a configuration choice, not a file format.', ['REPORT-STD-SEP','REPORT-BLUEBIRD','REPORT-CEDAR-A','REPORT-CEDAR-B']],
  'effective date': ['Effective date — when a rule is allowed to apply', 'A document can be approved and still not apply to the month under investigation. Start dates are inclusive; end dates are exclusive. The workflow checks the first day of the report month.', ['REPORT-STD-SEP','REPORT-STD-OCT']],
  'Data Integrations': ['Data Integrations — the fictional source-data team', 'Owns the ATLAS export format contracts and invalid export data in this scenario. A malformed source row should be corrected or quarantined by this team, rather than silently repaired by the report.', ['DH-188','FEED-ATLAS-2']],
  'Reporting Engineering': ['Reporting Engineering — the fictional implementation team', 'Owns report code and configuration defects in this scenario. It implements an approved rule; it does not decide which conflicting business agreement should win.', ['DH-188']],
  'Reporting Product': ['Reporting Product — the fictional rule owner', 'Owns the standard definition of the sales metric and approval of reporting changes. A conflicting or missing business decision needs an owner’s resolution before engineering changes the behavior.', ['REPORT-STD-SEP','REPORT-STD-OCT','DH-204']],
  'Customer Reporting': ['Customer Reporting — the fictional customer-agreement owner', 'Owns the Bluebird and Cedar addenda. An addendum is a customer-specific addition or exception to the default reporting agreement.', ['REPORT-BLUEBIRD','REPORT-CEDAR-A','REPORT-CEDAR-B']]
};
const statusHelp = {
  approved: 'Approved — still check customer, version and dates.',
  draft: 'Draft — a proposal, not an approved rule.',
  pending_approval: 'Pending approval — a request, not authorization.',
  done: 'Done — this work item is complete; read what it actually changed.'
};
const decisionHelp = {
  calculation_defect: ['Fix the calculation', 'The code transforms at least one included amount incorrectly.'],
  configuration_defect: ['Correct the report settings', 'The deployed date or transaction-type settings disagree with the applicable rule.'],
  configuration_and_calculation_defect: ['Fix both settings and calculation', 'Changing the configuration alone leaves incorrect transaction amounts.'],
  expected_behavior: ['Explain the existing result', 'The current report agrees with the applicable rules; a discrepancy alone does not justify changing code.'],
  insufficient_evidence: ['Stop and obtain an approved rule', 'The available evidence does not justify confirming a total.'],
  conflicting_policy: ['Stop and resolve the policy conflict', 'Applicable approved documents disagree. A business owner must decide which governs.'],
  invalid_source_data: ['Stop and correct the source data', 'The inputs violate the data contract or required shape. Do not silently alter them to make the total look plausible.']
};
const rxEscape = value => value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
function sourceLink(id,label){return `<a class="source-link" href="/documents/${encodeURIComponent(id)}" data-source="${esc(id)}" title="Open the complete source">${esc(label||id)}</a>`;}
function termLink(key,label){return `<a class="term-link" href="/?term=${encodeURIComponent(key)}" data-term="${esc(key)}">${esc(label||key)}</a>`;}
function scopeDescription(doc){const s=doc.scope;return s.feed?'ATLAS exports'+(s.schema_version?' · file version '+s.schema_version:' · all versions'):(s.customer==='*'?'Default reporting profile':s.customer+' customer profile')+' · net sales';}
function linkReferences(root){
  if(!root||!reader.documents.size)return;
  const aliases={Atlas:'ATLAS',Northstar:'NORTHSTAR',Bluebird:'BLUEBIRD',Cedar:'CEDAR'};
  const keys=[...reader.documents.keys(),...Object.keys(terms),...Object.keys(aliases)].sort((a,b)=>b.length-a.length);
  const pattern=new RegExp('\\b('+keys.map(rxEscape).join('|')+')\\b','g');
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];let node;
  while(node=walker.nextNode())if(!node.parentElement.closest('a,button,summary,textarea,script,style,select,option,[data-no-link]'))nodes.push(node);
  for(const textNode of nodes){let last=0,match;pattern.lastIndex=0;const fragment=document.createDocumentFragment();
    while(match=pattern.exec(textNode.textContent)){fragment.append(document.createTextNode(textNode.textContent.slice(last,match.index)));const key=match[0],a=document.createElement('a');a.textContent=key;
      if(reader.documents.has(key)){a.href='/documents/'+encodeURIComponent(key);a.dataset.source=key;a.className='source-link';a.title=sourceNotes[key][0];}
      else{const term=aliases[key]||key;a.href='/?term='+encodeURIComponent(term);a.dataset.term=term;a.className='term-link';a.title=terms[term][0];}
      fragment.append(a);last=pattern.lastIndex;
    }
    if(last){fragment.append(document.createTextNode(textNode.textContent.slice(last)));textNode.replaceWith(fragment);}
  }
}
function showReader(title,html,remember=true){
  const dialog=$('#readerDialog');
  if(remember&&dialog.open)reader.history.push({title:$('#readerTitle').textContent,html:$('#readerBody').innerHTML});
  $('#readerTitle').textContent=title;$('#readerBody').innerHTML=html;
  $('#readerBack').hidden=!reader.history.length;
  if(!dialog.open)dialog.showModal();
  $('#readerBody').scrollTop=0;linkReferences($('#readerBody'));$('#readerClose').focus();
}
function openSource(id){
  const snapshot=reader.documents.get(id);if(!snapshot)return;
  const doc=snapshot.document,note=sourceNotes[id];
  const period=doc.effective_from+' onward'+(doc.effective_to?' until '+doc.effective_to+' (end date excluded)':' · no end date specified');
  let context='';const c=reader.current?.case;
  if(c){const asOf=c.month+'-01';const outside=asOf<doc.effective_from||(doc.effective_to&&asOf>=doc.effective_to);
    context=outside?'This document is outside the effective period of the selected '+monthName(c.month)+' report.':'Its date window covers the selected '+monthName(c.month)+' report. Check customer and file-version scope as well.';
    if(doc.status==='draft'||doc.status==='pending_approval')context+=' Its status does not establish an approved requirement.';
  }
  showReader(doc.title,`<div class="reader-id">${esc(id)} · ${doc.system==='jira'?'Jira snapshot':'Business document'} · fictional source</div><div class="reader-notice">${esc(statusHelp[doc.status])}</div><h3>In plain English <small>· reader explanation</small></h3><p>${esc(note[1])}</p><dl class="source-meta"><dt>Owner</dt><dd>${esc(doc.owner)}</dd><dt>Applies to</dt><dd>${esc(scopeDescription(doc))}</dd><dt>Effective period</dt><dd>${esc(period)}</dd><dt>Document revision</dt><dd>${esc(doc.version)} — separate from the transaction’s file version</dd></dl><p class="reader-context">${esc(context)}</p><h3>Complete original source text</h3><blockquote class="original-source">${esc(doc.body)}</blockquote><p><a href="/documents/${encodeURIComponent(id)}" target="_blank" rel="noopener">Open this document as its own page ↗</a></p><details><summary>Source record and verification hash</summary><p>Raw docs mode reads the prose and metadata. The guided calculator also uses the hand-authored rules below.</p><pre>${esc(JSON.stringify(doc,null,2))}</pre><small>SHA256 ${esc(snapshot.sha256)}</small></details>`);
}
function openTerm(key){const term=terms[key];if(!term)return;showReader(term[0],`<p>${esc(term[1])}</p><h3>Read the related sources</h3><ul>${term[2].map(id=>'<li>'+sourceLink(id,sourceNotes[id][0])+' <small>'+esc(id)+'</small></li>').join('')}</ul>`);}
function sourceCard(id){const doc=reader.documents.get(id).document,note=sourceNotes[id];return `<article class="evidence-card"><div class="evidence-type">${doc.system==='jira'?'Jira record':'Business rule / agreement'} · <span class="source-status ${esc(doc.status)}">${esc(doc.status.replaceAll('_',' '))}</span></div><h3>${sourceLink(id,note[0])}</h3><p>${esc(note[1])}</p><div class="evidence-meta">${sourceLink(id)} · ${esc(doc.owner)}</div></article>`;}
function renderLibrary(){const query=$('#sourceSearch').value.trim().toLowerCase();const ids=[...reader.documents.keys()].filter(id=>JSON.stringify(reader.documents.get(id).document).toLowerCase().includes(query)||sourceNotes[id].join(' ').toLowerCase().includes(query));$('#sourceLibrary').innerHTML=ids.length?ids.map(sourceCard).join(''):'<p>No matching sources.</p>';linkReferences($('#sourceLibrary'));}
function readerLoadCase(data){
  reader.current=data;
  $('#caseSourceList').innerHTML=caseSources[data.case.id].map(sourceCard).join('');
  $('#sourceCaseLabel').textContent='Evidence to read for '+data.case.id;
  $('#worked').open=false;$('#walkthrough').innerHTML='';$('#walkthroughButton').disabled=false;
  $('#caseContext').innerHTML=`<b>Who is involved?</b> ${termLink(data.case.customer)} is the customer. ${termLink('ATLAS')} supplied these transaction rows. Our demo reporting code turned them into the application total. You are reviewing the support team’s next action.`;
  linkReferences($('.case-card'));linkReferences($('#caseSourceList'));
}
async function showWalkthrough(){
  const caseId=reader.current.case.id;$('#walkthroughButton').disabled=true;
  try{if(!reader.walkthroughs.has(caseId))reader.walkthroughs.set(caseId,(await api('/api/walkthroughs/'+caseId)).report);if(reader.current.case.id!==caseId)return;
    const r=reader.walkthroughs.get(caseId),decision=decisionHelp[r.decision];
    let html=`<div class="reader-notice"><b>Prepared teaching example — not a model run.</b> This is calculated from the demo’s hand-authored approved rules. It reveals the fixture answer and is never supplied to raw model sessions.</div><h3>${esc(decision[0])}</h3><p>${esc(decision[1])}</p><div class="worked-total">Rule-based reference: <b>${r.expected_total_cents===null?'No justified total':money(r.expected_total_cents)}</b></div>`;
    if(r.policy)html+=`<p><b>1. Decide which rows belong in the report.</b> ${sourceLink(r.policy.source_id)} uses ${termLink(r.policy.date_basis)} and includes ${esc(r.policy.included_kinds.join(' and '))}.</p>`;
    if(r.ledger.length){html+='<p><b>2. Interpret each amount using its export contract.</b> The table compares what the application did with what the approved rule requires.</p><div class="table-wrap"><table><thead><tr><th>Row</th><th>Source amount</th><th>Application counted</th><th>Rule requires</th><th>Why / source</th></tr></thead><tbody>';
      for(const row of r.ledger){const doc=reader.documents.get(row.feed_source).document;const explanation=row.reason==='outside_policy_month'?'Outside the reporting month using the approved date.':row.reason==='excluded_record_kind'?'This transaction type is excluded.':doc.rules.encoding==='signed'?'Keep the source sign, including positive return reversals.':'Use the type: add sales and subtract return sizes.';
        html+=`<tr class="${row.difference_cents?'row-difference':''}"><td>${esc(row.row_id)}</td><td>${money(row.raw_amount_cents)}</td><td>${money(row.observed_cents)}</td><td>${money(row.expected_cents)}</td><td class="row-explanation">${esc(explanation)} ${sourceLink(row.feed_source)} · ${sourceLink(row.policy_source)}</td></tr>`;
      }html+='</tbody></table></div>';html+=`<p><b>3. Add the required contributions.</b> ${r.ledger.map((row,index)=>index?(row.expected_cents<0?' − ':' + ')+money(Math.abs(row.expected_cents)):money(row.expected_cents)).join('')} = <b>${money(r.expected_total_cents)}</b>.</p>`;
    }
    html+=r.messages.map(message=>'<p class="reader-notice">'+esc(message)+'</p>').join('');
    html+=`<h3>What should happen next?</h3><p>${esc(r.next_action)}</p><p><b>Evidence used by this calculation:</b> ${r.sources.map(id=>sourceLink(id)).join(', ')}</p>`;
    $('#walkthrough').innerHTML=html;linkReferences($('#walkthrough'));
  }catch(e){$('#walkthrough').textContent='Could not load the worked example: '+e.message;}finally{if(reader.current.case.id===caseId)$('#walkthroughButton').disabled=false;}
}
function annotateRun(result){
  const notes=[...(result.restore_warnings||[])];if(result.comparability_warning)notes.unshift(result.comparability_warning);
  $('#runWarnings').innerHTML=notes.map(note=>'<p class="reader-notice">'+esc(note)+'</p>').join('');
  const cited=new Set();const pattern=new RegExp('\\b('+[...reader.documents.keys()].sort((a,b)=>b.length-a.length).map(rxEscape).join('|')+')\\b','g');
  const text=(result.answer||'')+' '+JSON.stringify(result.packet||{});for(const match of text.matchAll(pattern))cited.add(match[0]);
  $('#answerSources').innerHTML=cited.size?'<h3>Open the sources named in this answer</h3><p class="subtle">These are references in the model response, not a guarantee that every claim is supported. Read the original source to check.</p><div class="source-chips">'+[...cited].map(id=>sourceLink(id,sourceNotes[id][0])).join('')+'</div>':'';
  linkReferences($('#result'));linkReferences($('#trace'));
}
async function initReader(){
  const data=await api('/api/documents');reader.documents=new Map(data.documents.map(snapshot=>[snapshot.document.id,snapshot]));
  $('#termList').innerHTML=Object.keys(terms).map(key=>'<li>'+termLink(key,terms[key][0])+'</li>').join('');renderLibrary();
  $('#sourceSearch').oninput=renderLibrary;$('#walkthroughButton').onclick=showWalkthrough;
  $('#readerClose').onclick=()=>$('#readerDialog').close();
  $('#readerDialog').addEventListener('close',()=>{reader.history=[];});
  $('#readerBack').onclick=()=>{const previous=reader.history.pop();if(previous)showReader(previous.title,previous.html,false);};
  document.addEventListener('click',event=>{if(event.target.closest('a[href="#referenceDesk"]'))$('#referenceDesk').open=true;const link=event.target.closest('a[data-source],a[data-term]');if(!link||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();if(link.dataset.source)openSource(link.dataset.source);else openTerm(link.dataset.term);});
  linkReferences($('#orientation'));const params=new URLSearchParams(location.search);if(terms[params.get('term')])openTerm(params.get('term'));
}
