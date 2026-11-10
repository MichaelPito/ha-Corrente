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

    python tools/elcom_sweep.py 2027 [--limit N] [--out results.json] [--cache DIR] [--each]

It downloads each operator's public tariff file once, a few at a time. With
``--cache`` the files and ElCom's figures are kept in DIR, so a second run (to compare
two versions of the code) reads them from there. With ``--each`` the results also list
the grid suggested for every energy tariff, not only the closest.
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
    session: aiohttp.ClientSession, year: int, cache: Path | None
) -> list[elcom.OperatorInMunicipality]:
    saved = cache / f"elcom-{year}.json" if cache else None
    if saved and saved.exists():
        rows = json.loads(saved.read_text("utf-8"))
    else:
        rows = await elcom._query(session, elcom._QUERY.format(year=year, filter=""))
        if saved:
            saved.write_text(json.dumps(rows), "utf-8")
    first: dict[str, elcom.OperatorInMunicipality] = {}
    for place in elcom._rows_to_operators(rows, year):
        first.setdefault(place.operator_id, place)
    return sorted(first.values(), key=lambda p: p.operator_name)


async def _document(
    session: aiohttp.ClientSession,
    place: elcom.OperatorInMunicipality,
    year: int,
    day: date,
    cache: Path | None,
) -> dict:
    """The operator's tariff file: {"url", "document"}, or {"status"} when there is none."""
    saved = cache / f"file-{year}-{place.operator_id}.json" if cache else None
    if saved and saved.exists():
        return json.loads(saved.read_text("utf-8"))
    found = await _download(session, place, year, day)
    if saved:
        saved.write_text(json.dumps(found, ensure_ascii=False), "utf-8")
    return found


async def _download(
    session: aiohttp.ClientSession, place: elcom.OperatorInMunicipality, year: int, day: date
) -> dict:
    try:
        urls = await elcom.async_tariff_url_candidates(
            session, place.municipality, place.operator_id, year, place.tariff_url
        )
    except Exception as err:  # noqa: BLE001 - a report, not a failure
        return {"status": "no_link", "detail": repr(err)[:120]}
    for url in urls:
        try:
            document = await elcom.async_fetch_tariff_document(session, url)
            tariffs = parse_tariffs(document)
        except Exception:  # noqa: BLE001, S112 - try the next link
            continue
        if any(_supported(t) for t in tariffs_on(tariffs, "electricity", day)):
            return {"url": url, "document": document}
    return {"status": "no_readable_file" if urls else "no_link"}


async def _check(
    session: aiohttp.ClientSession,
    place: elcom.OperatorInMunicipality,
    year: int,
    day: date,
    cache: Path | None = None,
    each: bool = False,
) -> dict:
    result = {"operator": place.operator_name, "municipality": place.municipality_name}
    found = await _document(session, place, year, day, cache)
    if "document" not in found:
        return {**result, **found}
    result["url"] = found["url"]
    tariffs = parse_tariffs(found["document"])
    energies = [t for t in tariffs_on(tariffs, "electricity", day) if _supported(t)]
    standard = _standard_electricity(tariffs, day)
    if standard:
        energies = [t for t in energies if t.name == standard]
    grids = [t for t in tariffs_on(tariffs, "grid", day) if _supported(t)]
    if place.grid_h4_rp is None or place.aidfee_rp is None:
        return {**result, "status": "no_elcom_figures"}
    figures = (place.grid_h4_rp, place.aidfee_rp, year, place.grid_working_rp)
    best = None
    suggested = []
    for energy in tariffs_on(tariffs, "electricity", day) if each else energies:
        if not _supported(energy):
            continue
        grid = suggest_grid(energy, grids, place.municipality, place.municipality_name, figures)
        error = None if grid is None else h4_grid_error(grid, *figures)
        suggested.append([energy.name, grid and grid.name, error and round(error, 3)])
        if energy in energies and error is not None and (best is None or error < best[0]):
            best = (error, energy.name, grid.name)
    if each:
        result["each"] = suggested
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
    parser.add_argument("--cache", type=Path, help="keep downloaded files in this directory")
    parser.add_argument("--each", action="store_true", help="list every energy tariff")
    args = parser.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    # The tariffs in force: today for this year, mid-January for another year.
    day = date.today() if args.year == date.today().year else date(args.year, 1, 15)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        places = await _operators(session, args.year, args.cache)
        if args.limit:
            places = places[: args.limit]
        gate = asyncio.Semaphore(PARALLEL)

        async def one(place: elcom.OperatorInMunicipality) -> dict:
            async with gate:
                try:
                    return await _check(session, place, args.year, day, args.cache, args.each)
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
