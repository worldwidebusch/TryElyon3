'use strict';
/**
 * Signaal / database
 *
 * Gebruikt de ingebouwde node:sqlite. Geen npm install nodig.
 * Migratie naar Postgres of Supabase: vervang alleen dit bestand, de rest
 * van de code praat uitsluitend via de functies hieronder met de database.
 */

const { DatabaseSync } = require('node:sqlite');
const path = require('node:path');
const fs = require('node:fs');

const DATA_DIR = path.join(__dirname, '..', 'data');
const DB_PATH = process.env.SIGNAAL_DB || path.join(DATA_DIR, 'signaal.db');

let db = null;

function open() {
  if (db) return db;
  if (DB_PATH !== ':memory:') fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  db = new DatabaseSync(DB_PATH);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
  migrate();
  return db;
}

/* ==========================================================
   SCHEMA
   ========================================================== */
const SCHEMA = `
CREATE TABLE IF NOT EXISTS settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

/* ---------- verzendcapaciteit ---------- */
CREATE TABLE IF NOT EXISTS domains (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  domain        TEXT NOT NULL UNIQUE,
  provider      TEXT NOT NULL DEFAULT 'onbekend',
  tld           TEXT NOT NULL DEFAULT 'com',
  registered_at TEXT NOT NULL DEFAULT (date('now')),
  status        TEXT NOT NULL DEFAULT 'warming'
                CHECK (status IN ('warming','active','resting','retired')),
  spf           INTEGER NOT NULL DEFAULT 0,
  dkim          INTEGER NOT NULL DEFAULT 0,
  dmarc         INTEGER NOT NULL DEFAULT 0,
  notes         TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mailboxes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id     INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
  address       TEXT NOT NULL UNIQUE,
  display_name  TEXT,
  daily_cap     INTEGER NOT NULL DEFAULT 20,
  warmup_start  TEXT,
  status        TEXT NOT NULL DEFAULT 'warming'
                CHECK (status IN ('warming','active','resting','retired')),
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mailboxes_domain ON mailboxes(domain_id);

/* dagelijkse gezondheidsmeting per domein */
CREATE TABLE IF NOT EXISTS domain_health (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id    INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
  day          TEXT NOT NULL,
  sent         INTEGER NOT NULL DEFAULT 0,
  bounced      INTEGER NOT NULL DEFAULT 0,
  replied      INTEGER NOT NULL DEFAULT 0,
  spam_reports INTEGER NOT NULL DEFAULT 0,
  UNIQUE (domain_id, day)
);

/* ---------- doelgroep, gesloten lus ---------- */
CREATE TABLE IF NOT EXISTS personas (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1,
  parent_id     INTEGER REFERENCES personas(id) ON DELETE SET NULL,
  segment       TEXT,
  sbi_codes     TEXT,
  size_min      INTEGER,
  size_max      INTEGER,
  regions       TEXT,
  hypothesis    TEXT,
  status        TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','testing','retired')),
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (name, version)
);

/* ---------- catalysusbronnen ---------- */
CREATE TABLE IF NOT EXISTS sources (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL UNIQUE,
  kind           TEXT NOT NULL,
  url            TEXT,
  adapter        TEXT NOT NULL DEFAULT 'manual',
  /* juridische status bepaalt of de pijplijn hier automatisch mag ophalen */
  legal_status   TEXT NOT NULL DEFAULT 'review'
                 CHECK (legal_status IN ('toegestaan','api_vereist','verboden','review')),
  legal_note     TEXT,
  automated      INTEGER NOT NULL DEFAULT 0,
  cadence_hours  INTEGER NOT NULL DEFAULT 24,
  last_run_at    TEXT,
  active         INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

/* een brief is persona x bron: wat halen we hier op en waarom */
CREATE TABLE IF NOT EXISTS briefs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  persona_id   INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
  source_id    INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  query        TEXT NOT NULL,
  extract      TEXT,
  active       INTEGER NOT NULL DEFAULT 1,
  last_run_at  TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (persona_id, source_id, query)
);

/* ---------- leads ---------- */
CREATE TABLE IF NOT EXISTS leads (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  company        TEXT NOT NULL,
  kvk_number     TEXT,
  website        TEXT,
  contact_name   TEXT,
  contact_role   TEXT,
  email          TEXT,
  email_status   TEXT NOT NULL DEFAULT 'onbekend'
                 CHECK (email_status IN ('onbekend','gevonden','geverifieerd','ongeldig','risico')),
  employees      INTEGER,
  region         TEXT,
  persona_id     INTEGER REFERENCES personas(id) ON DELETE SET NULL,
  source_id      INTEGER REFERENCES sources(id) ON DELETE SET NULL,
  trigger_text   TEXT,
  trigger_url    TEXT,
  found_at       TEXT NOT NULL DEFAULT (datetime('now')),
  stage          TEXT NOT NULL DEFAULT 'scanned',
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_persona ON leads(persona_id);

/* elke trechterovergang wordt vastgelegd, zodat conversie herleidbaar is */
CREATE TABLE IF NOT EXISTS lead_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id    INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  stage      TEXT NOT NULL,
  reason     TEXT,
  at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_lead ON lead_events(lead_id);
CREATE INDEX IF NOT EXISTS idx_events_stage ON lead_events(stage);

/* ---------- campagnes en uitkomsten ---------- */
CREATE TABLE IF NOT EXISTS campaigns (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  persona_id    INTEGER REFERENCES personas(id) ON DELETE SET NULL,
  external_id   TEXT,
  status        TEXT NOT NULL DEFAULT 'concept'
                CHECK (status IN ('concept','live','gepauzeerd','klaar')),
  launched_at   TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS campaign_leads (
  campaign_id  INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  lead_id      INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  sent_at      TEXT,
  PRIMARY KEY (campaign_id, lead_id)
);

CREATE TABLE IF NOT EXISTS outcomes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id    INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  type       TEXT NOT NULL
             CHECK (type IN ('reply','positive','booked','closed','lost','unsubscribe','complaint')),
  value_eur  REAL NOT NULL DEFAULT 0,
  at         TEXT NOT NULL DEFAULT (datetime('now')),
  note       TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcomes_lead ON outcomes(lead_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_type ON outcomes(type);

/* ---------- AVG ---------- */
/* Onderdrukkingslijst. Alles hierin wordt nooit meer benaderd. */
CREATE TABLE IF NOT EXISTS suppression (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kind        TEXT NOT NULL CHECK (kind IN ('email','domain','company','kvk')),
  value       TEXT NOT NULL,
  reason      TEXT NOT NULL
              CHECK (reason IN ('bezwaar','afmelding','klacht','klant','concurrent','handmatig','bounce')),
  note        TEXT,
  added_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (kind, value)
);
CREATE INDEX IF NOT EXISTS idx_suppression_value ON suppression(value);

/* Verwerkingsregister, verplicht onder AVG artikel 30 */
CREATE TABLE IF NOT EXISTS processing_register (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  activity         TEXT NOT NULL,
  purpose          TEXT NOT NULL,
  legal_basis      TEXT NOT NULL,
  categories       TEXT NOT NULL,
  source_desc      TEXT NOT NULL,
  retention_days   INTEGER NOT NULL,
  recipients       TEXT,
  reviewed_at      TEXT NOT NULL DEFAULT (date('now'))
);

/* Verzoeken van betrokkenen: inzage, verwijdering, bezwaar */
CREATE TABLE IF NOT EXISTS data_requests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  email       TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('inzage','verwijdering','bezwaar','rectificatie')),
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','afgehandeld')),
  received_at TEXT NOT NULL DEFAULT (datetime('now')),
  handled_at  TEXT,
  note        TEXT
);

/* Afweging gerechtvaardigd belang. Moet bestaan EN gedateerd zijn voor de
   eerste verzending, anders is er geen grondslag voor persoonsgegevens. */
CREATE TABLE IF NOT EXISTS lia (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  purpose       TEXT NOT NULL,
  source_scope  TEXT NOT NULL,
  belang        TEXT NOT NULL,
  noodzaak      TEXT NOT NULL,
  afweging      TEXT NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1,
  dated_at      TEXT NOT NULL DEFAULT (date('now')),
  active        INTEGER NOT NULL DEFAULT 1
);

/* Verwerkersovereenkomsten, AVG artikel 28, plus doorgifte buiten de EER */
CREATE TABLE IF NOT EXISTS processors (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL UNIQUE,
  purpose        TEXT NOT NULL,
  dpa_signed     INTEGER NOT NULL DEFAULT 0,
  dpa_date       TEXT,
  transfer_basis TEXT,
  land           TEXT,
  note           TEXT
);

/* Onveranderlijk verzendlogboek. Zonder dit kun je achteraf niet
   reconstrueren op welke grondslag een bericht is verstuurd. */
CREATE TABLE IF NOT EXISTS audit_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id       INTEGER,
  email         TEXT NOT NULL,
  legal_basis   TEXT NOT NULL,
  evidence_ref  TEXT,
  lia_id        INTEGER,
  template      TEXT,
  suppressed    INTEGER NOT NULL DEFAULT 0,
  at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_email ON audit_log(email);

/* ---------- kosten ---------- */
CREATE TABLE IF NOT EXISTS costs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  provider    TEXT NOT NULL,
  category    TEXT NOT NULL,
  model       TEXT NOT NULL DEFAULT 'maandelijks'
              CHECK (model IN ('maandelijks','per_eenheid')),
  amount_eur  REAL NOT NULL DEFAULT 0,
  units       INTEGER NOT NULL DEFAULT 0,
  period      TEXT NOT NULL DEFAULT (strftime('%Y-%m','now')),
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_costs_period ON costs(period);
`;

