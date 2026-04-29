"""Diagnostics support for MyEPB."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    "account_number",
    "billing_address",
    "email",
    "email_address",
    "first_name",
    "full_service_address",
    "gis_id",
    "last_name",
    "location_label",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    data: dict[str, Any] = {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
    }

    if coordinator and coordinator.data:
        data["account_count"] = len(coordinator.data.get("power_accounts", {}))
        data["locations"] = async_redact_data(
            coordinator.data.get("locations", []), TO_REDACT
        )

    return data
