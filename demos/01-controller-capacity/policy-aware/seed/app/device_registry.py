"""Device configuration owned by the registry, rather than schedule requests."""

import copy
import json
from pathlib import Path


class DeviceRegistry:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(__file__).with_name("devices.json")
        records = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(records, dict):
            raise ValueError("Device registry must be an object keyed by controller ID")
        self._records = records

    def get(self, controller_id):
        record = self._records.get(controller_id)
        return copy.deepcopy(record) if record is not None else None