/**
 * Kolommen die later zijn toegevoegd. SQLite kan geen kolom toevoegen die
 * al bestaat, dus we kijken eerst wat er is.
 */
const LATER = [
  ['leads', 'record_class', "TEXT NOT NULL DEFAULT 'ONBEKEND'"],
  ['leads', 'legal_basis', 'TEXT'],
  ['leads', 'designation', "TEXT NOT NULL DEFAULT 'ONBEKEND'"],
  ['leads', 'evidence_url', 'TEXT'],
  ['leads', 'evidence_note', 'TEXT'],
  ['leads', 'acquired_method', 'TEXT'],
  ['leads', 'lia_id', 'INTEGER'],
];

function migrate() {
  db.exec(SCHEMA);
  for (const [tabel, kolom, definitie] of LATER) {
    const bestaand = db.prepare(`PRAGMA table_info(${tabel})`).all().map(r => r.name);
    if (!bestaand.includes(kolom)) db.exec(`ALTER TABLE ${tabel} ADD COLUMN ${kolom} ${definitie}`);
  }
}

/* ==========================================================
   HELPERS
   ========================================================== */
function all(sql, params = []) { return open().prepare(sql).all(...params); }
function get(sql, params = []) { return open().prepare(sql).get(...params); }
function run(sql, params = []) { return open().prepare(sql).run(...params); }

function setSetting(key, value) {
  run(
    `INSERT INTO settings (key,value,updated_at) VALUES (?,?,datetime('now'))
     ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')`,
    [key, String(value)]
  );
}
function getSetting(key, fallback = null) {
  const row = get('SELECT value FROM settings WHERE key = ?', [key]);
  return row ? row.value : fallback;
}
function getNumber(key, fallback) {
  const v = getSetting(key);
  if (v === null || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
function allSettings() {
  const out = {};
  for (const r of all('SELECT key,value FROM settings')) out[r.key] = r.value;
  return out;
}

function reset() {
  const d = open();
  const tables = all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'");
  d.exec('PRAGMA foreign_keys = OFF');
  for (const t of tables) d.exec(`DROP TABLE IF EXISTS ${t.name}`);
  d.exec('PRAGMA foreign_keys = ON');
  migrate();
}

function close() { if (db) { db.close(); db = null; } }

module.exports = { open, all, get, run, setSetting, getSetting, getNumber, allSettings, reset, close, DB_PATH };
