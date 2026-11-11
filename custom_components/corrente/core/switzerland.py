"""Swiss grid-operator tariffs in the VSE "Tariff Retrieval API" format.

Every Swiss grid operator must publish its tariffs as JSON in this format
(Art. 7b para. 1 StromVV); ElCom lists the link for each operator. Prices in
the files exclude VAT. Pure Python, no Home Assistant imports.

Spec: https://tariffconverter.strom.ch/ch-electricity-tariffs-openapi.yml
"""

from __future__ import annotations

import logging
import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any
from zoneinfo import ZoneInfo

from .dynamic import api_host, is_api_url
from .schedule import Segment

_LOGGER = logging.getLogger(__name__)

SWISS_TZ = ZoneInfo("Europe/Zurich")
SWISS_VAT = 0.081

# Federal per-kWh charges that operators' grid tariffs do not include, in CHF/kWh
# without VAT: grid surcharge (Art. 35 EnG), electricity reserve, Swissgrid general
# system services and solidarised transmission costs. Sources in docs/FONTI-DATI.md;
# the 2027 sum matches ElCom's published totals for AIL and AMB.
# The federal grid surcharge (Art. 35 EnG), part of the national charges, CHF/kWh.
GRID_SURCHARGE = 0.0230
NATIONAL_CHARGES: Mapping[int, float] = {
    2026: 0.0230 + 0.0041 + 0.0027 + 0.0005,
    2027: 0.0230 + 0.0017 + 0.0019 + 0.0019,
}

_WEEKDAYS = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6}
_MONTHS = {
    name: number
    for number, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        start=1,
    )
}
_KWH = "CHF/kWh"
_END_OF_DAY = time(23, 59)


class UnsupportedTariffError(ValueError):
    """The tariff cannot be priced from its static description."""


# ElCom's "grid usage" component includes the federal charges except the grid
# surcharge, which ElCom lists separately ("aidfee").
_H4_KWH_PER_YEAR = 4500
_MAX_FEES_COMBINED = 8  # beyond, only one fee or all of them are tried
# The federal-charge hypotheses are 0.73 and 2.3 Rp. apart: within this, one clearly fits.
_CLEAR_FIT_RP = 0.6
_CLOSE_FIT_RP = 1.0
_CLEAR_MARGIN_RP = 0.5
# A suggested grid tariff further than this from ElCom's household figure is unlikely.
_PLAUSIBLE_GRID_RP = 1.5
# Fees this far below ElCom's are taken to be missing from the file.
_MISSING_FEES_RP = 0.3
_SAME_RP = 0.05
_SAME_FEE_CHF = 6.0  # CHF a year: fixed fees this close are the same


# Dynamic tariffs whose file names no API although the operator publishes one, keyed
# by the file's "dsoName", the tariff's name and year. Primeo's 2026 file writes "URL
# wird auf der Webseite … bekannt gegeben"; the API answers with this tariff's prices
# (checked on 26 October 2026). See docs/FONTI-DATI.md.
KNOWN_DYNAMIC_URLS: dict[tuple[str, str, int], str] = {
    ("Primeo Energie", "Primeo NetzDynamisch", 2026): (
        "https://tarife.primeo-energie.ch/api/v1/tariffs"
    ),
}

# APIs whose grid prices hold the federal charges although the operator's other grid
# tariffs leave them out. Primeo, 1-25 October 2026: every one of 2404 quarter-hour
# prices is a whole number of Rp. plus 3.03, the 2026 federal charges.
_DYNAMIC_GRID_WITH_FEDERAL_CHARGES = {"tarife.primeo-energie.ch"}


def grid_includes_federal_charges(grid: Tariff) -> bool:
    """Whether a dynamic grid tariff's API prices already hold the federal charges."""
    return grid.is_dynamic and api_host(grid.dynamic_url) in _DYNAMIC_GRID_WITH_FEDERAL_CHARGES


def federal_addition(
    grid_tariffs: Sequence[Tariff],
    elcom_grid_rp: float,
    elcom_aidfee_rp: float,
    year: int,
    chosen: Tariff | None = None,
    *,
    elcom_working_rp: float | None = None,
) -> float | None:
    """How much federal charge to add on top of an operator's grid tariff, in CHF/kWh.

    Operators differ: AIL and ewb leave all federal charges out of their grid
    tariffs, EKZ includes them. ElCom publishes what a household (profile H4,
    4500 kWh/year) pays for grid usage, so the operator's flat grid tariffs are
    compared with ElCom under three hypotheses — nothing included (add all),
    everything but the grid surcharge included (add the surcharge), everything
    included (add nothing) — and the best match wins. None if no flat grid
    tariff is available to compare.

    The comparison uses, in order: the user's own grid tariff if it is flat
    (EKZ households: "400F"), the operator's flagged standard tariffs, flat
    tariffs for the same customers as the user's (same customer group, else
    same monthly fee), the user's own tariff even if it is not flat, then all
    flat grid tariffs. An operator can have
    products that match different hypotheses (EKZ "400LS" for businesses), so
    the closest to the user's tariff comes first: with a dynamic or day/night
    grid tariff, Groupe E's business tariffs once pointed to the wrong answer.

    Some operators have only day/night grid tariffs (ewz, which includes the
    charges): then the same order applies to those, each priced at its average
    over the year, every hour counting the same. ElCom's household uses more by
    day, so that average is a little low; the three hypotheses are 2-3 Rp.
    apart, much more than that difference.

    With ``elcom_working_rp`` (ElCom's grid price per kWh without the monthly fee
    and the federal charges) only prices per kWh are compared, leaving the monthly
    fees out: some files give a yearly fee as monthly (Spreitenbach: 66 CHF "a
    month", ElCom: 66 CHF a year), which made a 2.85 Rp. difference look like one
    of the hypotheses.
    """
    if chosen is not None and grid_includes_federal_charges(chosen):
        return 0.0
    with_base = elcom_working_rp is None
    if with_base:
        target = elcom_grid_rp + elcom_aidfee_rp  # what ElCom says grid costs, all charges in
    else:
        target = elcom_working_rp + 100 * national_charges(year)
    candidates = (national_charges(year), elcom_aidfee_rp / 100, 0.0)

    # The user's own tariff first, day/night too, when one hypothesis clearly fits:
    # ebs (Schwyz) and AIM (Mendrisio) have no flat household grid tariff, only
    # flat ones for building sites, which pointed to the wrong hypothesis.
    if chosen is not None:
        fits = [
            (abs(rp + 100 * addition - target), addition)
            for rp in _grid_rp(chosen, year, with_base)
            for addition in candidates
        ]
        fits.sort()
        if fits and (
            fits[0][0] <= _CLEAR_FIT_RP
            # A day/night average is a little low (see below), up to 0.7 Rp. at ebs:
            # still clear when the next hypothesis is much further away.
            or (fits[0][0] <= _CLOSE_FIT_RP and fits[1][0] - fits[0][0] >= _CLEAR_MARGIN_RP)
        ):
            return fits[0][1]

    def is_flat(tariff: Tariff) -> bool:
        return bool(tariff.energy) and all(w.every_day for w in tariff.energy)

    def is_priced(tariff: Tariff) -> bool:
        return bool(tariff.energy) and not tariff.is_dynamic

    pool = [t for t in grid_tariffs if is_flat(t)] or [t for t in grid_tariffs if is_priced(t)]
    choices = [[t for t in pool if t.standard]]
    if chosen is not None:
        choices = [
            [chosen] if chosen in pool else [],
            *choices,
            [t for t in pool if chosen.customer_type and t.customer_type == chosen.customer_type],
            [t for t in pool if t.monthly_base == chosen.monthly_base],
            # Then the user's own tariff even if not flat, rather than another
            # customer's: ebs's only flat grid tariff in 2027 is for building sites,
            # with a 90 CHF monthly fee, and pointed to "everything included".
            [chosen] if is_priced(chosen) else [],
        ]
    compared = next((group for group in choices if group), pool)
    if not compared:
        return None
    grid_rp = [rp for tariff in compared for rp in _grid_rp(tariff, year, with_base)]
    best_addition, best_error = None, None
    for addition in candidates:
        for rp in grid_rp:
            error = abs(rp + 100 * addition - target)
            if best_error is None or error < best_error:
                best_addition, best_error = addition, error
    return best_addition


