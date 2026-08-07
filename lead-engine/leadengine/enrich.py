"""Validatie en verrijking.

Zonder API-key: syntax + MX-record + wegwerpdomein-check + rolherkenning.
Met ZEROBOUNCE_API_KEY: echte mailbox-validatie (aanrader vóór je gaat sturen —
je bouncerate bepaalt of je domein blijft leven).
"""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import dns.resolver

from . import extract
from .config import SETTINGS
from .http import Fetcher
from .models import Lead
from .regions import bepaal_provincie

WEGWERP_DOMEINEN = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "yopmail.com", "sharklasers.com", "getnada.com",
    "temp-mail.org", "throwawaymail.com", "maildrop.cc", "dispostable.com",
}

GRATIS_PROVIDERS = {
    "gmail.com", "hotmail.com", "hotmail.nl", "live.nl", "outlook.com",
    "outlook.nl", "ziggo.nl", "kpnmail.nl", "planet.nl", "home.nl",
    "casema.nl", "chello.nl", "xs4all.nl", "telfort.nl", "upcmail.nl",
    "yahoo.com", "icloud.com", "me.com", "protonmail.com", "zonnet.nl",
}

_mx_cache: dict[str, bool] = {}
_resolver = dns.resolver.Resolver()
_resolver.timeout = 3.0
_resolver.lifetime = 3.0


def _heeft_mx(domein: str) -> bool:
    if domein in _mx_cache:
        return _mx_cache[domein]
    goed = False
    try:
        antwoorden = _resolver.resolve(domein, "MX")
        goed = len(antwoorden) > 0
    except Exception:
        try:
            _resolver.resolve(domein, "A")
            goed = True                      # A-record zonder MX: twijfelgeval
        except Exception:
            goed = False
    _mx_cache[domein] = goed
    return goed


async def controleer_mx(leads: list[Lead]) -> None:
    """Zet email_status op basis van syntax + MX. Draait DNS in threads."""
    domeinen = {
        l.email.split("@", 1)[1] for l in leads if l.email and "@" in l.email
    }
    if not domeinen:
        return

    lus = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=16) as pool:
        resultaten = await asyncio.gather(
            *(lus.run_in_executor(pool, _heeft_mx, d) for d in domeinen)
        )
    per_domein = dict(zip(domeinen, resultaten))

    for lead in leads:
        if not lead.email:
            lead.email_status = ""
            continue
        domein = lead.email.split("@", 1)[1]
        basis = extract.registreerbaar_domein(domein)
        if basis in WEGWERP_DOMEINEN:
            lead.email_status = "ongeldig"
        elif not per_domein.get(domein, False):
            lead.email_status = "ongeldig"
        elif lead.email_type in {"algemeen", "rol"}:
            lead.email_status = "risico"
        else:
            lead.email_status = "geldig"


async def valideer_zerobounce(fetcher: Fetcher, leads: list[Lead], *, max_checks: int = 500) -> int:
    """Echte mailbox-validatie. Overschrijft email_status. Kost credits."""
    if not SETTINGS.zerobounce_key:
        return 0

    te_checken = [l for l in leads if l.email and l.email_status != "ongeldig"][:max_checks]
    if not te_checken:
        return 0

    sem = asyncio.Semaphore(8)

    async def _check(lead: Lead) -> bool:
        async with sem:
            data = await fetcher.json(
                "https://api.zerobounce.net/v2/validate",
                params={"api_key": SETTINGS.zerobounce_key, "email": lead.email, "ip_address": ""},
            )
        if not data:
            return False
        status = (data.get("status") or "").lower()
        lead.email_status = {
            "valid": "geldig",
            "catch-all": "risico",
            "unknown": "risico",
            "do_not_mail": "ongeldig",
            "spamtrap": "ongeldig",
            "abuse": "ongeldig",
            "invalid": "ongeldig",
        }.get(status, "onbekend")
        lead.voornaam = lead.voornaam or (data.get("firstname") or "")
        lead.achternaam = lead.achternaam or (data.get("lastname") or "")
        return True

    resultaten = await asyncio.gather(*(_check(l) for l in te_checken), return_exceptions=True)
    return sum(1 for r in resultaten if r is True)


def normaliseer(leads: list[Lead]) -> None:
    """Laatste opschoning: casing, provincie, domein, naamvelden."""
    for lead in leads:
        lead.email = lead.email.strip().lower()
        if lead.email and not extract.is_bruikbaar_email(lead.email):
            lead.email = ""
            lead.email_type = ""

        if lead.website and not lead.domein:
            lead.domein = extract.registreerbaar_domein(lead.website)

        if lead.telefoon and not lead.telefoon.startswith("+"):
            lead.telefoon, lead.telefoon_type = extract.normaliseer_telefoon(lead.telefoon)

        if lead.volledige_naam and not lead.voornaam:
            lead.voornaam, lead.achternaam = extract.splits_naam(lead.volledige_naam)
        if not lead.volledige_naam:
            lead.volledige_naam = f"{lead.voornaam} {lead.achternaam}".strip()

        lead.voornaam = lead.voornaam.strip().title() if lead.voornaam.islower() else lead.voornaam.strip()
        lead.bedrijfsnaam = re.sub(r"\s+", " ", lead.bedrijfsnaam).strip()[:120]

        if not lead.provincie:
            lead.provincie = bepaal_provincie(lead.postcode, lead.plaats)

        if lead.email and not lead.email_type:
            lead.email_type = extract.email_type(lead.email)

        lead.notitie = re.sub(r"\s+", " ", lead.notitie).strip()[:600]
