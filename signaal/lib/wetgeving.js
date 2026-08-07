'use strict';
/**
 * Signaal / de twee poorten
 *
 * BELANGRIJK, EN ANDERS DAN VEEL BUITENLANDSE OPZETTEN AANNEMEN:
 *
 * Nederland kent GEEN algemeen opt-outregime voor zakelijke e-mail. Sinds
 * 1 oktober 2009 is het opt-invereiste van artikel 11.7 lid 1
 * Telecommunicatiewet uitgebreid naar rechtspersonen. Uitgangspunt voor
 * B2B is dus toestemming, niet afmelden.
 *
 * De enige echte uitzondering is artikel 11.7 lid 2, en dat is een
 * cumulatieve toets van drie delen die ALLE DRIE moeten kloppen:
 *
 *   1. de ontvanger is een rechtspersoon, of een natuurlijk persoon die
 *      handelt in de uitoefening van beroep of bedrijf, EN
 *   2. je gebruikt contactgegevens die de ontvanger ZELF daarvoor heeft
 *      bestemd en bekendgemaakt, EN
 *   3. je gebruik past bij de doeleinden die de ontvanger aan die
 *      gegevens heeft verbonden.
 *
 * "Bestemd en bekendgemaakt" is smaller dan "openbaar vindbaar". Een
 * info@ adres op een contactpagina is bekendgemaakt voor algemeen
 * contact, niet voor ongevraagde aanbiedingen. Dat onderscheid is precies
 * waar de meeste koude e-mailsystemen juridisch omvallen.
 *
 * Daarnaast geldt de AVG apart. Voldoen aan 11.7 levert GEEN AVG-grondslag
 * op, en een AVG-grondslag ontslaat je niet van 11.7. Twee poorten dus,
 * die allebei open moeten.
 *
 * Dit bestand is geen juridisch advies. Het zet de regels om in controles.
 */

const db = require('./db');

/* ==========================================================
   GRONDSLAGEN VOOR VERZENDEN, POORT 1
   ========================================================== */

const GRONDSLAGEN = {
  consent: {
    label: 'Toestemming',
    artikel: 'Tw 11.7 lid 1',
    eis: 'Aantoonbare, vrije, specifieke en geinformeerde toestemming, vastgelegd met tijdstip en bron.',
  },
  b2b_designated: {
    label: 'Zakelijk bestemd adres',
    artikel: 'Tw 11.7 lid 2',
    eis: 'Rechtspersoon of beroepsmatig handelend persoon, adres door henzelf bestemd en bekendgemaakt voor dit doel, en gebruik past bij dat doel.',
  },
  customer_relationship: {
    label: 'Bestaande klantrelatie',
    artikel: 'Tw 11.7 lid 3',
    eis: 'Gegevens verkregen bij een AFGERONDE verkoop, gebruik voor eigen gelijksoortige producten, met afmeldmogelijkheid bij verkrijging en in elk bericht.',
  },
};

/**
 * Sterkte van de bestemming. Alleen STRONG draagt lid 2 zelfstandig.
 * WEAK betekent: wel openbaar, maar niet bestemd voor aanbiedingen.
 */
const BESTEMMING = {
  STRONG: {
    label: 'Uitdrukkelijk bestemd',
    uitleg: 'Adres gepubliceerd met een uitnodiging om aanbiedingen te sturen, of een functioneel adres als sales@, inkoop@ of aanbiedingen@.',
    draagt_lid2: true,
  },
  WEAK: {
    label: 'Alleen bekendgemaakt',
    uitleg: 'Generiek info@ of contact@ op een contactpagina. Bekendgemaakt voor algemeen contact, niet bestemd voor ongevraagde aanbiedingen. Draagt lid 2 niet.',
    draagt_lid2: false,
  },
  NONE: {
    label: 'Niet bestemd',
    uitleg: 'Geraden, afgeleid, of gekocht adres. Draagt lid 2 niet.',
    draagt_lid2: false,
  },
  ONBEKEND: {
    label: 'Onbekend',
    uitleg: 'Nog niet beoordeeld. Telt als niet bestemd.',
    draagt_lid2: false,
  },
};

/* Adresvormen die wijzen op een uitdrukkelijke bestemming. */
const STERKE_LOCALPARTS = ['sales', 'verkoop', 'inkoop', 'aanbiedingen', 'offertes', 'offerte', 'aanbod', 'procurement', 'purchasing', 'tenders', 'aanbesteding'];
const ZWAKKE_LOCALPARTS = ['info', 'contact', 'hallo', 'hello', 'mail', 'algemeen', 'office', 'welkom'];
/* Deze zijn nooit een grondslag voor verkoop: verkeerd doel per lid 2 deel 3. */
const VERKEERD_DOEL = ['support', 'helpdesk', 'klantenservice', 'service', 'factuur', 'facturen', 'boekhouding', 'administratie', 'pers', 'press', 'privacy', 'avg', 'security', 'abuse', 'sollicitatie', 'vacature', 'recruitment', 'jobs'];

