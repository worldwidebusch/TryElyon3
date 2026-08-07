'use strict';
/**
 * Signaal / AVG en Telecommunicatiewet
 *
 * Dit is geen juridisch advies en dit bestand maakt je niet vanzelf
 * compliant. Wat het wel doet: de regels die je in een koude e-mailopzet
 * hoort na te leven omzetten in controles die daadwerkelijk tegenhouden.
 *
 * De kern van het Nederlandse verhaal, kort:
 *
 * - Telecommunicatiewet artikel 11.7 regelt ongevraagde communicatie.
 *   LET OP: Nederland kent GEEN algemeen opt-outregime voor zakelijke
 *   e-mail. Sinds 1 oktober 2009 geldt het opt-invereiste ook voor
 *   rechtspersonen. De enige uitzondering is lid 2, en dat is een
 *   cumulatieve toets van drie delen. Zie lib/wetgeving.js, daar staat
 *   de toets uitgewerkt en wordt hij ook afgedwongen.
 *
 * - Een zakelijk adres op naam (voornaam@bedrijf.nl) is een persoonsgegeven.
 *   Daarmee valt het onder de AVG en heb je een grondslag nodig. In de
 *   praktijk is dat gerechtvaardigd belang, en dat moet je afwegen en
 *   vastleggen voordat je verstuurt, niet erna.
 *
 * - Voldoen aan 11.7 levert geen AVG-grondslag op, en andersom. Twee
 *   poorten, die allebei open moeten.
 *
 * - Omdat je de gegevens niet bij de betrokkene zelf hebt opgehaald,
 *   geldt de informatieplicht van artikel 14. Praktisch: in het eerste
 *   bericht vertellen waar je de gegevens vandaan hebt.
 *
 * - Bezwaar tegen direct marketing is absoluut. Geen afweging, geen
 *   uitzondering: bezwaar betekent stoppen.
 *
 * Laat de teksten en de afwegingen nakijken door iemand die hiervoor
 * doorgeleerd heeft voordat de eerste campagne uitgaat.
 */

const db = require('./db');
const wet = require('./wetgeving');

/* ==========================================================
   ONDERDRUKKING
   ========================================================== */

const REDENEN = {
  bezwaar: 'Betrokkene heeft bezwaar gemaakt. Absoluut en permanent.',
  afmelding: 'Afgemeld via de afmeldlink.',
  klacht: 'Als spam gemarkeerd of klacht ingediend.',
  klant: 'Bestaande klant, hoort niet in koude uitstroom.',
  concurrent: 'Concurrent, bewust uitgesloten.',
  handmatig: 'Handmatig uitgesloten.',
  bounce: 'Adres bestaat niet of weigert structureel.',
};

function normEmail(e) { return String(e || '').trim().toLowerCase(); }
function emailDomain(e) { const s = normEmail(e); const i = s.indexOf('@'); return i < 0 ? null : s.slice(i + 1); }

function suppress({ kind = 'email', value, reason = 'handmatig', note = null }) {
  if (!value) throw new Error('waarde ontbreekt');
  const v = kind === 'email' || kind === 'domain' ? String(value).trim().toLowerCase() : String(value).trim();
  if (!Object.keys(REDENEN).includes(reason)) throw new Error(`onbekende reden: ${reason}`);
  db.run(
    `INSERT INTO suppression (kind, value, reason, note) VALUES (?,?,?,?)
     ON CONFLICT(kind, value) DO UPDATE SET reason = excluded.reason, note = COALESCE(excluded.note, suppression.note)`,
    [kind, v, reason, note]
  );
  return db.get('SELECT * FROM suppression WHERE kind = ? AND value = ?', [kind, v]);
}

/** Staat dit adres, domein of bedrijf op de onderdrukkingslijst. */
function isSuppressed({ email = null, company = null, kvk = null }) {
  const treffers = [];
  const e = normEmail(email);
  if (e) {
    const r = db.get("SELECT * FROM suppression WHERE kind='email' AND value = ?", [e]);
    if (r) treffers.push(r);
    const d = emailDomain(e);
    if (d) {
      const rd = db.get("SELECT * FROM suppression WHERE kind='domain' AND value = ?", [d]);
      if (rd) treffers.push(rd);
    }
  }
  if (company) {
    const r = db.get("SELECT * FROM suppression WHERE kind='company' AND value = ?", [String(company).trim()]);
    if (r) treffers.push(r);
  }
  if (kvk) {
    const r = db.get("SELECT * FROM suppression WHERE kind='kvk' AND value = ?", [String(kvk).trim()]);
    if (r) treffers.push(r);
  }
  return { onderdrukt: treffers.length > 0, treffers };
}

