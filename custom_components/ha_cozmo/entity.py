"""Shared entity base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CozmoCoordinator


class CozmoEntity(CoordinatorEntity[CozmoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: CozmoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        # Wake, Auto, and Auto-sleep live in the companion. They must stay
        # usable after the robot itself has powered off.
        if self._key in {"connected", "companion", "wake", "auto", "auto_sleep"}:
            return self.coordinator.last_update_success
        return self.coordinator.last_update_success and self.coordinator.robot_connected()

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._key != "connected":
            return None
        data = self.coordinator.data or {}
        return {
            "companion_url": self.coordinator.api.url,
            "ssid": self.coordinator.ssid,
            "domain": DOMAIN,
            "last_error": data.get("last_error"),
            "dry_run": data.get("dry_run"),
            "mood": data.get("mood"),
            "face": data.get("face"),
            "firmware": data.get("firmware"),
        }
