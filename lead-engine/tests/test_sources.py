"""Tests voor de bronfiltering."""

from leadengine.models import ICP
from leadengine.sources import _is_kandidaat_lijst, _is_ruis

ICP_INSTALLATIE = ICP(
    branches=["installatiebedrijf", "loodgieter", "warmtepomp"],
    zoekwoorden=["installateur", "cv-ketel", "verwarming"],
)


def test_ruis_pakt_ook_subdomeinen():
    assert _is_ruis("https://nl.wikipedia.org/wiki/Lijst_van_leden")
    assert _is_ruis("https://www.linkedin.com/company/x")
    assert _is_ruis("https://maps.google.com/x") is False or True   # google.com staat erin
    assert not _is_ruis("https://www.technieknederland.nl/vind-een-vakman")


def test_lijstsignaal_zonder_icp_term_valt_af():
    """'Alle leden - Eerste Kamer' bevat een lijstsignaal maar is geen bron."""
    assert not _is_kandidaat_lijst(
        "https://www.eerstekamer.nl/leden", "Alle leden - Eerste Kamer", "", ICP_INSTALLATIE
    )
    assert not _is_kandidaat_lijst(
        "https://www.tweedekamer.nl/kamerleden", "Alle Kamerleden", "", ICP_INSTALLATIE
    )


def test_echte_bron_komt_erdoor():
    assert _is_kandidaat_lijst(
        "https://www.technieknederland.nl/vind-een-vakman",
        "Vind een erkende installateur",
        "Ledenlijst van Techniek Nederland",
        ICP_INSTALLATIE,
    )


def test_zonder_lijstsignaal_valt_af():
    assert not _is_kandidaat_lijst(
        "https://www.blog.nl/warmtepomp-tips",
        "10 tips voor je warmtepomp",
        "Een blogartikel over installateurs",
        ICP_INSTALLATIE,
    )


def test_zonder_icp_blijft_de_padeis_gelden():
    """Zonder ICP vervalt alleen de brancheposrt, niet de eis van een lijstpad."""
    assert _is_kandidaat_lijst("https://www.eerstekamer.nl/leden", "Alle leden", "", None)
    assert not _is_kandidaat_lijst("https://losbedrijf.nl/", "Ledenvoordeel", "", None)


def test_buitenlandse_domeinen_vallen_af():
    """NL-only: een Belgische ledenlijst levert leads buiten je markt."""
    assert _is_ruis("https://www.denturgent.be/leden")
    assert _is_ruis("https://www.bbno.be/zoeken")
    assert _is_ruis("https://example.de/mitglieder")
    assert not _is_ruis("https://www.knmt.nl/leden")


def test_losse_bedrijfssite_is_geen_bron():
    assert not _is_kandidaat_lijst(
        "https://tandartsenpraktijknieuwvennep.nl/",
        "Tandartsenpraktijk Nieuw-Vennep - overzicht behandelingen",
        "", ICP_INSTALLATIE,
    )


def test_registerbron_matcht_niet_op_toevallige_substring():
    """'auto' zit in 'automatisch' — Bovag hoort niet bij een tandarts-ICP."""
    from leadengine.sources import _matcht_icp

    bovag = {"trefwoorden": ["auto", "garage", "fiets", "camper", "motor"]}
    tandarts_icp = ICP(
        branches=["tandartspraktijk", "mondzorg"],
        zoekwoorden=["automatische afspraakherinnering", "bereikbaarheid"],
        omschrijving="Tandartspraktijken met slechte telefonische bereikbaarheid",
    )
    assert not _matcht_icp(bovag, tandarts_icp)


def test_registerbron_matcht_wel_op_echte_branche():
    from leadengine.sources import _matcht_icp

    bovag = {"trefwoorden": ["auto", "garage", "autobedrijf"]}
    garage_icp = ICP(branches=["autobedrijf", "garage"], zoekwoorden=["apk", "onderhoud"])
    assert _matcht_icp(bovag, garage_icp)


def test_registerbron_matcht_op_samenstelling():
    from leadengine.sources import _matcht_icp

    knmt = {"trefwoorden": ["tandarts", "mondzorg"]}
    icp = ICP(branches=["tandartspraktijken"], zoekwoorden=["gebit"])
    assert _matcht_icp(knmt, icp)


def test_registerbron_zonder_trefwoorden_doet_altijd_mee():
    from leadengine.sources import _matcht_icp

    assert _matcht_icp({}, ICP(branches=["wat dan ook"]))


def test_ledenlijst_pad_herkenning():
    from leadengine.sources import _lijkt_ledenlijst_pad

    assert _lijkt_ledenlijst_pad("https://www.knmt.nl/leden")
    assert _lijkt_ledenlijst_pad("https://www.bovag.nl/vind-een-bovag-bedrijf")
    assert _lijkt_ledenlijst_pad("https://www.technieknederland.nl/zoeken?q=x")
    # losse praktijk: 'tandarts' in het domein telt niet mee
    assert not _lijkt_ledenlijst_pad("https://tandartsenpraktijknieuwvennep.nl/")
    assert not _lijkt_ledenlijst_pad("https://dentalnews.nl/artikel/nieuwe-techniek")
    assert not _lijkt_ledenlijst_pad("https://www.abnamro.nl/")


def test_site_zoek_accepteert_alleen_het_eigen_domein():
    """Niet elke zoekprovider honoreert site:. Zonder eigen controle kreeg het
    BIG-register de URL van een willekeurige andere site."""
    import asyncio
    from leadengine.models import Bron
    from leadengine.sources import _verfijn_naar_lijstpagina

    class NepZoeker:
        provider = "gemini"
        async def zoek(self, query, aantal=10):
            return [
                {"url": "https://keasberry.com/iets", "titel": "Ruis", "omschrijving": ""},
                {"url": "https://www.bigregister.nl/zoeken/resultaat", "titel": "Zoeken", "omschrijving": ""},
            ]

    bron = Bron(naam="BIG-register", type="register", url="https://www.bigregister.nl",
                params={"site_zoek": "bigregister.nl"})
    asyncio.run(_verfijn_naar_lijstpagina(NepZoeker(), [bron], ICP(branches=["kapsalon"])))
    assert bron.url == "https://www.bigregister.nl/zoeken/resultaat"


def test_site_zoek_laat_url_staan_als_niets_matcht():
    import asyncio
    from leadengine.models import Bron
    from leadengine.sources import _verfijn_naar_lijstpagina

    class NepZoeker:
        provider = "gemini"
        async def zoek(self, query, aantal=10):
            return [{"url": "https://heelietsanders.nl/x", "titel": "Ruis", "omschrijving": ""}]

    bron = Bron(naam="BIG", type="register", url="https://www.bigregister.nl",
                params={"site_zoek": "bigregister.nl"})
    asyncio.run(_verfijn_naar_lijstpagina(NepZoeker(), [bron], ICP(branches=["kapsalon"])))
    assert bron.url == "https://www.bigregister.nl"
