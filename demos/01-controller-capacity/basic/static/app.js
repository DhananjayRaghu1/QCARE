"use strict";

const byId = (id) => document.getElementById(id);
const make = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined && value !== null) node.textContent = String(value);
  return node;
};
const showError = (id, message) => {
  const node = byId(id);
  node.textContent = message || "";
  node.classList.toggle("hidden", !message);
};
const list = (value) => Array.isArray(value) ? value : [];

function activatePanel(id) {
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("hidden", panel.id !== id));
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.panel === id;
    tab.classList.toggle("active", active);
    if (active) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  });
}
document.querySelectorAll("[data-panel]").forEach((button) => button.addEventListener("click", () => activatePanel(button.dataset.panel)));

async function fetchJSON(url, signal) {
  const response = await fetch(url, { signal, cache: "no-store" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

let citations = new Map();
let citationNumbers = new Map();
function selectCitation(id) {
  const citation = citations.get(id);
  if (!citation) return;
  byId("source-title").textContent = `Reference ${citationNumbers.get(id)}`;
  const content = byId("source-content");
  content.replaceChildren();
  content.append(make("p", "source-label", citation.source || "Source record"));
  content.append(make("p", "source-range", `${citation.kind === "code" ? "Code" : "Company record"} · lines ${citation.line_start}–${citation.line_end}`));
  content.append(make("pre", `source-excerpt${citation.kind === "code" ? " code" : ""}`, citation.excerpt || "No excerpt supplied."));
  byId("source-inspector").querySelector(":scope > .muted").classList.add("hidden");
  document.querySelectorAll(".citation-button").forEach((button) => {
    const active = button.dataset.citation === id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (window.innerWidth <= 800) byId("source-inspector").scrollIntoView({ block: "start" });
}
function appendCitations(target, ids) {
  const refs = make("span", "citations");
  list(ids).forEach((id) => {
    if (!citations.has(id)) return;
    const button = make("button", "citation-button", citationNumbers.get(id));
    button.type = "button";
    button.dataset.citation = id;
    button.title = `Read ${citations.get(id).source}, lines ${citations.get(id).line_start}–${citations.get(id).line_end}`;
    button.setAttribute("aria-label", `Open reference ${citationNumbers.get(id)}: ${citations.get(id).source}`);
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => selectCitation(id));
    refs.append(button);
  });
  if (refs.childElementCount) target.append(refs);
}
function factParagraph(fact) {
  const p = make("p", "", fact?.text || "Unknown — no supporting source was retrieved.");
  appendCitations(p, fact?.citations);
  return p;
}
function section(title) {
  const node = make("section", "packet-section");
  node.append(make("h3", "", title));
  return node;
}
function resetPacket(message, detail) {
  byId("packet-layout").classList.add("hidden");
  byId("packet").replaceChildren();
  byId("source-content").replaceChildren();
  byId("source-title").textContent = "Open a citation";
  byId("source-inspector").querySelector(":scope > .muted").classList.remove("hidden");
  citations = new Map();
  citationNumbers = new Map();
  const empty = byId("packet-empty");
  empty.classList.remove("hidden");
  empty.replaceChildren(make("strong", "", message), make("span", "", detail));
}
function renderMetadata(metadata) {
  const target = byId("run-meta");
  target.replaceChildren();
  const local = metadata.mode === "local-sample";
  const seconds = typeof metadata.elapsed_seconds === "number" ? `${metadata.elapsed_seconds.toFixed(1)} s` : "Not recorded";
  const values = [
    ["Execution", local ? "Deterministic sample" : metadata.agent_run === false ? "No agent execution" : "Recorded Claude Code run"],
    ["Mode", metadata.mode === "repo-only" ? "Repository only" : local ? "Local sources" : "Company knowledge + repository"],
    ["Model", metadata.model || (local ? "No model used" : "Not recorded")],
    ["Elapsed", seconds],
    ["Run status", metadata.status || "Unknown"],
    ["Citation checks", metadata.validation?.status || "Not checked"],
    ["Claim review", metadata.claim_review || "Pending"],
    ["Sources during run", metadata.sources_unchanged === true ? "Unchanged" : metadata.sources_unchanged === false ? "Changed" : "Not recorded"],
  ];
  if (metadata.question) values.push(["Focus", metadata.question]);
  values.forEach(([label, value]) => {
    const item = make("div", "", label);
    item.append(make("strong", "", value));
    target.append(item);
  });
  target.classList.remove("hidden");
  const notice = byId("run-notice");
  const succeeded = ["success", "complete", "validated"].includes(metadata.status);
  notice.className = `run-notice${local ? " sample" : ""}${metadata.validation?.status !== "valid" || !succeeded ? " failed" : ""}`;
  notice.textContent = local
    ? "Deterministic sample · prepared from local sources. This is not Claude output or a live agent verification."
    : metadata.agent_run === false
      ? `Recorded attempt / replay · ${metadata.recorded_at || "recording time unknown"}. No agent execution was recorded.`
      : `Recorded run / replay · ${metadata.recorded_at || "recording time unknown"}. This viewer does not start model calls.`;
  if (!succeeded) notice.textContent += ` Run status: ${metadata.status || "unknown"}; no success packet is displayed.`;
  if (metadata.sources_unchanged === false) notice.textContent += " Source files changed during this run.";
}
function renderPacket(result) {
  const metadata = result.metadata || {};
  renderMetadata(metadata);
  const packet = result.packet;
  if (!packet) {
    resetPacket("No validated packet for this run", result.error || metadata.reason || "Inspect the terminal output and validation errors before retrying.");
    const errors = [...list(metadata.validation?.errors), ...list(metadata.problems)];
    if (errors.length) {
      const ul = make("ul", "warning-list");
      errors.forEach((error) => ul.append(make("li", "", typeof error === "string" ? error : JSON.stringify(error))));
      byId("packet-empty").append(ul);
    }
    return;
  }
  citations = new Map(list(packet.citations).map((citation) => [citation.id, citation]));
  citationNumbers = new Map(list(packet.citations).map((citation, index) => [citation.id, index + 1]));
  byId("packet-empty").classList.add("hidden");
  byId("packet-layout").classList.remove("hidden");
  const target = byId("packet");
  target.replaceChildren();
  const top = make("div", "packet-topline");
  top.append(make("span", "pill", packet.ticket_id || metadata.ticket_id || "Context packet"));
  const words = metadata.validation?.word_count;
  top.append(make("span", "muted", typeof words === "number" ? `${words} words · context packet` : "Developer context packet"));
  const summary = make("p", "packet-summary", packet.summary);
  appendCitations(summary, packet.summary_citations);
  target.append(top, make("h2", "", "Where to begin"), summary);
  const subsystem = section("Likely subsystem");
  subsystem.append(factParagraph(packet.likely_subsystem));
  target.append(subsystem);
  const files = section("Start in these files");
  list(packet.starting_files).forEach((file) => {
    const item = make("div", "start-file");
    const path = make("code", "", `${file.path}:${file.line_start}–${file.line_end}`);
    appendCitations(path, file.citations);
    item.append(path, make("p", "", file.reason));
    files.append(item);
  });
  if (!list(packet.starting_files).length) files.append(make("p", "", "No supported starting location was found."));
  target.append(files);
  const execution = section("Execution path");
  execution.append(factParagraph(packet.execution_path));
  target.append(execution);
  const history = section("Relevant history");
  list(packet.history).forEach((fact) => history.append(factParagraph(fact)));
  if (!list(packet.history).length) history.append(make("p", "", "Unknown — no company history was retrieved for this run."));
  target.append(history);
  const owner = section("Ownership");
  owner.append(factParagraph(packet.owner));
  target.append(owner);
  const next = section("First investigation");
  next.append(factParagraph(packet.first_investigation));
  target.append(next);
  const unknowns = section("Still unknown");
  const ul = make("ul");
  list(packet.unknowns).forEach((unknown) => ul.append(make("li", "", unknown)));
  if (!ul.childElementCount) ul.append(make("li", "", "No unknowns recorded. Review the scope of this packet."));
  unknowns.append(ul);
  target.append(unknowns);
  const warnings = list(metadata.validation?.warnings);
  if (warnings.length) {
    const warningList = make("ul", "warning-list");
    warnings.forEach((warning) => warningList.append(make("li", "", typeof warning === "string" ? warning : JSON.stringify(warning))));
    target.append(warningList);
  }
  // Evidence is opened only on an explicit reference click; no reference is inferred.
}

let runsSequence = 0;
let runSequence = 0;
let runAbort;
async function loadRun(id) {
  const sequence = ++runSequence;
  if (runAbort) runAbort.abort();
  runAbort = new AbortController();
  showError("global-error", "");
  byId("run-meta").classList.add("hidden");
  byId("run-notice").className = "run-notice";
  byId("run-notice").textContent = "Reading saved output · no model call is started by this viewer.";
  resetPacket("Loading saved output…", "Reading the saved packet and its citation checks.");
  try {
    const result = await fetchJSON(`/api/run?${new URLSearchParams({ id })}`, runAbort.signal);
    if (sequence === runSequence) renderPacket(result);
  } catch (error) {
    if (error.name !== "AbortError" && sequence === runSequence) {
      resetPacket("Saved output unavailable", "No fallback packet was substituted.");
      showError("global-error", error.message);
    }
  }
}
async function loadRuns() {
  const sequence = ++runsSequence;
  const refresh = byId("refresh-runs");
  const select = byId("run-select");
  refresh.disabled = true;
  select.disabled = true;
  showError("global-error", "");
  try {
    const result = await fetchJSON("/api/runs");
    if (sequence !== runsSequence) return;
    select.replaceChildren();
    list(result.runs).forEach((run) => {
      const metadata = run.metadata || {};
      const prefix = metadata.mode === "local-sample" ? "Sample" : metadata.mode === "repo-only" ? "Repo only" : "Augmented";
      const option = make("option", "", `${prefix} · ${metadata.ticket_id || "task"} · ${run.id}${run.packet_available ? "" : " · no validated packet"}`);
      option.value = run.id;
      select.append(option);
    });
    if (!select.options.length) {
      const placeholder = make("option", "", "No saved outputs yet");
      placeholder.value = "";
      select.append(placeholder);
      byId("run-meta").classList.add("hidden");
      resetPacket("No saved packets yet", "Run the onramping command in your terminal, then refresh this viewer.");
    } else {
      const initial = result.default_run_id || result.runs[0].id;
      select.value = initial;
      await loadRun(initial);
    }
    if (result.unreadable_count) showError("global-error", `${result.unreadable_count} saved output${result.unreadable_count === 1 ? " could" : "s could"} not be read. Check their local artifact files.`);
  } catch (error) {
    if (sequence === runsSequence) {
      resetPacket("Saved outputs unavailable", "No fallback packet was substituted.");
      showError("global-error", error.message);
    }
  } finally {
    if (sequence === runsSequence) {
      refresh.disabled = false;
      select.disabled = !select.options.length || !select.options[0].value;
    }
  }
}
byId("refresh-runs").addEventListener("click", loadRuns);
byId("run-select").addEventListener("change", () => loadRun(byId("run-select").value));

function citeLabel(citation) {
  const source = citation.source || "Synthetic source";
  if (citation.line_start === undefined) return source;
  return `${source} · lines ${citation.line_start}–${citation.line_end === undefined ? citation.line_start : citation.line_end}`;
}
function renderTicket(ticket) {
  const target = byId("ticket-content");
  target.replaceChildren();
  if (!ticket || ticket.status !== "ok") {
    const box = make("div", "empty-state");
    box.append(make("strong", "", "No exact ticket found"), make("span", "", ticket?.reason || "This ID is absent from the synthetic fixture."));
    target.append(box);
    return;
  }
  target.append(make("p", "ticket-id", ticket.id || "Exact ticket"));
  const lines = String(ticket.content || "").split("\n");
  const titleIndex = lines.findIndex((line) => /^#\s+/.test(line));
  let title = "Ticket content";
  if (titleIndex >= 0) {
    title = lines[titleIndex].replace(/^#\s+/, "");
    lines.splice(titleIndex, 1);
  }
  target.append(make("h3", "ticket-title", title), make("div", "ticket-text", lines.join("\n").trim()));
  const label = list(ticket.citations).length ? citeLabel(ticket.citations[0]) : ticket.source;
  if (label) target.append(make("p", "source-origin", label));
}
function renderSearch(result) {
  const target = byId("search-results");
  target.replaceChildren();
  const results = list(result?.results);
  byId("search-mode-label").textContent = result?.mode ? result.mode.toUpperCase() : "";
  byId("search-caption").textContent = `${results.length} source${results.length === 1 ? "" : "s"} returned`;
  if (result?.status === "unavailable" || result?.status === "invalid_request" || !results.length) {
    const box = make("div", "empty-state");
    box.append(make("strong", "", result?.status === "unavailable" ? "Retrieval mode unavailable" : result?.status === "invalid_request" ? "Invalid search request" : "No matching sources"));
    box.append(make("span", "", result?.reason || "No evidence was returned for this query."));
    target.append(box);
    return;
  }
  results.forEach((source, index) => {
    const card = make("article", "source-card");
    const meta = make("div", "source-meta");
    meta.append(make("span", "", `${String(index + 1).padStart(2, "0")} · ${source.id || "source"}`));
    meta.append(make("span", "", typeof source.score === "number" && Number.isFinite(source.score) ? `Score ${source.score.toFixed(3)}` : ""));
    card.append(meta, make("h3", "", source.title || source.source || "Knowledge source"));
    const passages = list(source.citations);
    if (passages.length) passages.forEach((citation) => card.append(make("p", "source-passage", citation.text || ""), make("p", "source-origin", citeLabel(citation))));
    else card.append(make("p", "source-passage", source.content || "No passage supplied."));
    if (source.content && passages.length) {
      const detail = make("details", "source-detail");
      detail.append(make("summary", "", "Read full source"), make("p", "source-passage", source.content));
      card.append(detail);
    }
    target.append(card);
  });
}
let ticketSequence = 0;
let searchSequence = 0;
let ticketAbort;
let searchAbort;
byId("ticket-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = byId("ticket-id").value.trim();
  if (!id) return;
  const sequence = ++ticketSequence;
  if (ticketAbort) ticketAbort.abort();
  ticketAbort = new AbortController();
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  button.textContent = "Fetching…";
  showError("ticket-error", "");
  byId("ticket-content").replaceChildren(make("p", "muted", `Fetching ${id}…`));
  try {
    const ticket = await fetchJSON(`/api/ticket?${new URLSearchParams({ id })}`, ticketAbort.signal);
    if (sequence === ticketSequence) renderTicket(ticket);
  } catch (error) {
    if (error.name !== "AbortError" && sequence === ticketSequence) {
      byId("ticket-content").replaceChildren();
      showError("ticket-error", error.message);
    }
  } finally {
    if (sequence === ticketSequence) {
      button.disabled = false;
      button.textContent = "Fetch";
    }
  }
});
byId("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const q = byId("search-query").value.trim();
  const mode = byId("search-mode").value;
  if (!q) return;
  const sequence = ++searchSequence;
  if (searchAbort) searchAbort.abort();
  searchAbort = new AbortController();
  const button = byId("search-submit");
  button.disabled = true;
  button.textContent = "Searching…";
  showError("search-error", "");
  byId("search-caption").textContent = "Searching the fixture…";
  byId("search-results").replaceChildren();
  try {
    const result = await fetchJSON(`/api/search?${new URLSearchParams({ q, mode })}`, searchAbort.signal);
    if (sequence === searchSequence) renderSearch(result);
  } catch (error) {
    if (error.name !== "AbortError" && sequence === searchSequence) {
      byId("search-caption").textContent = "Search failed";
      showError("search-error", error.message);
    }
  } finally {
    if (sequence === searchSequence) {
      button.disabled = false;
      button.textContent = "Search";
    }
  }
});
loadRuns();
