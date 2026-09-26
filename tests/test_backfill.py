from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.core import State

from custom_components.battery_roi.accumulator import Sample
from custom_components.battery_roi.backfill import replay

T0 = datetime(2026, 3, 14, 10, tzinfo=timezone.utc)


def _points(entity_id, *values):
    return [(T0 + timedelta(hours=i), State(entity_id, str(v))) for i, v in enumerate(values)]


def test_replay_books_cheap_charge_and_dear_discharge():
    """One hour charging 1 kW at 0.10, one hour discharging 1 kW at 0.40: +0.30."""
    points = {
        "sensor.battery": _points("sensor.battery", 1, -1, 0),
        "sensor.price": _points("sensor.price", 0.10, 0.40, 0.40),
    }

    def build(get, at):
        power, price = get("sensor.battery"), get("sensor.price")
        if power is None or price is None:
            return None
        kw = float(power.state)
        return Sample(max(kw, 0), max(-kw, 0), float(price.state))

    acc, first = replay(points, T0 - timedelta(hours=1), T0 + timedelta(hours=2), build)

    assert first == T0
    assert acc.totals.profit == pytest.approx(0.30)
    assert acc.totals.energy_in == pytest.approx(1)
    assert acc.totals.energy_out == pytest.approx(1)


def test_replay_skips_hours_home_assistant_was_off():
    """A power reading held through an outage must not be booked."""
    points = {"sensor.battery": _points("sensor.battery", -1)}

    def build(get, at):
        power = get("sensor.battery")
        return None if power is None else Sample(0, -float(power.state), 0.40)

    running = {T0, T0 + timedelta(hours=2)}  # off during the second hour
    acc, _ = replay(points, T0, T0 + timedelta(hours=3), build, running)

    assert acc.totals.energy_out == pytest.approx(2, abs=0.05)