def _grid_rp(tariff: Tariff, year: int, with_base: bool = True) -> list[float]:
    """A grid tariff's average price (with its monthly fee), in Rp./kWh; empty if unpriced."""
    if not tariff.energy or tariff.is_dynamic:
        return []
    try:
        average = _average_price(tariff.energy, year)
    except UnsupportedTariffError:
        return []
    base = tariff.monthly_base * 12 / _H4_KWH_PER_YEAR if with_base else 0.0
    return [100 * (average + base)]


def _average_price(windows: Sequence[PriceWindow], year: int) -> float:
    """Average price per kWh over a year, every hour counting the same.

    Windows repeat every week within a month, so one week per month is enough.
    """
    if all(w.every_day and w.months is None for w in windows):
        return sum(w.price for w in windows)  # flat: no need to walk the year
    hours = [
        datetime(year, month, 1, 0, 30) + timedelta(hours=n)
        for month in range(1, 13)
        for n in range(7 * 24)
    ]
    return sum(price_of_windows(windows, moment)[0] for moment in hours) / len(hours)


def h4_grid_error(
    grid: Tariff,
    elcom_grid_rp: float,
    elcom_aidfee_rp: float,
    year: int,
    elcom_working_rp: float | None = None,
) -> float | None:
    """How far a grid tariff is from ElCom's household figure, in Rp./kWh.

    The best of the three federal-charge hypotheses (see federal_addition, also for
    ``elcom_working_rp``); None for a tariff that cannot be priced from the file.
    """
    with_base = elcom_working_rp is None
    if with_base:
        target = elcom_grid_rp + elcom_aidfee_rp
    else:
        target = elcom_working_rp + 100 * national_charges(year)
    additions = (100 * national_charges(year), elcom_aidfee_rp, 0.0)
    errors = [
        abs(rp + addition - target)
        for rp in _grid_rp(grid, year, with_base)
        for addition in additions
    ]
    return min(errors, default=None)


def national_charges(year: int) -> float:
    """Return the federal per-kWh charges for a year (latest known year if unknown)."""
    if year in NATIONAL_CHARGES:
        return NATIONAL_CHARGES[year]
    return NATIONAL_CHARGES[max(NATIONAL_CHARGES)]


@dataclass(frozen=True, slots=True)
class PriceWindow:
    """A price that applies in some months, on some weekdays, between two times."""

    price: float
    start: time = time(0, 0)
    end: time | None = None  # None: until the end of the day
    months: frozenset[int] | None = None  # None: every month
    weekdays: frozenset[int] | None = None  # None: every day, 0 = Monday

    @property
    def all_day(self) -> bool:
        """True when the window covers whole days."""
        return self.start == time(0, 0) and self.end is None

    @property
    def every_day(self) -> bool:
        """True for a price that applies all day on every day of the week.

        Such prices add up with the others (a surcharge on top of the energy
        price), when they also apply in every month (see price_of_windows). A whole
        day on some weekdays only is one of the alternatives: ewz's grid tariff is
        06:00-22:00 and 22:00-06:00 Monday to Saturday, and the whole of Sunday.
        """
        return self.all_day and self.weekdays is None

    def covers(self, local: datetime) -> bool:
        """Return whether the window applies at a Swiss local time."""
        if self.months is not None and local.month not in self.months:
            return False
        if self.weekdays is not None and local.weekday() not in self.weekdays:
            return False
        moment = local.time().replace(tzinfo=None)
        if self.end is None:
            return moment >= self.start
        if self.start < self.end:
            return self.start <= moment < self.end
        # A window that wraps past midnight, e.g. 22:00-06:00.
        return moment >= self.start or moment < self.end

    def boundaries(self) -> tuple[time, ...]:
        """Times of day at which this window starts or stops applying."""
        return (self.start,) if self.end is None else (self.start, self.end)


def _parse_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _parse_window(raw: Mapping[str, Any]) -> PriceWindow | None:
    """Parse a TimeBasedPrice; return None for prices that are not per kWh."""
    if raw.get("priceUnit") != _KWH:
        return None
    start = _parse_time(raw["from"])
    end = _parse_time(raw["to"])
    months = raw.get("months") or None
    weekdays = raw.get("weekdays") or None
    return PriceWindow(
        price=float(raw["price"]),
        start=start,
        # "23:59" and "00:00" as end times mean the end of the day, so
        # "00:00"-"00:00" is a whole day. "22:00"-"06:00" wraps past midnight.
        end=None if end in (_END_OF_DAY, time(0, 0)) else end,
        # All twelve months or all seven days (EKZ lists them) is no restriction.
        months=_restriction({_MONTHS[m] for m in months} if months else None, 12),
        weekdays=_restriction({_WEEKDAYS[d] for d in weekdays} if weekdays else None, 7),
    )


def _restriction(values: set[int] | None, every: int) -> frozenset[int] | None:
    return None if values is None or len(values) == every else frozenset(values)


def _parse_date(text: str) -> date:
    """A tariff's start or end date; BKW writes "2027-01-01T00:00:00"."""
    return date.fromisoformat(text[:10])


