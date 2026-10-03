"""Connected / charging / cliff / pickup / backpack button."""

from __future__ import annotations

import time

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CozmoEntity


async def async_setup_entry(  # NOSONAR S7503 Home Assistant calls platform setup as a coroutine
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord = entry.runtime_data
    async_add_entities(
        [
            CozmoConnected(coord),
            CozmoFlagSensor(coord, "charging", BinarySensorDeviceClass.BATTERY_CHARGING),
            CozmoFlagSensor(coord, "on_charger", BinarySensorDeviceClass.PLUG),
            CozmoFlagSensor(coord, "cliff", None, "mdi:alert"),
            CozmoFlagSensor(coord, "picked_up", None, "mdi:hand-back-right"),
            CozmoFlagSensor(coord, "moving", None, "mdi:robot-mower"),
            CozmoFlagSensor(coord, "button_pressed", BinarySensorDeviceClass.OCCUPANCY, "mdi:gesture-tap-button"),
            *[CozmoCubeTap(coord, slot) for slot in (1, 2, 3)],
        ]
    )


class CozmoConnected(CozmoEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.robot_connected()


class CozmoFlagSensor(CozmoEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        device_class: BinarySensorDeviceClass | None,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_device_class = device_class
        if icon:
            self._attr_icon = icon
        if key == "button_pressed":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get(self._key))


class CozmoCubeTap(CozmoEntity, BinarySensorEntity):
    """On for a few seconds after the cube is tapped."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator, slot: int) -> None:
        super().__init__(coordinator, f"cube_{slot}_tapped")
        self._slot = slot
        self._attr_translation_key = None
        self._attr_name = f"Cube {slot} tapped"
        self._attr_icon = "mdi:gesture-tap"

    def _row(self) -> dict | None:
        for row in (self.coordinator.data or {}).get("cube_slots") or []:
            if row.get("slot") == self._slot and row.get("seen"):
                return row
        return None

    @property
    def available(self) -> bool:
        return super().available and self._row() is not None

    @property
    def is_on(self) -> bool:
        row = self._row() or {}
        last = row.get("last_tap") or 0
        return bool(last) and (time.time() - float(last)) < 12

    @property
    def extra_state_attributes(self) -> dict:
        row = self._row() or {}
        return {"taps": row.get("taps"), "last_tap": row.get("last_tap"), "factory_id": row.get("factory_id")}
