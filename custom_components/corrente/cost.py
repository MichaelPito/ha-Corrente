"""Cost sensors: each kWh the meter counts, priced at the moment it was used."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_TO_KWH = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}
# A jump larger than this between two readings is not consumption (meter swap, glitch).
_MAX_STEP_KWH = 100.0

PERIOD_DAY = "day"
PERIOD_MONTH = "month"


def to_kwh(value: str, unit: str | None) -> float | None:
    """Convert a meter reading to kWh, or None if it can't be used."""
    if value in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    factor = _TO_KWH.get(unit or "kWh")
    if factor is None:
        return None
    try:
        return float(value) * factor
    except ValueError:
        return None


def period_key(moment: datetime, period: str, tz: tzinfo) -> str:
    """Identify the day or month a moment falls in, in local time."""
    local = moment.astimezone(tz)
    return local.strftime("%Y-%m-%d") if period == PERIOD_DAY else local.strftime("%Y-%m")


class CostSensor(RestoreSensor):
    """Cost of today's or this month's consumption."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        *,
        unique_id: str,
        device_info: DeviceInfo,
        energy_entity: str,
        price_fn: Callable[[datetime], float | None],
        currency: str,
        period: str,
        tz: tzinfo,
    ) -> None:
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._attr_translation_key = f"cost_{period}"
        self._attr_native_unit_of_measurement = currency
        self._energy_entity = energy_entity
        self._price_fn = price_fn
        self._period = period
        self._tz = tz
        self._cost = 0.0
        self._kwh = 0.0
        self._last_reading: float | None = None
        self._unsub_rollover: Callable[[], None] | None = None
        self._period_key = period_key(dt_util.utcnow(), period, tz)
        self._attr_last_reset = self._period_start()

    def _period_start(self) -> datetime:
        local = dt_util.utcnow().astimezone(self._tz)
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.replace(day=1) if self._period == PERIOD_MONTH else start

    async def async_added_to_hass(self) -> None:
        """Restore the running total and follow the meter."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.attributes.get("period") == self._period_key:
            try:
                self._cost = float(last.state)
            except ValueError:
                self._cost = 0.0
            self._kwh = float(last.attributes.get("energy_kwh", 0.0))
            reading = last.attributes.get("last_reading_kwh")
            self._last_reading = None if reading is None else float(reading)

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._energy_entity], self._on_reading)
        )
        self._schedule_rollover()
        self.async_on_remove(self._cancel_rollover)

    def _schedule_rollover(self) -> None:
        """Wake up at the next local midnight (Italy or Switzerland, not the server's zone)."""
        local = dt_util.utcnow().astimezone(self._tz)
        midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self._unsub_rollover = async_track_point_in_utc_time(self.hass, self._on_midnight, midnight)

    @callback
    def _cancel_rollover(self) -> None:
        if self._unsub_rollover is not None:
            self._unsub_rollover()
            self._unsub_rollover = None

    @callback
    def _on_reading(self, event: Event[EventStateChangedData]) -> None:
        state = event.data["new_state"]
        if state is None:
            return
        reading = to_kwh(state.state, state.attributes.get("unit_of_measurement"))
        if reading is None:
            return
        self._roll_period()
        previous, self._last_reading = self._last_reading, reading
        if previous is None:
            self.async_write_ha_state()
            return
        step = reading - previous
        if step < 0 or step > _MAX_STEP_KWH:
            _LOGGER.debug("Ignoring meter jump from %s to %s kWh", previous, reading)
            self.async_write_ha_state()
            return
        price = self._price_fn(dt_util.utcnow())
        if price is not None:
            self._kwh += step
            self._cost += step * price
        self.async_write_ha_state()

    @callback
    def _on_midnight(self, _now: datetime) -> None:
        if self._roll_period():
            self.async_write_ha_state()
        self._schedule_rollover()

    def _roll_period(self) -> bool:
        key = period_key(dt_util.utcnow(), self._period, self._tz)
        if key == self._period_key:
            return False
        self._period_key = key
        self._cost = 0.0
        self._kwh = 0.0
        self._attr_last_reset = self._period_start()
        return True

    @property
    def native_value(self) -> float:
        """Cost so far in this period."""
        return round(self._cost, 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What is needed to continue after a restart, and the energy behind the cost."""
        return {
            "period": self._period_key,
            "energy_kwh": round(self._kwh, 4),
            "last_reading_kwh": self._last_reading,
            "meter": self._energy_entity,
        }
