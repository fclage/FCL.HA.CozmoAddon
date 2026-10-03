"""Home Assistant integration for Anki Cozmo via the hacozmo companion."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ANGLE,
    ATTR_DURATION,
    ATTR_EXPRESSION,
    ATTR_HEIGHT,
    ATTR_LEFT,
    ATTR_MEDIA,
    ATTR_NAME,
    ATTR_RIGHT,
    DOMAIN,
    PLATFORMS,
    SERVICE_DRIVE,
    SERVICE_PLAY_ANIM,
    SERVICE_PLAY_AUDIO,
    SERVICE_SET_FACE,
    SERVICE_SET_HEAD,
    SERVICE_SET_LIFT,
    SERVICE_PLAY,
    SERVICE_SPEAK,
    SERVICE_STOP,
    SERVICE_WIFI_JOIN,
    ATTR_TEXT,
    ATTR_PHRASE,
)
from .coordinator import CozmoCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(_hass: HomeAssistant, _config: ConfigType) -> bool:  # NOSONAR S7503 Home Assistant calls this as a coroutine
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = CozmoCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    if coordinator.ssid and coordinator.wifi_iface:
        hass.async_create_task(
            _async_join_wifi(coordinator),
            name="ha_cozmo_wifi_join",
        )
    return True


async def _async_join_wifi(coordinator: CozmoCoordinator) -> None:
    try:
        await coordinator.api.wifi_join(
            coordinator.ssid,
            coordinator.wifi_password,
            coordinator.wifi_iface,
        )
    except Exception as exc:  # noqa: BLE001 — companion logs the real failure
        _LOGGER.warning("Cozmo Wi-Fi join failed: %s", exc)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinators(hass: HomeAssistant) -> list[CozmoCoordinator]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]


def _pick(hass: HomeAssistant, call: ServiceCall) -> CozmoCoordinator:
    coords = _coordinators(hass)
    if not coords:
        raise ValueError("No Cozmo configured")
    target = call.data.get("url")
    if target:
        for coord in coords:
            if coord.api.url.rstrip("/") == str(target).rstrip("/"):
                return coord
    return coords[0]


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_DRIVE):
        return

    async def handle_drive(call: ServiceCall) -> None:
        await _pick(hass, call).async_command(
            "drive",
            left=call.data.get(ATTR_LEFT, 0),
            right=call.data.get(ATTR_RIGHT, 0),
            duration=call.data.get(ATTR_DURATION, 0.5),
        )

    async def handle_anim(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("anim", name=call.data[ATTR_NAME])

    async def handle_face(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("face", expression=call.data[ATTR_EXPRESSION])

    async def handle_stop(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("stop")

    async def handle_audio(call: ServiceCall) -> None:
        coord = _pick(hass, call)
        url = call.data[ATTR_MEDIA]
        import aiohttp

        session = coord.api._session  # noqa: SLF001 — same HA session
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            payload = await resp.read()
            ctype = resp.content_type or "application/octet-stream"
        await coord.api.play_audio_bytes(payload, ctype)

    async def handle_head(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("head", angle=call.data[ATTR_ANGLE])

    async def handle_lift(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("lift", height=call.data[ATTR_HEIGHT])

    async def handle_wifi(call: ServiceCall) -> None:
        coord = _pick(hass, call)
        await coord.api.wifi_join(
            call.data.get("ssid") or coord.ssid,
            call.data.get("password", coord.wifi_password),
            call.data.get("iface") or coord.wifi_iface,
        )

    async def handle_play(call: ServiceCall) -> None:
        await _pick(hass, call).async_command("play_command", name=call.data[ATTR_NAME])

    async def handle_speak(call: ServiceCall) -> None:
        await _pick(hass, call).async_command(
            "speak",
            text=call.data.get(ATTR_TEXT, ""),
            phrase_id=call.data.get(ATTR_PHRASE, ""),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DRIVE,
        handle_drive,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_LEFT, default=50): vol.Coerce(float),
                vol.Optional(ATTR_RIGHT, default=50): vol.Coerce(float),
                vol.Optional(ATTR_DURATION, default=0.5): vol.Coerce(float),
                vol.Optional(CONF_URL): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_ANIM,
        handle_anim,
        schema=vol.Schema(
            {vol.Required(ATTR_NAME): cv.string, vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FACE,
        handle_face,
        schema=vol.Schema(
            {vol.Required(ATTR_EXPRESSION): cv.string, vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        handle_stop,
        schema=vol.Schema({vol.Optional(CONF_URL): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_AUDIO,
        handle_audio,
        schema=vol.Schema(
            {vol.Required(ATTR_MEDIA): cv.url, vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEAD,
        handle_head,
        schema=vol.Schema(
            {vol.Required(ATTR_ANGLE): vol.Coerce(float), vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LIFT,
        handle_lift,
        schema=vol.Schema(
            {vol.Required(ATTR_HEIGHT): vol.Coerce(float), vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY,
        handle_play,
        schema=vol.Schema(
            {vol.Required(ATTR_NAME): cv.string, vol.Optional(CONF_URL): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SPEAK,
        handle_speak,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_TEXT): cv.string,
                vol.Optional(ATTR_PHRASE): cv.string,
                vol.Optional(CONF_URL): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WIFI_JOIN,
        handle_wifi,
        schema=vol.Schema(
            {
                vol.Optional("ssid"): cv.string,
                vol.Optional("password"): cv.string,
                vol.Optional(CONF_URL): cv.string,
            }
        ),
    )
