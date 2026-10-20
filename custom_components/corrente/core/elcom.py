"""ElCom open data (LINDAS): find a municipality's grid operators and tariff files.

ElCom publishes, for every municipality and year, the grid operator(s) and the
link to the operator's tariff file (Art. 7b StromVV). Licence: Open-Use.
https://energy.ld.admin.ch/elcom/electricityprice
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import aiohttp

from .version import USER_AGENT

LINDAS_ENDPOINT = "https://lindas.admin.ch/query"
_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Operators whose link registered with ElCom is a web page rather than the
# tariff file. Curated by hand; see docs/FONTI-DATI.md. Keyed by (operator id, year).
KNOWN_TARIFF_URLS: dict[tuple[str, int], str] = {
    ("33", 2027): "https://www.amb.ch/media/2hcct0s4/tariffe-2027.json",  # AMB Bellinzona
}

_QUERY = """
PREFIX schema: <http://schema.org/>
PREFIX cube: <https://cube.link/>
PREFIX elcom: <https://energy.ld.admin.ch/elcom/electricityprice/dimension/>
SELECT DISTINCT ?muni ?muniName ?op ?opName ?url ?total ?gridusage ?aidfee ?charge
  ?gridworking WHERE {{
  <https://energy.ld.admin.ch/elcom/electricityprice> cube:observationSet/cube:observation ?obs .
  ?obs elcom:municipality ?muni ;
       elcom:period "{year}"^^<http://www.w3.org/2001/XMLSchema#gYear> ;
       elcom:category <https://energy.ld.admin.ch/elcom/electricityprice/category/H4> ;
       elcom:product <https://energy.ld.admin.ch/elcom/electricityprice/product/standard> ;
       elcom:operator ?op ;
       elcom:total ?total .
  OPTIONAL {{ ?obs elcom:gridusage ?gridusage }}
  OPTIONAL {{ ?obs elcom:aidfee ?aidfee }}
  OPTIONAL {{ ?obs elcom:charge ?charge }}
  OPTIONAL {{ ?obs elcom:gridworkingprice ?gridworking }}
  OPTIONAL {{ ?obs elcom:urltr ?url }}
  ?op schema:name ?opName .
  ?muni schema:name ?muniName .
  {filter}
}}
ORDER BY ?muniName ?opName
"""


class ElcomError(Exception):
    """ElCom could not be reached or answered something unexpected."""


class TariffFileError(Exception):
    """The operator's tariff file could not be downloaded or read."""


@dataclass(frozen=True, slots=True)
class OperatorInMunicipality:
    """A grid operator serving a municipality in a given year."""

    municipality: int
    municipality_name: str
    operator_id: str
    operator_name: str
    tariff_url: str | None
    total_h4_rp: float  # ElCom's standard-product total for profile H4, Rp./kWh
    grid_h4_rp: float | None = None  # grid usage component (federal charges but the surcharge)
    aidfee_rp: float | None = None  # federal grid surcharge (Art. 35 EnG)
    charge_rp: float | None = None  # cantonal and municipal fees
    # Grid price per kWh without the monthly fee and the federal charges.
    grid_working_rp: float | None = None


def _clean_search(text: str) -> str:
    """Keep only characters that can appear in a Swiss municipality name."""
    return re.sub(r"[^\w\s'.()/-]", "", text, flags=re.UNICODE).strip().lower()


def _tariff_url(operator_id: str, year: int, url: str | None) -> str | None:
    if (operator_id, year) in KNOWN_TARIFF_URLS:
        return KNOWN_TARIFF_URLS[(operator_id, year)]
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


async def _query(session: aiohttp.ClientSession, query: str) -> list[dict[str, str]]:
    try:
        async with session.post(
            LINDAS_ENDPOINT,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
            timeout=_TIMEOUT,
        ) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as err:
        raise ElcomError(str(err)) from err
    try:
        bindings = payload["results"]["bindings"]
    except (KeyError, TypeError) as err:
        raise ElcomError("unexpected answer from LINDAS") from err
    return [{key: value["value"] for key, value in row.items()} for row in bindings]


def _rows_to_operators(rows: list[dict[str, str]], year: int) -> list[OperatorInMunicipality]:
    operators = []
    for row in rows:
        operator_id = row["op"].rsplit("/", 1)[-1]
        operators.append(
            OperatorInMunicipality(
                municipality=int(row["muni"].rsplit("/", 1)[-1]),
                municipality_name=row["muniName"],
                operator_id=operator_id,
                operator_name=row["opName"],
                tariff_url=_tariff_url(operator_id, year, row.get("url")),
                total_h4_rp=float(row["total"]),
                grid_h4_rp=float(row["gridusage"]) if "gridusage" in row else None,
                aidfee_rp=float(row["aidfee"]) if "aidfee" in row else None,
                charge_rp=float(row["charge"]) if "charge" in row else None,
                grid_working_rp=float(row["gridworking"]) if "gridworking" in row else None,
            )
        )
    return operators


async def async_search_municipalities(
    session: aiohttp.ClientSession, text: str, year: int
) -> list[OperatorInMunicipality]:
    """Find operators of municipalities whose name contains ``text``."""
    cleaned = _clean_search(text)
    if len(cleaned) < 2:
        return []
    literal = json.dumps(cleaned)  # a valid, escaped SPARQL string literal
    filter_clause = f"FILTER(CONTAINS(LCASE(STR(?muniName)), {literal}))"
    rows = await _query(session, _QUERY.format(year=year, filter=filter_clause))
    return _rows_to_operators(rows, year)


async def async_operators_for(
    session: aiohttp.ClientSession, municipality: int, year: int
) -> list[OperatorInMunicipality]:
    """Return the operators serving a municipality (by BFS number) in a year."""
    filter_clause = f"FILTER(?muni = <https://ld.admin.ch/municipality/{int(municipality)}>)"
    rows = await _query(session, _QUERY.format(year=year, filter=filter_clause))
    return _rows_to_operators(rows, year)


async def async_fetch_tariff_document(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    """Download and decode an operator's tariff file."""
    try:
        async with session.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT
        ) as response:
            response.raise_for_status()
            raw = await response.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise TariffFileError(str(err)) from err
    try:
        # utf-8-sig: some operators publish files with a byte order mark.
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise TariffFileError("the link does not point to a tariff file") from err
    if not isinstance(document, dict) or not isinstance(document.get("tariffs"), list):
        raise TariffFileError("the file is not in the VSE tariff format")
    return document


async def async_tariff_url_candidates(
    session: aiohttp.ClientSession,
    municipality: int,
    operator_id: str,
    year: int,
    current_url: str | None,
) -> list[str]:
    """Links that may hold an operator's tariffs for ``year``, most likely first.

    ElCom stores one link per year, and in practice it is not always the file
    for that year: for 2026 AIL registered a web page although its file exists
    at ".../tariffs_2026", and AIM's file registered for 2027 also holds 2026.
    So, after the link for the year: the link registered for the next year, and
    that link with the year swapped. Callers check each file for tariffs in force.
    """
    candidates: list[str] = []
    if current_url:
        candidates.append(current_url)
    try:
        next_year = await async_operators_for(session, municipality, year + 1)
    except ElcomError:
        next_year = []
    for operator in next_year:
        if operator.operator_id == operator_id and operator.tariff_url:
            candidates.append(operator.tariff_url)
            if str(year + 1) in operator.tariff_url:
                candidates.append(operator.tariff_url.replace(str(year + 1), str(year)))
    return list(dict.fromkeys(candidates))  # unique, order kept
