"""IR headlight and a small idle-blink personality loop."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
        [CozmoHeadLight(coord), CozmoPersonality(coord), CozmoAuto(coord), CozmoAutoSleep(coord)]
    )


class CozmoHeadLight(CozmoEntity, SwitchEntity):
    _attr_icon = "mdi:spotlight-beam"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "head_light")

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("head_light"))

    async def async_turn_on(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("head_light", on=True)

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("head_light", on=False)


class CozmoPersonality(CozmoEntity, SwitchEntity):
    _attr_icon = "mdi:heart"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "personality")

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("personality"))

    async def async_turn_on(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("personality", enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("personality", enabled=False)


class CozmoAuto(CozmoEntity, SwitchEntity):
    """After 30s idle, small moves and play. Faces stay on when this is off."""

    _attr_icon = "mdi:robot-excited"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "auto")

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("auto"))

    async def async_turn_on(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("auto", enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("auto", enabled=False)


class CozmoAutoSleep(CozmoEntity, SwitchEntity):
    """Power Cozmo off after 5 minutes without a tap, including on the charger."""

    _attr_icon = "mdi:sleep"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "auto_sleep")
        self._attr_translation_key = None
        self._attr_name = "Auto-sleep"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("auto_sleep"))

    async def async_turn_on(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("auto_sleep", enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("auto_sleep", enabled=False)
