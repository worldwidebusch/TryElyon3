"""Bronontdekking: van ICP naar een lijst catalyst databases.

Drie lagen, in deze volgorde:
  1. Statisch NL-register (bronnen/nl_register.yaml), gefilterd op ICP-match.
  2. LLM bedenkt ICP-specifieke NL-bronnen (branchesites, registers, beurzen).
  3. Live SERP-ontdekking: gerichte NL-zoekopdrachten die ledenlijsten en
     bedrijvengidsen opleveren die niemand handmatig had gevonden.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from . import llm, relevance
from .config import PROJECT_ROOT, SETTINGS
from .models import ICP, Bron, OOGST_API, OOGST_AUTO, OOGST_HANDMATIG
from .search import Zoeker, los_redirects_op

REGISTER_PAD = PROJECT_ROOT / "bronnen" / "nl_register.yaml"

# Domeinen die nooit een bron zijn (ruis uit de SERP filteren)
_RUIS_DOMEINEN = {
    "wikipedia.org", "youtube.com", "facebook.com", "linkedin.com", "x.com",
    "twitter.com", "instagram.com", "pinterest.com", "tiktok.com", "google.com",
    "marktplaats.nl", "bol.com", "amazon.nl", "nu.nl", "nos.nl", "rtl.nl",
    "telegraaf.nl", "ad.nl", "volkskrant.nl", "indeed.com", "glassdoor.nl",
    "tweakers.net", "reddit.com", "quora.com", "medium.com", "wordpress.com",
    "booking.com", "tripadvisor.nl", "thuisbezorgd.nl",
}

# Signaalwoorden dat een URL een lédenlijst/gids is (dus veel bedrijven bevat)
_LIJST_SIGNALEN = (
    "leden", "ledenlijst", "lidbedrijven", "aangesloten", "deelnemers",
    "exposanten", "vind-een", "zoek-een", "vindeen", "zoeken", "overzicht",
    "bedrijven", "bedrijvengids", "gids", "register", "directory", "members",
    "vestigingen", "adressen", "praktijken", "kantoren", "specialisten",
    "vakmensen", "dealers", "partners", "erkende",
)


def _domein_van(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


# Deze tool richt zich uitsluitend op Nederland. Een Belgische of Duitse
# ledenlijst is inhoudelijk misschien prima, maar levert leads buiten je markt.
_BUITENLANDSE_TLDS = (
    ".be", ".de", ".fr", ".uk", ".co.uk", ".es", ".it", ".at", ".ch", ".dk",
    ".se", ".no", ".fi", ".pl", ".pt", ".ie", ".cz", ".us", ".ca", ".au",
)


def _is_ruis(url_of_domein: str) -> bool:
    """Subdomeinen tellen mee: nl.wikipedia.org is net zo goed ruis."""
    domein = _domein_van(url_of_domein) if "://" in url_of_domein else url_of_domein.lower()
    if not domein:
        return True
    if domein.endswith(_BUITENLANDSE_TLDS):
        return True
    return any(domein == r or domein.endswith("." + r) for r in _RUIS_DOMEINEN)


def _laad_register() -> list[dict]:
    if not REGISTER_PAD.exists():
        return []
    data = yaml.safe_load(REGISTER_PAD.read_text(encoding="utf-8")) or {}
    return data.get("bronnen", []) or []


def _matcht_icp(item: dict, icp: ICP) -> bool:
    """Hoort deze registerbron bij dit ICP?

    Op losse substrings matchen gaat mis: 'auto' zit in 'automatisch', waardoor
    de Bovag-ledenlijst opdook bij een tandarts-ICP. We vergelijken daarom op
    woordstammen, met samenstellingen als enige uitzondering ('tandarts' mag
    'tandartspraktijk' vinden).
    """
    trefwoorden = [t.lower().strip() for t in (item.get("trefwoorden") or []) if t.strip()]
    if not trefwoorden:
        return True

    tekst = " ".join(
        icp.branches + icp.zoekwoorden + icp.functietitels + [icp.omschrijving]
    ).lower()
    woorden = relevance._tokens(tekst)

    for trefwoord in trefwoorden:
        stam = relevance._stam(trefwoord)
        if stam in woorden:
            return True
        # Samenstelling: 'tandarts' in 'tandartspraktijk'. Alleen bij termen die
        # lang genoeg zijn om niet toevallig ergens in te zitten.
        if len(stam) >= 6 and any(stam in w for w in woorden):
            return True
    return False


def _connector_beschikbaar(connector: str) -> bool:
    return {
        "google_places": bool(SETTINGS.places_key),
        "kvk": bool(SETTINGS.kvk_key),
        "youtube": bool(SETTINGS.youtube_key),
        "apollo": bool(SETTINGS.apollo_key),
        "hunter": bool(SETTINGS.hunter_key),
    }.get(connector, True)


def uit_register(icp: ICP) -> list[Bron]:
    bronnen: list[Bron] = []
    for item in _laad_register():
        if not _matcht_icp(item, icp):
            continue
        modus = item.get("oogstmodus", OOGST_AUTO)
        connector = item.get("connector", "listing")
        if modus == OOGST_API and not _connector_beschikbaar(connector):
            continue
        bronnen.append(
            Bron(
                naam=item["naam"],
                type=item.get("type", "overig"),
                url=item.get("url", ""),
                connector=connector,
                oogstmodus=modus,
                segment=item["naam"],
                prioriteit=int(item.get("prioriteit", 3)),
                signaal=item.get("signaal", ""),
                aanpak=(item.get("aanpak") or "").strip(),
                params={"site_zoek": item.get("site_zoek", "")},
            )
        )
    return bronnen


async def _verfijn_naar_lijstpagina(zoeker: Zoeker, bronnen: list[Bron], icp: ICP) -> None:
    """Vervang homepage-URL's door de échte ledenlijst binnen datzelfde domein.

    Een bron als 'zorgkaartnederland.nl' levert vanaf de homepage alleen
    footerlinks op. De zoekmachine weet wél welke diepe pagina de praktijken
    bevat — die gebruiken we in plaats van gokken op een URL-structuur.
    """
    branche = (icp.branches or icp.zoekwoorden or [""])[0]
    if not branche:
        return

    for bron in bronnen:
        domein = bron.params.get("site_zoek")
        if not domein:
            continue
        treffers = await zoeker.zoek(f"site:{domein} {branche}", aantal=8)
        for treffer in treffers:
            # De site:-operator wordt niet door elke zoekprovider gehonoreerd
            # (Gemini-grounding bijvoorbeeld niet), dus zelf controleren. Zonder
            # deze check kreeg het BIG-register de URL van een willekeurige site.
            gevonden_domein = _domein_van(treffer["url"])
            if gevonden_domein != domein and not gevonden_domein.endswith("." + domein):
                continue
            pad = urlparse(treffer["url"]).path.strip("/")
            if pad and pad.count("/") <= 2:          # diepe pagina, geen homepage
                bron.url = treffer["url"]
                bron.segment = f"{bron.naam} — {branche}"
                break


# ── Laag 2: LLM bedenkt bronnen ─────────────────────────────────────────────

def _prompt_bronnen(icp: ICP) -> str:
    return f"""CONTEXT
