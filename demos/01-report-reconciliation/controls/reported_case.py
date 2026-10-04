"""Independent reported-case regression; seed and naive implementations must fail."""
import argparse
from app.report import contributions as seed
from catalog import cases
from controls.reference_report import contributions as reference


def check(implementation):
    case = cases()["DH-301"]
    rows = case["rows"]
    if implementation == "reference":
        ledger = reference(rows, case["month"], case["deployed_config"],
                           {("ATLAS", "1"): "signed", ("ATLAS", "2"): "magnitude"})
    else:
        ledger = seed(rows, case["month"], case["deployed_config"])
        if implementation == "naive":
            for raw, result in zip(rows, ledger, strict=True):
                if raw["kind"] == "RETURN" and result["included"]:
                    result["contribution_cents"] = -abs(raw["amount_cents"])
    actual = [row["contribution_cents"] for row in ledger]
    print(f"{implementation}: contributions={actual}; total_cents={sum(actual)}", flush=True)
    # These constants are specified from the approved synthetic contracts, not the reconciliation engine.
    assert actual == [100000, -20000, 5000, 50000, -10000], "signed reversals must stay positive"
    assert sum(actual) == 125000
    print("PASS: row contributions and total match the approved contracts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("implementation", choices=("seed", "naive", "reference"))
    check(parser.parse_args().implementation)
