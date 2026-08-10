"""Website-connector: het werkpaard.

Van één bedrijfsdomein naar leads. Haalt de homepage op, kiest daaruit de
contact-/team-/over-ons-pagina's en oogst e-mail, telefoon, personen, KvK,
adres en socials. Werkt zonder enige API-key.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

from .. import extract
from ..http import Fetcher
from ..models import Bron, Lead
from ..namen import is_voornaam
from ..regions import bepaal_provincie

# Paden die we blind proberen als de homepage niet naar contact linkt
_GOK_PADEN = ("/contact", "/contact/", "/over-ons", "/team", "/colofon", "/contactgegevens")


async def oogst_domein(
    fetcher: Fetcher,
    url: str,
    bron: Bron,
    *,
    max_subpaginas: int = 4,
) -> list[Lead]:
    """Crawl één bedrijfssite en geef 0..n leads terug."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")

    start = await fetcher.html(url)
    if not start:
        return []
    eind_url, html = start

    hoofd = extract.extraheer(html, eind_url)
    domein = extract.registreerbaar_domein(eind_url)

    subpaginas = extract.interne_links(html, eind_url)[:max_subpaginas]
    if not subpaginas:
        basis = f"{urlparse(eind_url).scheme}://{urlparse(eind_url).netloc}"
        subpaginas = [urljoin(basis, p) for p in _GOK_PADEN[:3]]

    async def _sub(u: str):
        r = await fetcher.html(u)
        return extract.extraheer(r[1], r[0]) if r else None

    for gegevens in await asyncio.gather(*(_sub(u) for u in subpaginas), return_exceptions=True):
        if not isinstance(gegevens, extract.Contactgegevens):
            continue
        hoofd.emails.extend(e for e in gegevens.emails if e not in hoofd.emails)
        hoofd.telefoons.extend(t for t in gegevens.telefoons if t not in hoofd.telefoons)
        hoofd.personen.extend(gegevens.personen)
        hoofd.kvk_nummer = hoofd.kvk_nummer or gegevens.kvk_nummer
        hoofd.btw_nummer = hoofd.btw_nummer or gegevens.btw_nummer
        hoofd.adres = hoofd.adres or gegevens.adres
        hoofd.postcode = hoofd.postcode or gegevens.postcode
        hoofd.plaats = hoofd.plaats or gegevens.plaats
        hoofd.linkedin = hoofd.linkedin or gegevens.linkedin
        hoofd.facebook = hoofd.facebook or gegevens.facebook
        hoofd.instagram = hoofd.instagram or gegevens.instagram
        if not hoofd.tekstfragment:
            hoofd.tekstfragment = gegevens.tekstfragment

    return _naar_leads(hoofd, bron, eind_url, domein)


def _naar_leads(
    cg: extract.Contactgegevens,
    bron: Bron,
    website: str,
    domein: str,
) -> list[Lead]:
    """Splits de ruwe extractie in bruikbare leadrijen.

    Regel: e-mails op het eigen domein winnen. Persoonlijke adressen worden
    eigen rijen (die presteren het best), rol-adressen worden één bedrijfsrij.
    """
    eigen_mails = [e for e in cg.emails if extract.registreerbaar_domein(e) == domein]
    mails = eigen_mails or cg.emails[:2]

    telefoon, telefoon_type = ("", "")
    if cg.telefoons:
        telefoon, telefoon_type = extract.normaliseer_telefoon(cg.telefoons[0])

    basis = dict(
        bron_naam=bron.naam,
        bron_type=bron.type,
        segment=bron.segment or bron.naam,
        bron_url=bron.url,
        bedrijfsnaam=cg.bedrijfsnaam,
        website=website,
        domein=domein,
        telefoon=telefoon,
        telefoon_type=telefoon_type,
        adres=cg.adres,
        postcode=cg.postcode,
        plaats=cg.plaats,
        provincie=bepaal_provincie(cg.postcode, cg.plaats),
        kvk_nummer=cg.kvk_nummer,
        btw_nummer=cg.btw_nummer,
        linkedin_url=cg.linkedin,
        facebook_url=cg.facebook,
        instagram_url=cg.instagram,
        notitie=cg.tekstfragment[:600],
        gevonden_op=website,
    )

    leads: list[Lead] = []
    gebruikte_mails: set[str] = set()

    # 1. Personen met een eigen e-mailadres of duidelijke functie
    for persoon in cg.personen[:12]:
        naam = persoon.get("naam", "")
        if not naam:
            continue
        voornaam, achternaam = extract.splits_naam(naam)
        mail = persoon.get("email", "").lower()
        if mail and not extract.is_bruikbaar_email(mail):
            mail = ""
        if not mail:
            mail = _match_mail_op_naam(voornaam, achternaam, mails, gebruikte_mails)
        if mail:
            gebruikte_mails.add(mail)
        leads.append(Lead(
            **basis,
            voornaam=voornaam,
            achternaam=achternaam,
            volledige_naam=naam,
            functie=persoon.get("functie", ""),
            email=mail,
            email_type=extract.email_type(mail) if mail else "",
        ))

    # 2. Overgebleven persoonlijke adressen zonder gekoppelde naam
    for mail in mails:
        if mail in gebruikte_mails:
            continue
        soort = extract.email_type(mail)
        if soort != "persoonlijk":
            continue
        gebruikte_mails.add(mail)
        voornaam, achternaam = _naam_uit_lokaaldeel(mail.split("@")[0])
        leads.append(Lead(
            **basis,
            voornaam=voornaam,
            achternaam=achternaam,
            volledige_naam=f"{voornaam} {achternaam}".strip(),
            email=mail,
            email_type=soort,
        ))

    # 3. Eén bedrijfsrij voor het algemene adres (info@, contact@)
    algemeen = next((m for m in mails if m not in gebruikte_mails), "")
    if algemeen or (not leads and telefoon):
        leads.append(Lead(
            **basis,
            email=algemeen,
            email_type=extract.email_type(algemeen) if algemeen else "",
        ))

    return [l for l in leads if l.email or l.telefoon]


def _naam_uit_lokaaldeel(lokaal: str) -> tuple[str, str]:
    """'jan.devries' -> ('Jan', 'Devries'). Geeft ('','') bij twijfel.

    Een initiaal is géén voornaam: "Hoi J," is erger dan geen aanhef, dus
    dan laten we het veld leeg en valt je sequencer terug op de fallback.
    """
    tokens = [t for t in re.split(r"[._\-+0-9]+", lokaal.lower()) if t.isalpha()]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return (tokens[0].title(), "") if is_voornaam(tokens[0]) else ("", "")
    if len(tokens[0]) == 1:                       # initiaal -> onbruikbaar als aanhef
        return "", " ".join(t.title() for t in tokens[1:])
    return tokens[0].title(), " ".join(t.title() for t in tokens[1:])


def _match_mail_op_naam(
    voornaam: str,
    achternaam: str,
    mails: list[str],
    gebruikt: set[str],
) -> str:
    """Koppel 'Jan de Vries' aan jan@, j.devries@, jandevries@ ..."""
    if not voornaam:
        return ""
    vn = voornaam.lower()
    an = achternaam.lower().replace(" ", "")
    kandidaten = {vn, f"{vn}.{an}", f"{vn[0]}.{an}", f"{vn}{an}", f"{vn[0]}{an}", an}
    kandidaten.discard("")
    for mail in mails:
        if mail in gebruikt:
            continue
        if mail.split("@")[0].lower() in kandidaten:
            return mail
    return ""
