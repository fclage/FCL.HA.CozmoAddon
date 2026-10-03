"""Speaker + volume. TTS hook: play_media of WAV/MP3 (companion transcodes).

PyCozmo has no text-to-speech. Client.play_audio() plays 22 kHz 16-bit mono WAV.
Point HA TTS at this media_player; the companion runs ffmpeg when needed.
"""

from __future__ import annotations

import aiohttp

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CozmoEntity


async def async_setup_entry(  # NOSONAR S7503 Home Assistant calls platform setup as a coroutine
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([CozmoSpeaker(entry.runtime_data)])


class CozmoSpeaker(CozmoEntity, MediaPlayerEntity):
    _attr_icon = "mdi:speaker"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "speaker")

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data or {}
        if data.get("animating"):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        vol = (self.coordinator.data or {}).get("volume")
        if vol is None:
            return None
        return max(0.0, min(1.0, float(vol) / 100.0))

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_command("volume", level=int(volume * 100))

    async def async_media_stop(self) -> None:
        await self.coordinator.async_command("cancel_anim")

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs,
    ) -> None:
        del media_type, kwargs
        session = self.coordinator.api._session  # noqa: SLF001
        async with session.get(media_id, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            payload = await resp.read()
            ctype = resp.content_type or "application/octet-stream"
        await self.coordinator.api.play_audio_bytes(payload, ctype)
        await self.coordinator.async_request_refresh()