function suppressionList({ limit = 200, offset = 0 } = {}) {
  return db.all('SELECT * FROM suppression ORDER BY added_at DESC LIMIT ? OFFSET ?', [limit, offset]);
}

/* ==========================================================
   VERZENDCONTROLE
   Dit is de poort. Wat hier rood staat, gaat niet de deur uit.
   ========================================================== */

/** Instellingen die aan moeten staan voordat er uberhaupt verzonden mag worden. */
function accountChecks() {
  const checks = [];

  const afzender = db.getSetting('afzender_identiteit');
  checks.push({
    id: 'afzender_identiteit',
    ok: Boolean(afzender && afzender.trim()),
    eis: 'Identiteit van de afzender is verplicht in elk bericht (Telecommunicatiewet 11.7).',
    hint: 'Zet de bedrijfsnaam en het adres in de instelling afzender_identiteit.',
  });

  const afmeld = db.getSetting('afmeld_methode');
  checks.push({
    id: 'afmeld_methode',
    ok: Boolean(afmeld && afmeld.trim()),
    eis: 'Een werkende, kosteloze afmeldmogelijkheid in een stap is verplicht. Geen inlog, geen reden opgeven, geen bevestigingsstappen.',
    hint: 'Zet een afmeldlink of afmeldadres in de instelling afmeld_methode.',
  });

  /* Artikel 11.7 lid 4 vraagt letterlijk om een postadres of nummer waar
     de ontvanger een stopverzoek naartoe kan sturen. Een afmeldlink alleen
     voldoet niet aan de tekst van de wet. */
  const post = db.getSetting('postadres');
  checks.push({
    id: 'postadres',
    ok: Boolean(post && post.trim()),
    eis: 'Tw 11.7 lid 4 sub b: een geldig postadres of telefoonnummer voor stopverzoeken. Een afmeldlink alleen is niet genoeg.',
    hint: 'Zet een echt postadres of telefoonnummer in de instelling postadres.',
  });

  const entiteit = db.getSetting('juridische_entiteit');
  checks.push({
    id: 'juridische_entiteit',
    ok: Boolean(entiteit && entiteit.trim()),
    eis: 'Tw 11.7 lid 4 sub a: de ware juridische naam van de partij namens wie het bericht uitgaat. Een merknaam of persona volstaat niet.',
    hint: 'Zet de geregistreerde entiteitsnaam in de instelling juridische_entiteit.',
  });

  const lia = wet.actieveLia();
  checks.push({
    id: 'afweging_gerechtvaardigd_belang',
    ok: Boolean(lia),
    eis: 'Voor persoonsgegevens op grondslag gerechtvaardigd belang moet er een afweging zijn, gedateerd voor de eerste verzending.',
    hint: 'Voeg een afweging toe aan de tabel lia.',
  });

  const verwerkers = db.all('SELECT * FROM processors');
  const zonderDpa = verwerkers.filter(v => !v.dpa_signed);
  checks.push({
    id: 'verwerkersovereenkomsten',
    ok: verwerkers.length > 0 && zonderDpa.length === 0,
    eis: 'AVG artikel 28: met elke partij die namens jou persoonsgegevens verwerkt (verzendplatform, verrijking, taalmodel) hoort een verwerkersovereenkomst. Bij partijen buiten de EER ook een doorgiftegrondslag.',
    hint: verwerkers.length === 0
      ? 'Er staat geen enkele verwerker geregistreerd. Voeg ze toe aan de tabel processors.'
      : `Nog geen overeenkomst vastgelegd voor: ${zonderDpa.map(v => v.name).join(', ')}`,
  });

  const herkomst = db.getSetting('herkomst_zin');
  checks.push({
    id: 'herkomst_zin',
    ok: Boolean(herkomst && herkomst.trim()),
    eis: 'Informatieplicht AVG artikel 14: vertel waar je de gegevens vandaan hebt, omdat je ze niet bij de betrokkene zelf hebt opgehaald.',
    hint: 'Bijvoorbeeld: "Ik vond je bericht in <bron>." Zet de standaardformulering in herkomst_zin.',
  });

  const registerRegels = db.get("SELECT COUNT(*) AS n FROM processing_register WHERE legal_basis LIKE '%gerechtvaardigd%'");
  checks.push({
    id: 'verwerkingsregister',
    ok: (registerRegels?.n || 0) > 0,
    eis: 'AVG artikel 30: houd een verwerkingsregister bij. Leg de afweging voor gerechtvaardigd belang vast voordat je verstuurt.',
    hint: 'Voeg een regel toe aan het verwerkingsregister met grondslag gerechtvaardigd belang.',
  });

  const bewaar = db.getNumber('bewaartermijn_dagen', 0);
  checks.push({
    id: 'bewaartermijn',
    ok: bewaar > 0,
    eis: 'Bepaal een bewaartermijn. Leads eeuwig bewaren is in strijd met opslagbeperking.',
    hint: 'Zet bewaartermijn_dagen op bijvoorbeeld 365.',
  });

  return checks;
}

