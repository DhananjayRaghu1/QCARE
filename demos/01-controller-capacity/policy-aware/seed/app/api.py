"""Small API adapter; no web server is required to exercise the service."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: dict[str, Any]


def create_schedule(payload: Any, service=None) -> ApiResponse:
    from .schedule_service import ScheduleService

    return (service if service is not None else ScheduleService()).create_schedule(payload)
