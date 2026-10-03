"""Backpack RGB LEDs via pycozmo.set_all_backpack_lights."""

from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CozmoEntity


async def async_setup_entry(  # NOSONAR S7503 Home Assistant calls platform setup as a coroutine
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coord = entry.runtime_data
    async_add_entities(
        [CozmoBackpackLight(coord)]
        + [CozmoCubeLed(coord, slot, index) for slot in (1, 2, 3) for index in range(4)]
    )


class CozmoBackpackLight(CozmoEntity, LightEntity):
    _attr_icon = "mdi:led-strip"
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "backpack")
        self._brightness = 255
        self._rgb = (255, 80, 0)

    @property
    def is_on(self) -> bool:
        pack = (self.coordinator.data or {}).get("backpack") or {}
        return bool(pack.get("on"))

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        pack = (self.coordinator.data or {}).get("backpack") or {}
        rgb = pack.get("rgb") or list(self._rgb)
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    async def async_turn_on(self, **kwargs) -> None:
        if (rgb := kwargs.get("rgb_color")) is not None:
            self._rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        if (bri := kwargs.get("brightness")) is not None:
            self._brightness = int(bri)
        await self.coordinator.async_command(
            "backpack", rgb=list(self._rgb), brightness=self._brightness
        )

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command("backpack_off")


class CozmoCubeLed(CozmoEntity, LightEntity):
    """One of the four corner LEDs on a light cube."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator, slot: int, index: int) -> None:
        super().__init__(coordinator, f"cube_{slot}_led_{index + 1}")
        self._slot = slot
        self._index = index
        self._attr_translation_key = None
        self._attr_name = f"Cube {slot} LED {index + 1}"
        self._attr_icon = "mdi:led-on"

    def _row(self) -> dict | None:
        for row in (self.coordinator.data or {}).get("cube_slots") or []:
            if row.get("slot") == self._slot and row.get("connected"):
                return row
        return None

    @property
    def available(self) -> bool:
        return super().available and self._row() is not None

    @property
    def is_on(self) -> bool:
        row = self._row() or {}
        leds = row.get("leds") or []
        index = self._index
        if 0 <= index < len(leds):
            return bool(leds[index])
        return False

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        row = self._row() or {}
        leds = row.get("leds") or []
        index = self._index
        if 0 <= index < len(leds):
            color = leds[index]
            if isinstance(color, (list, tuple)) and len(color) >= 3:
                return (int(color[0]), int(color[1]), int(color[2]))
        return None

    async def async_turn_on(self, **kwargs) -> None:
        rgb = kwargs.get("rgb_color") or (255, 180, 40)
        await self.coordinator.async_command(
            "cube_led",
            slot=self._slot,
            index=self._index,
            rgb=[int(rgb[0]), int(rgb[1]), int(rgb[2])],
            on=True,
        )

    async def async_turn_off(self, **kwargs) -> None:
        del kwargs
        await self.coordinator.async_command(
            "cube_led", slot=self._slot, index=self._index, on=False
        )
