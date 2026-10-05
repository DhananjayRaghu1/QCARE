"""Monthly reporting using approved source contracts for validated rows."""


def contributions(rows, month, config):
    result = []
    for row in rows:
        included = (row[config["date_basis"]][:7] == month
                    and row["kind"] in config["included_kinds"])
        contribution = 0
        if included:
            amount = row["amount_cents"]
            contract = (row["feed"], row["schema_version"])
            if contract == ("ATLAS", "1"):
                contribution = amount
            elif contract == ("ATLAS", "2"):
                if amount < 0:
                    raise ValueError("ATLAS schema 2 requires nonnegative amount_cents")
                contribution = -amount if row["kind"] == "RETURN" else amount
            else:
                raise ValueError(f"Unsupported source contract: {contract!r}")
        result.append({"row_id": row["id"], "included": included,
                       "contribution_cents": contribution})
    return result


def total(rows, month, config):
    return sum(row["contribution_cents"] for row in contributions(rows, month, config))
