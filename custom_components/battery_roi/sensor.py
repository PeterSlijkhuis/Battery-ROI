"""Battery ROI sensors."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BatteryRoiHub
from .const import CONF_BATTERY_COST, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: BatteryRoiHub = entry.runtime_data
    currency = hass.config.currency

    def money(key: str, name: str, value, attrs=None, state_class=SensorStateClass.TOTAL):
        return RoiSensor(
            hub, entry, key, name, value, attrs,
            unit=currency, device_class=SensorDeviceClass.MONETARY, state_class=state_class,
        )

    entities = [
        RoiSensor(
            hub, entry, "rate", "Rate",
            lambda: _round(hub.acc.rate(), 4),
            lambda: hub.live,
            unit=f"{currency}/h", state_class=SensorStateClass.MEASUREMENT, icon="mdi:cash-sync",
        ),
        money("profit_total", "Profit total", lambda: _round(hub.acc.totals.profit)),
        money(
            "profit_today", "Profit today",
            lambda: _round(hub.acc.totals.today),
            lambda: {"last_period": _round(hub.acc.totals.yesterday)},
        ),
        money(
            "profit_this_month", "Profit this month",
            lambda: _round(hub.acc.totals.month),
            lambda: {"last_period": _round(hub.acc.totals.last_month)},
        ),
        RoiSensor(
            hub, entry, "energy_charged", "Energy charged",
            lambda: _round(hub.acc.totals.energy_in, 3), None,
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        RoiSensor(
            hub, entry, "energy_discharged", "Energy discharged",
            lambda: _round(hub.acc.totals.energy_out, 3), None,
            unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        RoiSensor(
            hub, entry, "efficiency", "Efficiency",
            lambda: _round(hub.acc.efficiency(), 1), None,
            unit=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, icon="mdi:battery-sync",
        ),
    ]
    if hub.config.get(CONF_BATTERY_COST):
        cost = hub.config[CONF_BATTERY_COST]
        entities.append(
            RoiSensor(
                hub, entry, "payback", "Payback",
                lambda: _round(hub.acc.payback_years(cost, dt_util.now()), 1),
                lambda: {"battery_cost": cost, "tracking_since": hub.acc.totals.since},
                unit=UnitOfTime.YEARS, icon="mdi:scale-balance",
            )
        )
    async_add_entities(entities)


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


class RoiSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hub: BatteryRoiHub,
        entry: ConfigEntry,
        key: str,
        name: str,
        value: Callable[[], Any],
        attrs: Callable[[], dict] | None,
        *,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        icon: str | None = None,
    ) -> None:
        self._hub = hub
        self._value = value
        self._attrs = attrs
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="Battery ROI"
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._hub.signal, self.async_write_ha_state)
        )

    @property
    def native_value(self):
        return self._value()

    @property
    def extra_state_attributes(self) -> dict | None:
        return self._attrs() if self._attrs else None
