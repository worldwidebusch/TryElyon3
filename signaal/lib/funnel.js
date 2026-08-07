'use strict';
/**
 * Signaal / trechteranalyse
 *
 * De trechter is het stuurinstrument. Niet omdat de percentages leuk zijn,
 * maar omdat je eraan kunt zien welke ene stap je moet repareren om alles
 * erna te laten stijgen. Daarom rekent dit bestand niet alleen conversie
 * uit, maar ook wat een verbetering van een stap oplevert aan de onderkant.
 */

const db = require('./db');

/** Vaste volgorde. Een lead doorloopt deze stappen, of valt onderweg af. */
const STAGES = [
  { key: 'scanned',    label: 'Gescand',            uitleg: 'Gevonden in een bron' },
  { key: 'email_found',label: 'E-mail gevonden',    uitleg: 'Er is een adres achterhaald' },
  { key: 'verified',   label: 'Geverifieerd',       uitleg: 'Adres bestaat en bounced niet' },
  { key: 'sendable',   label: 'Verzendbaar',        uitleg: 'Niet onderdrukt, geen dubbele, geen klant' },
  { key: 'pushed',     label: 'In campagne',        uitleg: 'Geladen in het verzendplatform' },
  { key: 'contacted',  label: 'Benaderd',           uitleg: 'Bericht daadwerkelijk verstuurd' },
  { key: 'replied',    label: 'Gereageerd',         uitleg: 'Enige reactie ontvangen' },
  { key: 'positive',   label: 'Positief',           uitleg: 'Reactie met interesse' },
  { key: 'booked',     label: 'Afspraak',           uitleg: 'Gesprek ingepland' },
  { key: 'closed',     label: 'Klant',              uitleg: 'Getekend' },
];

const STAGE_KEYS = STAGES.map(s => s.key);

function stageIndex(key) { return STAGE_KEYS.indexOf(key); }

/**
 * Aantal leads dat een stap ooit heeft bereikt.
 * We tellen op lead_events, niet op leads.stage, omdat een lead die
 * doorgestroomd is naar 'booked' ook 'contacted' bereikt heeft.
 */
function counts(where = {}) {
  const params = [];
  let filter = '';
  if (where.since) { filter += ' AND e.at >= ?'; params.push(where.since); }
  if (where.persona_id) { filter += ' AND l.persona_id = ?'; params.push(where.persona_id); }
  if (where.source_id) { filter += ' AND l.source_id = ?'; params.push(where.source_id); }

  const rows = db.all(`
    SELECT e.stage AS stage, COUNT(DISTINCT e.lead_id) AS n
    FROM lead_events e
    JOIN leads l ON l.id = e.lead_id
    WHERE 1=1 ${filter}
    GROUP BY e.stage
  `, params);

  const map = Object.fromEntries(rows.map(r => [r.stage, r.n]));
  return STAGE_KEYS.map(k => ({ stage: k, n: map[k] || 0 }));
}

/**
 * Volledige trechter met conversie per stap.
 * Conversie is altijd ten opzichte van de vorige stap, zoals je hem leest.
 */
function build(where = {}) {
  const c = counts(where);
  const out = [];

  for (let i = 0; i < STAGES.length; i++) {
    const meta = STAGES[i];
    const n = c[i].n;
    const prev = i === 0 ? n : c[i - 1].n;
    const conv = prev > 0 ? n / prev : 0;
    const top = c[0].n;
    out.push({
      ...meta,
      stage: meta.key,   // meta gebruikt 'key', de rest van de code leest 'stage'
      n,
      van_vorige: i === 0 ? 1 : conv,
      van_top: top > 0 ? n / top : 0,
      verloren: i === 0 ? 0 : Math.max(0, prev - n),
    });
  }
  return out;
}

/**
 * Waar zit de knel, en wat levert repareren op.
 *
 * Voor elke stap: als de conversie met `delta` stijgt, hoeveel extra leads
 * komen er dan onderaan uit? Dat is het getal waarop je moet sturen, niet
 * op het laagste percentage. Een slechte conversie bovenin een brede
 * trechter is veel meer waard dan een slechte conversie onderin een smalle.
 */
