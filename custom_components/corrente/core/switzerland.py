"""Swiss grid-operator tariffs in the VSE "Tariff Retrieval API" format.

Every Swiss grid operator must publish its tariffs as JSON in this format
(Art. 7b para. 1 StromVV); ElCom lists the link for each operator. Prices in
the files exclude VAT. Pure Python, no Home Assistant imports.

Spec: https://tariffconverter.strom.ch/ch-electricity-tariffs-openapi.yml
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Any
from zoneinfo import ZoneInfo

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

    def check_supported(self) -> None:
        """Raise if the tariff cannot be priced from the file alone."""
        if self.form == "dynamic":
            raise UnsupportedTariffError(f"{self.name}: dynamic tariff")
        # Several whole-day prices for a tiered tariff means the daily windows
        # were not encoded (seen in AMB "Dinamica" 2027).
        if (
            self.form == "multilevel"
            and len(self.energy) > 1
            and all(window.all_day for window in self.energy)
        ):
            raise UnsupportedTariffError(f"{self.name}: time windows missing")


def parse_tariffs(document: Mapping[str, Any]) -> list[Tariff]:
    """Parse a VSE tariff document."""
    tariffs = []
    for raw in document.get("tariffs", ()):
        prices = raw.get("prices") or {}
        canton_energy: dict[str, list[PriceWindow]] = {}
        for tax in prices.get("cantonalTaxes") or ():
            canton_energy.setdefault(tax["cantonName"], []).extend(
                _windows(tax.get("cantonEnergy"))
            )
        municipality_energy: dict[int, list[PriceWindow]] = {}
        for tax in prices.get("municipalityTaxes") or ():
            municipality_energy.setdefault(int(tax["municipalityNumber"]), []).extend(
                _windows(tax.get("municipalityEnergy"))
            )
        base = prices.get("base") or {}
        tariffs.append(
            Tariff(
                name=raw["tariffName"],
                tariff_type=raw["tariffType"],
                form=raw.get("tariffForm", "constant"),
                start_date=date.fromisoformat(raw["startDate"]),
                end_date=date.fromisoformat(raw["endDate"]),
                customer_type=raw.get("customerType", ""),
                energy=_windows(prices.get("energy")),
                monthly_base=float(base.get("price", 0)) if base.get("priceUnit") == "CHF/M" else 0,
                canton_energy={k: tuple(v) for k, v in canton_energy.items()},
                municipality_energy={k: tuple(v) for k, v in municipality_energy.items()},
                dynamic_url=(prices.get("dynamic") or {}).get("url"),
            )
        )
    return tariffs


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


@dataclass(frozen=True, slots=True)
class SwissContract:
    """The tariffs that make up a household's per-kWh price."""

    electricity: Tariff
    grid: Tariff
    regional_fees: Tariff | None = None
    canton: str | None = None
    municipality: int | None = None

    def __post_init__(self) -> None:
        for tariff in self._tariffs():
            tariff.check_supported()

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

    def price_at(self, moment: datetime) -> tuple[float, bool]:
        """Price per kWh including VAT at a moment, and whether a gap was filled."""
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        local = moment.astimezone(SWISS_TZ)
        total, any_gap = national_charges(local.year), False
        # Each tariff has its own schedule: price them separately, then add up.
        for tariff in self._tariffs():
            price, gap = price_of_windows(tariff.windows_for(self.canton, self.municipality), local)
            total += price
            any_gap = any_gap or gap
        return round(total * (1 + SWISS_VAT), 6), any_gap

    def is_time_dependent(self) -> bool:
        """True when the price changes during the day or week."""
        return any(not window.all_day for window in self._windows())

    def next_change(self, moment: datetime) -> tuple[datetime, float] | None:
        """Return the next moment the price changes and the new price (8 days ahead)."""
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")
        local = moment.astimezone(SWISS_TZ)
        current, _ = self.price_at(local)
        times = sorted({t for w in self._windows() for t in w.boundaries()} | {time(0, 0)})
        for offset in range(9):
            day = local.date() + timedelta(days=offset)
            for boundary in times:
                candidate = datetime.combine(day, boundary, SWISS_TZ)
                if candidate <= local:
                    continue
                price, _ = self.price_at(candidate)
                if price != current:
                    return candidate, price
        return None

    def period_at(self, moment: datetime) -> str:
        """Return "single", "high" or "low" for the price in force at a moment."""
        if not self.is_time_dependent():
            return "single"
        local = moment.astimezone(SWISS_TZ)
        current, _ = self.price_at(local)
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
