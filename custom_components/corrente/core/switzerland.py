"""Swiss grid-operator tariffs in the VSE "Tariff Retrieval API" format.

Every Swiss grid operator must publish its tariffs as JSON in this format
(Art. 7b para. 1 StromVV); ElCom lists the link for each operator. Prices in
the files exclude VAT. Pure Python, no Home Assistant imports.

Spec: https://tariffconverter.strom.ch/ch-electricity-tariffs-openapi.yml
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Any
from zoneinfo import ZoneInfo

from .dynamic import is_api_url
from .schedule import Segment

_LOGGER = logging.getLogger(__name__)

SWISS_TZ = ZoneInfo("Europe/Zurich")
SWISS_VAT = 0.081

# Federal per-kWh charges that operators' grid tariffs do not include, in CHF/kWh
# without VAT: grid surcharge (Art. 35 EnG), electricity reserve, Swissgrid general
# system services and solidarised transmission costs. Sources in docs/FONTI-DATI.md;
# the 2027 sum matches ElCom's published totals for AIL and AMB.
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


def federal_addition(
    grid_tariffs: Sequence[Tariff],
    elcom_grid_rp: float,
    elcom_aidfee_rp: float,
    year: int,
    chosen: Tariff | None = None,
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
    same monthly fee), then all flat grid tariffs. An operator can have
    products that match different hypotheses (EKZ "400LS" for businesses), so
    the closest to the user's tariff comes first: with a dynamic or day/night
    grid tariff, Groupe E's business tariffs once pointed to the wrong answer.
    """
    target = elcom_grid_rp + elcom_aidfee_rp  # what ElCom says grid costs, all charges in

    def is_flat(tariff: Tariff) -> bool:
        return bool(tariff.energy) and all(w.all_day for w in tariff.energy)

    all_flat = [t for t in grid_tariffs if is_flat(t)]
    choices = [[t for t in all_flat if t.standard]]
    if chosen is not None:
        choices = [
            [chosen] if is_flat(chosen) else [],
            *choices,
            [
                t
                for t in all_flat
                if chosen.customer_type and t.customer_type == chosen.customer_type
            ],
            [t for t in all_flat if t.monthly_base == chosen.monthly_base],
        ]
    flat = next((group for group in choices if group), all_flat)
    if not flat:
        return None
    candidates = (national_charges(year), elcom_aidfee_rp / 100, 0.0)
    best_addition, best_error = None, None
    for addition in candidates:
        for tariff in flat:
            grid_rp = 100 * (
                sum(w.price for w in tariff.energy) + tariff.monthly_base * 12 / _H4_KWH_PER_YEAR
            )
            error = abs(grid_rp + 100 * addition - target)
            if best_error is None or error < best_error:
                best_addition, best_error = addition, error
    return best_addition


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
        months=frozenset(_MONTHS[m] for m in months) if months else None,
        weekdays=frozenset(_WEEKDAYS[d] for d in weekdays) if weekdays else None,
    )


def _parse_date(text: str) -> date:
    """A tariff's start or end date; BKW writes "2027-01-01T00:00:00"."""
    return date.fromisoformat(text[:10])


def _windows(raws: Iterable[Mapping[str, Any]] | None) -> tuple[PriceWindow, ...]:
    windows = (_parse_window(raw) for raw in raws or ())
    return tuple(window for window in windows if window is not None)


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
    dynamic_url: str | None = None
    standard: bool = False  # the operator's flagged standard tariff (standardBasegroup)

    def valid_on(self, day: date) -> bool:
        """Return whether the tariff is in force on a day."""
        return self.start_date <= day <= self.end_date

    def windows_for(
        self, canton: str | None = None, municipality: int | None = None
    ) -> tuple[PriceWindow, ...]:
        """Per-kWh windows, including the canton's and municipality's surcharges."""
        windows = list(self.energy)
        if canton is not None:
            windows.extend(self.canton_energy.get(canton, ()))
        if municipality is not None:
            windows.extend(self.municipality_energy.get(municipality, ()))
        return tuple(windows)

    @property
    def is_dynamic(self) -> bool:
        """Priced per quarter hour by the operator's API (see core/dynamic.py)."""
        return self.form == "dynamic"

    def check_supported(self) -> None:
        """Raise if the tariff cannot be priced from the file and the operator's API."""
        if self.is_dynamic and not is_api_url(self.dynamic_url):
            raise UnsupportedTariffError(f"{self.name}: dynamic tariff without an API")
        # Several whole-day prices for a tiered tariff means the daily windows
        # were not encoded (seen in AMB "Dinamica" 2027).
        if (
            self.form == "multilevel"
            and len(self.energy) > 1
            and all(window.all_day for window in self.energy)
        ):
            raise UnsupportedTariffError(f"{self.name}: time windows missing")


