from datetime import datetime, timedelta, timezone

import pytest

from custom_components.battery_roi.accumulator import Accumulator, Sample

T0 = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def hold(acc, start, hours, *sample):
    """Feed steady values every minute, like the integration's 30 s tick."""
    for minute in range(int(hours * 60)):
        acc.update(start + timedelta(minutes=minute), Sample(*sample))
    return start + timedelta(hours=hours)


def test_discharge_at_high_price_minus_charge_at_low_price():
    acc = Accumulator()
    t = hold(acc, T0, 1, 2.0, 0.0, 0.10)  # charge 2 kW at 0.10
    t = hold(acc, t, 1, 0.0, 1.8, 0.40)  # discharge 1.8 kW at 0.40
    acc.update(t, Sample(0.0, 0.0, 0.40))

    t = acc.totals
    assert t.energy_in == pytest.approx(2.0)
    assert t.energy_out == pytest.approx(1.8)
    assert t.profit == pytest.approx(1.8 * 0.40 - 2.0 * 0.10)
    assert acc.efficiency() == pytest.approx(90)


def test_price_that_applied_is_used_not_the_new_one():
    acc = Accumulator()
    t = hold(acc, T0, 0.5, 0.0, 1.0, 0.30)
    acc.update(t, Sample(0.0, 1.0, 1.00))  # price jumps now
    assert acc.totals.profit == pytest.approx(0.15)
    assert acc.rate() == pytest.approx(1.00)


def test_negative_price_charging_is_profit():
    acc = Accumulator()
    t = hold(acc, T0, 1, 3.0, 0.0, -0.05)
    acc.update(t, Sample(0.0, 0.0, -0.05))
    assert acc.totals.profit == pytest.approx(0.15)


def test_unavailable_and_long_gaps_are_skipped():
    acc = Accumulator()
    acc.update(T0, Sample(0.0, 1.0, 0.30))
    acc.update(T0 + timedelta(minutes=1), None)  # books the first minute
    acc.update(T0 + timedelta(minutes=10), Sample(0.0, 1.0, 0.30))  # nothing: previous sample invalid
    acc.update(T0 + timedelta(hours=2), Sample(0.0, 1.0, 0.30))  # nothing: gap too long
    assert acc.totals.profit == pytest.approx(0.30 / 60)


def test_day_and_month_rollover_keep_last_period():
    acc = Accumulator()
    start = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)
    for minutes in range(0, 80, 10):
        acc.update(start + timedelta(minutes=minutes), Sample(0.0, 6.0, 0.50))
    t = acc.totals
    assert t.day == "2026-10-01" and t.month_key == "2026-10"
    assert t.yesterday == pytest.approx(3.0)
    assert t.last_month == pytest.approx(3.0)
    assert t.today == pytest.approx(0.5)
    assert t.profit == pytest.approx(3.5)


def test_restored_totals_roll_over_after_restart():
    acc = Accumulator({"profit": 10, "today": 1.2, "month": 5, "day": "2026-09-25", "month_key": "2026-09", "since": T0.isoformat()})
    acc.update(T0, Sample(0.0, 0.0, 0.3))
    assert acc.totals.yesterday == 1.2 and acc.totals.today == 0
    assert acc.totals.month == 5 and acc.totals.profit == 10


def test_payback_needs_a_week_of_data():
    acc = Accumulator({"profit": 20, "since": T0.isoformat()})
    assert acc.payback_years(1000, T0 + timedelta(days=3)) is None
    # 20 earned in 10 days -> 730/year; 980 left -> ~1.34 years
    assert acc.payback_years(1000, T0 + timedelta(days=10)) == pytest.approx(980 / 730)


@pytest.mark.parametrize(
    ("grid_kw", "charge", "discharge", "expected"),
    [
        # Discharging 1 kW, house still imports 0.5 kW: all of it avoided buying.
        (0.5, 0.0, 1.0, 1.0 * 0.30),
        # Discharging 1 kW while exporting 0.4 kW: 0.6 avoided buying, 0.4 was sold.
        (-0.4, 0.0, 1.0, 0.6 * 0.30 + 0.4 * 0.05),
        # Charging 2 kW from 3 kW solar surplus (still exporting 1 kW): cost is lost feed-in.
        (-1.0, 2.0, 0.0, -2.0 * 0.05),
        # Charging 2 kW, importing 1.5 kW: 1.5 bought at import price, 0.5 was solar.
        (1.5, 2.0, 0.0, -(1.5 * 0.30 + 0.5 * 0.05)),
    ],
)
def test_feed_in_price_with_grid_meter(grid_kw, charge, discharge, expected):
    assert Sample(charge, discharge, 0.30, 0.05, grid_kw).profit_per_hour() == pytest.approx(expected)


def test_same_price_both_ways_matches_simple_formula():
    for grid in (-3.0, -0.5, 0.0, 0.7, 4.0):
        assert Sample(0.0, 1.2, 0.25, 0.25, grid).profit_per_hour() == pytest.approx(0.30)


def test_charging_from_solar_is_not_selling():
    # 3 kW solar, 1 kW house, battery stores 2 kW, nothing exported.
    # Without the battery those 2 kW would have been sold at the feed-in price.
    assert Sample(2.0, 0.0, 0.30, 0.05, 0.0).profit_per_hour() == pytest.approx(-0.10)


def test_standby_and_wear():
    # Idle battery drawing 20 W from the grid costs money.
    assert Sample(0.0, 0.0, 0.30, 0.05, 0.5, standby_kw=0.02).profit_per_hour() == pytest.approx(-0.006)
    # Discharging 1 kW into the house, 0.05 EUR wear per kWh delivered.
    assert Sample(0.0, 1.0, 0.30, 0.05, 0.2, wear_per_kwh=0.05).profit_per_hour() == pytest.approx(0.25)
    # Same without a grid meter.
    assert Sample(0.0, 1.0, 0.30, standby_kw=0.02, wear_per_kwh=0.05).profit_per_hour() == pytest.approx(0.98 * 0.30 - 0.05)