function localpart(email) {
  const s = String(email || '').toLowerCase().trim();
  const i = s.indexOf('@');
  return i < 0 ? '' : s.slice(0, i);
}

/**
 * Bepaalt of een adres een persoonsgegeven is.
 * We kijken naar het hele record, niet alleen naar het adres: een
 * contactpersoon bij een generiek adres maakt het alsnog persoonlijk.
 */
function classificeer(lead) {
  const lp = localpart(lead.email);
  if (!lp) return 'ONBEKEND';

  const generiek = [...ZWAKKE_LOCALPARTS, ...STERKE_LOCALPARTS, ...VERKEERD_DOEL].includes(lp);
  const heeftNaam = Boolean(lead.contact_name && String(lead.contact_name).trim());

  // een naam in het adres, of een naam bij het record, maakt het persoonlijk
  const naamachtig = /^[a-z]+([._-][a-z]+)+$/.test(lp) || (!generiek && lp.length > 2);
  if (naamachtig || heeftNaam) return 'PERSONAL';
  if (generiek) return 'NON_PERSONAL';
  return 'ONBEKEND';
}

/**
 * Beoordeelt de bestemming van een adres op basis van de adresvorm.
 * Let op: dit is een VOORSTEL, geen bewijs. Lid 2 vraagt om bewijs dat de
 * ontvanger het adres zelf heeft bestemd, en dat kan een systeem niet uit
 * de adresvorm afleiden. Daarom mag deze functie de grondslag niet zetten,
 * alleen voorsorteren.
 */
function beoordeelBestemming(lead) {
  const lp = localpart(lead.email);
  if (!lp) return { voorstel: 'NONE', reden: 'geen adres' };
  if (VERKEERD_DOEL.includes(lp)) {
    return { voorstel: 'NONE', reden: `Adres "${lp}@" is bekendgemaakt voor een ander doel. Lid 2 deel 3 staat verkoop naar dit adres niet toe.` };
  }
  if (STERKE_LOCALPARTS.includes(lp)) {
    return { voorstel: 'STRONG', reden: `Functioneel adres "${lp}@" wijst op bestemming voor aanbiedingen. Leg het bewijs alsnog vast.` };
  }
  if (ZWAKKE_LOCALPARTS.includes(lp)) {
    return { voorstel: 'WEAK', reden: `Generiek adres "${lp}@" is bekendgemaakt, maar niet bestemd voor ongevraagde aanbiedingen.` };
  }
  return { voorstel: 'NONE', reden: 'Persoonlijk of afgeleid adres. Bestemming moet blijken uit bewijs, niet uit de adresvorm.' };
}

/* ==========================================================
   POORT 1: MAG DIT BERICHT VERSTUURD WORDEN
   ========================================================== */

function poort1(lead) {
  const redenen = [];
  const basis = lead.legal_basis;

  if (!basis) {
    const b = beoordeelBestemming(lead);
    redenen.push(`Geen grondslag vastgelegd. Nederland kent voor zakelijke e-mail een opt-inregime, dus zonder grondslag mag er niets uit. ${b.reden}`);
    return { mag: false, redenen, voorstel: b.voorstel };
  }
  if (!GRONDSLAGEN[basis]) {
    redenen.push(`Onbekende grondslag "${basis}".`);
    return { mag: false, redenen };
  }

  if (basis === 'b2b_designated') {
    const d = BESTEMMING[lead.designation] || BESTEMMING.ONBEKEND;
    if (!d.draagt_lid2) {
      redenen.push(`Grondslag lid 2 ingeroepen, maar de bestemming is "${lead.designation}". ${d.uitleg}`);
    }
    if (!lead.evidence_url && !lead.evidence_note) {
      redenen.push('Lid 2 vraagt bewijs dat de ontvanger het adres zelf heeft bestemd en bekendgemaakt. Dat bewijs ontbreekt.');
    }
    const lp = localpart(lead.email);
    if (VERKEERD_DOEL.includes(lp)) {
      redenen.push(`Adres "${lp}@" is voor een ander doel bekendgemaakt. Deel 3 van de toets faalt.`);
    }
  }

  if (basis === 'consent') {
    if (!lead.evidence_url && !lead.evidence_note) redenen.push('Toestemming moet aantoonbaar zijn. Leg vast wanneer en waar die is gegeven.');
  }

  if (basis === 'customer_relationship') {
    const verkoop = db.get("SELECT id FROM outcomes WHERE lead_id = ? AND type = 'closed'", [lead.id]);
    if (!verkoop) redenen.push('Lid 3 vraagt een AFGERONDE verkoop. Een offerte, download of webinar telt niet.');
  }

  return { mag: redenen.length === 0, redenen, grondslag: GRONDSLAGEN[basis] };
}

