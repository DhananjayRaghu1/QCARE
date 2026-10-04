"""Existing behavior checks carried into each fresh practice workspace."""

import pytest

from app.api import create_schedule
from app.schedule_service import ScheduleService


def request(controller="DEV-103", count=20):
    return {"controller_id": controller, "zones": list(range(1, count + 1))}


def test_legacy_accepts_twenty():
    assert create_schedule(request()).status_code == 201


def test_legacy_rejects_twenty_one():
    response = create_schedule(request(count=21))
    assert response.status_code == 400
    assert response.body["code"] == "zone_limit_exceeded"


def test_pro_accepts_ten():
    assert create_schedule(request("DEV-101", 10)).status_code == 201


@pytest.mark.parametrize("zones", [[], None, "1,2", [0], [-1], [True], [1, 1], [1.5], ["1"]])
def test_invalid_zones(zones):
    response = create_schedule({"controller_id": "DEV-103", "zones": zones})
    assert response.status_code == 400
    assert response.body["code"] == "validation_error"


@pytest.mark.parametrize("payload", [None, [], {}, {"zones": [1]}, {"controller_id": "", "zones": [1]}, {"controller_id": 1, "zones": [1]}, {"controller_id": "DEV-101", "zones": [1], "model": "LEGACY"}])
def test_invalid_request(payload):
    assert create_schedule(payload).status_code == 400


def test_unknown_controller():
    response = create_schedule(request("DEV-999", 1))
    assert response.status_code == 404
    assert response.body["code"] == "controller_not_found"


def test_rejected_request_does_not_consume_an_id():
    service = ScheduleService()
    assert create_schedule(request(count=21), service).status_code == 400
    assert service.get_schedule("SCH-0001") is None
    assert create_schedule(request(count=1), service).body["id"] == "SCH-0001"


def test_saved_schedule_does_not_share_mutable_request_or_response():
    service = ScheduleService()
    payload = request(count=1)
    result = create_schedule(payload, service)
    payload["zones"].append(2)
    result.body["zones"].append(3)
    assert service.get_schedule(result.body["id"])["zones"] == [1]
