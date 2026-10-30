"""Keeps a Swiss operator's tariff file, and its dynamic prices, up to date."""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CANTON,
    CONF_ELECTRICITY_TARIFF,
    CONF_GRID_TARIFF,
    CONF_MUNICIPALITY,
    CONF_MUNICIPALITY_NAME,
    CONF_OPERATOR_ID,
    CONF_OPERATOR_NAME,
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
    federal_addition,
    fee_applies,
    metering_per_month,
    missing_fees,
    parse_tariffs,
    regional_names,
    suggest_matching,
    tariffs_on,
    yearly_fee_as_monthly,
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
    # True while the operator's file cannot be downloaded and the last copy is used.
    offline_copy: bool = False


def tariff_file_store(hass: HomeAssistant, entry_id: str) -> Store[dict]:
    """The last tariff file read for an entry, kept for when the operator's site is down."""
    return Store(hass, 1, f"{DOMAIN}.tariff_file.{entry_id}")


@dataclass(frozen=True, slots=True)
class ElcomCheck:
    """What ElCom's household figures add to the file: federal charges and missing fees."""

    federal_per_kwh: float | None = None  # None: not checked, all charges are added
    other_fees_per_kwh: float = 0.0
    grid_monthly_base: float | None = None  # when the file gives the yearly fee as monthly
    metering_monthly: float = 0.0  # CHF without VAT, when the file leaves it out


