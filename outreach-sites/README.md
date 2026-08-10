# outreach-sites

Landingspagina's voor de vijf verzenddomeinen: `useelyon.com`, `withelyon.com`,
`meetelyon.com`, `heyelyon.com`, `goelyon.com`.

## Waarom dit bestaat

Een inbox-placementtest liet dit patroon zien:

| | Consument | Zakelijk |
|---|---|---|
| Google | Gmail **0 / 125** | Workspace **125 / 125** |
| Microsoft | Outlook.com **0 / 125** | Outlook Workspace **125 / 125** |

Twee tests, negen dagen uit elkaar, allebei hetzelfde. De scheidslijn liep niet
tussen Google en Microsoft maar tussen consument en zakelijk.

De oorzaak stond in de DNS. Alle vijf domeinen hadden:

```
@     A     192.0.2.1
www   A     192.0.2.1
```

`192.0.2.0/24` is TEST-NET-1, door RFC 5737 gereserveerd voor documentatie. Het
routeert niet. De domeinen hádden dus geen website. Een domein van twee weken
oud, zonder bereikbare site, dat koude mail stuurt, is voor Gmail en
Outlook.com de vingerafdruk van een wegwerp-spamdomein. Zakelijke tenants
controleren dat veel minder streng — vandaar de splitsing.

## Uitgangspunten

**Eerlijk.** Elke pagina zegt dat dit Elyon is en linkt naar tryelyon.com. Vijf
pagina's die doen alsof ze vijf verschillende bedrijven zijn is misleiding, en
filtervendors herkennen dat patroon toch.

**Niet identiek.** Vijf keer dezelfde HTML op vijf domeinen is zelf een signaal.
Elke variant heeft een eigen invalshoek, kop en tekst.

**Compleet.** Privacyverklaring, contactgegevens, afmeldroute en uitleg waarom
iemand die mail kreeg. Dat is wat een filter — en een prospect die doorklikt —
verwacht aan te treffen.

## Gebruik

```bash
cd outreach-sites
python build.py
```

Output komt in `dist/<domein>/`. Er zijn geen dependencies.

### Eerst invullen

Bovenin `build.py` staat:

```python
BEDRIJF = {
    "adres": "[ADRES]",
    "kvk": "[KVK]",
    "email": "[E-MAILADRES]",
}
```

**Deze moeten ingevuld voordat je deployt.** Ze staan nu ook nog als placeholder
op je hoofdsite (`nl/index.html`, `nl-receptionist/`). Zonder identificeerbare
bedrijfsgegevens mis je twee dingen: het vertrouwenssignaal waar dit hele
project om draait, en de wettelijke verplichting uit artikel 3:15d BW.

## Deployen op Netlify

Per domein een eigen site. Handmatig, via de UI:

1. Netlify → **Add new site** → **Deploy manually**
2. Sleep de map `dist/useelyon.com` erin
3. **Domain settings** → **Add custom domain** → `useelyon.com`
4. Herhaal voor de andere vier

Of met de CLI:

```bash
npx netlify-cli deploy --prod --dir=dist/useelyon.com --site=<site-id>
```

## DNS aanpassen

Dit is de stap die het probleem daadwerkelijk oplost. Per domein in Cloudflare:

| Type | Naam | Huidige waarde | Nieuwe waarde |
|---|---|---|---|
| A | `@` | `192.0.2.1` | `75.2.60.5` (Netlify apex) |
| CNAME | `www` | — | `<site>.netlify.app` |

Verwijder het bestaande `www` A-record naar `192.0.2.1`.

Raak **MX, SPF, DKIM en DMARC niet aan** — die zijn correct en je mailstroom
loopt erover.

## Daarna

1. **Controleer dat elke site echt laadt** op `https://<domein>` én
   `https://www.<domein>`. Een certificaatfout is net zo slecht als geen site.
2. **Repareer de DMARC-rapportage.** Vier domeinen hebben
   `rua=mailto:...@gmail.com`. Rapportage naar een ander domein vereist een
   autorisatierecord bij de ontvanger, en dat publiceert Gmail niet voor
   persoonlijke accounts — je ontvangt dus geen enkel rapport.
3. **Trek `withelyon.com` gelijk.** Die heeft een afwijkende DMARC (andere
   `rua`, plus `ruf` en `ri=604800`) dan de andere vier.
4. **Wacht en meet.** Verhoog je volume niet meteen. Draai over een week een
   nieuwe placementtest en vergelijk de consumentenkolom.

Reken niet op een omslag binnen een dag: reputatie bouwt op over dagen tot
weken. Een website is een noodzakelijke voorwaarde, geen schakelaar.
