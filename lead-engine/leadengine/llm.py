"""LLM-laag met twee providers: Gemini en Claude.

Prompts volgen COIE: Context, Objectief, Instructies, Voorbeelden.

Gemini heeft één eigenschap die deze tool bijzonder goed past: **Google Search
grounding**. Het model zoekt dan écht op Google voordat het antwoordt en geeft
de gebruikte bron-URL's terug. Voor bronontdekking is dat het verschil tussen
"verzin plausibele ledenlijsten" en "geef ledenlijsten die aantoonbaar bestaan".

Alles is optioneel: zonder key vallen de functies terug op None en draait de
motor op het statische NL-bronnenregister.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import SETTINGS

_anthropic_client = None

GEMINI_BASIS = "https://generativelanguage.googleapis.com/v1beta/models"


# ── Providerkeuze ───────────────────────────────────────────────────────────

def provider() -> str:
    """'gemini', 'anthropic' of '' (geen LLM beschikbaar)."""
    voorkeur = SETTINGS.llm_provider.lower().strip()
    if voorkeur == "gemini" and SETTINGS.gemini_key:
        return "gemini"
    if voorkeur == "anthropic" and SETTINGS.anthropic_key:
        return "anthropic"
    # auto: Gemini eerst — die kan grounden, Claude niet vanuit deze tool
    if SETTINGS.gemini_key:
        return "gemini"
    if SETTINGS.anthropic_key:
        return "anthropic"
    return ""


def beschikbaar() -> bool:
    return bool(provider())


def kan_gronden() -> bool:
    """Kunnen we Google Search grounding gebruiken?"""
    return provider() == "gemini"


# ── JSON uit modeltekst peuteren ────────────────────────────────────────────

def _pak_json(tekst: str) -> Any | None:
    tekst = (tekst or "").strip()
    if tekst.startswith("```"):
        tekst = re.sub(r"^```(?:json)?\s*|\s*```$", "", tekst, flags=re.S)
    try:
        return json.loads(tekst)
    except Exception:
        pass
    for opener, sluiter in (("{", "}"), ("[", "]")):
        start, eind = tekst.find(opener), tekst.rfind(sluiter)
        if start != -1 and eind > start:
            try:
                return json.loads(tekst[start:eind + 1])
            except Exception:
                continue
    return None


# ── Gemini ──────────────────────────────────────────────────────────────────

def _gemini_call(
    systeem: str,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    gronden: bool,
    model: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Geeft (tekst, bronnen) terug. `bronnen` is leeg zonder grounding."""
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": systeem}]},
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if gronden:
        # Met de search-tool aan mag je géén responseMimeType=application/json
        # meegeven; we vragen de JSON dus in de prompt en parsen uit de tekst.
        body["tools"] = [{"google_search": {}}]
    else:
        body["generationConfig"]["responseMimeType"] = "application/json"

    url = f"{GEMINI_BASIS}/{model or SETTINGS.gemini_model}:generateContent"
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            url,
            params={"key": SETTINGS.gemini_key},
            json=body,
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    kandidaten = data.get("candidates") or []
    if not kandidaten:
        return "", []

    kandidaat = kandidaten[0]
    tekst = "".join(
        deel.get("text", "")
        for deel in (kandidaat.get("content") or {}).get("parts", [])
    )

    bronnen: list[dict[str, str]] = []
    grond = kandidaat.get("groundingMetadata") or {}
    for brok in grond.get("groundingChunks") or []:
        web = brok.get("web") or {}
        if web.get("uri"):
            bronnen.append({
                "url": web["uri"],                       # redirect-URL van Google
                "titel": web.get("title", ""),
                "domein": web.get("domain", "") or web.get("title", ""),
            })
    return tekst, bronnen


# ── Claude ──────────────────────────────────────────────────────────────────

def _anthropic_call(systeem: str, prompt: str, *, max_tokens: int, temperature: float) -> str:
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=SETTINGS.anthropic_key)

    antwoord = _anthropic_client.messages.create(
        model=SETTINGS.anthropic_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=systeem,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        blok.text for blok in antwoord.content if getattr(blok, "type", "") == "text"
    )


# ── Publieke API ────────────────────────────────────────────────────────────

def vraag_json(
    systeem: str,
    prompt: str,
    *,
    max_tokens: int = 4000,
    temperature: float = 0.3,
) -> Any | None:
    """Vraag om JSON. Geeft None als er geen LLM beschikbaar is of iets misgaat."""
    huidige = provider()
    if not huidige:
        return None
    try:
        if huidige == "gemini":
            tekst, _ = _gemini_call(
                systeem, prompt,
                max_tokens=max_tokens, temperature=temperature, gronden=False,
            )
        else:
            tekst = _anthropic_call(
                systeem, prompt, max_tokens=max_tokens, temperature=temperature
            )
    except Exception as fout:
        print(f"  ! LLM ({huidige}) niet bereikbaar: {fout} — val terug op register")
        return None
    return _pak_json(tekst)


def vraag_json_gegrond(
    systeem: str,
    prompt: str,
    *,
    max_tokens: int = 8000,
    temperature: float = 0.2,
) -> tuple[Any | None, list[dict[str, str]]]:
    """Als `vraag_json`, maar het model zoekt eerst op Google.

    Geeft (json, gebruikte_bronnen) terug. De bron-URL's zijn Google-redirects;
    `sources.py` lost ze op naar de echte URL.
    """
    if not kan_gronden():
        return vraag_json(systeem, prompt, max_tokens=max_tokens, temperature=temperature), []
    try:
        tekst, bronnen = _gemini_call(
            systeem, prompt,
            max_tokens=max_tokens, temperature=temperature, gronden=True,
        )
    except Exception as fout:
        print(f"  ! Gemini grounding mislukt: {fout} — val terug op gewone zoekopdracht")
        return None, []
    return _pak_json(tekst), bronnen


def zoek_gegrond(query: str, *, max_tokens: int = 2000) -> list[dict[str, str]]:
    """Gebruik Gemini's Google Search als losse zoekmachine.

    Levert dezelfde vorm als de andere zoekproviders: titel/url/omschrijving.
    """
    if not kan_gronden():
        return []
    try:
        tekst, bronnen = _gemini_call(
            "Je bent een Nederlandse zoekassistent. Zoek op Google.nl en vat de "
            "gevonden pagina's kort samen. Antwoord in het Nederlands.",
            f"Zoek: {query}\n\nNoem de gevonden pagina's met hun titel en waar ze over gaan.",
            max_tokens=max_tokens, temperature=0.1, gronden=True,
        )
    except Exception:
        return []
    return [
        {"titel": b["titel"], "url": b["url"], "omschrijving": tekst[:200]}
        for b in bronnen
    ]


SYSTEEM_NL = (
    "Je bent een Nederlandse B2B-leadresearcher. Je kent de Nederlandse markt "
    "door en door: branchverenigingen, openbare registers, vakmedia, beurzen, "
    "marktplaatsen en online communities. Je antwoordt UITSLUITEND met geldige "
    "JSON, zonder uitleg eromheen, en altijd in het Nederlands."
)