def _windows(raws: Iterable[Mapping[str, Any]] | None) -> tuple[PriceWindow, ...]:
    windows = [w for w in (_parse_window(raw) for raw in raws or ()) if w is not None]
    # A price of 1 CHF/kWh or more is a price in Rp. written as CHF: Yverdon's file
    # gives its 2 Rp. municipal fee as 2 CHF/kWh, Romande Energie's 2027 file one of
    # the "Double" grid prices as 10.62 CHF/kWh (ElCom: about 12 Rp. in all).
    windows = [replace(w, price=w.price / 100) if w.price >= 1 else w for w in windows]
    # A single rate written as a high/low tariff with the same price twice (Gsteig,
    # Egerkingen, Glarus 2027): when every window comes the same number of times,
    # keep one of each. Repeated surcharges next to other windows still add up.
    counts = Counter(windows)
    if len(set(counts.values())) == 1 and next(iter(counts.values())) > 1:
        windows = list(dict.fromkeys(windows))
    # Some operators give the last minute included: ewz writes "06:00"-"21:59" and
    # "22:00"-"05:59". Read as up to 22:00 and 06:00, unless a window starts at :59.
    starts = {window.start for window in windows}
    return tuple(
        replace(window, end=_next_minute(window.end))
        if window.end is not None and window.end.minute == 59 and window.end not in starts
        else window
        for window in windows
    )


def _without_single_rate_alternative(windows: tuple[PriceWindow, ...]) -> tuple[PriceWindow, ...]:
    """Drop an all-day price that is the single-rate version of a day/night tariff.

    St. Gallen's "Netztarif K" 2026 gives the day and night prices (13.73 and 11.83
    Rp.) and, in the same tariff, the single-rate price (13.13 Rp.) as an all-day
    window. All-day prices otherwise add up (AIL's 0.6 Rp. "tìacqua" surcharge),
    which would double the price; a surcharge is never between the tariff's own
    lowest and highest timed price.
    """
    timed = [w.price for w in windows if not w.every_day]
    if not timed:
        return windows
    low, high = min(timed), max(timed)
    # Only an all-year price: a summer-only all-day price is a season of its own.
    return tuple(
        w for w in windows if not (w.every_day and w.months is None and low <= w.price <= high)
    )


def _next_minute(value: time) -> time | None:
    following = (datetime.combine(date(2000, 1, 1), value) + timedelta(minutes=1)).time()
    return None if following == time(0, 0) else following


@dataclass(frozen=True, slots=True)
class Tariff:
    """One tariff of an operator: energy, grid, metering or regional fees."""

    name: str
    tariff_type: str
    form: str
    start_date: date
    end_date: date
    customer_type: str
    energy: tuple[PriceWindow, ...]
    monthly_base: float
    canton_energy: Mapping[str, tuple[PriceWindow, ...]] = field(default_factory=dict)
    municipality_energy: Mapping[int, tuple[PriceWindow, ...]] = field(default_factory=dict)
    # BKW numbers municipalities its own way ("15040 Ittigen", federal number 362),
    # so fees are also found by the municipality's name.
    municipality_names: Mapping[str, int] = field(default_factory=dict)
    # Monthly fees by canton and municipality (OIKEN's municipal fee has one, CHF/month).
    canton_base: Mapping[str, float] = field(default_factory=dict)
    municipality_base: Mapping[int, float] = field(default_factory=dict)
    dynamic_url: str | None = None
    standard: bool = False  # the operator's flagged standard tariff (standardBasegroup)

    def valid_on(self, day: date) -> bool:
        """Return whether the tariff is in force on a day."""
        return self.start_date <= day <= self.end_date

    def windows_for(
        self,
        canton: str | None = None,
        municipality: int | None = None,
        municipality_name: str | None = None,
    ) -> tuple[PriceWindow, ...]:
        """Per-kWh windows, including the canton's and municipality's surcharges."""
        windows = list(self.energy)
        if canton is not None:
            windows.extend(self.canton_energy.get(canton, ()))
        key = self.municipality_key(municipality, municipality_name, canton)
        if key is not None:
            windows.extend(self.municipality_energy[key])
        return tuple(windows)

    def base_for(
        self,
        canton: str | None = None,
        municipality: int | None = None,
        municipality_name: str | None = None,
    ) -> float:
        """Monthly fee in CHF, including the canton's and municipality's."""
        base = self.monthly_base
        if canton is not None:
            base += self.canton_base.get(canton, 0.0)
        key = self.municipality_key(municipality, municipality_name, canton)
        if key is not None:
            base += self.municipality_base.get(key, 0.0)
        return base

    def municipality_key(
        self, number: int | None, name: str | None = None, canton: str | None = None
    ) -> int | None:
        """The key of a municipality's surcharges: its number, else its name, else its
        canton's number and name (EWO lists "6 Obwalden" for the whole canton); None if
        absent."""
        if number in self.municipality_energy:
            return number
        for spelling in _name_spellings(name):
            if (key := self.municipality_names.get(spelling)) is not None:
                return key
        whole_canton = canton_number(canton)
        if whole_canton is not None:
            for listed, key in self.municipality_names.items():
                if key == whole_canton and listed in _CANTON_NAMES.get(canton or "", ()):
                    return key
        return None

    @property
    def is_dynamic(self) -> bool:
        """Priced per quarter hour by the operator's API (see core/dynamic.py)."""
        return self.form == "dynamic"

    def check_supported(self) -> None:
        """Raise if the tariff cannot be priced from the file and the operator's API."""
        if self.is_dynamic and not is_api_url(self.dynamic_url):
            raise UnsupportedTariffError(f"{self.name}: dynamic tariff without an API")
        # Several whole-day prices at the same time for a tiered tariff means the
        # daily windows were not encoded (seen in AMB "Dinamica" 2027). Whole-day
        # prices for different months are fine: EKZ "Erneuerbar" 2026 has a winter
        # and a summer price.
        # Whole-year prices next to a complete set of seasonal ones are surcharges
        # (Herzogenbuchsee's grid: winter and summer prices, plus three small charges).
        seasonal = [w for w in self.energy if w.all_day and w.months is not None]
        seasons_cover_the_year = set().union(*(w.months for w in seasonal)) == set(range(1, 13))
        if (
            self.form == "multilevel"
            and len(self.energy) > 1
            and all(window.all_day for window in self.energy)
            and not seasons_cover_the_year
            and any(
                _same_days(first, second)
                for n, first in enumerate(self.energy)
                for second in self.energy[n + 1 :]
            )
        ):
            raise UnsupportedTariffError(f"{self.name}: time windows missing")
        # Timed windows that overlap at different prices, with no way to tell which
        # applies (Merenschwand 2027 left out the months of its winter and summer prices).
        try:
            for moment in _sample_moments(self.energy):
                price_of_windows(self.energy, moment)
        except UnsupportedTariffError as err:
            raise UnsupportedTariffError(f"{self.name}: {err}") from err


def _sample_moments(windows: Sequence[PriceWindow]) -> list[datetime]:
    """Moments that meet every combination of windows: each window boundary, on each
    weekday of a week in each month (only for tariffs with timed windows)."""
    if all(w.every_day for w in windows):
        return []
    times = sorted({t for w in windows for t in w.boundaries()} | {time(0, 0)})
    moments = []
    for month in range(1, 13):
        first = date(2027, month, 1)
        for offset in range(7):
            day = first + timedelta(days=offset)
            moments.extend(datetime.combine(day, t, SWISS_TZ) for t in times)
    return moments


