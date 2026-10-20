"""Tests for the ElCom (LINDAS) client and the tariff-file download."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.corrente.core.elcom import (
    LINDAS_ENDPOINT,
    ElcomError,
    TariffFileError,
    _clean_search,
    async_fetch_tariff_document,
    async_operators_for,
    async_search_municipalities,
    async_tariff_url_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ch"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


async def test_search_finds_lugano(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(LINDAS_ENDPOINT, text=fixture_text("lindas-lugano-2027.json"))
    operators = await async_search_municipalities(async_get_clientsession(hass), "Lugano", 2027)

    assert len(operators) == 1
    ail = operators[0]
    assert ail.municipality == 5192
    assert ail.municipality_name == "Lugano"
    assert ail.operator_id == "31"
    assert "AIL" in ail.operator_name
    assert ail.tariff_url.startswith("https://api-ail.")
    assert ail.total_h4_rp == pytest.approx(25.911)


async def test_grid_price_without_fees_is_read(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """ElCom's grid price per kWh without monthly fees and federal charges, when given."""
    answer = json.loads(fixture_text("lindas-lugano-2027.json"))
    answer["results"]["bindings"][0]["gridworking"] = {"type": "literal", "value": "7.53"}
    aioclient_mock.post(LINDAS_ENDPOINT, text=json.dumps(answer))
    operators = await async_operators_for(async_get_clientsession(hass), 5192, 2027)
    assert operators[0].grid_working_rp == pytest.approx(7.53)


async def test_web_page_links_are_corrected_or_normalised(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(LINDAS_ENDPOINT, text=fixture_text("lindas-bellinzona-zernez-2027.json"))
    operators = await async_operators_for(async_get_clientsession(hass), 5002, 2027)
    by_name = {op.operator_name: op for op in operators}

    # AMB registered "www.amb.ch" with ElCom: the curated table has the real file.
    amb = by_name["Azienda Multiservizi Bellinzona (AMB)"]
    assert amb.tariff_url == "https://www.amb.ch/media/2hcct0s4/tariffe-2027.json"
    # Zernez has two operators; bare host names get a scheme.
    assert by_name["Gemeinde Zernez"].tariff_url == "https://www.ee-en.ch/tarife"


async def test_short_or_empty_search_does_not_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    assert await async_search_municipalities(async_get_clientsession(hass), " ; ", 2027) == []
    assert aioclient_mock.call_count == 0


def test_search_text_is_sanitised() -> None:
    assert _clean_search('Lugano"} DROP') == "lugano drop"
    assert _clean_search("Sant'Antonino") == "sant'antonino"
    assert _clean_search("Biel/Bienne") == "biel/bienne"


async def test_elcom_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LINDAS_ENDPOINT, status=503)
    with pytest.raises(ElcomError):
        await async_operators_for(async_get_clientsession(hass), 5192, 2027)


async def test_fetch_tariff_document_with_bom(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    url = "https://example.ch/tariffe-2027.json"
    aioclient_mock.get(url, content=(FIXTURES / "amb-2027.json").read_bytes())
    document = await async_fetch_tariff_document(async_get_clientsession(hass), url)
    assert document["dsoName"].startswith("Azienda Multiservizi Bellinzona")


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (b"<html><body>Tariffe</body></html>", 200),  # a web page, not a tariff file
        (json.dumps({"hello": "world"}).encode(), 200),  # JSON, but not VSE
        (b'{"error":"File not found"}', 404),  # seen for AEM Massagno 2027
    ],
)
async def test_fetch_tariff_document_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, body: bytes, status: int
) -> None:
    url = "https://example.ch/tariffs"
    aioclient_mock.get(url, content=body, status=status)
    with pytest.raises(TariffFileError):
        await async_fetch_tariff_document(async_get_clientsession(hass), url)


async def test_url_candidates_add_next_year_and_swapped_year(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """AIL 2026: ElCom lists a web page, but next year's link with the year swapped works."""
    aioclient_mock.post(LINDAS_ENDPOINT, text=fixture_text("lindas-lugano-2027.json"))
    candidates = await async_tariff_url_candidates(
        async_get_clientsession(hass),
        5192,
        "31",
        2026,
        "https://www.ail.ch/privati/elettricita/servizi/tariffe",
    )
    assert candidates == [
        "https://www.ail.ch/privati/elettricita/servizi/tariffe",
        "https://api-ail.prod01.apimanagement.eu20.hana.ondemand.com/prd/tariffs_2027",
        "https://api-ail.prod01.apimanagement.eu20.hana.ondemand.com/prd/tariffs_2026",
    ]
