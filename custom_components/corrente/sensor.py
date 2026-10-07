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
from .const import ATTRIBUTION_ELCOM, CONF_ENERGY_SENSOR, DOMAIN
from .coordinator import SwissTariffCoordinator
from .core.contract import ItalyFixedContract
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
BEST_WINDOW_DURATION = timedelta(hours=2)


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


def _best_window(segments: list[Segment]) -> Window | None:
    return cheapest_window(segments, BEST_WINDOW_DURATION)


def _schedule_attributes(segments: list[Segment]) -> dict[str, Any]:
    """Attributes of the price sensor in both countries: everything the card draws."""
    window = None
    if segments:
        # Same 24-hour search as the best-start sensor, cut out of the 36-hour schedule.
        limit = segments[0].start + BEST_WINDOW_HORIZON
        window = _best_window(
            [Segment(s.start, min(s.end, limit), s.price) for s in segments if s.start < limit]
        )
    return {
        "schedule": [
            {"start": s.start.isoformat(), "end": s.end.isoformat(), "price": s.price}
            for s in segments
        ],
        "best_start": None if window is None else window.start.isoformat(),
        **{f"best_{key}": value for key, value in _best_window_attributes(window).items()},
    }


def _best_window_attributes(window: Window | None) -> dict[str, Any]:
    if window is None:
        return {}
    return {
        "end": window.end.isoformat(),
        "average_price": window.average_price,
        "duration_hours": BEST_WINDOW_DURATION.total_seconds() / 3600,
    }


@dataclass(frozen=True, kw_only=True)
class ItalySensorDescription(SensorEntityDescription):
    """Describes an Italian sensor."""

    value_fn: Callable[[ItalyFixedContract, datetime], float | str | datetime | None]


@dataclass(frozen=True, kw_only=True)
class SwissSensorDescription(SensorEntityDescription):
    """Describes a Swiss sensor."""

    value_fn: Callable[[SwissContract, datetime], float | str | datetime | None]


def _italy_best_start(contract: ItalyFixedContract, now: datetime) -> datetime | None:
    window = _best_window(italy_schedule(contract, now, BEST_WINDOW_HORIZON))
    return None if window is None else window.start


ITALY_SENSORS: tuple[ItalySensorDescription, ...] = (
    ItalySensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda contract, now: contract.price_at(now),
    ),
    ItalySensorDescription(
        key="band",
        translation_key="band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now: band_at(now).value.lower(),
    ),
    ItalySensorDescription(
        key="next_band_change",
        translation_key="next_band_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda contract, now: next_band_change(now)[0],
    ),
    ItalySensorDescription(
        key="next_band",
        translation_key="next_band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now: next_band_change(now)[1].value.lower(),
    ),
    ItalySensorDescription(
        key="next_price",
        translation_key="next_price",
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=4,
        value_fn=lambda contract, now: contract.price_for_band(next_band_change(now)[1]),
    ),
    ItalySensorDescription(
        key="best_start",
        translation_key="best_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_italy_best_start,
    ),
)


def _next_change_at(contract: SwissContract, now: datetime) -> datetime | None:
    change = contract.next_change(now)
    return None if change is None else change[0]


def _next_change_price(contract: SwissContract, now: datetime) -> float | None:
    change = contract.next_change(now)
    return None if change is None else change[1]


def _swiss_best_start(contract: SwissContract, now: datetime) -> datetime | None:
    window = _best_window(swiss_schedule(contract, now, BEST_WINDOW_HORIZON))
    return None if window is None else window.start


SWISS_SENSORS: tuple[SwissSensorDescription, ...] = (
    SwissSensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="CHF/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda contract, now: contract.price_at(now)[0],
    ),
    SwissSensorDescription(
        key="period",
        translation_key="period",
        device_class=SensorDeviceClass.ENUM,
        options=_PERIOD_OPTIONS,
        value_fn=lambda contract, now: contract.period_at(now),
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
        value_fn=lambda contract, now: contract.monthly_fixed,
    ),
    SwissSensorDescription(
        key="best_start",
        translation_key="best_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_swiss_best_start,
    ),
)


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
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the value at this moment."""
        return self.entity_description.value_fn(self._contract, dt_util.utcnow())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The schedule on the price sensor, window details on the best-start sensor."""
        key = self.entity_description.key
        if key == "price":
            return _schedule_attributes(
                italy_schedule(self._contract, dt_util.utcnow(), SCHEDULE_HORIZON)
            )
        if key == "best_start":
            segments = italy_schedule(self._contract, dt_util.utcnow(), BEST_WINDOW_HORIZON)
            return _best_window_attributes(_best_window(segments))
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
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the value at this moment."""
        return self.entity_description.value_fn(self.coordinator.data.contract, dt_util.utcnow())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Sources and schedule on the price sensor, window details on the best-start sensor."""
        contract = self.coordinator.data.contract
        now = dt_util.utcnow()
        if self.entity_description.key == "best_start":
            return _best_window_attributes(
                _best_window(swiss_schedule(contract, now, BEST_WINDOW_HORIZON))
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
            **_schedule_attributes(swiss_schedule(contract, now, SCHEDULE_HORIZON)),
        }