Wij doen koude acquisitie op de NEDERLANDSE markt. Een "catalyst database" is
een plek waar onze doelgroep zichzelf actief en openbaar heeft achtergelaten:
ledenlijsten van branchverenigingen, openbare registers, keurmerkregisters,
exposantenlijsten van vakbeurzen, vergelijkingssites, vakmedia-directories,
gemeentelijke ondernemersverenigingen, franchise-vestigingenlijsten.
Dat is iets ANDERS dan een gekochte database (Apollo, Cognism): het feit dat
iemand daar staat is zélf een koopsignaal.

ONS ICP
{json.dumps(icp.to_dict(), ensure_ascii=False, indent=2)}

OBJECTIEF
Noem 18-25 concrete NEDERLANDSE bronnen waar dit ICP zich openbaar bevindt.

INSTRUCTIES
1. UITSLUITEND Nederlandse bronnen. Geen .com-directories die de NL-markt niet dekken.
2. Alleen bronnen waarvan je vrij zeker weet dat ze bestaan. Twijfel je over de
   exacte URL? Laat "url" leeg en vul "zoekopdracht" met de Nederlandse
   Google-query die de juiste pagina zou vinden.
3. Varieer de types: branchevereniging, openbaar register, keurmerk, beurs,
   vergelijker, vakmedia, franchise, regionale ondernemersvereniging, vacaturesignaal.
