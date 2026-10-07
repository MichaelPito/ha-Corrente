"""Sensors for Corrente: current price, time band or period, and the next change."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CorrenteConfigEntry
from .const import ATTRIBUTION_ELCOM, CONF_BEST_HOURS, CONF_ENERGY_SENSOR, DOMAIN
from .coordinator import SwissTariffCoordinator
from .coordinator_gme import GmePriceCoordinator
from .core.contract import ItalyFixedContract, ItalyIndexedContract
from .core.gme import ATTRIBUTION as GME_ATTRIBUTION
from .core.italy import ITALY_TZ, Band, band_at, next_band_change
from .core.schedule import Segment, Window, build_schedule, cheapest_window
from .core.switzerland import SWISS_TZ, SwissContract
from .cost import PERIOD_DAY, PERIOD_MONTH, CostSensor

PARALLEL_UPDATES = 0

_BAND_OPTIONS = [band.value.lower() for band in Band]
_PERIOD_OPTIONS = ["single", "high", "low"]
_REPO_URL = "https://github.com/MichaelPito/ha-corrente"

# The card draws the next 36 hours; the best start is searched in the next 24.
SCHEDULE_HORIZON = timedelta(hours=36)
BEST_WINDOW_HORIZON = timedelta(hours=24)
DEFAULT_BEST_HOURS = 2.0


def best_duration(entry: CorrenteConfigEntry) -> timedelta:
    """How long the appliance runs, from the options (2 hours by default)."""
    hours = {**entry.data, **entry.options}.get(CONF_BEST_HOURS, DEFAULT_BEST_HOURS)
    return timedelta(hours=float(hours))


def italy_schedule(
    contract: ItalyFixedContract, now: datetime, horizon: timedelta
) -> list[Segment]:
    """Price segments of an Italian contract."""
    return build_schedule(
        contract.price_at, lambda moment: next_band_change(moment)[0], now, horizon
    )


def swiss_schedule(contract: SwissContract, now: datetime, horizon: timedelta) -> list[Segment]:
    """Price segments of a Swiss contract."""

    def next_change(moment: datetime) -> datetime | None:
        change = contract.next_change(moment)
        return None if change is None else change[0]

    return build_schedule(lambda m: contract.price_at(m)[0], next_change, now, horizon)


def _best_window(segments: list[Segment], duration: timedelta) -> Window | None:
    return cheapest_window(segments, duration)


def _schedule_attributes(segments: list[Segment], duration: timedelta) -> dict[str, Any]:
    """Attributes of the price sensor in both countries: everything the card draws."""
    window = None
    if segments:
        # Same 24-hour search as the best-start sensor, cut out of the 36-hour schedule.
        limit = segments[0].start + BEST_WINDOW_HORIZON
        window = _best_window(
            [Segment(s.start, min(s.end, limit), s.price) for s in segments if s.start < limit],
            duration,
        )
    return {
        "schedule": [
            {"start": s.start.isoformat(), "end": s.end.isoformat(), "price": s.price}
            for s in segments
        ],
        "best_start": None if window is None else window.start.isoformat(),
        **{
            f"best_{key}": value for key, value in _best_window_attributes(window, duration).items()
        },
    }


def _best_window_attributes(window: Window | None, duration: timedelta) -> dict[str, Any]:
    if window is None:
        return {}
    return {
        "end": window.end.isoformat(),
        "average_price": window.average_price,
        "duration_hours": duration.total_seconds() / 3600,
    }


@dataclass(frozen=True, kw_only=True)
class ItalySensorDescription(SensorEntityDescription):
    """Describes an Italian sensor."""

    value_fn: Callable[[ItalyFixedContract, datetime, timedelta], float | str | datetime | None]


@dataclass(frozen=True, kw_only=True)
class SwissSensorDescription(SensorEntityDescription):
    """Describes a Swiss sensor."""

    value_fn: Callable[[SwissContract, datetime, timedelta], float | str | datetime | None]


def _italy_best_start(
    contract: ItalyFixedContract, now: datetime, duration: timedelta
) -> datetime | None:
    window = _best_window(italy_schedule(contract, now, BEST_WINDOW_HORIZON), duration)
    return None if window is None else window.start


ITALY_SENSORS: tuple[ItalySensorDescription, ...] = (
    ItalySensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda contract, now, _d: contract.price_at(now),
    ),
    ItalySensorDescription(
        key="band",
        translation_key="band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now, _d: band_at(now).value.lower(),
    ),
    ItalySensorDescription(
        key="next_band_change",
        translation_key="next_band_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda contract, now, _d: next_band_change(now)[0],
    ),
    ItalySensorDescription(
        key="next_band",
        translation_key="next_band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now, _d: next_band_change(now)[1].value.lower(),
    ),
    ItalySensorDescription(
        key="next_price",
        translation_key="next_price",
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=4,
        value_fn=lambda contract, now, _d: contract.price_for_band(next_band_change(now)[1]),
    ),
    ItalySensorDescription(
        key="best_start",
        translation_key="best_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_italy_best_start,
    ),
)


def _next_change_at(contract: SwissContract, now: datetime, _d: timedelta) -> datetime | None:
    change = contract.next_change(now)
    return None if change is None else change[0]


def _next_change_price(contract: SwissContract, now: datetime, _d: timedelta) -> float | None:
    change = contract.next_change(now)
    return None if change is None else change[1]


def _swiss_best_start(
    contract: SwissContract, now: datetime, duration: timedelta
) -> datetime | None:
    window = _best_window(swiss_schedule(contract, now, BEST_WINDOW_HORIZON), duration)
    return None if window is None else window.start


SWISS_SENSORS: tuple[SwissSensorDescription, ...] = (
    SwissSensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="CHF/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda contract, now, _d: contract.price_at(now)[0],
    ),
    SwissSensorDescription(
        key="period",
        translation_key="period",
        device_class=SensorDeviceClass.ENUM,
        options=_PERIOD_OPTIONS,
        value_fn=lambda contract, now, _d: contract.period_at(now),
    ),
    SwissSensorDescription(
        key="next_price_change",
        translation_key="next_price_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_change_at,
    ),
    SwissSensorDescription(
        key="next_price",
        translation_key="next_price",
        native_unit_of_measurement="CHF/kWh",
        suggested_display_precision=4,
        value_fn=_next_change_price,
    ),
    SwissSensorDescription(
        key="monthly_fixed",
        translation_key="monthly_fixed",
        native_unit_of_measurement="CHF",
        suggested_display_precision=2,
        value_fn=lambda contract, now, _d: contract.monthly_fixed,
    ),
    SwissSensorDescription(
        key="best_start",
        translation_key="best_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_swiss_best_start,
    ),
)


@dataclass(frozen=True, slots=True)
class PunView:
    """What the PUN sensors need: the contract and the wholesale price segments."""

    contract: ItalyIndexedContract
    wholesale: list[Segment]

    def segment_at(self, moment: datetime) -> Segment | None:
        return next((s for s in self.wholesale if s.start <= moment < s.end), None)

    def price_at(self, moment: datetime) -> float | None:
        segment = self.segment_at(moment)
        return None if segment is None else self.contract.price_from(segment.price)

    def schedule(self, now: datetime, horizon: timedelta) -> list[Segment]:
        """Retail price segments from now, as far as GME has published (merged when equal)."""
        end = now + horizon
        merged: list[Segment] = []
        for s in self.wholesale:
            if s.end <= now or s.start >= end:
                continue
            piece = Segment(max(s.start, now), min(s.end, end), self.contract.price_from(s.price))
            if merged and merged[-1].price == piece.price and merged[-1].end == piece.start:
                merged[-1] = Segment(merged[-1].start, piece.end, piece.price)
            else:
                merged.append(piece)
        return merged

    def next_change(self, now: datetime) -> Segment | None:
        """The first segment after now whose price differs from the current one."""
        segments = self.schedule(now, SCHEDULE_HORIZON)
        return segments[1] if len(segments) > 1 else None


@dataclass(frozen=True, kw_only=True)
class PunSensorDescription(SensorEntityDescription):
    """Describes a sensor of a PUN-indexed Italian contract."""

    value_fn: Callable[[PunView, datetime, timedelta], float | str | datetime | None]


def _pun_best_start(view: PunView, now: datetime, duration: timedelta) -> datetime | None:
    window = _best_window(view.schedule(now, BEST_WINDOW_HORIZON), duration)
    return None if window is None else window.start


PUN_SENSORS: tuple[PunSensorDescription, ...] = (
    PunSensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda view, now, _d: view.price_at(now),
    ),
    PunSensorDescription(
        key="wholesale",
        translation_key="wholesale",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        value_fn=lambda view, now, _d: (s := view.segment_at(now)) and s.price,
    ),
    PunSensorDescription(
        key="band",
        translation_key="band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda view, now, _d: band_at(now).value.lower(),
    ),
    PunSensorDescription(
        key="next_price_change",
        translation_key="next_price_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda view, now, _d: (s := view.next_change(now)) and s.start,
    ),
    PunSensorDescription(
        key="next_price",
        translation_key="next_price",
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=4,
        value_fn=lambda view, now, _d: (s := view.next_change(now)) and s.price,
    ),
    PunSensorDescription(
        key="best_start",
        translation_key="best_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_pun_best_start,
    ),
)


def _hours_label(duration: timedelta) -> str:
    hours = duration.total_seconds() / 3600
    return f"{hours:g}"


def _device_info(entry: CorrenteConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=_REPO_URL,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CorrenteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors and refresh them every quarter of an hour."""
    data = entry.runtime_data
    entities: list[SensorEntity]
    if data.switzerland is not None:
        entities = [SwissSensor(entry, data.switzerland, d) for d in SWISS_SENSORS]
        coordinator = data.switzerland

        def price_fn(now: datetime) -> float | None:
            return coordinator.data.contract.price_at(now)[0] if coordinator.data else None

        currency, tz = "CHF", SWISS_TZ
    elif data.gme is not None:
        gme, indexed = data.gme, data.italy_indexed
        entities = [PunSensor(entry, gme, indexed, d) for d in PUN_SENSORS]

        def price_fn(now: datetime) -> float | None:
            return PunView(indexed, gme.data or []).price_at(now)

        currency, tz = "EUR", ITALY_TZ
    else:
        entities = [ItalySensor(entry, d) for d in ITALY_SENSORS]
        price_fn, currency, tz = data.italy.price_at, "EUR", ITALY_TZ
    async_add_entities(entities)

    meter = {**entry.data, **entry.options}.get(CONF_ENERGY_SENSOR)
    if meter:
        async_add_entities(
            CostSensor(
                unique_id=f"{entry.entry_id}_cost_{period}",
                device_info=_device_info(entry),
                energy_entity=meter,
                price_fn=price_fn,
                currency=currency,
                period=period,
                tz=tz,
            )
            for period in (PERIOD_DAY, PERIOD_MONTH)
        )

    @callback
    def _refresh(_now: datetime) -> None:
        for entity in entities:
            if entity.hass is not None:
                entity.async_write_ha_state()

    # Italian bands change on the hour; Swiss windows can start at any quarter.
    entry.async_on_unload(async_track_time_change(hass, _refresh, minute=(0, 15, 30, 45), second=0))


