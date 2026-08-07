#!/usr/bin/env node
'use strict';
/**
 * Signaal / server
 *
 * Nul afhankelijkheden: alleen node:http en node:sqlite. Geen npm install,
 * geen buildstap. Starten met:
 *
 *   node signaal/server.js
 *
 * Draait standaard op http://localhost:8787
 */

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const db = require('./lib/db');
const capacity = require('./lib/capacity');
const funnel = require('./lib/funnel');
const personas = require('./lib/personas');
const sources = require('./lib/sources');
const domains = require('./lib/domains');
const costs = require('./lib/costs');
const compliance = require('./lib/compliance');
const wet = require('./lib/wetgeving');
const adapters = require('./lib/adapters');

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '127.0.0.1';
const PUBLIC = path.join(__dirname, 'public');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
};

function json(res, data, status = 200) {
  const body = JSON.stringify(data, null, 2);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', c => {
      data += c;
      if (data.length > 1e6) { reject(new Error('body te groot')); req.destroy(); }
    });
    req.on('end', () => {
      if (!data) return resolve({});
      try { resolve(JSON.parse(data)); } catch { reject(new Error('ongeldige JSON')); }
    });
    req.on('error', reject);
  });
}

/* ==========================================================
   ROUTES
   ========================================================== */

const routes = {
  'GET /api/overzicht': () => {
    const plan = capacity.plan();
    const nalev = compliance.status();
    return {
      trechter: funnel.summary(),
      capaciteit: {
        per_dag_nu: plan.huidig.per_dag_nu,
        per_dag_nodig: plan.doel.per_dag_nodig,
        per_dag_plafond: plan.huidig.per_dag_plafond,
        doel_per_maand: plan.doel.contacten_per_maand,
        haalbaar: plan.haalbaar_zonder_bijbestellen,
        domeinen: plan.huidig.domeinen,
      },
      naleving: { mag_verzenden: nalev.mag_verzenden, blokkades: nalev.blokkades.length, open_verzoeken: nalev.open_verzoeken },
      domeinen_aandacht: domains.attention().length,
      kosten: costs.unitEconomics(),
      koppelingen: adapters.status(),
      demo_modus: !adapters.anyLive(),
    };
  },

  'GET /api/trechter': (q) => ({
    stappen: funnel.build(filter(q)),
    knelpunten: funnel.bottlenecks(filter(q), Number(q.delta) || 0.1, q.doel || 'booked'),
    samenvatting: funnel.summary(filter(q)),
  }),

  'GET /api/capaciteit': (q) => capacity.plan({
    contacten_per_maand: q.contacten ? Number(q.contacten) : undefined,
    afspraken_per_maand: q.afspraken ? Number(q.afspraken) : undefined,
  }),

  'GET /api/capaciteit/bestellen': (q) => adapters.domeinprovider.voorstelBestelling(
    (() => {
      const p = capacity.plan({
        contacten_per_maand: q.contacten ? Number(q.contacten) : undefined,
        afspraken_per_maand: q.afspraken ? Number(q.afspraken) : undefined,
      });
      return { domeinen: p.tekort.domeinen_bijbestellen, mailboxenPerDomein: p.instellingen.mailboxen_per_domein };
    })()
  ).then(v => ({ ...v, voorstel: capacity.orderProposal({
    contacten_per_maand: q.contacten ? Number(q.contacten) : undefined,
    afspraken_per_maand: q.afspraken ? Number(q.afspraken) : undefined,
  }) })),

  'GET /api/personas': () => ({
    scores: personas.score(),
    aanbeveling: personas.recommend(),
    winnaars: personas.winnerProfile(),
    wegingen: personas.WEIGHTS,
  }),

  'POST /api/personas/verfijnen': async (q, body) => personas.refine(Number(body.persona_id), body),

  'GET /api/bronnen': () => ({
    bronnen: sources.list(),
    juridisch: sources.legalOverview(),
    briefs: sources.briefs({ activeOnly: true }),
    klaar_om_te_draaien: sources.due().map(s => s.name),
  }),

  'POST /api/bronnen/automatisch': async (q, body) => sources.setAutomated(Number(body.id), Boolean(body.automated)),
  'POST /api/bronnen/status': async (q, body) => sources.setLegalStatus(Number(body.id), body.status, body.note),

  'GET /api/domeinen': () => ({
    domeinen: domains.assess(),
    aandacht: domains.attention(),
    weekrapport: domains.weeklyReport(),
    voorstel: domains.applyRecommendations({ dryRun: true }),
    grenzen: domains.limits(),
  }),

  'POST /api/domeinen/status': async (q, body) => domains.setStatus(Number(body.id), body.status, body.note),
  'POST /api/domeinen/toepassen': async (q, body) => domains.applyRecommendations({ dryRun: body.dryRun !== false }),

  'GET /api/kosten': (q) => ({
    economie: costs.unitEconomics(q.periode),
    regels: costs.entries(q.periode),
    projectie: costs.projection(Number(q.doel) || db.getNumber('doel_contacten_per_maand', 7000), q.periode),
  }),

  'GET /api/naleving': () => ({
    status: compliance.status(),
    onderdrukking: compliance.suppressionList({ limit: 50 }),
    register: compliance.register(),
    bewaartermijn: compliance.retentionSweep({ dryRun: true }),
    redenen: compliance.REDENEN,
  }),

  'POST /api/naleving/onderdrukken': async (q, body) => compliance.suppress(body),
  'POST /api/naleving/verzoek': async (q, body) => compliance.logRequest(body),
  'GET /api/naleving/inzage': (q) => compliance.exportSubject(q.email),
  'POST /api/naleving/verwijderen': async (q, body) => compliance.eraseSubject(body.email),
  'POST /api/naleving/opschonen': async (q, body) => compliance.retentionSweep({ dryRun: body.dryRun !== false }),

  /**
   * Verzendcontrole. Dit eindpunt laat zien wat er zou uitgaan en wat
   * tegengehouden wordt. Het verstuurt zelf niets.
   */
  'GET /api/verzendcontrole': (q) => {
    const limiet = Number(q.limiet) || 200;
    const leads = db.all(`
      SELECT l.*, s.name AS bron FROM leads l
      LEFT JOIN sources s ON s.id = l.source_id
      WHERE l.stage IN ('verified','sendable') LIMIT ?`, [limiet]);
    const r = compliance.filterSendable(leads);
    const redenTelling = {};
    for (const g of r.geweigerd || []) for (const reden of g.redenen) redenTelling[reden] = (redenTelling[reden] || 0) + 1;
    return {
      onderzocht: leads.length,
      mag_verzenden: r.mag_verzenden,
      blokkades: r.blokkades || [],
      toegestaan: r.aantal_toegestaan || 0,
      geweigerd: r.aantal_geweigerd || 0,
      redenen: Object.entries(redenTelling).map(([reden, n]) => ({ reden, n })).sort((a, b) => b.n - a.n),
      voorbeelden: (r.geweigerd || []).slice(0, 10),
    };
  },

  /**
   * Rechtmatig bereik. Dit eindpunt bestaat omdat het getal dat het
   * oplevert in vrijwel elke koude e-mailopzet ontbreekt: hoeveel van je
   * gescande adressen mag je daadwerkelijk benaderen.
   */
  'GET /api/bereik': () => {
    const b = wet.bereik();
    const p = capacity.plan();
    return {
      ...b,
      capaciteit_per_dag: p.huidig.per_dag_plafond,
      overcapaciteit: Math.max(0, p.huidig.per_dag_plafond - b.rechtmatig_per_dag),
      advies: b.rechtmatig_per_dag < p.huidig.per_dag_plafond
        ? `Je hebt capaciteit voor ${p.huidig.per_dag_plafond} berichten per dag en rechtmatig bereik voor ${b.rechtmatig_per_dag}. Meer domeinen kopen lost dit niet op. Het knelpunt zit in de bron van je adressen, niet in de verzendkant.`
        : 'Bereik en capaciteit liggen in dezelfde orde van grootte.',
      grondslagen: wet.GRONDSLAGEN,
      bestemmingen: wet.BESTEMMING,
    };
  },

  'GET /api/verwerkers': () => ({
    verwerkers: db.all('SELECT * FROM processors ORDER BY name'),
    lia: db.all('SELECT * FROM lia ORDER BY dated_at DESC'),
  }),

  'GET /api/instellingen': () => ({ instellingen: db.allSettings(), capaciteit_standaarden: capacity.DEFAULTS, domein_grenzen: domains.DEFAULT_LIMITS }),
  'POST /api/instellingen': async (q, body) => {
    for (const [k, v] of Object.entries(body || {})) db.setSetting(k, v);
    return { opgeslagen: Object.keys(body || {}).length, instellingen: db.allSettings() };
  },

  'GET /api/koppelingen': () => ({ koppelingen: adapters.status(), demo_modus: !adapters.anyLive() }),
};

