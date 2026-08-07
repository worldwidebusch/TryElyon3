"""Contactextractie uit HTML — Nederlands geoptimaliseerd.

Haalt e-mail, telefoon, naam, functie, KvK, BTW, adres en socials uit een pagina.
Kan ook door obfuscatie heen kijken ("info [at] domein punt nl", "apenstaartje").
"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import phonenumbers
import tldextract
from bs4 import BeautifulSoup

from .namen import is_voornaam

# ── Regexes ─────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"([A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,255}\.[A-Za-z]{2,24})"
    r"(?![A-Za-z0-9\-])"
)

# NL-telefoon: 06-12345678, 0031 6 1234 5678, +31 (0)20 123 45 67, 020-1234567
PHONE_RE = re.compile(
    r"(?:(?:\+|00)\s?31|\b0)\s?(?:\(0\)\s?)?"
    r"(?:\d[\s\-\.–]?){8,10}\d"
)

KVK_RE = re.compile(r"\b(?:kvk|k\.v\.k\.?|handelsregister)[^0-9]{0,25}(\d{8})\b", re.I)
BTW_RE = re.compile(r"\bNL\s?\d{9}\s?B\s?\d{2}\b", re.I)
POSTCODE_RE = re.compile(r"\b(\d{4})\s?([A-Za-z]{2})\b")

_OBF_PATRONEN = [
    (re.compile(r"\s*\(\s*(?:at|apenstaartje|apestaartje)\s*\)\s*", re.I), "@"),
    (re.compile(r"\s*\[\s*(?:at|apenstaartje|apestaartje)\s*\]\s*", re.I), "@"),
    (re.compile(r"\s+(?:at|apenstaartje|apestaartje)\s+", re.I), "@"),
    (re.compile(r"\s*\(\s*(?:dot|punt)\s*\)\s*", re.I), "."),
    (re.compile(r"\s*\[\s*(?:dot|punt)\s*\]\s*", re.I), "."),
    (re.compile(r"\s+(?:dot|punt)\s+", re.I), "."),
]

ALGEMENE_PREFIXEN = {
    "info", "contact", "hallo", "hello", "welkom", "mail", "email", "post",
    "algemeen", "general", "office", "kantoor", "team", "praktijk", "bedrijf",
}

ROL_PREFIXEN = ALGEMENE_PREFIXEN | {
    "sales", "verkoop", "support", "helpdesk", "service", "klantenservice",
    "administratie", "admin", "boekhouding", "facturen", "factuur", "finance",
    "financien", "debiteuren", "crediteuren", "betalingen", "betaling",
    "receptie", "balie", "afspraak", "afspraken", "assistente", "secretariaat",
    "planning", "planner", "webmaster", "webredactie", "redactie", "marketing",
    "communicatie", "pers", "media", "pr", "hr", "personeelszaken", "vacature",
    "vacatures", "sollicitatie", "sollicitaties", "recruitment", "werkenbij",
    "privacy", "avg", "noreply", "no-reply", "donotreply", "nieuwsbrief",
    "newsletter", "ledenadministratie", "leden", "lidmaatschap", "donateurs",
    "inschrijving", "inschrijvingen", "aanmelding", "aanmeldingen", "meldpunt",
    "klachten", "klacht", "bestuur", "directie", "secretaris", "penningmeester",
    "voorzitter", "vrijwilligers", "lotgenoten", "ervaringsdeskundigen",
    "opleidingen", "cursus", "cursussen", "training", "events", "evenementen",
    "reserveren", "reservering", "reserveringen", "boekingen", "bestellingen",
    "orders", "inkoop", "logistiek", "transport", "magazijn", "techniek",
    "ict", "it", "beheer", "systeembeheer", "facilitair", "receptionist",
    "onderhoud", "storing", "storingen", "spoed", "noodgeval", "verhuur",
    "offerte", "offertes", "aanvraag", "aanvragen", "advies", "vragen",
    "abonnementen", "abonnement", "webshop", "shop", "winkel", "retour",
    "retouren", "garantie", "kwaliteit", "veiligheid", "arbo", "opzeggen",
    "wijzigingen", "administratie1", "backoffice", "frontoffice", "helpdesk1",
}

# Woorddelen die een lokaal deel hoe dan ook tot een rol maken
_ROL_FRAGMENTEN = (
    "admin", "factu", "betaal", "betaling", "boekhoud", "receptie", "balie",
    "redactie", "secretar", "bestuur", "leden", "klacht", "meldpunt", "vacature",
    "sollicit", "recruit", "webmaster", "noreply", "no-reply", "donotreply",
    "nieuwsbrief", "newsletter", "helpdesk", "support", "service", "verkoop",
    "sales", "marketing", "communicat", "reserver", "boeking", "bestelling",
    "offerte", "aanvraag", "abonnement", "vrijwillig", "donateur", "opleiding",
    "planning", "inschrijv", "aanmeld", "afspraak", "afspraken", "storing",
)

TROEP_DOMEINEN = {
    "example.com", "example.org", "sentry.io", "wixpress.com", "godaddy.com",
    "domain.com", "yourdomain.com", "jouwdomein.nl", "email.com", "test.com",
    "schema.org", "w3.org", "wordpress.com", "wordpress.org", "squarespace.com",
    "jimdo.com", "shopify.com", "cloudflare.com", "google.com", "gstatic.com",
    "googleapis.com", "facebook.com", "sentry.wixpress.com", "mysite.com",
}

TROEP_EXTENSIES = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".ico",
    ".woff", ".woff2", ".ttf", ".pdf", ".mp4", ".webmanifest",
)

# Pagina's die het vaakst contactdata bevatten (NL + EN)
CONTACT_HINTS = (
    "contact", "over-ons", "overons", "over_ons", "about", "team", "ons-team",
    "onsteam", "medewerkers", "mensen", "wie-zijn-wij", "wiezijnwij",
    "vestigingen", "locaties", "filialen", "adres", "bereikbaarheid",
    "afspraak", "impressum", "colofon", "disclaimer", "algemene-voorwaarden",
    "privacy", "praktijk", "onze-praktijk", "management", "directie",
)

FUNCTIE_TREFWOORDEN = (
    "eigenaar", "oprichter", "founder", "directeur", "director", "manager",
    "bestuurder", "praktijkhouder", "praktijkmanager", "vestigingsmanager",
    "hoofd", "teamleider", "coördinator", "coordinator", "ceo", "cto", "coo",
    "cfo", "cmo", "partner", "vennoot", "makelaar", "adviseur", "consultant",
    "specialist", "tandarts", "huisarts", "fysiotherapeut", "advocaat",
    "notaris", "accountant", "hovenier", "installateur", "aannemer",
    "office manager", "marketing manager", "sales manager", "commercieel",
)

_TUSSENVOEGSELS = {
    "van", "de", "der", "den", "het", "ten", "ter", "te", "op", "aan", "in",
    "'t", "'s", "du", "la", "le", "von", "di", "da",
}

PROVINCIE_PER_PLAATS: dict[str, str] = {}  # gevuld door regions.py bij import


@dataclass
class Contactgegevens:
    """Ruwe extractieopbrengst van één pagina."""

    emails: list[str] = field(default_factory=list)
    telefoons: list[str] = field(default_factory=list)
    personen: list[dict[str, str]] = field(default_factory=list)
    bedrijfsnaam: str = ""
    kvk_nummer: str = ""
    btw_nummer: str = ""
    adres: str = ""
    postcode: str = ""
    plaats: str = ""
    linkedin: str = ""
    facebook: str = ""
    instagram: str = ""
    externe_links: list[str] = field(default_factory=list)
    titel: str = ""
    tekstfragment: str = ""


# ── Helpers ─────────────────────────────────────────────────────────────────

def registreerbaar_domein(url_of_email: str) -> str:
    """example.co.uk uit https://www.example.co.uk/pad -> example.co.uk"""
    waarde = url_of_email.strip()
    if "@" in waarde and "://" not in waarde:
        waarde = waarde.rsplit("@", 1)[1]
    ext = tldextract.extract(waarde)
    if not ext.domain or not ext.suffix:
        return ""
    return f"{ext.domain}.{ext.suffix}".lower()


