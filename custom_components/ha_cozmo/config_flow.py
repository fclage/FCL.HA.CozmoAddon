"""UI config flow: companion URL + Cozmo AP credentials."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.config_entries import ConfigFlowResult as FlowResult
except ImportError:  # HA < 2024.4
    from homeassistant.data_entry_flow import FlowResult  # type: ignore[assignment]

from .api import CompanionAuthError, CompanionError, CozmoCompanion
from .const import (
    CONF_FROM_ADDON,
    CONF_SSID,
    CONF_TOKEN,
    CONF_WIFI_DEVICE,
    DEFAULT_ADDON_URL,
    DEFAULT_NAME,
    DEFAULT_SSID,
    DEFAULT_URL,
    DOMAIN,
)

try:
    from homeassistant.helpers.service_info.hassio import HassioServiceInfo
except ImportError:  # pragma: no cover - older HA
    HassioServiceInfo = None  # type: ignore[misc, assignment]


async def _validate(hass: HomeAssistant, url: str, token: str | None) -> None:
    api = CozmoCompanion(async_get_clientsession(hass), url, token)
    await api.health()


def _schema(defaults: dict[str, Any] | None = None, *, advanced: bool = False) -> vol.Schema:
    defaults = defaults or {}
    fields: dict[Any, Any] = {
        vol.Required(CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL)): str,
        vol.Required(
            CONF_WIFI_DEVICE, default=defaults.get(CONF_WIFI_DEVICE, "")
        ): str,
        vol.Required(CONF_SSID, default=defaults.get(CONF_SSID, DEFAULT_SSID)): str,
        vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
    }
    if advanced:
        fields[vol.Required(CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL))] = str
        fields[vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))] = str
        fields[vol.Optional(CONF_TOKEN, default=defaults.get(CONF_TOKEN, ""))] = str
    return vol.Schema(fields)


class CozmoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_hassio(self, discovery_info: Any) -> FlowResult:
        """Discovered the hacozmo App (Supervisor)."""
        config = getattr(discovery_info, "config", None) or {}
        if isinstance(discovery_info, dict):
            config = discovery_info.get("config") or discovery_info
        host = config.get("host") or "172.30.32.1"
        port = int(config.get("port") or 8790)
        url = f"http://{host}:{port}".rstrip("/")
        await self.async_set_unique_id(url.lower())
        self._abort_if_unique_id_configured()
        try:
            await _validate(self.hass, url, None)
        except CompanionError:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={
                CONF_URL: url,
                CONF_NAME: DEFAULT_NAME,
                CONF_SSID: "",
                CONF_PASSWORD: "",
                CONF_TOKEN: "",
                CONF_FROM_ADDON: True,
            },
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = (user_input.get(CONF_URL) or DEFAULT_URL).strip().rstrip("/")
            user_input[CONF_URL] = url
            user_input.setdefault(CONF_TOKEN, "")
            try:
                await _validate(self.hass, url, user_input.get(CONF_TOKEN) or None)
            except CompanionAuthError:
                errors["base"] = "invalid_auth"
            except CompanionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                ssid = user_input[CONF_SSID].strip()
                user_input[CONF_SSID] = ssid
                user_input[CONF_WIFI_DEVICE] = user_input[CONF_WIFI_DEVICE].strip()
                user_input[CONF_NAME] = DEFAULT_NAME
                await self.async_set_unique_id(ssid.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
        defaults = dict(user_input or {})
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> CozmoOptionsFlow:
        return CozmoOptionsFlow()


class CozmoOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            user_input[CONF_URL] = url
            try:
                await _validate(self.hass, url, user_input.get(CONF_TOKEN) or None)
            except CompanionAuthError:
                errors["base"] = "invalid_auth"
            except CompanionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                user_input[CONF_SSID] = user_input[CONF_SSID].strip()
                user_input[CONF_WIFI_DEVICE] = user_input[CONF_WIFI_DEVICE].strip()
                user_input.setdefault(CONF_NAME, current.get(CONF_NAME) or DEFAULT_NAME)
                user_input.setdefault(CONF_TOKEN, current.get(CONF_TOKEN) or "")
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current, advanced=True),
            errors=errors,
        )
