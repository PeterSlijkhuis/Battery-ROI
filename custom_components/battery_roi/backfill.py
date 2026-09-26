"""Fill the totals from Home Assistant's recorded history.

Detailed state history only goes back as far as the recorder keeps it (10 days
by default). Before that, the hourly averages in long-term statistics are used,
which exist for sensors with a state class. Everything is replayed on a
one-minute grid through the same Accumulator the live sensors use.

A sensor that did not change keeps its value, so time when Home Assistant was
off would be booked as if the battery kept going. Hourly statistics are only
written while Home Assistant runs, so hours without them are skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .accumulator import Accumulator, Sample

STEP = timedelta(minutes=1)

Points = dict[str, list[tuple[datetime, State]]]
HOUR = timedelta(hours=1)


async def async_load(
    hass: HomeAssistant, entity_ids: list[str], start: datetime, end: datetime
) -> tuple[Points, set[datetime] | None]:
    return await get_instance(hass).async_add_executor_job(_load, hass, entity_ids, start, end)


def _load(
    hass: HomeAssistant, entity_ids: list[str], start: datetime, end: datetime
) -> tuple[Points, set[datetime] | None]:
    """History per sensor, plus the hours Home Assistant was running (None if unknown)."""
    ids = set(entity_ids)
    stats = statistics_during_period(hass, start, end, ids, "hour", None, {"mean"})
    meta = get_metadata(hass, statistic_ids=ids)
    raw = get_significant_states(
        hass, start, end, entity_ids, significant_changes_only=False, minimal_response=False
    )
    points: Points = {}
    running: set[datetime] | None = None
    for entity_id in entity_ids:
        states = [s for s in raw.get(entity_id, []) if isinstance(s, State)]
        detailed_from = states[0].last_updated if states else end
        unit = meta.get(entity_id, (None, {}))[1].get("unit_of_measurement")
        rows = [row for row in stats.get(entity_id, []) if row.get("mean") is not None]
        hours = {dt_util.utc_from_timestamp(row["start"]) for row in rows}
        # The battery power sensor is the first in the list; its hours tell when HA ran.
        if entity_id == entity_ids[0] and hours:
            running = hours
        hourly = [
            (
                dt_util.utc_from_timestamp(row["start"]),
                State(entity_id, str(row["mean"]), {"unit_of_measurement": unit} if unit else {}),
            )
            for row in rows
        ]
        points[entity_id] = [p for p in hourly if p[0] < detailed_from] + [
            (s.last_updated, s) for s in states
        ]
    return points, running


def replay(
    points: Points,
    start: datetime,
    end: datetime,
    build: Callable[[Callable[[str], State | None], datetime], Sample | None],
    running: set[datetime] | None = None,
) -> tuple[Accumulator, datetime | None]:
    """Step through the history minute by minute, booking what the battery did.

    Also returns the first moment with enough data to book anything.
    """
    acc = Accumulator()
    first: datetime | None = None
    current: dict[str, State | None] = {entity_id: None for entity_id in points}
    index = dict.fromkeys(points, 0)
    # The current hour has no statistics yet, so it counts as running.
    last_hour = max(running) if running else None
    now = start
    while now <= end:
        for entity_id, series in points.items():
            i = index[entity_id]
            while i < len(series) and series[i][0] <= now:
                current[entity_id] = series[i][1]
                i += 1
            index[entity_id] = i
        hour = now.replace(minute=0, second=0, microsecond=0)
        off = running is not None and hour not in running and hour <= last_hour
        sample = None if off else build(current.get, now)
        if sample is not None and first is None:
            first = now
        acc.update(dt_util.as_local(now), sample)
        now += STEP
    return acc, first
