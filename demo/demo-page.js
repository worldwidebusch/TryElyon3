/* ==========================================================================
   ELYON · DEMO PAGE CONTROLLER
   --------------------------------------------------------------------------
   Reads the slug from the URL, looks up its entry in demo-config.js, and
   renders the personalized Voice AI demo into the template in index.html.
   Handles: active / not-found / expired states, WhatsApp CTAs, analytics,
   and safe widget mounting with a loading + error fallback.
   Depends on: demo-config.js, widget-loader.js (loaded before this file).
   ========================================================================== */
(function () {
  'use strict';

  /* ---- analytics: reuse the site's GA4 / Meta Pixel wiring. Never adds a
     provider; if none is present the calls are no-ops. Mirrors trackEvent()
     in /index.html. ---- */
  function trackEvent(ev, props) {
    try {
      if (window.gtag) window.gtag('event', ev, props || {});
      if (window.fbq) window.fbq('trackCustom', ev, props || {});
    } catch (err) { /* analytics must never break the page */ }
  }

  /* ---- copy, per language. Only what differs from the HTML lives here. ---- */
  var COPY = {
    es: {
      badge: 'Demo personalizada',
      headline: function (d) { return 'Conoce a la recepcionista de IA de ' + d.businessName; },
      lede: 'Pruébala ahora. Habla como si fueras un cliente y descubre cómo atiende consultas, recopila datos y solicita el seguimiento del equipo.',
      cardTitle: 'Habla con tu recepcionista de IA',
      steps: [
        'Pulsa el botón para comenzar.',
        'Permite el acceso al micrófono.',
        'Habla como si fueras un cliente real.'
      ],
      qsLabel: 'Preguntas de prueba sugeridas',
      questions: [
        'Quiero solicitar una cita.',
        'Necesito información sobre un servicio.',
        '¿Pueden contactarme por WhatsApp?'
      ],
      notice: 'Esta es una demostración personalizada. Los servicios, horarios, respuestas, herramientas y acciones se configuran completamente antes de la activación.',
      bfEyebrow: 'Por qué Elyon',
      bfH: 'Una recepcionista de IA que trabaja como parte de tu equipo',
      bfLede: 'Se configura por completo a la medida de tu negocio y atiende cada contacto al instante, para que no pierdas ni una sola oportunidad.',
      benefits: [
        { title: 'Totalmente personalizable', text: 'Se adapta a tus servicios, precios, horarios y tono de voz. Habla como tu negocio, no como un robot genérico.' },
        { title: 'Disponible 24/7', text: 'Responde al instante de día, de noche, fines de semana y días festivos. Nunca deja una consulta sin atender.' },
        { title: 'Primera línea o respaldo', text: 'Ponla a atender todas las llamadas, o solo cuando tu equipo no alcanza a contestar. Tú decides cómo trabaja.' },
        { title: 'También en WhatsApp, Facebook e Instagram', text: 'Además de la voz, la versión de chat responde en WhatsApp, Facebook Messenger e Instagram desde un mismo lugar.' },
        { title: 'Ahorra tiempo y dinero', text: 'Automatiza las consultas repetitivas y libera a tu equipo del teléfono, sin sumar más personal para crecer.' },
        { title: 'Más clientes atendidos', text: 'Contesta al momento, resuelve dudas, solicita los datos del cliente y pide el seguimiento del equipo cuando hace falta.' }
      ],
      loading: 'Iniciando la recepcionista…',
      wErrTitle: 'No se pudo cargar la demo',
      wErrBody: 'La recepcionista de IA no cargó en este dispositivo o red. Escríbenos por WhatsApp y te la mostramos al instante.',
      wErrBtn: 'Escríbenos por WhatsApp',
      convertH: '¿Quieres probarla con tus clientes reales?',
      convertP: function (d) { return 'Podemos activar una prueba gratuita de ' + d.trialDays + ' días y adaptar la recepcionista a los servicios, horarios y forma de trabajar de tu negocio.'; },
      ctaTrial: 'Activar mi prueba gratuita',
      ctaTech: 'Tengo una pregunta técnica',
      waTrial: function (d) { return 'Hola, probé la demo de ' + d.businessName + ' y quiero activar la prueba gratuita de ' + d.trialDays + ' días.'; },
      waTech: function (d) { return 'Hola, probé la demo de ' + d.businessName + ' y tengo una pregunta técnica sobre el funcionamiento o las integraciones.'; },
      metaCity: 'Ciudad',
      metaIndustry: 'Industria',
      metaTrial: 'Prueba',
      trialUnit: function (d) { return d.trialDays + ' días'; },
      endedTitle: 'Esta demostración ha finalizado',
      endedBody: 'La demo personalizada ya no está activa. Con gusto reactivamos una nueva para tu negocio.',
      endedBtn: 'Escríbenos por WhatsApp',
      nfTitle: 'Demostración no encontrada',
      nfBody: 'Este enlace de demo no es válido o ya no está activo. Verifica la dirección o contáctanos.',
      nfBtn: 'Ir a tryelyon.com'
    },
    en: {
      badge: 'Personalized demo',
      headline: function (d) { return 'Meet the AI receptionist for ' + d.businessName; },
      lede: 'Try it now. Speak as if you were a customer and see how it handles questions, collects details and requests team follow-up.',
      cardTitle: 'Talk to your AI receptionist',
      steps: [
        'Press the button to start.',
        'Allow microphone access.',
        'Speak as if you were a real customer.'
      ],
      qsLabel: 'Suggested test questions',
      questions: [
        'I would like to book an appointment.',
        'I need information about a service.',
        'Can you contact me on WhatsApp?'
      ],
      notice: 'This is a personalized demo. Services, hours, responses, tools and actions are fully configured before activation.',
      bfEyebrow: 'Why Elyon',
      bfH: 'An AI receptionist that works like part of your team',
      bfLede: 'Fully configured to fit your business, answering every contact instantly so you never miss an opportunity.',
      benefits: [
        { title: 'Fully customizable', text: 'Adapts to your services, prices, hours and tone of voice. It sounds like your business, not a generic bot.' },
        { title: 'Available 24/7', text: 'Responds instantly day, night, weekends and holidays. It never leaves a question unanswered.' },
        { title: 'First line or backup', text: 'Have it answer every call, or only when your team can’t pick up. You decide how it works.' },
        { title: 'Also on WhatsApp, Facebook & Instagram', text: 'Beyond voice, the chat version replies on WhatsApp, Facebook Messenger and Instagram from one place.' },
        { title: 'Saves time and money', text: 'Automates repetitive questions and frees your team from the phone, without hiring more people to grow.' },
        { title: 'More customers served', text: 'Answers on the spot, resolves questions, collects the customer’s details and requests team follow-up when needed.' }
      ],
      loading: 'Starting the receptionist…',
      wErrTitle: 'The demo could not load',
      wErrBody: 'The AI receptionist did not load on this device or network. Message us on WhatsApp and we will show it to you right away.',
      wErrBtn: 'Message us on WhatsApp',
      convertH: 'Want to try it with your real customers?',
      convertP: function (d) { return 'We can activate a ' + d.trialDays + '-day free trial and tailor the receptionist to your services, hours and the way your business works.'; },
      ctaTrial: 'Activate my free trial',
      ctaTech: 'I have a technical question',
      waTrial: function (d) { return 'Hi, I tried the ' + d.businessName + ' demo and I want to activate the ' + d.trialDays + '-day free trial.'; },
      waTech: function (d) { return 'Hi, I tried the ' + d.businessName + ' demo and I have a technical question about how it works or the integrations.'; },
      metaCity: 'City',
      metaIndustry: 'Industry',
      metaTrial: 'Trial',
      trialUnit: function (d) { return d.trialDays + ' days'; },
      endedTitle: 'This demo has ended',
      endedBody: 'This personalized demo is no longer active. We are happy to spin up a fresh one for your business.',
      endedBtn: 'Message us on WhatsApp',
      nfTitle: 'Demo not found',
      nfBody: 'This demo link is invalid or no longer active. Please check the address or contact us.',
      nfBtn: 'Go to tryelyon.com'
    }
  };

  /* ---- helpers ---- */
  function $(id) { return document.getElementById(id); }
  function show(id) { var el = $(id); if (el) el.classList.remove('hidden'); }
  function setText(id, txt) { var el = $(id); if (el) el.textContent = txt; }

  /* ---- business-type template: colors, fonts, motif, favicon ----
     Templates live in demo-templates.js; this applies one to the page. */
  function hexToRgba(hex, a) {
    var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''));
    if (!m) return null;
    var n = parseInt(m[1], 16);
    return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  function applyTemplate(tpl) {
    if (!tpl) return;
    var root = document.documentElement;
    var map = {
      '--t-bg': tpl.palette.bg,
      '--t-surface': tpl.palette.surface,
      '--t-ink': tpl.palette.ink,
      '--t-ink-soft': tpl.palette.inkSoft,
      '--t-accent': tpl.palette.accent,
      '--t-accent-dark': tpl.palette.accentDark,
      '--t-on-accent': tpl.palette.onAccent,
      '--t-card-bg': tpl.palette.cardBg,
      '--t-card-ink': tpl.palette.cardInk,
      '--t-rule': tpl.palette.rule,
      '--t-disp': tpl.displayFamily,
      '--t-body': tpl.bodyFamily,
      '--t-motif-ink': tpl.motifInk || hexToRgba(tpl.palette.ink, 0.05) || 'rgba(0,0,0,.05)'
    };
    for (var k in map) { if (map[k]) root.style.setProperty(k, map[k]); }

    // template fonts (Google Fonts, loaded once)
    if (tpl.fontCss && !document.querySelector('link[data-tpl-font]')) {
      var l = document.createElement('link');
      l.rel = 'stylesheet';
      l.href = tpl.fontCss;
      l.setAttribute('data-tpl-font', '1');
      document.head.appendChild(l);
    }

    // background motif
    document.body.setAttribute('data-motif', tpl.motif || 'none');

    // favicon + theme color tinted to the template accent
    var fav = $('favicon');
    if (fav) {
      var a = encodeURIComponent(tpl.palette.accent);
      var o = encodeURIComponent(tpl.palette.onAccent);
      fav.href = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="18" fill="' + a + '"/><path d="M50 24a12 12 0 0 0-12 12v14a12 12 0 0 0 24 0V36a12 12 0 0 0-12-12Z" fill="' + o + '"/><path d="M30 50a20 20 0 0 0 40 0h-7a13 13 0 0 1-26 0Zm17 26h6v-8h-6Z" fill="' + o + '"/></svg>';
    }
    var tc = document.querySelector('meta[name="theme-color"]');
    if (tc) tc.setAttribute('content', tpl.palette.cardBg);
  }

  function resolveTemplate(demo) {
    if (typeof elyonTemplate !== 'function') return null; // demo-templates.js missing
    return elyonTemplate(demo && demo.template);
  }

  function slugFromLocation() {
    // Primary: path segment after /demo/. Fallback: ?slug= (local/file use).
    var m = location.pathname.match(/\/demo\/([^\/?#]+)/i);
    if (m && m[1] && m[1].toLowerCase() !== 'index.html') {
      return decodeURIComponent(m[1]).toLowerCase();
    }
    var q = new URLSearchParams(location.search).get('slug');
    return q ? q.toLowerCase() : '';
  }

  function waUrl(number, text) {
    return 'https://wa.me/' + number + '?text=' + encodeURIComponent(text);
  }

  function renderNotFound(t) {
    document.title = 'Demo · Elyon';
    setText('nf-title', t.nfTitle);
    setText('nf-body', t.nfBody);
    var btn = $('nf-btn');
    if (btn) { btn.textContent = t.nfBtn; btn.setAttribute('href', 'https://tryelyon.com/'); }
    show('view-notfound');
  }

  function renderEnded(demo, t) {
    var number = elyonWhatsApp(demo);
    document.title = 'Demo · ' + demo.businessName + ' | Elyon';
    setText('ended-title', t.endedTitle);
    setText('ended-body', t.endedBody);
    var btn = $('ended-btn');
    if (btn) { btn.textContent = t.endedBtn; btn.setAttribute('href', waUrl(number, t.waTech(demo))); }
    show('view-ended');
    trackEvent('demo_view', { slug: demo.slug, state: 'ended' });
  }

  function buildList(el, items, tag) {
    if (!el) return;
    el.innerHTML = '';
    items.forEach(function (txt) {
      var li = document.createElement(tag || 'li');
      li.textContent = txt;
      el.appendChild(li);
    });
  }

  function renderActive(demo, t) {
    var number = elyonWhatsApp(demo);
    var tpl = resolveTemplate(demo);

    // <head>
    document.title = 'Demo IA para ' + demo.businessName + ' | Elyon';
    document.documentElement.lang = demo.language || 'es';

    // header: branded for the business, not Elyon
    var brand = $('brand-name');
    if (brand) {
      brand.textContent = '';
      brand.appendChild(document.createTextNode(demo.businessName));
      var sm = document.createElement('small');
      sm.textContent = [demo.industry, demo.city].filter(Boolean).join(' · ');
      brand.appendChild(sm);
    }
    setText('top-chip', t.badge);

    // hero
    setText('badge-text', t.badge);
    setText('headline', t.headline(demo));
    setText('lede', t.lede);

    // meta pills
    var meta = $('meta');
    if (meta) {
      meta.innerHTML = '';
      [[t.metaIndustry, demo.industry], [t.metaCity, demo.city], [t.metaTrial, t.trialUnit(demo)]]
        .forEach(function (pair) {
          if (!pair[1]) return;
          var span = document.createElement('span');
          span.className = 'pill';
          var b = document.createElement('b');
          b.textContent = pair[0];
          span.appendChild(b);
          span.appendChild(document.createTextNode(pair[1]));
          meta.appendChild(span);
        });
    }

    // widget card
    setText('card-title', t.cardTitle);
    buildList($('steps'), t.steps);
    setText('qs-label', t.qsLabel);
    // suggested questions: per-business override > industry template > generic
    var questions = demo.questions ||
      (demo.language === 'es' && tpl && tpl.questions_es) || t.questions;
    buildList($('qs-list'), questions);
    setText('demo-notice', t.notice);
    setText('loading-text', t.loading);

    // benefits / why-elyon grid
    setText('bf-eyebrow', t.bfEyebrow);
    setText('bf-h', t.bfH);
    setText('bf-lede', t.bfLede);
    var bg = $('benefits-grid');
    if (bg && t.benefits) {
      bg.innerHTML = '';
      t.benefits.forEach(function (b, i) {
        var card = document.createElement('div');
        card.className = 'bf-card';
        var idx = document.createElement('span');
        idx.className = 'idx';
        idx.textContent = (i + 1 < 10 ? '0' : '') + (i + 1);
        var h = document.createElement('h3');
        h.textContent = b.title;
        var p = document.createElement('p');
        p.textContent = b.text;
        card.appendChild(idx);
        card.appendChild(h);
        card.appendChild(p);
        bg.appendChild(card);
      });
    }

    // conversion
    setText('cv-h', t.convertH);
    setText('cv-p', t.convertP(demo));
    var trial = $('cta-trial');
    if (trial) {
      trial.textContent = t.ctaTrial;
      trial.setAttribute('href', waUrl(number, t.waTrial(demo)));
      trial.addEventListener('click', function () {
        trackEvent('demo_trial_click', { slug: demo.slug });
      });
    }
    var tech = $('cta-tech');
    if (tech) {
      tech.textContent = t.ctaTech;
      tech.setAttribute('href', waUrl(number, t.waTech(demo)));
      tech.addEventListener('click', function () {
        trackEvent('demo_tech_click', { slug: demo.slug });
      });
    }

    show('view-active');
    trackEvent('demo_view', { slug: demo.slug, state: 'active' });

    // ---- widget ----
    var zone = $('widget-zone');
    var loading = $('widget-loading');

    function showWidgetError() {
      if (loading) loading.classList.add('hidden');
      zone.setAttribute('data-widget-state', 'error');
      var box = document.createElement('div');
      box.className = 'w-msg';
      var h = document.createElement('div'); h.className = 't'; h.textContent = t.wErrTitle;
      var p = document.createElement('p'); p.textContent = t.wErrBody;
      var a = document.createElement('a'); a.className = 'btn fill'; a.style.marginTop = '1rem';
      a.textContent = t.wErrBtn; a.setAttribute('href', waUrl(number, t.waTech(demo)));
      a.setAttribute('target', '_blank'); a.setAttribute('rel', 'noopener');
      box.appendChild(h); box.appendChild(p); box.appendChild(a);
      zone.appendChild(box);
      trackEvent('demo_widget_error', { slug: demo.slug });
    }

    if (!elyonWidgetConfigured(demo)) {
      // The embed is still the unfilled placeholder — surface it plainly.
      if (loading) loading.classList.add('hidden');
      zone.setAttribute('data-widget-state', 'error');
      var box = document.createElement('div');
      box.className = 'w-msg';
      box.innerHTML = '<div class="t">Widget sin configurar</div>' +
        '<p>Pega el código del widget de voz en <code>demo-config.js</code> para activar esta demo.</p>';
      zone.appendChild(box);
      return;
    }

    // Hide the loading skin once the widget reports ready (via the zone attr).
    var readyWatch = null;
    if (window.MutationObserver) {
      readyWatch = new MutationObserver(function () {
        if (zone.getAttribute('data-widget-state') === 'ready') {
          if (loading) loading.classList.add('hidden');
          readyWatch.disconnect();
        }
      });
      readyWatch.observe(zone, { attributes: true, attributeFilter: ['data-widget-state'] });
    }

    ElyonWidget.mount({
      mount: zone,
      embedHtml: demo.widget.embedHtml,
      onError: function () {
        if (readyWatch) readyWatch.disconnect();
        showWidgetError();
      }
    });
  }

  /* ---- boot ---- */
  function init() {
    var slug = slugFromLocation();
    var demo = elyonFindDemo(slug);
    var lang = (demo && COPY[demo.language]) ? demo.language : 'es';
    var t = COPY[lang];

    // Skin the page for the business type (neutral template when unknown).
    applyTemplate(resolveTemplate(demo));

    if (!demo || demo.status !== 'active') {
      renderNotFound(COPY.es); // not-found copy stays Spanish (site default)
      return;
    }
    if (elyonDemoExpired(demo)) {
      // keep the branded header even on the ended state
      var brand = $('brand-name');
      if (brand) brand.textContent = demo.businessName;
      renderEnded(demo, t);
      return;
    }
    renderActive(demo, t);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
