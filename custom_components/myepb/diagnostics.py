"""Diagnostics support for MyEPB."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_ON,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES_ON,
    DOMAIN,
)

REDACTED = "**REDACTED**"

SENSITIVE_KEYS = {
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_ON,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES_ON,
    CONF_USERNAME,
    "access",
    "account_holder_display_name",
    "account_id",
    "account_number",
    "billing_address",
    "customer",
    "display_name",
    "email",
    "email_address",
    "expires_on",
    "first_name",
    "full_service_address",
    "gis_id",
    "initials",
    "label",
    "label_with_unit",
    "last_name",
    "location_label",
    "nickname",
    "phone",
    "phone_number",
    "premise",
    "premise_id",
    "refresh",
    "token",
    "unit_number",
    "username",
    "zip",
    "zip_code",
    "zone_id",
}

SENSITIVE_KEY_MARKERS = (
    "account",
    "address",
    "email",
    "gis",
    "name",
    "phone",
    "premise",
    "token",
    "unit",
    "zip",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    data: dict[str, Any] = {
        "entry": _redact_data(dict(entry.data)),
    }

    if coordinator and coordinator.data:
        data["account_count"] = len(coordinator.data.get("power_accounts", {}))
        data["location_count"] = len(coordinator.data.get("locations", []))
        data["locations"] = _redact_data(coordinator.data.get("locations", []))
        data["outage_summaries"] = _redact_data(
            {
                outage_type: payload.get("summary", {})
                for outage_type, payload in coordinator.data.get("outages", {}).items()
                if isinstance(payload, dict)
            }
        )

    return data


def _redact_data(value: Any, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            item_key: _redact_data(item_value, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_data(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_KEYS or any(
        marker in lowered for marker in SENSITIVE_KEY_MARKERS
    )
