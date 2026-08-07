"""Listing-connector: ledenlijst/bedrijvengids -> bedrijfssites -> leads.

Werkt op elke lijstpagina zonder site-specifieke regels:
  1. haal de lijstpagina op (+ paginering)
  2. verzamel uitgaande links naar bedrijfsdomeinen (ruis eruit)
  3. pak meteen contactgegevens die al ín de lijst staan
  4. crawl elk bedrijfsdomein met de website-connector
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .. import extract
from ..http import Fetcher
from ..models import Bron, Lead
from ..regions import bepaal_provincie
from .website import oogst_domein

# Domeinen die nooit een lead zijn
_NIET_BEDRIJF = {
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "tiktok.com", "pinterest.com", "whatsapp.com",
    "google.com", "google.nl", "maps.google.com", "goo.gl", "apple.com",
    "microsoft.com", "adobe.com", "wordpress.org", "wordpress.com", "wix.com",
    "squarespace.com", "shopify.com", "cloudflare.com", "jimdo.com",
    "rijksoverheid.nl", "belastingdienst.nl", "kvk.nl", "europa.eu",
    "cookiebot.com", "cookieyes.com", "trustpilot.com", "spotify.com",
    "gravatar.com", "w3.org", "schema.org", "mailchimp.com", "hubspot.com",
    "addthis.com", "sharethis.com", "bing.com", "yahoo.com", "vimeo.com",
}

_PAGINERING_PATRONEN = (
    re.compile(r"[?&](?:page|pagina|p|start|offset)=(\d+)", re.I),
)


def _is_bedrijfsdomein(url: str, bron_domein: str) -> bool:
    domein = extract.registreerbaar_domein(url)
    if not domein or domein == bron_domein:
        return False
    if domein in _NIET_BEDRIJF or any(domein.endswith("." + n) for n in _NIET_BEDRIJF):
        return False
    if url.lower().endswith(extract.TROEP_EXTENSIES):
        return False
    return True


async def _vind_paginering(fetcher: Fetcher, url: str, html: str, max_paginas: int) -> list[str]:
    """Pak vervolgpagina's op basis van pagineringlinks."""
    if max_paginas <= 1:
        return []
    soup = BeautifulSoup(html, "lxml")
    kandidaten: list[str] = []
    for a in soup.find_all("a", href=True):
        tekst = a.get_text(" ", strip=True).lower()
        absoluut = urljoin(url, a["href"]).split("#")[0]
        if absoluut == url or extract.registreerbaar_domein(absoluut) != extract.registreerbaar_domein(url):
            continue
        is_paginering = (
            tekst.isdigit()
            or tekst in {"volgende", "verder", "next", "meer", "»", "›"}
            or any(p.search(absoluut) for p in _PAGINERING_PATRONEN)
            or re.search(r"/(?:page|pagina)/\d+", absoluut, re.I)
        )
        if is_paginering:
            kandidaten.append(absoluut)
    return list(dict.fromkeys(kandidaten))[: max_paginas - 1]


def _leads_uit_lijstpagina(html: str, url: str, bron: Bron) -> list[Lead]:
    """Sommige gidsen tonen e-mail/telefoon direct in de lijst — gratis leads."""
    soup = BeautifulSoup(html, "lxml")
    leads: list[Lead] = []

    blokken = soup.select(
        "[class*=result], [class*=listing], [class*=item], [class*=card], "
        "[class*=lid], [class*=member], [class*=bedrijf], [class*=company], "
        "[class*=vestiging], article, tr, li"
    )
    for blok in blokken[:600]:
        html_blok = str(blok)
        if "@" not in html_blok and "tel:" not in html_blok.lower():
            continue
        cg = extract.extraheer(html_blok, url)
        if not cg.emails and not cg.telefoons:
            continue

        naam = ""
        for kop in blok.select("h1,h2,h3,h4,h5,strong,b,a"):
            kandidaat = re.sub(r"\s+", " ", kop.get_text(" ", strip=True))
            if 3 <= len(kandidaat) <= 90 and "@" not in kandidaat:
                naam = kandidaat
                break

        site = next(
            (l for l in cg.externe_links if _is_bedrijfsdomein(l, extract.registreerbaar_domein(url))),
            "",
        )
        telefoon, telefoon_type = extract.normaliseer_telefoon(cg.telefoons[0]) if cg.telefoons else ("", "")
        email = cg.emails[0] if cg.emails else ""

        leads.append(Lead(
            bron_naam=bron.naam,
            bron_type=bron.type,
            segment=bron.segment or bron.naam,
            bron_url=url,
            bedrijfsnaam=naam,
            website=site,
            domein=extract.registreerbaar_domein(site) if site else "",
            email=email,
            email_type=extract.email_type(email) if email else "",
            telefoon=telefoon,
            telefoon_type=telefoon_type,
            postcode=cg.postcode,
            plaats=cg.plaats,
            provincie=bepaal_provincie(cg.postcode, cg.plaats),
            notitie=re.sub(r"\s+", " ", blok.get_text(" ", strip=True))[:300],
            gevonden_op=url,
        ))
    return leads


def _padpatroon(url: str) -> str:
    """/tandarts/praktijk-de-molen -> '/tandarts/*' — om zusterpagina's te tellen."""
    delen = [d for d in urlparse(url).path.strip("/").split("/") if d]
    if not delen:
        return "/"
    return "/" + "/".join(delen[:-1] + ["*"])