def _same_days(first: PriceWindow, second: PriceWindow) -> bool:
    """True when two windows apply on some of the same days."""

    def meet(a: frozenset[int] | None, b: frozenset[int] | None) -> bool:
        return a is None or b is None or bool(a & b)

    return meet(first.months, second.months) and meet(first.weekdays, second.weekdays)


# Household grid tariffs written ten times too high in an operator's file (0.82 CHF/kWh
# for 8.2 Rp.), checked against ElCom's grid price for the same operator and year.
# Keyed by the file's "dsoName", the tariff's name and year. See docs/FONTI-DATI.md.
KNOWN_TENFOLD_PRICES: frozenset[tuple[str, str, int]] = frozenset(
    {
        ("EW Rothrist AG", "EWR.Netz S", 2026),  # ElCom 8.2 Rp.
        ("EW Rothrist AG", "EWR.Netz S flex", 2026),
        ("TB Vilters-Wangs", "Haushalt Basis N", 2026),  # ElCom 7.95 Rp.
        ("TB Vilters-Wangs", "Haushalt Flex N", 2026),
        ("TB Vilters-Wangs", "Haushalt Flex mit Flexbonus N", 2026),
    }
)


def parse_tariffs(document: Mapping[str, Any]) -> list[Tariff]:
    """Parse a VSE tariff document, skipping entries that cannot be read.

    Real files have broken entries (BKW 2026: municipality "#N/A"); one bad
    entry must not hide the operator's other tariffs.
    """
    tariffs = []
    for raw in document.get("tariffs", ()):
        try:
            tariff = _parse_tariff(raw)
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Skipping unreadable tariff %s: %s", raw.get("tariffName"), err)
            continue
        key = (document.get("dsoName"), tariff.name, tariff.start_date.year)
        if tariff.is_dynamic and not is_api_url(tariff.dynamic_url) and key in KNOWN_DYNAMIC_URLS:
            tariff = replace(tariff, dynamic_url=KNOWN_DYNAMIC_URLS[key])
        if key in KNOWN_TENFOLD_PRICES:
            tariff = replace(
                tariff, energy=tuple(replace(w, price=w.price / 10) for w in tariff.energy)
            )
        tariffs.append(tariff)
    return tariffs


# Federal charges, as operators name them in their comments (de, fr, it).
_FEDERAL_CHARGE = re.compile(
    r"netzzuschlag|systemdienstleistung|stromreserve|solidarisierte"
    r"|suppl[ée]ment (de )?r[ée]seau|services? syst[èe]me|r[ée]serve d.[ée]lectricit[ée]"
    r"|co[ûu]ts solidaris|supplemento (di )?rete|servizi di sistema|riserva di energia"
    r"|costi solidali",
    re.IGNORECASE,
)


# A fee for consumption above a threshold: "ab 101'000 kWh", "dès 100 MWh", "oltre ...".
_LARGE_CONSUMER = re.compile(
    r"\b(ab|über|uber|dès|des|plus de|au-delà de|oltre|da|sopra)\s*[\d'’ .,]+\s*[km]wh",
    re.IGNORECASE,
)


_SMALL_CONSUMER = re.compile(r"\b(bis|jusqu.?à|fino a|up to)\s*[\d'’ .,]+\s*[km]wh", re.IGNORECASE)


def _is_large_consumer(comment: object) -> bool:
    """True for a fee tier for large consumers only; a household is in the first tier.

    Winterthur gives its municipal fee as 0.9 Rp. "bis 100'000 kWh" and 0.6 Rp.
    "ab 101'000 kWh": both would otherwise add up. A comment describing both tiers
    of one price (AIM: "fino a 500 MWh ... oltre 500 MWh") is the household's.
    """
    return (
        isinstance(comment, str)
        and _LARGE_CONSUMER.search(comment) is not None
        and _SMALL_CONSUMER.search(comment) is None
    )


# "ohne Netzzuschlag", "hors supplément réseau": a local fee that says what it excludes.
_EXCLUDING = re.compile(r"\b(ohne|exkl|excl|hors|sans|senza|escl)\w*\.?\W*$", re.IGNORECASE)


def _is_federal_charge(comment: object) -> bool:
    """True for a fee that is a federal charge (Energie Thun lists them as cantonal fees).

    Corrente adds the federal charges itself, checked with ElCom (federal_addition),
    so such a fee would count them twice.
    """
    if not isinstance(comment, str):
        return False
    return any(
        not _EXCLUDING.search(comment[max(0, match.start() - 20) : match.start()])
        for match in _FEDERAL_CHARGE.finditer(comment)
    )


def _monthly(raw: Mapping[str, Any] | None) -> float:
    """A monthly fee in CHF; 0 for other units."""
    raw = raw or {}
    return float(raw.get("price") or 0) if raw.get("priceUnit") == "CHF/M" else 0.0


def _parse_tariff(raw: Mapping[str, Any]) -> Tariff:
    prices = raw.get("prices") or {}
    canton_energy: dict[str, list[PriceWindow]] = {}
    canton_base: dict[str, float] = {}
    municipality_base: dict[int, float] = {}
    for tax in prices.get("cantonalTaxes") or ():
        if _is_federal_charge(tax.get("cantonComment")) or _is_large_consumer(
            tax.get("cantonComment")
        ):
            continue
        canton_energy.setdefault(tax["cantonName"], []).extend(_windows(tax.get("cantonEnergy")))
        if monthly := _monthly(tax.get("cantonBase")):
            canton_base[tax["cantonName"]] = canton_base.get(tax["cantonName"], 0.0) + monthly
    municipality_energy: dict[int, list[PriceWindow]] = {}
    municipality_names: dict[str, int] = {}
    for tax in prices.get("municipalityTaxes") or ():
        number = str(tax.get("municipalityNumber", ""))
        comment = tax.get("municipalityComment")
        if not number.isdigit() or _is_federal_charge(comment) or _is_large_consumer(comment):
            continue  # "#N/A" in BKW's file
        municipality_energy.setdefault(int(number), []).extend(
            _windows(tax.get("municipalityEnergy"))
        )
        if monthly := _monthly(tax.get("municipalityBase")):
            municipality_base[int(number)] = municipality_base.get(int(number), 0.0) + monthly
        if name := str(tax.get("municipalityName") or "").strip():
            municipality_names.setdefault(name.casefold(), int(number))
    return Tariff(
        name=raw["tariffName"],
        tariff_type=raw["tariffType"],
        form=raw.get("tariffForm", "constant"),
        start_date=_parse_date(raw["startDate"]),
        end_date=_parse_date(raw["endDate"]),
        customer_type=raw.get("customerType", ""),
        energy=_without_single_rate_alternative(_windows(prices.get("energy"))),
        monthly_base=_monthly(prices.get("base")),
        canton_energy={k: tuple(v) for k, v in canton_energy.items()},
        municipality_energy={k: tuple(v) for k, v in municipality_energy.items()},
        municipality_names=municipality_names,
        canton_base=canton_base,
        municipality_base=municipality_base,
        dynamic_url=(prices.get("dynamic") or {}).get("url"),
        standard=bool(raw.get("standardBasegroup")),
    )


