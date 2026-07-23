/* ==========================================================================
   ELYON · DEMO PAGE CONTROLLER
   --------------------------------------------------------------------------
   Reads the slug from the URL, looks up its entry in demo-config.js, and
   renders the personalized demo into the template in index.html. One
   universal conversion-optimized design; personalization is text-only
   (business name, industry, city, optional per-business questions).
   Handles: active / not-found / expired states, WhatsApp CTAs (hero,
   sticky, bottom), analytics, and safe widget mounting with loading +
   error fallback. Depends on: demo-config.js, widget-loader.js.

   NOTE ON CLAIMS: every factual claim in the copy below (trial length,
   included usage, setup time, no card, cancel anytime) mirrors what
   tryelyon.com already publishes. If the main site's terms change,
   update this copy to match.
   ========================================================================== */
(function () {
  'use strict';

  /* ---- analytics: reuse the site's GA4 / Meta Pixel wiring. Never adds a
     provider; if none is present the calls are no-ops. ---- */
  function trackEvent(ev, props) {
    try {
      if (window.gtag) window.gtag('event', ev, props || {});
      if (window.fbq) window.fbq('trackCustom', ev, props || {});
    } catch (err) { /* analytics must never break the page */ }
  }

  /* ---- copy, per language ---- */
  var COPY = {
    es: {
      badge: 'Demo personalizada',
      headline: function (d) { return 'Conoce a la recepcionista de IA de ' + d.businessName; },
      lede: 'Pruébala ahora. Habla como si fueras un cliente y descubre cómo atiende consultas, recopila datos y solicita el seguimiento del equipo.',
      heroCta: 'Activar mi prueba gratuita',
      trust: ['Sin tarjeta', 'Sin contratos', 'Cancelas cuando quieras'],
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
      loading: 'Iniciando la recepcionista…',
      hwEyebrow: 'Cómo funciona',
      hwH: 'De esta demo a tu negocio en 4 pasos',
      howSteps: [
        { t: 'Prueba la demo', p: 'Habla con la recepcionista aquí mismo y comprueba cómo atiende a un cliente.' },
        { t: 'Activa tu prueba gratuita', p: 'Nos escribes por WhatsApp y configuramos tu agente con tus servicios, horarios y tono. Queda lista en 3 a 5 días hábiles.' },
        { t: 'Úsala con clientes reales', p: function (d) { return d.trialDays + ' días de prueba con clientes reales. Sin tarjeta y sin compromiso.'; } },
        { t: 'Decide con resultados', p: 'Si te convence, eliges tu plan y sigue trabajando. Si no, no pagas nada.' }
      ],
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
      fqEyebrow: 'Preguntas frecuentes',
      fqH: 'Lo que normalmente nos preguntan',
      faq: [
        { q: '¿Suena robótica?', a: 'No. Tu agente se configura con los servicios, precios y tono de voz de tu negocio, y pasa la conversación a una persona de tu equipo cuando el caso lo necesita.' },
        { q: '¿La prueba gratuita es realmente gratis?', a: 'Sí, sin tarjeta. Incluye hasta 150 conversaciones de IA y 30 minutos de voz durante la prueba. Si superas el uso incluido, el agente se pausa y tú decides si continuar.' },
        { q: '¿Qué pasa cuando termina la prueba?', a: 'Continúas solo si quieres. Sin contratos y puedes cancelar cuando quieras. El costo de configuración aplica únicamente si decides quedarte con tu agente.' },
        { q: '¿En cuánto tiempo queda lista?', a: 'La mayoría de los agentes quedan activos entre 3 y 5 días hábiles después de que nos envías la información de tu negocio.' }
      ],
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
      trialUnit: function (d) { return d.trialDays + ' días gratis'; },
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
      heroCta: 'Activate my free trial',
      trust: ['No card required', 'No contracts', 'Cancel anytime'],
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
      loading: 'Starting the receptionist…',
      hwEyebrow: 'How it works',
      hwH: 'From this demo to your business in 4 steps',
      howSteps: [
        { t: 'Try the demo', p: 'Talk to the receptionist right here and see how it treats a customer.' },
        { t: 'Activate your free trial', p: 'Message us on WhatsApp and we configure your agent with your services, hours and tone. Live in 3 to 5 business days.' },
        { t: 'Use it with real customers', p: function (d) { return d.trialDays + ' days of trial with real customers. No card, no commitment.'; } },
        { t: 'Decide with results', p: 'If it convinces you, pick your plan and keep going. If not, you pay nothing.' }
      ],
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
      fqEyebrow: 'FAQ',
      fqH: 'What people usually ask us',
      faq: [
        { q: 'Will it sound robotic?', a: 'No. Your agent is configured with your services, prices and tone of voice, and it hands the conversation to a person on your team whenever a case needs one.' },
        { q: 'Is the free trial really free?', a: 'Yes, no card required. It includes up to 150 AI conversations and 30 voice minutes during the trial. If you pass the included usage, the agent pauses and you decide whether to continue.' },
        { q: 'What happens after the trial?', a: 'You continue only if you want to. No contracts, cancel anytime. The setup fee applies only if you decide to keep your agent.' },
        { q: 'How fast can it go live?', a: 'Most agents go live 3 to 5 business days after you send us your business information.' }
      ],
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
      trialUnit: function (d) { return d.trialDays + ' days free'; },
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
    var brand = $('brand-name');
    if (brand) brand.textContent = demo.businessName;
    setText('ended-title', t.endedTitle);
    setText('ended-body', t.endedBody);
    var btn = $('ended-btn');
    if (btn) { btn.textContent = t.endedBtn; btn.setAttribute('href', waUrl(number, t.waTech(demo))); }
    show('view-ended');
    trackEvent('demo_view', { slug: demo.slug, state: 'ended' });
  }

  function buildList(el, items) {
    if (!el) return;
    el.innerHTML = '';
    items.forEach(function (txt) {
      var li = document.createElement('li');
      li.textContent = txt;
      el.appendChild(li);
    });
  }

  function fillTrustLine(id, items) {
    var el = $(id);
    if (!el) return;
    el.innerHTML = '';
    items.forEach(function (txt) {
      var s = document.createElement('span');
      s.textContent = txt;
      el.appendChild(s);
    });
  }

  function wireTrialCta(id, demo, t, number, placement, label) {
    var el = $(id);
    if (!el) return;
    el.textContent = label || t.ctaTrial;
    el.setAttribute('href', waUrl(number, t.waTrial(demo)));
    el.addEventListener('click', function () {
      trackEvent('demo_trial_click', { slug: demo.slug, placement: placement });
    });
  }

  function renderActive(demo, t) {
    var number = elyonWhatsApp(demo);

    // <head>
    document.title = 'Demo IA para ' + demo.businessName + ' | Elyon';
    document.documentElement.lang = demo.language || 'es';

    // header: branded for the business
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
    wireTrialCta('cta-hero', demo, t, number, 'hero', t.heroCta);
    fillTrustLine('trust-hero', t.trust);

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
    // suggested questions: per-business override in the config beats generic
    buildList($('qs-list'), demo.questions || t.questions);
    setText('demo-notice', t.notice);
    setText('loading-text', t.loading);

    // how it works
    setText('hw-eyebrow', t.hwEyebrow);
    setText('hw-h', t.hwH);
    var hg = $('how-grid');
    if (hg) {
      hg.innerHTML = '';
      t.howSteps.forEach(function (s) {
        var div = document.createElement('div');
        div.className = 'how-step';
        var h = document.createElement('h3');
        h.textContent = s.t;
        var p = document.createElement('p');
        p.textContent = typeof s.p === 'function' ? s.p(demo) : s.p;
        div.appendChild(h);
        div.appendChild(p);
        hg.appendChild(div);
      });
    }

    // benefits
    setText('bf-eyebrow', t.bfEyebrow);
    setText('bf-h', t.bfH);
    setText('bf-lede', t.bfLede);
    var bg = $('benefits-grid');
    if (bg) {
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

    // FAQ
    setText('fq-eyebrow', t.fqEyebrow);
    setText('fq-h', t.fqH);
    var fl = $('faq-list');
    if (fl) {
      fl.innerHTML = '';
      t.faq.forEach(function (f) {
        var d = document.createElement('details');
        var s = document.createElement('summary');
        s.textContent = f.q;
        var p = document.createElement('p');
        p.textContent = f.a;
        d.appendChild(s);
        d.appendChild(p);
        d.addEventListener('toggle', function () {
          if (d.open) trackEvent('demo_faq_open', { slug: demo.slug, q: f.q });
        });
        fl.appendChild(d);
      });
    }

    // conversion
    setText('cv-h', t.convertH);
    setText('cv-p', t.convertP(demo));
    fillTrustLine('trust-convert', t.trust);
    wireTrialCta('cta-trial', demo, t, number, 'bottom');
    var tech = $('cta-tech');
    if (tech) {
      tech.textContent = t.ctaTech;
      tech.setAttribute('href', waUrl(number, t.waTech(demo)));
      tech.addEventListener('click', function () {
        trackEvent('demo_tech_click', { slug: demo.slug });
      });
    }

    // mobile sticky CTA
    wireTrialCta('cta-sticky', demo, t, number, 'sticky');
    show('sticky-cta');

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

    if (!demo || demo.status !== 'active') {
      renderNotFound(COPY.es); // not-found copy stays Spanish (site default)
      return;
    }
    if (elyonDemoExpired(demo)) {
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
