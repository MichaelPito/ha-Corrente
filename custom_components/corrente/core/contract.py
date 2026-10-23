"""Retail electricity contracts: turn a moment in time into a price per kWh.

Pure Python, no Home Assistant imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .italy import Band, band_at


class ItalyContractType(StrEnum):
    """Shapes of Italian contracts."""

    SINGLE = "single"  # monoraria: one price at all hours
    TWO_BANDS = "two_bands"  # bioraria: F1 and F23 (F2 + F3)
    THREE_BANDS = "three_bands"  # trioraria: F1, F2, F3
    INDEXED = "pun"  # PUN (or a zonal price) + spread


@dataclass(frozen=True, slots=True)
class ItalyIndexedContract:
    """A contract indexed to the PUN Index GME or to a zonal price, in EUR/kWh."""

    spread: float
    losses: float = 0.0  # grid losses applied to the wholesale price, e.g. 0.10 for 10%
    zone: str = "PUN"
    # From the bill, if the user enters them: transport, system charges and excise
    # per kWh, and the fixed charges per month.
    other_per_kwh: float = 0.0
    monthly_fixed: float = 0.0

    def __post_init__(self) -> None:
        if not 0 <= self.losses < 1:
            raise ValueError("losses must be between 0 and 1")
        if self.other_per_kwh < 0 or self.monthly_fixed < 0:
            raise ValueError("other costs cannot be negative")

    def price_from(self, wholesale: float) -> float:
        """Price per kWh from the wholesale price per kWh: energy and other costs."""
        return round(wholesale * (1 + self.losses) + self.spread + self.other_per_kwh, 6)


@dataclass(frozen=True, slots=True)
class ItalyFixedContract:
    """An Italian contract with fixed prices per band, in EUR/kWh."""

    contract_type: ItalyContractType
    price_f1: float
    price_f2: float | None = None
    price_f3: float | None = None
    # From the bill, if the user enters them: transport, system charges and excise
    # per kWh, and the fixed charges per month.
    other_per_kwh: float = 0.0
    monthly_fixed: float = 0.0

    def __post_init__(self) -> None:
        if self.other_per_kwh < 0 or self.monthly_fixed < 0:
            raise ValueError("other costs cannot be negative")
        prices = [self.price_f1]
        if self.contract_type is ItalyContractType.TWO_BANDS:
            if self.price_f2 is None:
                raise ValueError("a two-band contract needs the F23 price")
            prices.append(self.price_f2)
        elif self.contract_type is ItalyContractType.THREE_BANDS:
            if self.price_f2 is None or self.price_f3 is None:
                raise ValueError("a three-band contract needs F2 and F3 prices")
            prices.extend((self.price_f2, self.price_f3))
        if any(price < 0 for price in prices):
            raise ValueError("prices cannot be negative")

    def price_for_band(self, band: Band) -> float:
        """Return the price per kWh that applies in a band, other costs included."""
        return round(self._energy_price(band) + self.other_per_kwh, 6)

    def _energy_price(self, band: Band) -> float:
        if self.contract_type is ItalyContractType.SINGLE or band is Band.F1:
            return self.price_f1
        if self.contract_type is ItalyContractType.TWO_BANDS:
            # price_f2 holds the F23 price for two-band contracts.
            return self.price_f2  # type: ignore[return-value]
        return self.price_f2 if band is Band.F2 else self.price_f3  # type: ignore[return-value]

    def price_at(self, moment: datetime) -> float:
        """Return the price per kWh at a timezone-aware moment."""
        return self.price_for_band(band_at(moment))
