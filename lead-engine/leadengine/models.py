"""Datamodellen: ICP, Bron (catalyst database) en Lead."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any


# ── Oogstmodus per bron ─────────────────────────────────────────────────────
# "auto"      = de motor scrapet dit zelf
# "api"       = via officiële API, alleen als de key aanwezig is
# "handmatig" = platform staat geautomatiseerd oogsten van persoonsgegevens niet
#               toe (LinkedIn, Facebook, Discord, Skool, Instagram). We zetten de
#               bron wél op je bronnenlijst met een concreet handmatig recept,
#               zodat je 'm bewust en binnen de regels kunt gebruiken.
OOGST_AUTO = "auto"
OOGST_API = "api"
OOGST_HANDMATIG = "handmatig"


@dataclass
class ICP:
    """Ideaal klantprofiel — altijd NL-gericht."""

    omschrijving: str = ""
    branches: list[str] = field(default_factory=list)
    functietitels: list[str] = field(default_factory=list)
    bedrijfsgrootte: str = ""
    regios: list[str] = field(default_factory=list)
    pijnpunten: list[str] = field(default_factory=list)
    koopsignalen: list[str] = field(default_factory=list)
    zoekwoorden: list[str] = field(default_factory=list)
    branchverenigingen: list[str] = field(default_factory=list)
    uitsluiten: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ICP":
        bekend = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in bekend})

    def samenvatting(self) -> str:
        delen = []
        if self.branches:
            delen.append("Branches: " + ", ".join(self.branches))
        if self.functietitels:
            delen.append("Functies: " + ", ".join(self.functietitels))
        if self.bedrijfsgrootte:
            delen.append("Grootte: " + self.bedrijfsgrootte)
        if self.regios:
            delen.append("Regio's: " + ", ".join(self.regios))
        return " | ".join(delen) or self.omschrijving


@dataclass
class Bron:
    """Eén catalyst database — een plek waar de ICP actief samenkomt."""

    naam: str
    type: str                      # branchevereniging, register, marktplaats, community, ...
    url: str = ""
    connector: str = "listing"     # welke connector 'm kan oogsten
    oogstmodus: str = OOGST_AUTO
    segment: str = ""              # micro-segment-label; wordt de CSV-groepering
    prioriteit: int = 3            # 1 (hoog) .. 5 (laag)
    verwacht_volume: str = ""
    signaal: str = ""              # waarom aanwezigheid hier een koopsignaal is
    aanpak: str = ""               # concreet recept (vooral bij oogstmodus=handmatig)
    params: dict[str, Any] = field(default_factory=dict)

    def sleutel(self) -> str:
        return hashlib.sha1(f"{self.connector}|{self.url or self.naam}".lower().encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("params", None)
        return d


@dataclass
class Lead:
    """Eén contact. Alles optioneel behalve de bron-herkomst."""

    bron_naam: str
    bron_type: str = ""
    segment: str = ""
    bron_url: str = ""

    bedrijfsnaam: str = ""
    website: str = ""
    domein: str = ""

    voornaam: str = ""
    achternaam: str = ""
    volledige_naam: str = ""
    functie: str = ""

    email: str = ""
    email_status: str = ""         # geldig / risico / ongeldig / onbekend
    email_type: str = ""           # persoonlijk / rol / algemeen
    telefoon: str = ""
    telefoon_type: str = ""        # mobiel / vast / onbekend

    adres: str = ""
    postcode: str = ""
    plaats: str = ""
    provincie: str = ""
    land: str = "Nederland"

    kvk_nummer: str = ""
    btw_nummer: str = ""
    linkedin_url: str = ""
    facebook_url: str = ""
    instagram_url: str = ""

    beoordeling: str = ""          # Google-rating e.d.
    aantal_reviews: str = ""
    branche: str = ""
    notitie: str = ""              # ruwe context voor je AI-personalisatie
    gevonden_op: str = ""

    score: int = 0
    relevantie: int = 0            # 0-100: hoe goed dit bedrijf op het ICP past

    def identiteit(self) -> str:
        """Ontdubbelsleutel: e-mail > telefoon > domein+naam."""
        if self.email:
            return f"e:{self.email.lower()}"
        if self.telefoon:
            return f"t:{self.telefoon}"
        basis = f"{self.domein}|{self.bedrijfsnaam}".lower().strip("|")
        return f"b:{hashlib.sha1(basis.encode()).hexdigest()[:16]}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
