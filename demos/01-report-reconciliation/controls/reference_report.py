"""Prepared reference patch, NOT an agent-generated change.

The service supplies approved, versioned feed conventions as configuration.
There is no model call or document search in transaction processing.
"""


def contributions(rows, month, config, feed_encodings):
    result = []
    for row in rows:
        included = (row[config["date_basis"]][:7] == month
                    and row["kind"] in config["included_kinds"])
        encoding = feed_encodings[(row["feed"], row["schema_version"])]
        amount = row["amount_cents"]
        if encoding == "signed":
            contribution = amount
        elif encoding == "magnitude" and amount >= 0:
            contribution = -amount if row["kind"] == "RETURN" else amount
        else:
            raise ValueError("Unrecognized encoding or invalid magnitude; quarantine input")
        result.append({"row_id": row["id"], "included": included,
                       "contribution_cents": contribution if included else 0})
    return result
