"""Face (pycozmo.expressions) and animation select entities."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FACE_OPTIONS
from .entity import CozmoEntity


async def async_setup_entry(  # NOSONAR S7503 Home Assistant calls platform setup as a coroutine
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord = entry.runtime_data
    async_add_entities([CozmoFaceSelect(coord), CozmoAnimSelect(coord)])


class CozmoFaceSelect(CozmoEntity, SelectEntity):
    _attr_icon = "mdi:emoticon-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "face")
        self._attr_options = list(FACE_OPTIONS)

    @property
    def current_option(self) -> str | None:
        return (self.coordinator.data or {}).get("face") or "neutral"

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_command("face", expression=option)


class CozmoAnimSelect(CozmoEntity, SelectEntity):
    _attr_icon = "mdi:animation-play"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "animation")

    @property
    def options(self) -> list[str]:
        names = list(self.coordinator.anims)
        return names or ["anim_launch_wakeup_01"]

    @property
    def current_option(self) -> str | None:
        last = (self.coordinator.data or {}).get("last_anim")
        if last in self.options:
            return last
        return self.options[0]

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data or {}
        # Groups come from play_anim_group; clips from play_anim.
        if data.get("anims_loaded"):
            await self.coordinator.async_command("anim_group", name=option)
        else:
            await self.coordinator.async_command("anim", name=option)
