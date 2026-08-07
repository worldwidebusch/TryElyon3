'use strict';
/**
 * Signaal / capaciteitsplanning
 *
 * Rekent een maanddoel terug naar verzendinfrastructuur: hoeveel mailboxen
 * en domeinen heb je nodig, wat heb je nu, en wat kom je tekort.
 *
 * Alle grenswaarden staan in settings, zodat je ze kunt bijstellen zonder
 * de code aan te raken. De standaardwaarden staan bewust conservatief:
 * te hard verzenden verbrandt domeinen sneller dan je ze kunt bijkopen.
 */

const db = require('./db');

/* Standaarden. Bewust aan de voorzichtige kant. */
const DEFAULTS = {
  werkdagen_per_maand: 21.7,        // 261 werkdagen per jaar gedeeld door 12
  sends_per_mailbox_per_dag: 20,    // koud verkeer, niet warm
  mailboxen_per_domein: 3,          // meer dan dit koppelt de reputatie te strak
  warmup_dagen: 21,                 // tot volle capaciteit
  warmup_start_ratio: 0.15,         // waar een nieuwe mailbox begint
  levertijd_dagen: 2,               // domein geregistreerd tot mailbox bruikbaar
};

function settings() {
  const s = {};
  for (const [k, v] of Object.entries(DEFAULTS)) s[k] = db.getNumber(k, v);
  return s;
}

function daysBetween(from, to = new Date()) {
  if (!from) return 0;
  const a = new Date(from + (from.length === 10 ? 'T00:00:00Z' : 'Z'));
  if (Number.isNaN(a.getTime())) return 0;
  return Math.max(0, Math.floor((to.getTime() - a.getTime()) / 86400000));
}

/**
 * Effectieve dagcapaciteit van een mailbox, rekening houdend met opwarmen.
 * Een mailbox die gisteren is aangemaakt levert nog bijna niets.
 */
function effectiveCap(mailbox, s = settings()) {
  if (mailbox.status === 'retired' || mailbox.status === 'resting') return 0;
  const cap = mailbox.daily_cap || s.sends_per_mailbox_per_dag;
  if (mailbox.status === 'active') return cap;
  // warming
  const d = daysBetween(mailbox.warmup_start);
  const ratio = s.warmup_start_ratio + (1 - s.warmup_start_ratio) * Math.min(1, d / s.warmup_dagen);
  return Math.round(cap * Math.min(1, Math.max(s.warmup_start_ratio, ratio)));
}

/** Wat kan de infrastructuur vandaag daadwerkelijk aan. */
function currentCapacity() {
  const s = settings();
  const mailboxes = db.all(`
    SELECT m.*, d.domain, d.status AS domain_status
    FROM mailboxes m JOIN domains d ON d.id = m.domain_id
  `);

  let today = 0, ceiling = 0, warming = 0, active = 0, resting = 0;
  for (const m of mailboxes) {
    // een mailbox op een rustend of uitgefaseerd domein telt niet mee
    const blocked = m.domain_status === 'resting' || m.domain_status === 'retired';
    if (blocked || m.status === 'resting' || m.status === 'retired') { resting++; continue; }
    today += effectiveCap(m, s);
    ceiling += m.daily_cap || s.sends_per_mailbox_per_dag;
    if (m.status === 'warming') warming++; else active++;
  }

  const domains = db.get(`
    SELECT
      COUNT(*) AS totaal,
      SUM(CASE WHEN status='active'  THEN 1 ELSE 0 END) AS actief,
      SUM(CASE WHEN status='warming' THEN 1 ELSE 0 END) AS opwarmend,
      SUM(CASE WHEN status='resting' THEN 1 ELSE 0 END) AS rustend,
      SUM(CASE WHEN status='retired' THEN 1 ELSE 0 END) AS uitgefaseerd
    FROM domains
  `) || {};

  return {
    per_dag_nu: today,
    per_dag_plafond: ceiling,
    per_maand_nu: Math.round(today * s.werkdagen_per_maand),
    per_maand_plafond: Math.round(ceiling * s.werkdagen_per_maand),
    mailboxen: { totaal: mailboxes.length, actief: active, opwarmend: warming, buiten_gebruik: resting },
    domeinen: domains,
  };
}

/**
 * Reken een maanddoel terug naar benodigde infrastructuur.
 * Doel kan opgegeven worden als aantal contacten, of als aantal gewenste
 * afspraken waarbij we via de trechterpercentages terugrekenen.
 */