def is_bruikbaar_email(email: str) -> bool:
    email = email.lower().strip(" .,;:<>()[]\"'")
    if email.count("@") != 1 or len(email) > 254:
        return False
    lokaal, domein = email.split("@")
    if not lokaal or not domein or ".." in email:
        return False
    if email.endswith(TROEP_EXTENSIES):
        return False
    if registreerbaar_domein(domein) in TROEP_DOMEINEN:
        return False
    if re.fullmatch(r"[0-9a-f]{16,}", lokaal):     # hashes uit tracking-pixels
        return False
    if any(t in lokaal for t in ("example", "yourname", "jouwnaam", "naam@")):
        return False
    if domein.endswith((".png", ".jpg", ".webp", ".gif")):
        return False
    return True


def email_type(email: str) -> str:
    """'algemeen' (info@), 'rol' (facturen@), 'persoonlijk' (j.devries@) of 'onbekend'.

    Streng aan de persoonlijke kant: liever een echte persoon als 'onbekend'
    bestempelen dan `betalingen@` als voornaam "Betalingen" de deur uit sturen.
    """
    lokaal = email.split("@", 1)[0].lower()
    tokens = [t for t in re.split(r"[._\-+0-9]+", lokaal) if t]
    kern = tokens[0] if tokens else lokaal

    if lokaal in ALGEMENE_PREFIXEN or kern in ALGEMENE_PREFIXEN:
        return "algemeen"
    if lokaal in ROL_PREFIXEN or kern in ROL_PREFIXEN:
        return "rol"
    if any(fragment in lokaal for fragment in _ROL_FRAGMENTEN):
        return "rol"

    # voornaam.achternaam / v.achternaam — het klassieke persoonlijke patroon
    if len(tokens) >= 2 and all(t.isalpha() for t in tokens[:2]):
        if is_voornaam(tokens[0]) or len(tokens[0]) == 1 or is_voornaam(tokens[-1]):
            return "persoonlijk"
        # twee onbekende woorden: waarschijnlijk toch een naam, maar niet zeker
        return "persoonlijk" if len(tokens[0]) >= 3 and len(tokens[1]) >= 3 else "onbekend"

    # één woord: alleen persoonlijk als het écht een voornaam is
    if is_voornaam(kern):
        return "persoonlijk"
    return "onbekend"


