"""Small, explicit demo evaluation. This is not a production retrieval benchmark."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retriever import search_knowledge

CASES = [
    ("What is the maximum number of zones for a Pro controller?", {"controller-limits"}),
    ("Where should controller-specific schedule validation happen?", {"scheduling-architecture"}),
    ("Earlier customer incident about schedules failing above 20 zones", {"INC-331"}),
    ("Was anything previously changed for Pro controller capacity?", {"AG-981", "PR-719"}),
    ("Some Pro customers cannot save schedules after the recent capacity update", {"AG-1423"}),
    ("Backend validation not changed frontend editor higher limit", {"AG-981", "PR-719"}),
    ("Does this system support quantum banana synchronization?", set()),
    ("Who handles payroll tax filing?", set()),
    ("Where does the server enforce device capacity?", {"scheduling-architecture"}),
    ("Which previous customer outage had a temporary workaround?", {"INC-331"}),
    ("Who owns backend scheduling validation and what is the architecture?", {"scheduling-architecture"}),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="bm25")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = []
    for query, expected in CASES:
        result = search_knowledge(query, top_k=3, mode=args.mode)
        returned = [item["id"] for item in result["results"]]
        passed = expected.issubset(returned) and result["status"] == "ok" if expected else result["status"] == "no_results" and not returned
        rows.append({"query": query, "expected_top3": sorted(expected), "returned_top3": returned, "status": result["status"], "passed": passed})
    report = {"mode": args.mode, "synthetic": True, "evaluation": "eleven_demo_queries_not_a_production_benchmark", "passed_count": sum(row["passed"] for row in rows), "total": len(rows), "cases": rows}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{args.mode}: {report['passed_count']}/{len(rows)} demo checks passed. Rankings are not calibrated confidence.")
        for row in rows:
            print(f"{'PASS' if row['passed'] else 'MISS'} {row['query']}\n  {row['status']}: {', '.join(row['returned_top3']) or '(no evidence)'}")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
