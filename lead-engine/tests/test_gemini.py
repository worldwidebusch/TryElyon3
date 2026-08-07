"""Tests voor de Gemini-laag met gemockte API-responses.

Verifieert de request-vorm (die moet exact kloppen met de Gemini REST API) en
de verwerking van grounding-metadata, zonder een echte key nodig te hebben.
"""

import asyncio
import json

import httpx
import pytest

from leadengine import llm, sources
from leadengine.config import SETTINGS
from leadengine.models import ICP


def _antwoord(tekst: str, chunks: list[dict] | None = None) -> dict:
    kandidaat = {"content": {"parts": [{"text": tekst}], "role": "model"}}
    if chunks is not None:
        kandidaat["groundingMetadata"] = {"groundingChunks": chunks}
    return {"candidates": [kandidaat]}


@pytest.fixture
def gemini(monkeypatch):
    """Zet een neppe Gemini-key en vang de uitgaande request op."""
    monkeypatch.setattr(SETTINGS, "gemini_key", "test-key")
    monkeypatch.setattr(SETTINGS, "anthropic_key", "")
    monkeypatch.setattr(SETTINGS, "llm_provider", "auto")
    opgevangen: dict = {}

    def maak_client(payload):
        class NepClient:
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def post(self, url, params=None, json=None, headers=None):
                opgevangen["url"] = url
                opgevangen["params"] = params
                opgevangen["body"] = json
                return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

        return lambda **kw: NepClient()

    return opgevangen, maak_client


def test_provider_kiest_gemini(gemini):
    assert llm.provider() == "gemini"
    assert llm.beschikbaar() and llm.kan_gronden()


def test_request_vorm_zonder_grounding(gemini, monkeypatch):
    opgevangen, maak_client = gemini
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord('{"a": 1}')))

    assert llm.vraag_json("systeem", "prompt") == {"a": 1}

    body = opgevangen["body"]
    assert body["contents"][0]["parts"][0]["text"] == "prompt"
    assert body["systemInstruction"]["parts"][0]["text"] == "systeem"
    # zonder grounding mag JSON-mode aan
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "tools" not in body
    assert opgevangen["params"]["key"] == "test-key"
    assert SETTINGS.gemini_model in opgevangen["url"]


def test_request_vorm_met_grounding(gemini, monkeypatch):
    opgevangen, maak_client = gemini
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord('{"bronnen": []}', [])))

    llm.vraag_json_gegrond("systeem", "prompt")

    body = opgevangen["body"]
    assert body["tools"] == [{"google_search": {}}]
    # KRITIEK: JSON-mode mag NIET samen met de search-tool
    assert "responseMimeType" not in body["generationConfig"]


def test_grounding_chunks_worden_bronnen(gemini, monkeypatch):
    chunks = [
        {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc",
                 "title": "Techniek Nederland — vind een vakman"}},
        {"web": {"uri": "https://redirect/x", "title": "Bovag ledenlijst"}},
    ]
    _, maak_client = gemini
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord('{"bronnen": []}', chunks)))

    data, geciteerd = llm.vraag_json_gegrond("s", "p")
    assert data == {"bronnen": []}
    assert [g["titel"] for g in geciteerd] == [
        "Techniek Nederland — vind een vakman", "Bovag ledenlijst"
    ]


def test_json_uit_markdown_fence(gemini, monkeypatch):
    _, maak_client = gemini
    tekst = 'Hier is het resultaat:\n```json\n{"bronnen": [{"naam": "X"}]}\n```\n'
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord(tekst, [])))
    data, _ = llm.vraag_json_gegrond("s", "p")
    assert data["bronnen"][0]["naam"] == "X"


def test_fout_geeft_none_geen_crash(gemini, monkeypatch):
    def kapotte_client(**kw):
        class C:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, *a, **kw): raise httpx.ConnectError("geen netwerk")
        return C()

    monkeypatch.setattr(httpx, "Client", kapotte_client)
    assert llm.vraag_json("s", "p") is None
    assert llm.vraag_json_gegrond("s", "p") == (None, [])


def test_grounded_bronontdekking_bouwt_bron_objecten(gemini, monkeypatch):
    _, maak_client = gemini
    payload = json.dumps({"bronnen": [{
        "naam": "Techniek Nederland — vind een vakman",
        "type": "branchevereniging",
        "url": "https://www.technieknederland.nl/vind-een-vakman",
        "segment": "Erkende installateurs",
        "signaal": "Erkenning kost geld en audits",
        "prioriteit": 1,
        "verwacht_volume": "400-900 bedrijven",
    }]})
    chunks = [{"web": {"uri": "https://www.bovag.nl/ledenlijst", "title": "Bovag ledenlijst"}}]
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord(payload, chunks)))

    class NepFetcher:
        async def eind_url(self, url): return url

    icp = ICP(branches=["installatiebedrijf"], regios=["Noord-Brabant"])
    bronnen = asyncio.run(sources.via_gemini_grounding(NepFetcher(), icp))

    op_naam = {b.naam: b for b in bronnen}
    hoofd = op_naam["Techniek Nederland — vind een vakman"]
    assert hoofd.url == "https://www.technieknederland.nl/vind-een-vakman"
    assert hoofd.prioriteit == 1 and hoofd.segment == "Erkende installateurs"
    # De pagina die Gemini daadwerkelijk las komt er als extra bron bij. Die
    # passeert bewust zonder ICP-term-poort: de zoekopdracht was al ICP-gericht.
    assert any(b.url == "https://www.bovag.nl/ledenlijst" for b in bronnen)


def test_ruisdomeinen_uit_grounding_worden_geweerd(gemini, monkeypatch):
    _, maak_client = gemini
    payload = json.dumps({"bronnen": [
        {"naam": "Wikipedia lijst", "url": "https://nl.wikipedia.org/wiki/Lijst_van_leden"},
    ]})
    chunks = [{"web": {"uri": "https://www.linkedin.com/company/leden", "title": "LinkedIn leden"}}]
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord(payload, chunks)))

    class NepFetcher:
        async def eind_url(self, url): return url

    bronnen = asyncio.run(sources.via_gemini_grounding(NepFetcher(), ICP(branches=["test"])))
    assert bronnen == []


def test_zoek_gegrond_geeft_zoekresultaatvorm(gemini, monkeypatch):
    _, maak_client = gemini
    chunks = [{"web": {"uri": "https://www.knmt.nl/leden", "title": "KNMT ledenlijst"}}]
    monkeypatch.setattr(httpx, "Client", maak_client(_antwoord("Gevonden pagina's...", chunks)))

    resultaten = llm.zoek_gegrond("tandartspraktijken ledenlijst")
    assert resultaten[0]["url"] == "https://www.knmt.nl/leden"
    assert resultaten[0]["titel"] == "KNMT ledenlijst"
    assert "omschrijving" in resultaten[0]
