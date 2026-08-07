"""ICP bepalen — uit een vrije omschrijving óf uit een bestaande website.

Bij een website: we lezen de homepage + een handvol relevante subpagina's,
en leiden daaruit af wie hún ideale klant is (dus niet: wie zíj zijn).
"""

from __future__ import annotations

import asyncio
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import llm
from .http import Fetcher
from .models import ICP

_SITE_HINTS = (
    "diensten", "services", "oplossingen", "solutions", "voor-wie", "doelgroep",
    "klanten", "cases", "referenties", "over-ons", "about", "branches",
    "sectoren", "producten", "aanbod", "wat-we-doen", "prijzen", "tarieven",
)


async def _lees_site(fetcher: Fetcher, url: str, *, max_paginas: int = 6) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    opgehaald = await fetcher.html(url)
    if not opgehaald:
        return ""
    eind_url, html = opgehaald

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    brokken = [f"### {eind_url}\n{soup.get_text(' ', strip=True)[:6000]}"]

    kandidaten: list[str] = []
    for a in soup.find_all("a", href=True):
        absoluut = urljoin(eind_url, a["href"]).split("#")[0]
        pad = absoluut.lower()
        if any(h in pad for h in _SITE_HINTS) and absoluut not in kandidaten:
            kandidaten.append(absoluut)
        if len(kandidaten) >= max_paginas:
            break

    async def _pagina(u: str) -> str:
        r = await fetcher.html(u)
        if not r:
            return ""
        s = BeautifulSoup(r[1], "lxml")
        for t in s(["script", "style", "noscript", "svg"]):
            t.decompose()
        return f"### {u}\n{s.get_text(' ', strip=True)[:3500]}"

    for stuk in await asyncio.gather(*(_pagina(u) for u in kandidaten), return_exceptions=True):
        if isinstance(stuk, str) and stuk:
            brokken.append(stuk)

    return "\n\n".join(brokken)[:30000]


def _prompt_uit_omschrijving(omschrijving: str) -> str:
    return f"""CONTEXT
Een Nederlands bedrijf gaat koude e-mail/telefonische acquisitie doen op de
Nederlandse markt. Zij beschrijven hun ideale klant hieronder in eigen woorden.

OBJECTIEF
Zet die losse omschrijving om in een scherp, machine-bruikbaar ICP dat gebruikt
wordt om (a) Nederlandse bronnen te vinden en (b) zoekopdrachten te bouwen.

INSTRUCTIES
1. Vertaal vage termen naar concrete NL-brancheaanduidingen zoals ze in het
   Handelsregister, op branchesites en in Google Maps voorkomen.
2. functietitels: gebruik Nederlandse titels zoals ze écht op websites staan
   (bijv. "praktijkhouder", "vestigingsmanager", "eigenaar"), niet Engelse.
3. regios: als er niets genoemd is, gebruik ["Nederland"].
4. zoekwoorden: 10-20 losse Nederlandse termen die op de website van zo'n
   bedrijf staan. Geen operatoren, geen zinnen.
5. branchverenigingen: noem échte Nederlandse verenigingen/keurmerken voor deze
   branche (bijv. Bovag, Techniek Nederland, KNMT, NVM, Koninklijke Horeca
   Nederland, ANKO, NBBU). Laat leeg als je er geen kent — verzin er geen.
6. koopsignalen: waarneembare signalen dat ze NU een probleem hebben
   (bijv. "vacature voor receptioniste open", "bereikbaarheid als klacht in
   Google-reviews", "recent nieuw pand geopend").
7. uitsluiten: types organisaties die eruit gefilterd moeten worden.

OMSCHRIJVING VAN DE GEBRUIKER
\"\"\"{omschrijving}\"\"\"

VOORBEELD VAN DE VERWACHTE OUTPUT (vorm, niet inhoud)
{{
  "omschrijving": "Tandartspraktijken in de Randstad met 2-8 behandelkamers die telefonisch slecht bereikbaar zijn",
  "branches": ["tandartspraktijk", "mondzorg", "orthodontiepraktijk", "implantologie"],
  "functietitels": ["praktijkhouder", "praktijkmanager", "tandarts-eigenaar"],
  "bedrijfsgrootte": "3-25 medewerkers",
  "regios": ["Noord-Holland", "Zuid-Holland", "Utrecht"],
  "pijnpunten": ["telefoon wordt niet opgenomen tijdens behandelingen", "no-shows"],
  "koopsignalen": ["vacature balie-assistente", "reviews klagen over bereikbaarheid"],
  "zoekwoorden": ["tandartspraktijk", "mondhygiënist", "nieuwe patiënten welkom", "spoedtandarts"],
  "branchverenigingen": ["KNMT", "ANT"],
  "uitsluiten": ["ziekenhuizen", "tandtechnische laboratoria", "opleidingen"]
}}

Geef nu uitsluitend het JSON-object voor de omschrijving hierboven."""


