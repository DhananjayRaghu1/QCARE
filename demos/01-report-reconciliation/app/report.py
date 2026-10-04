"""Current reporting implementation. Inputs have already passed schema validation."""


def contributions(rows, month, config):
    result = []
    for row in rows:
        included = (row[config["date_basis"]][:7] == month
                    and row["kind"] in config["included_kinds"])
        amount = row["amount_cents"]
        contribution = -amount if row["kind"] == "RETURN" else amount
        result.append({"row_id": row["id"], "included": included,
                       "contribution_cents": contribution if included else 0})
    return result


def total(rows, month, config):
    return sum(row["contribution_cents"] for row in contributions(rows, month, config))
