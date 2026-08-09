"""Tests voor het schrijven van .env en het testen van een Gemini-key."""

import httpx
import pytest

from leadengine import setup


@pytest.fixture
def env_pad(tmp_path, monkeypatch):
    pad = tmp_path / ".env"
    monkeypatch.setattr(setup, "ENV_PAD", pad)
    return pad


def test_maakt_env_aan_als_die_niet_bestaat(env_pad):
    setup.schrijf_sleutel("GEMINI_API_KEY", "AIzaTest123")
    assert env_pad.read_text(encoding="utf-8") == "GEMINI_API_KEY=AIzaTest123\n"


def test_vervangt_bestaande_regel_en_laat_rest_staan(env_pad):
    env_pad.write_text(
        "# commentaar\nGEMINI_API_KEY=oud\nHUNTER_API_KEY=blijf\n", encoding="utf-8"
    )
    setup.schrijf_sleutel("GEMINI_API_KEY", "nieuw")
    regels = env_pad.read_text(encoding="utf-8").splitlines()
    assert regels == ["# commentaar", "GEMINI_API_KEY=nieuw", "HUNTER_API_KEY=blijf"]


def test_voegt_toe_zonder_bestaande_regel(env_pad):
    env_pad.write_text("HUNTER_API_KEY=abc\n", encoding="utf-8")
    setup.schrijf_sleutel("GEMINI_API_KEY", "xyz")
    inhoud = env_pad.read_text(encoding="utf-8")
    assert "HUNTER_API_KEY=abc" in inhoud
    assert inhoud.rstrip().endswith("GEMINI_API_KEY=xyz")


def test_ruimt_duplicaten_op(env_pad):
    env_pad.write_text(
        "GEMINI_API_KEY=een\nANDERE=x\nGEMINI_API_KEY=twee\n", encoding="utf-8"
    )
    setup.schrijf_sleutel("GEMINI_API_KEY", "drie")
    regels = env_pad.read_text(encoding="utf-8").splitlines()
    assert regels.count("GEMINI_API_KEY=drie") == 1
    assert not any(r.startswith("GEMINI_API_KEY=") and r != "GEMINI_API_KEY=drie" for r in regels)


def test_leest_bestand_met_bom(env_pad):
    """.env.example gekopieerd vanuit Kladblok krijgt een BOM mee."""
    env_pad.write_text("GEMINI_API_KEY=\n", encoding="utf-8-sig")
    setup.schrijf_sleutel("GEMINI_API_KEY", "nieuw")
    ruw = env_pad.read_bytes()
    assert not ruw.startswith(b"\xef\xbb\xbf")          # BOM moet weg
    assert ruw == b"GEMINI_API_KEY=nieuw\n"


def test_schrijft_lf_geen_crlf(env_pad):
    setup.schrijf_sleutel("GEMINI_API_KEY", "abc")
    assert b"\r\n" not in env_pad.read_bytes()


def _nep_client(status: int, payload: dict | None = None, tekst: str = ""):
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def post(self, url, params=None, json=None):
            req = httpx.Request("POST", url)
            if payload is not None:
                return httpx.Response(status, json=payload, request=req)
            return httpx.Response(status, text=tekst, request=req)

    return lambda **kw: C()


def test_geldige_key(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(200, {"candidates": []}))
    goed, melding, _versie = setup.test_gemini("AIzaGeldig")
    assert goed and "Werkt" in melding


def test_ongeldige_key_geeft_hint_over_AQ_prefix(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(
        400, {"error": {"message": "API key not valid. Please pass a valid API key."}}
    ))
    goed, melding, _versie = setup.test_gemini("AQ.tokenachtig")
    assert not goed
    assert "AIza" in melding and "AQ." in melding


def test_uitgeschakelde_api_geeft_bruikbare_melding(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(
        403, {"error": {"message": "Generative Language API has not been used in project 123"}}
    ))
    goed, melding, _versie = setup.test_gemini("AIzaX")
    assert not goed and "staat uit" in melding


def test_onbekend_model_geeft_bruikbare_melding(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(404, {}, ""))
    goed, melding, _versie = setup.test_gemini("AIzaX", model="gemini-99-onzin")
    assert not goed and "gemini-99-onzin" in melding


def test_quotum_meldt_dat_de_key_wel_klopt(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(429, {}, ""))
    goed, melding, _versie = setup.test_gemini("AIzaX")
    assert not goed and "geldig" in melding


