"""API-connectors: Google Places, KvK, YouTube, Apollo, Hunter, podcasts.

Elke connector geeft niets terug wanneer zijn key ontbreekt — de motor slaat
'm dan gewoon over.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .. import extract
from ..config import SETTINGS
from ..http import Fetcher
from ..models import Bron, ICP, Lead
from ..regions import bepaal_provincie, steden_voor
from .website import oogst_domein


# ── Google Places (New) ─────────────────────────────────────────────────────

_PLACES_FIELDS = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.primaryTypeDisplayName",
    "places.businessStatus",
    "nextPageToken",
])


async def oogst_places(
    fetcher: Fetcher,
    bron: Bron,
    icp: ICP,
    *,
    max_steden: int = 12,
    max_per_zoekopdracht: int = 60,
    verrijk_met_website: bool = True,
) -> list[Lead]:
    """Fan-out over NL-steden x ICP-branchetermen via de Places Text Search."""
    if not SETTINGS.places_key:
        return []

    termen = (icp.branches or icp.zoekwoorden or [icp.omschrijving])[:4]
    steden = steden_voor(icp.regios, limiet=max_steden)

    async def _zoek(term: str, stad: str) -> list[Lead]:
        leads: list[Lead] = []
        page_token = ""
        while len(leads) < max_per_zoekopdracht:
            body: dict = {
                "textQuery": f"{term} in {stad}",
                "languageCode": "nl",
                "regionCode": "NL",
                "maxResultCount": 20,
            }
            if page_token:
                body["pageToken"] = page_token
            data = await fetcher.post_json(
                "https://places.googleapis.com/v1/places:searchText",
                json_body=body,
                headers={
                    "X-Goog-Api-Key": SETTINGS.places_key,
                    "X-Goog-FieldMask": _PLACES_FIELDS,
                    "Content-Type": "application/json",
                },
            )
            if not data:
                break
            for plaats in data.get("places", []) or []:
                if plaats.get("businessStatus") == "CLOSED_PERMANENTLY":
                    continue
                adres = plaats.get("formattedAddress", "")
                postcode = ""
                if (m := extract.POSTCODE_RE.search(adres)):
                    postcode = f"{m.group(1)} {m.group(2).upper()}"
                telefoon, telefoon_type = extract.normaliseer_telefoon(
                    plaats.get("internationalPhoneNumber") or plaats.get("nationalPhoneNumber") or ""
                )
                site = plaats.get("websiteUri", "")
                leads.append(Lead(
                    bron_naam=bron.naam,
                    bron_type=bron.type,
                    segment=f"{term.title()} — {stad}",
                    bron_url="https://maps.google.nl",
                    bedrijfsnaam=(plaats.get("displayName") or {}).get("text", ""),
                    website=site,
                    domein=extract.registreerbaar_domein(site) if site else "",
                    telefoon=telefoon,
                    telefoon_type=telefoon_type,
                    adres=adres,
                    postcode=postcode,
                    plaats=stad,
                    provincie=bepaal_provincie(postcode, stad),
                    beoordeling=str(plaats.get("rating", "")),
                    aantal_reviews=str(plaats.get("userRatingCount", "")),
                    branche=(plaats.get("primaryTypeDisplayName") or {}).get("text", ""),
                    gevonden_op=f"Google Places — {term} in {stad}",
                ))
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
        return leads

    taken = [_zoek(t, s) for t in termen for s in steden]
    alles: list[Lead] = []
    for groep in await asyncio.gather(*taken, return_exceptions=True):
        if isinstance(groep, list):
            alles.extend(groep)

    if not verrijk_met_website:
        return alles

    # Places geeft telefoon maar zelden e-mail — die halen we van hun eigen site.
    per_domein: dict[str, Lead] = {}
    for lead in alles:
        if lead.domein and lead.domein not in per_domein:
            per_domein[lead.domein] = lead

    async def _site(lead: Lead) -> list[Lead]:
        try:
            gevonden = await oogst_domein(fetcher, lead.website, bron)
        except Exception:
            return []
        for g in gevonden:
            g.segment = lead.segment
            g.bedrijfsnaam = g.bedrijfsnaam or lead.bedrijfsnaam
            g.telefoon = g.telefoon or lead.telefoon
            g.telefoon_type = g.telefoon_type or lead.telefoon_type
            g.adres = g.adres or lead.adres
            g.postcode = g.postcode or lead.postcode
            g.plaats = g.plaats or lead.plaats
            g.provincie = g.provincie or lead.provincie
            g.beoordeling = lead.beoordeling
            g.aantal_reviews = lead.aantal_reviews
            g.branche = g.branche or lead.branche
        return gevonden

    verrijkt: list[Lead] = []
    for groep in await asyncio.gather(
        *(_site(l) for l in list(per_domein.values())[:400]), return_exceptions=True
    ):
        if isinstance(groep, list):
            verrijkt.extend(groep)

    return alles + verrijkt


# ── KvK Handelsregister ─────────────────────────────────────────────────────

async def oogst_kvk(fetcher: Fetcher, bron: Bron, icp: ICP, *, max_per_zoek: int = 100) -> list[Lead]:
    if not SETTINGS.kvk_key:
        return []

    termen = (icp.branches or icp.zoekwoorden)[:4]
    steden = steden_voor(icp.regios, limiet=8)

    async def _zoek(term: str, stad: str) -> list[Lead]:
        leads: list[Lead] = []
        for pagina in range(1, (max_per_zoek // 100) + 2):
            data = await fetcher.json(
                "https://api.kvk.nl/api/v2/zoeken",
                params={"naam": term, "plaats": stad, "pagina": pagina, "resultatenPerPagina": 100},
                headers={"apikey": SETTINGS.kvk_key},
            )
            if not data or not data.get("resultaten"):
                break
            for r in data["resultaten"]:
                adres = (r.get("adres") or {}).get("binnenlandsAdres") or {}
                postcode = adres.get("postcode", "")
                woonplaats = adres.get("plaats", stad)
                leads.append(Lead(
                    bron_naam=bron.naam,
                    bron_type=bron.type,
                    segment=f"KvK — {term.title()} {stad}",
                    bron_url="https://www.kvk.nl",
                    bedrijfsnaam=r.get("handelsnaam", ""),
                    kvk_nummer=str(r.get("kvkNummer", "")),
                    adres=" ".join(filter(None, [
                        adres.get("straatnaam", ""), str(adres.get("huisnummer", "") or "")
                    ])).strip(),
                    postcode=postcode,
                    plaats=woonplaats,
                    provincie=bepaal_provincie(postcode, woonplaats),
                    branche=r.get("type", ""),
                    gevonden_op=f"KvK Zoeken — {term} / {stad}",
                ))
            if len(leads) >= max_per_zoek:
                break
        return leads[:max_per_zoek]

    alles: list[Lead] = []
    for groep in await asyncio.gather(
        *(_zoek(t, s) for t in termen for s in steden), return_exceptions=True
    ):
        if isinstance(groep, list):
            alles.extend(groep)
    return alles


# ── YouTube: kanalen/podcasts waar de ICP te gast is ────────────────────────

async def oogst_youtube(
    fetcher: Fetcher,
    bron: Bron,
    icp: ICP,
    *,
    max_videos: int = 120,
) -> list[Lead]:
    """Videobeschrijvingen bevatten de sites van gasten — dat zijn je leads."""
    if not SETTINGS.youtube_key:
        return []

    termen = (icp.branches or icp.zoekwoorden)[:3]
    queries = [f"{t} ondernemer interview Nederland" for t in termen] + \
              [f"{t} podcast nederlands" for t in termen]

    video_ids: list[str] = []
    for query in queries:
        data = await fetcher.json(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": SETTINGS.youtube_key, "part": "snippet", "q": query,
                "type": "video", "maxResults": 50, "relevanceLanguage": "nl",
                "regionCode": "NL",
            },
        )
        for item in (data or {}).get("items", []):
            vid = (item.get("id") or {}).get("videoId")
            if vid:
                video_ids.append(vid)
        if len(video_ids) >= max_videos:
            break
    video_ids = list(dict.fromkeys(video_ids))[:max_videos]

    sites: dict[str, str] = {}   # domein -> (url, video-titel)
    context: dict[str, str] = {}
    for i in range(0, len(video_ids), 50):
        data = await fetcher.json(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"key": SETTINGS.youtube_key, "part": "snippet", "id": ",".join(video_ids[i:i + 50])},
        )
        for item in (data or {}).get("items", []):
            snippet = item.get("snippet", {})
            beschrijving = snippet.get("description", "")
            titel = snippet.get("title", "")
            for url in re.findall(r"https?://[^\s<>\"')]+", beschrijving):
                domein = extract.registreerbaar_domein(url)
                if not domein or domein in _YT_RUIS:
                    continue
                if domein not in sites:
                    sites[domein] = url.rstrip(".,);")
                    context[domein] = titel[:200]

    async def _site(domein: str) -> list[Lead]:
        try:
            gevonden = await oogst_domein(fetcher, sites[domein], bron)
        except Exception:
            return []
        for g in gevonden:
            g.segment = bron.segment or "YouTube-gasten"
            g.notitie = f"Genoemd in video: {context.get(domein, '')} | {g.notitie}"[:600]
        return gevonden

    alles: list[Lead] = []
    for groep in await asyncio.gather(
        *(_site(d) for d in list(sites)[:150]), return_exceptions=True
    ):
        if isinstance(groep, list):
            alles.extend(groep)
    return alles


_YT_RUIS = {
    "youtube.com", "youtu.be", "instagram.com", "facebook.com", "twitter.com",
    "x.com", "tiktok.com", "linkedin.com", "spotify.com", "apple.com",
    "patreon.com", "bit.ly", "linktr.ee", "amazon.nl", "amazon.com",
    "podcasts.apple.com", "open.spotify.com", "discord.gg", "paypal.com",
}


# ── Apollo (B2B-contacten) ──────────────────────────────────────────────────

async def oogst_apollo(
    fetcher: Fetcher,
    bron: Bron,
    icp: ICP,
    *,
    max_paginas: int = 5,
) -> list[Lead]:
    if not SETTINGS.apollo_key:
        return []

    titels = icp.functietitels[:8] or ["owner", "founder", "director", "manager"]
    branches = icp.branches[:5]

    leads: list[Lead] = []
    for pagina in range(1, max_paginas + 1):
        data = await fetcher.post_json(
            "https://api.apollo.io/api/v1/mixed_people/search",
            json_body={
                "person_titles": titels,
                "person_locations": ["Netherlands"],
                "q_organization_keyword_tags": branches,
                "page": pagina,
                "per_page": 100,
            },
            headers={
                "x-api-key": SETTINGS.apollo_key,
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
        )
        mensen = (data or {}).get("people") or []
        if not mensen:
            break
        for p in mensen:
            org = p.get("organization") or {}
            site = org.get("website_url", "") or ""
            email = (p.get("email") or "").lower()
            if email in {"email_not_unlocked@domain.com"}:
                email = ""
            telefoon, telefoon_type = extract.normaliseer_telefoon(
                org.get("phone") or p.get("sanitized_phone") or ""
            )
            plaats = p.get("city") or org.get("city") or ""
            leads.append(Lead(
                bron_naam=bron.naam,
                bron_type=bron.type,
                segment=bron.segment or "Apollo B2B",
                bron_url="https://www.apollo.io",
                bedrijfsnaam=org.get("name", ""),
                website=site,
                domein=extract.registreerbaar_domein(site) if site else "",
                voornaam=p.get("first_name", ""),
                achternaam=p.get("last_name", ""),
                volledige_naam=p.get("name", ""),
                functie=p.get("title", ""),
                email=email if email and extract.is_bruikbaar_email(email) else "",
                email_type=extract.email_type(email) if email else "",
                telefoon=telefoon,
                telefoon_type=telefoon_type,
                plaats=plaats,
                provincie=bepaal_provincie("", plaats),
                linkedin_url=p.get("linkedin_url", "") or "",
                branche=org.get("industry", ""),
                gevonden_op="Apollo people search",
            ))
    return leads


# ── Hunter: domein -> e-mailadressen ────────────────────────────────────────

async def hunter_domein(fetcher: Fetcher, domein: str) -> list[dict]:
    if not SETTINGS.hunter_key or not domein:
        return []
    data = await fetcher.json(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domein, "api_key": SETTINGS.hunter_key, "limit": 10},
    )
    return ((data or {}).get("data") or {}).get("emails") or []


async def vul_aan_met_hunter(fetcher: Fetcher, leads: list[Lead], *, max_domeinen: int = 100) -> int:
    """Vul leads zonder e-mail aan via Hunter. Geeft het aantal aanvullingen terug."""
    if not SETTINGS.hunter_key:
        return 0

    zonder_mail = [l for l in leads if not l.email and l.domein]
    domeinen = list(dict.fromkeys(l.domein for l in zonder_mail))[:max_domeinen]
    resultaten = await asyncio.gather(
        *(hunter_domein(fetcher, d) for d in domeinen), return_exceptions=True
    )
    per_domein = {
        d: (r if isinstance(r, list) else [])
        for d, r in zip(domeinen, resultaten)
    }

    aangevuld = 0
    for lead in zonder_mail:
        treffers = per_domein.get(lead.domein) or []
        if not treffers:
            continue
        beste = max(treffers, key=lambda e: (e.get("confidence") or 0))
        adres = (beste.get("value") or "").lower()
        if not extract.is_bruikbaar_email(adres):
            continue
        lead.email = adres
        lead.email_type = extract.email_type(adres)
        lead.email_status = "geldig" if (beste.get("confidence") or 0) >= 80 else "risico"
        lead.voornaam = lead.voornaam or (beste.get("first_name") or "")
        lead.achternaam = lead.achternaam or (beste.get("last_name") or "")
        lead.volledige_naam = lead.volledige_naam or f"{lead.voornaam} {lead.achternaam}".strip()
        lead.functie = lead.functie or (beste.get("position") or "")
        aangevuld += 1
    return aangevuld


# ── Podcasts: RSS-feeds bevatten vaak het eigenaars-e-mailadres ─────────────

async def oogst_podcasts(fetcher: Fetcher, bron: Bron, icp: ICP, *, max_feeds: int = 25) -> list[Lead]:
    termen = (icp.branches or icp.zoekwoorden)[:3]
    feeds: dict[str, dict] = {}

    for term in termen:
        data = await fetcher.json(
            "https://itunes.apple.com/search",
            params={"term": term, "country": "NL", "media": "podcast", "limit": 50},
        )
        for item in (data or {}).get("results", []):
            feed = item.get("feedUrl")
            if feed and feed not in feeds:
                feeds[feed] = item

    async def _feed(url: str) -> list[Lead]:
        opgehaald = await fetcher.html(url)
        if not opgehaald:
            return []
        soup = BeautifulSoup(opgehaald[1], "xml")
        mails = [
            e for e in extract.EMAIL_RE.findall(opgehaald[1])
            if extract.is_bruikbaar_email(e)
        ]
        link_tag = soup.find("link")
        site = (link_tag.get_text(strip=True) if link_tag else "") or ""
        titel_tag = soup.find("title")
        titel = titel_tag.get_text(strip=True) if titel_tag else feeds[url].get("collectionName", "")
        if not mails and not site:
            return []
        email = mails[0] if mails else ""
        return [Lead(
            bron_naam=bron.naam,
            bron_type=bron.type,
            segment=bron.segment or "NL-podcasts",
            bron_url=url,
            bedrijfsnaam=titel[:120],
            website=site,
            domein=extract.registreerbaar_domein(site) if site else "",
            email=email,
            email_type=extract.email_type(email) if email else "",
            volledige_naam=feeds[url].get("artistName", "")[:80],
            notitie=f"Podcast: {titel} | {feeds[url].get('primaryGenreName', '')}"[:300],
            gevonden_op=url,
        )]

    alles: list[Lead] = []
    for groep in await asyncio.gather(
        *(_feed(u) for u in list(feeds)[:max_feeds]), return_exceptions=True
    ):
        if isinstance(groep, list):
            alles.extend(groep)
    return alles