function filter(q) {
  const f = {};
  if (q.sinds) f.since = q.sinds;
  if (q.persona) f.persona_id = Number(q.persona);
  if (q.bron) f.source_id = Number(q.bron);
  return f;
}

/* ==========================================================
   SERVER
   ========================================================== */

function serveStatic(req, res, pathname) {
  const rel = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const file = path.join(PUBLIC, rel);
  // geen padtraversal
  if (!file.startsWith(PUBLIC)) { res.writeHead(403); return res.end('verboden'); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }); return res.end('niet gevonden'); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
}

const server = http.createServer(async (req, res) => {
  let url;
  try { url = new URL(req.url, `http://${req.headers.host || 'localhost'}`); }
  catch { return json(res, { fout: 'ongeldige url' }, 400); }

  const q = Object.fromEntries(url.searchParams);
  const sleutel = `${req.method} ${url.pathname}`;

  if (url.pathname.startsWith('/api/')) {
    const handler = routes[sleutel];
    if (!handler) return json(res, { fout: 'onbekend eindpunt', eindpunt: sleutel, beschikbaar: Object.keys(routes) }, 404);
    try {
      const body = req.method === 'POST' ? await readBody(req) : null;
      const uit = await handler(q, body);
      return json(res, uit);
    } catch (e) {
      const status = e.code === 'JURIDISCH_GEBLOKKEERD' ? 409 : 400;
      return json(res, { fout: e.message, code: e.code || null }, status);
    }
  }

  if (req.method !== 'GET') { res.writeHead(405); return res.end(); }
  return serveStatic(req, res, url.pathname);
});

if (require.main === module) {
  db.open();
  const leeg = (db.get('SELECT COUNT(*) AS n FROM leads')?.n || 0) === 0;
  server.listen(PORT, HOST, () => {
    console.log(`\n  Signaal draait op http://${HOST}:${PORT}`);
    console.log(`  Database: ${db.DB_PATH}`);
    if (leeg) console.log('  Database is leeg. Vul hem met: node signaal/seed.js');
    if (!adapters.anyLive()) console.log('  DEMOSTAND: geen enkele koppeling heeft een sleutel. Cijfers uit externe bronnen zijn verzonnen.');
    console.log('');
  });
}

module.exports = { server, routes };
