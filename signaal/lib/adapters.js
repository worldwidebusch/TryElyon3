'use strict';
/**
 * Signaal / koppelingen naar externe diensten
 *
 * Elke koppeling heeft twee standen: aangesloten en niet aangesloten.
 * Zonder sleutel draait de koppeling in demostand en geeft hij verzonnen
 * data terug. Die data is ALTIJD gemarkeerd met mock: true, en het
 * dashboard laat dat ook zien.
 *
 * Dat is met opzet zo streng. Het gevaarlijkste dat een systeem als dit
 * kan doen is nepdata tonen die eruitziet als echte data, want dan ga je
 * sturen op cijfers die niemand heeft gemeten.
 *
 * Sleutels komen uit omgevingsvariabelen, nooit uit de database en nooit
 * uit de broncode.
 */

const db = require('./db');

/* ==========================================================
   BASIS
   ========================================================== */

function env(naam) {
  const v = process.env[naam];
  return v && String(v).trim() ? String(v).trim() : null;
}

/** Minimale fetch met time-out. Node 22 heeft fetch ingebouwd. */
async function request(url, opties = {}, timeoutMs = 15000) {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opties, signal: ac.signal });
    const tekst = await res.text();
    let body = tekst;
    try { body = JSON.parse(tekst); } catch { /* geen json, laat als tekst */ }
    if (!res.ok) {
      const err = new Error(`${res.status} ${res.statusText}`);
      err.status = res.status; err.body = body;
      throw err;
    }
    return body;
  } finally {
    clearTimeout(t);
  }
}

/* ==========================================================
   KVK HANDELSREGISTER
   ========================================================== */

const kvk = {
  naam: 'KVK Handelsregister',
  envVar: 'KVK_API_KEY',
  doel: 'Bedrijfsgegevens, SBI-codes, vestigingen',
  configured() { return Boolean(env('KVK_API_KEY')); },

  async zoek({ naam = null, kvkNummer = null, plaats = null, limit = 10 } = {}) {
    if (!this.configured()) {
      return {
        mock: true,
        toelichting: 'Geen KVK_API_KEY ingesteld. Dit zijn verzonnen voorbeelden.',
        resultaten: Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
          kvkNummer: `9000000${i}`,
          naam: naam ? `${naam} ${i + 1} B.V.` : `Voorbeeldbedrijf ${i + 1} B.V.`,
          plaats: plaats || ['Utrecht', 'Rotterdam', 'Eindhoven'][i % 3],
          sbi: ['6201', '7022', '4321'][i % 3],
        })),
      };
    }
    const params = new URLSearchParams();
    if (naam) params.set('naam', naam);
    if (kvkNummer) params.set('kvkNummer', kvkNummer);
    if (plaats) params.set('plaats', plaats);
    const body = await request(`https://api.kvk.nl/api/v2/zoeken?${params}`, {
      headers: { apikey: env('KVK_API_KEY') },
    });
    return { mock: false, resultaten: body.resultaten || [], totaal: body.totaal };
  },
};

/* ==========================================================
   TENDERNED
   ========================================================== */

const tenderned = {
  naam: 'TenderNed',
  envVar: null,
  doel: 'Openbare aanbestedingen',
  configured() { return true; }, // open data, geen sleutel nodig

  async recent({ limit = 10 } = {}) {
    // De publicatie-API van TenderNed wisselt van vorm. Houd deze methode
    // dun en pas alleen de mapping aan als het eindpunt verandert.
    const basis = env('TENDERNED_API_URL');
    if (!basis) {
      return {
        mock: true,
        toelichting: 'Geen TENDERNED_API_URL ingesteld. Zet die op het actuele publicatie-eindpunt.',
        resultaten: Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
          titel: ['Inhuur technisch personeel', 'Onderhoud ICT-werkplekken', 'Wervingscampagne'][i],
          opdrachtgever: ['Gemeente Zuid-Holland', 'Waterschap Oost', 'Provincie Noord'][i],
          publicatiedatum: new Date(Date.now() - i * 86400000).toISOString().slice(0, 10),
        })),
      };
    }
    const body = await request(`${basis}?limit=${limit}`);
    return { mock: false, resultaten: Array.isArray(body) ? body : (body.content || []) };
  },
};

