#!/usr/bin/env python3
"""Genereert een landingspagina per verzenddomein.

Waarom dit bestaat
------------------
De vijf outreach-domeinen wezen allemaal naar 192.0.2.1 — een adres dat RFC 5737
reserveert voor documentatie en dat niet routeert. Ze hadden dus geen website.
Consumentenfilters van Gmail en Outlook.com wegen dat zwaar mee: een jong domein
zonder bereikbare site dat koude mail stuurt is de vingerafdruk van een
wegwerp-spamdomein. Dat verklaarde 0% inbox bij consumenten tegenover 100% bij
zakelijke tenants.

Uitgangspunten
--------------
1. Eerlijk. Elke pagina zegt dat dit Elyon is en linkt naar tryelyon.com.
   Vijf pagina's die doen alsof ze vijf bedrijven zijn is misleiding, en
   filtervendors herkennen dat patroon toch.
2. Niet identiek. Vijf keer exact dezelfde HTML op vijf domeinen is zelf een
   signaal. Elke variant heeft een eigen invalshoek en eigen tekst.
3. Echt. Een privacyverklaring, contactgegevens, een afmeldroute en een uitleg
   waarom iemand die mail kreeg. Dat is wat een filter — en een prospect die
   doorklikt — verwacht te zien.

Draaien:  python build.py
Output:   dist/<domein>/
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

HIER = Path(__file__).resolve().parent
DIST = HIER / "dist"

# ── Bedrijfsgegevens ────────────────────────────────────────────────────────
# LET OP: deze staan bewust als placeholder. Ze staan ook nog zo op je
# hoofdsite. Vul ze in vóór je deployt — zonder identificeerbare
# bedrijfsgegevens mis je zowel het vertrouwenssignaal als de wettelijke
# verplichting (art. 3:15d BW).
BEDRIJF = {
    "naam": "Elyon",
    "hoofdsite": "https://tryelyon.com",
    "adres": "[ADRES]",
    "kvk": "[KVK]",
    "email": "[E-MAILADRES]",
}

JAAR = date.today().year
BIJGEWERKT = date.today().strftime("%B %Y")

# ── Per domein een eigen invalshoek ─────────────────────────────────────────
DOMEINEN = {
    "useelyon.com": {
        "kicker": "AI-medewerkers",
        "titel": "Je telefoon wordt altijd opgenomen",
        "intro": (
            "Elyon bouwt AI-medewerkers die je telefoon aannemen, klanten te woord staan, "
            "afspraken inplannen en leads opvolgen. Wij richten alles in en blijven het "
            "verbeteren — jij merkt alleen dat er niets meer blijft liggen."
        ),
        "punten": [
            "Neemt op tijdens gesprekken, in de auto en buiten kantooruren",
            "Verbindt door naar de juiste collega of plant direct een afspraak",
            "Stuurt na elk gesprek een samenvatting naar je inbox",
        ],
        "meta": "Elyon bouwt AI-medewerkers voor telefoon en klantcontact. Wij richten alles in.",
    },
    "withelyon.com": {
        "kicker": "Samenwerken",
        "titel": "Wat een AI-medewerker voor je team doet",
        "intro": (
            "Elyon werkt met bedrijven die meer telefoontjes krijgen dan ze kunnen "
            "aannemen. Geen software die je zelf moet uitzoeken: wij bouwen de "
            "AI-medewerker, trainen hem op jouw manier van werken en beheren hem daarna."
        ),
        "punten": [
            "Wij richten in, trainen en verbeteren — jij houdt de controle",
            "Werkt naast je team, niet in plaats van je team",
            "Live binnen enkele werkdagen",
        ],
        "meta": "Elyon bouwt en beheert AI-medewerkers voor bedrijven die telefoontjes missen.",
    },
    "meetelyon.com": {
        "kicker": "Kennismaken",
        "titel": "Maak kennis met Elyon",
        "intro": (
            "Wij bouwen AI-medewerkers voor sales, support en klantcontact — op de "
            "kanalen waar je klanten al zitten: telefoon, WhatsApp, Instagram en "
            "Messenger. Actief in Nederland en Latijns-Amerika."
        ),
        "punten": [
            "Telefoon, WhatsApp, Instagram en Messenger in één",
            "Vloeiend Nederlands, 24 uur per dag",
            "Je hoort zelf hoe het klinkt voordat je iets beslist",
        ],
        "meta": "Maak kennis met Elyon: AI-medewerkers voor telefoon, WhatsApp en klantcontact.",
    },
    "heyelyon.com": {
        "kicker": "Even voorstellen",
        "titel": "Hoeveel telefoontjes mist je bedrijf?",
        "intro": (
            "Een groot deel van de telefoontjes naar kleinere bedrijven wordt nooit "
            "door een mens opgenomen. Elyon bouwt AI-medewerkers die dat gat dichten: "
            "ze nemen op, helpen de beller verder en zetten de afspraak in je agenda."
        ),
        "punten": [
            "Elke beller krijgt antwoord, ook als iedereen bezet is",
            "Geen keuzemenu's — gewoon een gesprek",
            "Je ziet per gesprek wat er is besproken",
        ],
        "meta": "Elyon bouwt AI-medewerkers die opnemen wanneer jij dat niet kunt.",
    },
    "goelyon.com": {
        "kicker": "Aan de slag",
        "titel": "Van eerste gesprek naar live in dagen",
        "intro": (
            "Elyon bouwt AI-medewerkers voor telefoon en klantcontact. We beginnen met "
            "een kort gesprek over hoe jullie nu bellen, bouwen daarna de medewerker, "
            "en zetten hem live zodra je tevreden bent over hoe hij klinkt."
        ),
        "punten": [
            "Eerst horen hoe het klinkt, dan pas beslissen",
            "Wij doen de inrichting en de training",
            "Aanpassen kan altijd, ook nadat hij live staat",
        ],
        "meta": "Elyon bouwt AI-medewerkers voor telefoon en klantcontact. Live binnen dagen.",
    },
}

# ── Gedeelde stijl (overgenomen van tryelyon.com) ───────────────────────────
STIJL = """
:root{
  --bg:#efede6;--surface:#e6e3da;--ink:#131316;--ink-soft:#50505a;
  --accent:#2038e6;--accent-dark:#1a2cb8;--rule:#131316;--phone:#1e7a46;
  --disp:'Martian Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --body:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  background:var(--bg);color:var(--ink);font-family:var(--body);
  font-size:15.5px;line-height:1.65;-webkit-font-smoothing:antialiased;
  background-image:
    linear-gradient(rgba(32,56,230,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(32,56,230,.05) 1px,transparent 1px);
  background-size:34px 34px;
}
a{color:inherit}
::selection{background:var(--accent);color:var(--bg)}
:focus-visible{outline:2.5px solid var(--accent);outline-offset:3px}
img,svg{max-width:100%}
.wrap{max-width:1100px;margin:0 auto;padding:clamp(44px,6vw,80px) clamp(18px,4vw,28px)}
h1,h2,h3{font-family:var(--disp);letter-spacing:-.02em;line-height:1.14}
h1,h2{font-weight:800;text-transform:uppercase}
h1{font-size:clamp(1.45rem,4.4vw,2.5rem);max-width:24ch}
h2{font-size:clamp(1.1rem,2.6vw,1.6rem)}
h3{font-size:.98rem;font-weight:800;text-transform:uppercase}
p{max-width:64ch}
.kicker{display:inline-block;font-family:var(--disp);font-size:.66rem;font-weight:700;
  letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:1rem}
.sub{color:var(--ink-soft);margin-top:.9rem}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.55rem;
  font-family:var(--disp);font-weight:700;font-size:.74rem;letter-spacing:.06em;
  text-transform:uppercase;text-decoration:none;cursor:pointer;
  padding:.95rem 1.5rem;border:1.5px solid var(--rule);background:transparent;color:var(--ink);
  transition:background .15s,color .15s,border-color .15s,transform .1s}
