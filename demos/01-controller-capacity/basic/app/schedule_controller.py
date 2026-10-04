"""Transport adapter for POST and GET /api/schedules."""

from .schedule_service import ApiResponse, ScheduleService


class ScheduleController:
    def __init__(self, service: ScheduleService | None = None):
        self._service = service if service is not None else ScheduleService()

    def create(self, payload: object) -> ApiResponse:
        return self._service.create_schedule(payload)

    def get(self, schedule_id: str) -> ApiResponse:
        return self._service.get_schedule(schedule_id)
