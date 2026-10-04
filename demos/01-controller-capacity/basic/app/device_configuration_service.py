"""Resolve scheduling capabilities for a controller family."""

from .controller_capabilities import CONTROLLER_LIMITS


class DeviceConfigurationService:
    def resolve_maximum_zones(self, controller_type: str = "LEGACY") -> int:
        """Use Legacy capabilities when a caller does not select a family."""
        return CONTROLLER_LIMITS[controller_type]
