"""Tests voor de extractielaag. Draaien: python -m pytest tests/ -q"""

from leadengine import extract
from leadengine.regions import bepaal_provincie

VOORBEELD_HTML = """
<html><head><title>Tandartspraktijk De Molen | Utrecht</title>
<script type="application/ld+json">
{"@type":"Dentist","name":"Tandartspraktijk De Molen",
 "telephone":"+31 30 123 45 67","email":"info@demolen-tandarts.nl",
 "address":{"@type":"PostalAddress","streetAddress":"Molenweg 12",
            "postalCode":"3512 AB","addressLocality":"Utrecht"},
 "sameAs":["https://www.linkedin.com/company/demolen"]}
</script></head>
<body>
  <div class="team-member">
    <h3>Jan van der Berg</h3>
    <p>Praktijkhouder &amp; tandarts</p>
    <a href="mailto:j.vandenberg@demolen-tandarts.nl">mail</a>
  </div>
  <div class="team-member">
    <h3>Sanne Bakker</h3><p>Praktijkmanager</p>
  </div>
  <p>Bereikbaar via sanne [at] demolen-tandarts punt nl of bel 06-12345678.</p>
  <p>KvK: 12345678 — BTW NL123456789B01</p>
  <a href="/contact">Contact</a><a href="/over-ons">Over ons</a>
</body></html>
"""


def test_jsonld_en_basis():
    cg = extract.extraheer(VOORBEELD_HTML, "https://demolen-tandarts.nl")
    assert cg.bedrijfsnaam == "Tandartspraktijk De Molen"
    assert cg.postcode == "3512 AB"
    assert cg.plaats == "Utrecht"
    assert cg.kvk_nummer == "12345678"
    assert cg.btw_nummer == "NL123456789B01"
    assert "linkedin.com/company/demolen" in cg.linkedin


def test_emails_inclusief_obfuscatie():
    cg = extract.extraheer(VOORBEELD_HTML, "https://demolen-tandarts.nl")
    assert "info@demolen-tandarts.nl" in cg.emails
    assert "j.vandenberg@demolen-tandarts.nl" in cg.emails
    assert "sanne@demolen-tandarts.nl" in cg.emails      # "[at]" + "punt" gedecodeerd


def test_telefoons_genormaliseerd():
    cg = extract.extraheer(VOORBEELD_HTML, "https://demolen-tandarts.nl")
    assert "+31301234567" in cg.telefoons
    assert "+31612345678" in cg.telefoons


def test_personen_met_functie():
    cg = extract.extraheer(VOORBEELD_HTML, "https://demolen-tandarts.nl")
    namen = {p["naam"] for p in cg.personen}
    assert "Jan van der Berg" in namen
    assert "Sanne Bakker" in namen


def test_telefoon_types():
    assert extract.normaliseer_telefoon("06-12345678") == ("+31612345678", "mobiel")
    assert extract.normaliseer_telefoon("020 123 4567")[1] == "vast"
    assert extract.normaliseer_telefoon("+31 (0)30 1234567")[0] == "+31301234567"
    assert extract.normaliseer_telefoon("0032 2 123 4567") == ("", "")   # BE -> weg
    assert extract.normaliseer_telefoon("12345") == ("", "")


def test_email_typering():
    assert extract.email_type("info@bedrijf.nl") == "algemeen"
    assert extract.email_type("sales@bedrijf.nl") == "rol"
    assert extract.email_type("jan.devries@bedrijf.nl") == "persoonlijk"
    assert extract.email_type("j.devries@bedrijf.nl") == "persoonlijk"


def test_rol_adressen_zijn_geen_personen():
    """De duurste bug die deze tool kan maken: "Hoi Betalingen," de deur uit."""
    for adres in [
        "betalingen@bedrijf.nl", "webredactie@bedrijf.nl", "lotgenoten@bedrijf.nl",
        "ledenadministratie@bedrijf.nl", "meldpunt@bedrijf.nl", "redactie@bedrijf.nl",
        "ervaringsdeskundigen@bedrijf.nl", "facturen@bedrijf.nl", "planning@bedrijf.nl",
        "reserveringen@bedrijf.nl", "administratie2024@bedrijf.nl",
    ]:
        assert extract.email_type(adres) == "rol", adres


def test_onbekende_losse_woorden_niet_persoonlijk():
    assert extract.email_type("praktijkzwolle@bedrijf.nl") == "onbekend"
    assert extract.email_type("xyzabc@bedrijf.nl") == "onbekend"
    assert extract.email_type("sanne@bedrijf.nl") == "persoonlijk"
    assert extract.email_type("thijs@bedrijf.nl") == "persoonlijk"


def test_naam_uit_lokaaldeel():
    from leadengine.connectors.website import _naam_uit_lokaaldeel

    assert _naam_uit_lokaaldeel("jan.devries") == ("Jan", "Devries")
    assert _naam_uit_lokaaldeel("j.devries") == ("", "Devries")   # initiaal -> geen aanhef
    assert _naam_uit_lokaaldeel("sanne") == ("Sanne", "")
    assert _naam_uit_lokaaldeel("betalingen") == ("", "")


def test_troep_eruit():
    assert not extract.is_bruikbaar_email("logo@2x.png")
    assert not extract.is_bruikbaar_email("iets@sentry.wixpress.com")
    assert not extract.is_bruikbaar_email("naam@example.com")
    assert extract.is_bruikbaar_email("info@echtbedrijf.nl")


def test_naam_splitsen():
    assert extract.splits_naam("Jan van der Berg") == ("Jan", "van der Berg")
    assert extract.splits_naam("Sanne Bakker") == ("Sanne", "Bakker")
    assert extract.splits_naam("Kees") == ("Kees", "")


def test_domein_extractie():
    assert extract.registreerbaar_domein("https://www.sub.bedrijf.nl/pad") == "bedrijf.nl"
    assert extract.registreerbaar_domein("jan@bedrijf.co.uk") == "bedrijf.co.uk"


def test_interne_contactlinks():
    links = extract.interne_links(VOORBEELD_HTML, "https://demolen-tandarts.nl")
    assert any(l.endswith("/contact") for l in links)
    assert any(l.endswith("/over-ons") for l in links)


def test_provincie_afleiding():
    assert bepaal_provincie("3512 AB", "Utrecht") == "Utrecht"
    assert bepaal_provincie("1012 AB", "") == "Noord-Holland"
    assert bepaal_provincie("", "Eindhoven") == "Noord-Brabant"
