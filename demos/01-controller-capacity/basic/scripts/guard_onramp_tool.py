"""Claude PreToolUse guard: permit only synthetic app reads and two MCP tools.

This is a tool-level boundary, not an operating-system sandbox. The runner also
removes shell/edit tools and checks that source hashes remain unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

KNOWLEDGE_TOOLS = {
    "mcp__engineering-knowledge__get_engineering_ticket",
    "mcp__engineering-knowledge__search_engineering_knowledge",
}


def decide(event: dict, workspace: Path, augmented: bool) -> dict:
    name = event.get("tool_name", "")
    args = event.get("tool_input", {})
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Only synthetic app reads and configured knowledge tools are permitted."}
    if not isinstance(args, dict):
        return {"hookSpecificOutput": decision}
    if name == "StructuredOutput" or (augmented and name in KNOWLEDGE_TOOLS):
        decision["permissionDecision"] = "allow"
        return {"hookSpecificOutput": decision}
    if name not in {"Read", "Glob", "Grep"}:
        return {"hookSpecificOutput": decision}
    key = "file_path" if name == "Read" else "path"
    value = args.get(key) or ("app" if name != "Read" else "")
    if not isinstance(value, str) or not value:
        return {"hookSpecificOutput": decision}
    raw = Path(value)
    target = raw if raw.is_absolute() else workspace / raw
    app = workspace / "app"
    if name != "Read" and target.resolve() == workspace.resolve():
        target = app
    if target.is_symlink() or not target.resolve().is_relative_to(app.resolve()):
        return {"hookSpecificOutput": decision}
    if any(parent.is_symlink() for parent in target.parents if parent.is_relative_to(workspace)):
        return {"hookSpecificOutput": decision}
    if name == "Read" and (not target.is_file() or target.suffix != ".py"):
        return {"hookSpecificOutput": decision}
    # A Glob pattern can itself contain an absolute/parent path, independently
    # of its path argument. Grep's glob filter is limited in the same way.
    pattern = args.get("pattern" if name == "Glob" else "glob", "")
    if isinstance(pattern, str) and (Path(pattern).is_absolute() or ".." in pattern or "{" in pattern or "}" in pattern):
        return {"hookSpecificOutput": decision}
    if name == "Glob" and isinstance(pattern, str) and pattern.startswith("app/"):
        args = {**args, "pattern": pattern[4:]}
    decision.update(permissionDecision="allow", permissionDecisionReason="Read-only synthetic demo evidence.")
    decision["updatedInput"] = {**args, key: str(target.resolve())}
    return {"hookSpecificOutput": decision}


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
        print(json.dumps(decide(event, Path(sys.argv[1]).resolve(), sys.argv[2] == "augmented")))
    except Exception:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Unable to verify demo tool scope."}}))
