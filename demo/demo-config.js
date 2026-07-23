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

var ELYON_DEMOS = [
  {
    slug: 'the-shop-automotive',
    businessName: 'The Shop Automotive Service',
    industry: 'Taller automotriz',
    city: 'Querétaro, México',
    language: 'es',
    trialDays: 7,
    status: 'active',
    expiresAt: null,
    whatsappNumber: ELYON_WA_DEFAULT, // uses the Elyon WhatsApp Business line
    widget: {
      placement: 'inline',
      /* ----------------------------------------------------------------
         Voice AI widget embed, verbatim from GoHighLevel.
         IMPORTANT: inside GoHighLevel, this widget's "Widget Placement"
         must be set to Embedded / Inline (NOT floating) so it renders
         inside the card below instead of as a floating bubble.
         ---------------------------------------------------------------- */
      embedHtml: `<script src="https://widgets.leadconnectorhq.com/loader.js" data-resources-url="https://widgets.leadconnectorhq.com/chat-widget/loader.js" data-widget-id="6a6167b1cbb3de01dd6c4421"></script>`
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
