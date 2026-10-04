"""Portable decision packets backed by captured, successfully read evidence.

The model selects source IDs and line spans. This module supplies the excerpts;
it never asks the model to reproduce them and never reads the current checkout.
Mechanical verification proves provenance, not that a citation supports a claim.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import json
from pathlib import PurePosixPath
import re
from typing import Any, Mapping


def _text(limit: int = 2000) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": limit}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object", "properties": properties, "required": list(properties),
        "additionalProperties": False,
    }


_ID = {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"}
_REFS = {"type": "array", "maxItems": 12, "uniqueItems": True, "items": _ID}
_LINE = {"type": "integer", "minimum": 1, "maximum": 100000}
_FACT = _object({"text": _text(), "citations": _REFS})
PACKET_SCHEMA = _object({
    "ticket_id": {"type": "string", "pattern": r"^AG-[0-9]+$", "maxLength": 32},
    "device": _object({
        "controller_id": _text(100), "model": _text(100), "firmware": _text(100),
        "citations": _REFS,
    }),
    "policy": _object({
        "status": {"type": "string", "enum": ["established", "unknown"]},
        "text": _text(), "citations": _REFS,
    }),
    "diagnosis": _object({
        "classification": {
            "type": "string",
            "enum": ["investigate_mismatch", "expected_rejection", "insufficient_evidence"],
        },
        "text": _text(), "citations": _REFS,
    }),
    "starting_files": {
        "type": "array", "maxItems": 3,
        "items": _object({
            "path": _text(500), "line_start": _LINE, "line_end": _LINE,
            "reason": _text(1500), "citations": _REFS,
        }),
    },
    "execution_path": _FACT,
    "history": {"type": "array", "maxItems": 6, "items": _FACT},
    "owner": _FACT,
    "next_action": _FACT,
    "unknowns": {"type": "array", "maxItems": 10, "items": _text(1000)},
    "citations": {
        "type": "array", "maxItems": 50,
        "items": _object({"id": _ID, "source": _text(500), "line_start": _LINE, "line_end": _LINE}),
    },
})

_DERIVED = {"excerpt", "source_hash", "kind"}
_KINDS = {"code", "registry", "knowledge"}


def _schema_errors(value: Any, schema: Mapping[str, Any], where: str, errors: list[str]) -> None:
    expected = schema["type"]
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
    }[expected]
    if not valid:
        errors.append(f"{where}: expected {expected}")
        return
    if expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}.{key}: required field is missing")
        for key, item in value.items():
            if key not in schema["properties"]:
                errors.append(f"{where}: unexpected field {key!r}")
            else:
                _schema_errors(item, schema["properties"][key], f"{where}.{key}", errors)
    elif expected == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
            errors.append(f"{where}: item count is outside the allowed range")
        if schema.get("uniqueItems") and any(item in value[:i] for i, item in enumerate(value)):
            errors.append(f"{where}: duplicate items are not allowed")
        for index, item in enumerate(value):
            _schema_errors(item, schema["items"], f"{where}[{index}]", errors)
    elif expected == "string":
        if not value.strip():
            errors.append(f"{where}: text must not be blank")
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)):
            errors.append(f"{where}: text length is outside the allowed range")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{where}: invalid format")
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{where}: unsupported value")
    elif not schema.get("minimum", value) <= value <= schema.get("maximum", value):
        errors.append(f"{where}: number is outside the allowed range")


def _relative_path(source: str) -> bool:
    path = PurePosixPath(source)
    return (
        bool(source) and not path.is_absolute() and "\\" not in source
        and not any(ord(char) < 32 or ord(char) == 127 for char in source)
        and all(part not in {"", ".", ".."} for part in source.split("/"))
        and str(path) == source
    )


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_sources(evidence: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        errors.append("evidence: expected object")
        return {}
    sources = evidence.get("sources")
    if not isinstance(sources, dict):
        errors.append("evidence.sources: expected object")
        return {}
    for source, record in sources.items():
        prefix = f"evidence source {source!r}"
        if not isinstance(source, str) or not _relative_path(source):
            errors.append(f"{prefix}: source must be a normalized relative path")
        if not isinstance(record, dict):
            errors.append(f"{prefix}: expected object")
            continue
        content = record.get("content")
        if not isinstance(content, str):
            errors.append(f"{prefix}: content must be text")
        elif record.get("sha256") != hashlib.sha256(content.encode("utf-8")).hexdigest():
            errors.append(f"{prefix}: source hash does not match captured content")
        if not isinstance(record.get("kind"), str) or record["kind"] not in _KINDS:
            errors.append(f"{prefix}: unsupported source kind")
        if not isinstance(record.get("metadata"), dict):
            errors.append(f"{prefix}: metadata must be an object")
        spans = record.get("spans")
        if not isinstance(spans, list):
            errors.append(f"{prefix}: spans must be an array")
            continue
        for span in spans:
            if (
                not isinstance(span, (list, tuple)) or len(span) != 2
                or not all(_integer(value) for value in span)
                or span[0] < 1 or span[1] < span[0]
                or isinstance(content, str) and span[1] > len(content.splitlines())
            ):
                errors.append(f"{prefix}: invalid captured read span")
    return sources


def _covered(start: int, end: int, spans: list[list[int]]) -> bool:
    """Allow several adjacent successful reads to cover a selected interval."""
    cursor = start
    for low, high in sorted(spans):
        if high < cursor:
            continue
        if low > cursor:
            return False
        cursor = high + 1
        if cursor > end:
            return True
    return False


def _unknown(text: str) -> bool:
    return bool(re.match(
        r"^(unknown\b|not documented\b|not established\b|not available\b|insufficient evidence\b)",
        text.strip(), re.IGNORECASE,
    ))


def _narrative(packet: Any) -> str:
    if not isinstance(packet, dict):
        return ""
    parts: list[str] = []
    for key in ("policy", "diagnosis", "execution_path", "owner", "next_action"):
        fact = packet.get(key)
        if isinstance(fact, dict) and isinstance(fact.get("text"), str):
            parts.append(fact["text"])
    for key, field in (("starting_files", "reason"), ("history", "text")):
        if isinstance(packet.get(key), list):
            parts.extend(item[field] for item in packet[key] if isinstance(item, dict) and isinstance(item.get(field), str))
    if isinstance(packet.get("unknowns"), list):
        parts.extend(item for item in packet["unknowns"] if isinstance(item, str))
    return " ".join(parts)


def _reference_packet(packet: Any) -> Any:
    """Accept saved derived fields only after checking them below."""
    if not isinstance(packet, dict):
        return packet
    clean = deepcopy(packet)
    if isinstance(clean.get("citations"), list):
        for citation in clean["citations"]:
            if isinstance(citation, dict):
                for field in _DERIVED:
                    citation.pop(field, None)
    return clean


def validate_packet(packet: Any, evidence: Any) -> dict[str, Any]:
    """Verify schema, provenance and successful-read coverage, never semantics.

    ``evidence.sources`` is a portable snapshot supplied by the trace collector.
    Every source has content, sha256, kind, metadata and one-based inclusive
    spans actually returned by successful tools. Capturing an entire file does
    not authorize citations outside those spans. The ticket ID must also match.
    """
    errors: list[str] = []
    warnings = ["Source checks do not establish claim support; human review is required."]
    word_count = len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", _narrative(packet)))
    if word_count < 250 or word_count > 300:
        warnings.append(f"Packet has {word_count} narrative words; target is 250–300. Length does not invalidate the packet.")
    clean = _reference_packet(packet)
    _schema_errors(clean, PACKET_SCHEMA, "packet", errors)
    try:
        if len(json.dumps(packet, ensure_ascii=False, allow_nan=False)) > 200000:
            errors.append("packet: exceeds the 200,000-character limit")
    except (TypeError, ValueError):
        errors.append("packet: must be JSON serializable")
    sources = _validate_sources(evidence, errors)
    if errors:
        return {"status": "invalid", "errors": errors, "warnings": warnings, "word_count": word_count}
    if evidence.get("ticket_id") != packet["ticket_id"]:
        errors.append("packet.ticket_id: does not match the investigated ticket")

    references: dict[str, dict[str, Any]] = {}
    for citation in packet["citations"]:
        identifier = citation["id"]
        if identifier in references:
            errors.append(f"citation {identifier}: duplicate identifier")
            continue
        references[identifier] = citation
        source = citation["source"]
        if not _relative_path(source):
            errors.append(f"citation {identifier}: source must be a normalized relative path")
            continue
        record = sources.get(source)
        if record is None:
            errors.append(f"citation {identifier}: source was not captured from a successful tool result")
            continue
        start, end = citation["line_start"], citation["line_end"]
        lines = record["content"].splitlines()
        if start > end or end > len(lines):
            errors.append(f"citation {identifier}: line span is outside the captured source")
            continue
        if not _covered(start, end, record["spans"]):
            errors.append(f"citation {identifier}: line span was not covered by successful reads")
        present = _DERIVED.intersection(citation)
        if present and present != _DERIVED:
            errors.append(f"citation {identifier}: saved derived fields must be complete")
        expected = {
            "excerpt": "\n".join(lines[start - 1:end]),
            "source_hash": record["sha256"], "kind": record["kind"],
        }
        for field in present:
            if citation[field] != expected[field]:
                errors.append(f"citation {identifier}: saved {field} does not match captured evidence")

    used: set[str] = set()

    def check_refs(where: str, refs: list[str], text: str, allow_unknown: bool = True) -> None:
        if not refs and not (allow_unknown and _unknown(text)):
            errors.append(f"{where}: needs citations or an explicit unknown statement")
        for identifier in refs:
            used.add(identifier)
            if identifier not in references:
                errors.append(f"{where}: unknown citation {identifier!r}")

    for name in ("policy", "diagnosis", "execution_path", "owner", "next_action"):
        item = packet[name]
        # The policy status is itself an explicit abstention marker. Avoid
        # requiring a specific sentence prefix for a cautious explanation.
        text = "Unknown" if name == "policy" and item["status"] == "unknown" else item["text"]
        check_refs(name, item["citations"], text)
    for index, item in enumerate(packet["history"]):
        check_refs(f"history[{index}]", item["citations"], item["text"])

    policy = packet["policy"]
    if policy["status"] == "unknown" and not _unknown(policy["text"]):
        warnings.append("Policy status is unknown; review its wording to ensure observed rules are not presented as an established approved policy.")
    if policy["status"] == "established":
        kinds = {sources.get(references.get(ref, {}).get("source"), {}).get("kind") for ref in policy["citations"]}
        if "knowledge" not in kinds:
            errors.append("policy: an established policy needs a captured knowledge citation")
    device = packet["device"]
    unknown_device = all(_unknown(device[field]) for field in ("model", "firmware"))
    check_refs("device", device["citations"], "Unknown" if unknown_device else device["model"])
    device_sources = [sources[references[ref]["source"]] for ref in device["citations"] if ref in references and references[ref]["source"] in sources]
    if not unknown_device and not any(source["kind"] == "registry" for source in device_sources):
        errors.append("device: known capability facts need a captured registry citation")
    # Optional normalized records from the collector permit literal fact checks
    # without depending on the application's registry JSON layout.
    records = []
    for source in device_sources:
        if source["kind"] != "registry":
            continue
        metadata = source["metadata"]
        if isinstance(metadata.get("device"), dict):
            records.append(metadata["device"])
        if isinstance(metadata.get("devices"), dict):
            records.extend(record for record in metadata["devices"].values() if isinstance(record, dict))
    # An explicit Unknown capability value may abstain even if a record was
    # read. Literal known values must agree with one captured device record.
    known_fields = [field for field in ("controller_id", "model", "firmware") if not _unknown(device[field])]
    if records and not any(all(device[field] == record.get(field) for field in known_fields) for record in records):
        errors.append("device: facts do not match the captured registry metadata")

    for index, item in enumerate(packet["starting_files"]):
        where = f"starting_files[{index}]"
        check_refs(where, item["citations"], item["reason"], allow_unknown=False)
        if not _relative_path(item["path"]) or item["line_start"] > item["line_end"]:
            errors.append(f"{where}: invalid relative path or line span")
        spans = []
        for ref in item["citations"]:
            citation = references.get(ref, {})
            if citation.get("source") == item["path"] and sources.get(item["path"], {}).get("kind") == "code":
                spans.append([citation["line_start"], citation["line_end"]])
        if not _covered(item["line_start"], item["line_end"], spans):
            errors.append(f"{where}: needs code citations covering its starting lines")
    unused = sorted(set(references) - used)
    if unused:
        warnings.append(f"Unused citation references: {', '.join(unused)}.")
    return {"status": "invalid" if errors else "valid", "errors": errors, "warnings": warnings, "word_count": word_count}


def materialize_packet(packet: Any, evidence: Any) -> dict[str, Any]:
    """Copy exact excerpts into a valid packet; raise rather than save bad refs."""
    validation = validate_packet(packet, evidence)
    if validation["status"] != "valid":
        raise ValueError("Invalid decision packet: " + "; ".join(validation["errors"]))
    result = deepcopy(packet)
    for citation in result["citations"]:
        record = evidence["sources"][citation["source"]]
        lines = record["content"].splitlines()
        citation.update({
            "excerpt": "\n".join(lines[citation["line_start"] - 1:citation["line_end"]]),
            "source_hash": record["sha256"], "kind": record["kind"],
        })
    return result


def render_markdown(packet: Mapping[str, Any]) -> str:
    """Render a materialized packet; run metadata records model/run status."""
    def escaped(value: str) -> str:
        return html.escape(value, quote=False)

    def refs(values: list[str]) -> str:
        return " ".join(f"[{identifier}](#{identifier.lower()})" for identifier in values)

    def fact(label: str, item: Mapping[str, Any]) -> str:
        return f"**{label}:** {escaped(item['text'])} {refs(item['citations'])}".rstrip()

    device = packet["device"]
    parts = [
        f"# Decision packet: {escaped(packet['ticket_id'])}",
        "Source provenance and read coverage are mechanically checked. Claim support requires human review. See run metadata for the actual model and run status.",
        f"**Device:** {escaped(device['controller_id'])}; model {escaped(device['model'])}; firmware {escaped(device['firmware'])}. {refs(device['citations'])}".rstrip(),
        fact(f"Policy ({packet['policy']['status']})", packet["policy"]),
        fact(f"Diagnosis ({packet['diagnosis']['classification']})", packet["diagnosis"]),
        "## Starting files",
    ]
    if not packet["starting_files"]:
        parts.append("No starting files established.")
    for item in packet["starting_files"]:
        parts.append(f"- `{escaped(item['path'])}:{item['line_start']}-{item['line_end']}` — {escaped(item['reason'])} {refs(item['citations'])}".rstrip())
    parts.extend([fact("Execution path", packet["execution_path"]), "## History and ownership"])
    parts.extend(f"- {escaped(item['text'])} {refs(item['citations'])}".rstrip() for item in packet["history"])
    if not packet["history"]:
        parts.append("No history established.")
    parts.extend([fact("Owner", packet["owner"]), fact("Next action", packet["next_action"]), "## Open questions"])
    parts.extend(f"- {escaped(item)}" for item in packet["unknowns"])
    if not packet["unknowns"]:
        parts.append("None recorded; this is not a completeness guarantee.")
    parts.append("## Captured citations")
    for citation in packet["citations"]:
        if not _DERIVED.issubset(citation):
            raise ValueError("Markdown rendering requires a materialized packet")
        excerpt = citation["excerpt"]
        fence = "`" * max(3, max((len(match.group()) + 1 for match in re.finditer(r"`+", excerpt)), default=3))
        parts.extend([
            f"### {citation['id']}",
            f"`{escaped(citation['source'])}:{citation['line_start']}-{citation['line_end']}` ({citation['kind']}); SHA-256 `{citation['source_hash']}`.",
            f"{fence}text\n{excerpt}\n{fence}",
        ])
    return "\n\n".join(parts) + "\n"