/* ==========================================================
   WEBZOEKEN, VOOR PERSONA-ONDERZOEK
   ========================================================== */

const zoek = {
  naam: 'Webzoeken',
  envVar: 'EXA_API_KEY',
  doel: 'Onderzoek naar klanten die getekend hebben, om persona te verfijnen',
  configured() { return Boolean(env('EXA_API_KEY')); },

  async onderzoek(vraag, { limit = 5 } = {}) {
    if (!this.configured()) {
      return {
        mock: true,
        toelichting: 'Geen EXA_API_KEY ingesteld.',
        vraag,
        resultaten: [{ titel: 'Voorbeeldresultaat', url: 'https://example.nl', samenvatting: 'Verzonnen onderzoeksresultaat.' }],
      };
    }
    const body = await request('https://api.exa.ai/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': env('EXA_API_KEY') },
      body: JSON.stringify({ query: vraag, numResults: limit, contents: { text: true } }),
    });
    return { mock: false, vraag, resultaten: body.results || [] };
  },
};

/* ==========================================================
   VERZENDPLATFORM
   ========================================================== */

const verzender = {
  naam: 'Verzendplatform',
  envVar: 'INSTANTLY_API_KEY',
  doel: 'Campagnes laden en versturen',
  configured() { return Boolean(env('INSTANTLY_API_KEY')); },

  /**
   * Leads in een campagne laden.
   * Belangrijk: deze methode controleert NIET op AVG. Die controle hoort
   * eerder te gebeuren, in compliance.filterSendable, zodat er nooit een
   * pad bestaat waarlangs een onderdrukt adres alsnog verstuurd wordt.
   */
  async pushLeads(campagneId, leads) {
    if (!this.configured()) {
      return {
        mock: true,
        toelichting: 'Geen INSTANTLY_API_KEY ingesteld. Er is niets verstuurd.',
        campagne: campagneId,
        aantal: leads.length,
      };
    }
    const body = await request('https://api.instantly.ai/api/v2/leads/list', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${env('INSTANTLY_API_KEY')}` },
      body: JSON.stringify({
        campaign_id: campagneId,
        leads: leads.map(l => ({
          email: l.email,
          company_name: l.company,
          first_name: (l.contact_name || '').split(' ')[0] || '',
          custom_variables: { trigger: l.trigger_text || '', bron: l.bron || '', trigger_url: l.trigger_url || '' },
        })),
      }),
    });
    return { mock: false, campagne: campagneId, aantal: leads.length, antwoord: body };
  },
};

/* ==========================================================
   DOMEINEN EN MAILBOXEN
   ========================================================== */

const domeinprovider = {
  naam: 'Domeinprovider',
  envVar: 'MAILDOSO_API_KEY',
  doel: 'Domeinen registreren en mailboxen aanmaken',
  configured() { return Boolean(env('MAILDOSO_API_KEY')); },

  /**
   * Bestellen is met opzet nooit automatisch. Deze methode geeft een
   * voorstel terug dat een mens moet bevestigen. Een systeem dat zelf
   * domeinen koopt op basis van een rekensom is een systeem dat op een
   * ochtend zestig domeinen heeft gekocht door een verkeerde instelling.
   */
  async voorstelBestelling({ domeinen, mailboxenPerDomein }) {
    return {
      mock: !this.configured(),
      bevestiging_vereist: true,
      toelichting: 'Bestellingen worden nooit automatisch uitgevoerd. Bevestig handmatig.',
      domeinen,
      mailboxen: domeinen * mailboxenPerDomein,
      mailboxen_per_domein: mailboxenPerDomein,
    };
  },
};

/* ==========================================================
   REGISTER
   ========================================================== */

const ALLE = { kvk, tenderned, zoek, verzender, domeinprovider };

/** Overzicht van wat aangesloten is, voor het dashboard. */
function status() {
  return Object.entries(ALLE).map(([sleutel, a]) => ({
    sleutel,
    naam: a.naam,
    doel: a.doel,
    env_var: a.envVar,
    aangesloten: a.configured(),
  }));
}

/** Draait het systeem ergens op echte data. */
function anyLive() { return status().some(a => a.aangesloten); }

module.exports = { ...ALLE, ALLE, status, anyLive, request };
