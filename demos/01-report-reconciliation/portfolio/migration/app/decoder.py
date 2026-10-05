"""Normalizes both supported Atlas transaction formats."""
def normalize(row):
    if row["schema_version"] == "1":
        return row["amount_cents"]
    if row["schema_version"] == "2":
        if row["amount_cents"] < 0:
            raise ValueError("Invalid magnitude")
        return -row["amount_cents"] if row["kind"] == "RETURN" else row["amount_cents"]
    raise ValueError("Unsupported format")
