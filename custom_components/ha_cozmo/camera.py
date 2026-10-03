"""Last JPEG from Cozmo's camera (pycozmo EvtNewRawCameraImage)."""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CozmoEntity


async def async_setup_entry(  # NOSONAR S7503 Home Assistant calls platform setup as a coroutine
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CozmoCamera(entry.runtime_data)])


class CozmoCamera(CozmoEntity, Camera):
    _attr_translation_key = "camera"
    _attr_supported_features = CameraEntityFeature(0)

    def __init__(self, coordinator) -> None:
        Camera.__init__(self)
        CozmoEntity.__init__(self, coordinator, "camera")
        self._attr_name = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        del width, height
        return await self.coordinator.api.camera_jpeg()
