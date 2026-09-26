"""Profit bookkeeping, free of Home Assistant so it can be tested on its own.

Profit is what the grid bill would have been without the battery minus what
it is with the battery. With one price for both directions that is simply
(discharge_kW - charge_kW) * price. With a separate feed-in price and a grid
meter, each kWh the battery shifts is valued at the price it actually
displaced: import price when it avoids buying, feed-in price when it avoids
or causes exporting.

Each sample's values are booked for the interval that follows it (left
Riemann sum). A tariff is a step function, so that is the price that applied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

# Gaps longer than this (HA restart, sensor offline) are skipped, not guessed.
MAX_GAP = timedelta(minutes=15)


@dataclass
class Totals:
    profit: float = 0.0
    energy_in: float = 0.0
    energy_out: float = 0.0
    today: float = 0.0
    yesterday: float | None = None
    month: float = 0.0
    last_month: float | None = None
    day: str | None = None
    month_key: str | None = None
    since: str | None = None


@dataclass(frozen=True)
class Sample:
    charge_kw: float
    discharge_kw: float
    import_price: float
    export_price: float | None = None
    grid_kw: float | None = None  # + importing, - exporting

    def profit_per_hour(self) -> float:
        if self.export_price is None or self.grid_kw is None:
            return (self.discharge_kw - self.charge_kw) * self.import_price
        without_battery = self.grid_kw - self.charge_kw + self.discharge_kw
        return self._bill(without_battery) - self._bill(self.grid_kw)

    def _bill(self, grid_kw: float) -> float:
        return grid_kw * (self.import_price if grid_kw > 0 else self.export_price)


class Accumulator:
    def __init__(self, stored: dict | None = None) -> None:
        self.totals = Totals(**(stored or {}))
        self._last: tuple[datetime, Sample] | None = None

    def update(self, now: datetime, sample: Sample | None) -> None:
        """Book the interval since the previous sample, then remember this one."""
        t = self.totals
        if t.since is None:
            t.since = now.isoformat()

        if self._last is not None:
            last_at, last = self._last
            gap = now - last_at
            if timedelta(0) < gap <= MAX_GAP:
                hours = gap.total_seconds() / 3600
                kwh_in = last.charge_kw * hours
                kwh_out = last.discharge_kw * hours
                money = last.profit_per_hour() * hours
                t.energy_in += kwh_in
                t.energy_out += kwh_out
                t.profit += money
                t.today += money
                t.month += money

        self._rollover(now)

        self._last = None if sample is None else (now, sample)

    def _rollover(self, now: datetime) -> None:
        t = self.totals
        day = now.date().isoformat()
        month_key = day[:7]
        if t.day != day:
            if t.day is not None:
                t.yesterday = t.today
            t.today = 0.0
            t.day = day
        if t.month_key != month_key:
            if t.month_key is not None:
                t.last_month = t.month
            t.month = 0.0
            t.month_key = month_key

    def rate(self) -> float | None:
        """Current EUR/h: positive while the battery is earning."""
        return None if self._last is None else self._last[1].profit_per_hour()

    def efficiency(self) -> float | None:
        t = self.totals
        if t.energy_in < 1:
            return None
        return t.energy_out / t.energy_in * 100

    def payback_years(self, cost: float | None, now: datetime) -> float | None:
        """Years left until the battery has earned back its cost at the average rate so far."""
        t = self.totals
        if not cost or t.since is None or t.profit <= 0:
            return None
        days = (now - datetime.fromisoformat(t.since)).total_seconds() / 86400
        if days < 7:
            return None
        per_year = t.profit / days * 365
        return max(cost - t.profit, 0) / per_year

    def as_dict(self) -> dict:
        return asdict(self.totals)
