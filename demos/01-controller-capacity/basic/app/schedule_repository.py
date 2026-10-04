"""Per-instance, in-memory schedule storage."""

from typing import Any

from .schedule_validator import ValidatedSchedule


class ScheduleRepository:
    def __init__(self):
        self._schedules: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _copy(stored: dict[str, Any]) -> dict[str, Any]:
        return {**stored, "zones": list(stored["zones"])}

    def save(self, schedule: ValidatedSchedule) -> dict[str, Any]:
        schedule_id = f"SCHEDULE-{len(self._schedules) + 1:03d}"
        stored = {
            "id": schedule_id,
            "name": schedule.name,
            "controller_type": schedule.controller_type,
            "zones": list(schedule.zones),
            "zone_count": len(schedule.zones),
        }
        self._schedules[schedule_id] = stored
        return self._copy(stored)

    def get(self, schedule_id: str) -> dict[str, Any] | None:
        stored = self._schedules.get(schedule_id)
        return None if stored is None else self._copy(stored)

    @property
    def count(self) -> int:
        return len(self._schedules)
