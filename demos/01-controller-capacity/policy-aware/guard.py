"""Tool boundary for the local synthetic demo; this is not an OS sandbox."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import sys

MCP_TOOLS = {f"mcp__engineering-knowledge__{name}" for name in
             ("get_ticket", "get_document", "search_knowledge", "get_device")}
# The repo-only control runs in an isolated copy with a developer's everyday read/test commands.
SHELL_COMMANDS = {"ls", "cat", "head", "tail", "wc", "find", "grep", "rg", "tree", "pwd", "echo", "cd",
                  "git", "python", "python3", "pytest", "uv"}
GIT_READS = {"status", "diff", "log", "show", "ls-files", "grep", "blame"}


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
    if name == "Bash" and phase == "baseline":
        return {"hookSpecificOutput": shell_command(args, decision, workspace)}
    if phase == "baseline" and name in {"Read", "Glob", "Grep"}:
        return {"hookSpecificOutput": developer_read(name, args, decision, workspace)}
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
        elif phase == "baseline":
            allowed = relative.parts[0] in {"app", "tests"} and path.suffix == ".py"
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


def developer_read(name: str, args: dict, decision: dict, workspace: Path) -> dict:
    key = "file_path" if name == "Read" else "path"
    value = args.get(key) or "."
    pattern = args.get("pattern", "") if name == "Glob" else args.get("glob", "")
    if not isinstance(value, str) or not isinstance(pattern, str) or Path(pattern).is_absolute() or ".." in pattern:
        return decision
    path = Path(value) if Path(value).is_absolute() else workspace / value
    if not scoped(path, workspace):
        return decision
    return {**decision, "permissionDecision": "allow", "permissionDecisionReason": "Isolated repository read.",
            "updatedInput": {**args, key: str(path.resolve())}}


def unquoted_newlines_as_separators(command: str) -> str:
    """Newlines outside quotes separate shell commands, exactly like `;`."""
    quote, output = None, []
    for char in command:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "\n":
            char = " ; "
        output.append(char)
    return "".join(output)


def shell_command(args: dict, decision: dict, workspace: Path) -> dict:
    """Allow read/test commands whose paths stay inside the isolated copy; writes go through Edit/Write."""
    command = args.get("command")
    if not isinstance(command, str):
        return decision
    # Heredocs (`python - <<'EOF'`, `cat >> tests/x.py <<'EOF'`) are checked with their body as an argument.
    command = re.sub(r"<<-?\s*(['\"]?)(\w+)\1\n(.*?)\n\2(?=\n|$)",
                     lambda m: shlex.quote(m[3]), command, flags=re.S)
    if any(x in command for x in ("$", "`", "~")):
        return decision
    command = unquoted_newlines_as_separators(command)
    command = command.replace("2>&1", "").replace("2>/dev/null", "")
    if re.search(r"<|-exec|-delete", re.sub(r"'[^']*'|\"[^\"]*\"", "", command)):
        return decision
    root = os.path.normpath(workspace.resolve())
    roots = {root, root.removeprefix("/private")}
    inside = lambda path: any(path == r or path.startswith(r + "/") for r in roots)
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return decision
    segments, current = [], []
    for token in tokens:
        if token in {"&&", "||", ";", "|"}:
            segments.append(current)
            current = []
        elif set(token) <= set(";&|"):
            return decision
        else:
            current.append(token)
    segments.append(current)
    # The client's shell keeps its directory between calls, so a traversal must stay inside the copy
    # from at least one directory within it; the copy itself sits in a temp directory away from the demo.
    bases = [root] + sorted(str(d) for d in workspace.resolve().rglob("*") if d.is_dir() and not {".git", "__pycache__"} & set(d.parts))
    for words in segments:
        if not words or words[0] not in SHELL_COMMANDS or words == ["cd"]:
            return decision
        if words[0] == "git" and (len(words) < 2 or words[1] not in GIT_READS):
            return decision
        if words[0] == "uv" and words[1:3] not in (["run", "python"], ["run", "python3"], ["run", "pytest"]):
            return decision
        if any(w.startswith("-p") for w in words[1:]) and "pytest" in words:
            return decision
        for word in words[1:]:
            # Absolute paths and parent traversals, including ones inside inline Python, must stay in the copy.
            absolute = re.findall(r"(?<![\w.])/[^\s'\":,)]*", word)
            relative = re.findall(r"(?<![\w/])(?:[\w.-]+/)*\.\.(?:/[\w.-]*)*", word)
            if any(x != "/dev/null" and not inside(os.path.normpath(x)) for x in absolute):
                return decision
            if any(not any(inside(os.path.normpath(os.path.join(base, x))) for base in bases) for x in relative):
                return decision
        if words[0] == "cd" and len(words) != 2:
            return decision
    return {**decision, "permissionDecision": "allow", "permissionDecisionReason": "Developer read/test command."}

if __name__ == "__main__":
    try:
        print(json.dumps(decide(json.load(sys.stdin), Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3])))
    except Exception:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                "permissionDecisionReason": "Cannot verify demo scope."}}))
