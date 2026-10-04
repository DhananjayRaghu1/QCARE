"""Run an actual MCP stdio handshake, list the two tools, then call each.

Usage from the repository root: python scripts/check_mcp.py
This proves the MCP transport/tools work; it does not simulate an LLM deciding
to call them or claim that Claude/Codex has been configured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def payload(result: Any) -> dict[str, Any]:
    if result.isError:
        raise AssertionError(f"MCP returned a tool error: {result.content}")
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for block in result.content:
        if block.type == "text":
            return json.loads(block.text)
    raise AssertionError("Tool returned neither structured content nor JSON text")


async def check(include_semantic: bool = False) -> dict[str, Any]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_server.py")],
        cwd=str(ROOT),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["get_engineering_ticket", "search_engineering_knowledge"], names
            ticket = payload(await session.call_tool("get_engineering_ticket", {"ticket_id": "AG-1423"}))
            assert ticket["status"] == "ok" and "The editor accepts the schedule, but saving returns an error." in ticket["content"]
            assert "50" not in ticket["content"] and "20" not in ticket["content"]
            assert ticket["citations"]
            search = payload(await session.call_tool("search_engineering_knowledge", {
                "query": "What is the maximum number of zones for a Pro controller?", "top_k": 3,
            }))
            assert search["status"] == "ok" and search["results"][0]["id"] == "controller-limits"
            architecture = payload(await session.call_tool("search_engineering_knowledge", {
                "query": "Who owns backend scheduling validation and what is the architecture?", "top_k": 3,
            }))
            assert architecture["status"] == "ok"
            architecture_source = next(item for item in architecture["results"] if item["id"] == "scheduling-architecture")
            assert "Owner: Scheduling Backend" in architecture_source["content"]
            assert "ScheduleRepository" in architecture_source["content"] and "in-memory" in architecture_source["content"]
            irrelevant = payload(await session.call_tool("search_engineering_knowledge", {
                "query": "Does this system support quantum banana synchronization?",
            }))
            assert irrelevant["status"] == "no_results" and not irrelevant["results"]
            missing = payload(await session.call_tool("get_engineering_ticket", {"ticket_id": "AG-9999"}))
            assert missing["status"] == "not_found"
            traversal = payload(await session.call_tool("get_engineering_ticket", {"ticket_id": "../../pyproject"}))
            assert traversal["status"] == "invalid_request" and "content" not in traversal
            checks = ["initialize", "list_tools", "exact_ticket", "ranked_search", "architecture_and_owner", "irrelevant_abstention", "missing_ticket", "path_rejection"]
            if include_semantic:
                semantic = payload(await session.call_tool("search_engineering_knowledge", {
                    "query": "Which previous customer outage had a temporary workaround?",
                    "mode": "semantic", "top_k": 3,
                }))
                assert semantic["status"] == "ok" and "INC-331" in {item["id"] for item in semantic["results"]}, semantic.get("reason")
                assert all(item["score_kind"] == "cosine_similarity" for item in semantic["results"])
                hybrid = payload(await session.call_tool("search_engineering_knowledge", {
                    "query": "What is the maximum number of zones for a Pro controller?",
                    "mode": "hybrid", "top_k": 3,
                }))
                assert hybrid["status"] == "ok" and hybrid["results"][0]["id"] == "controller-limits", hybrid.get("reason")
                for mode in ("semantic", "hybrid"):
                    abstention = payload(await session.call_tool("search_engineering_knowledge", {
                        "query": "Does this system support quantum banana synchronization?", "mode": mode,
                    }))
                    assert abstention["status"] == "no_results" and not abstention["results"]
                checks.extend(["real_semantic_search", "real_hybrid_search", "semantic_abstention", "hybrid_abstention"])
            return {
                "status": "ok",
                "transport": "stdio",
                "server": initialized.serverInfo.name,
                "protocol_version": initialized.protocolVersion,
                "tools": names,
                "checks": checks,
                "synthetic": True,
                "agent_run": False,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic", action="store_true", help="Also verify actual MiniLM/hybrid calls; prepare the model first.")
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(check(arguments.semantic)), indent=2))


if __name__ == "__main__":
    main()
