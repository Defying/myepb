"""Data coordinator for MyEPB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MyEPBAuthError, MyEPBClient, MyEPBError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MyEPBPowerAccount:
    """Normalized data for one linked power account."""

    account_number: str
    gis_id: str
    zone_id: str
    location_label: str
    service_address: str
    location: dict[str, Any]
    account: dict[str, Any]
    usage: dict[str, Any]
    inferred_usage: dict[str, Any]
    bill_summary: dict[str, Any] | None
    prepay_summary: dict[str, Any] | None


@dataclass(slots=True)
class _UsageSample:
    """Observed cycle kWh total at the time it changed."""

    kwh: float
    observed_at: datetime


class MyEPBCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate MyEPB API polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MyEPBClient,
        *,
        public_outages_only: bool = False,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.public_outages_only = public_outages_only
        self._usage_samples: dict[str, _UsageSample] = {}
        self._latest_inferred_usage: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            sample_time = dt_util.utcnow()
            outages = await self._async_get_public_outages()
            if self.public_outages_only:
                return {
                    "locations": [],
                    "power_accounts": {},
                    "outages": outages,
                }

            locations = await self.client.async_get_locations()
            power_locations = [
                location for location in locations if location.get("power")
            ]
            account_numbers = [
                str(location["power"]["account_number"])
                for location in power_locations
                if location.get("power", {}).get("account_number")
            ]
            accounts = await self._async_get_power_accounts(account_numbers)
            accounts_by_number = {
                str(account.get("account_number")): account for account in accounts
            }

            power_accounts: dict[str, MyEPBPowerAccount] = {}
            for location in power_locations:
                power = location.get("power", {})
                premise = location.get("premise", {})
                account_number = str(power.get("account_number") or "")
                gis_id = str(premise.get("gis_id") or "")
                zone_id = str(premise.get("zone_id") or "")

                if not account_number or not gis_id or not zone_id:
                    continue

                usage = await self.client.async_get_current_cycle_power_usage(
                    account_number, gis_id, zone_id
                )
                inferred_usage = self._infer_usage(account_number, usage, sample_time)
                account = accounts_by_number.get(account_number, {})
                bill_summary = await self._async_get_bill_summary(account_number)
                prepay_summary = None
                if account.get("enrolled_pre_pay"):
                    prepay_summary = await self._async_get_prepay_summary(
                        account_number
                    )

                power_accounts[account_number] = MyEPBPowerAccount(
                    account_number=account_number,
                    gis_id=gis_id,
                    zone_id=zone_id,
                    location_label=location.get("location_label") or "",
                    service_address=_format_service_address(premise),
                    location=location,
                    account=account,
                    usage=usage,
                    inferred_usage=inferred_usage,
                    bill_summary=bill_summary,
                    prepay_summary=prepay_summary,
                )

            self._drop_stale_usage_samples(set(power_accounts))
            return {
                "locations": locations,
                "power_accounts": power_accounts,
                "outages": outages,
            }
        except MyEPBAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MyEPBError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_get_power_accounts(
        self, account_numbers: list[str]
    ) -> list[dict[str, Any]]:
        try:
            if account_numbers:
                return await self.client.async_get_power_accounts(account_numbers)
            return await self.client.async_get_power_accounts()
        except MyEPBError:
            if account_numbers:
                return await self.client.async_get_power_accounts()
            raise

    async def _async_get_bill_summary(
        self, account_number: str
    ) -> dict[str, Any] | None:
        try:
            return await self.client.async_get_power_bill_summary(account_number)
        except MyEPBError:
            return None

    async def _async_get_prepay_summary(
        self, account_number: str
    ) -> dict[str, Any] | None:
        try:
            return await self.client.async_get_power_prepay_summary(account_number)
        except MyEPBError:
            return None

    async def _async_get_public_outages(self) -> dict[str, dict[str, Any]]:
        return {
            "energy_incidents": await self.client.async_get_energy_outage_incidents(),
            "energy_restores": await self.client.async_get_energy_outage_restores(),
            "fiber_incidents": await self.client.async_get_fiber_outage_incidents(),
            "fiber_restores": await self.client.async_get_fiber_outage_restores(),
        }

    def _infer_usage(
        self,
        account_number: str,
        usage: dict[str, Any],
        observed_at: datetime,
    ) -> dict[str, Any]:
        """Infer latest observed energy delta and rate from cycle total changes."""

        cycle_kwh = _number(_dig(usage, "current_cycle_totals", "pos_kwh"))
        if cycle_kwh is None:
            return self._latest_inferred_usage.get(account_number, {})

        cycle_kwh = float(cycle_kwh)
        previous = self._usage_samples.get(account_number)
        if previous is None:
            self._usage_samples[account_number] = _UsageSample(cycle_kwh, observed_at)
            return self._latest_inferred_usage.get(account_number, {})

        if cycle_kwh < previous.kwh:
            self._usage_samples[account_number] = _UsageSample(cycle_kwh, observed_at)
            self._latest_inferred_usage.pop(account_number, None)
            return {}

        if cycle_kwh == previous.kwh:
            return self._latest_inferred_usage.get(account_number, {})

        elapsed_hours = (observed_at - previous.observed_at).total_seconds() / 3600
        if elapsed_hours <= 0:
            return self._latest_inferred_usage.get(account_number, {})

        delta_kwh = cycle_kwh - previous.kwh
        inferred_usage = {
            "latest_usage_delta_kwh": _round(delta_kwh),
            "latest_usage_rate_kw": _round(delta_kwh / elapsed_hours),
            "latest_usage_elapsed_hours": _round(elapsed_hours),
            "latest_usage_started_at": previous.observed_at.isoformat(),
            "latest_usage_ended_at": observed_at.isoformat(),
        }
        self._usage_samples[account_number] = _UsageSample(cycle_kwh, observed_at)
        self._latest_inferred_usage[account_number] = inferred_usage
        return inferred_usage

    def _drop_stale_usage_samples(self, account_numbers: set[str]) -> None:
        for account_number in set(self._usage_samples) - account_numbers:
            self._usage_samples.pop(account_number, None)
            self._latest_inferred_usage.pop(account_number, None)


def _format_service_address(premise: dict[str, Any]) -> str:
    parts = [
        premise.get("full_service_address"),
        premise.get("city"),
        premise.get("state"),
        premise.get("zip_code"),
    ]
    return " ".join(str(part).strip() for part in parts if part)


def _dig(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return value
    text = str(value).strip()
    if not text or text == "-":
        return None
    text = text.replace("$", "").replace(",", "").replace("%", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed.is_integer():
        return int(parsed)
    return parsed


def _round(value: float) -> float | int:
    rounded = round(value, 3)
    if rounded.is_integer():
        return int(rounded)
    return rounded
