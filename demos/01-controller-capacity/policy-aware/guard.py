"""Tool boundary for the local synthetic demo; this is not an OS sandbox."""
from __future__ import annotations

import json
from pathlib import Path
import sys

MCP_TOOLS = {f"mcp__engineering-knowledge__{name}" for name in
             ("get_ticket", "get_document", "search_knowledge", "get_device")}


def scoped(path: Path, workspace: Path) -> bool:
    if not path.resolve().is_relative_to(workspace.resolve()):
        return False
    return not any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(workspace))


def decide(event: dict, workspace: Path, phase: str, context: str) -> dict:
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Outside this demo phase's permitted files and tools."}
    args, name = event.get("tool_input", {}), event.get("tool_name", "")
    if not isinstance(args, dict):
        return {"hookSpecificOutput": decision}
    if name == "StructuredOutput" or (context == "tools" and name in MCP_TOOLS):
        decision["permissionDecision"] = "allow"
        return {"hookSpecificOutput": decision}
    if name not in {"Read", "Glob", "Grep", "Write", "Edit"}:
        return {"hookSpecificOutput": decision}
    key = "file_path" if name in {"Read", "Write", "Edit"} else "path"
    search_pattern = args.get("pattern" if name == "Glob" else "glob", "")
    default_root = "tests" if isinstance(search_pattern, str) and search_pattern.startswith("tests/") else "app"
    value = args.get(key) or (default_root if name in {"Glob", "Grep"} else "")
    if not isinstance(value, str) or not value:
        return {"hookSpecificOutput": decision}
    path = Path(value)
    path = path if path.is_absolute() else workspace / path
    pattern_key = "pattern" if name == "Glob" else "glob"
    pattern = args.get(pattern_key, "") if name in {"Glob", "Grep"} else ""
    if not isinstance(pattern, str) or Path(pattern).is_absolute() or any(x in pattern for x in ("..", "{", "}")):
        return {"hookSpecificOutput": decision}
    if name in {"Glob", "Grep"} and path.resolve() == workspace.resolve():
        directory = "tests" if pattern.startswith("tests/") else "app"
        path = workspace / directory
        if pattern.startswith(directory + "/"):
            args = {**args, pattern_key: pattern[len(directory) + 1:]}
    elif name == "Glob" and pattern.startswith(path.name + "/"):
        args = {**args, pattern_key: pattern[len(path.name) + 1:]}
    if not scoped(path, workspace):
        return {"hookSpecificOutput": decision}
    if name in {"Glob", "Grep"} and path.is_dir() and any(child.is_symlink() for child in path.rglob("*")):
        return {"hookSpecificOutput": decision}
    relative = path.resolve().relative_to(workspace.resolve())
    if not relative.parts or relative.parts[0] not in {"app", "tests"}:
        return {"hookSpecificOutput": decision}
    if name == "Read" and (not path.is_file() or not (path.suffix == ".py" or relative.as_posix() == "app/devices.json")):
        return {"hookSpecificOutput": decision}
    if name in {"Edit", "Write"}:
        if phase == "reproduce":
            allowed = relative.as_posix() == "tests/test_reported_case.py"
        elif phase == "fix":
            allowed = (relative.parts[0] == "app" and len(relative.parts) == 2 and path.suffix == ".py") or (
                relative.parts[0] == "tests" and len(relative.parts) == 2 and path.name.startswith("test_policy_") and path.suffix == ".py")
        else:
            allowed = False
        if not allowed:
            return {"hookSpecificOutput": decision}
    decision.update(permissionDecision="allow", permissionDecisionReason="Permitted synthetic demo phase.")
    decision["updatedInput"] = {**args, key: str(path.resolve())}
    return {"hookSpecificOutput": decision}


if __name__ == "__main__":
    try:
        print(json.dumps(decide(json.load(sys.stdin), Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3])))
    except Exception:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                "permissionDecisionReason": "Cannot verify demo scope."}}))