/** Mag er op dit moment uberhaupt verzonden worden. */
function canSendAtAll() {
  const checks = accountChecks();
  const open = checks.filter(c => !c.ok);
  return { mag: open.length === 0, checks, blokkades: open };
}

/**
 * Controleer een enkele lead vlak voor verzending.
 * Geeft altijd een reden terug, zodat je in de trechter kunt zien
 * waarom iets is afgevallen.
 */
function checkLead(lead) {
  const redenen = [];

  if (!lead) return { mag: false, redenen: ['lead bestaat niet'] };
  if (!lead.email) redenen.push('geen e-mailadres');
  if (lead.email_status === 'ongeldig') redenen.push('adres ongeldig bevonden');
  if (lead.email_status === 'onbekend') redenen.push('adres niet geverifieerd');

  /* De twee wettelijke poorten. Dit is de kern: zonder grondslag onder
     11.7 en zonder AVG-grondslag voor persoonsgegevens gaat er niets uit. */
  const w = wet.beoordeel(lead);
  redenen.push(...w.redenen);

  const s = isSuppressed({ email: lead.email, company: lead.company, kvk: lead.kvk_number });
  if (s.onderdrukt) {
    for (const t of s.treffers) redenen.push(`onderdrukt (${t.reason}): ${REDENEN[t.reason] || ''}`.trim());
  }

  const bewaar = db.getNumber('bewaartermijn_dagen', 0);
  if (bewaar > 0 && lead.found_at) {
    const dagen = (Date.now() - new Date(lead.found_at.replace(' ', 'T') + 'Z').getTime()) / 86400000;
    if (dagen > bewaar) redenen.push(`ouder dan de bewaartermijn van ${bewaar} dagen`);
  }

  return { mag: redenen.length === 0, redenen };
}

/**
 * Filter een lijst leads tot wat daadwerkelijk verzonden mag worden.
 * Geeft ook terug wat is afgevallen en waarom, want dat is precies de
 * stap waar de trechter in de praktijk lek loopt.
 */
function filterSendable(leads) {
  const account = canSendAtAll();
  if (!account.mag) {
    return {
      mag_verzenden: false,
      reden: 'Accountcontroles staan open. Er gaat niets uit tot die opgelost zijn.',
      blokkades: account.blokkades,
      toegestaan: [],
      geweigerd: leads.map(l => ({ lead_id: l.id, redenen: ['accountcontroles open'] })),
    };
  }

  const toegestaan = [];
  const geweigerd = [];
  for (const l of leads) {
    const c = checkLead(l);
    if (c.mag) toegestaan.push(l);
    else geweigerd.push({ lead_id: l.id, company: l.company, redenen: c.redenen });
  }
  return { mag_verzenden: true, toegestaan, geweigerd, aantal_toegestaan: toegestaan.length, aantal_geweigerd: geweigerd.length };
}

/* ==========================================================
   VERZOEKEN VAN BETROKKENEN
   ========================================================== */

function logRequest({ email, kind, note = null }) {
  if (!['inzage', 'verwijdering', 'bezwaar', 'rectificatie'].includes(kind)) throw new Error(`onbekend verzoek: ${kind}`);
  const r = db.run('INSERT INTO data_requests (email, kind, note) VALUES (?,?,?)', [normEmail(email), kind, note]);
  // bezwaar werkt direct door, daar hoeft niemand op te wachten
  if (kind === 'bezwaar') suppress({ kind: 'email', value: email, reason: 'bezwaar', note: 'automatisch onderdrukt bij binnenkomst bezwaar' });
  return db.get('SELECT * FROM data_requests WHERE id = ?', [Number(r.lastInsertRowid)]);
}

