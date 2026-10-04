"""Prepared reference state, kept outside the initial agent workspace."""

import re


def validate_zones(zones, device):
    """Return a validation error string, or None when the schedule is valid."""
    if not isinstance(device, dict) or not isinstance(device.get("model"), str) or device["model"] not in {"LEGACY", "PRO"}:
        return "Controller model metadata is missing or unrecognized"
    firmware = device.get("firmware")
    if not isinstance(firmware, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", firmware) is None:
        return "Controller firmware metadata must contain three numeric components"
    if not isinstance(zones, list) or not zones:
        return "Zones must be a nonempty list"
    if any(not isinstance(zone, int) or isinstance(zone, bool) or zone <= 0 for zone in zones):
        return "Zone IDs must be positive integers"
    if len(set(zones)) != len(zones):
        return "Zone IDs must be unique"
    try:
        version = tuple(int(component) for component in firmware.split("."))
    except ValueError:
        return "Controller firmware metadata cannot be parsed"
    maximum = 50 if device["model"] == "PRO" and version >= (3, 2, 0) else 20
    if len(zones) > maximum:
        return f"Controller supports at most {maximum} zones"
    return None