def _detailpaginas(html: str, basis_url: str, *, min_zusters: int = 5) -> list[str]:
    """Vind interne profielpagina's.

    Nederlandse gidsen (Zorgkaart, Funda-makelaars, Bovag) linken niet naar de
    website van het bedrijf maar naar hun eigen profielpagina. Die pagina's
    delen één padpatroon en komen in bulk voor — daar herkennen we ze aan.
    """
    soup = BeautifulSoup(html, "lxml")
    basis_domein = extract.registreerbaar_domein(basis_url)
    per_patroon: dict[str, list[str]] = defaultdict(list)

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absoluut = urljoin(basis_url, href).split("#")[0].split("?")[0]
        if extract.registreerbaar_domein(absoluut) != basis_domein:
            continue
        if absoluut.lower().endswith(extract.TROEP_EXTENSIES):
            continue
        pad = urlparse(absoluut).path.strip("/")
        if not pad or pad.count("/") > 3:
            continue
        laatste = pad.rsplit("/", 1)[-1]
        if len(laatste) < 4 or laatste.isdigit():
            continue
        per_patroon[_padpatroon(absoluut)].append(absoluut)

    beste: list[str] = []
    for patroon, urls in sorted(per_patroon.items(), key=lambda kv: -len(kv[1])):
        uniek = list(dict.fromkeys(urls))
        if len(uniek) < min_zusters:
            continue
        # sla generieke secties over die toevallig veel kinderen hebben
        if any(w in patroon for w in ("/nieuws", "/blog", "/artikel", "/tag", "/categorie")):
            continue
        beste.extend(uniek)
        if len(beste) >= 200:
            break
    return beste


async def oogst_lijst(
    fetcher: Fetcher,
    bron: Bron,
    *,
    max_bedrijven: int = 60,
    max_paginas: int = 3,
) -> list[Lead]:
    if not bron.url:
        return []

    eerste = await fetcher.html(bron.url)
    if not eerste:
        return []
    eind_url, html = eerste
    bron_domein = extract.registreerbaar_domein(eind_url)

    paginas: list[tuple[str, str]] = [(eind_url, html)]
    for vervolg in await _vind_paginering(fetcher, eind_url, html, max_paginas):
        r = await fetcher.html(vervolg)
        if r:
            paginas.append(r)

    directe_leads: list[Lead] = []
    bedrijfssites: list[str] = []
    detailkandidaten: list[str] = []
    for pagina_url, pagina_html in paginas:
        directe_leads.extend(_leads_uit_lijstpagina(pagina_html, pagina_url, bron))
        cg = extract.extraheer(pagina_html, pagina_url)
        bedrijfssites.extend(l for l in cg.externe_links if _is_bedrijfsdomein(l, bron_domein))
        detailkandidaten.extend(_detailpaginas(pagina_html, pagina_url))

    # Weinig uitgaande bedrijfslinks? Dan hosten ze de profielen intern —
    # open die profielpagina's en haal daar de bedrijfswebsite vandaan.
    if len(set(map(extract.registreerbaar_domein, bedrijfssites))) < 8 and detailkandidaten:
        doelen_detail = list(dict.fromkeys(detailkandidaten))[:max_bedrijven]

        async def _detail(u: str) -> tuple[list[Lead], list[str]]:
            r = await fetcher.html(u)
            if not r:
                return [], []
            leads = _leads_uit_lijstpagina(r[1], r[0], bron)
            cg = extract.extraheer(r[1], r[0])
            sites = [l for l in cg.externe_links if _is_bedrijfsdomein(l, bron_domein)]
            if not leads and (cg.emails or cg.telefoons):
                leads = [_lead_uit_detail(cg, bron, r[0], sites)]
            return leads, sites

        for uitkomst in await asyncio.gather(
            *(_detail(u) for u in doelen_detail), return_exceptions=True
        ):
            if isinstance(uitkomst, tuple):
                directe_leads.extend(uitkomst[0])
                bedrijfssites.extend(uitkomst[1])

    # één URL per domein — anders crawlen we dezelfde site tien keer
    per_domein: dict[str, str] = {}
    for site in bedrijfssites:
        d = extract.registreerbaar_domein(site)
        per_domein.setdefault(d, site)
    doelen = list(per_domein.values())[:max_bedrijven]

    async def _site(u: str) -> list[Lead]:
        try:
            return await oogst_domein(fetcher, u, bron)
        except Exception:
            return []

    gecrawld: list[Lead] = []
    for groep in await asyncio.gather(*(_site(u) for u in doelen), return_exceptions=True):
        if isinstance(groep, list):
            gecrawld.extend(groep)

    return directe_leads + gecrawld


def _lead_uit_detail(
    cg: extract.Contactgegevens,
    bron: Bron,
    url: str,
    sites: list[str],
) -> Lead:
    site = sites[0] if sites else ""
    telefoon, telefoon_type = extract.normaliseer_telefoon(cg.telefoons[0]) if cg.telefoons else ("", "")
    email = cg.emails[0] if cg.emails else ""
    return Lead(
        bron_naam=bron.naam,
        bron_type=bron.type,
        segment=bron.segment or bron.naam,
        bron_url=bron.url,
        bedrijfsnaam=cg.bedrijfsnaam,
        website=site,
        domein=extract.registreerbaar_domein(site) if site else "",
        email=email,
        email_type=extract.email_type(email) if email else "",
        telefoon=telefoon,
        telefoon_type=telefoon_type,
        adres=cg.adres,
        postcode=cg.postcode,
        plaats=cg.plaats,
        provincie=bepaal_provincie(cg.postcode, cg.plaats),
        kvk_nummer=cg.kvk_nummer,
        linkedin_url=cg.linkedin,
        facebook_url=cg.facebook,
        notitie=cg.tekstfragment[:600],
        gevonden_op=url,
    )
