"""Reset button, for starting over after fixing a wrong sensor or sign."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ResetButton(entry)])


class ResetButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "reset_totals"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restore"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_reset_totals"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Battery ROI")

    async def async_press(self) -> None:
        await self._entry.runtime_data.async_reset()