.btn:active{transform:translateY(1px)}
.btn:hover{background:var(--ink);color:var(--bg)}
.btn-primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-dark);border-color:var(--accent-dark)}
.topbar{border-bottom:1.5px solid var(--rule);background:var(--bg);display:flex;
  align-items:center;justify-content:space-between;gap:1rem;min-height:56px;
  padding:.6rem clamp(16px,4vw,28px)}
.brand{display:flex;align-items:center;gap:.6rem;text-decoration:none;
  font-family:var(--disp);font-weight:800;font-size:.95rem;letter-spacing:.04em}
.brand svg{width:20px;height:20px;display:block}
.toplinks{display:flex;gap:.9rem;font-size:.7rem;font-family:var(--disp);
  font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.toplinks a{text-decoration:none;color:var(--ink-soft)}
.toplinks a:hover{color:var(--accent)}
.hero{border-bottom:1.5px solid var(--rule)}
.cta-row{display:flex;flex-wrap:wrap;gap:.8rem;margin-top:1.8rem}
@media (max-width:560px){.cta-row{flex-direction:column}.cta-row .btn{width:100%}}
.lijst{list-style:none;margin-top:1.4rem;display:flex;flex-direction:column;gap:.5rem}
.lijst li{display:flex;gap:.6rem;align-items:flex-start;font-size:.94rem;max-width:60ch}
.lijst li::before{content:"\\2713";color:var(--phone);font-weight:700;flex:none}
.sec-alt{background:var(--surface);border-top:1.5px solid var(--rule)}
.kaart{background:var(--bg);border:1.5px solid var(--rule);padding:clamp(20px,3vw,30px)}
.duo{display:grid;grid-template-columns:1fr;gap:16px;margin-top:1.6rem}
@media (min-width:820px){.duo{grid-template-columns:1fr 1fr}}
.duo p{font-size:.92rem;color:var(--ink-soft);margin-top:.5rem}
dl{margin-top:1rem;font-size:.92rem}
dt{font-family:var(--disp);font-weight:700;font-size:.68rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink-soft);margin-top:.9rem}
dd{margin-top:.15rem}
footer{border-top:1.5px solid var(--rule);background:var(--surface);
  padding:2.2rem clamp(18px,4vw,28px);text-align:center;font-size:.85rem;color:var(--ink-soft)}