def _prompt_uit_website(url: str, sitetekst: str) -> str:
    return f"""CONTEXT
Hieronder staat de tekst van de website van een Nederlands bedrijf ({url}).
Dit bedrijf wil koude acquisitie doen op de Nederlandse markt.

OBJECTIEF
Leid af wie de IDEALE KLANT van dit bedrijf is. Let op: je beschrijft NIET dit
bedrijf zelf, maar het type organisatie dat zij zouden moeten benaderen.

INSTRUCTIES
1. Baseer je op wat ze verkopen, welke cases/klanten ze noemen, welke
   sectorpagina's ze hebben en welke problemen hun copy adresseert.
2. Zijn er expliciete klantvoorbeelden? Laat het ICP daar zwaar op leunen.
3. Alle waarden in het Nederlands, precies zoals NL-bedrijven zichzelf noemen.
4. Verzin geen branchverenigingen die je niet zeker weet — leeg is beter.
5. Zet in "omschrijving" één zin die het ICP samenvat.

WEBSITETEKST
\"\"\"
{sitetekst}
\"\"\"

Geef uitsluitend een JSON-object met exact deze sleutels:
omschrijving, branches, functietitels, bedrijfsgrootte, regios, pijnpunten,
koopsignalen, zoekwoorden, branchverenigingen, uitsluiten."""


def _terugval_icp(omschrijving: str) -> ICP:
    """Zonder LLM: bouw een bruikbaar ICP uit de kale tekst."""
    woorden = [w.strip(".,;:!?").lower() for w in omschrijving.split()]
    stop = {
        "en", "de", "het", "een", "in", "van", "voor", "met", "die", "dat", "op",
        "bij", "aan", "of", "te", "is", "zijn", "ze", "hun", "we", "ik", "naar",
        "alle", "meer", "dan", "als", "om", "er", "wat", "wie", "waar", "tot",
    }
    kern = [w for w in woorden if len(w) > 3 and w not in stop]
    uniek = list(dict.fromkeys(kern))
    return ICP(
        omschrijving=omschrijving.strip(),
        branches=uniek[:6],
        functietitels=["eigenaar", "directeur", "manager"],
        regios=["Nederland"],
        zoekwoorden=uniek[:20],
    )


async def bepaal_icp(
    fetcher: Fetcher,
    *,
    omschrijving: str = "",
    website: str = "",
) -> ICP:
    if website:
        sitetekst = await _lees_site(fetcher, website)
        if not sitetekst:
            raise SystemExit(f"Kon {website} niet lezen — controleer de URL of gebruik --icp.")
        data = llm.vraag_json(llm.SYSTEEM_NL, _prompt_uit_website(website, sitetekst))
        if isinstance(data, dict):
            icp = ICP.from_dict(data)
            icp.omschrijving = icp.omschrijving or f"ICP afgeleid van {website}"
            return icp
        # zonder LLM: gebruik de sitetekst als ruwe basis
        return _terugval_icp(sitetekst[:600])

    data = llm.vraag_json(llm.SYSTEEM_NL, _prompt_uit_omschrijving(omschrijving))
    if isinstance(data, dict):
        icp = ICP.from_dict(data)
        icp.omschrijving = icp.omschrijving or omschrijving
        if not icp.regios:
            icp.regios = ["Nederland"]
        return icp
    return _terugval_icp(omschrijving)
