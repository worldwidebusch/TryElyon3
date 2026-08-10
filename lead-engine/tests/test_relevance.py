"""Tests voor het ICP-relevantiefilter."""

from leadengine.models import ICP, Lead
from leadengine.relevance import bepaal_relevantie, filter_op_relevantie

ICP_TANDARTS = ICP(
    omschrijving="Tandartspraktijken in de Randstad",
    branches=["tandartspraktijk", "mondzorg", "orthodontie"],
    zoekwoorden=["tandarts", "mondhygienist", "gebit"],
    functietitels=["praktijkhouder"],
)


def _lead(naam: str, domein: str = "", notitie: str = "") -> Lead:
    return Lead(
        bron_naam="test", bedrijfsnaam=naam,
        domein=domein or "voorbeeld.nl", notitie=notitie,
        email="info@voorbeeld.nl",
    )


def test_treffer_in_bedrijfsnaam_scoort_hoog():
    leads = [_lead("Tandartspraktijk De Molen", "demolen-tandarts.nl")]
    bepaal_relevantie(leads, ICP_TANDARTS)
    assert leads[0].relevantie >= 50


def test_patientenvereniging_valt_af():
    leads = [_lead("Patiëntenvereniging blaas- of nierkanker", "blaasofnierkanker.nl")]
    bepaal_relevantie(leads, ICP_TANDARTS)
    assert leads[0].relevantie == 0


def test_toezichthouder_valt_af():
    leads = [_lead("Landelijk Meldpunt Zorg", "igj.nl", "Inspectie Gezondheidszorg en Jeugd")]
    bepaal_relevantie(leads, ICP_TANDARTS)
    assert leads[0].relevantie == 0


def test_filter_gooit_ruis_weg_en_houdt_signaal():
    leads = [
        _lead("Tandartspraktijk Centrum", "tandartscentrum.nl"),
        _lead("Patiëntenvereniging X", "patienten.nl"),
        _lead("Glutenvrij Nederland", "glutenvrij.nl", "Alles voor een glutenvrij leven"),
    ]
    behouden, afgewezen = filter_op_relevantie(leads, ICP_TANDARTS, drempel=30)
    assert len(afgewezen) == 2
    assert [l.bedrijfsnaam for l in behouden] == ["Tandartspraktijk Centrum"]


def test_bronnaam_telt_niet_mee():
    """De bron heet 'Algemene tandartspraktijken' — dat mag geen leads redden."""
    lead = Lead(
        bron_naam="Algemene tandartspraktijken - Staat van de Mondzorg",
        segment="Algemene tandartspraktijken - Staat van de Mondzorg",
        bedrijfsnaam="Henry Schein Dental",
        domein="henryschein.nl",
        notitie="Distributeur van producten, instrumenten en apparatuur.",
        email="ruben.plomp@henryschein.nl",
    )
    bepaal_relevantie([lead], ICP_TANDARTS)
    assert lead.relevantie == 0


def test_leveranciers_en_opleiders_vallen_af():
    for naam, notitie in [
        ("Henry Schein", "Dental depot met 25000 producten op voorraad"),
        ("NTI", "MBO opleiding tandartsassistent"),
        ("Jaarbeurs Utrecht", "Congres en beurs voor de mondzorg"),
    ]:
        lead = _lead(naam, notitie=notitie)
        bepaal_relevantie([lead], ICP_TANDARTS)
        assert lead.relevantie == 0, naam


def test_zonder_icp_termen_filtert_niets():
    leeg = ICP(omschrijving="iets vaags")
    leads = [_lead("Willekeurig Bedrijf")]
    behouden, afgewezen = filter_op_relevantie(leads, leeg, drempel=30)
    assert afgewezen == [] and len(behouden) == 1


def test_samenstellingen_worden_herkend():
    leads = [_lead("Mondzorgcentrum Zuid", "mondzorgzuid.nl")]
    bepaal_relevantie(leads, ICP_TANDARTS)
    assert leads[0].relevantie >= 30
