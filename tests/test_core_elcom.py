"""Tests for the ElCom (LINDAS) client and the tariff-file download."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    fold,
    parse_tariff_file,
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


@pytest.mark.parametrize(
    ("typed", "official"),
    [
        ("Zurich", "Zürich"),
        ("Zuerich", "Zürich"),
        ("Neuchatel", "Neuchâtel"),
        ("St Gallen", "St. Gallen"),
        ("Sankt Gallen", "St. Gallen"),
        ("Muenchenstein", "Münchenstein"),
        ("Delemont", "Delémont"),
        ("St-Imier", "Saint-Imier"),
    ],
)
def test_spellings_fold_to_the_same_name(typed: str, official: str) -> None:
    """People type names without accents or dots, or with "ue" for "ü"."""
    assert fold(typed) in fold(official)


async def test_search_ignores_accents_and_knows_other_languages(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(LINDAS_ENDPOINT, text=fixture_text("lindas-lugano-2027.json"))
    session = async_get_clientsession(hass)
    await async_search_municipalities(session, "Zurigo", 2027)
    query = aioclient_mock.mock_calls[-1][2]["query"]
    assert '"zurich"' in query  # the Italian name, folded
    assert "REPLACE(" in query  # the municipality names are folded the same way


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


def _vse(name: str, year: int) -> dict:
    return {
        "dsoName": "Example",
        "tariffs": [
            {
                "tariffName": name,
                "tariffType": "electricity",
                "startDate": f"{year}-01-01",
                "endDate": f"{year}-12-31",
                "prices": {},
            }
        ],
    }


def test_file_with_two_documents() -> None:
    """IWB (Basel) 2027: the 2027 and 2026 files one after the other in one file."""
    raw = (json.dumps(_vse("A", 2027), indent=1) + "\n\n" + json.dumps(_vse("B", 2026))).encode()
    document = parse_tariff_file(raw)
    assert [t["tariffName"] for t in document["tariffs"]] == ["A", "B"]


def test_file_in_utf16() -> None:
    raw = json.dumps(_vse("A", 2027)).encode("utf-16")  # with its byte order mark
    assert parse_tariff_file(raw)["tariffs"][0]["tariffName"] == "A"


def test_file_in_a_zip() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("tarife 2027.json", json.dumps(_vse("A", 2027)))
        archive.writestr("readme.txt", "not a tariff file")
    assert parse_tariff_file(buffer.getvalue())["tariffs"][0]["tariffName"] == "A"


async def test_web_page_linking_to_the_files(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """About 70 operators registered with ElCom the page that links to their files
    (Törbel, Glarus Nord...): the ".json" files linked from it are read together."""
    page = "https://example.ch/strom/tarife"
    aioclient_mock.get(
        page,
        text=(
            "<!DOCTYPE html><html><head>"
            '<link rel="manifest" href="/favicon/manifest.json"></head><body>'
            '<a href="/files/Tarife 2027.json">2027</a>'
            '<a href="https://example.ch/files/tarife-2026.json?v=2">2026</a>'
            '<a href="https://example.ch/wp-json/wp/v2/pages/1">api</a>'
            "</body></html>"
        ),
    )
    aioclient_mock.get("https://example.ch/files/Tarife 2027.json", json=_vse("A", 2027))
    aioclient_mock.get("https://example.ch/files/tarife-2026.json?v=2", json=_vse("B", 2026))
    document = await async_fetch_tariff_document(async_get_clientsession(hass), page)
    assert sorted(t["tariffName"] for t in document["tariffs"]) == ["A", "B"]
    requested = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert not any("manifest" in url or "wp-json" in url for url in requested)


async def test_busy_server_is_asked_twice(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Shared municipal web hosting answers 503 to requests in a row."""
    url = "https://example.ch/tarife.json"
    aioclient_mock.get(url, status=503)
    with (
        patch("custom_components.corrente.core.elcom.asyncio.sleep", AsyncMock()),
        pytest.raises(TariffFileError),
    ):
        await async_fetch_tariff_document(async_get_clientsession(hass), url)
    assert aioclient_mock.call_count == 2


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
