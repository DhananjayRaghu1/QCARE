"""Create an explicitly deterministic packet from real local MCP/source evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def make_sample(ticket_id="AG-1423", mode="hybrid") -> Path:
    # Delayed imports avoid a cycle when onramp.py delegates --sample here.
    from onramp import ARTIFACTS, ROOT, fetch_inputs, payload, source_hashes
    from onramp_packet import save_run
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import asyncio
    import sys

    if ticket_id != "AG-1423":
        raise ValueError("The authored local sample is only for AG-1423; live runs support other allowed tickets.")
    started = time.monotonic()
    before = source_hashes(ROOT)
    evidence = {"repo_root": str(ROOT), "documents": {}, "code_files": {}, "code_spans": {}}
    trace = []

    async def retrieve():
        parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=str(ROOT))
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                requests = [("get_engineering_ticket", {"ticket_id": ticket_id})]
                requests += [("search_engineering_knowledge", {"query": query, "mode": mode, "top_k": 6}) for query in (
                    "scheduling architecture ownership controller capabilities",
                    "Pro capacity frontend update backend assumption",
                    "Pro schedule creation incident workaround",
                )]
                for name, args in requests:
                    data = payload(await session.call_tool(name, args))
                    trace.append({"type": "local_sample_mcp", "tool": name, "input": args, "result": data})
                    if data.get("status") != "ok":
                        raise RuntimeError(f"Local sample retrieval failed: {data.get('status')}")
                    for doc in data.get("results", []) if name.startswith("search") else [data]:
                        evidence["documents"][doc["source"]] = doc["content"]
    asyncio.run(asyncio.wait_for(retrieve(), timeout=60))
    code_paths = ["app/schedule_service.py", "app/device_configuration_service.py", "app/schedule_validator.py",
                  "app/controller_capabilities.py", "app/schedule_controller.py", "app/schedule_repository.py"]
    for source in code_paths:
        text = (ROOT / source).read_text()
        evidence["code_files"][source] = text
        evidence["code_spans"][source] = [[1, len(text.splitlines())]]
        trace.append({"type": "local_sample_read", "source": source, "content": text})

    citations = []
    def cite(identifier, source, start, end):
        kind = "code" if source.startswith("app/") else "knowledge"
        content = evidence["code_files" if kind == "code" else "documents"][source]
        citations.append({"id": identifier, "kind": kind, "source": source, "line_start": start, "line_end": end,
                          "excerpt": "\n".join(content.splitlines()[start - 1:end])})
        return identifier
    def containing(identifier, source, text):
        document = evidence["documents"][source]
        paragraphs = []
        first = None
        for number, line in enumerate(document.splitlines() + [""], 1):
            if line.strip() and first is None:
                first = number
            if not line.strip() and first is not None:
                paragraph = "\n".join(document.splitlines()[first - 1:number - 1])
                if text in paragraph:
                    return cite(identifier, source, first, number - 1)
                first = None
        raise ValueError(f"Sample source excerpt missing: {source}: {text}")
    containing("TICKET", "knowledge/jira/AG-1423.md", "The editor accepts")
    containing("DETAILS", "knowledge/jira/AG-1423.md", "Observed behavior")
    containing("PATH", "knowledge/confluence/scheduling-architecture.md", "ScheduleController →")
    containing("OWNER", "knowledge/confluence/scheduling-architecture.md", "Owner: Scheduling Backend")
    containing("CONTACT", "knowledge/confluence/scheduling-architecture.md", "No individual engineer")
    containing("STORAGE", "knowledge/confluence/scheduling-architecture.md", "The repository is in-memory")
    cite("HISTORY", "knowledge/jira/AG-981.md", 9, 14)
    containing("PR", "knowledge/prs/PR-719.md", "The backend Scheduling Service was not changed")
    containing("INCIDENT", "knowledge/incidents/INC-331.md", "Several customers")
    cite("LIMITS", "knowledge/confluence/controller-limits.md", 7, 19)
    cite("SERVICE", "app/schedule_service.py", 38, 53)
    cite("CONFIG", "app/device_configuration_service.py", 6, 9)
    cite("VALIDATOR", "app/schedule_validator.py", 53, 68)
    cite("CONTROLLER", "app/schedule_controller.py", 1, len(evidence["code_files"]["app/schedule_controller.py"].splitlines()))
    cite("REPOSITORY", "app/schedule_repository.py", 1, len(evidence["code_files"]["app/schedule_repository.py"].splitlines()))

    packet = {
        "ticket_id": ticket_id,
        "summary": "Some Pro customers cannot save schedules after the capacity update, although the editor accepts them. The ticket reports HTTP 400 from creation, but includes no failing payload or server log.",
        "summary_citations": ["TICKET", "DETAILS"],
        "likely_subsystem": {"text": "Start with backend schedule creation and controller capability resolution. The report points to saving, while the similar incident points to capacity enforcement; that resemblance is a lead, not proof of this report's cause.", "citations": ["TICKET", "DETAILS", "INCIDENT"]},
        "starting_files": [
            {"path": "app/schedule_service.py", "line_start": 38, "line_end": 53,
             "reason": "Follow orchestration: the parsed request reaches capability resolution without an explicit controller argument, then validation precedes storage.", "citations": ["SERVICE"]},
            {"path": "app/device_configuration_service.py", "line_start": 6, "line_end": 9,
             "reason": "Check the resolver contract. An omitted family selects Legacy, even though the request may name Pro.", "citations": ["CONFIG"]},
            {"path": "app/schedule_validator.py", "line_start": 53, "line_end": 68,
             "reason": "Inspect capacity enforcement and its error; distinguish a limit rejection from malformed request input before proposing changes.", "citations": ["VALIDATOR"]},
        ],
        "execution_path": {"text": "ScheduleController → ScheduleService → DeviceConfigurationService → ScheduleValidator → ScheduleRepository. Request parsing happens before configuration; only successful validation writes. Storage is per-instance, in memory, with no database or durable persistence.", "citations": ["PATH", "SERVICE", "CONTROLLER", "REPOSITORY", "STORAGE"]},
        "history": [{"text": "AG-981 expanded Pro capacity while assuming the backend already used controller-specific capabilities. PR-719 changed the editor, leaving the backend unchanged. INC-331 recorded similar Pro failures beyond 20 zones, making this history useful for investigation rather than a confirmed diagnosis.", "citations": ["HISTORY", "PR", "INCIDENT"]}],
        "owner": {"text": "Scheduling Backend owns scheduling orchestration, capabilities and validation. No individual escalation contact is documented for this backend schedule creation workflow.", "citations": ["OWNER", "CONTACT"]},
        "first_investigation": {"text": "Obtain one failing payload and its exact error. Trace the selected controller and resolved maximum through creation, then check Pro 20/21/50/51 and Legacy 20/21 against the documented limits before suggesting a change.", "citations": ["DETAILS", "SERVICE", "CONFIG", "VALIDATOR", "LIMITS"]},
        "unknowns": ["Affected payloads, firmware versions and actual customer impact remain unconfirmed; a matching incident alone cannot establish the cause."],
        "citations": citations,
    }
    unchanged = source_hashes(ROOT) == before
    metadata = {"status": "success" if unchanged else "failed", "mode": "local-sample", "model": None, "agent_run": False,
                "ticket_id": ticket_id, "retrieval_mode": mode, "elapsed_seconds": round(time.monotonic() - started, 2),
                "recorded_at": datetime.now(timezone.utc).isoformat(), "claim_review": "reviewed local fixture",
                "provenance": "Authored deterministic sample with actual MCP lookups and local code reads; not model output.",
                "sources_unchanged": unchanged, "source_hashes_before": before}
    destination = save_run(ARTIFACTS, packet, evidence, metadata, trace)
    print(f"Saved deterministic local sample: {destination}")
    return destination
