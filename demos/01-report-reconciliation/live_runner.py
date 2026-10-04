"""Fresh Claude Code sessions, observable tool events, and retained run records.

Raw modes use an ordinary prompt and native tools. They never receive the
calculator, structured policies, oracle, prior results, or an output schema.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid

import agent
from catalog import ROOT, digest
from codex_compare import inputs

MODES = {
    "raw_repo": "Raw · repo only",
    "raw_docs": "Raw · repo + business docs / Jira",
    "workflow": "Guided · evidence tools + calculator",
}
RAW_PROMPT = ("Investigate the customer issue in issue.json. Explain what is happening "
              "and recommend the next step. Do not modify files. Use only the files "
              "in this working directory.")


def raw_command(model, budget):
    # The default Claude Code system prompt is preserved. Restricted mode confines
    # file tools. Native Bash supports ordinary inspection and test commands.
    # This is not an OS read sandbox: Python can access files outside the directory.
    command = [shutil.which("claude") or "claude", "--print", "--output-format", "stream-json",
               "--verbose", "--restricted", "--safe-mode", "--tools", "Read,Glob,Grep,Bash",
               "--allowedTools", "Read,Glob,Grep,Bash",
               "--permission-mode", "dontAsk", "--setting-sources", "",
               "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
               "--max-budget-usd", str(budget)]
    if model:
        command += ["--model", model]
    return command


def stop_process(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
        except ProcessLookupError:
            pass


class Run:
    def __init__(self, case_id, mode, prompt=RAW_PROMPT, *, timeout=240, budget=1.0):
        self.id = uuid.uuid4().hex
        self.case_id, self.mode, self.prompt = case_id, mode, prompt
        self.timeout, self.budget = timeout, budget
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.events = []
        self.status = "running"
        self.result = None
        self.started = time.monotonic()
        self.recorded_at = datetime.now(timezone.utc).isoformat()

    def emit(self, kind, **data):
        with self.lock:
            self.events.append({"index": len(self.events), "kind": kind,
                                "seconds": round(time.monotonic() - self.started, 2), **data})

    def snapshot(self, after=0):
        with self.lock:
            return {"id": self.id, "case_id": self.case_id, "mode": self.mode,
                    "status": self.status, "elapsed_seconds": round(time.monotonic() - self.started, 2)
                    if self.status == "running" else self.result["elapsed_seconds"],
                    "events": self.events[after:], "cursor": len(self.events), "result": self.result}

    def consume(self, event):
        # Expose tool activity and user-facing answer text, never thinking blocks.
        if event.get("type") == "system" and event.get("subtype") == "init":
            self.emit("session", model=event.get("model"), tools=event.get("tools", []))
        message = event.get("message") or {}
        blocks = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(blocks, list):
            return
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                if block.get("name") != "StructuredOutput":
                    self.emit("tool_call", tool_id=block.get("id"), name=block.get("name"),
                              input=block.get("input", {}))
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                self.emit("tool_result", tool_id=block.get("tool_use_id"),
                          error=bool(block.get("is_error")), content=block.get("content"))
            elif event.get("type") == "assistant" and block.get("type") == "text":
                self.emit("message", text=block.get("text", ""))

    def execute(self):
        destination = ROOT / "artifacts" / "live" / self.id
        destination.mkdir(parents=True)
        result = {"id": self.id, "case_id": self.case_id, "mode": self.mode,
                  "recorded_at": self.recorded_at, "status": "failed", "errors": [],
                  "answer": "", "packet": None, "models": [], "cost_usd": None,
                  "artifact_directory": str(destination), "agent_run": False,
                  "budget_usd": self.budget, "timeout_seconds": self.timeout}
        process = None
        trace = []
        try:
            self.emit("status", text="Checking Claude Code authentication…")
            client = agent.preflight()
            result["client"] = client
            if not client.get("authenticated"):
                result["status"] = "blocked"
                raise RuntimeError("Claude Code is not signed in. Run claude auth login in your terminal, then start a new run.")
            with tempfile.TemporaryDirectory(prefix="datahoney-live-") as temporary:
                files = {} if self.mode == "workflow" else inputs(self.mode == "raw_docs", self.case_id)
                for relative, content in files.items():
                    path = Path(temporary) / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
                text = agent.prompt(self.case_id, "workflow") if self.mode == "workflow" else self.prompt
                command = agent.client_command("workflow", client.get("configured_model"), self.budget) if self.mode == "workflow" else raw_command(client.get("configured_model"), self.budget)
                result["prompt"] = text
                result["input_hashes"] = {name: digest(content) for name, content in files.items()}
                result["working_directory"] = temporary
                result["runner_sha256"] = digest(Path(__file__).read_text())
                (destination / "inputs.json").write_text(json.dumps(files, indent=2) + "\n")
                (destination / "prompt.txt").write_text(text)
                self.emit("inputs", files=list(files), prompt=text, mode=self.mode)
                if self.cancel.is_set():
                    result["status"] = "cancelled"
                    raise RuntimeError("Stopped before launching the model.")
                with (destination / "stderr.txt").open("w") as stderr:
                    process = subprocess.Popen(command, cwd=temporary, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=stderr, text=True, start_new_session=True,
                        env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
                    result["agent_run"] = True
                    process.stdin.write(text)
                    process.stdin.close()
                    self.emit("status", text="Fresh model session started. Waiting for its first tool call or response…")
                    lines = queue.Queue()

                    def read_stdout():
                        try:
                            for line in process.stdout:
                                lines.put(line)
                        finally:
                            lines.put(None)

                    reader = threading.Thread(target=read_stdout, daemon=True)
                    reader.start()
                    deadline = time.monotonic() + self.timeout
                    ended = False
                    with (destination / "trace.jsonl").open("w") as trace_file:
                        while not ended:
                            if self.cancel.is_set() or time.monotonic() >= deadline:
                                result["status"] = "cancelled" if self.cancel.is_set() else "failed"
                                result["errors"].append("Stopped by user." if self.cancel.is_set() else "Timed out. This attempt was saved; it was not retried.")
                                stop_process(process)
                                break
                            try:
                                line = lines.get(timeout=0.15)
                            except queue.Empty:
                                continue
                            if line is None:
                                ended = True
                                continue
                            trace.append(line)
                            trace_file.write(line)
                            trace_file.flush()
                            try:
                                event = json.loads(line)
                                if isinstance(event, dict):
                                    self.consume(event)
                            except ValueError:
                                pass
                    process.wait(timeout=5)
                    reader.join(timeout=2)
                result["exit_code"] = process.returncode
                events = []
                for line in trace:
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            events.append(value)
                    except ValueError:
                        pass
                finals = [event for event in events if event.get("type") == "result"]
                final = finals[-1] if finals else {}
                result["answer"] = final.get("result", "")
                result["packet"] = final.get("structured_output")
                result["cost_usd"] = final.get("total_cost_usd")
                result["usage"] = final.get("usage")
                result["models"] = sorted({event["model"] for event in events if event.get("type") == "system" and event.get("model")})
                result["permission_denials"] = final.get("permission_denials", [])
                if not final or final.get("is_error") or process.returncode != 0:
                    result["errors"].append("Claude did not return a successful final response" + (": " + str(final.get("subtype")) if final else "."))
                if result["permission_denials"]:
                    result["errors"].append("A requested tool was denied. Inspect the trace; this run is incomplete.")
                if not result["answer"] and not result["packet"]:
                    result["errors"].append("The client returned no final answer.")
                changed = [name for name, content in files.items()
                           if not (Path(temporary) / name).is_file()
                           or (Path(temporary) / name).read_text() != content]
                result["changed_input_files"] = changed
                if changed:
                    result["errors"].append("The model changed task inputs despite the read-only request.")
                if self.mode == "workflow":
                    parsed = agent.parse_trace("".join(trace), "workflow")
                    result["errors"] += parsed["errors"]
                    result["observed_sources"] = parsed["sources"]
                    # Evaluation occurs only after the guided run; never for raw modes.
                    from evaluation import PACKET_SCHEMA, score
                    from jsonschema import validate, ValidationError
                    try:
                        validate(result["packet"], PACKET_SCHEMA)
                    except ValidationError:
                        result["errors"].append("Guided answer did not match the requested schema.")
                    result["acceptance"] = score(result["packet"], self.case_id, parsed["sources"])
                if not result["errors"]:
                    result["status"] = "completed"
        except Exception as error:
            result["errors"].append(str(error))
        finally:
            if process:
                stop_process(process)
            result["elapsed_seconds"] = round(time.monotonic() - self.started, 3)
            (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            self.emit("finished", status=result["status"])
            (destination / "events.json").write_text(json.dumps(self.events, indent=2) + "\n")
            with self.lock:
                self.result, self.status = result, result["status"]
