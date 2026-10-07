"""Italian day-ahead prices (PUN Index GME and zonal prices) from GME's website.

GME (Gestore dei Mercati Energetici) publishes the MGP results as a ZIP of XML
files, hourly and — since 1 October 2025 — per quarter hour. The download is
the one GME's own web page uses (also used by the MIT-licensed pun_sensor);
it is not a documented API and may change.

Terms (owner's decision of 7 October 2026, docs/DECISIONI.md): each Home
Assistant downloads its own data once or twice a day, nothing is shared or
cached centrally, "Source: GME" is shown, and no paid feature uses this data.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, time, timedelta

import aiohttp

from .italy import ITALY_TZ
from .schedule import Segment

GME_URL = (
    "https://gme.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload/downloadzipfile"
)
GME_HEADERS = {
    # The values GME's own download page sends; without them the server answers 401.
    "moduleid": "12103",
    "tabid": "1749",
    "userid": "-1",
    "referer": "https://gme.mercatoelettrico.org/en-us/Home/Results/Electricity/MGP/Download?valore=Prezzi",
    "User-Agent": "Corrente/0.1 (+https://github.com/MichaelPito/ha-corrente)",
}
ATTRIBUTION = "Fonte: Gestore dei Mercati Energetici S.p.A. (GME)"

# PUN Index GME and the Italian bidding zones, as tagged in GME's XML.
ZONES = ("PUN", "NORD", "CNOR", "CSUD", "SUD", "CALA", "SICI", "SARD")

_TIMEOUT = aiohttp.ClientTimeout(total=60)
_QUARTER = timedelta(minutes=15)
_HOUR = timedelta(hours=1)


class GmeError(Exception):
    """GME could not be reached or answered something unexpected."""


def _price_per_kwh(text: str) -> float:
    """GME writes €/MWh with a decimal comma, e.g. "209,705070"."""
    return float(text.replace(".", "").replace(",", ".")) / 1000


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), ITALY_TZ)


def _segments(xml: bytes, zone: str) -> tuple[date, list[Segment]] | None:
    root = ET.fromstring(xml)
    rows = [row for row in root if not row.tag.endswith("schema")]
    if not rows:
        return None
    quarter = rows[0].tag == "Prezzi15"
    step = _QUARTER if quarter else _HOUR
    day = datetime.strptime(rows[0].findtext("Data") or "", "%Y%m%d").date()
    # Periods count real elapsed time from local midnight: 92 or 100 quarter
    # hours (23 or 25 hours) on the days the clocks change.
    midnight = _local_midnight(day).timestamp()
    segments = []
    for row in rows:
        number = int(row.findtext("Periodo" if quarter else "Ora") or 0)
        value = row.findtext(zone)
        if number < 1 or not value:
            continue
        begin = datetime.fromtimestamp(midnight + (number - 1) * step.total_seconds(), ITALY_TZ)
        segments.append(Segment(begin, begin + step, round(_price_per_kwh(value), 6)))
    return day, sorted(segments, key=lambda s: s.start)


def parse_gme_zip(data: bytes, zone: str = "PUN") -> list[Segment]:
    """Price segments for every day in a GME ZIP, quarter hours preferred."""
    if zone not in ZONES:
        raise ValueError(f"unknown zone {zone}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as err:
        raise GmeError("GME did not send a ZIP file") from err
    quarter: dict[date, list[Segment]] = {}
    hourly: dict[date, list[Segment]] = {}
    for name in archive.namelist():
        if not name.endswith(".xml"):
            continue
        try:
            parsed = _segments(archive.read(name), zone)
        except (ET.ParseError, ValueError) as err:
            raise GmeError(f"unreadable file {name}") from err
        if parsed is None:
            continue
        day, segments = parsed
        (quarter if "Prezzi15" in name else hourly)[day] = segments
    days = sorted(set(quarter) | set(hourly))
    return [segment for day in days for segment in quarter.get(day) or hourly[day]]


async def async_fetch_gme(session: aiohttp.ClientSession, first: date, last: date) -> bytes:
    """Download GME's MGP prices from ``first`` to ``last`` (inclusive)."""
    params = {
        "DataInizio": first.strftime("%Y%m%d"),
        "DataFine": last.strftime("%Y%m%d"),
        "Date": last.strftime("%Y%m%d"),
        "Mercato": "MGP",
        "Settore": "Prezzi",
        "FiltroDate": "InizioFine",
    }
    try:
        async with session.get(
            GME_URL, params=params, headers=GME_HEADERS, timeout=_TIMEOUT
        ) as response:
            response.raise_for_status()
            return await response.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise GmeError(str(err)) from err
