"""Keeps a Swiss operator's tariff file, and its dynamic prices, up to date."""

from __future__ import annotations

import logging
import zlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

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
    CONF_MUNICIPALITY_NAME,
    CONF_OPERATOR_ID,
    CONF_REGIONAL_TARIFF,
    CONF_TARIFF_URL,
    DOMAIN,
)
from .core.dynamic import DynamicTariffError, async_fetch_prices
from .core.elcom import (
    ElcomError,
    TariffFileError,
    async_fetch_tariff_document,
    async_operators_for,
    async_tariff_url_candidates,
)
from .core.schedule import Segment
from .core.switzerland import (
    SWISS_TZ,
    SwissContract,
    Tariff,
    UnsupportedTariffError,
    canton_of,
    combine_fees,
    federal_addition,
    parse_tariffs,
    regional_names,
    suggest_matching,
    tariffs_on,
)

_LOGGER = logging.getLogger(__name__)

# The tariff file is read twice a day. Dynamic prices for tomorrow come out
# between late morning and early evening (CKW about 11:20, Groupe E 14:50, EKZ
# 17:50), so from noon plus a minute of its own each installation checks every
# half hour until they are there; usually that is a few calls a day.
FILE_MAX_AGE = timedelta(hours=12)
UPDATE_INTERVAL = timedelta(minutes=30)
_TOMORROW_FROM = time(12, 0)


@dataclass(frozen=True, slots=True)
class SwissTariffData:
    """The operator's tariffs and the contract chosen from them for today."""

    tariffs: list[Tariff]
    contract: SwissContract
    source_url: str
    # True when the federal charges were checked against ElCom for this operator.
    federal_checked: bool = False