function plan(input = {}) {
  const s = settings();
  const cur = currentCapacity();

  let doelContacten = Number(input.contacten_per_maand) || 0;
  const afspraken = Number(input.afspraken_per_maand) || 0;

  // percentages als fractie (0.22 = 22%)
  const replyRate = Number(input.reply_rate) || db.getNumber('doel_reply_rate', 0.2);
  const positiefVanReply = Number(input.positief_van_reply) || db.getNumber('doel_positief_van_reply', 0.35);
  const afspraakVanPositief = Number(input.afspraak_van_positief) || db.getNumber('doel_afspraak_van_positief', 0.5);

  let afgeleid = null;
  if (!doelContacten && afspraken > 0) {
    const perContact = replyRate * positiefVanReply * afspraakVanPositief;
    if (perContact > 0) {
      doelContacten = Math.ceil(afspraken / perContact);
      afgeleid = { vanuit: 'afspraken', afspraken, afspraken_per_contact: perContact };
    }
  }
  if (!doelContacten) doelContacten = db.getNumber('doel_contacten_per_maand', 7000);

  const perDagNodig = Math.ceil(doelContacten / s.werkdagen_per_maand);
  const mailboxenNodig = Math.ceil(perDagNodig / s.sends_per_mailbox_per_dag);
  const domeinenNodig = Math.ceil(mailboxenNodig / s.mailboxen_per_domein);

  const tekortPerDag = Math.max(0, perDagNodig - cur.per_dag_nu);
  const tekortPlafond = Math.max(0, perDagNodig - cur.per_dag_plafond);

  // Bijbestellen baseren we op het plafond, niet op de dagstand van vandaag.
  // Anders koop je domeinen bij terwijl bestaande mailboxen nog opwarmen.
  const mailboxenBij = Math.ceil(tekortPlafond / s.sends_per_mailbox_per_dag);
  const domeinenBij = Math.ceil(mailboxenBij / s.mailboxen_per_domein);

  const verwacht = {
    replies: Math.round(doelContacten * replyRate),
    positief: Math.round(doelContacten * replyRate * positiefVanReply),
    afspraken: Math.round(doelContacten * replyRate * positiefVanReply * afspraakVanPositief),
  };

  return {
    doel: {
      contacten_per_maand: doelContacten,
      per_dag_nodig: perDagNodig,
      afgeleid,
      aannames: { reply_rate: replyRate, positief_van_reply: positiefVanReply, afspraak_van_positief: afspraakVanPositief },
    },
    verwacht,
    benodigd: { mailboxen: mailboxenNodig, domeinen: domeinenNodig },
    huidig: cur,
    tekort: {
      per_dag_vandaag: tekortPerDag,
      per_dag_op_plafond: tekortPlafond,
      mailboxen_bijbestellen: mailboxenBij,
      domeinen_bijbestellen: domeinenBij,
      // opwarmen kost tijd: dit is wanneer bijbestelde capaciteit echt meedoet
      beschikbaar_over_dagen: mailboxenBij > 0 ? s.levertijd_dagen + s.warmup_dagen : 0,
    },
    haalbaar_zonder_bijbestellen: tekortPlafond === 0,
    instellingen: s,
  };
}

/** Concreet bestelvoorstel, klaar om aan een domeinprovider te geven. */
function orderProposal(input = {}) {
  const p = plan(input);
  const s = p.instellingen;
  const domeinen = p.tekort.domeinen_bijbestellen;
  const mailboxen = p.tekort.mailboxen_bijbestellen;

  const kostenPerDomein = db.getNumber('kosten_per_domein_eur', 12);
  const kostenPerMailbox = db.getNumber('kosten_per_mailbox_eur', 3);

  return {
    nodig: domeinen > 0 || mailboxen > 0,
    domeinen,
    mailboxen,
    mailboxen_per_domein: s.mailboxen_per_domein,
    geschatte_kosten_eur: Math.round(domeinen * kostenPerDomein + mailboxen * kostenPerMailbox),
    geschatte_maandlast_eur: Math.round(mailboxen * kostenPerMailbox),
    productief_over_dagen: p.tekort.beschikbaar_over_dagen,
    waarschuwing: domeinen > 0
      ? `Nieuwe domeinen leveren pas na ongeveer ${s.levertijd_dagen + s.warmup_dagen} dagen volle capaciteit. Bestel dus voordat je het tekort hebt, niet erna.`
      : null,
  };
}

module.exports = { plan, currentCapacity, orderProposal, effectiveCap, settings, DEFAULTS };
