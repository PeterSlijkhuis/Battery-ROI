"""Setup screen: users pick their own sensors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_COST,
    CONF_CHARGE_POWER,
    CONF_DISCHARGE_POWER,
    CONF_FEED_IN_FIXED,
    CONF_FEED_IN_PRICE,
    CONF_GRID_POWER,
    CONF_INSTALL_DATE,
    CONF_NET_METERING_UNTIL,
    CONF_POSITIVE_MEANS,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_NIGHT_WEEKEND,
    CONF_PRICE,
    CONF_PRICE_FIXED,
    CONF_PRICE_NIGHT,
    CONF_PRICE_SURCHARGE,
    CONF_SOC,
    CONF_SOLAR_POWER,
    CONF_STANDBY_POWER,
    CONF_VAT,
    CONF_WEAR_COST,
    DOMAIN,
    POSITIVE_CHARGING,
    POSITIVE_DISCHARGING,
)

_POWER = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="power")
)
_SENSOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _number(unit: str | None = None, step: float | str = "any", maximum: float | None = None):
    config = selector.NumberSelectorConfig(min=0, step=step, mode=selector.NumberSelectorMode.BOX)
    if maximum is not None:
        config["max"] = maximum
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


# Required fields sit in the open sections; extras are folded away.
SECTIONS: dict[str, tuple[bool, dict]] = {
    "battery": (False, {
        vol.Required(CONF_CHARGE_POWER): _POWER,
        vol.Optional(CONF_DISCHARGE_POWER): _POWER,
        vol.Required(CONF_POSITIVE_MEANS, default=POSITIVE_CHARGING): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[POSITIVE_CHARGING, POSITIVE_DISCHARGING],
                translation_key=CONF_POSITIVE_MEANS,
            )
        ),
        vol.Optional(CONF_SOC): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="battery")
        ),
    }),
    "prices": (False, {
        vol.Optional(CONF_PRICE): _SENSOR,
        vol.Optional(CONF_PRICE_SURCHARGE): _number(maximum=1),
        vol.Optional(CONF_VAT): _number("%", 0.1, 100),
        vol.Optional(CONF_PRICE_FIXED): _number(maximum=5),
        vol.Optional(CONF_PRICE_NIGHT): _number(maximum=5),
        vol.Optional(CONF_NIGHT_START, default="23:00:00"): selector.TimeSelector(),
        vol.Optional(CONF_NIGHT_END, default="07:00:00"): selector.TimeSelector(),
        vol.Optional(CONF_NIGHT_WEEKEND, default=True): selector.BooleanSelector(),
        vol.Optional(CONF_FEED_IN_PRICE): _SENSOR,
        vol.Optional(CONF_FEED_IN_FIXED): _number(maximum=1),
        vol.Optional(CONF_NET_METERING_UNTIL): selector.DateSelector(),
    }),
    "grid": (True, {
        vol.Optional(CONF_GRID_POWER): _POWER,
        vol.Optional(CONF_SOLAR_POWER): _POWER,
    }),
    "costs": (True, {
        vol.Optional(CONF_STANDBY_POWER): _number("W", 1, 1000),
        vol.Optional(CONF_WEAR_COST): _number(maximum=1),
        vol.Optional(CONF_BATTERY_COST): _number(step=1),
        vol.Optional(CONF_INSTALL_DATE): selector.DateSelector(),
    }),
}

def _schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    """Optional sections start folded, unless they already hold a setting."""
    current = current or {}
    return vol.Schema(
        {
            vol.Required(name): section(
                vol.Schema(fields),
                {"collapsed": collapsed and not any(str(k) in current for k in fields)},
            )
            for name, (collapsed, fields) in SECTIONS.items()
        }
    )


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Store answers flat so the rest of the integration never sees sections."""
    return {k: v for part in user_input.values() for k, v in part.items()}


def _nest(flat: Mapping[str, Any]) -> dict[str, dict]:
    return {
        name: {str(key): flat[str(key)] for key in fields if str(key) in flat}
        for name, (_, fields) in SECTIONS.items()
    }


RELOAD_HINT = (
    "Battery ROI is set up. To add its card, reload the page first: "
    "press F5 in a browser, or fully close the Home Assistant app and open it again."
)
RELOAD_HINT_NL = (
    "Battery ROI is ingesteld. Herlaad eerst de pagina om de kaart toe te voegen: "
    "druk op F5 in de browser, of sluit de Home Assistant-app helemaal af en open hem opnieuw."
)


def _errors(data: dict[str, Any]) -> dict[str, str]:
    if data.get(CONF_DISCHARGE_POWER) == data[CONF_CHARGE_POWER]:
        return {"base": "same_sensor"}
    if not data.get(CONF_PRICE) and data.get(CONF_PRICE_FIXED) is None:
        return {"base": "no_price"}
    return {}


class BatteryRoiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten(user_input)
            errors = _errors(data)
            if not errors:
                # An open dashboard only picks up the new card after a reload.
                nl = self.hass.config.language.startswith("nl")
                persistent_notification.async_create(
                    self.hass,
                    RELOAD_HINT_NL if nl else RELOAD_HINT,
                    "Battery ROI",
                    f"{DOMAIN}_reload",
                )
                return self.async_create_entry(title="Battery ROI", data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_schema(), user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BatteryRoiOptionsFlow()


class BatteryRoiOptionsFlow(OptionsFlow):
    """Change the chosen sensors later without losing the running totals."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten(user_input)
            errors = _errors(data)
            if not errors:
                return self.async_create_entry(data=data)
        saved = self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_schema(saved), user_input or _nest(saved)),
            errors=errors,
        )
