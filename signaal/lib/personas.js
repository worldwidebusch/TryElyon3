'use strict';
/**
 * Signaal / persona's, de gesloten lus
 *
 * Het punt van dit bestand: een persona wordt niet beoordeeld op reacties
 * maar op omzet. Reacties zijn goedkoop en misleidend. Wie tekent bepaalt
 * waar we morgen zoeken.
 *
 * De lus is: contacten -> uitkomsten -> score per persona -> de winnaars
 * krijgen meer briefs en een verfijnde opvolger, de verliezers gaan uit.
 */

const db = require('./db');

/**
 * Wegingen. Een klant weegt honderd keer zwaarder dan een reactie, want
 * dat is ongeveer de verhouding waarin ze voorkomen en tellen.
 * Klachten wegen negatief: een persona die klachten oplevert kost je
 * domeinen, en domeinen zijn duurder dan leads.
 */
const WEIGHTS = {
  closed: 100,
  booked: 25,
  positive: 5,
  reply: 1,
  lost: 0,
  unsubscribe: -5,
  complaint: -25,
};

/** Ruwe cijfers per persona over alle leads die ooit benaderd zijn. */
function stats(where = {}) {
  const params = [];
  let filter = '';
  if (where.since) { filter += ' AND l.found_at >= ?'; params.push(where.since); }

  const rows = db.all(`
    SELECT
      p.id, p.name, p.version, p.segment, p.status, p.hypothesis,
      COUNT(DISTINCT l.id) AS leads,
      COUNT(DISTINCT CASE WHEN ce.stage = 'contacted' THEN l.id END) AS benaderd,
      COUNT(DISTINCT CASE WHEN o.type = 'reply'    THEN o.id END) AS replies,
      COUNT(DISTINCT CASE WHEN o.type = 'positive' THEN o.id END) AS positief,
      COUNT(DISTINCT CASE WHEN o.type = 'booked'   THEN o.id END) AS afspraken,
      COUNT(DISTINCT CASE WHEN o.type = 'closed'   THEN o.id END) AS klanten,
      COUNT(DISTINCT CASE WHEN o.type = 'complaint' THEN o.id END) AS klachten,
      COUNT(DISTINCT CASE WHEN o.type = 'unsubscribe' THEN o.id END) AS afmeldingen,
      COALESCE(SUM(CASE WHEN o.type = 'closed' THEN o.value_eur ELSE 0 END), 0) AS omzet_eur
    FROM personas p
    LEFT JOIN leads l ON l.persona_id = p.id ${filter ? filter.replace(/ AND /g, ' AND ') : ''}
    LEFT JOIN lead_events ce ON ce.lead_id = l.id AND ce.stage = 'contacted'
    LEFT JOIN outcomes o ON o.lead_id = l.id
    GROUP BY p.id
    ORDER BY p.name, p.version
  `, params);

  return rows;
}

/**
 * Score per persona. Genormaliseerd op benaderde leads, want een persona
 * met tien keer zoveel volume hoort niet automatisch te winnen.
 */
function score(where = {}) {
  const rows = stats(where);
  const minVolume = db.getNumber('persona_min_volume', 40);

  const scored = rows.map(r => {
    const benaderd = r.benaderd || 0;
    const punten =
      r.klanten * WEIGHTS.closed +
      r.afspraken * WEIGHTS.booked +
      r.positief * WEIGHTS.positive +
      r.replies * WEIGHTS.reply +
      r.afmeldingen * WEIGHTS.unsubscribe +
      r.klachten * WEIGHTS.complaint;

    const perContact = benaderd > 0 ? punten / benaderd : 0;
    const omzetPerContact = benaderd > 0 ? r.omzet_eur / benaderd : 0;

    return {
      ...r,
      punten,
      score: Number(perContact.toFixed(3)),
      omzet_per_contact_eur: Number(omzetPerContact.toFixed(2)),
      reply_rate: benaderd > 0 ? Number((r.replies / benaderd).toFixed(4)) : 0,
      afspraak_rate: benaderd > 0 ? Number((r.afspraken / benaderd).toFixed(4)) : 0,
      klant_rate: benaderd > 0 ? Number((r.klanten / benaderd).toFixed(4)) : 0,
      klacht_rate: benaderd > 0 ? Number((r.klachten / benaderd).toFixed(4)) : 0,
      // Onder de drempel is de score ruis. Dat zeggen we er expliciet bij,
      // anders ga je sturen op drie toevallige klanten.
      betrouwbaar: benaderd >= minVolume,
      volume_drempel: minVolume,
    };
  });

  scored.sort((a, b) => {
    if (a.betrouwbaar !== b.betrouwbaar) return a.betrouwbaar ? -1 : 1;
    return b.score - a.score;
  });
  return scored;
}

/**
 * Aanbeveling per persona: opschalen, aanhouden, verfijnen of stoppen.
 * Dit is de stap die de lus sluit.
 */
