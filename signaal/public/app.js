'use strict';
/* Signaal / bedieningspaneel. Geen framework, geen buildstap. */

const $ = (s, el = document) => el.querySelector(s);
const paneel = $('#paneel');

/* ---------- hulpjes ---------- */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (n) => (n === null || n === undefined || Number.isNaN(n)) ? '-' : Number(n).toLocaleString('nl-NL');
const pct = (n, d = 1) => (n === null || n === undefined) ? '-' : (Number(n) * 100).toFixed(d) + '%';
const eur = (n) => (n === null || n === undefined) ? '-' : '€ ' + Number(n).toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(pad, opties) {
  const res = await fetch(pad, opties);
  const data = await res.json();
  if (!res.ok) throw Object.assign(new Error(data.fout || 'fout'), { data });
  return data;
}
async function post(pad, body) {
  return api(pad, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

function kpi(k, v, s = '', klasse = '') {
  return `<div class="kpi ${klasse}"><div class="k">${esc(k)}</div><div class="v">${v}</div><div class="s">${esc(s)}</div></div>`;
}
function tabel(kolommen, rijen) {
  return `<div class="tabelwrap"><table>
    <thead><tr>${kolommen.map(c => `<th class="${c.num ? 'num' : ''}">${esc(c.t)}</th>`).join('')}</tr></thead>
    <tbody>${rijen.map(r => `<tr>${r.map((c, i) => `<td class="${kolommen[i]?.num ? 'num' : ''} ${kolommen[i]?.wrap ? 'wrap' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody>
  </table></div>`;
}
const badge = (tekst, k) => `<span class="badge ${k}">${esc(tekst)}</span>`;

/* ==========================================================
   TABBLADEN
   ========================================================== */
const weergaven = {};

weergaven.overzicht = async () => {
  const d = await api('/api/overzicht');
  const t = d.trechter, c = d.capaciteit;
  const dekking = c.per_dag_nodig > 0 ? c.per_dag_nu / c.per_dag_nodig : 1;

  return `
  <section class="blok">
    <h2>Waar staat het</h2>
    <p class="uitleg">Eén scherm met de vier getallen die er dagelijks toe doen. De rest zit achter de tabbladen.</p>
    <div class="kpis">
      ${kpi('Benaderd', num(t.benaderd), 'in de gemeten periode')}
      ${kpi('Reactiepercentage', pct(t.reply_rate), `${num(t.gereageerd)} reacties`, t.reply_rate >= 0.15 ? 'goed' : 'let')}
      ${kpi('Afspraken', num(t.afspraken), `${pct(t.afspraak_rate, 2)} van benaderd`)}
      ${kpi('Klanten', num(t.klanten), 'getekend')}
    </div>
    <div class="kpis">
      ${kpi('Capaciteit vandaag', num(c.per_dag_nu) + '/dag', `nodig: ${num(c.per_dag_nodig)}/dag`, dekking >= 1 ? 'goed' : 'slecht')}
      ${kpi('Plafond', num(c.per_dag_plafond) + '/dag', 'als alles opgewarmd is')}
      ${kpi('Domeinen', num(c.domeinen.totaal), `${num(c.domeinen.actief)} actief, ${num(c.domeinen.opwarmend)} opwarmend`)}
      ${kpi('Kosten per afspraak', eur(d.kosten.per_afspraak_eur), `rendement ${d.kosten.rendement ?? '-'}x`)}
    </div>
  </section>

  ${!d.naleving.mag_verzenden ? `<div class="melding fout"><b>Verzenden staat geblokkeerd</b>
    ${d.naleving.blokkades} accountcontrole(s) staan open. Zolang die openstaan, houdt de AVG-poort alles tegen. Zie het tabblad AVG.</div>` : ''}

  ${d.domeinen_aandacht > 0 ? `<div class="melding waarschuwing"><b>${d.domeinen_aandacht} domein(en) vragen aandacht</b>
    Zie het tabblad Domeinen. Een domein dat te lang doorloopt met klachten neemt de rest van je verzending mee.</div>` : ''}

  <section class="blok">
    <h2>Koppelingen</h2>
    <p class="uitleg">Zonder sleutel draait een koppeling in demostand en levert hij verzonnen data. Sleutels zet je als omgevingsvariabele, niet in de database.</p>
    ${tabel(
      [{ t: 'Koppeling' }, { t: 'Waarvoor', wrap: true }, { t: 'Omgevingsvariabele' }, { t: 'Status' }],
      d.koppelingen.map(k => [esc(k.naam), esc(k.doel), k.env_var ? `<code>${esc(k.env_var)}</code>` : 'geen nodig',
        k.aangesloten ? badge('aangesloten', 'b-ok') : badge('demostand', 'b-let')])
    )}
  </section>`;
};

weergaven.trechter = async () => {
  const d = await api('/api/trechter');
  const top = d.stappen[0].n || 1;
  const knel = d.knelpunten.top?.stage;

  const balken = d.stappen.map(s => `
    <div class="stap ${s.stage === knel ? 'knel' : ''}">
      <div class="naam">${esc(s.label)}<small>${esc(s.uitleg)}</small></div>
      <div class="baan"><i style="width:${Math.max(0.4, (s.n / top) * 100).toFixed(2)}%"></i></div>
      <div class="cijfers"><b>${num(s.n)}</b><span>${pct(s.van_vorige)} van vorige${s.verloren ? ` · ${num(s.verloren)} kwijt` : ''}</span></div>
    </div>`).join('');

  const k = d.knelpunten;
  return `
  <section class="blok">
    <h2>Trechter</h2>
    <p class="uitleg">Elke stap toont de conversie ten opzichte van de stap erboven. De oranje balk is de stap waar repareren het meeste oplevert, niet de stap met het laagste percentage.</p>
    <div class="trechter">${balken}</div>
  </section>

  <section class="blok">
    <h2>Knelpunt</h2>
    <p class="uitleg">Wat levert het op als je één stap tien procentpunt verbetert, gemeten in extra ${esc(k.doelstap)}. Een slechte conversie bovenin een brede trechter is meer waard dan een slechte conversie onderin een smalle.</p>
    ${k.waarschuwing ? `<div class="melding waarschuwing"><b>Te weinig volume</b>${esc(k.waarschuwing)}</div>` : ''}
    ${tabel(
      [{ t: 'Stap' }, { t: 'Instroom', num: true }, { t: 'Nu', num: true }, { t: 'Wordt', num: true }, { t: `Extra ${k.doelstap}`, num: true }, { t: 'Zekerheid' }],
      k.items.map(i => [
        esc(i.label), num(i.instroom), pct(i.conversie), pct(i.bij_plus_delta),
        `<b>+${i.extra_op_doel}</b>`,
        i.betrouwbaar ? badge('gemeten', 'b-ok') : badge('schatting', 'b-let'),
      ])
    )}
  </section>`;
};

weergaven.capaciteit = async () => {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const d = await api('/api/capaciteit?' + params);
  const b = await api('/api/capaciteit/bestellen?' + params);
  const v = b.voorstel;

  return `
  <section class="blok">
    <h2>Capaciteitsplanning</h2>
    <p class="uitleg">Geef een maanddoel op als aantal contacten, of als aantal gewenste afspraken. In dat laatste geval rekent hij terug via de trechterpercentages.</p>
    <div class="rij">
      <div><label>Contacten per maand</label><input id="in-contacten" type="number" min="0" step="100" value="${d.doel.contacten_per_maand}"></div>
      <div><label>of afspraken per maand</label><input id="in-afspraken" type="number" min="0" step="5" placeholder="bijv. 40"></div>
      <button class="knop" id="bereken">Doorrekenen</button>
    </div>

    <div class="kpis">
      ${kpi('Nodig per dag', num(d.doel.per_dag_nodig), `${num(d.doel.contacten_per_maand)} per maand`)}
      ${kpi('Nu per dag', num(d.huidig.per_dag_nu), 'inclusief opwarmen', d.huidig.per_dag_nu >= d.doel.per_dag_nodig ? 'goed' : 'slecht')}
      ${kpi('Plafond per dag', num(d.huidig.per_dag_plafond), 'volledig opgewarmd')}
      ${kpi('Tekort', num(d.tekort.per_dag_op_plafond) + '/dag', 'op plafond gemeten', d.tekort.per_dag_op_plafond > 0 ? 'slecht' : 'goed')}
    </div>

    ${d.doel.afgeleid ? `<div class="melding"><b>Teruggerekend vanuit afspraken</b>
      ${d.doel.afgeleid.afspraken} afspraken bij ${pct(d.doel.afgeleid.afspraken_per_contact, 3)} per contact betekent ${num(d.doel.contacten_per_maand)} contacten per maand.</div>` : ''}

    <div class="kpis">
      ${kpi('Verwachte reacties', num(d.verwacht.replies), `bij ${pct(d.doel.aannames.reply_rate)}`)}
      ${kpi('Verwacht positief', num(d.verwacht.positief), `${pct(d.doel.aannames.positief_van_reply)} van reacties`)}
      ${kpi('Verwachte afspraken', num(d.verwacht.afspraken), `${pct(d.doel.aannames.afspraak_van_positief)} van positief`)}
      ${kpi('Mailboxen nodig', num(d.benodigd.mailboxen), `${num(d.benodigd.domeinen)} domeinen`)}
    </div>
  </section>

  <section class="blok">
    <h2>Bijbestellen</h2>
    <p class="uitleg">Bestellingen gaan nooit automatisch de deur uit. Dit is een voorstel dat een mens bevestigt.</p>
    ${v.nodig ? `
      <div class="melding waarschuwing">
        <b>Voorstel: ${v.domeinen} domein(en) en ${v.mailboxen} mailbox(en)</b>
        Eenmalig ongeveer ${eur(v.geschatte_kosten_eur)}, daarna ${eur(v.geschatte_maandlast_eur)} per maand.
        ${esc(v.waarschuwing || '')}
      </div>` : `<div class="melding goed"><b>Niets bijbestellen</b>Het plafond dekt het doel. Bijkopen zou stilstaande capaciteit opleveren.</div>`}
  </section>`;
};

weergaven.personas = async () => {
  const d = await api('/api/personas');
  const kleur = { opschalen: 'b-ok', aanhouden: 'b-cobalt', verfijnen: 'b-let', stoppen: 'b-slecht' };
  const actieVan = Object.fromEntries((d.aanbeveling.acties || []).map(a => [a.persona_id, a]));

  return `
  <section class="blok">
    <h2>Persona's, gesloten lus</h2>
    <p class="uitleg">Een persona wordt beoordeeld op wat hij oplevert, niet op hoeveel reacties hij trekt. Let op de persona met een hoog reactiepercentage en nul klanten: dat is precies het geval waarin sturen op reacties je op het verkeerde been zet.</p>
    ${!d.aanbeveling.klaar ? `<div class="melding waarschuwing"><b>Nog geen oordeel</b>${esc(d.aanbeveling.reden)}</div>` : ''}
    ${tabel(
      [{ t: 'Persona' }, { t: 'Benaderd', num: true }, { t: 'Reactie', num: true }, { t: 'Afspraken', num: true },
       { t: 'Klanten', num: true }, { t: 'Omzet', num: true }, { t: 'Klacht', num: true }, { t: 'Score', num: true }, { t: 'Advies' }],
      d.scores.map(p => [
        esc(p.name) + ` <small style="color:var(--ink-soft)">v${p.version}</small>` + (p.betrouwbaar ? '' : ' ' + badge('weinig data', 'b-uit')),
        num(p.benaderd), pct(p.reply_rate), num(p.afspraken), num(p.klanten),
        eur(p.omzet_eur), pct(p.klacht_rate, 2), `<b>${p.score}</b>`,
        actieVan[p.id] ? badge(actieVan[p.id].actie, kleur[actieVan[p.id].actie] || '') : '-',
      ])
    )}
  </section>

  <section class="blok">
    <h2>Wat de winnaars gemeen hebben</h2>
    <p class="uitleg">Afgeleid uit de leads die daadwerkelijk een afspraak of handtekening opleverden. Dit is de invoer voor een verfijning.</p>
    ${d.winnaars.aantal === 0 ? '<div class="melding">Nog geen afspraken of klanten om een profiel uit af te leiden.</div>' : `
      <div class="kpis">
        ${kpi('Winnaars', num(d.winnaars.aantal), 'afspraak of klant')}
        ${kpi('Grootte', d.winnaars.patronen.grootte ? `${d.winnaars.patronen.grootte.mediaan} mdw` : '-', d.winnaars.patronen.grootte ? `${d.winnaars.patronen.grootte.min} tot ${d.winnaars.patronen.grootte.max}` : '')}
        ${kpi('Beste regio', d.winnaars.patronen.regio[0]?.waarde || '-', `${d.winnaars.patronen.regio[0]?.n || 0} keer`)}
        ${kpi('Beste bron', d.winnaars.patronen.bron[0]?.waarde || '-', `${d.winnaars.patronen.bron[0]?.n || 0} keer`)}
      </div>`}
  </section>

  <section class="blok">
    <h2>Wegingen</h2>
    <p class="uitleg">Zo zwaar telt elke uitkomst mee in de score. Klachten tellen negatief, want een segment dat klachten oplevert kost je domeinen en domeinen zijn duurder dan leads.</p>
    ${tabel([{ t: 'Uitkomst' }, { t: 'Gewicht', num: true }], Object.entries(d.wegingen).map(([k, v]) => [esc(k), v]))}
  </section>`;
};

weergaven.bronnen = async () => {
  const d = await api('/api/bronnen');
  const kleur = { toegestaan: 'b-ok', api_vereist: 'b-cobalt', verboden: 'b-slecht', review: 'b-let' };

  return `
  <section class="blok">
    <h2>Bronnen</h2>
    <p class="uitleg">De juridische status is geen notitieveld maar een slot. Een bron op "verboden" of "review" kan niet op automatisch gezet worden, ook niet per ongeluk. Dat is strenger dan de opzet waar dit op gebaseerd is, en met opzet.</p>
    ${tabel(
      [{ t: 'Bron' }, { t: 'Soort' }, { t: 'Status' }, { t: 'Automatisch' }, { t: 'Cadans', num: true }, { t: 'Toelichting', wrap: true }],
      d.bronnen.map(b => [
        esc(b.name), esc(b.kind), badge(b.legal_status, kleur[b.legal_status] || ''),
        b.automated ? badge('aan', 'b-ok') : (b.mag_automatisch ? badge('uit', 'b-uit') : badge('geblokkeerd', 'b-slecht')),
        b.cadence_hours + 'u', esc(b.legal_note || ''),
      ])
    )}
  </section>

  <section class="blok">
    <h2>Briefs</h2>
    <p class="uitleg">Een brief is een combinatie van persona en bron: wat halen we hier op, en waarvoor.</p>
    ${tabel(
      [{ t: 'Persona' }, { t: 'Bron' }, { t: 'Zoekopdracht', wrap: true }, { t: 'Haalt op', wrap: true }],
      d.briefs.map(b => [esc(b.persona) + ` v${b.persona_versie}`, esc(b.bron), esc(b.query), esc(b.extract || '')])
    )}
  </section>`;
};

weergaven.domeinen = async () => {
  const d = await api('/api/domeinen');
  const kleur = { ok: 'b-ok', let_op: 'b-cobalt', waarschuwing: 'b-let', kritiek: 'b-slecht' };
  const w = d.weekrapport;

  return `
  <section class="blok">
    <h2>Domeingezondheid</h2>
    <p class="uitleg">Domeinen zijn niet duur om te kopen maar wel duur om te verbranden: een vervanger doet pas na drie weken opwarmen mee. De klachtgrens staat bewust onder wat Google toestaat.</p>
    <div class="kpis">
      ${kpi('Domeinen', num(d.domeinen.length), `${num(d.aandacht.length)} met aandacht`, d.aandacht.length ? 'let' : 'goed')}
      ${kpi('Bounce, 7 dagen', pct(w.gemiddelde.bounce_rate, 2), 'gemiddeld', w.gemiddelde.bounce_rate > 0.03 ? 'slecht' : 'goed')}
      ${kpi('Klachten, 7 dagen', pct(w.gemiddelde.klacht_rate, 3), 'gemiddeld', w.gemiddelde.klacht_rate > 0.001 ? 'slecht' : 'goed')}
      ${kpi('Reacties, 7 dagen', pct(w.gemiddelde.reply_rate, 2), 'gemiddeld')}
    </div>
    ${tabel(
      [{ t: 'Domein' }, { t: 'Status' }, { t: 'Auth' }, { t: 'Verzonden', num: true }, { t: 'Bounce', num: true },
       { t: 'Klacht', num: true }, { t: 'Reactie', num: true }, { t: 'Ernst' }, { t: 'Advies' }],
      d.domeinen.map(x => [
        esc(x.domain), esc(x.status),
        (x.spf && x.dkim && x.dmarc) ? badge('volledig', 'b-ok') : badge('incompleet', 'b-slecht'),
        num(x.verzonden), pct(x.bounce_rate, 2), pct(x.klacht_rate, 3), pct(x.reply_rate, 2),
        badge(x.ernst, kleur[x.ernst] || ''), esc(x.advies),
      ])
    )}
  </section>

  ${d.aandacht.length ? `<section class="blok">
    <h2>Wat er mis is</h2>
    <ul class="lijst">
      ${d.aandacht.map(a => `<li><b>${esc(a.domain)}</b> ${badge(a.advies, kleur[a.ernst])}<br>${a.problemen.map(esc).join('<br>')}</li>`).join('')}
    </ul>
  </section>` : ''}`;
};

weergaven.kosten = async () => {
  const d = await api('/api/kosten');
  const e = d.economie, p = d.projectie;

  return `
  <section class="blok">
    <h2>Kosten en opbrengst</h2>
    <p class="uitleg">De maandrekening zegt weinig. Wat een afspraak kost en wat een afspraak waard is, dat is het gesprek.</p>
    <div class="kpis">
      ${kpi('Totaal deze maand', eur(e.kosten.totaal_eur), `vast ${eur(e.kosten.vast_eur)}, variabel ${eur(e.kosten.variabel_eur)}`)}
      ${kpi('Per benaderde lead', eur(e.per_benaderde_lead_eur), `${num(e.volume.benaderd)} benaderd`)}
      ${kpi('Per afspraak', eur(e.per_afspraak_eur), `${num(e.volume.afspraken)} afspraken`)}
      ${kpi('Rendement', (e.rendement ?? '-') + 'x', `omzet ${eur(e.omzet_eur)}`, e.rendement >= 1 ? 'goed' : 'slecht')}
    </div>
  </section>

  <section class="blok">
    <h2>Als je opschaalt naar ${num(p.doel_contacten)} contacten</h2>
    ${p.oordeel ? `<div class="melding ${p.kosten_per_afspraak_eur >= (p.waarde_per_afspraak_eur || Infinity) ? 'fout' : 'goed'}">
      <b>Oordeel</b>${esc(p.oordeel)}</div>` : ''}
    <div class="kpis">
      ${kpi('Geprojecteerde kosten', eur(p.geprojecteerde_kosten_eur), `variabel ${eur(p.variabel_per_contact_eur)} per contact`)}
      ${kpi('Verwachte afspraken', num(p.verwachte_afspraken), 'bij huidige percentages')}
      ${kpi('Kosten per afspraak', eur(p.kosten_per_afspraak_eur), 'geprojecteerd')}
      ${kpi('Waarde per afspraak', eur(p.waarde_per_afspraak_eur), 'uit instellingen')}
    </div>
  </section>

  <section class="blok">
    <h2>Regels</h2>
    ${tabel(
      [{ t: 'Leverancier' }, { t: 'Categorie' }, { t: 'Model' }, { t: 'Bedrag', num: true }, { t: 'Eenheden', num: true }],
      d.regels.map(r => [esc(r.provider), esc(r.category), esc(r.model), eur(r.amount_eur), num(r.units)])
    )}
  </section>`;
};

weergaven.naleving = async () => {
  const d = await api('/api/naleving');
  const c = await api('/api/verzendcontrole?limiet=500');
  const s = d.status;

  return `
  <section class="blok">
    <h2>AVG en Telecommunicatiewet</h2>
    <p class="uitleg">Dit maakt je niet vanzelf compliant. Wat het wel doet: de controles die je hoort na te leven daadwerkelijk laten tegenhouden. Laat de teksten en de afweging nakijken voordat de eerste campagne uitgaat.</p>

    <div class="melding ${s.mag_verzenden ? 'goed' : 'fout'}">
      <b>${s.mag_verzenden ? 'Verzenden toegestaan' : 'Verzenden geblokkeerd'}</b>
      ${s.mag_verzenden ? 'Alle accountcontroles staan groen.' : `${s.blokkades.length} controle(s) staan open. Er gaat niets uit tot die opgelost zijn.`}
    </div>

    ${tabel(
      [{ t: 'Controle' }, { t: 'Status' }, { t: 'Eis', wrap: true }],
      s.controles.map(x => [esc(x.id), x.ok ? badge('ok', 'b-ok') : badge('open', 'b-slecht'), esc(x.eis)])
    )}
  </section>

  <section class="blok">
    <h2>Rechtmatig bereik</h2>
    <p class="uitleg">Het getal dat in vrijwel elke koude e-mailopzet ontbreekt. Nederland kent geen algemeen opt-outregime voor zakelijke e-mail: sinds 2009 geldt het opt-invereiste ook voor rechtspersonen. De enige uitzondering, artikel 11.7 lid 2, vraagt dat de ontvanger het adres <em>zelf heeft bestemd en bekendgemaakt</em> voor dit doel. Een info@ op een contactpagina voldoet daar niet aan.</p>
    <div id="bereik-blok"><p class="laden">Rekenen...</p></div>
  </section>

  <section class="blok">
    <h2>Verzendcontrole</h2>
    <p class="uitleg">Wat er zou uitgaan en wat de poort tegenhoudt. Dit eindpunt verstuurt zelf niets.</p>
    <div class="kpis">
      ${kpi('Onderzocht', num(c.onderzocht), 'leads klaar om te verzenden')}
      ${kpi('Toegestaan', num(c.toegestaan), 'mag de deur uit', 'goed')}
      ${kpi('Tegengehouden', num(c.geweigerd), 'door de poort', c.geweigerd ? 'let' : '')}
      ${kpi('Onderdrukt totaal', num(s.onderdrukte_records), 'op de lijst')}
    </div>
    ${c.redenen.length ? tabel([{ t: 'Reden' }, { t: 'Aantal', num: true }], c.redenen.map(r => [esc(r.reden), num(r.n)])) : ''}
  </section>

  <section class="blok">
    <h2>Bewaartermijn</h2>
    <p class="uitleg">Leads eeuwig bewaren botst met opslagbeperking. Leads met een afspraak of handtekening blijven staan, daar geldt een ander belang voor.</p>
    <div class="melding ${d.bewaartermijn.aantal > 0 ? 'waarschuwing' : 'goed'}">
      <b>${num(d.bewaartermijn.aantal)} leads over de termijn van ${d.bewaartermijn.bewaartermijn_dagen} dagen</b>
      ${esc(d.bewaartermijn.toelichting || '')}
    </div>
  </section>

  <section class="blok">
    <h2>Verwerkingsregister</h2>
    <p class="uitleg">Verplicht onder AVG artikel 30. Leg de afweging voor gerechtvaardigd belang vast voordat je verstuurt, niet erna.</p>
    ${tabel(
      [{ t: 'Activiteit', wrap: true }, { t: 'Grondslag', wrap: true }, { t: 'Bewaartermijn', num: true }],
      d.register.map(r => [esc(r.activity), esc(r.legal_basis), r.retention_days + ' dagen'])
    )}
  </section>`;
};

/* ==========================================================
   ROUTERING
   ========================================================== */
async function toon(naam) {
  for (const b of document.querySelectorAll('#tabs button')) b.classList.toggle('actief', b.dataset.tab === naam);
  paneel.innerHTML = '<p class="laden">Laden...</p>';
  try {
    paneel.innerHTML = await (weergaven[naam] || weergaven.overzicht)();
    hangHandlers();
  } catch (e) {
    paneel.innerHTML = `<div class="melding fout"><b>Fout bij laden</b>${esc(e.message)}</div>`;
  }
}

async function vulBereik() {
  const doel = $('#bereik-blok');
  if (!doel) return;
  try {
    const b = await api('/api/bereik');
    const behoud = b.met_adres > 0 ? b.beide_poorten / b.met_adres : 0;
    doel.innerHTML = `
      <div class="melding ${behoud < 0.25 ? 'fout' : 'goed'}">
        <b>${num(b.beide_poorten)} van ${num(b.met_adres)} adressen mogen benaderd worden (${pct(behoud)})</b>
        ${esc(b.oordeel)}
      </div>
      <div class="kpis">
        ${kpi('Met adres', num(b.met_adres), 'gescand en verrijkt')}
        ${kpi('Poort 1, Tw 11.7', num(b.poort1_haalbaar), 'grondslag om te verzenden')}
        ${kpi('Beide poorten', num(b.beide_poorten), 'ook AVG in orde', behoud < 0.25 ? 'slecht' : 'goed')}
        ${kpi('Rechtmatig per dag', num(b.rechtmatig_per_dag), `capaciteit: ${num(b.capaciteit_per_dag)}/dag`, 'let')}
      </div>
      <div class="melding waarschuwing"><b>Verhouding capaciteit en bereik</b>${esc(b.advies)}</div>
      ${tabel(
        [{ t: 'Bestemming' }, { t: 'Aantal', num: true }, { t: 'Draagt lid 2' }, { t: 'Uitleg', wrap: true }],
        Object.entries(b.per_bestemming).sort((x, y) => y[1] - x[1]).map(([k, n]) => [
          esc(b.bestemmingen[k]?.label || k), num(n),
          b.bestemmingen[k]?.draagt_lid2 ? badge('ja', 'b-ok') : badge('nee', 'b-slecht'),
          esc(b.bestemmingen[k]?.uitleg || ''),
        ])
      )}
      <h3 style="margin:1.2rem 0 .4rem;font-size:.8rem;letter-spacing:.06em;text-transform:uppercase">Waarom de rest afvalt</h3>
      ${tabel([{ t: 'Reden', wrap: true }, { t: 'Aantal', num: true }], b.top_redenen.map(r => [esc(r.reden), num(r.n)]))}`;
  } catch (e) {
    doel.innerHTML = `<div class="melding fout"><b>Kon bereik niet berekenen</b>${esc(e.message)}</div>`;
  }
}

function hangHandlers() {
  vulBereik();
  const knop = $('#bereken');
  if (knop) {
    knop.onclick = () => {
      const c = $('#in-contacten').value, a = $('#in-afspraken').value;
      const p = new URLSearchParams();
      if (a) p.set('afspraken', a); else if (c) p.set('contacten', c);
      location.hash = `capaciteit?${p}`;
      toon('capaciteit');
    };
  }
}

document.getElementById('tabs').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  location.hash = b.dataset.tab;   // hashchange doet de rest
});

/* Zonder deze luisteraar werken de terugknop van de browser en een
   handmatig aangepaste hash niet. */
window.addEventListener('hashchange', () => {
  const naam = (location.hash || '#overzicht').slice(1).split('?')[0];
  toon(weergaven[naam] ? naam : 'overzicht');
});

(async function start() {
  try {
    const d = await api('/api/overzicht');
    $('#topmeta').innerHTML = `
      <span>Benaderd <b>${num(d.trechter.benaderd)}</b></span>
      <span>Reactie <b>${pct(d.trechter.reply_rate)}</b></span>
      <span>Afspraken <b>${num(d.trechter.afspraken)}</b></span>
      <span>Capaciteit <b>${num(d.capaciteit.per_dag_nu)}/dag</b></span>`;
    if (d.demo_modus) {
      $('#demobalk').hidden = false;
      $('#demotekst').textContent = 'Geen enkele koppeling heeft een API-sleutel. Alles wat je ziet komt uit de lokale demodata, niet uit een echte bron.';
    }
  } catch { /* het paneel toont de fout zelf wel */ }

  const start = (location.hash || '#overzicht').slice(1).split('?')[0];
  toon(weergaven[start] ? start : 'overzicht');
})();