def parse_tariffs(document: Mapping[str, Any]) -> list[Tariff]:
    """Parse a VSE tariff document, skipping entries that cannot be read.

    Real files have broken entries (BKW 2026: municipality "#N/A"); one bad
    entry must not hide the operator's other tariffs.
    """
    tariffs = []
    for raw in document.get("tariffs", ()):
        try:
            tariffs.append(_parse_tariff(raw))
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Skipping unreadable tariff %s: %s", raw.get("tariffName"), err)
    return tariffs


def _parse_tariff(raw: Mapping[str, Any]) -> Tariff:
    prices = raw.get("prices") or {}
    canton_energy: dict[str, list[PriceWindow]] = {}
    for tax in prices.get("cantonalTaxes") or ():
        canton_energy.setdefault(tax["cantonName"], []).extend(_windows(tax.get("cantonEnergy")))
    municipality_energy: dict[int, list[PriceWindow]] = {}
    for tax in prices.get("municipalityTaxes") or ():
        number = str(tax.get("municipalityNumber", ""))
        if not number.isdigit():
            continue  # "#N/A" in BKW's file
        municipality_energy.setdefault(int(number), []).extend(
            _windows(tax.get("municipalityEnergy"))
        )
    base = prices.get("base") or {}
    return Tariff(
        name=raw["tariffName"],
        tariff_type=raw["tariffType"],
        form=raw.get("tariffForm", "constant"),
        start_date=_parse_date(raw["startDate"]),
        end_date=_parse_date(raw["endDate"]),
        customer_type=raw.get("customerType", ""),
        energy=_windows(prices.get("energy")),
        monthly_base=float(base.get("price", 0)) if base.get("priceUnit") == "CHF/M" else 0,
        canton_energy={k: tuple(v) for k, v in canton_energy.items()},
        municipality_energy={k: tuple(v) for k, v in municipality_energy.items()},
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
    whole_day = sum(w.price for w in windows if w.all_day and w.covers(local))
    timed = [w for w in windows if not w.all_day]
    if not timed:
        return whole_day, False
    matching = [w for w in timed if w.covers(local)]
    if len(matching) > 1:
        raise UnsupportedTariffError("overlapping time windows")
    if matching:
        return whole_day + matching[0].price, False
    return whole_day + min(w.price for w in timed), True


class PriceNotPublishedError(LookupError):
    """A dynamic tariff has no published price for that moment (yet)."""


@dataclass(frozen=True, slots=True)
class SwissContract:
    """The tariffs that make up a household's per-kWh price."""

    electricity: Tariff
    grid: Tariff
    regional_fees: Tariff | None = None
    canton: str | None = None
    municipality: int | None = None
    # Federal charges to add per kWh; None: all of them (see federal_addition).
    federal_per_kwh: float | None = None
    # Published per-kWh prices of the dynamic tariffs (CHF without VAT, UTC),
    # by tariff type ("electricity", "grid"); see core/dynamic.py.
    dynamic: Mapping[str, tuple[Segment, ...]] = field(default_factory=dict)
    _starts: Mapping[str, list[datetime]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for tariff in self._tariffs():
            tariff.check_supported()
        object.__setattr__(
            self,
            "_starts",
            {kind: [s.start for s in segments] for kind, segments in self.dynamic.items()},
        )

    def _tariffs(self) -> list[Tariff]:
        tariffs = [self.electricity, self.grid]
        if self.regional_fees is not None:
            tariffs.append(self.regional_fees)
        return tariffs

    def _windows(self) -> tuple[PriceWindow, ...]:
        return tuple(
            window
            for tariff in self._tariffs()
            for window in tariff.windows_for(self.canton, self.municipality)
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
        federal = (
            national_charges(local.year) if self.federal_per_kwh is None else self.federal_per_kwh
        )
        total, any_gap = federal, False
        # Each tariff has its own schedule: price them separately, then add up.
        for tariff in self._tariffs():
            windows = tariff.windows_for(self.canton, self.municipality)
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
        return bool(self.dynamic_tariffs) or any(not w.all_day for w in self._windows())

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
        """Fixed charges per month including VAT (metering is not included)."""
        base = sum(tariff.monthly_base for tariff in self._tariffs())
        return round(base * (1 + SWISS_VAT), 2)


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


def tariffs_on(tariffs: Iterable[Tariff], tariff_type: str, day: date) -> list[Tariff]:
    """Tariffs of a type that are in force on a day."""
    return [t for t in tariffs if t.tariff_type == tariff_type and t.valid_on(day)]
