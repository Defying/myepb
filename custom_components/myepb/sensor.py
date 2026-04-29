"""Sensors for MyEPB."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import StateType

from .const import ATTR_ACCOUNT_NUMBER, ATTR_SERVICE_ADDRESS, DOMAIN
from .coordinator import MyEPBCoordinator, MyEPBPowerAccount


@dataclass(frozen=True, kw_only=True)
class MyEPBSensorEntityDescription(SensorEntityDescription):
    """Describe a MyEPB sensor."""

    value_fn: Callable[[MyEPBPowerAccount], StateType]
    exists_fn: Callable[[MyEPBPowerAccount], bool] = lambda account: True


@dataclass(frozen=True, kw_only=True)
class MyEPBOutageSensorEntityDescription(SensorEntityDescription):
    """Describe a public EPB outage sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]


OUTAGE_SENSOR_DESCRIPTIONS: tuple[MyEPBOutageSensorEntityDescription, ...] = (
    MyEPBOutageSensorEntityDescription(
        key="energy_customers_affected",
        translation_key="energy_customers_affected",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "energy_incidents", "summary", "customers_affected")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="energy_outage_incidents",
        translation_key="energy_outage_incidents",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "energy_incidents", "summary", "outage_incidents")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="energy_repairs_in_progress",
        translation_key="energy_repairs_in_progress",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "energy_incidents", "summary", "repairs_in_progress")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="energy_customers_in_repair",
        translation_key="energy_customers_in_repair",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(
                outages,
                "energy_incidents",
                "summary",
                "customer_repairs_in_progress",
            )
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="energy_customers_restored_24h",
        translation_key="energy_customers_restored_24h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "energy_restores", "summary", "customers_restored")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="energy_incidents_restored_24h",
        translation_key="energy_incidents_restored_24h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "energy_restores", "summary", "incidents_restored")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_customers_affected",
        translation_key="fiber_customers_affected",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "fiber_incidents", "summary", "customers_affected")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_outage_incidents",
        translation_key="fiber_outage_incidents",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "fiber_incidents", "summary", "outage_incidents")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_repairs_in_progress",
        translation_key="fiber_repairs_in_progress",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "fiber_incidents", "summary", "repairs_in_progress")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_customers_in_repair",
        translation_key="fiber_customers_in_repair",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(
                outages,
                "fiber_incidents",
                "summary",
                "customer_repairs_in_progress",
            )
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_customers_restored_24h",
        translation_key="fiber_customers_restored_24h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "fiber_restores", "summary", "customers_restored")
        ),
    ),
    MyEPBOutageSensorEntityDescription(
        key="fiber_incidents_restored_24h",
        translation_key="fiber_incidents_restored_24h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda outages: _number(
            _dig(outages, "fiber_restores", "summary", "incidents_restored")
        ),
    ),
)


