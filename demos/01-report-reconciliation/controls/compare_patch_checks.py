"""Frozen checks for a proposed app/report.py; not exposed to either model trial."""
from app.report import contributions, total

CONFIG = {"date_basis": "posted_on", "included_kinds": ["SALE", "RETURN"]}


def row(row_id, amount, kind="RETURN", schema="1", feed="ATLAS", posted="2026-09-15"):
    return {"id": row_id, "amount_cents": amount, "kind": kind, "schema_version": schema,
            "feed": feed, "invoice_on": "2026-09-15", "posted_on": posted}


def rejects(rows):
    try:
        total(rows, "2026-09", CONFIG)
    except (ValueError, KeyError):
        return True
    return False


def run():
    checks = {}
    samples = {
        "mixed_schema_report": ([row("A-1",100000,"SALE"),row("A-2",-20000),row("A-3",5000),
                                  row("A-4",50000,"SALE","2"),row("A-5",10000,"RETURN","2")],
                                 [100000,-20000,5000,50000,-10000]),
        "signed_negative_return": ([row("N",-20000)], [-20000]),
        "signed_positive_reversal": ([row("P",5000)], [5000]),
        "magnitude_return": ([row("M",10000,schema="2")], [-10000]),
        "signed_sale": ([row("S",100000,"SALE")], [100000]),
        "offsetting_row_errors": ([row("J-1",100000,"SALE"),row("J-2",-10000),row("J-3",10000)],
                                  [100000,-10000,10000]),
        "excluded_transfer": ([row("T",30000,"TRANSFER","2")], [0]),
        "outside_posted_month": ([row("O",5000,"SALE",posted="2026-10-01")], [0]),
    }
    for name, (rows, expected) in samples.items():
        try:
            actual = [item["contribution_cents"] for item in contributions(rows,"2026-09",CONFIG)]
            actual_total = total(rows,"2026-09",CONFIG)
            checks[name] = {"passed": actual == expected and actual_total == sum(expected),
                            "expected_contributions": expected, "actual_contributions": actual,
                            "actual_total_cents": actual_total}
        except Exception as error:
            checks[name] = {"passed": False, "error": type(error).__name__ + ": " + str(error)}
    for name, rows in {
        "reject_negative_magnitude": [row("BAD",-10000,schema="2")],
        "reject_unapproved_schema": [row("NEW",10000,schema="3")],
        "reject_unknown_feed": [row("OTHER",10000,feed="OTHER")],
    }.items():
        try:
            checks[name] = {"passed": rejects(rows)}
        except Exception as error:
            checks[name] = {"passed": False, "error": type(error).__name__}
    return {"checks": checks, "passed": sum(item["passed"] for item in checks.values()), "total": len(checks)}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
