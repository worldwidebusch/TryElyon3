'use strict';
/**
 * Signaal / domeingezondheid
 *
 * Domeinen zijn het schaarse goed in koude e-mail. Ze zijn niet duur om te
 * kopen maar wel duur om te verbranden, want een verbrand domein kost je
 * drie weken opwarmen voordat de vervanger meedoet.
 *
 * Dit bestand kijkt per domein naar bounce, klachten en reacties, en zegt
 * of het domein door kan, moet rusten, of eruit moet.
 */

const db = require('./db');

/**
 * Grenswaarden. De klachtgrens is de harde: Google hanteert 0,3 procent
 * als bovengrens en 0,1 procent als streefwaarde voor bulkverzenders.
 * Wij gaan daar bewust onder zitten, omdat een enkele slechte dag je
 * gemiddelde al over de grens tilt.
 */
const DEFAULT_LIMITS = {
  max_bounce_rate: 0.03,
  kritiek_bounce_rate: 0.05,
  max_klacht_rate: 0.001,
  kritiek_klacht_rate: 0.003,
  min_reply_rate: 0.01,
  venster_dagen: 14,
  rust_dagen: 14,
};

function limits() {
  const l = {};
  for (const [k, v] of Object.entries(DEFAULT_LIMITS)) l[k] = db.getNumber(k, v);
  return l;
}

/** Meetwaarden per domein over het meetvenster. */
function metrics(vensterDagen) {
  const l = limits();
  const dagen = vensterDagen || l.venster_dagen;

  return db.all(`
    SELECT
      d.id, d.domain, d.status, d.provider, d.tld, d.registered_at,
      d.spf, d.dkim, d.dmarc,
      (SELECT COUNT(*) FROM mailboxes m WHERE m.domain_id = d.id) AS mailboxen,
      COALESCE(SUM(h.sent), 0)         AS verzonden,
      COALESCE(SUM(h.bounced), 0)      AS bounces,
      COALESCE(SUM(h.replied), 0)      AS replies,
      COALESCE(SUM(h.spam_reports), 0) AS klachten
    FROM domains d
    LEFT JOIN domain_health h
      ON h.domain_id = d.id AND h.day >= date('now', ?)
    GROUP BY d.id
    ORDER BY d.domain
  `, [`-${dagen} days`]);
}

/**
 * Beoordeel elk domein en geef een advies.
 * De volgorde van de controles is bewust: authenticatie eerst, want zonder
 * SPF, DKIM en DMARC is de rest van de meting betekenisloos.
 */
function assess(vensterDagen) {
  const l = limits();
  const rows = metrics(vensterDagen);

  return rows.map(d => {
    const verzonden = d.verzonden || 0;
    const bounceRate = verzonden > 0 ? d.bounces / verzonden : 0;
    const klachtRate = verzonden > 0 ? d.klachten / verzonden : 0;
    const replyRate = verzonden > 0 ? d.replies / verzonden : 0;

    const problemen = [];
    let advies = 'doorgaan';
    let ernst = 'ok';

    if (!d.spf || !d.dkim || !d.dmarc) {
      const mist = [!d.spf && 'SPF', !d.dkim && 'DKIM', !d.dmarc && 'DMARC'].filter(Boolean).join(', ');
      problemen.push(`Authenticatie onvolledig: ${mist} ontbreekt. Google en Microsoft weigeren bulkmail zonder deze records.`);
      advies = 'repareren';
      ernst = 'kritiek';
    }

    // te weinig data om iets te vinden
    const genoegData = verzonden >= db.getNumber('domein_min_volume', 100);

    if (genoegData) {
      if (klachtRate >= l.kritiek_klacht_rate) {
        problemen.push(`Klachten ${(klachtRate * 100).toFixed(2)}% boven kritieke grens ${(l.kritiek_klacht_rate * 100).toFixed(2)}%.`);
        advies = 'uitfaseren'; ernst = 'kritiek';
      } else if (klachtRate >= l.max_klacht_rate) {
        problemen.push(`Klachten ${(klachtRate * 100).toFixed(2)}% boven streefwaarde ${(l.max_klacht_rate * 100).toFixed(2)}%.`);
        if (ernst !== 'kritiek') { advies = 'rusten'; ernst = 'waarschuwing'; }
      }

      if (bounceRate >= l.kritiek_bounce_rate) {
        problemen.push(`Bounce ${(bounceRate * 100).toFixed(1)}% boven kritieke grens ${(l.kritiek_bounce_rate * 100).toFixed(1)}%. Dit wijst op slechte verificatie, niet op een slecht domein.`);
        if (advies !== 'uitfaseren') { advies = 'rusten'; }
        ernst = 'kritiek';
      } else if (bounceRate >= l.max_bounce_rate) {
        problemen.push(`Bounce ${(bounceRate * 100).toFixed(1)}% boven streefwaarde ${(l.max_bounce_rate * 100).toFixed(1)}%.`);
        if (ernst === 'ok') { advies = 'rusten'; ernst = 'waarschuwing'; }
      }

      if (replyRate < l.min_reply_rate && d.status === 'active') {
        problemen.push(`Reacties ${(replyRate * 100).toFixed(2)}% onder ${(l.min_reply_rate * 100).toFixed(2)}%. Kan aan het domein liggen, maar kijk eerst naar de doelgroep en de tekst.`);
        if (ernst === 'ok') { advies = 'onderzoeken'; ernst = 'let_op'; }
      }
    }

    return {
      ...d,
      venster_dagen: vensterDagen || l.venster_dagen,
      bounce_rate: Number(bounceRate.toFixed(4)),
      klacht_rate: Number(klachtRate.toFixed(4)),
      reply_rate: Number(replyRate.toFixed(4)),
      genoeg_data: genoegData,
      ernst,
      advies,
      problemen,
    };
  });
}

