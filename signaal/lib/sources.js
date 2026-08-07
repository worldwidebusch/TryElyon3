'use strict';
/**
 * Signaal / bronnen
 *
 * Een bron is een plek waar signalen vandaan komen. Elke bron heeft een
 * juridische status, en die status is geen notitieveld maar een slot:
 * de pijplijn weigert automatisch op te halen bij een bron die op
 * 'verboden' of 'review' staat.
 *
 * Dat is bewust strenger dan de Amerikaanse opzet waar dit op gebaseerd
 * is. LinkedIn en Facebook verbieden geautomatiseerd ophalen in hun
 * voorwaarden. Dat je het technisch kunt, maakt het niet verstandig als
 * je klanten Nederlandse bedrijven zijn en je onder de AVG valt.
 */

const db = require('./db');

const LEGAL = {
  toegestaan: 'Openbare bron, geautomatiseerd ophalen is toegestaan',
  api_vereist: 'Alleen via de officiele API met een geldig contract of sleutel',
  verboden: 'Voorwaarden verbieden geautomatiseerd ophalen. Handmatig gebruik alleen.',
  review: 'Nog niet beoordeeld. Blijft uit de automatische pijplijn tot dat wel zo is.',
};

/** Alleen deze statussen mogen in een geautomatiseerde run meedoen. */
const AUTOMATISEERBAAR = new Set(['toegestaan', 'api_vereist']);

/**
 * Startregister voor de Nederlandse markt.
 * De juridische status is een werkaanname en geen juridisch advies.
 * Laat dit nakijken voordat je een bron op automatisch zet.
 */
const NL_SOURCES = [
  {
    name: 'KVK Handelsregister',
    kind: 'register',
    url: 'https://developers.kvk.nl/',
    adapter: 'kvk',
    legal_status: 'api_vereist',
    legal_note: 'Officiele API van de Kamer van Koophandel. Vereist een account en is betaald per bevraging. Het Handelsregister is openbaar, maar hergebruik van persoonsgegevens uit het register kent beperkingen.',
    automated: 1,
    cadence_hours: 24,
  },
  {
    name: 'TenderNed',
    kind: 'aanbesteding',
    url: 'https://www.tenderned.nl/',
    adapter: 'tenderned',
    legal_status: 'toegestaan',
    legal_note: 'Aanbestedingen zijn verplicht openbaar. Beschikbaar als open data via data.overheid.nl.',
    automated: 1,
    cadence_hours: 12,
  },
  {
    name: 'Vacaturepaginas van bedrijven',
    kind: 'vacature',
    url: null,
    adapter: 'careersite',
    legal_status: 'toegestaan',
    legal_note: 'Eigen website van het bedrijf. Respecteer robots.txt en houd het verzoektempo laag.',
    automated: 1,
    cadence_hours: 24,
  },
  {
    name: 'Nieuws en persberichten',
    kind: 'nieuws',
    url: null,
    adapter: 'rss',
    legal_status: 'toegestaan',
    legal_note: 'RSS en nieuwsfeeds zijn bedoeld om gelezen te worden. Geen persoonsgegevens opslaan die je niet nodig hebt.',
    automated: 1,
    cadence_hours: 6,
  },
  {
    name: 'Reddit',
    kind: 'sociaal',
    url: 'https://www.reddit.com/dev/api/',
    adapter: 'reddit',
    legal_status: 'api_vereist',
    legal_note: 'Reddit heeft een officiele API met betaalde limieten. Gebruik die, niet de HTML.',
    automated: 0,
    cadence_hours: 4,
  },
  {
    name: 'Werk.nl',
    kind: 'vacature',
    url: 'https://www.werk.nl/',
    adapter: 'manual',
    legal_status: 'review',
    legal_note: 'UWV-vacaturebank. Voorwaarden voor geautomatiseerd hergebruik nog na te gaan.',
    automated: 0,
    cadence_hours: 24,
  },
  {
    name: 'Indeed NL',
    kind: 'vacature',
    url: 'https://nl.indeed.com/',
    adapter: 'manual',
    legal_status: 'verboden',
    legal_note: 'Indeed verbiedt geautomatiseerd ophalen in de gebruiksvoorwaarden en blokkeert er actief op. Alleen handmatig, of via een betaalde partneroplossing.',
    automated: 0,
    cadence_hours: 24,
  },
  {
    name: 'LinkedIn',
    kind: 'sociaal',
    url: 'https://www.linkedin.com/',
    adapter: 'manual',
    legal_status: 'verboden',
    legal_note: 'De gebruiksvoorwaarden verbieden scrapen expliciet en LinkedIn handhaaft dat ook via de rechter. Blijft in dit systeem handmatig. Signalen mogen hier vandaan komen, maar dan door een mens ingevoerd.',
    automated: 0,
    cadence_hours: 24,
  },
  {
    name: 'Facebook ondernemersgroepen',
    kind: 'sociaal',
    url: 'https://www.facebook.com/',
    adapter: 'manual',
    legal_status: 'verboden',
    legal_note: 'Meta verbiedt geautomatiseerd ophalen. Bij besloten groepen komt daar bovenop dat leden geen openbaarmaking verwachten, wat het onder de AVG lastiger maakt. Handmatig invoeren mag.',
    automated: 0,
    cadence_hours: 24,
  },
  {
    name: 'Branchefora',
    kind: 'forum',
    url: null,
    adapter: 'manual',
    legal_status: 'review',
    legal_note: 'Per forum beoordelen. Openbare fora zonder inlog zijn meestal werkbaar, besloten fora niet.',
    automated: 0,
    cadence_hours: 12,
  },
];

