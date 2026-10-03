"""Battery, cubes, pose sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
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
            CozmoBattery(coord),
            CozmoVoltage(coord),
            CozmoCubes(coord),
            CozmoOrientation(coord),
            *[CozmoCubeBattery(coord, slot) for slot in (1, 2, 3)],
        ]
    )


class CozmoBattery(CozmoEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "battery")

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("battery_percent")


class CozmoVoltage(CozmoEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "battery_voltage")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("battery_voltage")


class CozmoCubes(CozmoEntity, SensorEntity):
    _attr_icon = "mdi:cube-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "cubes")

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        return int(data.get("cubes_available") or 0)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "connected": data.get("cubes_connected"),
            "cubes": data.get("cubes") or [],
        }


class CozmoCubeBattery(CozmoEntity, SensorEntity):
    """Cube radio battery level. The robot reports a small integer, not volts."""

    _attr_icon = "mdi:battery"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, slot: int) -> None:
        super().__init__(coordinator, f"cube_{slot}_battery")
        self._slot = slot
        self._attr_translation_key = None
        self._attr_name = f"Cube {slot} battery"

    def _row(self) -> dict | None:
        slots = (self.coordinator.data or {}).get("cube_slots") or []
        for row in slots:
            if row.get("slot") == self._slot and row.get("seen"):
                return row
        return None

    @property
    def available(self) -> bool:
        return super().available and self._row() is not None

    @property
    def native_value(self) -> int | None:
        row = self._row()
        if not row:
            return None
        return row.get("battery")

    @property
    def extra_state_attributes(self) -> dict:
        row = self._row() or {}
        return {
            "factory_id": row.get("factory_id"),
            "linked": row.get("connected"),
            "missed_packets": row.get("missed_packets"),
            "rssi": row.get("rssi"),
        }


class CozmoOrientation(CozmoEntity, SensorEntity):
    _attr_icon = "mdi:axis-arrow"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "orientation")

    @property
    def native_value(self) -> str | None:
        value = (self.coordinator.data or {}).get("orientation")
        return value.lower() if isinstance(value, str) else value