4. "segment" is het micro-segment-label; dit wordt de naam van het CSV-bestand.
   Houd het kort en herkenbaar, bijv. "Bovag-garages Noord-Holland".
5. "signaal": in één zin waarom aanwezigheid op deze bron een koopsignaal is.
6. "prioriteit": 1 = veel leads én sterk signaal, 5 = niche/klein.
7. "verwacht_volume": ruwe schatting, bijv. "200-800 bedrijven".
8. Geen LinkedIn/Facebook/Instagram/Discord — die staan al apart in ons systeem.

VOORBEELD VAN ÉÉN ITEM (vorm, niet inhoud)
{{
  "naam": "Techniek Nederland — erkende warmtepompinstallateurs",
  "type": "branchevereniging",
  "url": "https://www.technieknederland.nl/vind-een-vakman",
  "zoekopdracht": "Techniek Nederland erkende installateurs warmtepomp ledenlijst",
  "segment": "Erkende warmtepompinstallateurs",
  "signaal": "Erkenning kost geld en audits — dit zijn geen zzp'ers maar bedrijven met personeel",
  "prioriteit": 1,
  "verwacht_volume": "400-900 bedrijven"
}}

Geef uitsluitend JSON terug in de vorm: {{"bronnen": [ ... ]}}"""


def van_llm(icp: ICP) -> list[Bron]:
    data = llm.vraag_json(llm.SYSTEEM_NL, _prompt_bronnen(icp), max_tokens=6000)
    if not isinstance(data, dict):
        return []
    bronnen: list[Bron] = []
    for item in data.get("bronnen", []) or []:
        if not isinstance(item, dict) or not item.get("naam"):
            continue
        bronnen.append(
            Bron(
                naam=str(item["naam"])[:120],
                type=str(item.get("type", "overig")),
                url=str(item.get("url", "")).strip(),
                connector="listing",
                oogstmodus=OOGST_AUTO,
                segment=str(item.get("segment") or item["naam"])[:80],
                prioriteit=int(item.get("prioriteit", 3) or 3),
                verwacht_volume=str(item.get("verwacht_volume", "")),
                signaal=str(item.get("signaal", "")),
                params={"zoekopdracht": str(item.get("zoekopdracht", ""))},
            )
        )
    return bronnen


# ── Laag 2b: Gemini met Google Search grounding ─────────────────────────────

def _prompt_gegronde_bronnen(icp: ICP) -> str:
    return f"""CONTEXT
Wij doen koude acquisitie op de NEDERLANDSE markt. Een "catalyst database" is
een openbare plek waar onze doelgroep zichzelf actief heeft achtergelaten:
ledenlijsten van branchverenigingen, keurmerkregisters, openbare registers,
exposantenlijsten van vakbeurzen, vergelijkingssites en vakmedia-directories.
Het feit dat iemand daar staat is zélf een koopsignaal.

ONS ICP
{json.dumps(icp.to_dict(), ensure_ascii=False, indent=2)}

OBJECTIEF
ZOEK OP GOOGLE.NL en geef 15-20 Nederlandse bronnen terug die je daadwerkelijk
in de zoekresultaten hebt gezien. Voor elke bron de directe URL van de
LIJSTPAGINA (de pagina met de bedrijven), niet de homepage.

