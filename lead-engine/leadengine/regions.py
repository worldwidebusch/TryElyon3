"""Nederlandse geografie: provincies, steden en postcode->provincie.

Gebruikt voor (a) geografische fan-out bij Google Places / zoekopdrachten en
(b) het verrijken van leads met een provincie, zodat je per regio kunt segmenteren.
"""

from __future__ import annotations

import re

PROVINCIES = [
    "Groningen", "Friesland", "Drenthe", "Overijssel", "Flevoland",
    "Gelderland", "Utrecht", "Noord-Holland", "Zuid-Holland", "Zeeland",
    "Noord-Brabant", "Limburg",
]

# De 60 grootste gemeenten — dekt ~55% van alle NL-bedrijven en is genoeg
# voor een landelijke fan-out zonder je Places-quota op te blazen.
STEDEN: dict[str, str] = {
    "Amsterdam": "Noord-Holland", "Rotterdam": "Zuid-Holland", "Den Haag": "Zuid-Holland",
    "Utrecht": "Utrecht", "Eindhoven": "Noord-Brabant", "Groningen": "Groningen",
    "Tilburg": "Noord-Brabant", "Almere": "Flevoland", "Breda": "Noord-Brabant",
    "Nijmegen": "Gelderland", "Apeldoorn": "Gelderland", "Arnhem": "Gelderland",
    "Haarlem": "Noord-Holland", "Haarlemmermeer": "Noord-Holland", "Amersfoort": "Utrecht",
    "Enschede": "Overijssel", "Zaanstad": "Noord-Holland", "Den Bosch": "Noord-Brabant",
    "Zwolle": "Overijssel", "Zoetermeer": "Zuid-Holland", "Leeuwarden": "Friesland",
    "Leiden": "Zuid-Holland", "Maastricht": "Limburg", "Dordrecht": "Zuid-Holland",
    "Ede": "Gelderland", "Alphen aan den Rijn": "Zuid-Holland", "Westland": "Zuid-Holland",
    "Alkmaar": "Noord-Holland", "Emmen": "Drenthe", "Delft": "Zuid-Holland",
    "Venlo": "Limburg", "Deventer": "Overijssel", "Helmond": "Noord-Brabant",
    "Oss": "Noord-Brabant", "Amstelveen": "Noord-Holland", "Hilversum": "Noord-Holland",
    "Sittard-Geleen": "Limburg", "Heerlen": "Limburg", "Hengelo": "Overijssel",
    "Purmerend": "Noord-Holland", "Roosendaal": "Noord-Brabant", "Schiedam": "Zuid-Holland",
    "Lelystad": "Flevoland", "Spijkenisse": "Zuid-Holland", "Almelo": "Overijssel",
    "Gouda": "Zuid-Holland", "Vlaardingen": "Zuid-Holland", "Assen": "Drenthe",
    "Bergen op Zoom": "Noord-Brabant", "Capelle aan den IJssel": "Zuid-Holland",
    "Veenendaal": "Utrecht", "Katwijk": "Zuid-Holland", "Zeist": "Utrecht",
    "Nieuwegein": "Utrecht", "Roermond": "Limburg", "Doetinchem": "Gelderland",
    "Hoorn": "Noord-Holland", "Terneuzen": "Zeeland", "Middelburg": "Zeeland",
    "Drachten": "Friesland", "Waalwijk": "Noord-Brabant", "Barneveld": "Gelderland",
}

# Randstad-kern: hoogste bedrijfsdichtheid, gebruik dit voor snelle testruns.
RANDSTAD = [
    "Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Haarlem", "Leiden",
    "Delft", "Zoetermeer", "Amstelveen", "Almere", "Amersfoort", "Dordrecht",
]

# Eerste twee postcodecijfers -> provincie (grove maar betrouwbare mapping).
_POSTCODE_PROVINCIE: list[tuple[range, str]] = [
    (range(10, 22), "Noord-Holland"),
    (range(22, 34), "Zuid-Holland"),
    (range(34, 40), "Utrecht"),
    (range(40, 45), "Zuid-Holland"),
    (range(43, 46), "Zeeland"),
    (range(46, 50), "Noord-Brabant"),
    (range(50, 57), "Noord-Brabant"),
    (range(57, 60), "Noord-Brabant"),
    (range(58, 65), "Limburg"),
    (range(65, 68), "Gelderland"),
    (range(68, 71), "Gelderland"),
    (range(71, 74), "Gelderland"),
    (range(74, 78), "Overijssel"),
    (range(78, 80), "Drenthe"),
    (range(80, 84), "Overijssel"),
    (range(82, 85), "Flevoland"),
    (range(85, 90), "Friesland"),
    (range(90, 98), "Groningen"),
    (range(98, 100), "Groningen"),
]


def provincie_van_postcode(postcode: str) -> str:
    m = re.match(r"\s*(\d{2})", postcode or "")
    if not m:
        return ""
    prefix = int(m.group(1))
    for bereik, provincie in _POSTCODE_PROVINCIE:
        if prefix in bereik:
            return provincie
    return ""


def provincie_van_plaats(plaats: str) -> str:
    if not plaats:
        return ""
    schoon = plaats.strip().title()
    if schoon in STEDEN:
        return STEDEN[schoon]
    for stad, prov in STEDEN.items():
        if stad.lower() in plaats.lower():
            return prov
    if schoon in PROVINCIES:
        return schoon
    return ""


def bepaal_provincie(postcode: str = "", plaats: str = "") -> str:
    return provincie_van_postcode(postcode) or provincie_van_plaats(plaats)


def steden_voor(regios: list[str], *, limiet: int = 25) -> list[str]:
    """Zet ICP-regio's om naar een concrete stedenlijst voor geo fan-out."""
    if not regios:
        return list(STEDEN)[:limiet]

    gekozen: list[str] = []
    for regio in regios:
        r = regio.strip()
        laag = r.lower()
        if laag in {"nederland", "nl", "landelijk", "heel nederland"}:
            gekozen.extend(STEDEN)
            continue
        if laag == "randstad":
            gekozen.extend(RANDSTAD)
            continue
        prov = next((p for p in PROVINCIES if p.lower() == laag), "")
        if prov:
            gekozen.extend([s for s, p in STEDEN.items() if p == prov])
            continue
        gekozen.append(r)

    uniek = list(dict.fromkeys(gekozen))
    return uniek[:limiet] if uniek else list(STEDEN)[:limiet]