/* ==========================================================
   POORT 2: MAG DIT PERSOONSGEGEVEN VERWERKT WORDEN
   ========================================================== */

function actieveLia() {
  return db.get('SELECT * FROM lia WHERE active = 1 ORDER BY dated_at DESC LIMIT 1');
}

function poort2(lead) {
  const redenen = [];
  const klasse = lead.record_class && lead.record_class !== 'ONBEKEND' ? lead.record_class : classificeer(lead);

  if (klasse === 'NON_PERSONAL') return { mag: true, klasse, redenen: [], toelichting: 'Generiek adres zonder herleidbare persoon. AVG-poort niet van toepassing.' };

  const lia = actieveLia();
  if (!lia) {
    redenen.push('Persoonsgegeven zonder afweging gerechtvaardigd belang. Die afweging moet bestaan voor de eerste verzending, niet erna.');
  } else if (lead.found_at && lia.dated_at > String(lead.found_at).slice(0, 10)) {
    redenen.push(`De afweging is gedateerd ${lia.dated_at}, na het moment waarop deze lead is verzameld. Een afweging achteraf dekt de verwerking niet.`);
  }

  if (!lead.source_id && !lead.acquired_method) {
    redenen.push('Herkomst ontbreekt. Zonder herleidbare bron kun je de informatieplicht van artikel 14 niet nakomen.');
  }

  return { mag: redenen.length === 0, klasse, redenen, lia: lia || null };
}

/** Beide poorten samen. */
function beoordeel(lead) {
  const p1 = poort1(lead);
  const p2 = poort2(lead);
  return {
    mag: p1.mag && p2.mag,
    poort1: p1,
    poort2: p2,
    redenen: [...p1.redenen.map(r => `[Tw 11.7] ${r}`), ...p2.redenen.map(r => `[AVG] ${r}`)],
  };
}

/* ==========================================================
   BEREIKBEREKENING
   Het getal dat in vrijwel elke opzet ontbreekt: hoeveel blijft er
   over als je de poorten eerlijk toepast. Bouw geen verzendcapaciteit
   voor volume dat je niet rechtmatig kunt vullen.
   ========================================================== */

function bereik() {
  const totaal = db.get('SELECT COUNT(*) AS n FROM leads')?.n || 0;
  const metEmail = db.get('SELECT COUNT(*) AS n FROM leads WHERE email IS NOT NULL')?.n || 0;

  const leads = db.all('SELECT * FROM leads WHERE email IS NOT NULL');
  let poort1Ok = 0, beide = 0;
  const perBestemming = {};
  const perKlasse = {};
  const redenTelling = {};

  for (const l of leads) {
    const b = beoordeel(l);
    const voorstel = l.designation && l.designation !== 'ONBEKEND' ? l.designation : beoordeelBestemming(l).voorstel;
    perBestemming[voorstel] = (perBestemming[voorstel] || 0) + 1;
    const klasse = l.record_class && l.record_class !== 'ONBEKEND' ? l.record_class : classificeer(l);
    perKlasse[klasse] = (perKlasse[klasse] || 0) + 1;
    if (b.poort1.mag) poort1Ok++;
    if (b.mag) beide++;
    else for (const r of b.redenen) {
      const kort = r.slice(0, 90);
      redenTelling[kort] = (redenTelling[kort] || 0) + 1;
    }
  }

  const werkdagen = db.getNumber('werkdagen_per_maand', 21.7);
  const doel = db.getNumber('doel_contacten_per_maand', 7000);

  return {
    totaal_leads: totaal,
    met_adres: metEmail,
    poort1_haalbaar: poort1Ok,
    beide_poorten: beide,
    verlies_percentage: metEmail > 0 ? Number((1 - beide / metEmail).toFixed(4)) : null,
    per_bestemming: perBestemming,
    per_klasse: perKlasse,
    top_redenen: Object.entries(redenTelling).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([reden, n]) => ({ reden, n })),
    doel_per_maand: doel,
    rechtmatig_per_dag: Number((beide / werkdagen).toFixed(1)),
    oordeel: beide === 0
      ? 'Op dit moment is er geen enkele lead die beide poorten haalt. Verzendcapaciteit bijbouwen heeft dan geen zin: er is niets om rechtmatig te versturen.'
      : beide < doel * 0.25
        ? `Slechts ${beide} van ${metEmail} adressen halen beide poorten. Dat is ver onder het doel van ${doel} per maand. Het knelpunt is niet capaciteit maar rechtmatig bereik.`
        : `${beide} adressen halen beide poorten.`,
  };
}

module.exports = {
  GRONDSLAGEN, BESTEMMING, STERKE_LOCALPARTS, ZWAKKE_LOCALPARTS, VERKEERD_DOEL,
  localpart, classificeer, beoordeelBestemming, poort1, poort2, beoordeel, actieveLia, bereik,
};
