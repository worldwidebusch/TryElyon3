'use strict';
/**
 * Signaal / demodata
 *
 * Vult een lege database met een geloofwaardige Nederlandse situatie,
 * zodat het dashboard meteen iets laat zien. De cijfers zijn verzonnen
 * maar de verhoudingen zijn realistisch: de trechter lekt op de plekken
 * waar hij in het echt ook lekt.
 *
 * Draai `node signaal/seed.js --reset` om opnieuw te beginnen.
 */

const db = require('./db');
const sources = require('./sources');
const funnel = require('./funnel');

/* Deterministische toevalsgenerator, zodat de demo elke keer gelijk is. */
function rng(seed = 42) {
  let s = seed >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
const rand = rng(20260807);
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const between = (a, b) => a + Math.floor(rand() * (b - a + 1));

function dagenGeleden(n) {
  return new Date(Date.now() - n * 86400000).toISOString().slice(0, 19).replace('T', ' ');
}
function datumGeleden(n) {
  return new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);
}

/* ---------- instellingen ---------- */
const SETTINGS = {
  doel_contacten_per_maand: 7000,
  doel_reply_rate: 0.2,
  doel_positief_van_reply: 0.35,
  doel_afspraak_van_positief: 0.5,
  sends_per_mailbox_per_dag: 20,
  mailboxen_per_domein: 3,
  warmup_dagen: 21,
  werkdagen_per_maand: 21.7,
  persona_min_volume: 40,
  waarde_per_afspraak_eur: 450,
  kosten_per_domein_eur: 12,
  kosten_per_mailbox_eur: 3,
  bewaartermijn_dagen: 365,
  afzender_identiteit: 'Elyon, handelend vanuit een in de Verenigde Staten geregistreerde LLC. Contact via de oprichter, telefonisch bereikbaar.',
  // Tw 11.7 lid 4 vraagt letterlijk om deze twee. Vul ze in met echte gegevens.
  juridische_entiteit: 'VUL IN: geregistreerde naam van de LLC',
  postadres: 'VUL IN: geldig postadres of telefoonnummer voor stopverzoeken',
  afmeld_methode: 'Afmeldlink in elke e-mail, plus reageren met "stop" werkt ook.',
  herkomst_zin: 'Ik vond dit bericht in {bron}. Wil je niet benaderd worden, laat het weten en ik haal je gegevens weg.',
};

/* ---------- persona's ---------- */
const PERSONAS = [
  { name: 'Detachering IT', segment: 'Detacheringsbureaus die IT-profielen leveren', sbi_codes: '7820,6202', size_min: 20, size_max: 80, regions: 'Randstad, Brabant', hypothesis: 'Bedrijven die herhaald dezelfde technische rol uitzetten hebben een leverancierprobleem, geen wervingsprobleem.' },
  { name: 'Marketingbureau B2B', segment: 'Bureaus die B2B-leadgeneratie verkopen', sbi_codes: '7311,7312', size_min: 15, size_max: 60, regions: 'Landelijk', hypothesis: 'Bureaus wisselen van leverancier op het moment dat hun huidige partij ruis levert.' },
  { name: 'IT consultancy', segment: 'Implementatie en koppelingen, vaak rond ERP', sbi_codes: '6202,6201', size_min: 25, size_max: 120, regions: 'Landelijk', hypothesis: 'Een intern vastgelopen koppelingsproject is een direct koopmoment.' },
  { name: 'Werving en selectie', segment: 'Bureaus voor vaste plaatsingen', sbi_codes: '7810', size_min: 10, size_max: 50, regions: 'Landelijk', hypothesis: 'Uitbreiding naar een tweede vestiging gaat vooraf aan een wervingsgolf.' },
  { name: 'HR dienstverlening', segment: 'Onboarding, verzuim, HR-software', sbi_codes: '7830,6201', size_min: 15, size_max: 70, regions: 'Randstad', hypothesis: 'Snelle groei in koppen maakt HR-processen acuut, en dat zeggen ze zelf openbaar.' },
];