/** Alles wat aandacht nodig heeft, gesorteerd op ernst. */
function attention(vensterDagen) {
  const rang = { kritiek: 0, waarschuwing: 1, let_op: 2, ok: 3 };
  return assess(vensterDagen)
    .filter(d => d.ernst !== 'ok')
    .sort((a, b) => rang[a.ernst] - rang[b.ernst]);
}

/** Zet een domein op rust of faseer het uit, inclusief de mailboxen. */
function setStatus(domainId, status, note = null) {
  const geldig = ['warming', 'active', 'resting', 'retired'];
  if (!geldig.includes(status)) throw new Error(`ongeldige status: ${status}`);

  db.run('UPDATE domains SET status = ?, notes = COALESCE(?, notes) WHERE id = ?', [status, note, domainId]);
  // mailboxen volgen het domein, anders blijft de capaciteitsberekening liegen
  if (status === 'resting' || status === 'retired') {
    db.run('UPDATE mailboxes SET status = ? WHERE domain_id = ?', [status, domainId]);
  } else if (status === 'active') {
    db.run("UPDATE mailboxes SET status = 'active' WHERE domain_id = ? AND status IN ('resting')", [domainId]);
  }
  return db.get('SELECT * FROM domains WHERE id = ?', [domainId]);
}

/** Voer de adviezen automatisch uit. Alleen aanzetten als je het vertrouwt. */
function applyRecommendations({ dryRun = true } = {}) {
  const beoordeeld = assess();
  const gedaan = [];

  for (const d of beoordeeld) {
    let doel = null;
    if (d.advies === 'uitfaseren') doel = 'retired';
    else if (d.advies === 'rusten' && d.status === 'active') doel = 'resting';
    if (!doel || d.status === doel) continue;

    gedaan.push({ domain: d.domain, van: d.status, naar: doel, reden: d.problemen.join(' ') });
    if (!dryRun) setStatus(d.id, doel, d.problemen.join(' '));
  }
  return { dryRun, aantal: gedaan.length, wijzigingen: gedaan };
}

/** Weekrapport, het equivalent van het Slack-bericht uit de opzet. */
function weeklyReport() {
  const beoordeeld = assess(7);
  const totaal = beoordeeld.reduce((a, d) => ({
    verzonden: a.verzonden + d.verzonden,
    bounces: a.bounces + d.bounces,
    klachten: a.klachten + d.klachten,
    replies: a.replies + d.replies,
  }), { verzonden: 0, bounces: 0, klachten: 0, replies: 0 });

  return {
    periode: '7 dagen',
    domeinen: beoordeeld.length,
    totaal,
    gemiddelde: {
      bounce_rate: totaal.verzonden ? Number((totaal.bounces / totaal.verzonden).toFixed(4)) : 0,
      klacht_rate: totaal.verzonden ? Number((totaal.klachten / totaal.verzonden).toFixed(4)) : 0,
      reply_rate: totaal.verzonden ? Number((totaal.replies / totaal.verzonden).toFixed(4)) : 0,
    },
    aandacht: beoordeeld.filter(d => d.ernst !== 'ok').map(d => ({
      domain: d.domain, ernst: d.ernst, advies: d.advies, problemen: d.problemen,
    })),
  };
}

module.exports = { DEFAULT_LIMITS, limits, metrics, assess, attention, setStatus, applyRecommendations, weeklyReport };
