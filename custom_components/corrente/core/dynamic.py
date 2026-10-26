"""Swiss dynamic tariffs: prices per quarter hour from the operator's own API.

Operators that sell a dynamic tariff name its API in their VSE tariff file
(``prices.dynamic.url``). The API follows the VSE / SmartGridready standard
(https://github.com/SmartGridready/SGrSpecifications/tree/master/DynamicTariff),
is public and needs no account. Seen live on 8 October 2026: EKZ, Groupe E and
CKW, all answering in the 2026 format.

Two formats exist for the price of one tariff type in an interval:
- 2026 (v1): a list of components, ``[{"unit": "CHF_kWh", "value": 0.115}, ...]``;
- 2027 (v2): an object, ``{"tariff_name": ..., "energy": {"unit": "CHF/kWh", "value": ...}}``.
Prices exclude VAT. Only the per-kWh part is read here: fixed monthly charges
come from the tariff file, and power charges (CHF/kW) do not apply to households.
Pure Python, no Home Assistant imports.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from yarl import URL

from .schedule import Segment
from .version import USER_AGENT

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_PER_KWH = {"CHF_kWh", "CHF/kWh"}
# Primeo answers only up to 36 hours ahead; a minute less, to be safe.
_MAX_AHEAD = timedelta(hours=36, minutes=-1)


class DynamicTariffError(Exception):
    """The operator's dynamic tariff API could not be read."""


class NotAnApiError(DynamicTariffError):
    """The operator's link answers, but with a web page instead of prices.

    AIL (2026) links its dynamic tariff to a page of its website: Corrente
    cannot read those prices until the operator publishes them in the standard.
    """


def api_host(url: str | None) -> str | None:
    """The host of a dynamic tariff's API link, None when it is not one."""
    return URL(url).host if is_api_url(url) else None


def is_api_url(url: str | None) -> bool:
    """Whether a tariff file's dynamic link is an API Corrente can call.

    Some operators put a web page without a scheme there ("www.aew.ch/dynamic").
    """
    return bool(url) and URL(url).scheme == "https" and bool(URL(url).host)


def request_url(url: str, tariff_type: str, start: datetime, end: datetime) -> URL:
    """The API call for one tariff type in ``[start, end)``.

    The operator's link may already choose the product (EKZ:
    ``?tariff_name=electricity_dynamic``); that part is kept.
    """
    return URL(url).update_query(
        tariff_type=tariff_type,
        start_timestamp=start.isoformat(timespec="seconds"),
        end_timestamp=end.isoformat(timespec="seconds"),
    )


def _per_kwh(item: Any) -> float | None:
    """The per-kWh price of one tariff type in one interval, in either format."""
    if isinstance(item, list):  # 2026 format
        values = [
            float(c["value"])
            for c in item
            if isinstance(c, Mapping) and c.get("unit") in _PER_KWH and c.get("value") is not None
        ]
        return sum(values) if values else None
    if isinstance(item, Mapping):  # 2027 format
        energy = item.get("energy")
        if isinstance(energy, Mapping) and energy.get("unit") in _PER_KWH:
            return float(energy["value"])
    return None


def parse_prices(document: Mapping[str, Any], tariff_type: str) -> list[Segment]:
    """Per-kWh price segments (CHF, without VAT) for one tariff type, in UTC."""
    prices = document.get("prices")
    if not isinstance(prices, list):
        raise DynamicTariffError("the answer has no prices")
    segments = []
    for interval in prices:
        try:
            price = _per_kwh(interval.get(tariff_type))
            if price is None:
                continue
            start = datetime.fromisoformat(interval["start_timestamp"]).astimezone(UTC)
            end = datetime.fromisoformat(interval["end_timestamp"]).astimezone(UTC)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise DynamicTariffError(f"unreadable interval: {err}") from err
        if end > start:
            segments.append(Segment(start, end, round(price, 6)))
    segments.sort(key=lambda s: s.start)
    return segments


async def async_fetch_prices(
    session: aiohttp.ClientSession,
    url: str,
    tariff_type: str,
    start: datetime,
    end: datetime,
    now: datetime | None = None,
) -> list[Segment]:
    """Download the per-kWh prices of a dynamic tariff between ``start`` and ``end``.

    When the API refuses the request (HTTP 400 or 422) it is asked again within
    the limits Primeo sets (2026): no more than 36 hours ahead ("end_timestamp cannot
    be more than 36 hours in the future"), and no ``tariff_type=electricity``, the
    energy prices coming with every other answer.
    """
    latest = (now or datetime.now(UTC)) + _MAX_AHEAD
    latest = latest.replace(minute=latest.minute - latest.minute % 15, second=0, microsecond=0)
    attempts = [(tariff_type, end)]
    if end > latest:
        attempts.append((tariff_type, latest))
    if tariff_type == "electricity":
        attempts += [("grid", until) for _, until in list(attempts)]
    for number, (asked, until) in enumerate(attempts, 1):
        try:
            raw = await _async_get(session, url, asked, start, until)
            break
        except aiohttp.ClientResponseError as err:
            if err.status not in (400, 422) or number == len(attempts):
                raise DynamicTariffError(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DynamicTariffError(str(err)) from err
    try:
        document = json.loads(raw)
    except ValueError as err:  # a web page, not prices
        raise NotAnApiError("the link is a web page, not a price list") from err
    if not isinstance(document, Mapping) or "prices" not in document:
        raise NotAnApiError("the answer is not a price list")
    return [s for s in parse_prices(document, tariff_type) if s.end > start and s.start < end]


async def _async_get(
    session: aiohttp.ClientSession, url: str, tariff_type: str, start: datetime, end: datetime
) -> bytes:
    async with session.get(
        request_url(url, tariff_type, start, end),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=_TIMEOUT,
    ) as response:
        response.raise_for_status()
        return await response.read()