const BEDRIJVEN = ['Vandenberg', 'De Wit', 'Kroon', 'Meijer', 'Bakker', 'Van Dijk', 'Hoekstra', 'Smit', 'Jansen', 'Visser', 'Dekker', 'Mulder', 'Bos', 'Peters', 'Willems', 'Groot', 'Brouwer', 'Timmermans', 'Vos', 'Blom'];
const SUFFIX = ['B.V.', 'Groep', 'Solutions', 'Techniek', 'Partners', 'Advies', 'Systemen'];
const REGIOS = ['Utrecht', 'Amsterdam', 'Rotterdam', 'Eindhoven', 'Twente', 'Brabant', 'Gelderland', 'Groningen', 'Zuid-Holland', 'Limburg'];
const ROLLEN = ['operationeel directeur', 'eigenaar', 'commercieel manager', 'HR-manager', 'oprichter', 'teamlead', 'directeur'];
const VOORNAMEN = ['Thomas', 'Sanne', 'Bas', 'Lotte', 'Daan', 'Eva', 'Ruben', 'Fleur', 'Joris', 'Anne', 'Sem', 'Julia'];

const TRIGGERS = [
  'Vierde vacature voor dezelfde rol binnen drie weken geplaatst.',
  'Openbare vraag om een leverancier in een ondernemersgroep.',
  'Aanbesteding gepubliceerd voor inhuur van personeel.',
  'Nieuwe vestiging ingeschreven bij de KVK.',
  'Bericht over groei van 18 naar 30 medewerkers dit kwartaal.',
  'Zoekt partij voor een koppeling die intern niet lukt.',
  'Huidig bureau stopt ermee, vraagt om aanraders.',
  'Zeven vacatures open, drie langer dan zestig dagen.',
];

