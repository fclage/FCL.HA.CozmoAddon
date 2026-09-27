"""Diagnostics for the Cozmo integration (no secrets)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN

TO_REDACT = {CONF_PASSWORD, CONF_TOKEN, "password", "token", "psk"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    status = dict(coordinator.data or {})
    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "status": async_redact_data(status, TO_REDACT),
        "anims": list(coordinator.anims),
        "companion_url": coordinator.api.url,
        "last_update_success": coordinator.last_update_success,
    }