def price_of_windows(windows: Sequence[PriceWindow], local: datetime) -> tuple[float, bool]:
    """Price per kWh at a moment and whether a gap in the schedule was filled.

    Whole-day prices add up (a green surcharge on top of the energy price).
    At most one timed window applies at once. If the timed windows ever leave a
    gap, the cheapest timed price is used (in Swiss high/low tariffs uncovered
    hours are the night) and the gap is reported so the UI can flag it.
    """

    # Only a price for every day of the year is a surcharge. A whole day in some months
    # is a season, one of the alternatives: Uznach's grid is 12.45 Rp. all day from
    # October to March and by the clock from April to September (its winter counted
    # twice up to 0.3.13).
    def surcharge(w: PriceWindow) -> bool:
        return w.every_day and w.months is None

    whole_day = sum(w.price for w in windows if surcharge(w) and w.covers(local))
    timed = [w for w in windows if not surcharge(w)]
    if not timed:
        return whole_day, False
    matching = [w for w in timed if w.covers(local)]
    if len(matching) > 1:
        matching = _narrowest(matching)
    if matching:
        return whole_day + matching[0].price, False
    return whole_day + min(w.price for w in timed), True


def _narrowest(matching: list[PriceWindow]) -> list[PriceWindow]:
    """The one window that applies when several timed windows cover the same moment.

    Same price: no conflict (Diessenhofen gives Saturday as a whole day and as
    07:00-13:00, at one price). A window for part of a day inside a whole day wins:
    Dietlikon's grid is 7.22 Rp. on Saturday 07:00-13:00 and 5.48 the rest of Saturday,
    written as the whole of Saturday. Anything else cannot be priced.
    """
    if len({w.price for w in matching}) == 1:
        return matching[:1]
    parts = [w for w in matching if not w.all_day]
    if len(parts) == 1:
        return parts
    raise UnsupportedTariffError("overlapping time windows")


class PriceNotPublishedError(LookupError):
    """A dynamic tariff has no published price for that moment (yet)."""


@dataclass(frozen=True, slots=True)
class SwissContract:
    """The tariffs that make up a household's per-kWh price."""

    electricity: Tariff
    grid: Tariff
    # One fee tariff or several (Lausanne publishes each fee on its own); always a
    # tuple after construction. Each is priced on its own schedule, then added up.
    regional_fees: Tariff | Sequence[Tariff] | None = None
    canton: str | None = None
    municipality: int | None = None
    municipality_name: str | None = None
    # Federal charges to add per kWh; None: all of them (see federal_addition).
    federal_per_kwh: float | None = None
    # Cantonal and municipal fees ElCom counts and the file leaves out, CHF/kWh
    # (see missing_fees).
    other_fees_per_kwh: float = 0.0
    # Metering fee per month, CHF without VAT, when the file's fees leave it out
    # (see metering_per_month).
    metering_monthly: float = 0.0
    # Published per-kWh prices of the dynamic tariffs (CHF without VAT, UTC),
    # by tariff type ("electricity", "grid"); see core/dynamic.py.
    dynamic: Mapping[str, tuple[Segment, ...]] = field(default_factory=dict)
    _starts: Mapping[str, list[datetime]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        fees = self.regional_fees
        object.__setattr__(
            self,
            "regional_fees",
            () if fees is None else (fees,) if isinstance(fees, Tariff) else tuple(fees),
        )
        for tariff in self._tariffs():
            tariff.check_supported()
        object.__setattr__(
            self,
            "_starts",
            {kind: [s.start for s in segments] for kind, segments in self.dynamic.items()},
        )

    def _tariffs(self) -> list[Tariff]:
        return [self.electricity, self.grid, *self.regional_fees]

    def _windows(self) -> tuple[PriceWindow, ...]:
        return tuple(
            window
            for tariff in self._tariffs()
            for window in tariff.windows_for(self.canton, self.municipality, self.municipality_name)
        )

    @property
    def dynamic_tariffs(self) -> list[Tariff]:
        """The tariffs whose price comes from the operator's API."""
        return [tariff for tariff in self._tariffs() if tariff.is_dynamic]

    def with_dynamic_prices(self, prices: Mapping[str, Sequence[Segment]]) -> SwissContract:
        """The same contract with newly downloaded dynamic prices."""
        return replace(
            self,
            dynamic={
                kind: tuple(sorted(segments, key=lambda s: s.start))
                for kind, segments in prices.items()
            },
        )

    @property
    def known_until(self) -> datetime | None:
        """When the published dynamic prices end; None without dynamic tariffs."""
        if not self.dynamic_tariffs:
            return None
        ends = []
        for tariff in self.dynamic_tariffs:
            segments = self.dynamic.get(tariff.tariff_type)
            if not segments:
                return datetime.min.replace(tzinfo=UTC)
            ends.append(segments[-1].end)
        return min(ends)

    def _dynamic_price(self, tariff: Tariff, moment: datetime) -> float:
        segments = self.dynamic.get(tariff.tariff_type, ())
        index = bisect_right(self._starts.get(tariff.tariff_type, []), moment) - 1
        if index < 0 or not segments[index].start <= moment < segments[index].end:
            raise PriceNotPublishedError(f"{tariff.name}: no price for {moment.isoformat()}")
        return segments[index].price

    def price_at(self, moment: datetime) -> tuple[float, bool]:
        """Price per kWh including VAT at a moment, and whether a gap was filled.

        Raises PriceNotPublishedError when a dynamic tariff has no price then.
        """
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        local = moment.astimezone(SWISS_TZ)
        federal = self.federal_per_kwh
        if federal is None:  # not checked with ElCom: all of them, unless in the grid's API
            federal = national_charges(local.year)
            if grid_includes_federal_charges(self.grid):
                federal = 0.0
        total, any_gap = federal + self.other_fees_per_kwh, False
        # Each tariff has its own schedule: price them separately, then add up.
        for tariff in self._tariffs():
            windows = tariff.windows_for(self.canton, self.municipality, self.municipality_name)
            if tariff.is_dynamic:
                # The API gives the tariff's own price; the file's fixed price for a
                # dynamic tariff (AIL "dinamica": 8.35 Rp) is only indicative.
                windows = windows[len(tariff.energy) :]
            price, gap = price_of_windows(windows, local)
            if tariff.is_dynamic:
                price += self._dynamic_price(tariff, moment)
            total += price
            any_gap = any_gap or gap
        return round(total * (1 + SWISS_VAT), 6), any_gap

    def price_or_none(self, moment: datetime) -> float | None:
        """Price per kWh including VAT, or None when it is not published yet."""
        try:
            return self.price_at(moment)[0]
        except PriceNotPublishedError:
            return None

    def is_time_dependent(self) -> bool:
        """True when the price changes during the day or week."""
        return bool(self.dynamic_tariffs) or any(not w.every_day for w in self._windows())

    def _change_points(self, start: datetime, end: datetime) -> list[datetime]:
        """Moments in ``(start, end)`` where the price may change, in UTC."""
        times = sorted({t for w in self._windows() for t in w.boundaries()} | {time(0, 0)})
        first = start.astimezone(SWISS_TZ).date()
        days = (end.astimezone(SWISS_TZ).date() - first).days
        points = {
            datetime.combine(first + timedelta(days=offset), boundary, SWISS_TZ).astimezone(UTC)
            for offset in range(days + 1)
            for boundary in times
        }
        for segments in self.dynamic.values():
            for segment in segments:
                points.update((segment.start, segment.end))
        return sorted(point for point in points if start < point < end)

    def schedule(self, start: datetime, end: datetime) -> list[Segment]:
        """Constant-price segments in ``[start, end)``, in UTC, merged when equal.

        For dynamic tariffs the schedule stops where the published prices end.
        """
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        if (known := self.known_until) is not None:
            end = min(end, known)
        segments: list[Segment] = []
        if end <= start:
            return segments
        points = [start, *self._change_points(start, end), end]
        for left, right in zip(points, points[1:], strict=False):
            try:
                price = self.price_at(left)[0]
            except PriceNotPublishedError:
                break
            if segments and segments[-1].price == price and segments[-1].end == left:
                segments[-1] = Segment(segments[-1].start, right, price)
            else:
                segments.append(Segment(left, right, price))
        return segments

    def next_change(self, moment: datetime) -> tuple[datetime, float] | None:
        """Return the next moment the price changes and the new price (8 days ahead)."""
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        segments = self.schedule(moment, moment + timedelta(days=8))
        if len(segments) < 2:
            return None
        return segments[1].start.astimezone(SWISS_TZ), segments[1].price

    def period_at(self, moment: datetime) -> str | None:
        """Return "single", "high" or "low" for the price in force at a moment.

        For dynamic tariffs "high" means above the day's average price.
        """
        if not self.is_time_dependent():
            return "single"
        local = moment.astimezone(SWISS_TZ)
        current = self.price_or_none(local)
        if current is None:
            return None
        if self.dynamic_tariffs:
            midnight = datetime.combine(local.date(), time(0, 0), SWISS_TZ)
            day = self.schedule(
                midnight, datetime.combine(local.date() + timedelta(days=1), time(0, 0), SWISS_TZ)
            )
            seconds = sum((s.end - s.start).total_seconds() for s in day)
            average = sum(s.price * (s.end - s.start).total_seconds() for s in day) / seconds
            return "high" if current > average else "low"
        times = sorted({t for w in self._windows() for t in w.boundaries()} | {time(0, 0)})
        levels = {current}
        for offset in range(7):
            day = local.date() + timedelta(days=offset)
            for boundary in times:
                levels.add(self.price_at(datetime.combine(day, boundary, SWISS_TZ))[0])
        if len(levels) == 1:
            return "single"
        return "high" if current == max(levels) else "low"

    @property
    def monthly_fixed(self) -> float:
        """Fixed charges per month including VAT, metering included."""
        base = sum(
            tariff.base_for(self.canton, self.municipality, self.municipality_name)
            for tariff in self._tariffs()
        )
        return round((base + self.metering_monthly) * (1 + SWISS_VAT), 2)


def suggest_matching(name: str, candidates: Sequence[Tariff]) -> Tariff | None:
    """Pick the candidate whose name looks most like ``name``.

    Operators name the parts of one product inconsistently ("Casa", "Casa & PMI
    24h-grid7", "Tariffa PC Piccoli clienti - Rete 2027"), so this is only a
    suggestion that the user confirms.
    """
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda tariff: SequenceMatcher(None, name.lower(), tariff.name.lower()).ratio(),
    )


