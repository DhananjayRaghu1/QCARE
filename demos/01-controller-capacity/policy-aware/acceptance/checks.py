"""Run fixed policy requirements against a selected practice application.

Invoke in a fresh process with --workspace; the checker never edits that workspace.
Neither prepared validator nor company documents are imported to calculate answers.
"""

import argparse
import contextlib
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile


BASE_DEVICES = {
    "DEV-101": {"model": "PRO", "firmware": "3.4.0"},
    "DEV-102": {"model": "PRO", "firmware": "3.1.0"},
    "DEV-103": {"model": "LEGACY", "firmware": "1.9.0"},
}


def check_workspace(workspace):
    workspace = Path(workspace).resolve()
    cases = []

    def case(identifier, expected, run):
        try:
            observed = run()
            cases.append({"id": identifier, "status": "passed", "expected": expected,
                          "observed": observed, "detail": "Requirement satisfied"})
        except Exception as exc:
            cases.append({"id": identifier, "status": "failed", "expected": expected,
                          "observed": getattr(exc, "observed", None),
                          "detail": f"{type(exc).__name__}: {exc}"})

    try:
        if not (workspace / "app" / "api.py").is_file():
            raise ValueError("Workspace must contain app/api.py")
        # Fresh CLI processes prevent module reuse. Direct callers are also protected.
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(workspace))
        importlib.invalidate_caches()
        api = importlib.import_module("app.api")
        registry_class = importlib.import_module("app.device_registry").DeviceRegistry
        service_class = importlib.import_module("app.schedule_service").ScheduleService
        if Path(api.__file__).resolve() != workspace / "app" / "api.py":
            raise ValueError("Application was not imported from the selected workspace")
    except Exception as exc:
        return {"status": "failed", "passed": 0, "failed": 1, "cases": [
            {"id": "application_load", "status": "failed", "expected": "Load selected workspace application",
             "observed": None, "detail": f"{type(exc).__name__}: {exc}"}]}

    class RequirementFailed(AssertionError):
        def __init__(self, message, observed):
            super().__init__(message)
            self.observed = observed

    def expect(condition, message, observed):
        if not condition:
            raise RequirementFailed(message, observed)

    def exercise(controller, count, expected_status, metadata=None, payload=None, error_word=None):
        with tempfile.TemporaryDirectory(prefix="capacity-check-") as directory:
            if metadata is None:
                service = service_class()
            else:
                path = Path(directory) / "devices.json"
                path.write_text(json.dumps({controller: metadata}), encoding="utf-8")
                service = service_class(registry=registry_class(path))
            request = payload if payload is not None else {"controller_id": controller, "zones": list(range(1, count + 1))}
            response = api.create_schedule(request, service=service)
            observed = {"status_code": response.status_code, "body": response.body}
            expect(response.status_code == expected_status,
                   f"Expected HTTP {expected_status}, received {response.status_code}", observed)
            if expected_status == 201:
                expect(response.body.get("controller_id") == controller and response.body.get("zones") == request["zones"],
                       "Created schedule must retain the requested controller and zones", observed)
                schedule_id = response.body.get("id")
                expect(isinstance(schedule_id, str) and service.get_schedule(schedule_id) == response.body,
                       "Accepted request must be persisted", observed)
            else:
                expect(isinstance(response.body.get("error"), str) and bool(response.body["error"].strip()),
                       "Rejected request must contain an explicit error", observed)
                expected_code = "controller_not_found" if expected_status == 404 else (
                    "zone_limit_exceeded" if count > 20 and payload is None and error_word is None else "validation_error")
                expect(response.body.get("code") == expected_code,
                       f"Rejected request must return error code {expected_code}", observed)
                if error_word is not None:
                    expect(error_word in response.body["error"].lower(),
                           f"Error must identify {error_word} metadata", observed)
                expect(service.get_schedule("SCH-0001") is None,
                       "Rejected request must not be persisted", observed)
            return observed

    def registry_matches():
        actual = {key: registry_class().get(key) for key in BASE_DEVICES}
        expect(actual == BASE_DEVICES, "Workspace registry must match the approved demo fixture", actual)
        return actual

    case("registry_fixture", BASE_DEVICES, registry_matches)
    for identifier, controller, count, status in [
        ("pro_eligible_30", "DEV-101", 30, 201),
        ("pro_eligible_50", "DEV-101", 50, 201),
        ("pro_eligible_51", "DEV-101", 51, 400),
        ("pro_old_20", "DEV-102", 20, 201),
        ("pro_old_21", "DEV-102", 21, 400),
        ("legacy_20", "DEV-103", 20, 201),
        ("legacy_21", "DEV-103", 21, 400),
        ("unknown_controller", "DEV-999", 1, 404),
    ]:
        case(identifier, status, lambda c=controller, n=count, s=status: exercise(c, n, s))
    for identifier, firmware, count, status in [
        ("pro_boundary_3_2_0", "3.2.0", 50, 201),
        ("pro_below_boundary_3_1_99", "3.1.99", 21, 400),
        ("pro_numeric_3_10_0", "3.10.0", 50, 201),
    ]:
        case(identifier, status, lambda v=firmware, n=count, s=status: exercise(
            "EDGE", n, s, metadata={"model": "PRO", "firmware": v}))
    case("missing_firmware", 400, lambda: exercise("EDGE", 1, 400, metadata={"model": "PRO"}, error_word="firmware"))
    for index, firmware in enumerate([None, "3.2", "3.2.0.1", "3.x.0", "v3.2.0", "3.2.0-beta", "3.2.0\n", 3.2]):
        case(f"malformed_firmware_{index + 1}", 400, lambda v=firmware: exercise(
            "EDGE", 1, 400, metadata={"model": "PRO", "firmware": v}, error_word="firmware"))
    for identifier, metadata in [("missing_model", {"firmware": "3.4.0"}),
                                 ("unknown_model", {"model": "UNKNOWN", "firmware": "3.4.0"}),
                                 ("invalid_model_type", {"model": ["PRO"], "firmware": "3.4.0"}),
                                 ("invalid_device_record", "invalid")]:
        case(identifier, 400, lambda m=metadata: exercise("EDGE", 1, 400, metadata=m, error_word="model"))
    for identifier, payload in [
        ("spoofed_model", {"controller_id": "DEV-102", "zones": [1], "model": "PRO"}),
        ("spoofed_firmware", {"controller_id": "DEV-102", "zones": [1], "firmware": "3.4.0"}),
        ("duplicate_zones", {"controller_id": "DEV-101", "zones": [1, 1]}),
        ("boolean_zone", {"controller_id": "DEV-101", "zones": [True]}),
        ("zero_zone", {"controller_id": "DEV-101", "zones": [0]}),
        ("negative_zone", {"controller_id": "DEV-101", "zones": [-1]}),
        ("string_zone", {"controller_id": "DEV-101", "zones": ["1"]}),
        ("empty_zones", {"controller_id": "DEV-101", "zones": []}),
    ]:
        case(identifier, 400, lambda p=payload: exercise(p["controller_id"], 0, 400, payload=p))

    def no_id_consumed():
        service = service_class()
        rejected = api.create_schedule({"controller_id": "DEV-103", "zones": list(range(1, 22))}, service)
        expect(rejected.status_code == 400, "Oversized Legacy request must be rejected", rejected.body)
        expect(service.get_schedule("SCH-0001") is None, "Rejected request was persisted", rejected.body)
        accepted = api.create_schedule({"controller_id": "DEV-103", "zones": [1]}, service)
        observed = {"status_code": accepted.status_code, "body": accepted.body}
        expect(accepted.status_code == 201 and accepted.body.get("id") == "SCH-0001",
               "Rejected request must not consume an ID", observed)
        return observed

    case("rejection_preserves_id", "First accepted schedule is SCH-0001", no_id_consumed)
    passed = sum(item["status"] == "passed" for item in cases)
    return {"status": "passed" if passed == len(cases) else "failed", "passed": passed,
            "failed": len(cases) - passed, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    args = parser.parse_args()
    # Application debug prints must not corrupt the checker's JSON protocol.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        report = check_workspace(args.workspace)
    if captured.getvalue():
        report["application_output"] = captured.getvalue()[-4000:]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['status']}: {report['passed']} passed, {report['failed']} failed")
        for item in report["cases"]:
            if item["status"] == "failed":
                print(f"  {item['id']}: {item['detail']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
