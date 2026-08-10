"""Ontdubbelen en scoren.

Ontdubbelen gebeurt op drie niveaus:
  1. exacte identiteit (e-mail > telefoon > domein+bedrijfsnaam)
  2. één persoonlijk e-mailadres per persoon per domein
  3. optioneel: max N rijen per bedrijfsdomein, zodat één groot bedrijf je
     campagne niet overneemt
"""

from __future__ import annotations

from collections import defaultdict

from rapidfuzz import fuzz

from .config import PROJECT_ROOT
from .models import Lead

UITSLUITLIJST_PAD = PROJECT_ROOT / "uitsluitlijst.txt"


def laad_uitsluitlijst() -> set[str]:
    """Eén regel per e-mailadres of domein. Regels met # zijn commentaar."""
    if not UITSLUITLIJST_PAD.exists():
        return set()
    regels = UITSLUITLIJST_PAD.read_text(encoding="utf-8").splitlines()
    return {
        r.strip().lower()
        for r in regels
        if r.strip() and not r.strip().startswith("#")
    }


def _uitgesloten(lead: Lead, lijst: set[str]) -> bool:
    if not lijst:
        return False
    if lead.email and lead.email.lower() in lijst:
        return True
    if lead.domein and lead.domein.lower() in lijst:
        return True
    return False


def ontdubbel(
    leads: list[Lead],
    *,
    max_per_domein: int = 3,
    icp_uitsluitingen: list[str] | None = None,
) -> tuple[list[Lead], dict[str, int]]:
    lijst = laad_uitsluitlijst()
    uitsluittermen = [t.lower() for t in (icp_uitsluitingen or []) if len(t) > 3]

    statistiek = defaultdict(int)
    gezien: dict[str, Lead] = {}

    for lead in leads:
        if not lead.email and not lead.telefoon:
            statistiek["geen contactgegevens"] += 1
            continue
        if _uitgesloten(lead, lijst):
            statistiek["op uitsluitlijst"] += 1
            continue
        if lead.email_status == "ongeldig":
            statistiek["ongeldig e-mailadres"] += 1
            continue
        if uitsluittermen:
            hooi = f"{lead.bedrijfsnaam} {lead.branche} {lead.notitie}".lower()
            if any(t in hooi for t in uitsluittermen):
                statistiek["ICP-uitsluiting"] += 1
                continue

        sleutel = lead.identiteit()
        bestaand = gezien.get(sleutel)
        if bestaand is None:
            gezien[sleutel] = lead
        else:
            _voeg_samen(bestaand, lead)
            statistiek["dubbel samengevoegd"] += 1

    uniek = list(gezien.values())

    # Fuzzy dedupe: zelfde domein + bijna-identieke persoonsnaam
    per_domein: dict[str, list[Lead]] = defaultdict(list)
    for lead in uniek:
        per_domein[lead.domein or lead.bedrijfsnaam.lower()].append(lead)

    resultaat: list[Lead] = []
    for sleutel, groep in per_domein.items():
        behouden: list[Lead] = []
        for lead in sorted(groep, key=lambda l: -_ruwe_kwaliteit(l)):
            if any(
                lead.volledige_naam and k.volledige_naam
                and fuzz.token_sort_ratio(lead.volledige_naam, k.volledige_naam) > 88
                for k in behouden
            ):
                statistiek["fuzzy dubbel"] += 1
                continue
            behouden.append(lead)
        if sleutel and max_per_domein > 0 and len(behouden) > max_per_domein:
            statistiek["boven domeinlimiet"] += len(behouden) - max_per_domein
            behouden = behouden[:max_per_domein]
        resultaat.extend(behouden)

    return resultaat, dict(statistiek)


def _voeg_samen(doel: Lead, extra: Lead) -> None:
    """Vul lege velden van `doel` aan met wat `extra` wél heeft."""
    for veld in (
        "bedrijfsnaam", "website", "domein", "voornaam", "achternaam",
        "volledige_naam", "functie", "telefoon", "telefoon_type", "adres",
        "postcode", "plaats", "provincie", "kvk_nummer", "btw_nummer",
        "linkedin_url", "facebook_url", "instagram_url", "beoordeling",
        "aantal_reviews", "branche", "email", "email_type",
    ):
        if not getattr(doel, veld) and getattr(extra, veld):
            setattr(doel, veld, getattr(extra, veld))
    if extra.notitie and len(extra.notitie) > len(doel.notitie):
        doel.notitie = extra.notitie


def _ruwe_kwaliteit(lead: Lead) -> int:
    punten = 0
    if lead.email:
        punten += 3
        if lead.email_type == "persoonlijk":
            punten += 3
        if lead.email_status == "geldig":
            punten += 2
    if lead.telefoon:
        punten += 2
    if lead.volledige_naam:
        punten += 2
    if lead.functie:
        punten += 1
    return punten


# ── Scoren ──────────────────────────────────────────────────────────────────

def scoor(leads: list[Lead]) -> None:
    """0-100. Bepaalt in welke volgorde je ze in je sequencer zet."""
    for lead in leads:
        score = 0

        if lead.email:
            score += 25
            score += {"persoonlijk": 20, "rol": 8, "algemeen": 5}.get(lead.email_type, 0)
            score += {"geldig": 15, "risico": 5, "ongeldig": -40}.get(lead.email_status, 0)

        if lead.telefoon:
            score += 10
            if lead.telefoon_type == "mobiel":
                score += 5

        if lead.volledige_naam:
            score += 8
        if lead.functie:
            score += 7
        if lead.website:
            score += 3
        if lead.kvk_nummer:
            score += 2
        if lead.plaats or lead.postcode:
            score += 2

        # Reviewvolume = actief bedrijf met klantstroom
        try:
            reviews = int(lead.aantal_reviews or 0)
            if reviews >= 100:
                score += 5
            elif reviews >= 20:
                score += 3
        except ValueError:
            pass

        # Persoonlijke context voor je AI-copy is goud
        if len(lead.notitie) > 150:
            score += 3

        # ICP-fit weegt zwaar: een perfect bereikbare lead buiten je ICP is ruis
        score += round((lead.relevantie - 50) * 0.2)

        lead.score = max(0, min(100, score))
