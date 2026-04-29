"""Config flow for MyEPB."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MyEPBAuthError, MyEPBClient, MyEPBError
from .const import CONF_PUBLIC_OUTAGES_ONLY, DEFAULT_API_BASE_URL, DOMAIN

PUBLIC_OUTAGES_UNIQUE_ID = f"{DOMAIN}_public_outages"
USERNAME_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
)
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)


class MyEPBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a MyEPB config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            if not username and not password:
                await self.async_set_unique_id(PUBLIC_OUTAGES_UNIQUE_ID)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="EPB Public Outages",
                    data={CONF_PUBLIC_OUTAGES_ONLY: True},
                )

            if not username or not password:
                errors["base"] = "missing_credentials"
                return self._show_user_form(errors)

            result = await self._async_authenticate(
                {CONF_USERNAME: username, CONF_PASSWORD: password}
            )
            if isinstance(result, dict):
                await self.async_set_unique_id(_username_unique_id(username))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="MyEPB", data=result)
            errors["base"] = result

        return self._show_user_form(errors)

    def _show_user_form(
        self, errors: dict[str, str]
    ) -> config_entries.FlowResult:
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): USERNAME_SELECTOR,
                    vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.FlowResult:
        """Handle reauthentication."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Confirm reauthentication with a new password."""

        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            auth_input = {
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            result = await self._async_authenticate(auth_input)
            if isinstance(result, dict):
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, **result},
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")
            errors["base"] = result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            errors=errors,
        )

    async def _async_authenticate(
        self, user_input: dict[str, Any]
    ) -> dict[str, Any] | str:
        client = MyEPBClient(
            async_get_clientsession(self.hass),
            base_url=DEFAULT_API_BASE_URL,
        )
        try:
            await client.authenticate(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            await client.validate_authentication()
        except MyEPBAuthError:
            return "invalid_auth"
        except MyEPBError:
            return "cannot_connect"

        return {
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PUBLIC_OUTAGES_ONLY: False,
            **client.tokens,
        }


def _username_unique_id(username: str) -> str:
    normalized = username.strip().lower().encode()
    return f"{DOMAIN}_{hashlib.sha256(normalized).hexdigest()[:16]}"
