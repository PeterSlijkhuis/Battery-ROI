"""Setup screen: users pick their own sensors."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_COST,
    CONF_CHARGE_POWER,
    CONF_DISCHARGE_POWER,
    CONF_FEED_IN_PRICE,
    CONF_GRID_POWER,
    CONF_POSITIVE_MEANS,
    CONF_PRICE,
    CONF_PRICE_SURCHARGE,
    CONF_SOC,
    CONF_SOLAR_POWER,
    DOMAIN,
    POSITIVE_CHARGING,
    POSITIVE_DISCHARGING,
)

_POWER = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="power")
)

_SENSOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHARGE_POWER): _POWER,
        vol.Optional(CONF_DISCHARGE_POWER): _POWER,
        vol.Required(CONF_POSITIVE_MEANS, default=POSITIVE_CHARGING): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[POSITIVE_CHARGING, POSITIVE_DISCHARGING],
                translation_key=CONF_POSITIVE_MEANS,
            )
        ),
        vol.Required(CONF_PRICE): _SENSOR,
        vol.Optional(CONF_PRICE_SURCHARGE): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=1, step="any", mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FEED_IN_PRICE): _SENSOR,
        vol.Optional(CONF_GRID_POWER): _POWER,
        vol.Optional(CONF_SOLAR_POWER): _POWER,
        vol.Optional(CONF_SOC): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="battery")
        ),
        vol.Optional(CONF_BATTERY_COST): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, step=1, mode=selector.NumberSelectorMode.BOX)
        ),
    }
)


def _errors(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input.get(CONF_DISCHARGE_POWER) == user_input[CONF_CHARGE_POWER]:
        return {CONF_DISCHARGE_POWER: "same_sensor"}
    return {}


class BatteryRoiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _errors(user_input)
            if not errors:
                return self.async_create_entry(title="Battery ROI", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
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
            errors = _errors(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        current = user_input or self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, current),
            errors=errors,
        )
