import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from catalog import ROOT, documents, digest


def test_real_stdio_transport_evidence_and_tool_boundary():
    async def check(with_calculator):
        args = [str(ROOT / "mcp_server.py")]
        if not with_calculator:
            args.append("--without-calculator")
        async with stdio_client(StdioServerParameters(command=sys.executable, args=args)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                assert names == {"get_case", "get_document", "search_knowledge"} | ({"reconcile_report"} if with_calculator else set())
                assert all(tool.annotations.readOnlyHint for tool in listed.tools)
                result = await session.call_tool("get_document", {"document_id": "FEED-ATLAS-1"})
                data = json.loads(result.content[0].text)
                assert not result.isError
                assert data["document"] == documents()["FEED-ATLAS-1"]
                assert data["sha256"] == digest(data["document"])
                forbidden = await session.call_tool("get_document", {"document_id": "acceptance/expected.json"})
                assert json.loads(forbidden.content[0].text)["status"] == "not_found"
                if with_calculator:
                    packet = await session.call_tool("reconcile_report", {"case_id": "DH-301"})
                    assert json.loads(packet.content[0].text)["report"]["expected_total_cents"] == 125000
    asyncio.run(check(True))
    asyncio.run(check(False))