footer a{color:var(--accent)}
.flinks{display:flex;flex-wrap:wrap;gap:.4rem 1.4rem;justify-content:center;margin-top:.9rem}
.fsmall{margin-top:.7rem;font-size:.78rem}
.prose h2{margin-top:2rem}
.prose p,.prose li{color:var(--ink-soft);margin-top:.7rem}
.prose ul{margin-top:.5rem;padding-left:1.1rem}
"""

LOGO = (
    '<svg viewBox="-20 -20 100 100" aria-hidden="true">'
    '<rect x="0" y="0" width="13" height="60" fill="#131316"/>'
    '<rect x="0" y="0" width="60" height="13" fill="#2038E6"/>'
    '<rect x="0" y="23.5" width="47" height="13" fill="#131316"/>'
    '<rect x="0" y="47" width="34" height="13" fill="#131316"/></svg>'
)


def kop(domein: str, titel: str, omschrijving: str, pad: str = "/") -> str:
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titel}</title>
<meta name="description" content="{omschrijving}">
<link rel="canonical" href="https://{domein}{pad}">
<meta property="og:type" content="website">
<meta property="og:title" content="{titel}">
<meta property="og:description" content="{omschrijving}">
<meta property="og:url" content="https://{domein}{pad}">
<meta property="og:locale" content="nl_NL">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Martian+Mono:wght@700;800&display=swap" rel="stylesheet">
<style>{STIJL}</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="/" aria-label="{BEDRIJF['naam']}">{LOGO}{BEDRIJF['naam'].upper()}</a>
  <nav class="toplinks" aria-label="Site">
    <a href="/privacy/">Privacy</a>
    <a href="{BEDRIJF['hoofdsite']}/nl/">Hoofdsite</a>
  </nav>
</header>
"""


def voet(domein: str) -> str:
    return f"""
<footer>
  <div><strong>{BEDRIJF['naam']}</strong> &middot; {BEDRIJF['adres']} &middot; KvK {BEDRIJF['kvk']}</div>
  <div class="flinks">
    <a href="{BEDRIJF['hoofdsite']}/nl/">tryelyon.com</a>
    <a href="/privacy/">Privacyverklaring</a>
    <a href="mailto:{BEDRIJF['email']}">{BEDRIJF['email']}</a>
  </div>
  <div class="fsmall">
    {domein} is een verzenddomein van {BEDRIJF['naam']}. &copy; {JAAR}
  </div>
</footer>
</body>
</html>
"""


