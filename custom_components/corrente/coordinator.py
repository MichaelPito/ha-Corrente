"""Keeps a Swiss operator's tariff file up to date."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CANTON,
    CONF_ELECTRICITY_TARIFF,
    CONF_GRID_TARIFF,
    CONF_MUNICIPALITY,
    CONF_OPERATOR_ID,
    CONF_REGIONAL_TARIFF,
    CONF_TARIFF_URL,
    DOMAIN,
)
from .core.elcom import (
    ElcomError,
    TariffFileError,
    async_fetch_tariff_document,
    async_operators_for,
    async_tariff_url_candidates,
)
from .core.switzerland import (
    SWISS_TZ,
    SwissContract,
    Tariff,
    UnsupportedTariffError,
    parse_tariffs,
    suggest_matching,
    tariffs_on,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class SwissTariffData:
    """The operator's tariffs and the contract chosen from them for today."""

    tariffs: list[Tariff]
    contract: SwissContract
    source_url: str


def select_contract(tariffs: list[Tariff], options: dict, day: date) -> SwissContract:
    """Pick the user's tariffs that are in force on ``day``.

    Operators often rename tariffs from one year to the next ("… 2026" →
    "… 2027"), so when the stored name is not found the closest name of the
    same type is used.
    """

    def pick(tariff_type: str, name: str | None) -> Tariff | None:
        if not name:
            return None
        candidates = tariffs_on(tariffs, tariff_type, day)
        exact = [t for t in candidates if t.name == name]
        return exact[0] if exact else suggest_matching(name, candidates)

    electricity = pick("electricity", options[CONF_ELECTRICITY_TARIFF])
    grid = pick("grid", options[CONF_GRID_TARIFF])
    if electricity is None or grid is None:
        raise UnsupportedTariffError(f"no tariff of the operator is in force on {day}")
    return SwissContract(
        electricity=electricity,
        grid=grid,
        regional_fees=pick("regional_fees", options.get(CONF_REGIONAL_TARIFF)),
        canton=options.get(CONF_CANTON),
        municipality=options.get(CONF_MUNICIPALITY),
    )


class SwissTariffCoordinator(DataUpdateCoordinator[SwissTariffData]):
    """Downloads the tariff file twice a day and follows it across years."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._url: str = entry.data[CONF_TARIFF_URL]

    async def _async_update_data(self) -> SwissTariffData:
        options = {**self.config_entry.data, **self.config_entry.options}
        today = dt_util.now(SWISS_TZ).date()
        session = async_get_clientsession(self.hass)
        try:
            tariffs = await self._async_load(session, self._url, today)
            if tariffs is None:
                # A new year, or the operator moved its file: ask ElCom again.
                tariffs = await self._async_find_file(session, options, today)
            contract = select_contract(tariffs, options, today)
        except (ElcomError, UnsupportedTariffError) as err:
            raise UpdateFailed(str(err)) from err
        return SwissTariffData(tariffs=tariffs, contract=contract, source_url=self._url)

    async def _async_load(self, session, url: str, today: date) -> list[Tariff] | None:
        """Tariffs from ``url`` if the file is readable and has tariffs in force today."""
        try:
            tariffs = parse_tariffs(await async_fetch_tariff_document(session, url))
        except TariffFileError:
            return None
        return tariffs if tariffs_on(tariffs, "electricity", today) else None

    async def _async_find_file(self, session, options: dict, today: date) -> list[Tariff]:
        municipality, operator_id = options[CONF_MUNICIPALITY], options[CONF_OPERATOR_ID]
        current = [
            operator.tariff_url
            for operator in await async_operators_for(session, municipality, today.year)
            if operator.operator_id == operator_id
        ]
        candidates = await async_tariff_url_candidates(
            session, municipality, operator_id, today.year, current[0] if current else None
        )
        for url in candidates:
            if url != self._url and (tariffs := await self._async_load(session, url, today)):
                _LOGGER.info("Tariff file for %s: %s", today.year, url)
                self._url = url
                return tariffs
        raise UpdateFailed(f"no tariff file in force on {today} found for this operator")
