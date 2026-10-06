"""Sensors for Corrente: current price, current band and the next change."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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
from homeassistant.util import dt as dt_util

from . import CorrenteConfigEntry
from .const import DOMAIN
from .core.contract import ItalyFixedContract
from .core.italy import Band, band_at, next_band_change

PARALLEL_UPDATES = 0

_BAND_OPTIONS = [band.value for band in Band]


@dataclass(frozen=True, kw_only=True)
class CorrenteSensorDescription(SensorEntityDescription):
    """Describes a Corrente sensor."""

    value_fn: Callable[[ItalyFixedContract, datetime], float | str | datetime]


SENSORS: tuple[CorrenteSensorDescription, ...] = (
    CorrenteSensorDescription(
        key="price",
        translation_key="price",
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda contract, now: contract.price_at(now),
    ),
    CorrenteSensorDescription(
        key="band",
        translation_key="band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now: band_at(now).value,
    ),
    CorrenteSensorDescription(
        key="next_band_change",
        translation_key="next_band_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda contract, now: next_band_change(now)[0],
    ),
    CorrenteSensorDescription(
        key="next_band",
        translation_key="next_band",
        device_class=SensorDeviceClass.ENUM,
        options=_BAND_OPTIONS,
        value_fn=lambda contract, now: next_band_change(now)[1].value,
    ),
    CorrenteSensorDescription(
        key="next_price",
        translation_key="next_price",
        native_unit_of_measurement="EUR/kWh",
        suggested_display_precision=4,
        value_fn=lambda contract, now: contract.price_for_band(next_band_change(now)[1]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CorrenteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors and refresh them at the top of every hour."""
    entities = [CorrenteSensor(entry, description) for description in SENSORS]
    async_add_entities(entities)

    @callback
    def _refresh(_now: datetime) -> None:
        for entity in entities:
            entity.async_write_ha_state()

    # Bands only change on the hour.
    entry.async_on_unload(async_track_time_change(hass, _refresh, minute=0, second=0))


class CorrenteSensor(SensorEntity):
    """A sensor computed from the contract and the clock."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: CorrenteSensorDescription

    def __init__(self, entry: CorrenteConfigEntry, description: CorrenteSensorDescription) -> None:
        self.entity_description = description
        self._contract = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://github.com/MichaelPito/ha-corrente",
        )

    @property
    def native_value(self) -> float | str | datetime:
        """Return the value at this moment."""
        return self.entity_description.value_fn(self._contract, dt_util.utcnow())
