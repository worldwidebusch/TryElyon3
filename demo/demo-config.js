/* ==========================================================================
   ELYON · PERSONALIZED VOICE AI DEMO PAGES — CONFIGURATION
   --------------------------------------------------------------------------
   This is the ONLY file you edit to publish a new prospect demo.
   Add one object to ELYON_DEMOS below and the page at
   /demo/<slug> comes to life. Do not duplicate the page markup.

   FIELDS
   ------
   slug            URL segment. tryelyon.com/demo/<slug>. Lowercase, dashes.
   businessName    Shown in headline, title and WhatsApp messages.
   industry        Free text (e.g. "Taller automotriz").
   city            Free text (e.g. "Querétaro, México").
   language        "es" or "en". Drives on-page copy.
   generic         OPTIONAL. true -> the copy is written for "tu negocio"
                   instead of a specific business (the one link you can send
                   to any prospect). businessName is ignored in the copy.
   receptionistName OPTIONAL. The AI receptionist's persona name shown all
                   over the page. Defaults to ELYON_RECEPTIONIST below.
   questions       OPTIONAL array of 3 strings: industry-tailored suggested
                   test questions for this business. Falls back to generic
                   questions when omitted.
   trialDays       Number of free-trial days offered (e.g. 7).
   status          "active"  -> demo is live.
                   "inactive"-> shows the not-found state.
   expiresAt       OPTIONAL. ISO date string ("2026-09-01") or null.
                   When the date has passed the widget is replaced with a
                   tasteful "demo ended" message + WhatsApp button.
   whatsappNumber  Elyon WhatsApp Business number, INTERNATIONAL format,
                   digits only, no "+", spaces or symbols
                   (e.g. "5215512345678"). Falls back to ELYON_WA_DEFAULT.
   widget          The GoHighLevel Voice AI widget for THIS business.
                   {
                     placement : "inline"  // must be Embedded/Inline in GHL
                     embedHtml : `...`      // the FULL embed snippet, verbatim
                   }
                   Paste the complete snippet GoHighLevel gives you between
                   the backticks, unchanged, including every attribute. The
                   loader recreates the <script> so it executes safely and
                   loads only once. Never place API keys here — the GHL embed
                   snippet does not contain any; if yours does, stop.
   ========================================================================== */

/* Default Elyon WhatsApp number (international, digits only, no + / spaces).
   Currently the Elyon WhatsApp Business line (+52 55 9435 6033). */
var ELYON_WA_DEFAULT = '525594356033';

/* Default persona name for the AI receptionist, used across the page copy.
   Override per demo with receptionistName. */
var ELYON_RECEPTIONIST = 'Sofía';

