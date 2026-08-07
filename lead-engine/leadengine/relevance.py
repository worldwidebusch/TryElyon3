"""ICP-relevantie: past dit bedrijf überhaupt bij wie je zoekt?

Zonder deze stap sleept een ledenlijst alles mee wat toevallig op de pagina
stond — bij een tandarts-ICP kwamen er patiëntenverenigingen en toezichthouders
mee. Die vervuilen je campagne en je bounce-statistieken.

De regel: elk bedrijf krijgt 0-100. Bevat de ICP concrete branchetermen, dan
moet een lead minimaal één treffer hebben om mee te gaan.
"""

from __future__ import annotations

import re

from .models import ICP, Lead

# Organisaties die vrijwel nooit een B2B-koper zijn
_NOOIT_LEAD = (
    "patiëntenvereniging", "patientenvereniging", "belangenvereniging",
    "inspectie", "ministerie", "rijksoverheid", "gemeente ", "provincie ",
    "toezichthouder", "ombudsman", "meldpunt", "keurmerkinstituut",
    "kenniscentrum", "koepelorganisatie", "wikipedia", "encyclopedie",
    "vacaturebank", "nieuwsbrief", "persbericht", "subsidie", "fonds voor",
    "universiteit", "hogeschool", "studievereniging", "bibliotheek",
    # leveranciers en opleiders van je doelgroep — verkopen áán je ICP,
    # zijn zelf zelden je koper
    "groothandel", "distributeur", "leverancier van", "dental depot",
    "opleidingsinstituut", "cursusaanbod", "mbo opleiding", "hbo opleiding",
    "vakblad", "vaktijdschrift", "beursorganisatie", "jaarbeurs", "congresbureau",
)

_WOORD = re.compile(r"[a-zà-ÿ]+", re.I)

# Nederlandse meervouds- en afleidingsuitgangen, langste eerst
_UITGANGEN = ("elijke", "ingen", "eren", "en", "es", "s", "e")


def _stam(woord: str) -> str:
    """Grove stam zodat 'tandartspraktijken' en 'tandartspraktijk' matchen.

    Bewust primitief: geen echte stemmer, alleen genoeg om enkelvoud/meervoud
    en samenstellingen bij elkaar te brengen zonder valse treffers.
    """
    woord = woord.lower()
    for uitgang in _UITGANGEN:
        if len(woord) - len(uitgang) >= 5 and woord.endswith(uitgang):
            return woord[: -len(uitgang)]
    return woord


def _tokens(tekst: str) -> set[str]:
    return {_stam(w) for w in _WOORD.findall(tekst) if len(w) > 3}


def _termen(icp: ICP) -> tuple[set[str], set[str]]:
    """(sterke termen uit branches, zwakke termen uit zoekwoorden/titels)."""
    sterk: set[str] = set()
    for branche in icp.branches:
        sterk |= _tokens(branche)
    zwak: set[str] = set()
    for waarde in icp.zoekwoorden + icp.functietitels + icp.branchverenigingen:
        zwak |= _tokens(waarde)
    return sterk, zwak - sterk


def bepaal_relevantie(leads: list[Lead], icp: ICP) -> None:
    sterk, zwak = _termen(icp)

    for lead in leads:
        # LET OP: bewust zónder lead.segment/bron_naam. Die bevatten per definitie
        # de ICP-term (het is immers de bron die we ervoor kozen), waardoor élke
        # lead uit die bron automatisch zou slagen. Alleen wat het BEDRIJF zelf
        # zegt telt mee.
        hooi = " ".join([
            lead.bedrijfsnaam, lead.branche, lead.domein.replace(".", " "),
            lead.functie, lead.notitie[:400],
        ]).lower()

        if any(term in hooi for term in _NOOIT_LEAD):
            lead.relevantie = 0
            continue

        if not sterk and not zwak:
            lead.relevantie = 50            # geen ICP-termen: niets te filteren
            continue

        woorden = _tokens(hooi)
        treffers_sterk = len(sterk & woorden)
        treffers_zwak = len(zwak & woorden)

        # Substring-treffers op de stam vangen samenstellingen op:
        # "mondzorgcentrum" bevat "mondzorg", "installatiebedrijf" bevat "installatie"
        if not treffers_sterk:
            treffers_sterk = sum(1 for term in sterk if len(term) > 4 and term in hooi)
        if not treffers_zwak:
            treffers_zwak = sum(1 for term in zwak if len(term) > 4 and term in hooi)

        score = min(100, treffers_sterk * 30 + treffers_zwak * 10)

        # De bedrijfsnaam of het domein noemt de branche letterlijk: sterk signaal
        naam_en_domein = f"{lead.bedrijfsnaam} {lead.domein}".lower()
        if any(term in naam_en_domein for term in sterk if len(term) > 4):
            score = min(100, score + 25)

        lead.relevantie = score


def filter_op_relevantie(
    leads: list[Lead], icp: ICP, *, drempel: int
) -> tuple[list[Lead], list[Lead]]:
    """Geeft (behouden, afgewezen) terug.

    De afgewezen leads gooien we niet weg maar exporteren we apart. Staat je
    drempel te streng, dan zie je dat meteen in `afgewezen_buiten_icp.csv`
    in plaats van dat je leads stilzwijgend kwijtraakt.
    """
    bepaal_relevantie(leads, icp)
    sterk, zwak = _termen(icp)
    if not sterk and not zwak:
        return leads, []                   # geen ICP-termen: niets te filteren
    behouden = [l for l in leads if l.relevantie >= drempel]
    afgewezen = [l for l in leads if l.relevantie < drempel]
    return behouden, afgewezen
