"""Stop, wake, cancel animation."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
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
            CozmoActionButton(coord, "stop", "stop", "mdi:stop"),
            CozmoActionButton(coord, "wake", "wake", "mdi:weather-sunset-up"),
            CozmoActionButton(coord, "power_off", "power_off", "mdi:power"),
            CozmoActionButton(coord, "cancel_anim", "cancel_anim", "mdi:cancel"),
            CozmoActionButton(coord, "connect_cubes", "cubes_connect", "mdi:cube-scan"),
        ]
    )


class CozmoActionButton(CozmoEntity, ButtonEntity):
    def __init__(self, coordinator, key: str, cmd: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._cmd = cmd
        self._attr_icon = icon
        if key == "connect_cubes":
            self._attr_translation_key = None
            self._attr_name = "Link cubes"
        elif key == "power_off":
            self._attr_translation_key = None
            self._attr_name = "Power off"

    async def async_press(self) -> None:
        if self._cmd == "wake":
            await self.coordinator.async_command("wake")
            return
        await self.coordinator.async_command(self._cmd)
