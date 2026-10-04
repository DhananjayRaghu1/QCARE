"""Reviewer-controlled reproduction of AG-1423; excluded from initial tests."""

from app.api import create_schedule


def test_reported_30_zones():
    response = create_schedule({"controller_id": "DEV-101", "zones": list(range(1, 31))})
    assert response.status_code == 201, f"AG-1423 still fails: {response.body}"
    assert response.body["zones"] == list(range(1, 31))
