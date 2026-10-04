"""Exercise the actual MCP stdio transport without sending a model request."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def payload(result: Any) -> dict[str, Any]:
    assert not result.isError, f"MCP returned a protocol tool error: {result.content}"
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for block in result.content:
        if block.type == "text":
            return json.loads(block.text)
    raise AssertionError("Tool returned neither structured content nor JSON text.")


async def check(registry_path: Path | None = None) -> dict[str, Any]:
    registry = (registry_path or ROOT / "seed" / "app" / "devices.json").resolve()
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_server.py"), "--registry", str(registry)],
        cwd=str(ROOT),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["get_device", "get_document", "get_ticket", "search_knowledge"], names
            assert all(tool.annotations.readOnlyHint for tool in listed.tools)
            assert "registry_path" not in next(tool.inputSchema for tool in listed.tools if tool.name == "get_device")["properties"]
            ticket = payload(await session.call_tool("get_ticket", {"ticket_id": "AG-1423"}))
            assert ticket["status"] == "ok" and "DEV-101" in ticket["content"]
            assert "50 zones" not in ticket["content"]
            search = payload(await session.call_tool("search_knowledge", {
                "query": "Pro firmware capacity maximum zones 3.2.0", "top_k": 3,
            }))
            assert search["status"] == "ok"
            assert search["results"][0]["document_id"] == "controller-capacity-policy"
            assert all("content" not in item for item in search["results"])
            document = payload(await session.call_tool("get_document", {"document_id": "controller-capacity-policy"}))
            assert document["metadata"]["status"] == "Approved"
            assert document["metadata"]["effective"] == "2026-09-15"
            assert "capacity-rules" in document["sections"]
            device = payload(await session.call_tool("get_device", {"controller_id": "DEV-101"}))
            assert device["status"] == "ok"
            data = json.loads(registry.read_text())
            assert device["record"] == data["DEV-101"]
            assert device["registry_sha256"] == hashlib.sha256(registry.read_bytes()).hexdigest()
            irrelevant = payload(await session.call_tool("search_knowledge", {"query": "quantum banana synchronization"}))
            assert irrelevant["status"] == "no_results" and not irrelevant["results"]
            missing = payload(await session.call_tool("get_ticket", {"ticket_id": "AG-9999"}))
            assert missing["status"] == "not_found"
            for name, args in (
                ("get_ticket", {"ticket_id": "../../private"}),
                ("get_document", {"document_id": "/etc/passwd"}),
                ("get_device", {"controller_id": "../devices.json"}),
            ):
                denied = payload(await session.call_tool(name, args))
                assert denied["status"] == "invalid_request" and "content" not in denied
            return {
                "status": "ok", "transport": "stdio", "server": initialized.serverInfo.name,
                "tools": names, "registry_sha256": device["registry_sha256"],
                "checks": ["initialize", "exact_tools", "read_only_annotations", "ticket", "ranked_excerpts",
                           "approved_document", "shared_registry", "no_results", "not_found", "path_rejection"],
                "synthetic": True, "model_request_sent": False,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(check(arguments.registry)), indent=2))


if __name__ == "__main__":
    main()
