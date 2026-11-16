"""Reset and undo buttons, for starting over after fixing a wrong sensor or sign."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BatteryRoiConfigEntry
from .const import DOMAIN, VERSION


# Entities only read the hub's memory, so updates never need to wait for each other.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: BatteryRoiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ResetButton(entry), UndoResetButton(entry)])


class ResetButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "reset_totals"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restore"

    def __init__(self, entry: BatteryRoiConfigEntry) -> None:
        self._entry = entry
        key = self._attr_translation_key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self.entity_id = f"button.{DOMAIN}_{key}"  # English in every language
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Battery ROI",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        await self._entry.runtime_data.async_reset()


class UndoResetButton(ResetButton):
    """Only available right after a reset, for a press by mistake."""

    _attr_translation_key = "undo_reset"
    _attr_icon = "mdi:undo"

    @property
    def available(self) -> bool:
        return self._entry.runtime_data.acc.totals.previous is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._entry.runtime_data.signal, self.async_write_ha_state)
        )

    async def async_press(self) -> None:
        await self._entry.runtime_data.async_undo_reset()
