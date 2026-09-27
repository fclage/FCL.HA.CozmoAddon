"""Poll the Cozmo companion."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CompanionAuthError, CompanionError, CozmoCompanion
from .const import (
    CONF_SSID,
    CONF_TOKEN,
    CONF_WIFI_DEVICE,
    DEFAULT_NAME,
    DOMAIN,
    FALLBACK_ANIMS,
)

_LOGGER = logging.getLogger(__name__)


class CozmoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title or DEFAULT_NAME,
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        data = {**entry.data, **entry.options}
        self.api = CozmoCompanion(
            async_get_clientsession(hass),
            data.get(CONF_URL, ""),
            data.get(CONF_TOKEN) or None,
        )
        self.anims: list[str] = list(FALLBACK_ANIMS)

    @property
    def robot_name(self) -> str:
        return self.entry.data.get(CONF_NAME) or self.entry.title or DEFAULT_NAME

    @property
    def ssid(self) -> str:
        data = {**self.entry.data, **self.entry.options}
        return data.get(CONF_SSID) or ""

    @property
    def wifi_password(self) -> str:
        data = {**self.entry.data, **self.entry.options}
        return data.get(CONF_PASSWORD) or ""

    @property
    def wifi_iface(self) -> str:
        data = {**self.entry.data, **self.entry.options}
        return data.get(CONF_WIFI_DEVICE) or ""

    @property
    def device_info(self) -> DeviceInfo:
        status = self.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.robot_name,
            manufacturer="Anki / Digital Dream Labs",
            model="Cozmo",
            sw_version=status.get("firmware"),
            serial_number=status.get("serial"),
            configuration_url=self.api.url,
        )

    def robot_connected(self) -> bool:
        return bool((self.data or {}).get("robot_connected"))

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.status()
        except CompanionAuthError as exc:
            raise UpdateFailed(str(exc)) from exc
        except CompanionError as exc:
            raise UpdateFailed(str(exc)) from exc
        try:
            anims = await self.api.anims()
            options = anims.get("select") or anims.get("groups") or anims.get("clips") or []
            if options:
                self.anims = [str(x) for x in options]
        except CompanionError:
            pass
        return status

    async def async_command(self, cmd: str, **kwargs: Any) -> None:
        await self.api.command(cmd, **kwargs)
        await self.async_request_refresh()
