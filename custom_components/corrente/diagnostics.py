"""Diagnostics: what Corrente read and computed, to attach to a request on GitHub."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import CorrenteConfigEntry
from .core.schedule import Segment
from .core.switzerland import PriceNotPublishedError, PriceWindow, SwissContract, Tariff
from .core.version import VERSION

# No secrets are stored: the entry holds the place, the operator, the tariff names
# and prices the user chose, and the entities of the energy meters.


def _window(window: PriceWindow) -> str:
    """A window as a short line: "Mo-Fr 06:00-22:00 Jan-Mar: 0.0975"."""
    days = "" if window.weekdays is None else f"days {sorted(window.weekdays)} "
    months = "" if window.months is None else f"months {sorted(window.months)} "
    end = "24:00" if window.end is None else window.end.strftime("%H:%M")
    return f"{days}{months}{window.start.strftime('%H:%M')}-{end}: {window.price:g}"


def _tariff(tariff: Tariff, contract: SwissContract) -> dict[str, Any]:
    return {
        "name": tariff.name,
        "type": tariff.tariff_type,
        "valid": f"{tariff.start_date} to {tariff.end_date}",
        "customer_type": tariff.customer_type,
        "standard": tariff.standard,
        "dynamic": tariff.is_dynamic,
        "monthly_fee_chf": tariff.base_for(
            contract.canton, contract.municipality, contract.municipality_name
        ),
        "windows_chf_per_kwh": [
            _window(w)
            for w in tariff.windows_for(
                contract.canton, contract.municipality, contract.municipality_name
            )
        ],
    }


def _segments(segments: list[Segment]) -> list[dict[str, Any]]:
    return [
        {"start": s.start.isoformat(), "end": s.end.isoformat(), "price": round(s.price, 6)}
        for s in segments
    ]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CorrenteConfigEntry
) -> dict[str, Any]:
    """Return what a config entry is set to and what it computed."""
    now = dt_util.utcnow()
    result: dict[str, Any] = {
        "version": VERSION,
        "data": dict(entry.data),
        "options": dict(entry.options),
    }
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return result
    if runtime.switzerland is not None:
        coordinator = runtime.switzerland
        result["last_update_success"] = coordinator.last_update_success
        data = coordinator.data
        if data is not None:
            contract = data.contract
            try:
                price_now = contract.price_at(now)[0]
            except PriceNotPublishedError:
                price_now = None
            result["switzerland"] = {
                "source_url": data.source_url,
                "tariffs_in_file": len(data.tariffs),
                "canton": contract.canton,
                "municipality": contract.municipality,
                "federal_charges_checked_with_elcom": data.federal_checked,
                "federal_per_kwh": contract.federal_per_kwh,
                "other_fees_from_elcom_per_kwh": contract.other_fees_per_kwh,
                "price_now_with_vat": price_now,
                "period_now": contract.period_at(now),
                "monthly_fixed_with_vat": contract.monthly_fixed,
                "tariffs": [
                    _tariff(t, contract)
                    for t in (contract.electricity, contract.grid, *contract.regional_fees)
                ],
                "next_24_hours": _segments(contract.schedule(now, now + timedelta(hours=24))),
            }
    if runtime.italy is not None:
        result["italy"] = asdict(runtime.italy)
    if runtime.italy_indexed is not None:
        result["italy_indexed"] = asdict(runtime.italy_indexed)
    if runtime.gme is not None:
        segments = runtime.gme.data or []
        result["gme"] = {
            "last_update_success": runtime.gme.last_update_success,
            "prices": len(segments),
            "prices_until": segments[-1].end.isoformat() if segments else None,
            "first_prices": _segments(segments[:4]),
        }
    return result
