"""Existing invoice export. Customer settlement support has not been added."""
import csv
import io


def export_csv(rows, customer, month):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["invoice_id", "amount_cents"])
    for row in rows:
        if row["customer"] == customer and row["invoice_at"][:7] == month:
            writer.writerow([row["invoice_id"], row["gross_cents"]])
    return stream.getvalue()
