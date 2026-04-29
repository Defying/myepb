"""Client for the MyEPB web API used by epb.com."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_EXPIRES_ON,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES_ON,
    DEFAULT_API_BASE_URL,
)

TokenUpdateCallback = Callable[[dict[str, str | None]], Awaitable[None]]

AUTH_ERROR_CODES = {
    "INVALID_LOGIN",
    "INVALID_TOKEN",
    "MISSING_REQUIRED_CREDENTIALS",
    "REFRESH_DENIED",
    "REFRESH_EXPIRED",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")
REDACTED_TEXT = "redacted"


class MyEPBError(Exception):
    """Base MyEPB exception."""


class MyEPBAuthError(MyEPBError):
    """Authentication failed."""


class MyEPBApiError(MyEPBError):
    """MyEPB API request failed."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_code: str | None = None,
        reference_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.reference_id = reference_id


class MyEPBClient:
    """Small async client for MyEPB's web API."""

    def __init__(
        self,
        session: ClientSession,
        *,
        username: str | None = None,
        access_token: str | None = None,
        access_token_expires_on: str | None = None,
        refresh_token: str | None = None,
        refresh_token_expires_on: str | None = None,
        base_url: str = DEFAULT_API_BASE_URL,
        token_update_callback: TokenUpdateCallback | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._access_token = access_token
        self._access_token_expires_on = access_token_expires_on
        self._refresh_token = refresh_token
        self._refresh_token_expires_on = refresh_token_expires_on
        self._base_url = base_url.rstrip("/")
        self._token_update_callback = token_update_callback

    @property
    def tokens(self) -> dict[str, str | None]:
        """Return current token fields for persistence."""

        return {
            CONF_ACCESS_TOKEN: self._access_token,
            CONF_ACCESS_TOKEN_EXPIRES_ON: self._access_token_expires_on,
            CONF_REFRESH_TOKEN: self._refresh_token,
            CONF_REFRESH_TOKEN_EXPIRES_ON: self._refresh_token_expires_on,
        }

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with username/password."""

        response = await self._request(
            "POST",
            "/web/api/v1/login/",
            json={
                "grant_type": "PASSWORD",
                "username": username,
                "password": password,
            },
            allow_refresh=False,
        )
        self._username = username
        await self._persist_auth_response(response)
        return response

    async def validate_authentication(self) -> None:
        """Verify current credentials by loading portal locations."""

        await self.async_get_locations()

    async def async_get_locations(self) -> list[dict[str, Any]]:
        """Return portal locations linked to the MyEPB profile."""

        return await self._request("GET", "/web/api/v1/locations/portal", auth=True)

    async def async_get_account_links(self) -> list[dict[str, Any]]:
        """Return account links for the MyEPB profile."""

        return await self._request("GET", "/web/api/v1/account-links/", auth=True)

    async def async_get_power_accounts(
        self, account_numbers: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return linked power account details."""

        if account_numbers:
            return await self._request(
                "POST",
                "/web/api/v1/accounts/power",
                auth=True,
                json=account_numbers,
            )
        return await self._request("GET", "/web/api/v1/accounts/power", auth=True)

    async def async_get_current_cycle_power_usage(
        self, account_number: str, gis_id: str, zone_id: str
    ) -> dict[str, Any]:
        """Return current-cycle power usage."""

        return await self._request(
            "POST",
            "/web/api/v1/usage/power/permanent/cycle",
            auth=True,
            json={
                "account_number": account_number,
                "gis_id": gis_id,
                "zone_id": zone_id,
            },
        )

    async def async_compare_power_usage(
        self,
        period: str,
        account_number: str,
        gis_id: str,
        zone_id: str,
        **date_fields: str | int,
    ) -> dict[str, Any]:
        """Return hourly, daily, or monthly comparison usage data."""

        if period not in {"hourly", "daily", "monthly"}:
            raise ValueError(f"Unsupported usage period: {period}")
        return await self._request(
            "POST",
            f"/web/api/v1/usage/power/permanent/compare/{period}",
            auth=True,
            json={
                "account_number": account_number,
                "gis_id": gis_id,
                "zone_id": zone_id,
                **date_fields,
            },
        )

    async def async_get_power_bill_summary(
        self, account_number: str
    ) -> dict[str, Any]:
        """Return current power bill summary."""

        return await self._request(
            "GET",
            f"/web/api/v1/bills/summary/power/{account_number}",
            auth=True,
        )

    async def async_get_power_prepay_summary(
        self, account_number: str
    ) -> dict[str, Any]:
        """Return current PrePay Power summary."""

        return await self._request(
            "GET",
            f"/web/api/v1/bills/summary/power/prepay/{account_number}",
            auth=True,
        )

    async def async_get_energy_outage_incidents(self) -> dict[str, Any]:
        """Return public current energy outage incidents."""

        return await self._request("GET", "/web/api/v2/outages/energy/incidents")

    async def async_get_energy_outage_restores(self) -> dict[str, Any]:
        """Return public energy restores from the outage map window."""

        return await self._request("GET", "/web/api/v2/outages/energy/restores")

    async def async_get_fiber_outage_incidents(self) -> dict[str, Any]:
        """Return public current fiber outage incidents."""

        return await self._request("GET", "/web/api/v2/outages/fiber/incidents")

    async def async_get_fiber_outage_restores(self) -> dict[str, Any]:
        """Return public fiber restores from the outage map window."""

        return await self._request("GET", "/web/api/v2/outages/fiber/restores")

    async def async_get_service_area_boundary(self) -> dict[str, Any]:
        """Return public EPB service-area GeoJSON."""

        return await self._request("GET", "/web/api/v1/boundaries/service-area")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = False,
        json: Any | None = None,
        allow_refresh: bool = True,
    ) -> Any:
        """Make a MyEPB API request."""

        headers = {"Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            headers["X-User-Token"] = await self._async_get_access_token()

        url = f"{self._base_url}{path}"
        try:
            response = await self._session.request(
                method,
                url,
                headers=headers,
                json=json,
            )
        except ClientError as err:
            raise MyEPBApiError(
                f"Error connecting to MyEPB: {_redact_sensitive_text(str(err))}"
            ) from err

        if response.ok:
            return await self._read_response(response)

        error = await self._build_error(response)
        if (
            auth
            and allow_refresh
            and error.error_code in AUTH_ERROR_CODES
            and self._refresh_token_is_valid()
        ):
            await self._refresh_access_token()
            return await self._request(
                method, path, auth=auth, json=json, allow_refresh=False
            )

        if error.error_code in AUTH_ERROR_CODES:
            raise MyEPBAuthError(str(error)) from error
        raise error

    async def _read_response(self, response: ClientResponse) -> Any:
        if response.status in (201, 204):
            return True
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return await response.json()
        if content_type.startswith("text/"):
            return await response.text()
        return await response.read()

    async def _build_error(self, response: ClientResponse) -> MyEPBApiError:
        payload: dict[str, Any] = {}
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            try:
                payload = await response.json()
            except (ClientError, ValueError):
                payload = {}
        error_code = response.headers.get("x-error-code") or payload.get("error")
        reference_id = response.headers.get("x-reference-id")
        message = payload.get("message") or response.reason or "MyEPB API error"
        return MyEPBApiError(
            _redact_sensitive_text(str(message)),
            status=response.status,
            error_code=error_code,
            reference_id=reference_id,
        )

    async def _async_get_access_token(self) -> str:
        if self._access_token and self._token_is_valid(self._access_token_expires_on):
            return self._access_token
        if self._refresh_token_is_valid():
            return await self._refresh_access_token()
        raise MyEPBAuthError("MyEPB login has expired")

    async def _refresh_access_token(self) -> str:
        if not self._username or not self._refresh_token:
            raise MyEPBAuthError("Missing refresh credentials")

        response = await self._request(
            "POST",
            "/web/api/v1/login/",
            json={
                "grant_type": "REFRESH_TOKEN",
                "username": self._username,
                "refresh_token": self._refresh_token,
            },
            allow_refresh=False,
        )
        await self._persist_auth_response(response)
        if not self._access_token:
            raise MyEPBAuthError("MyEPB did not return an access token")
        return self._access_token

    async def _persist_auth_response(self, response: dict[str, Any]) -> None:
        tokens = response.get("tokens", {})
        access = tokens.get("access", {})
        refresh = tokens.get("refresh", {})

        if access.get("token"):
            self._access_token = access.get("token")
            self._access_token_expires_on = access.get("expires_on")
        if refresh.get("token"):
            self._refresh_token = refresh.get("token")
            self._refresh_token_expires_on = refresh.get("expires_on")

        if not self._access_token:
            raise MyEPBAuthError("MyEPB did not return an access token")

        if self._token_update_callback:
            await self._token_update_callback(self.tokens)

    def _refresh_token_is_valid(self) -> bool:
        return bool(
            self._refresh_token and self._token_is_valid(self._refresh_token_expires_on)
        )

    def _token_is_valid(self, expires_on: str | None) -> bool:
        if not expires_on:
            return False
        expires = dt_util.parse_datetime(expires_on)
        if expires is None:
            return False
        if expires.tzinfo is None:
            expires = dt_util.as_utc(expires)
        return (expires - dt_util.utcnow()).total_seconds() > 60


def _redact_sensitive_text(text: str) -> str:
    text = EMAIL_RE.sub(REDACTED_TEXT, text)
    return LONG_NUMBER_RE.sub(REDACTED_TEXT, text)
