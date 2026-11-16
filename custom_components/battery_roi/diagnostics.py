"""Diagnostics: the chosen sensors, their current readings and the totals, for support questions."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import BatteryRoiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BatteryRoiConfigEntry
) -> dict[str, Any]:
    hub = entry.runtime_data
    sources = {}
    for key, entity_id in hub.config.items():
        if isinstance(entity_id, str) and entity_id.startswith("sensor."):
            state = hass.states.get(entity_id)
            sources[key] = {
                "entity_id": entity_id,
                "state": None if state is None else state.state,
                "unit": None if state is None else state.attributes.get("unit_of_measurement"),
            }
    return {
        "config": hub.config,
        "sources": sources,
        "live": hub.live,
        "rate": hub.acc.rate(),
        "totals": hub.acc.as_dict(),
    }
