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
    goed, melding = setup.test_gemini("AIzaGeldig")
    assert goed and "Werkt" in melding


def test_ongeldige_key_geeft_hint_over_AQ_prefix(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(
        400, {"error": {"message": "API key not valid. Please pass a valid API key."}}
    ))
    goed, melding = setup.test_gemini("AQ.tokenachtig")
    assert not goed
    assert "AIza" in melding and "AQ." in melding


def test_uitgeschakelde_api_geeft_bruikbare_melding(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(
        403, {"error": {"message": "Generative Language API has not been used in project 123"}}
    ))
    goed, melding = setup.test_gemini("AIzaX")
    assert not goed and "staat uit" in melding


def test_onbekend_model_geeft_bruikbare_melding(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(404, {}, ""))
    goed, melding = setup.test_gemini("AIzaX", model="gemini-99-onzin")
    assert not goed and "gemini-99-onzin" in melding


def test_quotum_meldt_dat_de_key_wel_klopt(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _nep_client(429, {}, ""))
    goed, melding = setup.test_gemini("AIzaX")
    assert not goed and "geldig" in melding


def test_netwerkfout_crasht_niet(monkeypatch):
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **kw): raise httpx.ConnectError("geen netwerk")

    monkeypatch.setattr(httpx, "Client", lambda **kw: C())
    goed, melding = setup.test_gemini("AIzaX")
    assert not goed and "Geen verbinding" in melding