var ELYON_DEMOS = [
  {
    /* THE general demo: one link you can send to any Mexican business.
       tryelyon.com/demo/sofia — copy speaks to "tu negocio", no company
       name. NOTE: needs its own GENERIC Voice AI agent in GoHighLevel
       (e.g. duplicate an existing agent, rename it "Sofía", strip the
       business-specific services) with its own Embedded/Inline chat
       widget — do NOT reuse a client's widget here, the persona would
       answer as that client's business. */
    slug: 'sofia',
    generic: true,
    businessName: 'Elyon',
    industry: 'Para todo tipo de negocio',
    city: '',
    language: 'es',
    receptionistName: ELYON_RECEPTIONIST,
    questions: [
      'Quiero agendar una cita, ¿tienen espacio esta semana?',
      '¿Qué servicios ofrecen y en qué horarios atienden?',
      '¿Me pueden mandar la información por WhatsApp?'
    ],
    trialDays: 7,
    status: 'active',
    expiresAt: null,
    whatsappNumber: ELYON_WA_DEFAULT,
    widget: {
      placement: 'inline',
      /* PENDING: paste the generic Sofía agent's inline embed here
         (<div data-chat-widget ...> + loader <script>, verbatim). */
      embedHtml: `[PASTE_THE_COMPLETE_GHL_WIDGET_EMBED_CODE_HERE]`
    }
  },

  {
    slug: 'the-shop-automotive',
    businessName: 'The Shop Automotive Service',
    industry: 'Taller automotriz',
    city: 'Querétaro, México',
    language: 'es',
    questions: [
      'Quiero agendar una cita para el servicio de mi carro, ¿tienen lugar esta semana?',
      '¿Cuánto me sale la revisión de frenos y en cuánto tiempo me entregan el coche?',
      '¿Me pueden mandar la cotización por WhatsApp cuando esté lista?'
    ],
    trialDays: 7,
    status: 'active',
    expiresAt: null,
    whatsappNumber: ELYON_WA_DEFAULT, // uses the Elyon WhatsApp Business line
    widget: {
      placement: 'inline',
      /* ----------------------------------------------------------------
         GoHighLevel Chat Widget (Embedded / Inline) that hosts the Voice AI
         agent, verbatim. The <div data-chat-widget> is the inline mount the
         loader renders into; data-location-id is a public embed identifier
         (not a secret). Paste both the <div> and the <script>, unchanged.
         ---------------------------------------------------------------- */
      embedHtml: `<div data-chat-widget data-widget-id="6a61922ecbb3de01dd722f05" data-location-id="5ynssMYlwC8Q67rGQchD"></div><script src="https://widgets.leadconnectorhq.com/loader.js" data-resources-url="https://widgets.leadconnectorhq.com/chat-widget/loader.js" data-widget-id="6a61922ecbb3de01dd722f05"></script>`
    }
  },

  {
    /* Prospect contact: Arq. Paola (+52 442 471 1702) — send her the demo
       link once the widget below is configured. City assumed Querétaro from
       the 442 area code; adjust if wrong. */
    slug: 'pool-depot',
    businessName: 'Pool Depot',
    industry: 'Construcción y equipamiento de albercas',
    city: 'Querétaro, México',
    language: 'es',
    questions: [
      'Hola, quiero construir una alberca en mi casa, ¿pueden agendar una visita para hacerme una cotización?',
      'Mi bomba de la alberca está fallando y creo que el filtro ya necesita cambio, ¿qué equipos manejan y dan servicio de mantenimiento?',
      '¿Me pueden mandar la información y la cotización por WhatsApp, por favor?'
    ],
    trialDays: 7,
    status: 'active',
    expiresAt: null,
    whatsappNumber: ELYON_WA_DEFAULT, // CTAs always go to the Elyon line
    widget: {
      placement: 'inline',
      /* ----------------------------------------------------------------
         PENDING: create the Pool Depot Voice AI agent + chat widget in
         GoHighLevel (placement Embedded/Inline), then paste the inline
         embed here: the <div data-chat-widget data-widget-id
         data-location-id> mount AND the loader <script>, verbatim.
         Until then the page shows a "widget sin configurar" notice.
         ---------------------------------------------------------------- */
      embedHtml: `[PASTE_THE_COMPLETE_GHL_WIDGET_EMBED_CODE_HERE]`
    }
  }
];

/* --- lookup helpers (no dependencies) --------------------------------- */
function elyonFindDemo(slug) {
  if (!slug) return null;
  var s = String(slug).toLowerCase();
  for (var i = 0; i < ELYON_DEMOS.length; i++) {
    if (ELYON_DEMOS[i].slug === s) return ELYON_DEMOS[i];
  }
  return null;
}

/* True when a demo has an expiry that is in the past. */
function elyonDemoExpired(demo) {
  if (!demo || !demo.expiresAt) return false;
  var t = Date.parse(demo.expiresAt);
  if (isNaN(t)) return false;
  return Date.now() > t;
}

/* True when the embed still holds the unfilled placeholder token. */
function elyonWidgetConfigured(demo) {
  var html = demo && demo.widget && demo.widget.embedHtml;
  if (!html || !html.trim()) return false;
  return html.indexOf('PASTE_THE_COMPLETE_GHL_WIDGET_EMBED_CODE_HERE') === -1;
}

/* Resolve the WhatsApp number for a demo, with fallback. */
function elyonWhatsApp(demo) {
  var n = (demo && demo.whatsappNumber) || ELYON_WA_DEFAULT;
  return String(n).replace(/[^0-9]/g, '');
}

/* Expose for Node/tests if ever needed; harmless in the browser. */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ELYON_DEMOS: ELYON_DEMOS,
    elyonFindDemo: elyonFindDemo,
    elyonDemoExpired: elyonDemoExpired,
    elyonWidgetConfigured: elyonWidgetConfigured,
    elyonWhatsApp: elyonWhatsApp
  };
}
