'use strict';
// Workflow diagrams for Demos 2 and 3. Fixed Mermaid source rendered by the vendored
// Mermaid (vendor/mermaid.min.js); no model output ever enters a diagram.
(() => {
const CLASSES = `
  classDef code fill:#eef1ea,stroke:#8d9c84,color:#193b38
  classDef ai fill:#e4eefb,stroke:#4f7cc4,color:#14305c
  classDef you fill:#fff1cf,stroke:#c99c38,color:#4a3300
  linkStyle default stroke:#8d9c84,stroke-width:1.5px`;
const DIAGRAMS = {
  export: {
    caption: 'Grey steps are code, blue steps are separate Claude sessions, gold steps wait for you. Build, review and the rules check repeat for at most 3 rounds.',
    steps: ['Jira ticket and your note', 'Claude gathers context and finds conflicts', 'You decide any conflict before code is written', 'Claude writes the code and tests on its own branch', 'A separate Claude session reviews it', 'Rules in code check it; failures go back to the build', 'You approve or send it back', 'The draft PR is marked ready for your team’s review'],
    source: `flowchart LR
  T["Jira ticket<br/>+ your note"]:::code --> A["Gather context<br/>& find conflicts"]:::ai
  A --> D{{"You decide<br/><i>only if a conflict</i>"}}:::you
  subgraph L["Build loop · up to 3 rounds"]
    direction LR
    B["Write code<br/>on a branch"]:::ai --> R["Independent<br/>review"]:::ai --> G["Rules check<br/>in code"]:::code
    G -. not met .-> B
  end
  D --> B
  G -- met --> Y{{"Your review"}}:::you
  Y -. send back .-> A
  Y -- approve --> P["Draft PR ready<br/>for team review"]:::code
  style L fill:#fbfcf8,stroke:#b9c6ae,stroke-dasharray:4 3,color:#526a5b`},
  migration: {
    caption: 'With business context off, the replay still runs, but Claude cannot see the agreements, usage or owners. The gate rules are the same.',
    steps: ['A cleanup PR whose CI is green', 'Code replays recent jobs on the old and new code', 'Claude maps who depends on it and what is owed', 'Rules in code allow or block each dependent', 'You choose what happens next', 'Code drafts the PR review, sign-off requests and decision record; nothing is sent'],
    source: `flowchart LR
  P["Cleanup PR<br/>CI is green"]:::code --> R["Replay recent jobs<br/>old vs new code"]:::code
  R --> M["Map who depends on it<br/>& what they were promised"]:::ai
  M --> G["Release gate in code<br/>allow or block"]:::code
  G --> Y{{"You decide<br/>what happens next"}}:::you
  Y --> H["Draft review,<br/>sign-offs & record"]:::code`},
};
const LEGEND = '<div class="wf-legend"><span class="code">Code</span><span class="ai">Claude</span><span class="you">You</span></div>';
let ready = false, counter = 0;

async function renderWorkflowDiagram(root, key){
  const spec = DIAGRAMS[key];
  if(!root || !spec) return;
  const fallback = `<ol class="wf-diagram-steps">${spec.steps.map(step => `<li>${step}</li>`).join('')}</ol>`;
  root.innerHTML = `<figure class="wf-diagram"><div class="wf-diagram-canvas" role="img" aria-label="Workflow: ${spec.steps.join(', then ')}"></div><figcaption>${LEGEND}<span class="small">${spec.caption}</span></figcaption></figure>`;
  const canvas = root.querySelector('.wf-diagram-canvas');
  try{
    if(!window.mermaid) throw new Error('Mermaid did not load');
    if(!ready){
      window.mermaid.initialize({startOnLoad:false, securityLevel:'strict', theme:'base',
        themeVariables:{fontFamily:'Inter, ui-sans-serif, system-ui, sans-serif', fontSize:'15px', primaryColor:'#eef1ea', lineColor:'#8d9c84', edgeLabelBackground:'#fffefb'},
        flowchart:{curve:'basis', nodeSpacing:30, rankSpacing:36, padding:12, htmlLabels:true}});
      ready = true;
    }
    const {svg} = await window.mermaid.render('wf-diagram-' + key + '-' + (++counter), spec.source + CLASSES);
    canvas.innerHTML = svg;
  }catch(error){
    canvas.innerHTML = fallback;
  }
}
window.renderWorkflowDiagram = renderWorkflowDiagram;
// Architecture pages mark the slot with data-diagram="export" or "migration".
const mount = () => document.querySelectorAll('[data-diagram]').forEach(el => renderWorkflowDiagram(el, el.dataset.diagram));
document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', mount) : mount();
})();