INSTRUCTIES
1. Zoek eerst. Geef alleen bronnen die je in de zoekresultaten bent tegengekomen.
2. Verzin NOOIT een URL. Weet je de exacte lijstpagina niet, laat "url" leeg.
3. Uitsluitend Nederlandse bronnen die de NL-markt dekken.
4. Geef de URL van de ledenlijst/zoekpagina, dus niet www.vereniging.nl maar
   www.vereniging.nl/leden of /vind-een-vakman.
5. Sla LinkedIn, Facebook, Instagram, Discord en Skool over — die zitten al
   apart in ons systeem.
6. Sla ook leveranciers, groothandels, opleidingsinstituten en vakbladen over:
   die verkopen áán onze doelgroep, ze zíjn onze doelgroep niet.
7. "segment" wordt de bestandsnaam van een campagne: kort en herkenbaar.
8. "signaal": in één zin waarom aanwezigheid op deze bron een koopsignaal is.
9. "prioriteit": 1 = veel leads én sterk signaal, 5 = niche of klein.

VERWACHTE OUTPUT (vorm, niet inhoud)
{{"bronnen": [
  {{
    "naam": "Techniek Nederland — vind een vakman",
    "type": "branchevereniging",
    "url": "https://www.technieknederland.nl/vind-een-vakman",
    "segment": "Erkende installateurs",
    "signaal": "Erkenning kost geld en audits: bedrijven met personeel, geen zzp'ers",
    "prioriteit": 1,
    "verwacht_volume": "400-900 bedrijven"
  }}
]}}