function recommend(where = {}) {
  const scored = score(where);
  const betrouwbaar = scored.filter(s => s.betrouwbaar);
  if (betrouwbaar.length === 0) {
    return {
      klaar: false,
      reden: `Nog geen enkele persona heeft de volumedrempel van ${db.getNumber('persona_min_volume', 40)} benaderde leads gehaald. Tot die tijd is elke ranglijst toeval.`,
      acties: [],
    };
  }

  const mediaan = betrouwbaar[Math.floor(betrouwbaar.length / 2)].score;
  const beste = betrouwbaar[0].score;
  const klachtGrens = db.getNumber('max_klacht_rate', 0.003);

  const acties = betrouwbaar.map(p => {
    let actie, reden;
    if (p.klacht_rate > klachtGrens) {
      actie = 'stoppen';
      reden = `Klachtpercentage ${(p.klacht_rate * 100).toFixed(2)}% ligt boven de grens van ${(klachtGrens * 100).toFixed(2)}%. Dit segment kost je domeinen.`;
    } else if (p.score >= beste * 0.8) {
      actie = 'opschalen';
      reden = `Score ${p.score} zit in de kopgroep. Meer briefs op deze persona, en een verfijnde versie maken.`;
    } else if (p.score >= mediaan) {
      actie = 'aanhouden';
      reden = `Score ${p.score} rond de mediaan. Laten lopen, niet uitbreiden.`;
    } else if (p.klanten === 0 && p.afspraken === 0) {
      actie = 'stoppen';
      reden = `Geen enkele afspraak of klant uit ${p.benaderd} contacten. Reacties alleen betalen de rekening niet.`;
    } else {
      actie = 'verfijnen';
      reden = `Score ${p.score} onder de mediaan, maar er zit wel resultaat in. Smaller maken op wat wel werkte.`;
    }
    return { persona_id: p.id, naam: p.name, versie: p.version, score: p.score, actie, reden };
  });

  return { klaar: true, mediaan, beste, acties };
}

/**
 * Maak een opvolger van een persona. De lus in de praktijk: je gooit de
 * oude niet weg, je zet een smallere versie ernaast en vergelijkt.
 */
function refine(personaId, { segment, sbi_codes, size_min, size_max, regions, hypothesis } = {}) {
  const ouder = db.get('SELECT * FROM personas WHERE id = ?', [personaId]);
  if (!ouder) throw new Error('persona bestaat niet');

  const hoogste = db.get('SELECT MAX(version) AS v FROM personas WHERE name = ?', [ouder.name]);
  const versie = (hoogste?.v || ouder.version) + 1;

  const r = db.run(`
    INSERT INTO personas (name, version, parent_id, segment, sbi_codes, size_min, size_max, regions, hypothesis, status)
    VALUES (?,?,?,?,?,?,?,?,?,'testing')
  `, [
    ouder.name, versie, ouder.id,
    segment ?? ouder.segment,
    sbi_codes ?? ouder.sbi_codes,
    size_min ?? ouder.size_min,
    size_max ?? ouder.size_max,
    regions ?? ouder.regions,
    hypothesis ?? `Verfijning van versie ${ouder.version}`,
  ]);

  return db.get('SELECT * FROM personas WHERE id = ?', [Number(r.lastInsertRowid)]);
}

/**
 * Welke kenmerken hebben de klanten gemeen die daadwerkelijk getekend
 * hebben. Dit is de input voor een verfijning, en in de echte opzet ook
 * de input voor het onderzoek via de zoek-API.
 */
function winnerProfile() {
  const winnaars = db.all(`
    SELECT l.*, s.name AS bron
    FROM leads l
    JOIN outcomes o ON o.lead_id = l.id AND o.type IN ('closed','booked')
    LEFT JOIN sources s ON s.id = l.source_id
  `);
  if (winnaars.length === 0) return { aantal: 0, patronen: null };

  const tel = (veld) => {
    const m = {};
    for (const w of winnaars) {
      const v = w[veld];
      if (v === null || v === undefined || v === '') continue;
      m[v] = (m[v] || 0) + 1;
    }
    return Object.entries(m).sort((a, b) => b[1] - a[1]).map(([k, n]) => ({ waarde: k, n }));
  };

  const groottes = winnaars.map(w => w.employees).filter(n => Number.isFinite(n)).sort((a, b) => a - b);

  return {
    aantal: winnaars.length,
    patronen: {
      regio: tel('region'),
      bron: tel('bron'),
      rol: tel('contact_role'),
      grootte: groottes.length ? {
        min: groottes[0],
        mediaan: groottes[Math.floor(groottes.length / 2)],
        max: groottes[groottes.length - 1],
      } : null,
    },
  };
}

module.exports = { WEIGHTS, stats, score, recommend, refine, winnerProfile };
