"""CSV-export.

Levert per run:
  leads_alle.csv              alles, gesorteerd op score
  segmenten/<segment>.csv     één bestand per catalyst database  <- je campagnes
  bronnen.csv                 de complete bronnenlijst, ook de handmatige
  overzicht.csv               volume per segment (jouw "kolom F")
  instantly/<segment>.csv     kale kolommen, direct te importeren in Instantly
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from .models import Bron, Lead

KOLOMMEN = [
    ("bedrijfsnaam", "Bedrijfsnaam"),
    ("voornaam", "Voornaam"),
    ("achternaam", "Achternaam"),
    ("volledige_naam", "Volledige naam"),
    ("functie", "Functie"),
    ("email", "E-mail"),
    ("email_status", "E-mailstatus"),
    ("email_type", "E-mailtype"),
    ("telefoon", "Telefoon"),
    ("telefoon_type", "Telefoontype"),
    ("website", "Website"),
    ("domein", "Domein"),
    ("adres", "Adres"),
    ("postcode", "Postcode"),
    ("plaats", "Plaats"),
    ("provincie", "Provincie"),
    ("land", "Land"),
    ("kvk_nummer", "KvK-nummer"),
    ("btw_nummer", "BTW-nummer"),
    ("branche", "Branche"),
    ("beoordeling", "Beoordeling"),
    ("aantal_reviews", "Aantal reviews"),
    ("linkedin_url", "LinkedIn"),
    ("facebook_url", "Facebook"),
    ("instagram_url", "Instagram"),
    ("score", "Score"),
    ("relevantie", "ICP-relevantie"),
    ("segment", "Segment"),
    ("bron_naam", "Bron"),
    ("bron_type", "Brontype"),
    ("bron_url", "Bron-URL"),
    ("gevonden_op", "Gevonden op"),
    ("notitie", "Context voor personalisatie"),
]

INSTANTLY_KOLOMMEN = [
    ("email", "email"),
    ("voornaam", "first_name"),
    ("achternaam", "last_name"),
    ("bedrijfsnaam", "company_name"),
    ("functie", "job_title"),
    ("telefoon", "phone"),
    ("website", "website"),
    ("plaats", "city"),
    ("provincie", "province"),
    ("segment", "segment"),
    ("notitie", "context"),
]

BRON_KOLOMMEN = [
    ("naam", "Bron"),
    ("type", "Type"),
    ("segment", "Segment"),
    ("url", "URL"),
    ("connector", "Connector"),
    ("oogstmodus", "Oogstmodus"),
    ("prioriteit", "Prioriteit"),
    ("verwacht_volume", "Verwacht volume"),
    ("signaal", "Waarom dit een koopsignaal is"),
    ("aanpak", "Aanpak"),
]


def _veilige_naam(tekst: str) -> str:
    schoon = re.sub(r"[^\w\s\-]", "", tekst, flags=re.UNICODE).strip()
    schoon = re.sub(r"[\s]+", "_", schoon)
    return (schoon or "segment")[:60]


def _schrijf(pad: Path, kolommen: list[tuple[str, str]], rijen: list[dict]) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig zodat Excel op Windows de accenten goed toont
    with pad.open("w", newline="", encoding="utf-8-sig") as f:
        schrijver = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        schrijver.writerow([kop for _, kop in kolommen])
        for rij in rijen:
            schrijver.writerow([rij.get(veld, "") for veld, _ in kolommen])


def exporteer(
    map_pad: Path,
    leads: list[Lead],
    bronnen: list[Bron],
    *,
    min_score: int = 0,
) -> dict[str, int]:
    map_pad.mkdir(parents=True, exist_ok=True)

    gefilterd = [l for l in leads if l.score >= min_score]
    gesorteerd = sorted(gefilterd, key=lambda l: (-l.score, l.segment, l.bedrijfsnaam))
    rijen = [l.to_dict() for l in gesorteerd]

    _schrijf(map_pad / "leads_alle.csv", KOLOMMEN, rijen)

    per_segment: dict[str, list[Lead]] = defaultdict(list)
    for lead in gesorteerd:
        per_segment[lead.segment or lead.bron_naam or "overig"].append(lead)

    for segment, groep in per_segment.items():
        bestandsnaam = f"{_veilige_naam(segment)}.csv"
        _schrijf(
            map_pad / "segmenten" / bestandsnaam,
            KOLOMMEN,
            [l.to_dict() for l in groep],
        )
        met_mail = [l for l in groep if l.email and l.email_status != "ongeldig"]
        if met_mail:
            _schrijf(
                map_pad / "instantly" / bestandsnaam,
                INSTANTLY_KOLOMMEN,
                [l.to_dict() for l in met_mail],
            )

    _schrijf(map_pad / "bronnen.csv", BRON_KOLOMMEN, [b.to_dict() for b in bronnen])

    overzicht = []
    for segment, groep in sorted(per_segment.items(), key=lambda kv: -len(kv[1])):
        met_mail = sum(1 for l in groep if l.email and l.email_status != "ongeldig")
        met_tel = sum(1 for l in groep if l.telefoon)
        persoonlijk = sum(1 for l in groep if l.email_type == "persoonlijk")
        overzicht.append({
            "segment": segment,
            "bron": groep[0].bron_naam,
            "brontype": groep[0].bron_type,
            "totaal": len(groep),
            "met_email": met_mail,
            "persoonlijk_email": persoonlijk,
            "met_telefoon": met_tel,
            "gem_score": round(sum(l.score for l in groep) / len(groep)),
            "bestand": f"segmenten/{_veilige_naam(segment)}.csv",
        })

    _schrijf(
        map_pad / "overzicht.csv",
        [
            ("segment", "Segment"),
            ("bron", "Bron"),
            ("brontype", "Brontype"),
            ("totaal", "Totaal leads"),
            ("met_email", "Met e-mail"),
            ("persoonlijk_email", "Persoonlijk e-mail"),
            ("met_telefoon", "Met telefoon"),
            ("gem_score", "Gem. score"),
            ("bestand", "Bestand"),
        ],
        overzicht,
    )

    return {
        "leads": len(gesorteerd),
        "segmenten": len(per_segment),
        "met_email": sum(1 for l in gesorteerd if l.email and l.email_status != "ongeldig"),
        "met_telefoon": sum(1 for l in gesorteerd if l.telefoon),
    }


def lees_csv_leads(pad: Path, bron_naam: str = "Handmatige import") -> list[Lead]:
    """Voor `leadengine importeer`: CSV met minimaal een website- of domeinkolom."""
    leads: list[Lead] = []
    with pad.open(newline="", encoding="utf-8-sig") as f:
        monster = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(monster, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        for rij in csv.DictReader(f, dialect=dialect):
            genormaliseerd = {(k or "").strip().lower(): (v or "").strip() for k, v in rij.items()}
            website = (
                genormaliseerd.get("website")
                or genormaliseerd.get("url")
                or genormaliseerd.get("domein")
                or genormaliseerd.get("domain")
                or ""
            )
            bedrijf = (
                genormaliseerd.get("bedrijfsnaam")
                or genormaliseerd.get("bedrijf")
                or genormaliseerd.get("company")
                or genormaliseerd.get("naam")
                or ""
            )
            if not website and not bedrijf:
                continue
            leads.append(Lead(
                bron_naam=bron_naam,
                bron_type="handmatige import",
                segment=genormaliseerd.get("segment") or bron_naam,
                bedrijfsnaam=bedrijf,
                website=website,
                email=genormaliseerd.get("email") or genormaliseerd.get("e-mail") or "",
                telefoon=genormaliseerd.get("telefoon") or genormaliseerd.get("phone") or "",
                plaats=genormaliseerd.get("plaats") or genormaliseerd.get("city") or "",
                volledige_naam=genormaliseerd.get("volledige naam") or genormaliseerd.get("name") or "",
            ))
    return leads