# First municipality number (BFS) of each canton: the numbers are given out in one
# block per canton. Checked against the federal list on LINDAS (13 October 2026);
# numbers from 9000 are lakes.
_CANTON_BLOCKS = (
    (1, "ZH"), (301, "BE"), (1001, "LU"), (1201, "UR"), (1301, "SZ"), (1401, "OW"),
    (1501, "NW"), (1601, "GL"), (1701, "ZG"), (2001, "FR"), (2401, "SO"), (2701, "BS"),
    (2761, "BL"), (2901, "SH"), (3001, "AR"), (3101, "AI"), (3201, "SG"), (3501, "GR"),
    (4001, "AG"), (4401, "TG"), (5001, "TI"), (5401, "VD"), (6001, "VS"), (6401, "NE"),
    (6601, "GE"), (6701, "JU"),
)  # fmt: skip


# Canton names as operators may write them (de, fr, it), for fees given for a whole
# canton under its federal canton number (EWO: "6 Obwalden").
_CANTON_NAMES = {
    "ZH": ("zürich", "zurich", "zurigo"), "BE": ("bern", "berne", "berna"),
    "LU": ("luzern", "lucerne", "lucerna"), "UR": ("uri",), "SZ": ("schwyz", "svitto"),
    "OW": ("obwalden", "obwald", "obvaldo"), "NW": ("nidwalden", "nidwald", "nidvaldo"),
    "GL": ("glarus", "glaris", "glarona"), "ZG": ("zug", "zoug", "zugo"),
    "FR": ("freiburg", "fribourg", "friburgo"), "SO": ("solothurn", "soleure", "soletta"),
    "BS": ("basel-stadt", "bâle-ville", "basilea città"),
    "BL": ("basel-landschaft", "bâle-campagne", "basilea campagna"),
    "SH": ("schaffhausen", "schaffhouse", "sciaffusa"),
    "AR": ("appenzell ausserrhoden", "appenzell rhodes-extérieures", "appenzello esterno"),
    "AI": ("appenzell innerrhoden", "appenzell rhodes-intérieures", "appenzello interno"),
    "SG": ("st. gallen", "sankt gallen", "saint-gall", "san gallo"),
    "GR": ("graubünden", "grisons", "grigioni"), "AG": ("aargau", "argovie", "argovia"),
    "TG": ("thurgau", "thurgovie", "turgovia"), "TI": ("ticino", "tessin"),
    "VD": ("vaud", "waadt"), "VS": ("valais", "wallis", "vallese"),
    "NE": ("neuchâtel", "neuenburg"), "GE": ("genève", "genf", "ginevra"), "JU": ("jura",),
}  # fmt: skip


