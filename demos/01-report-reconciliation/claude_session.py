"""One fresh Claude Code session per workflow step, streamed as display events.

Follows live_runner.Run.execute: restricted CLI flags, a hard deadline, cancellation
and process-group cleanup. Tool activity and answer text are surfaced; thinking never is.
"""
from dataclasses import dataclass, field
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

from agent import _objects
from catalog import ROOT, digest
import context_mcp
from live_runner import stop_process

CONTEXT_TOOLS = [f"mcp__context__{name}" for name in context_mcp.TOOLS]


class Cancelled(Exception):
    """The presenter stopped the workflow."""


@dataclass
class Session:
    output: dict | None = None
    answer: str = ""
    cost_usd: float | None = None
    models: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    fetched: dict = field(default_factory=dict)  # source ID -> SHA256 of a verified context fetch
    denials: list = field(default_factory=list)  # tool calls refused by the step's allow-list
    lookups: int = 0
    tool_calls: int = 0
    elapsed_seconds: float = 0.0


def session_command(tools, schema, model, budget, *, context=True, system_prompt=None, allow=None):
    # Same isolation as the raw modes, minus --safe-mode, which also disables MCP servers.
    # allow can narrow a tool to patterns such as "Bash(git push:*)"; anything else is refused.
    servers = {"context": {"command": sys.executable, "args": [str(ROOT / "context_mcp.py")]}} if context else {}
    allowed = list(allow if allow is not None else tools) + (CONTEXT_TOOLS if context else [])
    command = [shutil.which("claude") or "claude", "--print", "--output-format", "stream-json", "--verbose",
               "--restricted", "--tools", ",".join(tools), "--permission-mode", "dontAsk", "--setting-sources", "",
               "--strict-mcp-config", "--mcp-config", json.dumps({"mcpServers": servers}),
               "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
               "--json-schema", json.dumps(schema), "--max-budget-usd", str(budget)]
    if allowed:
        command += ["--allowedTools", ",".join(allowed)]
    if system_prompt:
        command += ["--append-system-prompt", system_prompt]
    if model:
        command += ["--model", model]
    return command


def clip(value, limit=4000):
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[:limit] + f"… [{len(text) - limit} more characters in the saved trace]"


def consume(event, uses, session, emit, known, inputs=None):
    inputs = {} if inputs is None else inputs
    if event.get("type") == "system" and event.get("subtype") == "init":
        if event.get("model"):
            session.models = sorted(set(session.models) | {event["model"]})
        emit("session", model=event.get("model"))
    message = event.get("message") or {}
    blocks = message.get("content", []) if isinstance(message, dict) else []
    if not isinstance(blocks, list):
        return
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if event.get("type") == "assistant" and block.get("type") == "tool_use":
            name = block.get("name")
            uses[block.get("id")] = name
            inputs[block.get("id")] = block.get("input") or {}
            if name == "StructuredOutput":
                continue
            tool = name.removeprefix("mcp__context__") if isinstance(name, str) else name
            if tool in context_mcp.TOOLS:
                session.lookups += 1
                emit("lookup", tool_id=block.get("id"), system=context_mcp.TOOLS[tool],
                     text=context_mcp.describe_call(tool, block.get("input") or {}), input=block.get("input", {}))
            else:
                session.tool_calls += 1
                emit("tool_call", tool_id=block.get("id"), name=name, input=block.get("input", {}))
        elif event.get("type") == "user" and block.get("type") == "tool_result":
            name = uses.get(block.get("tool_use_id"))
            tool = name.removeprefix("mcp__context__") if isinstance(name, str) else name
            if name == "StructuredOutput":
                continue
            if tool in context_mcp.TOOLS and not block.get("is_error"):
                objects = list(_objects(block.get("content")))
                result = next((obj for obj in objects if "document" in obj or "results" in obj
                               or obj.get("status") in {"not_found", "invalid_request", "no_results"}), None)
                for obj in objects:
                    doc = obj.get("document")
                    # Count a source as read only when the returned record matches the snapshot exactly.
                    if isinstance(doc, dict) and known.get(doc.get("id")) == doc and obj.get("sha256") == digest(doc):
                        session.fetched[doc["id"]] = obj["sha256"]
                emit("lookup_result", tool_id=block.get("tool_use_id"), text=context_mcp.describe_result(result))
            elif block.get("is_error") and "Permission to use" in json.dumps(block.get("content")):
                # Refused by the allow-list: shown as a guardrail at work, not a crash.
                attempted = inputs.get(block.get("tool_use_id"), {})
                session.denials.append({"tool": name, "input": attempted})
                emit("denied", tool_id=block.get("tool_use_id"), name=name,
                     text=f"Blocked by this step's permissions: {name} {clip(attempted.get('command') or attempted.get('file_path') or '', 160)}".strip())
            else:
                emit("tool_result", tool_id=block.get("tool_use_id"), error=bool(block.get("is_error")),
                     content=clip(block.get("content")))
        elif event.get("type") == "assistant" and block.get("type") == "text":
            emit("message", text=block.get("text", ""))


def run_session(command, prompt, cwd, *, timeout, cancel, emit, record_dir):
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / "prompt.txt").write_text(prompt)
    session, uses, inputs, final, known = Session(), {}, {}, {}, context_mcp.records()
    started = time.monotonic()
    with (record_dir / "stderr.txt").open("w") as stderr, (record_dir / "trace.jsonl").open("w") as trace:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                   text=True, start_new_session=True,
                                   env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        try:
            process.stdin.write(prompt)
            process.stdin.close()
            lines = queue.Queue()

            def read_stdout():
                try:
                    for line in process.stdout:
                        lines.put(line)
                finally:
                    lines.put(None)

            reader = threading.Thread(target=read_stdout, daemon=True)
            reader.start()
            deadline, ended = time.monotonic() + timeout, False
            while not ended or process.poll() is None:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() >= deadline:
                    session.errors.append(f"Timed out after {timeout} seconds. Saved; not retried.")
                    break
                if ended:
                    # EOF is not process completion; keep the deadline and cancellation active.
                    try:
                        process.wait(timeout=0.15)
                    except subprocess.TimeoutExpired:
                        pass
                    continue
                try:
                    line = lines.get(timeout=0.15)
                except queue.Empty:
                    continue
                if line is None:
                    ended = True
                    continue
                trace.write(line)
                trace.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    if event.get("type") == "result":
                        final = event
                    consume(event, uses, session, emit, known, inputs)
            reader.join(timeout=2)
        finally:
            stop_process(process)
    session.elapsed_seconds = round(time.monotonic() - started, 2)
    session.answer = final.get("result") if isinstance(final.get("result"), str) else ""
    session.output = final.get("structured_output") if isinstance(final.get("structured_output"), dict) else None
    session.cost_usd = final.get("total_cost_usd")
    if not session.models:
        session.models = sorted((final.get("modelUsage") or {}).keys())
    if not final or final.get("is_error"):
        session.errors.append("Claude did not return a successful final response" + (": " + str(final.get("subtype")) if final else "."))
    if session.output is None and not session.errors:
        session.errors.append("Claude returned no structured output.")
    (record_dir / "output.json").write_text(json.dumps({"output": session.output, "answer": session.answer,
        "cost_usd": session.cost_usd, "models": session.models, "errors": session.errors,
        "fetched": session.fetched, "denials": session.denials, "elapsed_seconds": session.elapsed_seconds}, indent=2) + "\n")
    return session