function seed({ resetFirst = false } = {}) {
  if (resetFirst) db.reset();
  db.open();

  /* instellingen */
  for (const [k, v] of Object.entries(SETTINGS)) db.setSetting(k, v);

  /* Afweging gerechtvaardigd belang. Moet gedateerd zijn VOOR de oudste
     lead, anders dekt hij de verwerking niet en blokkeert poort 2. */
  if (db.all('SELECT id FROM lia').length === 0) {
    db.run(`INSERT INTO lia (purpose, source_scope, belang, noodzaak, afweging, version, dated_at)
            VALUES (?,?,?,?,?,1,?)`, [
      'Koude zakelijke benadering op basis van openbaar geuite koopsignalen',
      'KVK Handelsregister, TenderNed, openbare vacaturepaginas, openbare nieuwsberichten',
      'Commercieel belang bij het benaderen van bedrijven die openbaar kenbaar maken dat zij zoeken wat wij leveren.',
      'Minder ingrijpend alternatief ontbreekt voor dit specifieke signaal. Waar een functioneel adres bestaat, gebruiken we dat in plaats van een persoon.',
      'Beperkt tot zakelijke context, geen bijzondere categorieen, eenmalige benadering met directe afmeldmogelijkheid, bewaartermijn beperkt. Belang van betrokkene weegt zwaarder bij persoonlijke adressen, daarom worden die niet op deze grondslag benaderd.',
      datumGeleden(400),
    ]);
  }

  /* Verwerkers, AVG artikel 28. Zonder deze regels blokkeert de poort,
     en dat hoort ook: dit wordt in de praktijk stelselmatig overgeslagen. */
  if (db.all('SELECT id FROM processors').length === 0) {
    const verwerkers = [
      ['Verzendplatform', 'Versturen van e-mail en bijhouden van reacties', 1, 'Modelbepalingen EU', 'Verenigde Staten'],
      ['E-mailzoeker', 'Achterhalen van zakelijke adressen', 0, null, 'Verenigde Staten'],
      ['Verificatiedienst', 'Controleren of een adres bestaat', 1, 'Modelbepalingen EU', 'Europese Unie'],
      ['Taalmodel', 'Opstellen van concepttekst op basis van de aanleiding', 0, null, 'Verenigde Staten'],
    ];
    for (const [naam, doel, dpa, basis, land] of verwerkers) {
      db.run('INSERT OR IGNORE INTO processors (name, purpose, dpa_signed, dpa_date, transfer_basis, land) VALUES (?,?,?,?,?,?)',
        [naam, doel, dpa, dpa ? datumGeleden(200) : null, basis, land]);
    }
  }

  /* verwerkingsregister, want zonder regel blokkeert de AVG-poort */
  if (db.all('SELECT id FROM processing_register').length === 0) {
    db.run(`INSERT INTO processing_register (activity, purpose, legal_basis, categories, source_desc, retention_days, recipients)
            VALUES (?,?,?,?,?,?,?)`, [
      'Koude zakelijke benadering op basis van openbare signalen',
      'Zakelijke bedrijven benaderen die openbaar kenbaar maken dat zij een dienst zoeken die wij leveren',
      'Gerechtvaardigd belang (AVG artikel 6 lid 1 sub f). Afweging vastgelegd en periodiek herzien.',
      'Zakelijke contactgegevens: naam, functie, zakelijk e-mailadres, werkgever. Geen bijzondere categorieen.',
      'Openbare bronnen: KVK Handelsregister, TenderNed, vacaturepaginas, openbare berichten',
      365,
      'Verzendplatform voor e-mail, verwerkersovereenkomst vereist',
    ]);
  }

  /* bronnen */
  for (const s of sources.NL_SOURCES) {
    db.run(`INSERT OR IGNORE INTO sources (name, kind, url, adapter, legal_status, legal_note, automated, cadence_hours)
            VALUES (?,?,?,?,?,?,?,?)`,
      [s.name, s.kind, s.url, s.adapter, s.legal_status, s.legal_note, s.automated, s.cadence_hours]);
  }
  const bronRijen = db.all('SELECT * FROM sources');
  const bronById = Object.fromEntries(bronRijen.map(b => [b.id, b]));
  const automatischeBronnen = bronRijen.filter(b => b.automated === 1);

  /* persona's */
  for (const p of PERSONAS) {
    db.run(`INSERT OR IGNORE INTO personas (name, version, segment, sbi_codes, size_min, size_max, regions, hypothesis)
            VALUES (?,1,?,?,?,?,?,?)`,
      [p.name, p.segment, p.sbi_codes, p.size_min, p.size_max, p.regions, p.hypothesis]);
  }
  const personaRijen = db.all('SELECT * FROM personas');

  /* briefs: elke persona op elke automatiseerbare bron */
  for (const p of personaRijen) {
    for (const b of automatischeBronnen) {
      db.run('INSERT OR IGNORE INTO briefs (persona_id, source_id, query, extract) VALUES (?,?,?,?)', [
        p.id, b.id,
        `${p.segment} in ${p.regions}`,
        'bedrijfsnaam, aanleiding, contactpersoon, link naar de vindplaats',
      ]);
    }
  }

  /* domeinen en mailboxen */
  const tlds = ['com', 'nl', 'co'];
  const domeinAantal = 14;
  for (let i = 0; i < domeinAantal; i++) {
    const tld = tlds[i % tlds.length];
    const naam = `elyon-${['post', 'mail', 'bericht', 'contact', 'inbox', 'signaal', 'lijn'][i % 7]}${i + 1}.${tld}`;
    const leeftijd = between(5, 120);
    // de laatste paar domeinen zijn nog aan het opwarmen
    const status = i >= domeinAantal - 3 ? 'warming' : (i === 2 ? 'resting' : 'active');
    const r = db.run(`INSERT OR IGNORE INTO domains (domain, provider, tld, registered_at, status, spf, dkim, dmarc)
                      VALUES (?,?,?,?,?,?,?,?)`,
      [naam, 'demoprovider', tld, datumGeleden(leeftijd), status, 1, 1, i === 5 ? 0 : 1]);
    if (r.changes === 0) continue;
    const domainId = Number(r.lastInsertRowid);

    for (let m = 0; m < 3; m++) {
      const adres = `${['thijs', 'team', 'hallo'][m]}@${naam}`;
      db.run(`INSERT OR IGNORE INTO mailboxes (domain_id, address, display_name, daily_cap, warmup_start, status)
              VALUES (?,?,?,?,?,?)`,
        [domainId, adres, 'Thijs Buschman', 20, datumGeleden(Math.min(leeftijd, between(1, 40))),
         status === 'resting' ? 'resting' : status]);
    }

    /* gezondheidsmetingen over veertien dagen */
    for (let d = 0; d < 14; d++) {
      const verzonden = status === 'active' ? between(35, 60) : status === 'warming' ? between(4, 14) : 0;
      // domein 5 mist DMARC en presteert slecht, domein 2 rust al
      const slecht = i === 5;
      db.run(`INSERT OR IGNORE INTO domain_health (domain_id, day, sent, bounced, replied, spam_reports)
              VALUES (?,?,?,?,?,?)`, [
        domainId, datumGeleden(d), verzonden,
        Math.round(verzonden * (slecht ? 0.07 : 0.015)),
        Math.round(verzonden * (slecht ? 0.004 : 0.05)),
        slecht && d % 3 === 0 ? 1 : 0,
      ]);
    }
  }

  /* onderdrukkingslijst */
  const onderdrukt = [
    { kind: 'domain', value: 'concurrentbureau.nl', reason: 'concurrent' },
    { kind: 'email', value: 'info@bestaandeklant.nl', reason: 'klant' },
    { kind: 'email', value: 'geen.mail@voorbeeld.nl', reason: 'bezwaar' },
  ];
  for (const o of onderdrukt) {
    db.run('INSERT OR IGNORE INTO suppression (kind, value, reason) VALUES (?,?,?)', [o.kind, o.value, o.reason]);
  }

  /* ---------- leads en trechter ---------- */
  const bestaand = db.get('SELECT COUNT(*) AS n FROM leads')?.n || 0;
  if (bestaand === 0) {
    // Genoeg volume zodat ook de onderkant van de trechter gevuld raakt.
    // Met te weinig leads komen er nul klanten uit en heeft de
    // persona-weging niets om op te ranken.
    const AANTAL = 5200;
    const conv = {
      email_found: 0.60,
      verified: 0.84,
      sendable: 0.72,
      pushed: 0.96,
      contacted: 0.98,
      replied: 0.22,
      positive: 0.34,
      booked: 0.52,
      closed: 0.26,
    };

    /* Niet elke persona presteert gelijk, anders valt er niets te kiezen
       en is de hele gesloten lus een sierstuk. IT consultancy loopt goed,
       HR dienstverlening reageert veel maar tekent niet, en die laatste
       is precies het geval waar sturen op reacties je bedriegt. */
    const persFactor = {
      'IT consultancy':        { reply: 1.15, booked: 1.35, closed: 1.6, klacht: 0.6 },
      'Detachering IT':        { reply: 1.05, booked: 1.10, closed: 1.2, klacht: 0.8 },
      'Werving en selectie':   { reply: 0.95, booked: 0.95, closed: 0.9, klacht: 1.0 },
      'Marketingbureau B2B':   { reply: 0.90, booked: 0.75, closed: 0.6, klacht: 1.4 },
      'HR dienstverlening':    { reply: 1.30, booked: 0.45, closed: 0.25, klacht: 2.2 },
    };

    for (let i = 0; i < AANTAL; i++) {
      const persona = pick(personaRijen);
      const pf = persFactor[persona.name] || { reply: 1, booked: 1, closed: 1, klacht: 1 };
      const bron = pick(automatischeBronnen.length ? automatischeBronnen : bronRijen);
      const bedrijf = `${pick(BEDRIJVEN)} ${pick(SUFFIX)}`;
      const gevonden = between(1, 60);
      const heeftEmail = rand() < conv.email_found;
      const voornaam = pick(VOORNAMEN);
      const slug = bedrijf.toLowerCase().replace(/[^a-z]+/g, '');

      /* Realistische verdeling van adresvormen bij geschraapte B2B-data.
         Dit bepaalt of artikel 11.7 lid 2 uberhaupt in beeld komt.
         De meeste adressen zijn geraden of persoonlijk, en die dragen
         lid 2 niet. Dat is precies wat het bereikcijfer moet laten zien. */
      const r0 = rand();
      let localpart, bestemming, grondslag, bewijs;
      if (r0 < 0.08) {
        localpart = pick(['sales', 'inkoop', 'aanbiedingen', 'offertes']);
        bestemming = 'STRONG';
        grondslag = 'b2b_designated';
        bewijs = `https://${slug}.nl/contact (adres gepubliceerd met uitnodiging om aanbod te sturen)`;
      } else if (r0 < 0.34) {
        localpart = pick(['info', 'contact']);
        bestemming = 'WEAK';
        grondslag = 'b2b_designated';   // wordt bewust geweigerd door de poort
        bewijs = `https://${slug}.nl/contact (algemeen contactadres)`;
      } else if (r0 < 0.40) {
        localpart = pick(['support', 'facturen', 'vacature']);
        bestemming = 'NONE';
        grondslag = 'b2b_designated';   // verkeerd doel, wordt geweigerd
        bewijs = `https://${slug}.nl/contact`;
      } else {
        localpart = voornaam.toLowerCase();
        bestemming = 'NONE';
        grondslag = null;               // geraden persoonlijk adres, geen grondslag
        bewijs = null;
      }

      const r = db.run(`INSERT INTO leads
        (company, kvk_number, website, contact_name, contact_role, email, email_status,
         employees, region, persona_id, source_id, trigger_text, trigger_url, found_at, stage,
         legal_basis, designation, evidence_url, acquired_method, record_class)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`, [
        bedrijf,
        String(between(10000000, 89999999)),
        `https://${slug}.nl`,
        `${voornaam} ${pick(BEDRIJVEN)}`,
        pick(ROLLEN),
        heeftEmail ? `${localpart}@${slug}.nl` : null,
        heeftEmail ? 'gevonden' : 'onbekend',
        between(persona.size_min || 10, persona.size_max || 80),
        pick(REGIOS),
        persona.id,
        bron.id,
        pick(TRIGGERS),
        `${bronById[bron.id]?.url || 'https://voorbeeld.nl'}/bericht/${i}`,
        dagenGeleden(gevonden),
        'scanned',
        grondslag,
        bestemming,
        bewijs,
        'openbare bron, geautomatiseerd opgehaald',
        bestemming === 'NONE' && !grondslag ? 'PERSONAL' : 'NON_PERSONAL',
      ]);
      const leadId = Number(r.lastInsertRowid);

      // trechter aflopen, met een tijdstip dat oploopt
      let dag = gevonden;
      const stap = (naam) => { funnel.record(leadId, naam); };
      stap('scanned');
      if (!heeftEmail) continue;
      stap('email_found');

      if (rand() >= conv.verified) { db.run("UPDATE leads SET email_status='ongeldig' WHERE id=?", [leadId]); continue; }
      db.run("UPDATE leads SET email_status='geverifieerd' WHERE id=?", [leadId]);
      stap('verified');

      if (rand() >= conv.sendable) continue;
      stap('sendable');
      if (rand() >= conv.pushed) continue;
      stap('pushed');
      if (rand() >= conv.contacted) continue;
      stap('contacted');

      if (rand() >= conv.replied * pf.reply) continue;
      stap('replied');
      db.run("INSERT INTO outcomes (lead_id, type, at) VALUES (?,'reply',?)", [leadId, dagenGeleden(Math.max(0, dag - 2))]);

      if (rand() >= conv.positive) continue;
      stap('positive');
      db.run("INSERT INTO outcomes (lead_id, type, at) VALUES (?,'positive',?)", [leadId, dagenGeleden(Math.max(0, dag - 3))]);

      if (rand() >= conv.booked * pf.booked) continue;
      stap('booked');
      db.run("INSERT INTO outcomes (lead_id, type, at) VALUES (?,'booked',?)", [leadId, dagenGeleden(Math.max(0, dag - 4))]);

      if (rand() >= conv.closed * pf.closed) continue;
      stap('closed');
      db.run("INSERT INTO outcomes (lead_id, type, value_eur, at) VALUES (?,'closed',?,?)",
        [leadId, between(1200, 6500), dagenGeleden(Math.max(0, dag - 8))]);
    }

    /* Onderdruk een deel van de echte leads, anders staat de AVG-poort
       er wel maar houdt hij nooit iets tegen en lijkt hij versiering. */
    const kandidaten = db.all("SELECT id, email, company FROM leads WHERE email IS NOT NULL LIMIT 900");
    const redenen = ['bezwaar', 'afmelding', 'klant', 'klacht', 'concurrent'];
    for (let i = 0; i < kandidaten.length; i += 11) {
      const k = kandidaten[i];
      db.run('INSERT OR IGNORE INTO suppression (kind, value, reason, note) VALUES (?,?,?,?)',
        ['email', k.email.toLowerCase(), redenen[(i / 11) % redenen.length], 'demodata']);
    }
    // en een heel bedrijfsdomein, dat komt in het echt ook voor
    const bedrijfsdomein = kandidaten.find(k => k.email && k.email.includes('@'));
    if (bedrijfsdomein) {
      db.run('INSERT OR IGNORE INTO suppression (kind, value, reason, note) VALUES (?,?,?,?)',
        ['domain', bedrijfsdomein.email.split('@')[1].toLowerCase(), 'klant', 'hele organisatie uitgesloten']);
    }

    // een paar klachten en afmeldingen, want die horen erbij
    const benaderd = db.all("SELECT lead_id FROM lead_events WHERE stage='contacted' LIMIT 400");
    for (let i = 0; i < benaderd.length; i += 90) {
      db.run("INSERT INTO outcomes (lead_id, type) VALUES (?,'unsubscribe')", [benaderd[i].lead_id]);
    }
    for (let i = 5; i < benaderd.length; i += 260) {
      db.run("INSERT INTO outcomes (lead_id, type) VALUES (?,'complaint')", [benaderd[i].lead_id]);
    }
  }

  /* kosten van deze maand */
  if ((db.get('SELECT COUNT(*) AS n FROM costs')?.n || 0) === 0) {
    const regels = [
      ['Verzendplatform', 'verzenden', 'maandelijks', 97, 0],
      ['Domeinprovider', 'infrastructuur', 'maandelijks', 168, 42],
      ['Webzoeken', 'onderzoek', 'per_eenheid', 84.5, 8450],
      ['E-mailzoeker', 'verrijking', 'per_eenheid', 128.4, 12840],
      ['Verificatie', 'verrijking', 'per_eenheid', 31.2, 15600],
      ['KVK API', 'data', 'per_eenheid', 42.8, 6685],
      ['Taalmodel', 'tekst', 'per_eenheid', 96.3, 0],
      ['Domeinregistratie', 'infrastructuur', 'maandelijks', 42, 14],
    ];
    for (const [p, c, m, bedrag, eenheden] of regels) {
      db.run('INSERT INTO costs (provider, category, model, amount_eur, units) VALUES (?,?,?,?,?)', [p, c, m, bedrag, eenheden]);
    }
  }

  return samenvatting();
}

function samenvatting() {
  const tel = (t) => db.get(`SELECT COUNT(*) AS n FROM ${t}`)?.n || 0;
  return {
    domeinen: tel('domains'),
    mailboxen: tel('mailboxes'),
    personas: tel('personas'),
    bronnen: tel('sources'),
    briefs: tel('briefs'),
    leads: tel('leads'),
    gebeurtenissen: tel('lead_events'),
    uitkomsten: tel('outcomes'),
    onderdrukt: tel('suppression'),
    kostenregels: tel('costs'),
  };
}

module.exports = { seed, samenvatting, SETTINGS };
