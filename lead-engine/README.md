# lead-engine

Leadmotor voor de **Nederlandse markt**. Je geeft een ICP of een website op, de
motor zoekt uit waar die doelgroep online openbaar samenkomt ("catalyst
databases"), oogst daar contactgegevens en levert per bron een campagneklare CSV.

Gebouwd rond één idee: *waar* iemand gevonden wordt is zelf een koopsignaal.
Een tandarts die op de KNMT-ledenlijst staat is iets anders dan een rij uit een
gekochte database — en verdient dus een andere mail.

---

## Snel starten

```bash
cd lead-engine
python -m pip install -r requirements.txt
cp .env.example .env          # niets invullen mag; keys maken 'm alleen beter
python -m leadengine status   # laat zien wat aanstaat én wat je mist
```

Wil je meteen goede resultaten: zet één key, `GEMINI_API_KEY`
([gratis](https://aistudio.google.com/apikey)). Daarmee wordt het ICP scherp én
zoekt de motor je bronnen via Google Search grounding op — zie hieronder.

Eerste run:

```bash
python -m leadengine zoek --icp "installatiebedrijven met 5-30 man in Noord-Brabant"
```

Of laat het ICP afleiden uit een bestaande website:

```bash
python -m leadengine zoek --website https://tryelyon.com
```

---

## Wat je terugkrijgt

Alles komt in `uitvoer/<datum>_<label>/`:

| Bestand | Wat het is |
|---|---|
| `overzicht.csv` | **Begin hier.** Volume per segment: hoeveel leads, hoeveel met e-mail, gemiddelde score |
| `segmenten/*.csv` | Eén bestand per catalyst database — dit is één campagne |
| `instantly/*.csv` | Kale kolommen, direct te importeren in Instantly/Smartlead |
| `leads_alle.csv` | Alles bij elkaar, gesorteerd op score |
| `afgewezen_buiten_icp.csv` | Wat het relevantiefilter tegenhield — check dit als je te weinig leads hebt |
| `bronnen.csv` | Je complete bronnenlijst, inclusief de handmatige |
| `handmatige_bronnen.md` | Recepten voor LinkedIn/Facebook/Skool |
| `icp.json` | Het vastgestelde ICP — hergebruiken met `--icp-bestand` |
| `AVG_verwerkingsnotitie.md` | Je verantwoording, bewaar dit bij het leadbestand |

---

## Hoe het werkt

```
ICP (tekst of website)
   ↓  het model leidt branches, functietitels, regio's en koopsignalen af
Bronnen ontdekken  ── 3 lagen ──────────────────────────────────
   1. Statisch NL-register    bronnen/nl_register.yaml (KvK, Bovag, KNMT, …)
   2. Gemini + Google Search  het model zoekt écht op Google en levert
      grounding                bronnen mét geverifieerde URL  ← beste laag
      (of, zonder Gemini: het model bedenkt bronnen uit zijn geheugen)
   3. Live SERP-ontdekking    25 NL-zoekopdrachten naar lijstpagina's
   ↓
Oogsten per bron   ── connectors ───────────────────────────────
   listing        ledenlijst → profielpagina's → bedrijfssites
   website        bedrijfssite → contact/team/over-ons → gegevens
   google_places  NL-steden × branchetermen (beste bron voor lokaal MKB)
   kvk            Handelsregister op naam + plaats
   youtube        videobeschrijvingen → websites van gasten
   apollo         B2B-contacten op functietitel
   podcast        RSS-feeds → eigenaars-e-mailadres
   ↓
Verrijken   Hunter vult ontbrekende e-mails · MX + syntax · ZeroBounce
Filteren    ICP-relevantie · uitsluitlijst · ongeldige adressen
Ontdubbelen e-mail > telefoon > domein · fuzzy op naam · max N per bedrijf
Scoren      0-100 op bereikbaarheid, persoonsniveau en ICP-fit
   ↓
CSV per segment
```

---

## Google Search grounding (de aanbevolen opzet)

De zwakste schakel in elke leadscraper is bronontdekking: een taalmodel dat uit
zijn geheugen ledenlijsten opnoemt, verzint met enige regelmaat URL's die nooit
hebben bestaan. Gemini's **Google Search grounding** lost dat op — het model
zoekt eerst écht op Google.nl en antwoordt op basis van wat het daar vond, met
de gebruikte pagina's als bijlage.

De motor gebruikt dat op twee manieren:

1. **Bronontdekking.** Gemini krijgt je ICP en zoekt zelf de Nederlandse
   ledenlijsten, registers en exposantenlijsten op. De URL's die eruit komen
   zijn geverifieerd, en de pagina's die het model daadwerkelijk las worden
   zelf óók kandidaat-bronnen.
2. **Zoekmachine.** Heb je geen aparte zoek-key, dan kan Gemini als
   zoekmachine dienen (`LEADENGINE_SEARCH_PROVIDER=gemini`).

Aanzetten kost één regel — een key haal je gratis op
[aistudio.google.com/apikey](https://aistudio.google.com/apikey):

```bash
GEMINI_API_KEY=...
```

Staat Gemini aan, dan slaat de motor de "bedenk bronnen uit je geheugen"-laag
over: die levert dezelfde soort bronnen maar zonder geverifieerde URL.

### De ideale Google-opzet

Alle drie mogen dezelfde Google Cloud-key zijn, mits je per API de juiste
service aanzet in de console:

```bash
GEMINI_API_KEY=...            # bronontdekking mét grounding + ICP-analyse
GOOGLE_CSE_KEY=...            # echte Google-resultaten (100 queries/dag gratis)
GOOGLE_CSE_CX=...             #   engine met "Zoek op het hele web" AAN
GOOGLE_PLACES_API_KEY=...     # lokale NL-bedrijven met telefoon en reviews
```

---

## API-keys

Niets is verplicht. Zonder keys draait de motor op DuckDuckGo + website-crawl.
Elke key zet extra bronnen aan — `python -m leadengine status` laat de stand
zien én vertelt wat je mist.

| Key | Wat het toevoegt | Prioriteit |
|---|---|---|
| `GEMINI_API_KEY` | Scherp ICP + **bronnen met geverifieerde URL's** via Google Search | ⭐ begin hier |
| `GOOGLE_PLACES_API_KEY` | **Lokale NL-bedrijven** met telefoon, adres en reviews | ⭐ bij lokaal MKB |
| `GOOGLE_CSE_KEY` + `_CX` | Echte Google-resultaten voor bronontdekking | hoog |
| `HUNTER_API_KEY` | Vult ontbrekende e-mails aan per domein | hoog |
| `SERPER_API_KEY` | Alternatief voor Google CSE, geen dagquotum | midden |
| `KVK_API_KEY` | Officiële bedrijfsgegevens + KvK-nummers | midden |
| `APOLLO_API_KEY` | Contacten op functietitel (dekt de LinkedIn-behoefte) | midden |
| `ZEROBOUNCE_API_KEY` | Echte mailboxvalidatie vóór verzenden | midden |
| `ANTHROPIC_API_KEY` | Alternatief voor Gemini (geen grounding) | optioneel |
| `YOUTUBE_API_KEY` | Gasten uit NL-vakpodcasts en interviews | laag |

Provider forceren als je meerdere keys hebt:

```bash
LEADENGINE_LLM_PROVIDER=gemini        # of: anthropic, auto
LEADENGINE_SEARCH_PROVIDER=google_cse # of: serper, brave, gemini, duckduckgo
GEMINI_MODEL=gemini-2.5-flash         # zwaarder model? zet 'm hier
```

> **Zoek je lokale bedrijven** (kappers, garages, praktijken, horeca, klusbedrijven)?
> Zet dan `GOOGLE_PLACES_API_KEY`. Zonder die key kan de motor wel de gidsen en
> ledenlijsten vinden, maar veel van die gidsen linken alleen naar hun eigen
> overzichtspagina's — je krijgt dan aggregators terug in plaats van de
> individuele bedrijven. Places lost dat in één klap op.

---

## Alle commando's

```bash
# Volledige run
python -m leadengine zoek --icp "tandartspraktijken Randstad"

# Alleen de bronnenlijst (snel, geen oogst) — handig om je ICP te toetsen
python -m leadengine bronnen --icp "tandartspraktijken Randstad"

# Eigen lijst bedrijven verrijken (Sales Navigator-export, beursdeelnemers, …)
python -m leadengine importeer mijn_lijst.csv --bron "LinkedIn SN"

# Welke bronnen staan aan?
python -m leadengine status
```

Nuttige vlaggen bij `zoek`:

| Vlag | Standaard | Waarvoor |
|---|---|---|
| `--max-bronnen` | 40 | Meer bronnen = meer segmenten = meer campagnes |
| `--max-bedrijven` | 60 | Bedrijven per bron |
| `--max-paginas` | 3 | Hoe diep in de paginering van een ledenlijst |
| `--max-per-domein` | 3 | Voorkomt dat één groot bedrijf je campagne overneemt |
| `--min-relevantie` | 30 | ICP-strengheid. **Te weinig leads? Zet 'm op 0** |
| `--min-score` | 0 | Filtert zwakke leads uit de export |
| `--icp-bestand` | — | Hergebruik een eerder `icp.json` |
| `--diep-valideren` | uit | ZeroBounce-validatie (kost credits) |

---

## Wat deze tool bewust niet doet

Geen geautomatiseerd scrapen van **LinkedIn, Facebook, Instagram, Discord of
Skool**. Dat schendt hun voorwaarden en levert persoonsgegevens op die niet als
zakelijk contactgegeven bedoeld zijn — precies het soort data waar de AP op
handhaaft.

Die platforms verdwijnen niet uit je strategie: ze komen op je bronnenlijst
terecht met oogstmodus `handmatig` en een concreet recept in
`handmatige_bronnen.md`. Wat je daar handmatig uit haalt (bedrijfsnamen,
websites) voer je terug met `leadengine importeer` — de motor haalt de zakelijke
contactgegevens dan van hun eigen website. Voor de LinkedIn-populatie zelf is de
Apollo-connector de legale route.

De motor respecteert `robots.txt`, houdt 1,5 seconde tussen requests per domein
aan en identificeert zichzelf in de User-Agent. Pas dat aan in `.env`.

---

## AVG in het kort

Elke run schrijft een `AVG_verwerkingsnotitie.md`. Drie dingen die je zelf moet
regelen vóór de eerste mail:

1. **Afmeldlink in elke mail** (art. 11.7 Telecommunicatiewet) — één klik, geen inlog.
2. **Afzender identificeren**: bedrijfsnaam, adres en KvK-nummer in de voettekst.
3. **Afmeldingen direct in `uitsluitlijst.txt`** — die filtert de motor bij elke
   volgende run automatisch weg.

---

## Bronnenregister uitbreiden

`bronnen/nl_register.yaml` is gewoon tekst. Ken je een goede NL-ledenlijst voor
jouw markt? Zet 'm erin:

```yaml
  - naam: Vereniging van Hoveniers
    type: branchevereniging
    url: https://www.vhg.org/leden
    site_zoek: vhg.org        # laat de zoekmachine de echte lijstpagina vinden
    connector: listing
    oogstmodus: auto
    prioriteit: 1
    trefwoorden: [hovenier, tuin, groenvoorziening]
    signaal: "Lidmaatschap kost geld = bedrijf met personeel, geen zzp'er"
```

`trefwoorden` bepaalt wanneer de bron meedoet: alleen als je ICP erop matcht.
Laat het veld leeg om de bron altijd mee te nemen.

---

## Tests

```bash
python -m pytest tests/ -q
```

36 tests: de extractielaag (e-mail, telefoon, namen, obfuscatie, JSON-LD), het
ICP-relevantiefilter, de bronfiltering en de Gemini-laag (request-vorm en
grounding-verwerking, met gemockte API-responses — geen key nodig).
