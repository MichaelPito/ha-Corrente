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
            tariffs = parse_tariffs(await async_fetch_tariff_document(session, self._url))
            if not tariffs_on(tariffs, "electricity", today):
                # New year: ElCom links each year's file separately.
                tariffs = await self._async_follow_new_year(session, options, today.year)
            contract = select_contract(tariffs, options, today)
        except (TariffFileError, ElcomError, UnsupportedTariffError) as err:
            raise UpdateFailed(str(err)) from err
        return SwissTariffData(tariffs=tariffs, contract=contract, source_url=self._url)

    async def _async_follow_new_year(self, session, options: dict, year: int) -> list[Tariff]:
        operators = await async_operators_for(session, options[CONF_MUNICIPALITY], year)
        for operator in operators:
            if operator.operator_id == options[CONF_OPERATOR_ID] and operator.tariff_url:
                self._url = operator.tariff_url
                return parse_tariffs(await async_fetch_tariff_document(session, self._url))
        raise TariffFileError(f"no tariff file published for {year} yet")
