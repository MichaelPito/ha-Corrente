"""ElCom open data (LINDAS): find a municipality's grid operators and tariff files.

ElCom publishes, for every municipality and year, the grid operator(s) and the
link to the operator's tariff file (Art. 7b StromVV). Licence: Open-Use.
https://energy.ld.admin.ch/elcom/electricityprice
"""

from __future__ import annotations

import asyncio
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

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
  ?gridworking ?gridfix ?metering WHERE {{
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
  OPTIONAL {{ ?obs elcom:fixcosts ?gridfix }}
  OPTIONAL {{ ?obs elcom:meteringrate ?metering }}
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
    # The grid's fixed costs for a household, CHF a year.
    grid_fix_chf: float | None = None
    # Metering, Rp./kWh at 4500 kWh a year (the household's metering fee).
    metering_rp: float | None = None


def _clean_search(text: str) -> str:
    """Keep only characters that can appear in a Swiss municipality name."""
    return re.sub(r"[^\w\s'.()/-]", "", text, flags=re.UNICODE).strip().lower()


# Spellings people type for the same name, folded the same way on both sides of the
# search: "Zurich" and "Zuerich" find "Zürich", "St Gallen" finds "St. Gallen".
_FOLDS: tuple[tuple[str, str], ...] = (
    *(
        (accented, plain)
        for plain, letters in (
            ("a", "äàâá"),
            ("e", "éèêë"),
            ("i", "îïí"),
            ("o", "öôó"),
            ("u", "üûùú"),
            ("c", "ç"),
        )
        for accented in letters
    ),
    ("ae", "a"),
    ("oe", "o"),
    ("ue", "u"),
    (".", ""),
    ("(", ""),  # "Aesch BL" finds "Aesch (BL)"
    (")", ""),
    ("sankt", "st"),
    ("saint", "st"),
)

# Names of the larger towns in the other languages (and in English), folded.
_EXONYMS = {
    "zurigo": "zurich",
    "geneva": "geneve",
    "ginevra": "geneve",
    "genf": "geneve",
    "basilea": "basel",
    "bale": "basel",
    "berna": "bern",
    "berne": "bern",
    "lucerna": "luzern",
    "lucerne": "luzern",
    "san gallo": "st gallen",
    "coira": "chur",
    "friburgo": "fribourg",
    "freiburg": "fribourg",
    "soletta": "solothurn",
    "sciaffusa": "schaffhausen",
    "neuenburg": "neuchatel",
    "losanna": "lausanne",
    "sitten": "sion",
    "zugo": "zug",
    "lauis": "lugano",
    "bellenz": "bellinzona",
}


def fold(text: str) -> str:
    """A name or a search folded so that spellings of the same name are equal."""
    text = text.lower()
    for written, plain in _FOLDS:
        text = text.replace(written, plain)
    return text


def _fold_sparql(expression: str) -> str:
    """The same folding as ``fold``, in SPARQL (REPLACE takes a regular expression)."""
    for written, plain in _FOLDS:
        expression = f"REPLACE({expression}, {json.dumps(re.escape(written))}, {json.dumps(plain)})"
    return expression


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
                grid_fix_chf=float(row["gridfix"]) if "gridfix" in row else None,
                metering_rp=float(row["metering"]) if "metering" in row else None,
            )
        )
    return operators


async def async_search_municipalities(
    session: aiohttp.ClientSession, text: str, year: int
) -> list[OperatorInMunicipality]:
    """Find operators of municipalities whose name contains ``text``."""
    cleaned = fold(_clean_search(text))
    if len(cleaned) < 2:
        return []
    cleaned = _EXONYMS.get(cleaned, cleaned)
    literal = json.dumps(cleaned)  # a valid, escaped SPARQL string literal
    name = _fold_sparql("LCASE(STR(?muniName))")
    filter_clause = f"FILTER(CONTAINS({name}, {literal}))"
    rows = await _query(session, _QUERY.format(year=year, filter=filter_clause))
    return _rows_to_operators(rows, year)


async def async_operators_for(
    session: aiohttp.ClientSession, municipality: int, year: int
) -> list[OperatorInMunicipality]:
    """Return the operators serving a municipality (by BFS number) in a year."""
    filter_clause = f"FILTER(?muni = <https://ld.admin.ch/municipality/{int(municipality)}>)"
    rows = await _query(session, _QUERY.format(year=year, filter=filter_clause))
    return _rows_to_operators(rows, year)


