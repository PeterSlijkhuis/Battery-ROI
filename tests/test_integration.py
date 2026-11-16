from datetime import timedelta

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.battery_roi.config_flow import _nest
from custom_components.battery_roi.const import DOMAIN, VERSION

TICK = timedelta(seconds=30)


async def _run(hass: HomeAssistant, freezer, duration: timedelta) -> None:
    """Let time pass in 30 s ticks, like a running Home Assistant."""
    for _ in range(int(duration / timedelta(seconds=30))):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


INPUT = {
    "charge_power": "sensor.ecoflow_power",
    "positive_means": "discharging",
    "price": "sensor.tariff",
    "soc": "sensor.ecoflow_soc",
    "battery_cost": 1500,
}


async def _setup(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("sensor.ecoflow_power", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "12", {"unit_of_measurement": "ct/kWh"})
    hass.states.async_set("sensor.ecoflow_soc", "80", {"unit_of_measurement": "%"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _nest(INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_setup_screen_and_profit(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-09-26 10:00:00+02:00")
    await _setup(hass, freezer)

    # Charging 2 kW at 12 ct for an hour (signed sensor, positive = discharging).
    hass.states.async_set("sensor.ecoflow_power", "-2000", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    rate = hass.states.get("sensor.battery_roi_rate")
    assert float(rate.state) == pytest.approx(-0.24)
    assert rate.attributes["price"] == pytest.approx(0.12)
    assert rate.attributes["soc"] == 80

    await _run(hass, freezer, timedelta(hours=1))
    hass.states.async_set("sensor.ecoflow_power", "1.5", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.tariff", "0.40", {"unit_of_measurement": "EUR/kWh"})
    await hass.async_block_till_done()

    await _run(hass, freezer, timedelta(hours=1))

    today = hass.states.get("sensor.battery_roi_profit_today")
    assert float(today.state) == pytest.approx(1.5 * 0.40 - 2 * 0.12)
    assert today.attributes["unit_of_measurement"] == hass.config.currency
    assert float(hass.states.get("sensor.battery_roi_profit_this_month").state) == pytest.approx(0.36)
    assert float(hass.states.get("sensor.battery_roi_energy_charged").state) == pytest.approx(2)
    assert float(hass.states.get("sensor.battery_roi_energy_discharged").state) == pytest.approx(1.5)
    assert hass.states.get("sensor.battery_roi_payback") is not None
    # Statistics need to know the daily and monthly totals start over.
    assert today.attributes["last_reset"].startswith("2026-09-26T00:00:00")
    month = hass.states.get("sensor.battery_roi_profit_this_month")
    assert month.attributes["last_reset"].startswith("2026-09-01T00:00:00")


async def test_second_instance_blocked_and_same_sensor_rejected(hass: HomeAssistant, freezer) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({"charge_power": "sensor.a", "discharge_power": "sensor.a", "positive_means": "charging", "price": "sensor.p"}),
    )
    assert result["errors"] == {"base": "same_sensor"}

    await _setup(hass, freezer)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT


async def test_options_change_keeps_totals(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-09-26 10:00:00+02:00")
    await _setup(hass, freezer)
    hass.states.async_set("sensor.ecoflow_power", "1000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await _run(hass, freezer, timedelta(minutes=10))
    before = float(hass.states.get("sensor.battery_roi_profit_total").state)
    assert before == pytest.approx(0.02)
    assert hass.states.get("sensor.battery_roi_profit_total").attributes["tracking_since"]

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    new = {k: v for k, v in INPUT.items() if k != "soc"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], _nest(new))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.battery_roi_profit_total").state) == pytest.approx(before)
    assert hass.states.get("sensor.battery_roi_rate").attributes["soc"] is None


async def test_epex_surcharge_feed_in_and_p1(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-09-26 10:00:00+02:00")
    hass.states.async_set("sensor.bat_in", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.bat_out", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.epex", "100", {"unit_of_measurement": "EUR/MWh"})
    hass.states.async_set("sensor.feed_in", "0.05", {"unit_of_measurement": "EUR/kWh"})
    hass.states.async_set("sensor.p1", "-400", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.solar", "2500", {"unit_of_measurement": "W"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({
            "charge_power": "sensor.bat_in",
            "discharge_power": "sensor.bat_out",
            "positive_means": "charging",
            "price": "sensor.epex",
            "price_surcharge": 0.15,
            "feed_in_price": "sensor.feed_in",
            "grid_power": "sensor.p1",
            "solar_power": "sensor.solar",
            "vat": 21,
        }),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    rate = hass.states.get("sensor.battery_roi_rate")
    # 0.6 kW avoided buying at (0.10 + 0.15) * 1.21, 0.4 kW sold at 0.05.
    assert float(rate.state) == pytest.approx(0.6 * 0.3025 + 0.4 * 0.05, abs=1e-4)
    assert rate.attributes["price"] == pytest.approx(0.3025)
    assert rate.attributes["solar_kw"] == pytest.approx(2.5)

    await _run(hass, freezer, timedelta(hours=1))
    assert float(hass.states.get("sensor.battery_roi_profit_today").state) == pytest.approx(0.2, abs=0.01)

    # A wrong sign or sensor can be undone: reset starts the books again.
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.battery_roi_reset_totals"}, blocking=True
    )
    total = hass.states.get("sensor.battery_roi_profit_total")
    assert float(total.state) == 0
    # A new cycle for statistics, so the drop to 0 is not booked as a loss.
    assert total.attributes["last_reset"]
    assert hass.states.get("sensor.battery_roi_energy_charged").attributes["last_reset"] == total.attributes["last_reset"]


def test_card_version_matches_integration():
    """The card shows a reload hint when these differ, so they must ship in step."""
    from pathlib import Path

    card = Path(__file__).parents[1] / "custom_components/battery_roi/frontend/battery-roi-card.js"
    assert f'const CARD_VERSION = "{VERSION}";' in card.read_text()


async def test_solar_charging_costs_fixed_feed_in(hass: HomeAssistant, freezer) -> None:
    """Charging 1 kW from solar that would otherwise be exported costs only the feed-in price."""
    freezer.move_to("2026-09-26 12:00:00+02:00")
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "0.30", {"unit_of_measurement": "EUR/kWh"})
    hass.states.async_set("sensor.grid", "-2000", {"unit_of_measurement": "W"})  # still exporting
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({**INPUT, "grid_power": "sensor.grid", "feed_in_fixed": 0.05}),
    )
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.05)

    # Same charge, but now the house imports: it came from the grid at the full price.
    hass.states.async_set("sensor.grid", "1500", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.30)


async def test_net_metering_ignores_feed_in_until_its_end(hass: HomeAssistant, freezer) -> None:
    """Set up once: solar is worth the full price until net metering ends, then the feed-in price."""
    freezer.move_to("2026-12-31 12:00:00+01:00")
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "0.30", {"unit_of_measurement": "EUR/kWh"})
    hass.states.async_set("sensor.grid", "-2000", {"unit_of_measurement": "W"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({**INPUT, "grid_power": "sensor.grid", "feed_in_fixed": 0.05, "net_metering_until": "2027-01-01"}),
    )
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.30)

    freezer.move_to("2027-01-01 12:00:00+01:00")
    hass.states.async_set("sensor.grid", "-2001", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.05)


async def test_feed_in_costs_count_under_net_metering(hass: HomeAssistant, freezer) -> None:
    """Storing solar avoids the supplier's feed-in costs, even while net metering."""
    freezer.move_to("2026-10-18 12:00:00+02:00")
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "0.30", {"unit_of_measurement": "EUR/kWh"})
    hass.states.async_set("sensor.grid", "-2000", {"unit_of_measurement": "W"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({**INPUT, "grid_power": "sensor.grid", "feed_in_cost": 0.12, "net_metering_until": "2027-01-01"}),
    )
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.18)

    # Grid charging still costs the full import price.
    hass.states.async_set("sensor.grid", "1500", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.30)


async def test_fixed_day_and_night_price_without_sensor(hass: HomeAssistant, freezer) -> None:
    """A fixed day/night contract works without any price sensor."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-09-25 12:00:00+02:00")  # a Friday
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    no_price = {k: v for k, v in INPUT.items() if k != "price"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _nest(no_price))
    assert result["errors"] == {"base": "no_price"}

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({**no_price, "price_fixed": 0.30, "price_night": 0.20, "night_start": "23:00:00", "night_end": "07:00:00"}),
    )
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.30)

    freezer.move_to("2026-09-25 23:30:00+02:00")
    hass.states.async_set("sensor.ecoflow_power", "-1001", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.2002)

    # Saturday noon: weekends are off-peak by default.
    freezer.move_to("2026-09-26 12:00:00+02:00")
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.20)


async def test_fixed_price_covers_an_unavailable_sensor(hass: HomeAssistant, freezer) -> None:
    """The dynamic sensor wins; the fixed price only fills in when it has no value."""
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "0.10", {"unit_of_measurement": "EUR/kWh"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(result["flow_id"], _nest({**INPUT, "price_fixed": 0.30}))
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.10)

    hass.states.async_set("sensor.tariff", "unavailable")
    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.30)


def test_paid_back_on_is_a_date(freezer) -> None:
    from custom_components.battery_roi.sensor import _paid_back_on

    freezer.move_to("2026-09-26 12:00:00+02:00")
    assert _paid_back_on(None) is None
    assert _paid_back_on(2.0)[:7] == "2028-09"


async def test_reset_survives_a_restart_with_an_install_date(hass: HomeAssistant, freezer) -> None:
    """A reset must not be undone by replaying the history again on the next start."""
    freezer.move_to("2026-09-26 10:00:00+02:00")
    await _setup(hass, freezer)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hub = entry.runtime_data
    hub.acc.totals.backfilled_from = "2026-09-01"
    hub.config["install_date"] = "2026-09-01"

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.battery_roi_reset_totals"}, blocking=True
    )
    assert hub.acc.totals.backfilled_from == "2026-09-01"


async def test_entities_refresh_on_the_tick_not_on_every_change(hass: HomeAssistant, freezer) -> None:
    """A grid meter updating every second must not write a state row every second."""
    freezer.move_to("2026-09-26 10:00:00+02:00")
    await _setup(hass, freezer)
    hass.states.async_set("sensor.ecoflow_power", "-2000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.battery_roi_rate").state) == 0

    await _run(hass, freezer, TICK)
    assert float(hass.states.get("sensor.battery_roi_rate").state) == pytest.approx(-0.24)

    from custom_components.battery_roi.sensor import RateSensor

    assert "grid_kw" in RateSensor._unrecorded_attributes


async def test_reset_during_backfill_wins(hass: HomeAssistant, freezer) -> None:
    """History that finishes loading after a reset must not overwrite the fresh totals."""
    import asyncio
    from unittest.mock import patch

    freezer.move_to("2026-09-26 10:00:00+02:00")
    hass.config.components.add("recorder")
    release = asyncio.Event()

    async def slow_load(*args):
        await release.wait()
        return {}, None

    with patch("custom_components.battery_roi.backfill.async_load", slow_load):
        hass.states.async_set("sensor.ecoflow_power", "0", {"unit_of_measurement": "W"})
        hass.states.async_set("sensor.tariff", "12", {"unit_of_measurement": "ct/kWh"})
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        await hass.config_entries.flow.async_configure(
            result["flow_id"], _nest({**INPUT, "install_date": "2026-09-01"})
        )
        await hass.async_block_till_done(wait_background_tasks=False)
        hub = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        await hub.async_reset()
        reset = hub.acc
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hub.acc is reset
    assert hub.acc.totals.backfilled_from == "2026-09-01"


def test_price_units_in_subunits_and_per_mwh() -> None:
    from homeassistant.core import State

    from custom_components.battery_roi import _per_kwh

    def price(value, unit):
        return _per_kwh(State("sensor.p", value, {"unit_of_measurement": unit}))

    assert price("25", "ct/kWh") == pytest.approx(0.25)
    assert price("25", "Cent/kWh") == pytest.approx(0.25)
    assert price("150", "öre/kWh") == pytest.approx(1.5)
    assert price("150", "øre/kWh") == pytest.approx(1.5)
    assert price("24.5", "p/kWh") == pytest.approx(0.245)
    assert price("120", "EUR/MWh") == pytest.approx(0.12)
    assert price("2.1", "SEK/kWh") == pytest.approx(2.1)
    assert price("0.3", "GBP/kWh") == pytest.approx(0.3)


async def test_backfill_reads_only_what_the_profit_needs(hass: HomeAssistant, freezer) -> None:
    from unittest.mock import AsyncMock, patch

    freezer.move_to("2026-09-26 10:00:00+02:00")
    hass.config.components.add("recorder")
    load = AsyncMock(return_value=({}, None))
    with patch("custom_components.battery_roi.backfill.async_load", load):
        hass.states.async_set("sensor.ecoflow_power", "0", {"unit_of_measurement": "W"})
        hass.states.async_set("sensor.tariff", "12", {"unit_of_measurement": "ct/kWh"})
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        await hass.config_entries.flow.async_configure(
            result["flow_id"], _nest({**INPUT, "install_date": "2026-09-01"})
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert load.call_args.args[1] == ["sensor.ecoflow_power", "sensor.tariff"]
    hub = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert hub.acc.totals.backfilled_from == "2026-09-01"


async def test_separate_import_and_export_grid_sensors(hass: HomeAssistant, freezer) -> None:
    """Import minus export gives the same answer as one signed grid sensor."""
    freezer.move_to("2026-09-26 12:00:00+02:00")
    hass.states.async_set("sensor.ecoflow_power", "-1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.tariff", "0.30", {"unit_of_measurement": "EUR/kWh"})
    hass.states.async_set("sensor.grid_import", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.grid_export", "2", {"unit_of_measurement": "kW"})  # still exporting
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _nest({**INPUT, "grid_power": "sensor.grid_import", "grid_export_power": "sensor.grid_export", "feed_in_fixed": 0.05}),
    )
    await _run(hass, freezer, TICK)
    rate = hass.states.get("sensor.battery_roi_rate")
    assert float(rate.state) == pytest.approx(-0.05)
    assert rate.attributes["grid_kw"] == pytest.approx(-2)
