"""Validate schedule request fields and controller capacity."""

from collections.abc import Mapping
from dataclasses import dataclass

from .controller_capabilities import CONTROLLER_LIMITS


class ScheduleValidationError(ValueError):
    def __init__(self, code: str, message: str, field: str):
        super().__init__(message)
        self.code = code
        self.field = field


@dataclass(frozen=True)
class ValidatedSchedule:
    controller_type: str
    zones: tuple[int, ...]
    name: str


def parse_schedule(payload: object) -> ValidatedSchedule:
    """Validate the JSON request shape before applying controller capabilities."""
    if not isinstance(payload, Mapping):
        raise ScheduleValidationError("INVALID_PAYLOAD", "Request must be a JSON object.", "body")

    controller_type = payload.get("controller_type")
    if not isinstance(controller_type, str) or controller_type not in CONTROLLER_LIMITS:
        raise ScheduleValidationError(
            "UNSUPPORTED_CONTROLLER", "Controller must be LEGACY or PRO.", "controller_type"
        )

    zones = payload.get("zones")
    if not isinstance(zones, list) or not zones:
        raise ScheduleValidationError(
            "INVALID_ZONES", "Zones must be a non-empty array of positive integer IDs.", "zones"
        )
    if any(type(zone) is not int or zone <= 0 for zone in zones):
        raise ScheduleValidationError(
            "INVALID_ZONES", "Zone IDs must be positive integers; booleans are invalid.", "zones"
        )
    if len(set(zones)) != len(zones):
        raise ScheduleValidationError("INVALID_ZONES", "Zone IDs must be unique.", "zones")

    name = payload.get("name", "Irrigation schedule")
    if not isinstance(name, str) or not name.strip():
        raise ScheduleValidationError("INVALID_NAME", "Schedule name must be a non-empty string.", "name")

    return ValidatedSchedule(controller_type, tuple(zones), name.strip())


def enforce_zone_limit(schedule: ValidatedSchedule, maximum_zones: int) -> ValidatedSchedule:
    if len(schedule.zones) > maximum_zones:
        raise ScheduleValidationError(
            "ZONE_LIMIT_EXCEEDED",
            f"{schedule.controller_type} controller supports at most {maximum_zones} zones.",
            "zones",
        )
    return schedule


class ScheduleValidator:
    def parse(self, payload: object) -> ValidatedSchedule:
        return parse_schedule(payload)

    def validate(self, schedule: ValidatedSchedule, maximum_zones: int) -> ValidatedSchedule:
        return enforce_zone_limit(schedule, maximum_zones)
