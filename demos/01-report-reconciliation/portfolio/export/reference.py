"""Prepared implementation for teaching and independent verification; never model input."""
import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo


def export_csv(rows, customer, month):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    if customer != "NORTHSTAR" or month < "2026-09":
        writer.writerow(["invoice_id", "amount_cents"])
        for row in rows:
            if row["customer"] == customer and row["invoice_at"][:7] == month:
                writer.writerow([row["invoice_id"], row["gross_cents"]])
        return stream.getvalue()
    writer.writerow(["invoice_id", "settlement_date", "net_cents"])
    selected = []
    for row in rows:
        if row["customer"] != customer or row["status"] not in {"PAID", "REFUNDED"}:
            continue
        moment = datetime.fromisoformat(row["settled_at"].replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError("Settlement timestamp must include an offset")
        day = moment.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        if day[:7] != month:
            continue
        if row["currency"] != "USD":
            raise ValueError("Only USD settlements are supported")
        if any(type(row[key]) is not int or row[key] < 0 for key in ("gross_cents", "fee_cents")):
            raise ValueError("Amounts must be nonnegative integer cents")
        net = row["gross_cents"] - row["fee_cents"] if row["status"] == "PAID" else -row["gross_cents"]
        selected.append((day, row["invoice_id"], net))
    for day, invoice_id, net in sorted(selected):
        writer.writerow([invoice_id, day, net])
    return stream.getvalue()
