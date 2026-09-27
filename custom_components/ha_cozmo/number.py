"""Head angle, lift height, volume."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CozmoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord = entry.runtime_data
    async_add_entities(
        [
            CozmoHead(coord),
            CozmoLift(coord),
            CozmoVolume(coord),
        ]
    )


class CozmoHead(CozmoEntity, NumberEntity):
    _attr_icon = "mdi:head"
    _attr_native_min_value = -25.0
    _attr_native_max_value = 44.5
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "head_angle")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("head_angle")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command("head", angle=value)


class CozmoLift(CozmoEntity, NumberEntity):
    _attr_icon = "mdi:arrow-up-down"
    _attr_native_min_value = 32.0
    _attr_native_max_value = 92.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "lift_height")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("lift_height_mm")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command("lift", height=value)


class CozmoVolume(CozmoEntity, NumberEntity):
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "volume")

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("volume")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command("volume", level=int(value))