# A tariff file found on a web page: links whose path ends in ".json", but not the
# site's icon manifest or WordPress's own API.
_JSON_LINK = re.compile(r"""href=["']([^"'#]+?\.json(?:\?[^"']*)?)["']""", re.IGNORECASE)
_NOT_TARIFF_LINK = re.compile(r"manifest[^/]*\.json|/wp-json/|oembed", re.IGNORECASE)
_HTML = re.compile(r"<html|<!doctype html", re.IGNORECASE)
_MAX_LINKS_FROM_PAGE = 6
_RETRY_STATUSES = {429, 502, 503, 504}


async def _async_download(session: aiohttp.ClientSession, url: str) -> bytes:
    """The body at ``url``; one more try after a server's passing error."""
    for attempt in (1, 2):
        try:
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT
            ) as response:
                if response.status in _RETRY_STATUSES and attempt == 1:
                    await asyncio.sleep(2)
                    continue
                response.raise_for_status()
                return await response.read()
        except aiohttp.ServerDisconnectedError as err:
            if attempt == 2:
                raise TariffFileError(str(err)) from err
            await asyncio.sleep(2)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TariffFileError(str(err)) from err
    raise TariffFileError(f"{url}: no answer")  # pragma: no cover


def _decode(raw: bytes) -> str:
    """Text of a file: UTF-16 with its byte order mark (two operators), else UTF-8."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")  # some files start with a byte order mark


def _json_documents(text: str) -> list[Any]:
    """Every JSON document in ``text``: IWB (Basel) publishes 2027 and 2026 one after
    the other in the same file."""
    decoder, documents, position = json.JSONDecoder(), [], 0
    try:
        while True:
            while position < len(text) and text[position].isspace():
                position += 1
            if position >= len(text):
                return documents
            document, position = decoder.raw_decode(text, position)
            documents.append(document)
    except json.JSONDecodeError as err:
        raise TariffFileError("the link does not point to a tariff file") from err


def parse_tariff_file(raw: bytes) -> dict[str, Any]:
    """An operator's tariff file in the VSE format, from what its link returns.

    Also read: a zip holding the file (two operators), UTF-16, and several
    documents in one file, whose tariffs are put together.
    """
    if raw[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = [n for n in archive.namelist() if n.lower().endswith(".json")]
                parts = [parse_tariff_file(archive.read(name)) for name in members]
        except zipfile.BadZipFile as err:
            raise TariffFileError("the link does not point to a tariff file") from err
        if not parts:
            raise TariffFileError("the archive holds no tariff file")
        return _merged(parts)
    try:
        documents = _json_documents(_decode(raw))
    except UnicodeDecodeError as err:
        raise TariffFileError("the link does not point to a tariff file") from err
    files = [d for d in documents if isinstance(d, dict) and isinstance(d.get("tariffs"), list)]
    if not files:
        raise TariffFileError("the file is not in the VSE tariff format")
    return _merged(files)


def _merged(files: list[dict[str, Any]]) -> dict[str, Any]:
    if len(files) == 1:
        return files[0]
    return {**files[0], "tariffs": [tariff for file in files for tariff in file["tariffs"]]}


def _links_to_files(page: str, base_url: str) -> list[str]:
    links = [urljoin(base_url, html.unescape(link)) for link in _JSON_LINK.findall(page)]
    links = [
        link for link in links if link.startswith("http") and not _NOT_TARIFF_LINK.search(link)
    ]
    return list(dict.fromkeys(links))[:_MAX_LINKS_FROM_PAGE]


async def async_fetch_tariff_document(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    """Download and decode an operator's tariff file.

    About 70 operators registered with ElCom the web page that links to their
    file rather than the file: then the ".json" files linked from the page are
    read and put together (often this year's and next year's), and callers pick
    the tariffs in force.
    """
    raw = await _async_download(session, url)
    try:
        return parse_tariff_file(raw)
    except TariffFileError as err:
        try:
            page = _decode(raw)
        except UnicodeDecodeError:
            raise err from None
        if not _HTML.search(page[:5000]):
            raise
        parts = []
        for link in _links_to_files(page, url):
            try:
                parts.append(parse_tariff_file(await _async_download(session, link)))
            except TariffFileError:
                continue
        if not parts:
            raise TariffFileError("the link does not point to a tariff file") from err
        return _merged(parts)


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