def normaliseer_telefoon(ruw: str) -> tuple[str, str]:
    """(E.164-nummer, 'mobiel'|'vast'|'onbekend') of ('', '')."""
    kandidaat = re.sub(r"\(0\)", "", ruw)
    kandidaat = re.sub(r"[^\d+]", "", kandidaat)
    if kandidaat.startswith("0031"):
        kandidaat = "+31" + kandidaat[4:]
    elif kandidaat.startswith("00"):
        kandidaat = "+" + kandidaat[2:]
    try:
        nummer = phonenumbers.parse(kandidaat, "NL")
    except phonenumbers.NumberParseException:
        return "", ""
    if not phonenumbers.is_valid_number(nummer):
        return "", ""
    if phonenumbers.region_code_for_number(nummer) != "NL":
        return "", ""
    soort = phonenumbers.number_type(nummer)
    if soort == phonenumbers.PhoneNumberType.MOBILE:
        label = "mobiel"
    elif soort in (
        phonenumbers.PhoneNumberType.FIXED_LINE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    ):
        label = "vast"
    else:
        label = "onbekend"
    return phonenumbers.format_number(nummer, phonenumbers.PhoneNumberFormat.E164), label


def splits_naam(volledig: str) -> tuple[str, str]:
    """'Jan van der Berg' -> ('Jan', 'van der Berg')."""
    delen = [d for d in re.split(r"\s+", volledig.strip()) if d]
    if not delen:
        return "", ""
    if len(delen) == 1:
        return delen[0], ""
    voornaam = delen[0]
    rest = delen[1:]
    while rest and rest[0].lower().rstrip(".") in {"j", "a", "m", "p", "b"} and len(rest) > 1:
        rest = rest[1:]
    return voornaam, " ".join(rest)


def lijkt_op_naam(tekst: str) -> bool:
    tekst = tekst.strip()
    if not (4 <= len(tekst) <= 60):
        return False
    woorden = tekst.split()
    if not (2 <= len(woorden) <= 5):
        return False
    if any(c.isdigit() for c in tekst) or "@" in tekst:
        return False
    hoofdletterwoorden = sum(
        1 for w in woorden if w[:1].isupper() or w.lower() in _TUSSENVOEGSELS
    )
    return hoofdletterwoorden == len(woorden)


# ── Kernextractie ───────────────────────────────────────────────────────────

def _deobfusceer(tekst: str) -> str:
    for patroon, vervanging in _OBF_PATRONEN:
        tekst = patroon.sub(vervanging, tekst)
    return tekst