Geef uitsluitend dit JSON-object terug, zonder tekst eromheen."""


# Padfragmenten die op een échte ledenlijst wijzen
_PAD_SIGNALEN = (
    "leden", "ledenlijst", "lidbedrijven", "aangesloten", "deelnemers",
    "exposanten", "vind-een", "zoek-een", "vindeen", "zoeken", "overzicht",
    "bedrijvengids", "register", "directory", "members", "vestigingen",
    "praktijken", "kantoren", "specialisten", "vakmensen", "dealers",
    "erkende", "zoekresultaten", "adressen",
)


def _lijkt_ledenlijst_pad(url: str) -> bool:
    """Wijst het URL-pad op een lijst van bedrijven?

    Een losse praktijk als tandartspraktijkxyz.nl haalt dit niet, ook al staat
    'tandarts' in de domeinnaam — en dat is precies de bedoeling.
    """
    pad = urlparse(url).path.lower()
    if pad.strip("/") == "":
        return False                       # homepage is geen ledenlijst
    return any(sig in pad for sig in _PAD_SIGNALEN)


async def via_gemini_grounding(fetcher, icp: ICP) -> list[Bron]:
    """Laat Gemini écht op Google zoeken en lever geverifieerde bronnen.

    Dit is het verschil met laag 2: daar bedenkt het model bronnen uit zijn
    geheugen (en verzint het soms URL's die niet bestaan). Hier komt elke bron
    uit een daadwerkelijk Google-resultaat.
    """
    if not llm.kan_gronden():
        return []

    lus = asyncio.get_running_loop()
    data, geciteerd = await lus.run_in_executor(
        None,
        lambda: llm.vraag_json_gegrond(llm.SYSTEEM_NL, _prompt_gegronde_bronnen(icp)),
    )

    bronnen: list[Bron] = []
    for item in ((data or {}).get("bronnen") or []) if isinstance(data, dict) else []:
        if not isinstance(item, dict) or not item.get("naam"):
            continue
        url = str(item.get("url", "")).strip()
        if url and _is_ruis(url):
            continue
        bronnen.append(Bron(
            naam=str(item["naam"])[:120],
            type=str(item.get("type", "overig")),
            url=url,
            connector="listing",
            oogstmodus=OOGST_AUTO,
            segment=str(item.get("segment") or item["naam"])[:80],
            prioriteit=int(item.get("prioriteit", 2) or 2),
            verwacht_volume=str(item.get("verwacht_volume", "")),
            signaal=str(item.get("signaal", "")),
        ))

    # De pagina's die Gemini daadwerkelijk las zijn zelf kandidaat-bronnen.
    # Die zijn per definitie echt — ze komen uit de zoekresultaten.
    if geciteerd:
        opgelost = await los_redirects_op(fetcher, [g["url"] for g in geciteerd])
        bekend = {b.url for b in bronnen if b.url}
        for citaat in geciteerd:
            echte_url = opgelost.get(citaat["url"], "")
            if not echte_url or echte_url in bekend:
                continue
            if _is_ruis(echte_url):
                continue
            domein = _domein_van(echte_url)
            titel = citaat.get("titel") or domein
            # Strenger dan bij de bronnen die Gemini expliciet noemt: dit zijn
            # zomaar de pagina's die het model onderweg las, dus daar zitten
            # losse praktijken en vakbladen tussen. Alleen het URL-pad telt —
            # een lijstwoord in de paginatitel zegt te weinig.
            if not _lijkt_ledenlijst_pad(echte_url):
                continue
            bekend.add(echte_url)
            bronnen.append(Bron(
                naam=re.sub(r"\s+", " ", titel)[:110],
                type="gevonden via Google (Gemini)",
                url=echte_url,
                connector="listing",
                oogstmodus=OOGST_AUTO,
                segment=domein,
                prioriteit=3,
                signaal="Gevonden in de Google-resultaten die Gemini gebruikte",
            ))

    return bronnen


# ── Laag 3: live SERP-ontdekking ────────────────────────────────────────────

def _prompt_queries(icp: ICP) -> str:
    return f"""CONTEXT
We zoeken via Google.nl naar Nederlandse pagina's die LIJSTEN van bedrijven
bevatten die passen bij ons ICP (ledenlijsten, bedrijvengidsen, registers,
exposantenlijsten). We willen zoekopdrachten die lijstpagina's opleveren,
geen losse bedrijfssites en geen blogartikelen.

ONS ICP
{json.dumps(icp.to_dict(), ensure_ascii=False, indent=2)}

OBJECTIEF
Schrijf 25 Nederlandse Google-zoekopdrachten die zulke lijstpagina's vinden.

INSTRUCTIES
1. Alles in het Nederlands.
2. Combineer branchetermen met lijstwoorden: ledenlijst, aangesloten bedrijven,
   erkende bedrijven, bedrijvengids, exposanten, vind een vakman, overzicht,
   deelnemers, keurmerk, register.
3. Voeg minstens 5 queries toe met een geografische term uit de ICP-regio's.
4. Voeg 3 queries toe die een KOOPSIGNAAL vinden (bijv. vacatures die op de
   pijn wijzen, of nieuwsberichten over uitbreiding).
5. Gebruik hooguit lichte operatoren (site:, intitle:, "quotes"). Geen exotische syntax.
6. Elke query op zichzelf staand en direct plakbaar in Google.

VOORBEELD (vorm)
[
  "tandartspraktijken ledenlijst KNMT Noord-Holland",
  "\\"aangesloten tandartspraktijken\\" overzicht Utrecht",
  "intitle:vacature balie-assistente tandartspraktijk Amsterdam"
]

Geef uitsluitend JSON terug in de vorm: {{"queries": ["...", "..."]}}"""


def _terugval_queries(icp: ICP) -> list[str]:
    termen = (icp.branches or icp.zoekwoorden or [icp.omschrijving])[:6]
    regios = (icp.regios or ["Nederland"])[:4]
    lijstwoorden = ["ledenlijst", "aangesloten bedrijven", "bedrijvengids", "overzicht bedrijven", "erkende bedrijven"]
    queries: list[str] = []
    for term in termen:
        for woord in lijstwoorden:
            queries.append(f"{term} {woord} Nederland")
        for regio in regios:
            queries.append(f"{term} bedrijven {regio}")
    return queries[:30]


def _is_kandidaat_lijst(url: str, titel: str, omschrijving: str, icp: ICP | None = None) -> bool:
    """Is dit een lijstpagina die óók over ons ICP gaat?

    Alleen op lijstsignalen filteren is niet genoeg: "Alle leden — Eerste Kamer"
    bevat 'leden' maar heeft niets met installatiebedrijven te maken. De bron
    moet dus ook een ICP-term noemen.
    """
    if _is_ruis(url):
        return False
    hooi = f"{url.lower()} {titel.lower()} {omschrijving.lower()}"
    if not any(sig in hooi for sig in _LIJST_SIGNALEN):
        return False
    # Het pad moet ook op een lijst wijzen. Zonder deze eis komen losse
    # bedrijfssites en vakbladartikelen binnen op een lijstwoord in hun titel.
    if not _lijkt_ledenlijst_pad(url):
        return False
    if icp is None:
        return True

    termen = {
        stam
        for waarde in (icp.branches + icp.zoekwoorden)
        for stam in relevance._tokens(waarde)
    }
    if not termen:
        return True
    woorden = relevance._tokens(hooi)
    return bool(termen & woorden) or any(t in hooi for t in termen if len(t) > 4)


async def via_serp(zoeker: Zoeker, icp: ICP, *, max_bronnen: int = 40) -> list[Bron]:
    data = llm.vraag_json(llm.SYSTEEM_NL, _prompt_queries(icp), max_tokens=2500)
    queries = (data or {}).get("queries") if isinstance(data, dict) else None
    if not queries:
        queries = _terugval_queries(icp)

    # Met Gemini als zoekmachine is elke query een volledige grounded LLM-call:
    # traag en duur. De grounded laag hierboven heeft het zware werk al gedaan,
    # dus houden we deze blinde laag dan kort.
    limiet = 6 if zoeker.provider == "gemini" else 30
    queries = [str(q) for q in queries][:limiet]

    resultaten = await zoeker.zoek_veel(queries, aantal=15)

    per_domein: dict[str, Bron] = {}
    for r in resultaten:
        url, titel, oms = r.get("url", ""), r.get("titel", ""), r.get("omschrijving", "")
        if not url or not _is_kandidaat_lijst(url, titel, oms, icp):
            continue
        domein = _domein_van(url)
        if domein in per_domein:
            continue
        per_domein[domein] = Bron(
            naam=re.sub(r"\s+", " ", titel)[:110] or domein,
            type="gevonden lijstpagina",
            url=url,
            connector="listing",
            oogstmodus=OOGST_AUTO,
            segment=domein,
            prioriteit=3,
            signaal=oms[:180],
        )
        if len(per_domein) >= max_bronnen:
            break
    return list(per_domein.values())


# ── Samenvoegen ─────────────────────────────────────────────────────────────

async def ontdek(zoeker: Zoeker, icp: ICP, *, max_bronnen: int = 60) -> list[Bron]:
    uit_reg = uit_register(icp)
    await _verfijn_naar_lijstpagina(zoeker, uit_reg, icp)

    gegrond = await via_gemini_grounding(zoeker.f, icp)
    # Kan Gemini gronden, dan is de "verzin bronnen uit je geheugen"-laag
    # overbodig: die levert dezelfde soort bronnen maar zonder geverifieerde URL.
    bedacht = [] if gegrond else van_llm(icp)

    alles = uit_reg + gegrond + bedacht + await via_serp(zoeker, icp)

    # Vul ontbrekende URL's van LLM-bronnen aan met één gerichte zoekopdracht.
    zonder_url = [b for b in alles if not b.url and b.params.get("zoekopdracht")]
    for bron in zonder_url[:15]:
        treffers = await zoeker.zoek(bron.params["zoekopdracht"], aantal=5)
        for t in treffers:
            if not _is_ruis(t["url"]):
                bron.url = t["url"]
                break

    uniek: dict[str, Bron] = {}
    for bron in alles:
        if bron.oogstmodus == OOGST_AUTO and not bron.url:
            continue
        sleutel = bron.sleutel()
        bestaand = uniek.get(sleutel)
        if bestaand is None or bron.prioriteit < bestaand.prioriteit:
            uniek[sleutel] = bron

    gesorteerd = sorted(
        uniek.values(),
        key=lambda b: (b.oogstmodus == OOGST_HANDMATIG, b.prioriteit, b.naam.lower()),
    )
    return gesorteerd[:max_bronnen]