def _name_spellings(name: str | None) -> list[str]:
    """A municipality's name as ElCom gives it, and without the canton: ElCom writes
    "Kirchdorf (BE)", an operator may write "Kirchdorf"."""
    if not name:
        return []
    full = name.casefold().strip()
    short = re.sub(r"\s*\([a-z]{2}\)$", "", full)
    return [full, short] if short != full else [full]


def canton_number(canton: str | None) -> int | None:
    """The federal number of a canton (ZH 1 ... JU 26), the order of _CANTON_BLOCKS."""
    codes = [code for _, code in _CANTON_BLOCKS]
    return codes.index(canton) + 1 if canton in codes else None


def canton_of(municipality: int | None) -> str | None:
    """The canton of a municipality, from its BFS number."""
    if municipality is None or not 1 <= municipality < 9000:
        return None
    index = bisect_right([start for start, _ in _CANTON_BLOCKS], municipality) - 1
    return _CANTON_BLOCKS[index][1]


# Tariffs for building sites and other temporary connections, never a home's.
_BUILDING_SITE = re.compile(
    # "Temprorär": EWO's spelling.
    r"bau(strom|stelle|anschluss)|temp\w{0,3}r[äa]r|chantier|provisoire|cantier|provvisori",
    re.IGNORECASE,
)


def _for_building_sites(tariff: Tariff) -> bool:
    """True for a tariff named for building sites or other temporary connections.

    The name only: descriptions mislead ("except building sites"), and RTB describes
    as temporary the only low-voltage grid that matches ElCom's household figure.
    """
    return bool(_BUILDING_SITE.search(tariff.name))


def _by_time_of_day(tariff: Tariff) -> bool:
    """True for a dynamic tariff or one whose price changes during the day."""
    return tariff.is_dynamic or any(not window.every_day for window in tariff.energy)


def _names_place(tariff: Tariff, municipality_name: str, canton: str | None) -> bool:
    """True when the tariff says it is for this municipality or canton ("NNA_GR")."""
    text = f"{tariff.name} {tariff.customer_type}"
    # Whole words only: a municipality is called "Au", and that is in "Haushalt".
    if municipality_name and re.search(
        rf"(?<!\w){re.escape(municipality_name)}(?!\w)", text, re.IGNORECASE
    ):
        return True
    # Only as a code joined to the tariff's name ("NNA_ZH", "NNE-H_GR", "(GR)"): a bare
    # "AG" is a company form, and "NE7" a network level, not Aargau or Neuchâtel.
    return bool(canton) and re.search(rf"[_\-(]{canton}(?![A-Za-z0-9])", tariff.name) is not None


def suggest_grid(
    electricity: Tariff,
    grids: Sequence[Tariff],
    municipality: int | None = None,
    municipality_name: str | None = None,
    elcom: tuple[float, float, int] | tuple[float, float, int, float | None] | None = None,
) -> Tariff | None:
    """The grid tariff that most likely goes with an energy tariff.

    Names alone mislead: ewz serves the city of Zürich and some villages in
    Graubünden ("NNA_ZH", "NNA_GR"), EKZ has nine grid tariffs for three kinds of
    customer. So the signals in the file come first, strongest first: a grid tariff
    named exactly like the energy tariff (Primeo "NetzDynamisch": energy by the clock,
    dynamic grid; 6 of 3486 suggestions in the 2026 and 2027 files changed, all for the
    better), a building-site tariff only with a building-site tariff (Jona-Rapperswil
    2026: "Baustrom" went with household energy, being single-price like it),
    dynamic with dynamic, the same kind of customer, the user's municipality
    or canton named in the tariff, the operator's standard tariff (unless a tariff of the
    energy's shape is closer to ElCom: Groupe E, up to 0.3.14), a day/night tariff
    with a day/night tariff, then (with ``elcom``: ElCom's household grid figure, surcharge and
    year, and optionally its grid price per kWh without fees) the price closest to
    what ElCom says a household pays, to the nearest Rp.: St. Gallen's reactive
    energy price and Geneva's separate "réserve d'électricité" are grid tariffs too.
    Before the day/night match, a price more than 3 Rp. away from ElCom's counts
    against a tariff: with a flat energy tariff, Gränichen's only flat grid tariff
    is for building sites (20 Rp. off). The name decides only between otherwise
    equal tariffs.
    """
    customer = electricity.customer_type.strip().casefold()
    canton = canton_of(municipality)

    def error(grid: Tariff) -> float | None:
        return None if elcom is None else h4_grid_error(grid, *elcom)

    def closeness(grid: Tariff) -> int:
        if elcom is None:
            return 0
        rp = error(grid)
        return -1000 if rp is None else -round(rp)

    def plausible(grid: Tariff) -> bool:
        rp = error(grid)
        return elcom is None or rp is None or rp <= _PLAUSIBLE_GRID_RP

    same_name = electricity.name.strip().casefold()

    def same_shape(grid: Tariff) -> bool:
        return _by_time_of_day(grid) == _by_time_of_day(electricity)

    def standard(grid: Tariff) -> bool:
        """The operator's standard grid, unless it has the other shape and a grid of the
        energy's shape is closer to ElCom: Groupe E flags its day/night grid as
        standard, also next to its single-price energy (1.1 Rp. off ElCom, the
        single-price grid 0.3). BKW has only a single-price household grid."""
        if not grid.standard:
            return False
        if same_shape(grid) or elcom is None:
            return True
        own = error(grid)
        return not any(
            same_shape(other) and (rp := error(other)) is not None and (own is None or rp < own)
            for other in grids
        )

    def score(grid: Tariff) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, int, float]:
        return (
            grid.name.strip().casefold() == same_name,
            _for_building_sites(grid) == _for_building_sites(electricity),
            grid.is_dynamic == electricity.is_dynamic,
            bool(customer) and grid.customer_type.strip().casefold() == customer,
            _names_place(grid, municipality_name or "", canton),
            standard(grid),
            plausible(grid),
            same_shape(grid),
            closeness(grid),
            SequenceMatcher(None, electricity.name.lower(), grid.name.lower()).ratio(),
        )

    return max(grids, key=score, default=None)


