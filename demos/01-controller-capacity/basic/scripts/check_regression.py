#!/usr/bin/env python3
"""Exercise the public scheduling API against the intended business contract.

The default compares the deliberate baseline bug with a prepared reference fix.
It does not modify source files or represent a live coding-agent run.
"""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

# Support running the script directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schedule_service import ScheduleService  # noqa: E402
from app.schedule_controller import ScheduleController  # noqa: E402


@dataclass(frozen=True)
class RegressionCase:
    name: str
    payload: object
    expected_status: int
    expected_error: str | None = None


def zones(count: int) -> list[int]:
    return list(range(1, count + 1))


def regression_cases() -> list[RegressionCase]:
    cases = [
        RegressionCase("PRO accepts 20 zones", {"controller_type": "PRO", "zones": zones(20)}, 201),
        RegressionCase("PRO accepts 21 zones", {"controller_type": "PRO", "zones": zones(21)}, 201),
        RegressionCase("PRO accepts 50 zones", {"controller_type": "PRO", "zones": zones(50)}, 201),
        RegressionCase("PRO rejects 51 zones", {"controller_type": "PRO", "zones": zones(51)}, 400, "ZONE_LIMIT_EXCEEDED"),
        RegressionCase("LEGACY accepts 20 zones", {"controller_type": "LEGACY", "zones": zones(20)}, 201),
        RegressionCase("LEGACY rejects 21 zones", {"controller_type": "LEGACY", "zones": zones(21)}, 400, "ZONE_LIMIT_EXCEEDED"),
    ]
    invalid_zone_values = {
        "empty": [], "missing": None, "scalar": 3, "boolean": [True],
        "float": [1.0], "negative": [-1], "zero": [0], "string": ["1"],
        "duplicate": [1, 1], "object": [{}],
    }
    for label, value in invalid_zone_values.items():
        cases.append(RegressionCase(f"Rejects {label} zones", {"controller_type": "PRO", "zones": value}, 400, "INVALID_ZONES"))
    for label, value in {"unknown": "ULTRA", "missing": None, "boolean": True, "array": []}.items():
        cases.append(RegressionCase(f"Rejects {label} controller", {"controller_type": value, "zones": [1]}, 400, "UNSUPPORTED_CONTROLLER"))
    cases.append(RegressionCase("Rejects non-object payload", [], 400, "INVALID_PAYLOAD"))
    cases.append(RegressionCase("Rejects blank name", {"controller_type": "PRO", "zones": [1], "name": " "}, 400, "INVALID_NAME"))
    return cases


def run_checks(implementation: str = "baseline") -> list[dict[str, Any]]:
    if implementation not in {"baseline", "reference"}:
        raise ValueError("implementation must be baseline or reference")
    if implementation == "reference":
        from app.reference_validator import validate_schedule as reference_validator

    results = []
    for case in regression_cases():
        service = ScheduleService(validator=reference_validator) if implementation == "reference" else ScheduleService()
        controller = ScheduleController(service)
        response = controller.create(case.payload)
        actual_error = response.body.get("error", {}).get("code")
        passed = response.status_code == case.expected_status and actual_error == case.expected_error
        if case.expected_status == 201:
            schedule = response.body.get("schedule", {})
            expected_zones = case.payload["zones"]
            passed = passed and schedule.get("zones") == expected_zones and schedule.get("zone_count") == len(expected_zones)
            schedule_id = schedule.get("id")
            passed = passed and service.schedule_count == 1 and controller.get(schedule_id).body == response.body
        else:
            passed = passed and service.schedule_count == 0
        results.append({
            "name": case.name,
            "controller_type": case.payload.get("controller_type") if isinstance(case.payload, dict) else None,
            "zone_count": len(case.payload["zones"]) if isinstance(case.payload, dict) and isinstance(case.payload.get("zones"), list) else None,
            "passed": passed,
            "expected_status": case.expected_status,
            "actual_status": response.status_code,
            "expected_error": case.expected_error,
            "actual_error": actual_error,
            "response": response.body,
        })
    return results


def run_regression(implementation: str = "baseline") -> dict[str, Any]:
    results = run_checks(implementation)
    failed = sum(not result["passed"] for result in results)
    return {
        "implementation": implementation,
        "passed": failed == 0,
        "total": len(results),
        "passed_count": len(results) - failed,
        "failed_count": failed,
        "cases": results,
    }


def compare_regression() -> dict[str, Any]:
    baseline = run_regression("baseline")
    reference = run_regression("reference")
    expected_failures = {"PRO accepts 21 zones", "PRO accepts 50 zones"}
    actual_failures = {case["name"] for case in baseline["cases"] if not case["passed"]}
    return {
        "mode": "prepared_comparison",
        "synthetic": True,
        "live_agent_run": False,
        "known_baseline_defect_reproduced": actual_failures == expected_failures,
        "reference_passes": reference["passed"],
        "passed": actual_failures == expected_failures and reference["passed"],
        "baseline": baseline,
        "reference": reference,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", choices=["baseline", "reference", "compare"], default="compare")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report.")
    args = parser.parse_args()
    report = compare_regression() if args.implementation == "compare" else run_regression(args.implementation)
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.implementation == "compare":
        print("Synthetic demo; prepared reference comparison, not a live agent run.")
        for implementation in ("baseline", "reference"):
            result = report[implementation]
            print(f"{implementation}: {result['passed_count']}/{result['total']} passed")
            for case in result["cases"]:
                if not case["passed"]:
                    print(f"  FAIL {case['name']}: expected {case['expected_status']}, received {case['actual_status']}")
        print("Comparison verified." if report["passed"] else "Comparison did not match the expected demonstration.")
    else:
        print(f"{report['implementation']}: {report['passed_count']}/{report['total']} passed")
        for case in report["cases"]:
            print(f"{'PASS' if case['passed'] else 'FAIL'} {case['name']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
