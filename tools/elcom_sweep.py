"""Compare Corrente's Swiss grid prices with ElCom's, for every operator of a year.

For each grid operator in ElCom's open data (one municipality each), this does what
the setup does: find the operator's tariff file, take the energy tariff, let Corrente
suggest the grid tariff with ElCom's figures, and measure how far that grid price is
from ElCom's household figure (H4). The energy tariff is the one the operator flags as
standard; without one, every energy tariff is tried and the closest counts, standing
in for the household tariff ElCom measures (the first in alphabetical order would be a
building-site or large-customer tariff no household chooses). The README and the
launch posts quote the result ("within 0.6 Rp/kWh for 95% of operators").

Run from the repository root, in an environment with Home Assistant installed:

    python tools/elcom_sweep.py 2027 [--limit N] [--out results.json]

It downloads each operator's public tariff file once, a few at a time.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.corrente.config_flow import _standard_electricity, _supported  # noqa: E402
from custom_components.corrente.core import elcom  # noqa: E402
from custom_components.corrente.core.switzerland import (  # noqa: E402
    h4_grid_error,
    parse_tariffs,
    suggest_grid,
    tariffs_on,
)

WITHIN_RP = 0.6
PARALLEL = 6


async def _operators(
    session: aiohttp.ClientSession, year: int
) -> list[elcom.OperatorInMunicipality]:
    rows = await elcom._query(session, elcom._QUERY.format(year=year, filter=""))
    first: dict[str, elcom.OperatorInMunicipality] = {}
    for place in elcom._rows_to_operators(rows, year):
        first.setdefault(place.operator_id, place)
    return sorted(first.values(), key=lambda p: p.operator_name)


async def _check(
    session: aiohttp.ClientSession, place: elcom.OperatorInMunicipality, year: int, day: date
) -> dict:
    result = {"operator": place.operator_name, "municipality": place.municipality_name}
    try:
        urls = await elcom.async_tariff_url_candidates(
            session, place.municipality, place.operator_id, year, place.tariff_url
        )
    except Exception as err:  # noqa: BLE001 - a report, not a failure
        return {**result, "status": "no_link", "detail": repr(err)[:120]}
    if not urls:
        return {**result, "status": "no_link"}
    tariffs = []
    for url in urls:
        try:
            document = await elcom.async_fetch_tariff_document(session, url)
            tariffs = parse_tariffs(document)
        except Exception:  # noqa: BLE001, S112 - try the next link
            continue
        if any(_supported(t) for t in tariffs_on(tariffs, "electricity", day)):
            result["url"] = url
            break
    else:
        return {**result, "status": "no_readable_file"}
    energies = [t for t in tariffs_on(tariffs, "electricity", day) if _supported(t)]
    standard = _standard_electricity(tariffs, day)
    if standard:
        energies = [t for t in energies if t.name == standard]
    grids = [t for t in tariffs_on(tariffs, "grid", day) if _supported(t)]
    if place.grid_h4_rp is None or place.aidfee_rp is None:
        return {**result, "status": "no_elcom_figures"}
    figures = (place.grid_h4_rp, place.aidfee_rp, year, place.grid_working_rp)
    best = None
    for energy in energies:
        grid = suggest_grid(energy, grids, place.municipality, place.municipality_name, figures)
        error = None if grid is None else h4_grid_error(grid, *figures)
        if error is not None and (best is None or error < best[0]):
            best = (error, energy.name, grid.name)
    if best is None:
        return {**result, "status": "no_priced_grid"}
    return {
        **result,
        "status": "compared",
        "standard_flagged": bool(standard),
        "energy": best[1],
        "grid": best[2],
        "error_rp": round(best[0], 3),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("year", type=int)
    parser.add_argument("--limit", type=int, default=0, help="only the first N operators")
    parser.add_argument("--out", type=Path, help="write every result to this JSON file")
    args = parser.parse_args()
    # The tariffs in force: today for this year, mid-January for another year.
    day = date.today() if args.year == date.today().year else date(args.year, 1, 15)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        places = await _operators(session, args.year)
        if args.limit:
            places = places[: args.limit]
        gate = asyncio.Semaphore(PARALLEL)

        async def one(place: elcom.OperatorInMunicipality) -> dict:
            async with gate:
                try:
                    return await _check(session, place, args.year, day)
                except Exception as err:  # noqa: BLE001
                    detail = repr(err)[:120]
                    return {"operator": place.operator_name, "status": "error", "detail": detail}

        results = await asyncio.gather(*(one(p) for p in places))
    statuses = Counter(r["status"] for r in results)
    compared = [r for r in results if r["status"] == "compared"]
    within = [r for r in compared if r["error_rp"] <= WITHIN_RP]
    print(f"{args.year}: {len(results)} operators in ElCom's data")
    for status, count in statuses.most_common():
        print(f"  {status}: {count}")
    if compared:
        share = 100 * len(within) / len(compared)
        print(
            f"  grid within {WITHIN_RP} Rp of ElCom:"
            f" {len(within)} of {len(compared)} ({share:.0f}%)"
        )
        worst = sorted(compared, key=lambda r: -r["error_rp"])[:10]
        print("  farthest:", ", ".join(f"{r['operator']} {r['error_rp']}" for r in worst))
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    asyncio.run(main())