class ItalySensor(SensorEntity):
    """A sensor computed from the Italian contract and the clock."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: ItalySensorDescription

    def __init__(self, entry: CorrenteConfigEntry, description: ItalySensorDescription) -> None:
        self.entity_description = description
        self._contract = entry.runtime_data.italy
        self._duration = best_duration(entry)
        self._attr_translation_placeholders = {"hours": _hours_label(self._duration)}
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the value at this moment."""
        return self.entity_description.value_fn(self._contract, dt_util.utcnow(), self._duration)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The schedule on the price sensor, window details on the best-start sensor."""
        key = self.entity_description.key
        if key == "price":
            return _schedule_attributes(
                italy_schedule(self._contract, dt_util.utcnow(), SCHEDULE_HORIZON), self._duration
            )
        if key == "best_start":
            segments = italy_schedule(self._contract, dt_util.utcnow(), BEST_WINDOW_HORIZON)
            return _best_window_attributes(_best_window(segments, self._duration), self._duration)
        return None


class SwissSensor(CoordinatorEntity[SwissTariffCoordinator], SensorEntity):
    """A sensor computed from the operator's tariff file and the clock."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION_ELCOM
    entity_description: SwissSensorDescription

    def __init__(
        self,
        entry: CorrenteConfigEntry,
        coordinator: SwissTariffCoordinator,
        description: SwissSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._duration = best_duration(entry)
        self._attr_translation_placeholders = {"hours": _hours_label(self._duration)}
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the value at this moment."""
        return self.entity_description.value_fn(
            self.coordinator.data.contract, dt_util.utcnow(), self._duration
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Sources and schedule on the price sensor, window details on the best-start sensor."""
        contract = self.coordinator.data.contract
        now = dt_util.utcnow()
        if self.entity_description.key == "best_start":
            return _best_window_attributes(
                _best_window(swiss_schedule(contract, now, BEST_WINDOW_HORIZON), self._duration),
                self._duration,
            )
        if self.entity_description.key != "price":
            return None
        _, gap = contract.price_at(now)
        return {
            "energy_tariff": contract.electricity.name,
            "grid_tariff": contract.grid.name,
            "regional_fees": contract.regional_fees.name if contract.regional_fees else None,
            "schedule_gap_filled": gap,
            "source": self.coordinator.data.source_url,
            "federal_charges_checked_with_elcom": self.coordinator.data.federal_checked,
            **_schedule_attributes(swiss_schedule(contract, now, SCHEDULE_HORIZON), self._duration),
        }


class PunSensor(CoordinatorEntity[GmePriceCoordinator], SensorEntity):
    """A sensor of a PUN-indexed contract, from GME's prices and the clock."""

    _attr_has_entity_name = True
    _attr_attribution = GME_ATTRIBUTION
    entity_description: PunSensorDescription

    def __init__(
        self,
        entry: CorrenteConfigEntry,
        coordinator: GmePriceCoordinator,
        contract: ItalyIndexedContract,
        description: PunSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._contract = contract
        self._duration = best_duration(entry)
        self._attr_translation_placeholders = {
            "hours": _hours_label(self._duration),
            "zone": contract.zone,
        }
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    def _view(self) -> PunView:
        return PunView(self._contract, self.coordinator.data or [])

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the value at this moment."""
        return self.entity_description.value_fn(self._view(), dt_util.utcnow(), self._duration)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The schedule (as far as GME has published) on the price sensor."""
        view, now = self._view(), dt_util.utcnow()
        if self.entity_description.key == "price":
            return {
                "zone": self._contract.zone,
                "spread": self._contract.spread,
                "losses": self._contract.losses,
                **_schedule_attributes(view.schedule(now, SCHEDULE_HORIZON), self._duration),
            }
        if self.entity_description.key == "best_start":
            segments = view.schedule(now, BEST_WINDOW_HORIZON)
            return _best_window_attributes(_best_window(segments, self._duration), self._duration)
        return None