def select_contract(
    tariffs: list[Tariff], options: dict, day: date, federal_per_kwh: float | None = None
) -> SwissContract:
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

    municipality = options.get(CONF_MUNICIPALITY)
    municipality_name = options.get(CONF_MUNICIPALITY_NAME)
    fees: list[Tariff] = []
    for name in regional_names(options.get(CONF_REGIONAL_TARIFF)):
        # BKW gives the fees of each municipality the same name: take the user's.
        here = [
            t
            for t in tariffs_on(tariffs, "regional_fees", day)
            if t.name == name
            and t.municipality_key(municipality, municipality_name, canton_of(municipality))
            is not None
        ]
        fee = here[0] if here else pick("regional_fees", name)
        if fee is not None and fee not in fees:  # two old names can lead to one fee
            fees.append(fee)
    electricity = pick("electricity", options[CONF_ELECTRICITY_TARIFF])
    grid = pick("grid", options[CONF_GRID_TARIFF])
    if electricity is None or grid is None:
        raise UnsupportedTariffError(f"no tariff of the operator is in force on {day}")
    return SwissContract(
        electricity=electricity,
        grid=grid,
        regional_fees=combine_fees(fees),
        canton=options.get(CONF_CANTON) or canton_of(municipality),
        municipality=municipality,
        municipality_name=municipality_name,
        federal_per_kwh=federal_per_kwh,
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
        self._federal: dict[tuple[str, int, str], float | None] = {}
        self._file: tuple[list[Tariff], datetime, date] | None = None
        self._dynamic: dict[tuple[str, str], list[Segment]] = {}
        self._dynamic_attempt: dict[tuple[str, str], datetime] = {}
        # A stable minute per installation, 0-59, so not everyone calls at once.
        self._minute = zlib.crc32(entry.entry_id.encode()) % 60

    async def _async_update_data(self) -> SwissTariffData:
        options = {**self.config_entry.data, **self.config_entry.options}
        now = dt_util.utcnow()
        today = now.astimezone(SWISS_TZ).date()
        session = async_get_clientsession(self.hass)
        try:
            if self._file is None or now - self._file[1] >= FILE_MAX_AGE or self._file[2] != today:
                tariffs = await self._async_load(session, self._url, today)
                if tariffs is None:
                    # A new year, or the operator moved its file: ask ElCom again.
                    tariffs = await self._async_find_file(session, options, today)
                self._file = (tariffs, now, today)
            tariffs = self._file[0]
            federal = await self._async_federal(session, options, today, tariffs)
            contract = select_contract(tariffs, options, today, federal)
        except (ElcomError, UnsupportedTariffError) as err:
            raise UpdateFailed(str(err)) from err
        if contract.dynamic_tariffs:
            contract = contract.with_dynamic_prices(
                await self._async_dynamic(session, contract, now)
            )
        return SwissTariffData(
            tariffs=tariffs,
            contract=contract,
            source_url=self._url,
            federal_checked=federal is not None,
        )

    async def _async_dynamic(
        self, session, contract: SwissContract, now: datetime
    ) -> dict[str, list[Segment]]:
        """Today's and, once published, tomorrow's prices of the dynamic tariffs."""
        local = now.astimezone(SWISS_TZ)
        midnight = datetime.combine(local.date(), time(0, 0), SWISS_TZ)
        day_after = datetime.combine(local.date() + timedelta(days=2), time(0, 0), SWISS_TZ)
        tomorrow_noon = datetime.combine(
            local.date() + timedelta(days=1), time(12, 0), SWISS_TZ
        ).astimezone(UTC)
        tomorrow_due = local >= datetime.combine(
            local.date(), _TOMORROW_FROM, SWISS_TZ
        ) + timedelta(minutes=self._minute)
        prices: dict[str, list[Segment]] = {}
        for tariff in contract.dynamic_tariffs:
            assert tariff.dynamic_url is not None  # checked by check_supported
            key = (tariff.dynamic_url, tariff.tariff_type)
            known = [s for s in self._dynamic.get(key, []) if s.end > midnight]
            need_today = not _covers(known, now)
            need_tomorrow = tomorrow_due and not _covers(known, tomorrow_noon)
            last = self._dynamic_attempt.get(key)
            if need_today or (need_tomorrow and (last is None or now - last >= UPDATE_INTERVAL)):
                self._dynamic_attempt[key] = now
                try:
                    fresh = await async_fetch_prices(
                        session, tariff.dynamic_url, tariff.tariff_type, midnight, day_after
                    )
                except DynamicTariffError as err:
                    if need_today:
                        raise UpdateFailed(f"{tariff.name}: dynamic prices: {err}") from err
                    _LOGGER.debug("Tomorrow's prices of %s not available yet: %s", tariff.name, err)
                else:
                    by_start = {s.start: s for s in known} | {s.start: s for s in fresh}
                    known = [by_start[start] for start in sorted(by_start)]
            if not _covers(known, now):
                raise UpdateFailed(f"{tariff.name}: no dynamic price published for now")
            self._dynamic[key] = known
            prices[tariff.tariff_type] = known
        return prices

    async def _async_federal(
        self, session, options: dict, today: date, tariffs: list[Tariff]
    ) -> float | None:
        """Federal charges to add for this operator, checked with ElCom once per file and year."""
        key = (self._url, today.year, options[CONF_GRID_TARIFF])
        if key in self._federal:
            return self._federal[key]
        try:
            operators = await async_operators_for(session, options[CONF_MUNICIPALITY], today.year)
        except ElcomError:
            return None  # try again at the next refresh; meanwhile add all charges
        federal = None
        options_contract = select_contract(tariffs, options, today)  # the user's grid tariff
        for operator in operators:
            if (
                operator.operator_id == options[CONF_OPERATOR_ID]
                and operator.grid_h4_rp is not None
                and operator.aidfee_rp is not None
            ):
                federal = federal_addition(
                    tariffs_on(tariffs, "grid", today),
                    operator.grid_h4_rp,
                    operator.aidfee_rp,
                    today.year,
                    chosen=options_contract.grid,
                )
                break
        self._federal[key] = federal
        return federal

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


def _covers(segments: list[Segment], moment: datetime) -> bool:
    return any(s.start <= moment < s.end for s in segments)
