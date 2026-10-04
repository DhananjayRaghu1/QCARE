"""Validate evidence references and render saved developer context packets.

These checks establish where an excerpt came from. They do not establish that
the excerpt supports the surrounding claim; that still needs human review.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from uuid import uuid4


def _text(limit: int = 2000) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": limit}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object", "properties": properties,
        "required": list(properties), "additionalProperties": False,
    }


_CITATION_IDS = {
    "type": "array", "maxItems": 12, "uniqueItems": True,
    "items": {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"},
}
_FACT = _object({"text": _text(), "citations": _CITATION_IDS})
_LINE = {"type": "integer", "minimum": 1, "maximum": 100000}
PACKET_SCHEMA = _object({
    "ticket_id": {"type": "string", "pattern": r"^AG-[0-9]+$", "maxLength": 32},
    "summary": _text(),
    "summary_citations": {**_CITATION_IDS, "minItems": 1},
    "likely_subsystem": _FACT,
    "starting_files": {
        "type": "array", "minItems": 1, "maxItems": 3,
        "items": _object({
            "path": _text(500), "line_start": _LINE, "line_end": _LINE,
            "reason": _text(1500), "citations": _CITATION_IDS,
        }),
    },
    "execution_path": _FACT,
    "history": {"type": "array", "maxItems": 6, "items": _FACT},
    "owner": _FACT,
    "first_investigation": _FACT,
    "unknowns": {"type": "array", "maxItems": 10, "items": _text(1000)},
    "citations": {
        "type": "array", "minItems": 1, "maxItems": 50,
        "items": _object({
            "id": {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"},
            "kind": {"type": "string", "enum": ["code", "knowledge"]},
            "source": _text(500), "line_start": _LINE, "line_end": _LINE,
            "excerpt": _text(12000),
        }),
    },
})


def _schema_errors(value: Any, schema: Mapping[str, Any], where: str, errors: list[str]) -> None:
    """Check the small JSON Schema subset above without another dependency."""
    expected = schema["type"]
    valid_type = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
    }[expected]
    if not valid_type:
        errors.append(f"{where}: expected {expected}")
        return
    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}.{key}: required field is missing")
        for key, item in value.items():
            if not isinstance(key, str) or key not in schema["properties"]:
                errors.append(f"{where}: unexpected field {key!r}")
            else:
                _schema_errors(item, schema["properties"][key], f"{where}.{key}", errors)
    elif expected == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{where}: item count is outside the allowed range")
        if schema.get("uniqueItems") and any(item in value[:index] for index, item in enumerate(value)):
            errors.append(f"{where}: duplicate items are not allowed")
        for index, item in enumerate(value):
            _schema_errors(item, schema["items"], f"{where}[{index}]", errors)
    elif expected == "string":
        if not value.strip():
            errors.append(f"{where}: text must not be blank")
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{where}: text length is outside the allowed range")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{where}: invalid format")
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{where}: unsupported value")
    elif expected == "integer":
        if not schema.get("minimum", value) <= value <= schema.get("maximum", value):
            errors.append(f"{where}: number is outside the allowed range")


def _normal(text: str) -> str:
    return " ".join(text.split())


def _relative_path(source: str) -> bool:
    path = PurePosixPath(source)
    return (
        bool(source) and not path.is_absolute() and "\\" not in source
        and all(part not in {".", ".."} for part in source.split("/"))
        and str(path) == source
    )


def _code_source(source: str, evidence: Mapping[str, Any], errors: list[str]) -> str | None:
    files = evidence.get("code_files", {})
    if not isinstance(files, dict) or source not in files or not isinstance(files[source], str):
        errors.append(f"{source}: code source was not captured from a successful read")
        return None
    repo_root = evidence.get("repo_root")
    if not isinstance(repo_root, str) or not Path(repo_root).is_absolute():
        errors.append("evidence.repo_root: an absolute repository path is required")
        return None
    root = Path(repo_root).resolve()
    target = root / source
    try:
        target.resolve().relative_to(root)
        walking = root
        for component in PurePosixPath(source).parts:
            walking = walking / component
            if walking.is_symlink():
                raise ValueError("symlink")
        if not target.is_file():
            raise ValueError("missing file")
        current = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        errors.append(f"{source}: code file is missing, unreadable, or outside the repository")
        return None
    if current != files[source]:
        errors.append(f"{source}: current code differs from the captured evidence")
        return None
    return current


def _covered_by_reads(start: int, end: int, spans: Any) -> bool:
    if not isinstance(spans, list):
        return False
    clean = []
    for span in spans:
        if (
            not isinstance(span, (list, tuple)) or len(span) != 2
            or any(not isinstance(n, int) or isinstance(n, bool) for n in span)
            or span[0] < 1 or span[1] < span[0]
        ):
            return False
        clean.append(span)
    cursor = start
    for low, high in sorted(clean):
        if low > cursor:
            return False
        if high >= cursor:
            cursor = high + 1
        if cursor > end:
            return True
    return False


def _unknown(text: str) -> bool:
    return bool(re.match(r"^(unknown\b|not documented\b|not established\b|not available\b)", text.strip(), re.I))


def _narrative_text(packet: Mapping[str, Any]) -> str:
    parts = [packet.get("summary", "")]
    for name in ("likely_subsystem", "execution_path", "owner", "first_investigation"):
        fact = packet.get(name, {})
        if isinstance(fact, dict):
            parts.append(fact.get("text", ""))
    for item in packet.get("starting_files", []):
        if isinstance(item, dict):
            parts.append(item.get("reason", ""))
    for item in packet.get("history", []):
        if isinstance(item, dict):
            parts.append(item.get("text", ""))
    parts.extend(packet.get("unknowns", []))
    return " ".join(part for part in parts if isinstance(part, str))


def validate_packet(packet: Any, evidence: Any) -> dict[str, Any]:
    """Validate schema, captured sources, spans, excerpts and reference links."""
    errors: list[str] = []
    warnings: list[str] = []
    _schema_errors(packet, PACKET_SCHEMA, "packet", errors)
    try:
        if len(json.dumps(packet, ensure_ascii=False)) > 100000:
            errors.append("packet: total text exceeds the 100,000-character display limit")
    except (TypeError, ValueError):
        errors.append("packet: content is not JSON serializable")
    if not isinstance(evidence, dict):
        errors.append("evidence: expected object")
    word_count = 0
    if not errors:
        word_count = len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", _narrative_text(packet)))
        if word_count < 250:
            warnings.append(f"Packet has {word_count} narrative words; target is 250–300.")
        elif word_count > 300:
            warnings.append(f"Packet has {word_count} narrative words; exceeds the 300-word target. No text was truncated.")
        references: dict[str, Any] = {}
        code_cache: dict[str, str | None] = {}
        for citation in packet["citations"]:
            identifier = citation["id"]
            if identifier in references:
                errors.append(f"citation {identifier}: duplicate identifier")
                continue
            references[identifier] = citation
            source = citation["source"]
            if not _relative_path(source):
                errors.append(f"citation {identifier}: source must be a normalized repository-relative path")
                continue
            if citation["kind"] == "code":
                if source not in code_cache:
                    code_cache[source] = _code_source(source, evidence, errors)
                content = code_cache[source]
            else:
                documents = evidence.get("documents", {})
                content = documents.get(source) if isinstance(documents, dict) else None
                if not isinstance(content, str):
                    errors.append(f"citation {identifier}: knowledge source was not successfully retrieved")
                    content = None
            if content is None:
                continue
            start, end = citation["line_start"], citation["line_end"]
            lines = content.splitlines()
            if start > end or end > len(lines):
                errors.append(f"citation {identifier}: line span is outside the captured source")
                continue
            excerpt = _normal(citation["excerpt"])
            if excerpt not in _normal("\n".join(lines[start - 1:end])):
                errors.append(f"citation {identifier}: excerpt does not match its source lines")
            if citation["kind"] == "code" and "code_spans" in evidence:
                captured = evidence["code_spans"]
                spans = captured.get(source) if isinstance(captured, dict) else None
                if not _covered_by_reads(start, end, spans):
                    errors.append(f"citation {identifier}: line span was not covered by successful code reads")
        used: set[str] = set()

        def check_fact(fact: Mapping[str, Any], name: str, *, allow_unknown: bool = True) -> None:
            ids = fact["citations"]
            if not ids and not (allow_unknown and _unknown(fact.get("text", ""))):
                errors.append(f"{name}: factual text requires at least one citation")
            for identifier in ids:
                used.add(identifier)
                if identifier not in references:
                    errors.append(f"{name}: unknown citation {identifier}")

        check_fact({"text": packet["summary"], "citations": packet["summary_citations"]}, "summary", allow_unknown=False)
        for name in ("likely_subsystem", "execution_path", "owner", "first_investigation"):
            check_fact(packet[name], name)
        for index, fact in enumerate(packet["history"]):
            check_fact(fact, f"history[{index}]")
        for index, item in enumerate(packet["starting_files"]):
            name = f"starting_files[{index}]"
            check_fact(item, name, allow_unknown=False)
            source = item["path"]
            if not _relative_path(source):
                errors.append(f"{name}: file path must be normalized and repository-relative")
                continue
            if source not in code_cache:
                code_cache[source] = _code_source(source, evidence, errors)
            content = code_cache[source]
            start, end = item["line_start"], item["line_end"]
            if start > end or (content is not None and end > len(content.splitlines())):
                errors.append(f"{name}: line span is outside its file")
            matches = [references[identifier] for identifier in item["citations"] if identifier in references]
            if not any(
                cite["kind"] == "code" and cite["source"] == source
                and cite["line_start"] <= start <= end <= cite["line_end"]
                for cite in matches
            ):
                errors.append(f"{name}: needs a code citation covering its starting lines")
        unused = set(references) - used
        if unused:
            warnings.append("Unreferenced citations: " + ", ".join(sorted(unused)))
    return {
        "status": "invalid" if errors else "valid", "errors": errors,
        "warnings": warnings, "word_count": word_count,
    }


def _references(ids: list[str]) -> str:
    return " " + " ".join(f"[{identifier}]" for identifier in ids) if ids else ""


def render_markdown(packet: Mapping[str, Any]) -> str:
    """Render the packet without dropping long text or citation excerpts."""
    lines = [f"# {packet['ticket_id']} — Developer context", "", packet["summary"] + _references(packet["summary_citations"]), ""]
    fact = packet["likely_subsystem"]
    lines.extend(["## Likely subsystem", "", fact["text"] + _references(fact["citations"]), ""])
    lines.extend(["## Start here", ""])
    for item in packet["starting_files"]:
        location = f"{item['path']}:{item['line_start']}–{item['line_end']}"
        lines.append(f"- `{location}` — {item['reason']}" + _references(item["citations"]))
    lines.append("")
    fact = packet["execution_path"]
    lines.extend(["## Execution path", "", fact["text"] + _references(fact["citations"]), ""])
    lines.extend(["## Relevant history", ""])
    if packet["history"]:
        for fact in packet["history"]:
            lines.append("- " + fact["text"] + _references(fact["citations"]))
    else:
        lines.append("No supported history was included in this packet.")
    lines.append("")
    for title, name in (("Owner", "owner"), ("First investigation", "first_investigation")):
        fact = packet[name]
        lines.extend([f"## {title}", "", fact["text"] + _references(fact["citations"]), ""])
    lines.extend(["## Unknowns", ""])
    lines.extend("- " + item for item in packet["unknowns"])
    if not packet["unknowns"]:
        lines.append("No remaining unknowns were listed; review whether that is justified.")
    lines.extend(["", "## Sources", "", "Reference checks verify excerpts and locations; claim support still requires review.", ""])
    for cite in packet["citations"]:
        location = f"{cite['source']}:{cite['line_start']}–{cite['line_end']}"
        lines.extend([f"### [{cite['id']}] {location}", ""])
        lines.extend("    " + line for line in cite["excerpt"].splitlines())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_run(
    artifact_root: str | Path, packet: Mapping[str, Any] | None,
    evidence: Mapping[str, Any], metadata: Mapping[str, Any],
    trace: str | list[Any],
) -> Path:
    """Persist a unique run, including failed outputs and fresh validation."""
    validation = validate_packet(packet, evidence)
    saved_metadata = dict(metadata)
    saved_metadata["validation"] = validation
    saved_metadata.setdefault("claim_review", "pending")
    saved_metadata.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    saved_metadata.setdefault("ticket_id", packet.get("ticket_id") if isinstance(packet, Mapping) else None)
    saved_metadata.setdefault("status", "validated" if validation["status"] == "valid" else "failed")
    if validation["status"] != "valid" and saved_metadata["status"] not in {"failed", "partial", "timeout", "unavailable"}:
        saved_metadata["status"] = "partial" if packet else "failed"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    run_directory = Path(artifact_root) / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    for filename, value in (("metadata.json", saved_metadata), ("packet.json", packet), ("evidence.json", evidence)):
        (run_directory / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if validation["status"] == "valid":
        markdown = render_markdown(packet)
    else:
        markdown = "# Context packet unavailable\n\n" + "\n".join("- " + error for error in validation["errors"]) + "\n"
    (run_directory / "packet.md").write_text(markdown, encoding="utf-8")
    if isinstance(trace, str):
        trace_text = trace
    else:
        trace_text = "\n".join(json.dumps(event, ensure_ascii=False) for event in trace)
    (run_directory / "trace.jsonl").write_text(trace_text.rstrip() + "\n" if trace_text else "", encoding="utf-8")
    return run_directory