/** Alles wat we over een adres hebben, voor een inzageverzoek. */
function exportSubject(email) {
  const e = normEmail(email);
  const leads = db.all('SELECT * FROM leads WHERE lower(email) = ?', [e]);
  const ids = leads.map(l => l.id);
  const inClause = ids.length ? `(${ids.map(() => '?').join(',')})` : '(NULL)';
  return {
    email: e,
    leads,
    gebeurtenissen: ids.length ? db.all(`SELECT * FROM lead_events WHERE lead_id IN ${inClause}`, ids) : [],
    uitkomsten: ids.length ? db.all(`SELECT * FROM outcomes WHERE lead_id IN ${inClause}`, ids) : [],
    onderdrukking: db.all('SELECT * FROM suppression WHERE value = ?', [e]),
    verzoeken: db.all('SELECT * FROM data_requests WHERE email = ?', [e]),
  };
}

/**
 * Verwijderverzoek uitvoeren. Het adres blijft op de onderdrukkingslijst
 * staan, want anders scrapet de pijplijn morgen dezelfde persoon opnieuw.
 * Dat is toegestaan en zelfs nodig om aan het verzoek te blijven voldoen.
 */
function eraseSubject(email) {
  const e = normEmail(email);
  const leads = db.all('SELECT id FROM leads WHERE lower(email) = ?', [e]);
  for (const l of leads) db.run('DELETE FROM leads WHERE id = ?', [l.id]);
  suppress({ kind: 'email', value: e, reason: 'bezwaar', note: 'na verwijderverzoek, adres bewaard om herbenadering te voorkomen' });
  db.run("UPDATE data_requests SET status='afgehandeld', handled_at=datetime('now') WHERE email = ? AND kind IN ('verwijdering','bezwaar')", [e]);
  return { email: e, verwijderde_leads: leads.length };
}

/* ==========================================================
   BEWAARTERMIJN
   ========================================================== */

function retentionSweep({ dryRun = true } = {}) {
  const dagen = db.getNumber('bewaartermijn_dagen', 0);
  if (dagen <= 0) {
    return { uitgevoerd: false, reden: 'bewaartermijn_dagen staat niet ingesteld', aantal: 0 };
  }
  const oud = db.all(
    `SELECT id, company, email, found_at FROM leads
     WHERE found_at < datetime('now', ?)
       AND id NOT IN (SELECT lead_id FROM outcomes WHERE type IN ('booked','closed'))`,
    [`-${dagen} days`]
  );
  if (!dryRun) for (const l of oud) db.run('DELETE FROM leads WHERE id = ?', [l.id]);
  return {
    uitgevoerd: !dryRun,
    bewaartermijn_dagen: dagen,
    aantal: oud.length,
    toelichting: 'Leads met een afspraak of klantstatus blijven staan, daar is een andere grondslag en een ander belang voor.',
    voorbeelden: oud.slice(0, 10),
  };
}

/* ==========================================================
   VERWERKINGSREGISTER
   ========================================================== */

function register() { return db.all('SELECT * FROM processing_register ORDER BY id'); }

function addRegisterEntry(e) {
  const r = db.run(
    `INSERT INTO processing_register (activity, purpose, legal_basis, categories, source_desc, retention_days, recipients)
     VALUES (?,?,?,?,?,?,?)`,
    [e.activity, e.purpose, e.legal_basis, e.categories, e.source_desc, e.retention_days, e.recipients || null]
  );
  return db.get('SELECT * FROM processing_register WHERE id = ?', [Number(r.lastInsertRowid)]);
}

/** Eén overzicht voor het dashboard. */
function status() {
  const account = canSendAtAll();
  const openVerzoeken = db.get("SELECT COUNT(*) AS n FROM data_requests WHERE status='open'")?.n || 0;
  const onderdrukt = db.get('SELECT COUNT(*) AS n FROM suppression')?.n || 0;
  const sweep = retentionSweep({ dryRun: true });

  return {
    mag_verzenden: account.mag,
    controles: account.checks,
    blokkades: account.blokkades,
    open_verzoeken: openVerzoeken,
    onderdrukte_records: onderdrukt,
    over_bewaartermijn: sweep.aantal,
    register_regels: register().length,
  };
}

module.exports = {
  REDENEN, suppress, isSuppressed, suppressionList,
  accountChecks, canSendAtAll, checkLead, filterSendable,
  logRequest, exportSubject, eraseSubject,
  retentionSweep, register, addRegisterEntry, status,
};