def _zichtbare_tekst(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    return re.sub(r"[ \t ]+", " ", soup.get_text("\n"))


def _kerntekst(html: str) -> str:
    """Inhoudelijke tekst zonder navigatie — dít voedt je AI-personalisatie.

    Een menu-dump ("Home Over ons Contact Zoeken…") is waardeloos als context;
    de meta-description plus de eerste echte alinea's zijn dat wél.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header",
                     "footer", "aside", "form", "template", "iframe"]):
        tag.decompose()
    for tag in soup.select("[class*=menu], [class*=nav], [id*=menu], [id*=nav], "
                           "[class*=cookie], [class*=breadcrumb], [role=navigation]"):
        tag.decompose()

    stukken: list[str] = []
    beschrijving = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if beschrijving and beschrijving.get("content"):
        stukken.append(beschrijving["content"].strip())

    hoofd = soup.find("main") or soup.find("article") or soup
    for element in hoofd.find_all(["h1", "h2", "p", "li"], limit=150):
        tekst = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if len(tekst) < 45 or tekst in stukken:
            continue
        if tekst.count(" ") < 6:                 # losse labels en knoppen
            continue
        stukken.append(tekst)
        if sum(len(s) for s in stukken) > 1400:
            break

    return " ".join(stukken)[:1200]


def _uit_jsonld(soup: BeautifulSoup, cg: Contactgegevens) -> None:
    """Schema.org LocalBusiness/Organization/Person is goud: gestructureerd."""
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        try:
            data = json.loads(tag.string or tag.get_text() or "{}")
        except Exception:
            continue
        stapel = data if isinstance(data, list) else [data]
        while stapel:
            knoop = stapel.pop()
            if not isinstance(knoop, dict):
                continue
            if "@graph" in knoop and isinstance(knoop["@graph"], list):
                stapel.extend(knoop["@graph"])
            soort = knoop.get("@type", "")
            soorten = soort if isinstance(soort, list) else [soort]
            soorten = {str(s).lower() for s in soorten}

            if soorten & {"organization", "localbusiness", "corporation", "medicalbusiness",
                          "dentist", "physician", "homeandconstructionbusiness", "store",
                          "professionalservice", "legalservice", "realestateagent"}:
                cg.bedrijfsnaam = cg.bedrijfsnaam or str(knoop.get("name", ""))[:120]
                if isinstance(knoop.get("email"), str):
                    cg.emails.append(knoop["email"].replace("mailto:", ""))
                if isinstance(knoop.get("telephone"), str):
                    cg.telefoons.append(knoop["telephone"])
                adres = knoop.get("address")
                if isinstance(adres, dict):
                    cg.adres = cg.adres or " ".join(
                        str(adres.get(k, "")) for k in ("streetAddress",)
                    ).strip()
                    cg.postcode = cg.postcode or str(adres.get("postalCode", "")).strip()
                    cg.plaats = cg.plaats or str(adres.get("addressLocality", "")).strip()
                voor_zelfde = knoop.get("sameAs")
                if isinstance(voor_zelfde, list):
                    for link in voor_zelfde:
                        _sorteer_social(str(link), cg)

            if "person" in soorten:
                naam = str(knoop.get("name", "")).strip()
                if lijkt_op_naam(naam):
                    cg.personen.append({
                        "naam": naam,
                        "functie": str(knoop.get("jobTitle", "")).strip(),
                        "email": str(knoop.get("email", "")).replace("mailto:", "").strip(),
                    })


def _sorteer_social(url: str, cg: Contactgegevens) -> None:
    laag = url.lower()
    if "linkedin.com/" in laag and not cg.linkedin:
        cg.linkedin = url.split("?")[0]
    elif "facebook.com/" in laag and not cg.facebook:
        cg.facebook = url.split("?")[0]
    elif "instagram.com/" in laag and not cg.instagram:
        cg.instagram = url.split("?")[0]


def _personen_uit_kaarten(soup: BeautifulSoup, cg: Contactgegevens) -> None:
    """Teampagina's: naam + functie staan vrijwel altijd in hetzelfde blok."""
    kandidaten = soup.select(
        "[class*=team], [class*=medewerker], [class*=persoon], [class*=member], "
        "[class*=staff], [class*=employee], [class*=card], [class*=profiel], article, li"
    )
    for blok in kandidaten[:400]:
        tekst = re.sub(r"\s+", " ", blok.get_text(" ", strip=True))
        if not (6 <= len(tekst) <= 400):
            continue
        laag = tekst.lower()
        if not any(t in laag for t in FUNCTIE_TREFWOORDEN):
            continue

        naam = ""
        for kop in blok.select("h1, h2, h3, h4, h5, strong, b, [class*=naam], [class*=name], [class*=title]"):
            kandidaat = re.sub(r"\s+", " ", kop.get_text(" ", strip=True))
            if lijkt_op_naam(kandidaat):
                naam = kandidaat
                break
        if not naam:
            continue

        functie = ""
        for trefwoord in FUNCTIE_TREFWOORDEN:
            treffer = re.search(
                r"([^.·|\n]{0,45}\b" + re.escape(trefwoord) + r"\b[^.·|\n]{0,35})", tekst, re.I
            )
            if treffer:
                functie = treffer.group(1).strip(" -–—·|,")
                break

        mail = ""
        mailto = blok.find("a", href=re.compile(r"^mailto:", re.I))
        if mailto:
            mail = mailto.get("href", "")[7:].split("?")[0]

        cg.personen.append({"naam": naam, "functie": functie[:80], "email": mail})


def extraheer(html: str, basis_url: str) -> Contactgegevens:
    """Hoofdingang: HTML -> Contactgegevens."""
    cg = Contactgegevens()
    soup = BeautifulSoup(html, "lxml")

    titel_tag = soup.find("title")
    cg.titel = (titel_tag.get_text(strip=True) if titel_tag else "")[:160]

    _uit_jsonld(soup, cg)

    # mailto:/tel: links zijn de betrouwbaarste signalen
    eigen_domein = registreerbaar_domein(basis_url)
    for a in soup.find_all("a", href=True):
        href = html_lib.unescape(a["href"]).strip()
        laag = href.lower()
        if laag.startswith("mailto:"):
            cg.emails.append(href[7:].split("?")[0].strip())
        elif laag.startswith("tel:"):
            cg.telefoons.append(href[4:].strip())
        elif laag.startswith(("http://", "https://")):
            _sorteer_social(href, cg)
            doel = registreerbaar_domein(href)
            if doel and doel != eigen_domein:
                cg.externe_links.append(href.split("#")[0])
        elif laag.startswith("/") and not laag.startswith("//"):
            pass

    tekst = _deobfusceer(html_lib.unescape(_zichtbare_tekst(soup)))

    cg.emails.extend(EMAIL_RE.findall(tekst))
    cg.emails.extend(EMAIL_RE.findall(_deobfusceer(html_lib.unescape(html))))
    cg.telefoons.extend(PHONE_RE.findall(tekst))

    if (m := KVK_RE.search(tekst)):
        cg.kvk_nummer = m.group(1)
    if (m := BTW_RE.search(tekst)):
        cg.btw_nummer = re.sub(r"\s+", "", m.group(0)).upper()
    if not cg.postcode and (m := POSTCODE_RE.search(tekst)):
        cg.postcode = f"{m.group(1)} {m.group(2).upper()}"

    _personen_uit_kaarten(soup, cg)

    if not cg.bedrijfsnaam:
        og = soup.find("meta", attrs={"property": "og:site_name"})
        if og and og.get("content"):
            cg.bedrijfsnaam = og["content"].strip()[:120]
        elif cg.titel:
            cg.bedrijfsnaam = re.split(r"\s[|\-–—·»]\s", cg.titel)[0].strip()[:120]

    cg.tekstfragment = _kerntekst(html) or re.sub(r"\s+", " ", tekst).strip()[:600]

    # opschonen
    schone_mails, gezien = [], set()
    for e in cg.emails:
        e = html_lib.unescape(e).strip(" .,;:<>()[]\"'").lower()
        if is_bruikbaar_email(e) and e not in gezien:
            gezien.add(e)
            schone_mails.append(e)
    cg.emails = schone_mails

    schone_tels, gezien_t = [], set()
    for t in cg.telefoons:
        genormaliseerd, _ = normaliseer_telefoon(t)
        if genormaliseerd and genormaliseerd not in gezien_t:
            gezien_t.add(genormaliseerd)
            schone_tels.append(genormaliseerd)
    cg.telefoons = schone_tels

    unieke_personen, gezien_p = [], set()
    for p in cg.personen:
        sleutel = p["naam"].lower()
        if sleutel and sleutel not in gezien_p:
            gezien_p.add(sleutel)
            unieke_personen.append(p)
    cg.personen = unieke_personen[:40]

    cg.externe_links = list(dict.fromkeys(cg.externe_links))[:300]
    return cg


def interne_links(html: str, basis_url: str, *, alleen_contactachtig: bool = True) -> list[str]:
    """Interne links op dezelfde site — standaard gefilterd op contact-achtige paden."""
    soup = BeautifulSoup(html, "lxml")
    basis_domein = registreerbaar_domein(basis_url)
    gevonden: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absoluut = urljoin(basis_url, href).split("#")[0]
        if registreerbaar_domein(absoluut) != basis_domein:
            continue
        if absoluut.lower().endswith(TROEP_EXTENSIES):
            continue
        pad = urlparse(absoluut).path.lower()
        if alleen_contactachtig:
            ankertekst = a.get_text(" ", strip=True).lower()
            if not any(h in pad or h in ankertekst.replace(" ", "-") for h in CONTACT_HINTS):
                continue
        gevonden.append(absoluut)
    return list(dict.fromkeys(gevonden))