def suggest_regional_fees(
    electricity: Tariff,
    regionals: Sequence[Tariff],
    municipality: int | None = None,
    elcom_charge_rp: float | None = None,
    year: int | None = None,
    grid: Tariff | None = None,
    municipality_name: str | None = None,
) -> list[Tariff]:
    """The cantonal and municipal fees for the user's municipality.

    Fees list the municipalities they apply to, so those come first (ewz has fees
    for the city of Zürich and for eight villages in Graubünden). Operators then
    publish either one set of fees per product, to choose from (AIL), or each fee
    on its own, to add up (Lausanne: public lighting, energy efficiency...). The
    file does not say which: with ElCom's household fees (``elcom_charge_rp``) the
    combination closest to them wins; without, the most similar name. Fees are
    often named after the grid tariff (St. Gallen "Netztarif K", Geneva "Profil
    Simple"), so its name counts as well. BKW numbers municipalities its own way:
    with ``municipality_name`` its fees are found by name.
    """
    canton = canton_of(municipality)
    # Fees for this place, and fees for no place in particular, which apply everywhere;
    # fees for other places do not (Groupe E lists fees for Vaud and Neuchâtel
    # municipalities, none for Fribourg).
    here = [
        t
        for t in regionals
        if fee_applies(t, municipality, municipality_name, canton)
        # A fee with its own price and no place list; not one whose places were all
        # unreadable (BKW's "#N/A"), which carries no price at all.
        or (t.energy and not t.municipality_energy and not t.canton_energy)
    ]
    names = [electricity.name.lower()] + ([grid.name.lower()] if grid else [])

    def likeness(fee: Tariff) -> float:
        return max(SequenceMatcher(None, n, fee.name.lower()).ratio() for n in names)

    best = max(here, key=likeness, default=None)
    if best is None:
        return []
    if elcom_charge_rp is None or len(here) == 1:
        return [best]

    # Each fee's average once: the search below tries up to 255 combinations. Monthly
    # fees count at 4500 kWh a year, as in ElCom's figure: Blumenstein's fee for
    # businesses is 25 CHF a month and nothing per kWh.
    average: dict[int, float | None] = {}
    for fee in here:
        try:
            average[id(fee)] = 100 * (
                _average_price(
                    fee.windows_for(canton, municipality, municipality_name),
                    year or date.today().year,
                )
                + fee.base_for(canton, municipality, municipality_name) * 12 / _H4_KWH_PER_YEAR
            )
        except UnsupportedTariffError:
            average[id(fee)] = None

    def fees_rp(fees: Sequence[Tariff]) -> float | None:
        values = [average[id(fee)] for fee in fees]
        return None if None in values else sum(values)  # type: ignore[arg-type]

    # The combination closest to ElCom's figure: one fee (AIL), all (Lausanne), or
    # some (Neuchâtel: cantonal and low-voltage municipal fees, not medium-voltage).
    # Among equally close ones, the one with the most similar names.
    if len(here) <= _MAX_FEES_COMBINED:
        groups = [
            list(group) for size in range(1, len(here) + 1) for group in combinations(here, size)
        ]
    else:
        groups = [[best], here]
    scored = []
    for group in groups:
        total = fees_rp(group)
        if total is not None:
            error = round(abs(total - elcom_charge_rp), 2)
            scored.append((error, -sum(likeness(fee) for fee in group) / len(group), group))
    if not scored:
        return [best]
    return min(scored, key=lambda item: item[:2])[2]


def missing_fees(
    fees: Sequence[Tariff],
    canton: str | None,
    municipality: int | None,
    municipality_name: str | None,
    elcom_charge_rp: float,
    year: int,
) -> float:
    """The correction to the file's cantonal and municipal fees from ElCom's household
    figure, in CHF/kWh; 0 when they are within 0.3 Rp. of ElCom's.

    Fees ElCom counts and the file does not are added: 83 of 343 operators checked in
    October 2026 publish no fee at all in their file although ElCom lists some (up to
    4 Rp.), and IWB's file lacks most of Basel's (0.65 Rp. of 7.79). Fees that hold
    the federal charges, which Corrente adds on its own, are taken off when the
    file is above ElCom's by exactly the grid surcharge or all of them (Lachen 2.68
    against 0.38, Fällanden 2.85 against 0). Monthly fees count at ElCom's 4500 kWh
    a year, as in ElCom's figure; they are in the fixed charges already.
    """
    try:
        file_rp = sum(
            100 * _average_price(fee.windows_for(canton, municipality, municipality_name), year)
            + 100 * fee.base_for(canton, municipality, municipality_name) * 12 / _H4_KWH_PER_YEAR
            for fee in fees
        )
    except UnsupportedTariffError:
        return 0.0
    gap = elcom_charge_rp - file_rp
    federal = (100 * national_charges(year), 100 * GRID_SURCHARGE)
    if any(abs(gap + charge) <= _SAME_RP for charge in federal):
        return round(gap / 100, 6)
    return round(gap / 100, 6) if gap > _MISSING_FEES_RP else 0.0


def yearly_fee_as_monthly(grid: Tariff, elcom_fix_chf: float | None) -> float | None:
    """The grid's monthly fee when the file gives the yearly one as monthly, else None.

    Spreitenbach writes 66 CHF "a month", Quarten 144; ElCom has the same figures as
    fees a year. A monthly fee equal to ElCom's yearly one is read as yearly.
    """
    if not elcom_fix_chf or not grid.monthly_base:
        return None
    if abs(grid.monthly_base - elcom_fix_chf) <= 0.01 * elcom_fix_chf + 0.05:
        return round(elcom_fix_chf / 12, 4)
    return None


def fee_applies(
    fee: Tariff, municipality: int | None, municipality_name: str | None, canton: str | None
) -> bool:
    """True when a fee tariff lists the user's municipality (by number or name) or canton."""
    return (
        fee.municipality_key(municipality, municipality_name, canton) is not None
        or canton in fee.canton_energy
    )


def regional_names(value: str | Sequence[str] | None) -> list[str]:
    """The fees stored in an entry: a list since 0.2.2, one name (or "none") before."""
    if isinstance(value, str):
        value = [value]
    return [name for name in value or () if name and name != "none"]


def tariffs_on(tariffs: Iterable[Tariff], tariff_type: str, day: date) -> list[Tariff]:
    """Tariffs of a type that are in force on a day."""
    return [t for t in tariffs if t.tariff_type == tariff_type and t.valid_on(day)]


def metering_per_month(
    file_monthly: float, elcom_fix_chf: float | None, elcom_metering_rp: float | None
) -> float:
    """The household's metering fee per month, CHF without VAT, from ElCom; 0 when
    the file's monthly fees hold it already.

    Of 314 operators' files read in October 2026, 305 publish metering as a tariff of
    its own ("Messung Niederspannung Direkt", "Mesure directe BT"), which Corrente
    does not pick: their grid and fee monthly fees match ElCom's grid fixed costs
    alone. ElCom's metering figure is the direct-metering fee of a household (AIL
    5.30 CHF a month, OIKEN 6.60, Viteos 6.20), about 6 CHF a month.
    ``file_monthly`` is the grid's and the fees' monthly fees in the file.
    """
    if not elcom_metering_rp or elcom_metering_rp <= 0:
        return 0.0
    yearly = elcom_metering_rp * _H4_KWH_PER_YEAR / 100
    if elcom_fix_chf is not None:
        tolerance = max(_SAME_FEE_CHF, 0.05 * (elcom_fix_chf + yearly))
        holds_it = abs(12 * file_monthly - elcom_fix_chf - yearly) <= tolerance
        grid_only = abs(12 * file_monthly - elcom_fix_chf) <= tolerance
        if holds_it and not grid_only:
            return 0.0
    return round(yearly / 12, 4)
