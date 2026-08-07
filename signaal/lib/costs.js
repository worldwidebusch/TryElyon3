'use strict';
/**
 * Signaal / kosten
 *
 * Twee vragen die dit bestand beantwoordt:
 * 1. wat kost een lead, een reactie, een afspraak en een klant
 * 2. bij welke prijs stopt dit met uit kunnen
 *
 * Alle bedragen in euro. Kosten komen in twee vormen: vaste maandlasten
 * en verbruik per eenheid. Verbruik schaalt mee met je volume, vaste
 * lasten niet, en dat verschil bepaalt of opschalen slim is.
 */

const db = require('./db');
const funnel = require('./funnel');

function period(d = new Date()) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** Alle kostenregels van een periode. */
function entries(p = period()) {
  return db.all('SELECT * FROM costs WHERE period = ? ORDER BY category, provider', [p]);
}

function record({ provider, category, model = 'maandelijks', amount_eur = 0, units = 0, note = null, period: p = period() }) {
  const r = db.run(
    'INSERT INTO costs (provider, category, model, amount_eur, units, period, note) VALUES (?,?,?,?,?,?,?)',
    [provider, category, model, amount_eur, units, p, note]
  );
  return db.get('SELECT * FROM costs WHERE id = ?', [Number(r.lastInsertRowid)]);
}

/** Totaal, gesplitst naar vast en variabel. */
function totals(p = period()) {
  const rows = entries(p);
  let vast = 0, variabel = 0;
  const perCategorie = {};
  const perProvider = {};

  for (const r of rows) {
    const bedrag = r.amount_eur || 0;
    if (r.model === 'maandelijks') vast += bedrag; else variabel += bedrag;
    perCategorie[r.category] = (perCategorie[r.category] || 0) + bedrag;
    perProvider[r.provider] = (perProvider[r.provider] || 0) + bedrag;
  }

  const naar = (o) => Object.entries(o)
    .map(([k, v]) => ({ naam: k, bedrag_eur: Number(v.toFixed(2)) }))
    .sort((a, b) => b.bedrag_eur - a.bedrag_eur);

  return {
    periode: p,
    vast_eur: Number(vast.toFixed(2)),
    variabel_eur: Number(variabel.toFixed(2)),
    totaal_eur: Number((vast + variabel).toFixed(2)),
    per_categorie: naar(perCategorie),
    per_provider: naar(perProvider),
  };
}

/**
 * Kosten per uitkomst. Dit is het getal waar het gesprek over moet gaan,
 * niet de maandrekening. Een dure stack die klanten oplevert is goedkoop.
 */
function unitEconomics(p = period()) {
  const t = totals(p);
  const start = `${p}-01`;
  const s = funnel.summary({ since: start });

  const per = (n) => (n > 0 ? Number((t.totaal_eur / n).toFixed(2)) : null);

  const omzet = db.get(
    "SELECT COALESCE(SUM(value_eur),0) AS omzet FROM outcomes WHERE type='closed' AND at >= ?",
    [start]
  )?.omzet || 0;

  return {
    periode: p,
    kosten: t,
    volume: s,
    per_gescande_lead_eur: per(s.gescand),
    per_benaderde_lead_eur: per(s.benaderd),
    per_reactie_eur: per(s.gereageerd),
    per_afspraak_eur: per(s.afspraken),
    per_klant_eur: per(s.klanten),
    omzet_eur: Number(omzet.toFixed(2)),
    marge_eur: Number((omzet - t.totaal_eur).toFixed(2)),
    rendement: t.totaal_eur > 0 ? Number((omzet / t.totaal_eur).toFixed(2)) : null,
  };
}

/**
 * Wat kost het om het maanddoel te halen, en klopt dat met wat een klant
 * oplevert. Hierin zit de enige echt belangrijke waarschuwing: als de
 * kosten per afspraak boven de waarde van een afspraak liggen, is meer
 * volume niet de oplossing maar het probleem.
 */
function projection(doelContacten, p = period()) {
  const u = unitEconomics(p);
  const t = u.kosten;
  const benaderd = u.volume.benaderd || 0;

  // variabele kosten schalen mee, vaste niet
  const variabelPerContact = benaderd > 0 ? t.variabel_eur / benaderd : db.getNumber('geschat_variabel_per_contact_eur', 0.12);
  const geprojecteerd = t.vast_eur + variabelPerContact * doelContacten;

  const replyRate = u.volume.reply_rate || db.getNumber('doel_reply_rate', 0.2);
  const afspraakRate = u.volume.afspraak_rate || 0;
  const verwachteAfspraken = Math.round(doelContacten * (afspraakRate || replyRate * 0.35 * 0.5));

  const waardeAfspraak = db.getNumber('waarde_per_afspraak_eur', 0);
  const kostenPerAfspraak = verwachteAfspraken > 0 ? geprojecteerd / verwachteAfspraken : null;

  let oordeel = null;
  if (waardeAfspraak > 0 && kostenPerAfspraak !== null) {
    if (kostenPerAfspraak >= waardeAfspraak) {
      oordeel = `Kosten per afspraak (${kostenPerAfspraak.toFixed(0)} euro) liggen op of boven de waarde van een afspraak (${waardeAfspraak.toFixed(0)} euro). Opschalen vergroot dan het verlies. Repareer eerst de trechter.`;
    } else {
      oordeel = `Kosten per afspraak (${kostenPerAfspraak.toFixed(0)} euro) liggen onder de waarde (${waardeAfspraak.toFixed(0)} euro). Opschalen is verdedigbaar.`;
    }
  }

  return {
    doel_contacten: doelContacten,
    variabel_per_contact_eur: Number(variabelPerContact.toFixed(4)),
    vaste_lasten_eur: t.vast_eur,
    geprojecteerde_kosten_eur: Number(geprojecteerd.toFixed(2)),
    verwachte_afspraken: verwachteAfspraken,
    kosten_per_afspraak_eur: kostenPerAfspraak !== null ? Number(kostenPerAfspraak.toFixed(2)) : null,
    waarde_per_afspraak_eur: waardeAfspraak || null,
    oordeel,
  };
}

module.exports = { period, entries, record, totals, unitEconomics, projection };
