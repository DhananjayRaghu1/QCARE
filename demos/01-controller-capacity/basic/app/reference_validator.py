"""Prepared reference fix for deterministic replay; never enabled implicitly.

A live coding-agent run should modify schedule_validator.py and add regression
coverage. This reference is a labeled rehearsal/fallback, not an agent output.
"""

from .controller_capabilities import CONTROLLER_LIMITS
from .schedule_validator import ValidatedSchedule, enforce_zone_limit, parse_schedule


def validate_schedule(payload: object) -> ValidatedSchedule:
    schedule = parse_schedule(payload)
    maximum_zones = CONTROLLER_LIMITS[schedule.controller_type]
    return enforce_zone_limit(schedule, maximum_zones)
