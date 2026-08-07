# Signaal

Gesloten-lus motor voor koude e-mail op basis van openbare signalen, gebouwd voor de
Nederlandse markt.

Nul afhankelijkheden. Alleen `node:http` en `node:sqlite`. Geen npm install, geen buildstap.

```sh
node signaal/seed.js --reset     # demodata
node signaal/server.js           # http://localhost:8787
```

Node 22 of hoger.

---

## Lees dit eerst

Dit systeem is gebaseerd op een Amerikaanse opzet. Bij het bouwen bleek dat de
belangrijkste aanname daarvan niet klopt voor Nederland, en dat verandert wat het
systeem kan zijn.

**Nederland kent geen algemeen opt-outregime voor zakelijke e-mail.** Sinds 1 oktober
2009 geldt het opt-invereiste van artikel 11.7 lid 1 Telecommunicatiewet ook voor
rechtspersonen. De enige uitzondering is lid 2, en dat is een cumulatieve toets van
drie delen die alle drie moeten kloppen:

1. de ontvanger is een rechtspersoon of handelt beroepsmatig, **en**
2. je gebruikt contactgegevens die de ontvanger **zelf daarvoor heeft bestemd en
   bekendgemaakt**, **en**
3. je gebruik past bij de doeleinden die de ontvanger aan die gegevens heeft verbonden.

"Bestemd en bekendgemaakt" is smaller dan "openbaar vindbaar". Een `info@` op een
contactpagina is bekendgemaakt voor algemeen contact, niet bestemd voor ongevraagde
aanbiedingen. Daarnaast geldt de AVG apart: voldoen aan 11.7 levert geen AVG-grondslag
op, en andersom.

Het gevolg is te zien op het tabblad AVG. Met de demodata halen 233 van 3.065 adressen
beide poorten, ongeveer 7,6 procent. Dat is rechtmatig bereik voor ongeveer 11 berichten
per dag, terwijl de verzendinfrastructuur 780 per dag aankan.

**Daarom staat de bereikberekening in dit systeem.** Bouw geen verzendcapaciteit voor
volume dat je niet rechtmatig kunt vullen. Als het bereik te laag is, is bijkopen van
domeinen niet de oplossing: het knelpunt zit dan in de bron van je adressen.

Dit is geen juridisch advies. Laat de opzet, de teksten en de afweging nakijken door
iemand die hierin gespecialiseerd is voordat er een campagne uitgaat.

---

## Wat het doet

| Tabblad | Waarvoor |
|---|---|
| Overzicht | De vier getallen die dagelijks tellen, plus de status van de koppelingen |
| Trechter | Conversie per stap, en waar repareren het meeste oplevert |
| Capaciteit | Maanddoel terugrekenen naar mailboxen en domeinen |
| Persona's | Gesloten lus: welk segment levert klanten op, niet reacties |
| Bronnen | Register van signaalbronnen met juridische status als slot |
| Domeinen | Bounce, klachten, reputatie, en wanneer een domein moet rusten |
| Kosten | Kosten per lead, reactie, afspraak en klant, in euro |
| AVG | De twee poorten, het rechtmatige bereik, en wat er wordt tegengehouden |

### Drie dingen die anders zijn dan in de oorspronkelijke opzet

**De trechter stuurt op impact, niet op het laagste percentage.** Een slechte conversie
bovenin een brede trechter is meer waard dan een slechte conversie onderin een smalle.
Het knelpunt wordt berekend als: hoeveel extra afspraken levert tien procentpunt
verbetering op deze stap op.

**Persona's worden gewogen op omzet, niet op reacties.** In de demodata heeft
"HR dienstverlening" het hoogste reactiepercentage en nul klanten. Sorteren op reacties
zet dat segment bovenaan, sorteren op wat het oplevert zet het op plek vier. Dat verschil
is het hele punt van de gesloten lus.

**Juridische status van een bron is een slot, geen notitieveld.** LinkedIn, Facebook en
Indeed verbieden geautomatiseerd ophalen in hun voorwaarden. Die bronnen staan op
`verboden` en kunnen niet op automatisch worden gezet, ook niet per ongeluk. Handmatig
invoeren van een signaal blijft mogelijk.

---

## Koppelingen

Zonder API-sleutel draait een koppeling in demostand en levert verzonnen data. Dat wordt
altijd zichtbaar gemarkeerd, in de balk bovenaan en per koppeling. Sleutels komen uit
omgevingsvariabelen, nooit uit de database of de broncode.

| Variabele | Waarvoor |
|---|---|
| `KVK_API_KEY` | KVK Handelsregister |
| `EXA_API_KEY` | Webzoeken voor persona-onderzoek |
| `INSTANTLY_API_KEY` | Verzendplatform |
| `MAILDOSO_API_KEY` | Domeinen en mailboxen |
| `TENDERNED_API_URL` | Publicatie-eindpunt TenderNed |

```sh
KVK_API_KEY=... EXA_API_KEY=... node signaal/server.js
```

Bestellingen van domeinen gaan nooit automatisch. Het systeem doet een voorstel dat een
mens bevestigt.

---

## Opbouw

```
signaal/
  server.js            HTTP-server en API, nul afhankelijkheden
  seed.js              demodata vullen
  lib/
    db.js              schema en migraties (node:sqlite)
    wetgeving.js       de twee poorten: Tw 11.7 en AVG, plus bereikberekening
    compliance.js      onderdrukking, verzoeken, bewaartermijn, accountcontroles
    capacity.js        maanddoel terugrekenen naar infrastructuur
    funnel.js          trechter en knelpuntberekening
    personas.js        gesloten lus op uitkomsten
    sources.js         bronregister met juridisch slot
    domains.js         domeingezondheid en rotatie
    costs.js           kosten per uitkomst
    adapters.js        externe koppelingen, met demostand
  public/              dashboard, geen framework
  data/                sqlite-bestand, niet in git
```

Database vervangen door Postgres of Supabase: alleen `lib/db.js` aanpassen. De rest van
de code praat uitsluitend via de functies daaruit met de database.

---

## Nog niet af

Eerlijk over wat ontbreekt, zodat je niet aanneemt dat het er wel is.

- **Geen scrapers.** De pijplijn die daadwerkelijk bronnen uitleest is er niet. De
  adapters staan klaar, het ophalen zelf moet nog gebouwd.
- **Geen antwoordverwerking.** Er is geen component die inkomende Nederlandse
  antwoorden leest en classificeert ("graag verwijderen", "geen interesse"). Bezwaar
  moet nu handmatig worden ingevoerd, en dat schaalt niet.
- **Geen afmeldpagina.** Elk verzenddomein hoort een werkende afmeldpagina, een
  privacyverklaring en een bezwaarroute te hosten. Dat staat er nog niet.
- **Frequentiebegrenzing niet afgedwongen.** Het verzendlogboek ligt klaar, maar er is
  nog geen harde limiet op het aantal koude aanrakingen per persoon.
- **Verwerkersovereenkomsten staan open.** Twee verwerkers in de demodata hebben er
  geen. De poort blokkeert daarop, en dat is de bedoeling.
- **Google Workspace en Microsoft 365 verbieden ongevraagde bulkmail in hun
  gebruiksvoorwaarden.** Als je daar mailboxen afneemt voor koude uitstroom, loop je
  het risico dat de accounts worden gesloten, los van wat de wet zegt.