def index_pagina(domein: str, cfg: dict) -> str:
    punten = "\n".join(f"      <li>{p}</li>" for p in cfg["punten"])
    schema = (
        '{"@context":"https://schema.org","@type":"Organization",'
        f'"name":"{BEDRIJF["naam"]}","url":"{BEDRIJF["hoofdsite"]}",'
        f'"sameAs":["https://{domein}"],'
        '"description":"AI-medewerkers voor sales, support en klantcontact.",'
        '"areaServed":["NL","MX"]}'
    )
    return (
        kop(domein, f"{BEDRIJF['naam']} | {cfg['titel']}", cfg["meta"])
        + f"""
<script type="application/ld+json">{schema}</script>

<main>
  <section class="hero">
    <div class="wrap">
      <span class="kicker">{cfg['kicker']}</span>
      <h1>{cfg['titel']}</h1>
      <p class="sub">{cfg['intro']}</p>
      <ul class="lijst">
{punten}
      </ul>
      <div class="cta-row">
        <a class="btn btn-primary" href="{BEDRIJF['hoofdsite']}/nl/">Bekijk wat we doen</a>
        <a class="btn" href="mailto:{BEDRIJF['email']}">Stel een vraag</a>
      </div>
    </div>
  </section>

  <section class="sec-alt">
    <div class="wrap">
      <h2>Kreeg je een mail van dit domein?</h2>
      <p class="sub">
        Dan hebben wij je zakelijk benaderd omdat we denken dat een AI-medewerker
        jullie telefoon rustiger maakt. We gebruiken {domein} als verzenddomein
        naast onze hoofdsite {BEDRIJF['hoofdsite'].replace('https://', '')}.
      </p>
      <div class="duo">
        <div class="kaart">
          <h3>Liever geen mail meer</h3>
          <p>
            Antwoord met &ldquo;afmelden&rdquo; of gebruik de afmeldlink onderaan de mail.
            We verwerken dat direct en je hoort niets meer van ons &mdash; ook niet
            vanaf een van onze andere domeinen.
          </p>
        </div>
        <div class="kaart">
          <h3>Waar komen je gegevens vandaan</h3>
          <p>
            Uit openbare zakelijke bronnen: je website, het Handelsregister en
            openbare bedrijvenoverzichten. Nooit uit gekochte privélijsten.
            Wat we bewaren en hoe lang staat in onze
            <a href="/privacy/">privacyverklaring</a>.
          </p>
        </div>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>Contact</h2>
      <dl>
        <dt>Bedrijf</dt><dd>{BEDRIJF['naam']}</dd>
        <dt>E-mail</dt><dd><a href="mailto:{BEDRIJF['email']}">{BEDRIJF['email']}</a></dd>
        <dt>Adres</dt><dd>{BEDRIJF['adres']}</dd>
        <dt>KvK</dt><dd>{BEDRIJF['kvk']}</dd>
        <dt>Hoofdsite</dt>
        <dd><a href="{BEDRIJF['hoofdsite']}/nl/">{BEDRIJF['hoofdsite'].replace('https://', '')}</a></dd>
      </dl>
    </div>
  </section>
</main>
"""
        + voet(domein)
    )


