"""MyEPB integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyEPBClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_ON,
    CONF_PUBLIC_OUTAGES_ONLY,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES_ON,
    DEFAULT_API_BASE_URL,
    DOMAIN,
)
from .coordinator import MyEPBCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyEPB from a config entry."""

    async def _async_token_update(tokens: dict[str, str | None]) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: tokens.get(CONF_ACCESS_TOKEN),
                CONF_ACCESS_TOKEN_EXPIRES_ON: tokens.get(
                    CONF_ACCESS_TOKEN_EXPIRES_ON
                ),
                CONF_REFRESH_TOKEN: tokens.get(CONF_REFRESH_TOKEN),
                CONF_REFRESH_TOKEN_EXPIRES_ON: tokens.get(
                    CONF_REFRESH_TOKEN_EXPIRES_ON
                ),
            },
        )

    client = MyEPBClient(
        async_get_clientsession(hass),
        username=entry.data.get(CONF_USERNAME),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        access_token_expires_on=entry.data.get(CONF_ACCESS_TOKEN_EXPIRES_ON),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        refresh_token_expires_on=entry.data.get(CONF_REFRESH_TOKEN_EXPIRES_ON),
        base_url=entry.data.get("base_url", DEFAULT_API_BASE_URL),
        token_update_callback=_async_token_update,
    )
    coordinator = MyEPBCoordinator(
        hass,
        client,
        public_outages_only=entry.data.get(CONF_PUBLIC_OUTAGES_ONLY, False),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MyEPB config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
