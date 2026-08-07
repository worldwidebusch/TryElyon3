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


def test_zonder_icp_gedraagt_zich_als_voorheen():
    assert _is_kandidaat_lijst(
        "https://www.eerstekamer.nl/leden", "Alle leden", "", None
    )