/**
 * Terugvalpercentages, gebruikt wanneer een stap te weinig data heeft om
 * een betrouwbaar percentage uit af te leiden. Zonder deze terugval zou
 * één lege stap onderin de hele analyse op nul zetten, want dan
 * vermenigvuldig je alles erboven met nul.
 */
const FALLBACK = {
  email_found: 0.55, verified: 0.85, sendable: 0.75, pushed: 0.95,
  contacted: 0.98, replied: 0.15, positive: 0.35, booked: 0.50, closed: 0.20,
};

function bottlenecks(where = {}, delta = 0.1, doelStap = 'booked', minSample = 30) {
  const f = build(where);
  const doelIdx = stageIndex(doelStap);
  if (doelIdx < 1) throw new Error(`ongeldige doelstap: ${doelStap}`);

  const items = [];

  for (let i = 1; i <= doelIdx; i++) {
    const stap = f[i];
    const instroom = f[i - 1].n;
    if (instroom === 0) continue;

    // Conversie van deze stap tot aan de doelstap. Waar te weinig data is,
    // gebruiken we de terugval en zeggen we erbij dat het een schatting is.
    let naarDoel = 1;
    let geschat = false;
    for (let j = i + 1; j <= doelIdx; j++) {
      if (f[j - 1].n < minSample) { naarDoel *= FALLBACK[f[j].stage] ?? 0.5; geschat = true; }
      else naarDoel *= f[j].van_vorige;
    }

    const huidige = stap.van_vorige;
    const nieuwe = Math.min(1, huidige + delta);
    const extraHier = instroom * (nieuwe - huidige);
    const extraDoel = extraHier * naarDoel;

    items.push({
      stage: stap.stage,
      label: stap.label,
      instroom,
      conversie: huidige,
      verloren: stap.verloren,
      bij_plus_delta: nieuwe,
      extra_op_deze_stap: Math.round(extraHier),
      doelstap: doelStap,
      extra_op_doel: Number(extraDoel.toFixed(2)),
      // een schatting is bruikbaar om op te sturen, maar niet om op te rekenen
      geschat,
      betrouwbaar: !geschat && instroom >= minSample,
    });
  }

  items.sort((a, b) => b.extra_op_doel - a.extra_op_doel);
  const zeker = items.filter(i => i.betrouwbaar);
  return {
    delta,
    doelstap: doelStap,
    items,
    top: zeker[0] || items[0] || null,
    // expliciet, zodat het dashboard geen zekerheid suggereert die er niet is
    waarschuwing: zeker.length === 0
      ? 'Geen enkele stap heeft genoeg volume voor een betrouwbaar oordeel. De volgorde hieronder is een schatting.'
      : null,
  };
}

/** Registreer dat een lead een stap bereikt heeft. Idempotent per stap. */
function record(leadId, stage, reason = null) {
  if (!STAGE_KEYS.includes(stage)) throw new Error(`onbekende stap: ${stage}`);
  const bestaat = db.get('SELECT id FROM lead_events WHERE lead_id = ? AND stage = ?', [leadId, stage]);
  if (!bestaat) {
    db.run('INSERT INTO lead_events (lead_id, stage, reason) VALUES (?,?,?)', [leadId, stage, reason]);
  }
  // leads.stage houdt de verst bereikte stap vast
  const lead = db.get('SELECT stage FROM leads WHERE id = ?', [leadId]);
  if (lead && stageIndex(stage) > stageIndex(lead.stage)) {
    db.run('UPDATE leads SET stage = ? WHERE id = ?', [stage, leadId]);
  }
  return true;
}

/** Samenvatting voor bovenaan het dashboard. */
function summary(where = {}) {
  const f = build(where);
  const byKey = Object.fromEntries(f.map(s => [s.stage, s]));
  const contacted = byKey.contacted.n;
  return {
    gescand: byKey.scanned.n,
    benaderd: contacted,
    gereageerd: byKey.replied.n,
    afspraken: byKey.booked.n,
    klanten: byKey.closed.n,
    reply_rate: contacted > 0 ? byKey.replied.n / contacted : 0,
    afspraak_rate: contacted > 0 ? byKey.booked.n / contacted : 0,
    scan_naar_benaderd: byKey.scanned.n > 0 ? contacted / byKey.scanned.n : 0,
  };
}

module.exports = { STAGES, STAGE_KEYS, build, counts, bottlenecks, record, summary, stageIndex };
