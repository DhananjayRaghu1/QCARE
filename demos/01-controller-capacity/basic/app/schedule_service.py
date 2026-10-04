"""Coordinate schedule validation, controller capabilities and storage."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .device_configuration_service import DeviceConfigurationService
from .schedule_repository import ScheduleRepository
from .schedule_validator import ScheduleValidationError, ScheduleValidator, ValidatedSchedule


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"status_code": self.status_code, "body": self.body}


class ScheduleService:
    """POST /api/schedules semantics, suitable for a UI or an HTTP adapter.

    Failed requests never persist. A caller may inject a request validator.
    """

    def __init__(
        self,
        validator: Callable[[object], ValidatedSchedule] | None = None,
        configuration_service: DeviceConfigurationService | None = None,
        repository: ScheduleRepository | None = None,
    ):
        self._validator = validator
        self._schedule_validator = ScheduleValidator()
        self._configuration_service = configuration_service if configuration_service is not None else DeviceConfigurationService()
        self._repository = repository if repository is not None else ScheduleRepository()

    def create_schedule(self, payload: object) -> ApiResponse:
        try:
            if self._validator is not None:
                schedule = self._validator(payload)
            else:
                schedule = self._schedule_validator.parse(payload)
                maximum_zones = self._configuration_service.resolve_maximum_zones()
                schedule = self._schedule_validator.validate(schedule, maximum_zones)
        except ScheduleValidationError as error:
            return ApiResponse(
                400,
                {"error": {"code": error.code, "message": str(error), "field": error.field}},
            )

        stored = self._repository.save(schedule)
        return ApiResponse(201, {"schedule": stored})

    def get_schedule(self, schedule_id: str) -> ApiResponse:
        stored = self._repository.get(schedule_id)
        if stored is None:
            return ApiResponse(404, {"error": {"code": "NOT_FOUND", "message": "Schedule not found."}})
        return ApiResponse(200, {"schedule": stored})

    @property
    def schedule_count(self) -> int:
        return self._repository.count