def select_contract(
    tariffs: list[Tariff], options: dict, day: date, check: ElcomCheck | None = None
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
        # EKZ: three fees called "Gemeinde- und Kantonalabgaben", for ZH, for Menzingen
        # and for large consumers; the one for the user's place, whatever the file order.
        here = [
            t
            for t in tariffs_on(tariffs, "regional_fees", day)
            if t.name == name
            and fee_applies(t, municipality, municipality_name, canton_of(municipality))
        ]
        fee = here[0] if here else pick("regional_fees", name)
        if fee is not None and fee not in fees:  # two old names can lead to one fee
            fees.append(fee)
    electricity = pick("electricity", options[CONF_ELECTRICITY_TARIFF])
    grid = pick("grid", options[CONF_GRID_TARIFF])
    if electricity is None or grid is None:
        raise UnsupportedTariffError(f"no tariff of the operator is in force on {day}")
    if check is not None and check.grid_monthly_base is not None:
        grid = replace(grid, monthly_base=check.grid_monthly_base)
    return SwissContract(
        electricity=electricity,
        grid=grid,
        regional_fees=fees,
        canton=options.get(CONF_CANTON) or canton_of(municipality),
        municipality=municipality,
        municipality_name=municipality_name,
        federal_per_kwh=check.federal_per_kwh if check else None,
        other_fees_per_kwh=check.other_fees_per_kwh if check else 0.0,
        metering_monthly=check.metering_monthly if check else 0.0,
    )


def no_tariffs_issue_id(entry_id: str) -> str:
    """The Repairs issue raised while the operator has no tariffs in force."""
    return f"no_tariffs_in_force_{entry_id}"


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
        self._checks: dict[tuple, ElcomCheck] = {}
        self._file: tuple[list[Tariff], datetime, date] | None = None
        # The last file read (url, document), saved to disk when it changes.
        self._read: tuple[str, dict] | None = None
        self._saved: int | None = None
        self._store = tariff_file_store(hass, entry.entry_id)
        self._offline = False
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
                fetched = now
                tariffs = await self._async_load(session, self._url, today)
                try:
                    if tariffs is None:
                        # A new year, or the operator moved its file: ask ElCom again.
                        tariffs = await self._async_find_file(session, options, today)
                    self._offline = False
                    await self._async_save()
                except (UpdateFailed, ElcomError):
                    # The operator's site (or ElCom) does not answer: the last copy is
                    # still right if it has prices for today. Lausanne, 30 October 2026:
                    # "connection reset" for hours. Tried again at each refresh.
                    tariffs = await self._async_last_copy(today)
                    if tariffs is None:
                        raise
                    if not self._offline:
                        _LOGGER.warning(
                            "Tariff file not reachable, using the last copy: %s", self._url
                        )
                    self._offline = True
                    fetched = now - FILE_MAX_AGE
                self._file = (tariffs, fetched, today)
                issue_id = no_tariffs_issue_id(self.config_entry.entry_id)
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            tariffs = self._file[0]
            check = await self._async_elcom_check(session, options, today, tariffs)
            contract = select_contract(tariffs, options, today, check)
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
            federal_checked=check.federal_per_kwh is not None,
            offline_copy=self._offline,
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

    async def _async_elcom_check(
        self, session, options: dict, today: date, tariffs: list[Tariff]
    ) -> ElcomCheck:
        """Federal charges and missing fees for this contract, checked with ElCom once per
        file, year and choice of tariffs."""
        key = (
            self._url,
            today.year,
            options[CONF_GRID_TARIFF],
            tuple(regional_names(options.get(CONF_REGIONAL_TARIFF))),
        )
        if key in self._checks:
            return self._checks[key]
        try:
            operators = await async_operators_for(session, options[CONF_MUNICIPALITY], today.year)
        except ElcomError:
            return ElcomCheck()  # try again at the next refresh; meanwhile add all charges
        federal, other_fees, grid_base, metering = None, 0.0, None, 0.0
        options_contract = select_contract(tariffs, options, today)  # the user's tariffs
        for operator in operators:
            if operator.operator_id != options[CONF_OPERATOR_ID]:
                continue
            if operator.grid_h4_rp is not None and operator.aidfee_rp is not None:
                federal = federal_addition(
                    tariffs_on(tariffs, "grid", today),
                    operator.grid_h4_rp,
                    operator.aidfee_rp,
                    today.year,
                    chosen=options_contract.grid,
                    elcom_working_rp=operator.grid_working_rp,
                )
            grid_base = yearly_fee_as_monthly(options_contract.grid, operator.grid_fix_chf)
            grid = options_contract.grid
            if grid_base is not None:
                grid = replace(grid, monthly_base=grid_base)
            place = (
                options_contract.canton,
                options_contract.municipality,
                options_contract.municipality_name,
            )
            metering = metering_per_month(
                sum(t.base_for(*place) for t in (grid, *options_contract.regional_fees)),
                operator.grid_fix_chf,
                operator.metering_rp,
            )
            if operator.charge_rp is not None:
                other_fees = missing_fees(
                    options_contract.regional_fees,
                    options_contract.canton,
                    options_contract.municipality,
                    options_contract.municipality_name,
                    operator.charge_rp,
                    today.year,
                )
            break
        self._checks[key] = ElcomCheck(federal, other_fees, grid_base, metering)
        return self._checks[key]

    async def _async_load(self, session, url: str, today: date) -> list[Tariff] | None:
        """Tariffs from ``url`` if the file is readable and has tariffs in force today."""
        try:
            document = await async_fetch_tariff_document(session, url)
        except TariffFileError:
            return None
        tariffs = parse_tariffs(document)
        if not tariffs_on(tariffs, "electricity", today):
            return None
        self._read = (url, document)
        return tariffs

    async def _async_save(self) -> None:
        """Keep the file just read on disk, when it changed."""
        if self._read is None:
            return
        digest = hash(json.dumps(self._read[1], sort_keys=True))
        if digest != self._saved:
            await self._store.async_save({"url": self._read[0], "document": self._read[1]})
            self._saved = digest

    async def _async_last_copy(self, today: date) -> list[Tariff] | None:
        """The last file read (in memory, else on disk) if it has tariffs in force today."""
        if self._file is not None and tariffs_on(self._file[0], "electricity", today):
            return self._file[0]
        saved = await self._store.async_load()
        if not saved:
            return None
        tariffs = parse_tariffs(saved["document"])
        if not tariffs_on(tariffs, "electricity", today):
            return None  # a new year: Repairs explains it
        self._url = saved["url"]
        return tariffs

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
        # Usually the operator has not published next year's file yet (or ElCom still
        # links last year's): say so in Repairs. The next refreshes try again.
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            no_tariffs_issue_id(self.config_entry.entry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="no_tariffs_in_force",
            translation_placeholders={
                "operator": options.get(CONF_OPERATOR_NAME) or str(operator_id),
                "date": today.isoformat(),
            },
        )
        raise UpdateFailed(f"no tariff file in force on {today} found for this operator")


def _covers(segments: list[Segment], moment: datetime) -> bool:
    return any(s.start <= moment < s.end for s in segments)