function list({ onlyActive = false } = {}) {
  const rows = db.all(`SELECT * FROM sources ${onlyActive ? 'WHERE active = 1' : ''} ORDER BY name`);
  return rows.map(r => ({
    ...r,
    legal_uitleg: LEGAL[r.legal_status] || null,
    mag_automatisch: AUTOMATISEERBAAR.has(r.legal_status),
  }));
}

function get(id) {
  const r = db.get('SELECT * FROM sources WHERE id = ?', [id]);
  if (!r) return null;
  return { ...r, legal_uitleg: LEGAL[r.legal_status], mag_automatisch: AUTOMATISEERBAAR.has(r.legal_status) };
}

/**
 * Zet een bron op automatisch. Weigert als de juridische status dat niet
 * toelaat. Dit is met opzet een harde weigering en geen waarschuwing.
 */
function setAutomated(id, automated) {
  const bron = get(id);
  if (!bron) throw new Error('bron bestaat niet');
  if (automated && !bron.mag_automatisch) {
    const err = new Error(
      `Bron "${bron.name}" staat op status "${bron.legal_status}" en mag niet automatisch draaien. ${LEGAL[bron.legal_status]}`
    );
    err.code = 'JURIDISCH_GEBLOKKEERD';
    throw err;
  }
  db.run('UPDATE sources SET automated = ? WHERE id = ?', [automated ? 1 : 0, id]);
  return get(id);
}

function setLegalStatus(id, status, note = null) {
  if (!Object.keys(LEGAL).includes(status)) throw new Error(`onbekende status: ${status}`);
  db.run('UPDATE sources SET legal_status = ?, legal_note = COALESCE(?, legal_note) WHERE id = ?', [status, note, id]);
  // een bron die niet meer mag, gaat direct van automatisch af
  if (!AUTOMATISEERBAAR.has(status)) db.run('UPDATE sources SET automated = 0 WHERE id = ?', [id]);
  return get(id);
}

/** Bronnen die nu opgehaald mogen worden, op basis van cadans. */
function due() {
  return list({ onlyActive: true }).filter(s => {
    if (!s.automated || !s.mag_automatisch) return false;
    if (!s.last_run_at) return true;
    const verstreken = (Date.now() - new Date(s.last_run_at + 'Z').getTime()) / 3600000;
    return verstreken >= s.cadence_hours;
  });
}

function markRun(id) {
  db.run("UPDATE sources SET last_run_at = datetime('now') WHERE id = ?", [id]);
}

/* ---------- briefs: persona x bron ---------- */

function briefs({ personaId = null, activeOnly = true } = {}) {
  const where = [];
  const params = [];
  if (personaId) { where.push('b.persona_id = ?'); params.push(personaId); }
  if (activeOnly) where.push('b.active = 1');
  return db.all(`
    SELECT b.*, p.name AS persona, p.version AS persona_versie,
           s.name AS bron, s.legal_status, s.automated
    FROM briefs b
    JOIN personas p ON p.id = b.persona_id
    JOIN sources s ON s.id = b.source_id
    ${where.length ? 'WHERE ' + where.join(' AND ') : ''}
    ORDER BY p.name, s.name
  `, params);
}

function addBrief({ persona_id, source_id, query, extract = null }) {
  const bron = get(source_id);
  if (!bron) throw new Error('bron bestaat niet');
  const r = db.run(
    'INSERT OR IGNORE INTO briefs (persona_id, source_id, query, extract) VALUES (?,?,?,?)',
    [persona_id, source_id, query, extract]
  );
  return r.changes > 0
    ? db.get('SELECT * FROM briefs WHERE id = ?', [Number(r.lastInsertRowid)])
    : db.get('SELECT * FROM briefs WHERE persona_id=? AND source_id=? AND query=?', [persona_id, source_id, query]);
}

/** Overzicht van de juridische stand van zaken over alle bronnen. */
function legalOverview() {
  const rows = list();
  const per = {};
  for (const r of rows) (per[r.legal_status] ||= []).push(r.name);
  return {
    statussen: LEGAL,
    per_status: per,
    automatisch_actief: rows.filter(r => r.automated && r.mag_automatisch).map(r => r.name),
    geblokkeerd: rows.filter(r => !r.mag_automatisch).map(r => ({ naam: r.name, status: r.legal_status, reden: r.legal_note })),
    te_beoordelen: rows.filter(r => r.legal_status === 'review').map(r => r.name),
  };
}

module.exports = {
  LEGAL, AUTOMATISEERBAAR, NL_SOURCES,
  list, get, setAutomated, setLegalStatus, due, markRun,
  briefs, addBrief, legalOverview,
};
