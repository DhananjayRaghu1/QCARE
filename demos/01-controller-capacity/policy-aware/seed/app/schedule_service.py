"""Registry lookup, validation, and persistence for schedule creation."""

import copy

from .api import ApiResponse
from .device_registry import DeviceRegistry
from .schedule_validator import validate_zones


class ScheduleService:
    def __init__(self, registry=None):
        self.registry = registry if registry is not None else DeviceRegistry()
        self._schedules = {}
        self._next_id = 1

    def create_schedule(self, payload):
        if not isinstance(payload, dict):
            return self._invalid("Request must be an object")
        if set(payload) != {"controller_id", "zones"}:
            return self._invalid("Request must contain only controller_id and zones")
        controller_id = payload["controller_id"]
        if not isinstance(controller_id, str) or not controller_id.strip():
            return self._invalid("Controller ID must be a nonempty string")
        device = self.registry.get(controller_id)
        if device is None:
            return ApiResponse(404, {"error": "Controller was not found", "code": "controller_not_found"})
        error = validate_zones(payload["zones"], device)
        if error is not None:
            code = "zone_limit_exceeded" if error.startswith("Controller supports at most ") else "validation_error"
            return self._invalid(error, code)
        schedule_id = f"SCH-{self._next_id:04d}"
        schedule = {"id": schedule_id, "controller_id": controller_id, "zones": copy.deepcopy(payload["zones"])}
        self._schedules[schedule_id] = copy.deepcopy(schedule)
        self._next_id += 1
        return ApiResponse(201, copy.deepcopy(schedule))

    def get_schedule(self, schedule_id):
        schedule = self._schedules.get(schedule_id)
        return copy.deepcopy(schedule) if schedule is not None else None

    @staticmethod
    def _invalid(message, code="validation_error"):
        return ApiResponse(400, {"error": message, "code": code})
