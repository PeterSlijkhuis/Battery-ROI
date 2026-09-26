"""Battery ROI: what your home battery earned by charging cheap and discharging dear."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .accumulator import Accumulator, Sample
from .const import (
    CARD_URL,
    CONF_CHARGE_POWER,
    CONF_DISCHARGE_POWER,
    CONF_FEED_IN_PRICE,
    CONF_GRID_POWER,
    CONF_POSITIVE_MEANS,
    CONF_PRICE,
    CONF_PRICE_SURCHARGE,
    CONF_SOC,
    CONF_SOLAR_POWER,
    CONF_STANDBY_POWER,
    CONF_VAT,
    CONF_WEAR_COST,
    DOMAIN,
    POSITIVE_CHARGING,
    VERSION,
)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]
TICK = timedelta(seconds=30)
# Samples keep postponing a delayed save, so also save on a fixed beat
# in case Home Assistant stops without a clean shutdown.
SAVE_EVERY = timedelta(minutes=5)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and load it on every dashboard."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}/battery-roi-card.js?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = BatteryRoiHub(hass, entry)
    await hub.async_start()
    entry.runtime_data = hub
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _kw(state: State | None) -> float | None:
    """Power in kW, whatever unit the source reports."""
    value = _float(state)
    if value is None:
        return None
    unit = (state.attributes.get("unit_of_measurement") or "W").strip()
    return value * {"W": 0.001, "kW": 1.0, "MW": 1000.0}.get(unit, 0.001)


def _per_kwh(state: State | None) -> float | None:
    """Price per kWh in main currency units (handles ct/kWh and per MWh)."""
    value = _float(state)
    if value is None:
        return None
    unit = (state.attributes.get("unit_of_measurement") or "").lower()
    if "mwh" in unit:
        value /= 1000
    if "ct" in unit or "cent" in unit:
        value /= 100
    return value


def _float(state: State | None) -> float | None:
    try:
        return float(state.state)
    except (AttributeError, TypeError, ValueError):
        return None


class BatteryRoiHub:
    """Reads the chosen sensors, keeps the books, and tells the sensors to refresh."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        # Options replace the original answers wholesale, so cleared fields stay cleared.
        self.config = dict(entry.options or entry.data)
        self.signal = f"{DOMAIN}_{entry.entry_id}"
        self.store: Store[dict] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.acc = Accumulator()
        self.live: dict[str, float | None] = {}
        self._unsubs: list = []

    async def async_start(self) -> None:
        self.acc = Accumulator(await self.store.async_load())
        watched = [
            self.config[k]
            for k in (
                CONF_CHARGE_POWER, CONF_DISCHARGE_POWER, CONF_PRICE, CONF_FEED_IN_PRICE,
                CONF_GRID_POWER, CONF_SOLAR_POWER, CONF_SOC,
            )
            if self.config.get(k)
        ]
        self._unsubs = [
            async_track_state_change_event(self.hass, watched, self._on_change),
            async_track_time_interval(self.hass, self._on_tick, TICK),
            async_track_time_interval(self.hass, self._on_save, SAVE_EVERY),
        ]
        self._sample()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        await self.store.async_save(self.acc.as_dict())

    @callback
    def _on_change(self, event: Event) -> None:
        self._sample()

    @callback
    def _on_tick(self, now) -> None:
        self._sample()

    async def async_reset(self) -> None:
        """Forget all totals; tracking starts again now."""
        self.acc = Accumulator()
        self._sample()
        await self.store.async_save(self.acc.as_dict())

    async def _on_save(self, now) -> None:
        await self.store.async_save(self.acc.as_dict())

    def _read(self, key: str, parse):
        entity_id = self.config.get(key)
        return parse(self.hass.states.get(entity_id)) if entity_id else None

    @callback
    def _sample(self) -> None:
        price = self._read(CONF_PRICE, _per_kwh)
        if price is not None:
            price += self.config.get(CONF_PRICE_SURCHARGE) or 0
            price *= 1 + (self.config.get(CONF_VAT) or 0) / 100
        feed_in = self._read(CONF_FEED_IN_PRICE, _per_kwh)
        grid = self._read(CONF_GRID_POWER, _kw)

        charge = self._read(CONF_CHARGE_POWER, _kw)
        if self.config.get(CONF_DISCHARGE_POWER):
            discharge = self._read(CONF_DISCHARGE_POWER, _kw)
            charge = abs(charge) if charge is not None else None
            discharge = abs(discharge) if discharge is not None else None
        elif charge is not None:
            # One signed sensor: split it into its two directions.
            signed = charge if self.config.get(CONF_POSITIVE_MEANS, POSITIVE_CHARGING) == POSITIVE_CHARGING else -charge
            charge, discharge = max(signed, 0.0), max(-signed, 0.0)
        else:
            discharge = None

        # Shown on the card via the rate sensor's attributes.
        self.live = {
            "price": price,
            "feed_in_price": feed_in,
            "grid_kw": grid,
            "solar_kw": self._read(CONF_SOLAR_POWER, _kw),
            "soc": self._read(CONF_SOC, _float),
        }
        self.live = {k: None if v is None else round(v, 4) for k, v in self.live.items()}

        sample = None
        if None not in (charge, discharge, price):
            # A feed-in price only helps when the grid meter says which way power flows.
            split = feed_in is not None and grid is not None
            sample = Sample(
                charge, discharge, price,
                feed_in if split else None, grid if split else None,
                standby_kw=(self.config.get(CONF_STANDBY_POWER) or 0) / 1000,
                wear_per_kwh=self.config.get(CONF_WEAR_COST) or 0,
            )
        self.acc.update(dt_util.now(), sample)
        self.store.async_delay_save(self.acc.as_dict, 60)
        async_dispatcher_send(self.hass, self.signal)
