"""Claude client, scoped tool execution, and capture of evidence actually observed."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from guard import MCP_TOOLS
from evidence import PACKET_SCHEMA
from retriever import SOURCES, get_document, get_device

ROOT = Path(__file__).resolve().parent


def digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def capture(evidence: dict, source: str, content: str, spans: list, kind: str, metadata: dict | None = None) -> None:
    previous = evidence["sources"].get(source)
    if previous and previous["content"] != content:
        raise ValueError(f"Source changed during evidence capture: {source}")
    merged = {**(previous or {}).get("metadata", {}), **(metadata or {})}
    devices = {**(previous or {}).get("metadata", {}).get("devices", {}), **(metadata or {}).get("devices", {})}
    if devices:
        merged["devices"] = devices
    evidence["sources"][source] = {"content": content, "sha256": digest(content),
        "spans": sorted({tuple(span) for span in [*(previous or {}).get("spans", []), *spans]}),
        "kind": kind, "metadata": merged}


def payload(result) -> dict:
    if result.isError:
        raise RuntimeError("MCP returned a tool error")
    if result.structuredContent:
        return result.structuredContent
    for block in result.content:
        if block.type == "text":
            return json.loads(block.text)
    raise RuntimeError("MCP returned no JSON payload")


async def mcp_probe(workspace: Path, ticket_id: str, mode: str) -> dict:
    params = StdioServerParameters(command=sys.executable,
        args=[str(ROOT / "mcp_server.py"), "--registry", str(workspace / "app/devices.json")],
        cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(tool.name for tool in (await session.list_tools()).tools)
            if names != ["get_device", "get_document", "get_ticket", "search_knowledge"]:
                raise RuntimeError("Unexpected MCP tool manifest")
            ticket = payload(await session.call_tool("get_ticket", {"ticket_id": ticket_id}))
            if ticket.get("status") != "ok":
                raise ValueError(f"Ticket lookup: {ticket.get('status')}")
            search = payload(await session.call_tool("search_knowledge", {
                "query": "controller capacity firmware", "mode": mode, "top_k": 1}))
            if search.get("status") != "ok":
                raise RuntimeError(f"Retrieval unavailable: {search.get('status')}")
            # Registry consistency check is operator preflight, not agent evidence.
            device = payload(await session.call_tool("get_device", {"controller_id": "DEV-101"}))
            if device.get("content") != (workspace / "app/devices.json").read_text():
                raise RuntimeError("Application and MCP registry differ")
            return {"ticket": ticket, "tools": names, "registry_consistent": True}


def local_probe(workspace: Path, ticket_id: str = "AG-1423", mode: str = "bm25") -> dict:
    return asyncio.run(asyncio.wait_for(mcp_probe(workspace, ticket_id, mode), timeout=30))


def client_preflight() -> dict:
    executable = shutil.which("claude")
    if not executable:
        return {"installed": False, "authenticated": False, "configured_model": None}
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, timeout=10).stdout.strip()
    auth = subprocess.run([executable, "auth", "status"], text=True, capture_output=True, timeout=15)
    try:
        authenticated = json.loads(auth.stdout).get("loggedIn") is True
    except (ValueError, AttributeError):
        authenticated = False
    model = None
    settings = Path.home() / ".claude/settings.json"
    try:
        value = json.loads(settings.read_text()).get("model")
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,150}", value):
            model = value
    except (OSError, ValueError):
        pass
    return {"installed": True, "authenticated": authenticated, "version": version,
            "configured_model": model, "executable": executable}


def client_command(client: dict, workspace: Path, phase: str, context: str, mode: str,
                   schema: dict | None = None, model: str | None = None) -> list[str]:
    config = {"mcpServers": {"engineering-knowledge": {"type": "stdio", "command": sys.executable,
        "args": [str(ROOT / "mcp_server.py"), "--registry", str(workspace / "app/devices.json")],
        "env": {"ONRAMP_RETRIEVAL_MODE": mode}}}} if context == "tools" else {"mcpServers": {}}
    hook = " ".join(shlex.quote(x) for x in [sys.executable, str(ROOT / "guard.py"), str(workspace), phase, context])
    settings = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": hook, "timeout": 10}]}]}}
    native = "Read,Glob,Grep" + (",Write,Edit" if phase != "investigate" else "")
    allowed = native + (("," + ",".join(sorted(MCP_TOOLS))) if context == "tools" else "")
    command = [client["executable"], "--print", "--output-format", "stream-json", "--verbose",
        "--no-session-persistence", "--setting-sources", "", "--settings", json.dumps(settings),
        "--strict-mcp-config", "--mcp-config", json.dumps(config), "--permission-mode", "dontAsk",
        "--tools", native, "--allowedTools", allowed, "--disable-slash-commands", "--no-chrome",
        "--max-budget-usd", "2"]
    selected = model or client.get("configured_model")
    if selected:
        command.extend(["--model", selected])
    if schema:
        command.extend(["--json-schema", json.dumps(schema)])
    return command


def execute_client(command: list[str], prompt: str, workspace: Path, timeout: int) -> dict:
    started = time.monotonic()
    lines, timed_out, channel = [], False, queue.Queue()
    with tempfile.TemporaryFile(mode="w+") as errors:
        process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=errors, text=True, start_new_session=True,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        def consume():
            for line in process.stdout:
                channel.put(line)
            channel.put(None)
        threading.Thread(target=consume, daemon=True).start()
        try:
            process.stdin.write(prompt)
            process.stdin.close()
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    line = channel.get(timeout=min(0.5, remaining))
                except queue.Empty:
                    continue
                if line is None:
                    break
                lines.append(line)
                try:
                    event = json.loads(line)
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use":
                            args = block.get("input", {})
                            detail = args.get("query") or args.get("document_id") or args.get("controller_id") or args.get("file_path") or args.get("pattern") or ""
                            print(f"  {block.get('name')}: {str(detail).replace(str(workspace), '.')[:130]}", flush=True)
                except (ValueError, TypeError, AttributeError):
                    pass
        finally:
            if timed_out or process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
            while not channel.empty():
                line = channel.get_nowait()
                if line:
                    lines.append(line)
            errors.seek(0)
            stderr = errors.read()
    return {"lines": lines, "exit_code": process.returncode, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 2), "stderr": stderr}


def json_payloads(value):
    if isinstance(value, str):
        try:
            yield from json_payloads(json.loads(value))
        except ValueError:
            return
    elif isinstance(value, list):
        for item in value:
            yield from json_payloads(item)
    elif isinstance(value, dict):
        if "status" in value:
            yield value
        if "text" in value:
            yield from json_payloads(value["text"])


def content_text(value) -> str:
    return value if isinstance(value, str) else "\n".join(x.get("text", "") for x in value if isinstance(x, dict)) if isinstance(value, list) else ""


def read_spans(text: str, source: str) -> list:
    lines, numbers = source.splitlines(), []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d+)(?:→|\t)(.*)$", line)
        if match and 1 <= int(match[1]) <= len(lines) and match[2] == lines[int(match[1]) - 1]:
            numbers.append(int(match[1]))
    if not numbers and text.strip() == source.strip():
        return [[1, len(lines)]] if lines else []
    spans = []
    for number in sorted(set(numbers)):
        if spans and number == spans[-1][1] + 1:
            spans[-1][1] = number
        else:
            spans.append([number, number])
    return spans


def collect_trace(lines: list[str], workspace: Path, evidence: dict, phase: str, context: str) -> dict:
    uses, errors, format_errors, tools, models = {}, [], [], [], []
    field_attempts = {}
    result = None
    permitted = {"Read", "Glob", "Grep", "StructuredOutput"} | (MCP_TOOLS if context == "tools" else set())
    if phase != "investigate":
        permitted |= {"Write", "Edit"}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            errors.append("Malformed stream event")
            continue
        if event.get("type") == "system" and event.get("subtype") == "init" and event.get("model"):
            models.append(event["model"])
        message = event.get("message", {})
        if not isinstance(message, dict):
            errors.append("Malformed stream message")
            continue
        blocks = message.get("content", [])
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uses[block.get("id")] = block
                tools.append({"name": block.get("name"), "input": block.get("input", {})})
                if block.get("name") not in permitted:
                    if phase == "investigate" and format_errors and block.get("name") in PACKET_SCHEMA["properties"]:
                        field_attempts[block.get("id")] = block.get("name")
                    else:
                        errors.append(f"Tool outside phase scope: {block.get('name')}")
            elif block.get("type") == "tool_result":
                use = uses.get(block.get("tool_use_id"), {})
                name, args = use.get("name"), use.get("input", {})
                if block.get("is_error"):
                    message = content_text(block.get("content"))[:700]
                    if name == "StructuredOutput" and message.startswith("Output does not match required schema:"):
                        format_errors.append(message)
                    elif block.get("tool_use_id") in field_attempts and message == f"<tool_use_error>Error: No such tool available: {name}</tool_use_error>":
                        # The SDK rejected a misaddressed output field before executing any tool.
                        # This is output formatting; a final valid packet is still mandatory.
                        field_attempts.pop(block["tool_use_id"])
                        format_errors.append(message)
                    else:
                        errors.append(f"{name}: {message}")
                    continue
                if block.get("tool_use_id") in field_attempts:
                    errors.append(f"Unexpected execution of output field: {name}")
                    field_attempts.pop(block["tool_use_id"])
                if phase != "investigate":
                    continue
                if name == "Read":
                    value = args.get("file_path", "")
                    if not isinstance(value, str) or not value:
                        continue
                    path = (workspace / value).resolve()
                    raw_path = workspace / value
                    symlink = any(p.is_symlink() for p in [raw_path, *raw_path.parents] if p.is_relative_to(workspace))
                    if symlink or not path.is_relative_to(workspace) or not path.is_file():
                        errors.append("Native read escaped workspace")
                        continue
                    relative = path.relative_to(workspace).as_posix()
                    if not (relative.startswith(("app/", "tests/"))) or not (path.suffix == ".py" or relative == "app/devices.json"):
                        errors.append("Native read outside permitted evidence")
                        continue
                    content = path.read_text()
                    spans = read_spans(content_text(block.get("content")), content)
                    if spans:
                        metadata = {}
                        if relative == "app/devices.json":
                            devices = {}
                            for identifier in json.loads(content):
                                canonical = get_device(identifier, workspace / relative)
                                if canonical.get("status") == "ok" and any(low <= canonical["line_start"] and high >= canonical["line_end"] for low, high in spans):
                                    devices[identifier] = {"controller_id": identifier, **canonical["record"]}
                            metadata = {"devices": devices}
                        capture(evidence, relative, content, spans, "registry" if relative == "app/devices.json" else "code", metadata)
                    else:
                        errors.append("Successful native Read did not match source content")
                elif name in MCP_TOOLS:
                    for data in json_payloads(block.get("content")):
                        if data.get("status") != "ok":
                            if data.get("status") in {"invalid_request", "unavailable"}:
                                errors.append(f"{name}: {data['status']}")
                            continue
                        if name.endswith("get_device"):
                            content = (workspace / "app/devices.json").read_text()
                            canonical = get_device(args.get("controller_id"), workspace / "app/devices.json")
                            fields = ("controller_id", "source", "record", "line_start", "line_end", "registry_sha256", "content")
                            if canonical.get("status") != "ok" or any(data.get(key) != canonical.get(key) for key in fields):
                                errors.append("Registry tool result did not match workspace")
                                continue
                            normalized = {"controller_id": canonical["controller_id"], **canonical["record"]}
                            capture(evidence, "app/devices.json", content,
                                [[canonical["line_start"], canonical["line_end"]]], "registry", {"device": normalized, "devices": {canonical["controller_id"]: normalized}})
                        elif name.endswith("search_knowledge"):
                            for document in data.get("results", []):
                                if not isinstance(document, dict):
                                    errors.append("Search returned an invalid record")
                                    continue
                                canonical = get_document(document.get("document_id", ""))
                                if canonical.get("status") != "ok" or document.get("source") != canonical["source"]:
                                    errors.append("Search source is outside manifest")
                                    continue
                                spans = []
                                for excerpt in document.get("excerpts", []):
                                    if not isinstance(excerpt, dict):
                                        errors.append("Search returned an invalid excerpt")
                                        continue
                                    low, high = excerpt.get("line_start", 0), excerpt.get("line_end", 0)
                                    source_lines = canonical["content"].splitlines()
                                    if not isinstance(low, int) or isinstance(low, bool) or not isinstance(high, int) or isinstance(high, bool) or not 1 <= low <= high <= len(source_lines):
                                        errors.append("Search excerpt has invalid bounds")
                                        continue
                                    text = "\n".join(source_lines[low - 1:high])
                                    if excerpt.get("text") != text:
                                        errors.append("Search excerpt did not match manifest")
                                        continue
                                    spans.append([low, high])
                                if spans:
                                    capture(evidence, canonical["source"], canonical["content"], spans, "knowledge", canonical.get("metadata"))
                        else:
                            identifier = data.get("document_id") or data.get("ticket_id")
                            canonical = get_document(identifier)
                            requested = args.get("ticket_id") if name.endswith("get_ticket") else args.get("document_id")
                            if identifier != requested or canonical.get("status") != "ok" or data.get("source") != canonical.get("source") or data.get("content") != canonical.get("content"):
                                errors.append("Document result did not match manifest")
                                continue
                            capture(evidence, canonical["source"], canonical["content"], [[1, len(canonical["content"].splitlines())]], "knowledge", canonical.get("metadata"))
        if event.get("type") == "result":
            result = event
    if result:
        for item in result.get("permission_denials", []) or []:
            errors.append(f"Permission denial: {item.get('tool_name', 'unknown') if isinstance(item, dict) else 'unknown'}")
        if not models:
            models.extend(sorted((result.get("modelUsage") or {}).keys()))
    errors.extend(f"Unresolved output field tool attempt: {name}" for name in field_attempts.values())
    return {"result": result, "tools": tools, "errors": errors, "format_errors": format_errors,
            "model": ", ".join(dict.fromkeys(models)) or None}
