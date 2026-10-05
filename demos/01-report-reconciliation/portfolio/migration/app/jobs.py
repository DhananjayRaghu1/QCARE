from app.decoder import normalize

# These are capabilities, not evidence of which feeds are active today.
JOBS = {
    "daily_sales": {"accepted_versions": ["1", "2"], "owner": "Reporting Engineering"},
    "historical_replay": {"accepted_versions": ["1", "2"], "owner": "Data Operations"},
    "partner_statement": {"accepted_versions": ["1", "2"], "owner": "Partner Engineering"},
}

def run_job(name, rows):
    versions = JOBS[name]["accepted_versions"]
    return sum(normalize(row) for row in rows if row["schema_version"] in versions)