def _nep_modellenlijst(namen: list[str], status: int = 200):
    payload = {
        "models": [
            {"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
            for n in namen
        ]
    }

    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url, params=None):
            return httpx.Response(status, json=payload, request=httpx.Request("GET", url))

        def post(self, url, params=None, json=None):
            return httpx.Response(404, json={}, request=httpx.Request("POST", url))

    return lambda **kw: C()


def test_lijst_modellen_filtert_op_generatecontent(monkeypatch):
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url, params=None):
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            ]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "Client", lambda **kw: C())
    modellen, fout = setup.lijst_modellen("AIzaX")
    assert modellen == ["gemini-2.5-flash"] and not fout


def test_kies_model_volgt_voorkeur():
    assert setup.kies_model(["gemini-1.5-pro", "gemini-2.5-flash"]) == "gemini-2.5-flash"
    assert setup.kies_model(["gemini-1.5-pro", "gemini-1.5-flash"]) == "gemini-1.5-flash"


def test_kies_model_valt_terug_op_onbekende_naam():
    assert setup.kies_model(["gemini-9-flash-experimental"]) == "gemini-9-flash-experimental"
    assert setup.kies_model(["text-embedding-004", "gemini-toekomst"]) == "gemini-toekomst"
    assert setup.kies_model([]) == ""


def test_404_probeert_beide_api_versies(monkeypatch):
    """Een 404 op v1beta mag niet betekenen dat we v1 overslaan."""
    gezien = []

    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def post(self, url, params=None, json=None):
            gezien.append(url)
            status = 200 if "/v1/" in url else 404
            return httpx.Response(
                status, json={"candidates": []} if status == 200 else
                {"error": {"message": "not found for API version v1beta"}},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(httpx, "Client", lambda **kw: C())
    goed, melding, versie = setup.test_gemini("AIzaX", model="gemini-2.5-flash")
    assert goed and versie == "v1"
    assert any("/v1beta/" in u for u in gezien) and any("/v1/" in u for u in gezien)


def test_ongeldige_key_probeert_geen_tweede_versie(monkeypatch):
    pogingen = []

    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def post(self, url, params=None, json=None):
            pogingen.append(url)
            return httpx.Response(
                400, json={"error": {"message": "API key not valid"}},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(httpx, "Client", lambda **kw: C())
    goed, _melding, versie = setup.test_gemini("AQ.fout", model="gemini-2.5-flash")
    assert not goed and versie == ""
    assert len(pogingen) == 1


def test_kandidaten_sluit_ongeschikte_modellen_uit():
    beschikbaar = [
        "gemini-2.5-flash-preview-tts", "text-embedding-004", "imagen-3.0",
        "gemini-2.5-flash", "gemini-2.5-pro",
    ]
    kandidaten = setup._kandidaten(beschikbaar)
    assert kandidaten[0] == "gemini-2.5-flash"
    assert not any("tts" in k or "embedding" in k or "imagen" in k for k in kandidaten)


def test_search_tool_per_modelgeneratie():
    from leadengine.llm import _search_tool

    assert _search_tool("gemini-2.5-flash") == {"google_search": {}}
    assert _search_tool("gemini-2.0-flash") == {"google_search": {}}
    assert _search_tool("gemini-1.5-pro") == {"google_search_retrieval": {}}


def test_netwerkfout_crasht_niet(monkeypatch):
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **kw): raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(httpx, "Client", lambda **kw: C())
    goed, melding, _versie = setup.test_gemini("AIzaX")
    assert not goed and "Geen verbinding" in melding


def test_schoonmaken_van_geplakte_keys():
    """Onzichtbare tekens uit copy-paste maken een key stilletjes ongeldig."""
    assert setup._schoon_key("\ufeffAIzaAbc") == "AIzaAbc"          # BOM
    assert setup._schoon_key("AIzaAbc\u200b") == "AIzaAbc"          # zero-width space
    assert setup._schoon_key("  AIzaAbc  ") == "AIzaAbc"
    assert setup._schoon_key('"AIzaAbc"') == "AIzaAbc"
    assert setup._schoon_key("'AIzaAbc'") == "AIzaAbc"
    assert setup._schoon_key("GEMINI_API_KEY=AIzaAbc") == "AIzaAbc"
    assert setup._schoon_key("Bearer AIzaAbc") == "AIzaAbc"
    assert setup._schoon_key("AIza\u00a0Abc") == "AIzaAbc"          # non-breaking space
    assert setup._schoon_key("") == ""
