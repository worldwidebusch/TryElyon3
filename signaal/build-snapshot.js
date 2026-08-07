#!/usr/bin/env node
'use strict';
/**
 * Bouwt een losstaande HTML-momentopname van het dashboard.
 *
 * Het echte dashboard praat met een lokale server. Deze bouwstap haalt
 * alle eindpunten één keer op, bakt de antwoorden in de pagina, en zet
 * de fetch-laag om naar een opzoeking in die ingebakken data. Resultaat
 * is één bestand dat je kunt openen zonder server.
 *
 *   node signaal/server.js &
 *   node signaal/build-snapshot.js > signaal/momentopname.html
 */

const fs = require('node:fs');
const path = require('node:path');

const BASIS = process.env.SIGNAAL_URL || 'http://127.0.0.1:8787';
const PUBLIC = path.join(__dirname, 'public');

const EINDPUNTEN = [
  '/api/overzicht',
  '/api/trechter',
  '/api/capaciteit',
  '/api/capaciteit/bestellen',
  '/api/personas',
  '/api/bronnen',
  '/api/domeinen',
  '/api/kosten',
  '/api/naleving',
  '/api/bereik',
  '/api/verzendcontrole',
];

async function main() {
  const snapshot = {};
  for (const ep of EINDPUNTEN) {
    const url = BASIS + ep + (ep === '/api/verzendcontrole' ? '?limiet=500' : '');
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${ep} gaf ${res.status}`);
    snapshot[ep] = await res.json();
  }

  const css = fs.readFileSync(path.join(PUBLIC, 'app.css'), 'utf8');
  let js = fs.readFileSync(path.join(PUBLIC, 'app.js'), 'utf8');

  /* fetch vervangen door een opzoeking in de ingebakken data */
  const oudeApi = js.match(/async function api\(pad, opties\) \{[\s\S]*?\n\}/);
  if (!oudeApi) throw new Error('api() niet gevonden in app.js');
  js = js.replace(oudeApi[0], `async function api(pad) {
  const sleutel = pad.split('?')[0];
  const d = SNAPSHOT[sleutel];
  if (!d) throw new Error('geen momentopname voor ' + sleutel);
  return JSON.parse(JSON.stringify(d));
}`);

  const oudePost = js.match(/async function post\(pad, body\) \{[\s\S]*?\n\}/);
  if (oudePost) {
    js = js.replace(oudePost[0], `async function post() {
  throw new Error('Dit is een momentopname. Wijzigingen werken alleen tegen de draaiende server.');
}`);
  }

  /* de doorrekenknop kan zonder server niet herrekenen: dat zeggen we ook */
  js = js.replace(
    /  const knop = \$\('#bereken'\);[\s\S]*?\n  \}\n\}/,
    `  const knop = $('#bereken');
  if (knop) {
    knop.onclick = () => {
      const m = document.createElement('div');
      m.className = 'melding waarschuwing';
      m.innerHTML = '<b>Momentopname</b>Herrekenen werkt alleen tegen de draaiende server. Start hem met <code>node signaal/server.js</code> en open localhost:8787.';
      knop.closest('.rij').insertAdjacentElement('afterend', m);
      knop.disabled = true;
    };
  }
}`
  );

  const html = `<title>Signaal / bedieningspaneel</title>
<style>
${css}
/* De momentopname kiest bewust voor één visuele wereld: het papieren
   grondvlak van Elyon. Daarom een expliciete achtergrond op body, zodat
   de pagina ook standhoudt op een donker grondvlak van de viewer. */
html,body{background:var(--paper)}
.snapshotbalk{
  background:var(--cobalt);color:#fff;
  padding:.55rem clamp(12px,3vw,22px);font-size:.74rem;
}
.snapshotbalk b{font-weight:700}
td.num,th.num,.kpi .v,.stap .cijfers{font-variant-numeric:tabular-nums}
</style>

<header class="topbar">
  <div class="brand">
    <svg viewBox="0 0 100 100" aria-hidden="true"><rect x="22" y="22" width="12" height="56" fill="#EFEDE6"/><rect x="22" y="22" width="56" height="12" fill="#2038E6"/><rect x="22" y="44" width="44" height="12" fill="#EFEDE6"/><rect x="22" y="66" width="32" height="12" fill="#EFEDE6"/></svg>
    SIGNAAL
  </div>
  <div class="topmeta" id="topmeta"></div>
</header>

<div class="snapshotbalk">
  <b>Momentopname.</b> Dit is het echte dashboard met echte berekeningen, één keer vastgelegd zodat je het zonder server kunt bekijken. Alle tabbladen werken. Knoppen die iets wijzigen zijn uitgeschakeld.
</div>

<div id="demobalk" class="demobalk" hidden>
  <strong>Demostand.</strong>
  <span id="demotekst"></span>
</div>

<nav class="tabs" id="tabs">
  <button data-tab="overzicht" class="actief">Overzicht</button>
  <button data-tab="trechter">Trechter</button>
  <button data-tab="capaciteit">Capaciteit</button>
  <button data-tab="personas">Persona's</button>
  <button data-tab="bronnen">Bronnen</button>
  <button data-tab="domeinen">Domeinen</button>
  <button data-tab="kosten">Kosten</button>
  <button data-tab="naleving">AVG</button>
</nav>

<main id="paneel"><p class="laden">Laden...</p></main>

<footer class="voet">
  Signaal draait normaal lokaal op <code>node signaal/server.js</code>. Cijfers uit externe bronnen zijn verzonnen zolang er geen API-sleutels zijn ingesteld.
</footer>

<script>
const SNAPSHOT = ${JSON.stringify(snapshot)};
${js}
</script>
`;

  process.stdout.write(html);
}

main().catch(e => { console.error('mislukt:', e.message); process.exit(1); });
