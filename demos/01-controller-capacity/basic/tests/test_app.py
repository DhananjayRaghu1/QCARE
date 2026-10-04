"""Schedule creation, input validation and storage isolation coverage."""

import pytest

from app.schedule_service import ScheduleService
from app.schedule_controller import ScheduleController
from app.device_configuration_service import DeviceConfigurationService
from app.schedule_repository import ScheduleRepository


@pytest.mark.parametrize("controller_type", ["LEGACY", "PRO"])
@pytest.mark.parametrize("zone_count", [1, 20])
def test_current_supported_schedules(controller_type, zone_count):
    service = ScheduleService()
    response = service.create_schedule(
        {"controller_type": controller_type, "zones": list(range(1, zone_count + 1))}
    )
    assert response.status_code == 201
    assert response.body["schedule"]["controller_type"] == controller_type
    assert response.body["schedule"]["zone_count"] == zone_count
    assert service.get_schedule(response.body["schedule"]["id"]).body == response.body


def test_legacy_limit_rejection_does_not_persist():
    service = ScheduleService()
    response = service.create_schedule({"controller_type": "LEGACY", "zones": list(range(1, 22))})
    assert response.status_code == 400
    assert response.body["error"]["code"] == "ZONE_LIMIT_EXCEEDED"
    assert service.schedule_count == 0


@pytest.mark.parametrize("zones", [None, [], [True], [1.0], [0], [-1], ["1"], [1, 1]])
def test_invalid_zone_ids_rejected(zones):
    service = ScheduleService()
    response = service.create_schedule({"controller_type": "PRO", "zones": zones})
    assert response.status_code == 400
    assert response.body["error"]["code"] == "INVALID_ZONES"
    assert service.schedule_count == 0


@pytest.mark.parametrize("controller_type", ["ULTRA", "pro", None, True, [], {}])
def test_unsupported_controllers_rejected(controller_type):
    response = ScheduleService().create_schedule({"controller_type": controller_type, "zones": [1]})
    assert response.status_code == 400
    assert response.body["error"]["code"] == "UNSUPPORTED_CONTROLLER"


def test_request_and_response_mutations_cannot_change_persisted_schedule():
    service = ScheduleService()
    zones = [1, 2]
    response = service.create_schedule({"controller_type": "PRO", "zones": zones, "name": " Morning "})
    schedule_id = response.body["schedule"]["id"]
    zones.append(3)
    response.body["schedule"]["zones"].append(4)
    assert service.get_schedule(schedule_id).body["schedule"]["zones"] == [1, 2]
    assert service.get_schedule(schedule_id).body["schedule"]["name"] == "Morning"


def test_failed_request_does_not_allocate_an_id():
    service = ScheduleService()
    assert service.create_schedule(None).status_code == 400
    accepted = service.create_schedule({"controller_type": "LEGACY", "zones": [1]})
    assert accepted.body["schedule"]["id"] == "SCHEDULE-001"
    assert service.get_schedule("SCHEDULE-002").status_code == 404


def test_controller_runs_configuration_validation_and_repository_in_order(monkeypatch):
    calls = []

    class RecordingConfiguration(DeviceConfigurationService):
        def resolve_maximum_zones(self, *args):
            calls.append("configuration")
            return super().resolve_maximum_zones(*args)

    class RecordingRepository(ScheduleRepository):
        def save(self, schedule):
            calls.append("save")
            return super().save(schedule)

    service = ScheduleService(configuration_service=RecordingConfiguration(), repository=RecordingRepository())
    parser = service._schedule_validator.parse
    validator = service._schedule_validator.validate

    def record_parse(payload):
        calls.append("shape")
        return parser(payload)

    def record_validate(schedule, maximum_zones):
        calls.append("capacity")
        return validator(schedule, maximum_zones)

    monkeypatch.setattr(service._schedule_validator, "parse", record_parse)
    monkeypatch.setattr(service._schedule_validator, "validate", record_validate)
    controller = ScheduleController(service)
    response = controller.create({"controller_type": "PRO", "zones": [1, 2]})
    assert response.status_code == 201
    assert calls == ["shape", "configuration", "capacity", "save"]
    assert controller.get(response.body["schedule"]["id"]).body == response.body


def test_invalid_payload_stops_before_configuration_and_storage():
    class ForbiddenConfiguration(DeviceConfigurationService):
        def resolve_maximum_zones(self, *args):
            raise AssertionError("Malformed requests must not resolve controller capabilities")

    class ForbiddenRepository(ScheduleRepository):
        def save(self, schedule):
            raise AssertionError("Rejected requests must not persist")

    response = ScheduleController(ScheduleService(
        configuration_service=ForbiddenConfiguration(), repository=ForbiddenRepository(),
    )).create({"controller_type": [], "zones": [1]})
    assert response.status_code == 400
    assert response.body["error"]["code"] == "UNSUPPORTED_CONTROLLER"


def test_repository_instances_do_not_share_state():
    first = ScheduleController()
    created = first.create({"controller_type": "LEGACY", "zones": [1]})
    assert created.status_code == 201
    assert ScheduleController().get(created.body["schedule"]["id"]).status_code == 404