SENSOR_DESCRIPTIONS: tuple[MyEPBSensorEntityDescription, ...] = (
    MyEPBSensorEntityDescription(
        key="current_cycle_kwh",
        translation_key="current_cycle_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda account: _number(
            _dig(account.usage, "current_cycle_totals", "pos_kwh")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="current_cycle_estimated_cost",
        translation_key="current_cycle_estimated_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda account: _number(
            _dig(account.usage, "current_cycle_totals", "pos_wh_est_cost")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="previous_year_cycle_kwh",
        translation_key="previous_year_cycle_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda account: _number(
            _dig(account.usage, "previous_year_cycle_totals", "pos_kwh")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="usage_percent_difference",
        translation_key="usage_percent_difference",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda account: _number(_dig(account.usage, "percent_difference")),
    ),
    MyEPBSensorEntityDescription(
        key="latest_usage_rate",
        translation_key="latest_usage_rate",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda account: _number(
            _dig(account.inferred_usage, "latest_usage_rate_kw")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="latest_usage_delta",
        translation_key="latest_usage_delta",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda account: _number(
            _dig(account.inferred_usage, "latest_usage_delta_kwh")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="amount_due",
        translation_key="amount_due",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        value_fn=lambda account: _number(_dig(account.account, "amount_due")),
    ),
    MyEPBSensorEntityDescription(
        key="days_until_due",
        translation_key="days_until_due",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda account: _number(_dig(account.account, "days_from_due_date")),
    ),
    MyEPBSensorEntityDescription(
        key="prepay_balance",
        translation_key="prepay_balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        exists_fn=lambda account: account.prepay_summary is not None,
        value_fn=lambda account: _number(
            _dig(account.prepay_summary, "current_prepay_amount")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="prepay_average_daily_charge",
        translation_key="prepay_average_daily_charge",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        exists_fn=lambda account: account.prepay_summary is not None,
        value_fn=lambda account: _number(
            _dig(account.prepay_summary, "average_daily_charge")
        ),
    ),
    MyEPBSensorEntityDescription(
        key="prepay_estimated_days_left",
        translation_key="prepay_estimated_days_left",
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda account: account.prepay_summary is not None,
        value_fn=lambda account: _number(
            _dig(account.prepay_summary, "estimated_days_left")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MyEPB sensors from a config entry."""

    coordinator: MyEPBCoordinator = hass.data[DOMAIN][entry.entry_id]
    unique_prefix = entry.unique_id or entry.entry_id
    entities: list[SensorEntity] = [
        MyEPBOutageSensor(coordinator, unique_prefix, description)
        for description in OUTAGE_SENSOR_DESCRIPTIONS
    ]

    power_accounts = (coordinator.data or {}).get("power_accounts", {})
    for account_number, account in power_accounts.items():
        for description in SENSOR_DESCRIPTIONS:
            if description.exists_fn(account):
                entities.append(MyEPBSensor(coordinator, account_number, description))

    async_add_entities(entities)


class MyEPBSensor(CoordinatorEntity[MyEPBCoordinator], SensorEntity):
    """A MyEPB sensor."""

    entity_description: MyEPBSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyEPBCoordinator,
        account_number: str,
        description: MyEPBSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._account_number = account_number
        self.entity_description = description
        self._attr_unique_id = f"{account_number}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""

        account = self._account
        if account is None:
            return None
        return self.entity_description.value_fn(account)

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""

        account = self._account
        return (
            super().available
            and account is not None
            and self.entity_description.exists_fn(account)
            and self.native_value is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the EPB account."""

        account = self._account
        account_name = account.location_label if account else self._account_number
        return DeviceInfo(
            identifiers={(DOMAIN, self._account_number)},
            manufacturer="EPB",
            model="Energy account",
            name=f"EPB {account_name or self._account_number}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional account context."""

        account = self._account
        if account is None:
            return {}

        attributes = {
            ATTR_ACCOUNT_NUMBER: account.account_number,
            ATTR_SERVICE_ADDRESS: account.service_address,
            "gis_id": account.gis_id,
            "zone_id": account.zone_id,
            "current_cycle_label": _dig(account.usage, "current_cycle_label"),
            "percent_difference_label": _dig(
                account.usage, "percent_difference_label"
            ),
        }

        if account.bill_summary:
            attributes["due_date"] = _dig(
                account.bill_summary, "current_billing_cycle", "due_date"
            )
        if account.prepay_summary:
            attributes["prepay_traffic_light"] = _dig(
                account.prepay_summary, "traffic_light_value"
            )
        if self.entity_description.key in {"latest_usage_rate", "latest_usage_delta"}:
            attributes["latest_usage_elapsed_hours"] = _dig(
                account.inferred_usage, "latest_usage_elapsed_hours"
            )
            attributes["latest_usage_started_at"] = _dig(
                account.inferred_usage, "latest_usage_started_at"
            )
            attributes["latest_usage_ended_at"] = _dig(
                account.inferred_usage, "latest_usage_ended_at"
            )

        return {key: value for key, value in attributes.items() if value is not None}

    @property
    def _account(self) -> MyEPBPowerAccount | None:
        return (self.coordinator.data or {}).get("power_accounts", {}).get(
            self._account_number
        )


class MyEPBOutageSensor(CoordinatorEntity[MyEPBCoordinator], SensorEntity):
    """A public EPB outage map sensor."""

    entity_description: MyEPBOutageSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyEPBCoordinator,
        unique_prefix: str,
        description: MyEPBOutageSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{unique_prefix}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""

        outages = (self.coordinator.data or {}).get("outages", {})
        return self.entity_description.value_fn(outages)

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""

        return super().available and self.native_value is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for public EPB outage data."""

        return DeviceInfo(
            identifiers={(DOMAIN, "public_outages")},
            manufacturer="EPB",
            model="Public outage map",
            name="EPB Public Outages",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return public outage metadata."""

        outages = (self.coordinator.data or {}).get("outages", {})
        attributes = {
            "energy_incident_count": len(
                _dig(outages, "energy_incidents", "incidents") or []
            ),
            "energy_restore_count": len(
                _dig(outages, "energy_restores", "restores") or []
            ),
            "fiber_incident_count": len(
                _dig(outages, "fiber_incidents", "incidents") or []
            ),
            "fiber_restore_count": len(
                _dig(outages, "fiber_restores", "restores") or []
            ),
            "source": "https://epb.com/outage-storm-center/",
        }
        return {key: value for key, value in attributes.items() if value is not None}


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