def privacy_pagina(domein: str) -> str:
    return (
        kop(
            domein,
            f"Privacyverklaring | {BEDRIJF['naam']}",
            f"Hoe {BEDRIJF['naam']} omgaat met persoonsgegevens bij zakelijke benadering via {domein}.",
            "/privacy/",
        )
        + f"""
<main>
  <div class="wrap prose">
    <span class="kicker">Privacy</span>
    <h1>Privacyverklaring</h1>
    <p>
      {BEDRIJF['naam']} &middot; {BEDRIJF['adres']} &middot; KvK {BEDRIJF['kvk']}
      &middot; Laatst bijgewerkt: {BIJGEWERKT}
    </p>

    <h2>Waarvoor dit domein wordt gebruikt</h2>
    <p>
      Wij gebruiken {domein} om bedrijven zakelijk te benaderen. Onze hoofdsite is
      <a href="{BEDRIJF['hoofdsite']}/nl/">{BEDRIJF['hoofdsite'].replace('https://', '')}</a>.
      Deze verklaring gaat over de gegevens die wij in dat kader verwerken.
    </p>

    <h2>Welke gegevens wij verwerken</h2>
    <ul>
      <li>Zakelijke contactgegevens: bedrijfsnaam, naam en functie van de contactpersoon,
        zakelijk e-mailadres en zakelijk telefoonnummer.</li>
      <li>Bedrijfsgegevens uit openbare bronnen: website, vestigingsplaats, branche en
        KvK-nummer.</li>
      <li>Of je onze mail hebt geopend of beantwoord, en of je je hebt afgemeld.</li>
    </ul>

    <h2>Waar wij die gegevens vandaan halen</h2>
    <p>
      Uitsluitend uit openbaar toegankelijke zakelijke bronnen: bedrijfswebsites, het
      Handelsregister van de Kamer van Koophandel, ledenlijsten van branchverenigingen
      en openbare bedrijvenoverzichten. Wij kopen geen privélijsten en verzamelen geen
      gegevens uit besloten omgevingen.
    </p>

    <h2>Grondslag</h2>
    <p>
      Gerechtvaardigd belang (artikel 6 lid 1 sub f AVG): het benaderen van zakelijke
      contactpersonen in hun beroepsrol voor een aanbod dat op hun werk aansluit. Wij
      wegen daarbij jouw belang mee en beperken ons tot zakelijke gegevens.
    </p>

    <h2>Bewaartermijn</h2>
    <p>
      Reageer je niet, dan verwijderen wij je gegevens binnen twaalf maanden. Meld je je
      af, dan bewaren wij uitsluitend je e-mailadres op een uitsluitlijst, zodat wij je
      niet opnieuw benaderen. Die lijst geldt voor al onze verzenddomeinen.
    </p>

    <h2>Afmelden</h2>
    <p>
      Elke mail bevat een afmeldlink. Je kunt ook antwoorden met &ldquo;afmelden&rdquo; of
      mailen naar <a href="mailto:{BEDRIJF['email']}">{BEDRIJF['email']}</a>. Wij
      verwerken dat direct.
    </p>

    <h2>Je rechten</h2>
    <p>
      Je hebt recht op inzage, correctie, verwijdering, beperking en bezwaar, en op
      overdracht van je gegevens. Stuur je verzoek naar
      <a href="mailto:{BEDRIJF['email']}">{BEDRIJF['email']}</a>; wij reageren binnen
      vier weken. Je kunt ook een klacht indienen bij de Autoriteit Persoonsgegevens.
    </p>

    <h2>Delen met anderen</h2>
    <p>
      Wij verkopen je gegevens niet. Wij delen ze alleen met leveranciers die ons helpen
      bij het versturen en beheren van e-mail, en uitsluitend op basis van een
      verwerkersovereenkomst.
    </p>

    <h2>Cookies</h2>
    <p>
      Deze pagina plaatst geen tracking- of advertentiecookies.
    </p>

    <h2>Contact</h2>
    <p>
      {BEDRIJF['naam']} &middot; {BEDRIJF['adres']} &middot; KvK {BEDRIJF['kvk']} &middot;
      <a href="mailto:{BEDRIJF['email']}">{BEDRIJF['email']}</a>
    </p>
  </div>
</main>
"""
        + voet(domein)
    )


def robots(domein: str) -> str:
    # Bewust indexeerbaar: een pagina op noindex ziet eruit als een doorway page.
    return f"""User-agent: *
Allow: /

Sitemap: https://{domein}/sitemap.xml
"""


def sitemap(domein: str) -> str:
    vandaag = date.today().isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://{domein}/</loc><lastmod>{vandaag}</lastmod><priority>1.0</priority></url>
  <url><loc>https://{domein}/privacy/</loc><lastmod>{vandaag}</lastmod><priority>0.5</priority></url>
</urlset>
"""


NETLIFY = """[build]
  publish = "."

[[headers]]
  for = "/*"
  [headers.values]
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "SAMEORIGIN"
    Referrer-Policy = "strict-origin-when-cross-origin"
"""


def bouw() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)

    for domein, cfg in DOMEINEN.items():
        doel = DIST / domein
        (doel / "privacy").mkdir(parents=True, exist_ok=True)

        (doel / "index.html").write_text(index_pagina(domein, cfg), encoding="utf-8")
        (doel / "privacy" / "index.html").write_text(privacy_pagina(domein), encoding="utf-8")
        (doel / "robots.txt").write_text(robots(domein), encoding="utf-8")
        (doel / "sitemap.xml").write_text(sitemap(domein), encoding="utf-8")
        (doel / "netlify.toml").write_text(NETLIFY, encoding="utf-8")

        print(f"  {domein:<18} -> {doel.relative_to(HIER)}")

    ontbreekt = [k for k, v in BEDRIJF.items() if v.startswith("[")]
    print(f"\n{len(DOMEINEN)} sites gebouwd in {DIST.relative_to(HIER)}/")
    if ontbreekt:
        print(f"\n  LET OP: nog niet ingevuld: {', '.join(ontbreekt)}")
        print("  Pas BEDRIJF bovenin dit bestand aan en draai opnieuw.")


if __name__ == "__main__":
    bouw()
