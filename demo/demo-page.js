/* ==========================================================================
   ELYON · DEMO PAGE CONTROLLER
   --------------------------------------------------------------------------
   Reads the slug from the URL, looks up its entry in demo-config.js, and
   renders the demo. Content order optimized for the LATAM market: pain-first
   headline, trial CTA in the first viewport, short checkmark benefits,
   3-step trial explainer (last step highlighted), FAQ, closing CTA. CTAs
   repeat through the page (hero / benefits / bottom / sticky) — "perdidos
   en el texto pero siempre presentes".
   Persona: Sofía (receptionistName per demo). generic:true entries speak to
   "tu negocio"; business entries name the business.
   Depends on: demo-config.js, widget-loader.js.

   NOTE ON CLAIMS: every factual claim mirrors what tryelyon.com publishes
   (150 conversaciones + 30 min voz, 3-5 días hábiles de configuración, sin
   tarjeta, cancela cuando quieras). Do not add claims the site doesn't make.
   ========================================================================== */
(function () {
  'use strict';

  function trackEvent(ev, props) {
    try {
      if (window.gtag) window.gtag('event', ev, props || {});
      if (window.fbq) window.fbq('trackCustom', ev, props || {});
    } catch (err) { /* analytics must never break the page */ }
  }

  /* ---- copy, per language. Functions receive the demo entry `d`, which
     carries d.rName (resolved receptionist name) and d.generic. ---- */
  var COPY = {
    es: {
      badge: 'Demo en vivo',
      headlineParts: function () {
        return ['Nunca vuelvas a perder un cliente ', 'por no contestar el teléfono', ''];
      },
      ledeParts: function (d) {
        return d.generic
          ? ['', d.rName, ', tu recepcionista con IA, atiende llamadas y WhatsApp 24/7: responde dudas, agenda citas y da seguimiento por ti.']
          : ['', d.rName, ', la recepcionista con IA de ' + d.businessName + ', atiende llamadas y WhatsApp 24/7: responde dudas, agenda citas y da seguimiento por ti.'];
      },
      heroCta: function (d) { return 'Activa tu prueba gratuita de ' + d.trialDays + ' días'; },
      trust: ['Sin tarjeta', 'Sin compromiso', 'Configuración incluida'],
      personaRole: 'Recepcionista con IA',
      personaStatus: 'Disponible 24/7',
      steps: function (d) {
        return [
          'Pulsa el botón para llamar.',
          'Permite el acceso al micrófono.',
          'Pide informes o una cita, como si fueras un cliente real de ' + (d.generic ? 'tu negocio' : d.businessName) + '.'
        ];
      },
      qsLabel: 'Preguntas de prueba sugeridas',
      questions: [
        'Quiero agendar una cita.',
        'Necesito información sobre un servicio.',
        '¿Pueden contactarme por WhatsApp?'
      ],
      notice: 'Esta es una demostración. Los servicios, horarios, respuestas, herramientas y acciones se configuran completamente a la medida de tu negocio antes de la activación.',
      loading: function (d) { return 'Iniciando a ' + d.rName + '…'; },
      bfEyebrow: 'Beneficios',
      bfH: function (d) { return 'Todo lo que ' + d.rName + ' hace por tu negocio'; },
      checklist: [
        'Atiende llamadas 24/7, también fines de semana',
        'Agenda citas automáticamente',
        'Responde WhatsApp al instante',
        'Nunca olvida dar seguimiento',
        'Se adapta a tus servicios y a tu tono',
        'Más clientes atendidos sin contratar más personal'
      ],
      bfClose: 'Más citas, mejor servicio — más ventas.',
      benefitsCta: function (d) { return 'Quiero probar gratis ' + d.trialDays + ' días'; },
      hwEyebrow: 'Cómo funciona',
      hwH: function (d) { return '¿Cómo funciona la prueba de ' + d.trialDays + ' días?'; },
      howSteps: function (d) {
        return [
          { t: 'Activas tu prueba', p: 'Nos escribes por WhatsApp y configuramos a ' + d.rName + ' con tus servicios, horarios y tono. Queda lista en 3 a 5 días hábiles.' },
          { t: 'La pones a prueba', p: 'Atiende a tus clientes reales durante ' + d.trialDays + ' días completos.' },
          { t: 'Mides los resultados', p: 'Si no ves valor ni más citas agendadas, no pagas nada.', hl: true }
        ];
      },
      fqEyebrow: 'Preguntas frecuentes',
      fqH: 'Lo que normalmente nos preguntan',
      faq: function (d) {
        return [
          { q: '¿' + d.rName + ' suena robótica?', a: 'No. Se configura con los servicios, precios y tono de voz de tu negocio, y pasa la conversación a una persona de tu equipo cuando el caso lo necesita.' },
          { q: '¿La prueba gratuita es realmente gratis?', a: 'Sí, sin tarjeta. Incluye hasta 150 conversaciones de IA y 30 minutos de voz durante la prueba. Si superas el uso incluido, el agente se pausa y tú decides si continuar.' },
          { q: '¿Qué pasa cuando termina la prueba?', a: 'Continúas solo si quieres. Sin contratos y puedes cancelar cuando quieras. El costo de configuración aplica únicamente si decides quedarte con tu agente.' },
          { q: '¿En cuánto tiempo queda lista?', a: 'La mayoría de los agentes quedan activos entre 3 y 5 días hábiles después de que nos envías la información de tu negocio.' }
        ];
      },
      wErrTitle: 'No se pudo cargar la demo',
      wErrBody: function (d) { return d.rName + ' no cargó en este dispositivo o red. Escríbenos por WhatsApp y te la mostramos al instante.'; },
      wErrBtn: 'Escríbenos por WhatsApp',
      convertH: '¿Listo para dejar de perder clientes?',
      convertP: function (d) {
        return 'Activa hoy tu prueba gratuita de ' + d.trialDays + ' días. Adaptamos a ' + d.rName + ' a los servicios, horarios y forma de trabajar de tu negocio.';
      },
      ctaTrial: 'Empieza hoy tu prueba gratuita',
      ctaSticky: function (d) { return 'Activa tu prueba gratis · ' + d.trialDays + ' días'; },
      ctaTech: 'Tengo una pregunta técnica',
      waTrial: function (d) {
        return d.generic
          ? 'Hola, probé la demo de ' + d.rName + ', la recepcionista con IA, y quiero activar la prueba gratuita de ' + d.trialDays + ' días para mi negocio.'
          : 'Hola, probé la demo de ' + d.businessName + ' y quiero activar la prueba gratuita de ' + d.trialDays + ' días.';
      },
      waTech: function (d) {
        return d.generic
          ? 'Hola, probé la demo de ' + d.rName + ', la recepcionista con IA, y tengo una pregunta técnica sobre el funcionamiento o las integraciones.'
          : 'Hola, probé la demo de ' + d.businessName + ' y tengo una pregunta técnica sobre el funcionamiento o las integraciones.';
      },
      waInfo: function (d) {
        return d && !d.generic
          ? 'Hola, estoy viendo la demo de ' + d.businessName + ' y quiero más información.'
          : 'Hola, estoy viendo la demo de Sofía, la recepcionista con IA, y quiero más información.';
      },
      metaCity: 'Ciudad',
      metaIndustry: 'Industria',
      metaTrial: 'Prueba',
      trialUnit: function (d) { return d.trialDays + ' días gratis'; },
      title: function (d) {
        return d.generic
          ? 'Conoce a ' + d.rName + ' — Recepcionista con IA | Elyon'
          : 'Demo IA para ' + d.businessName + ' | Elyon';
      },
      brandTop: function (d) { return d.generic ? d.rName : d.businessName; },
      brandSub: function (d) {
        return d.generic
          ? 'Recepcionista con IA · Elyon'
          : [d.industry, d.city].filter(Boolean).join(' · ');
      },
      endedTitle: 'Esta demostración ha finalizado',
      endedBody: 'La demo ya no está activa. Con gusto reactivamos una nueva para tu negocio.',
      endedBtn: 'Escríbenos por WhatsApp',
      nfTitle: 'Demostración no encontrada',
      nfBody: 'Este enlace de demo no es válido o ya no está activo. Verifica la dirección o contáctanos.',
      nfBtn: 'Ir a tryelyon.com'
    },
    en: {
      badge: 'Live demo',
      headlineParts: function () {
        return ['Never lose another customer ', 'because no one answered the phone', ''];
      },
      ledeParts: function (d) {
        return d.generic
          ? ['', d.rName, ', your AI receptionist, handles calls and WhatsApp 24/7: answers questions, books appointments and follows up for you.']
          : ['', d.rName, ', the AI receptionist for ' + d.businessName + ', handles calls and WhatsApp 24/7: answers questions, books appointments and follows up for you.'];
      },
      heroCta: function (d) { return 'Activate your free ' + d.trialDays + '-day trial'; },
      trust: ['No card required', 'No commitment', 'Setup included'],
      personaRole: 'AI Receptionist',
      personaStatus: 'Available 24/7',
      steps: function (d) {
        return [
          'Press the button to call.',
          'Allow microphone access.',
          'Ask for info or an appointment, like a real customer of ' + (d.generic ? 'your business' : d.businessName) + '.'
        ];
      },
      qsLabel: 'Suggested test questions',
      questions: [
        'I would like to book an appointment.',
        'I need information about a service.',
        'Can you contact me on WhatsApp?'
      ],
      notice: 'This is a demo. Services, hours, responses, tools and actions are fully configured for your business before activation.',
      loading: function (d) { return 'Starting ' + d.rName + '…'; },
      bfEyebrow: 'Benefits',
      bfH: function (d) { return 'Everything ' + d.rName + ' does for your business'; },
      checklist: [
        'Answers calls 24/7, weekends included',
        'Books appointments automatically',
        'Replies on WhatsApp instantly',
        'Never forgets to follow up',
        'Adapts to your services and your tone',
        'More customers served without hiring more staff'
      ],
      bfClose: 'More appointments, better service — more sales.',
      benefitsCta: function (d) { return 'Try it free for ' + d.trialDays + ' days'; },
      hwEyebrow: 'How it works',
      hwH: function (d) { return 'How does the ' + d.trialDays + '-day trial work?'; },
      howSteps: function (d) {
        return [
          { t: 'Activate your trial', p: 'Message us on WhatsApp and we configure ' + d.rName + ' with your services, hours and tone. Live in 3 to 5 business days.' },
          { t: 'Put it to the test', p: 'It serves your real customers for ' + d.trialDays + ' full days.' },
          { t: 'Measure the results', p: 'If you see no value and no extra appointments, you pay nothing.', hl: true }
        ];
      },
      fqEyebrow: 'FAQ',
      fqH: 'What people usually ask us',
      faq: function (d) {
        return [
          { q: 'Does ' + d.rName + ' sound robotic?', a: 'No. It is configured with your services, prices and tone of voice, and hands the conversation to a person on your team whenever a case needs one.' },
          { q: 'Is the free trial really free?', a: 'Yes, no card required. It includes up to 150 AI conversations and 30 voice minutes during the trial. If you pass the included usage, the agent pauses and you decide whether to continue.' },
          { q: 'What happens after the trial?', a: 'You continue only if you want to. No contracts, cancel anytime. The setup fee applies only if you decide to keep your agent.' },
          { q: 'How fast can it go live?', a: 'Most agents go live 3 to 5 business days after you send us your business information.' }
        ];
      },
      wErrTitle: 'The demo could not load',
      wErrBody: function (d) { return d.rName + ' did not load on this device or network. Message us on WhatsApp and we will show it to you right away.'; },
      wErrBtn: 'Message us on WhatsApp',
      convertH: 'Ready to stop losing customers?',
      convertP: function (d) {
        return 'Activate your free ' + d.trialDays + '-day trial today. We tailor ' + d.rName + ' to your services, hours and the way your business works.';
      },
      ctaTrial: 'Start your free trial today',
      ctaSticky: function (d) { return 'Free ' + d.trialDays + '-day trial'; },
      ctaTech: 'I have a technical question',
      waTrial: function (d) {
        return d.generic
          ? 'Hi, I tried the demo of ' + d.rName + ', the AI receptionist, and I want to activate the ' + d.trialDays + '-day free trial for my business.'
          : 'Hi, I tried the ' + d.businessName + ' demo and I want to activate the ' + d.trialDays + '-day free trial.';
      },
      waTech: function (d) {
        return d.generic
          ? 'Hi, I tried the demo of ' + d.rName + ', the AI receptionist, and I have a technical question about how it works or the integrations.'
          : 'Hi, I tried the ' + d.businessName + ' demo and I have a technical question about how it works or the integrations.';
      },
      waInfo: function (d) {
        return d && !d.generic
          ? 'Hi, I am looking at the ' + d.businessName + ' demo and would like more information.'
          : 'Hi, I am looking at the Sofía AI receptionist demo and would like more information.';
      },
      metaCity: 'City',
      metaIndustry: 'Industry',
      metaTrial: 'Trial',
      trialUnit: function (d) { return d.trialDays + ' days free'; },
      title: function (d) {
        return d.generic
          ? 'Meet ' + d.rName + ' — AI Receptionist | Elyon'
          : 'AI Demo for ' + d.businessName + ' | Elyon';
      },
      brandTop: function (d) { return d.generic ? d.rName : d.businessName; },
      brandSub: function (d) {
        return d.generic
          ? 'AI Receptionist · Elyon'
          : [d.industry, d.city].filter(Boolean).join(' · ');
      },
      endedTitle: 'This demo has ended',
      endedBody: 'This demo is no longer active. We are happy to spin up a fresh one for your business.',
      endedBtn: 'Message us on WhatsApp',
      nfTitle: 'Demo not found',
      nfBody: 'This demo link is invalid or no longer active. Please check the address or contact us.',
      nfBtn: 'Go to tryelyon.com'
    }
  };

  /* Elyon contact shown in header + footer (display form of ELYON_WA). */
  var WA_DISPLAY = '+52 55 9435 6033';

  /* ---- helpers ---- */
  function $(id) { return document.getElementById(id); }
  function show(id) { var el = $(id); if (el) el.classList.remove('hidden'); }
  function setText(id, txt) { var el = $(id); if (el) el.textContent = txt; }

  function slugFromLocation() {
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

  /* Build "pre [accent] post" text into an element. */
  function setParts(id, parts, accentTag) {
    var el = $(id);
    if (!el) return;
    el.textContent = '';
    el.appendChild(document.createTextNode(parts[0]));
    if (parts[1]) {
      var s = document.createElement(accentTag || 'span');
      s.className = 'accent';
      s.textContent = parts[1];
      el.appendChild(s);
    }
    el.appendChild(document.createTextNode(parts[2]));
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
    document.title = 'Demo · ' + (demo.generic ? demo.rName : demo.businessName) + ' | Elyon';
    var brand = $('brand-name');
    if (brand) brand.textContent = t.brandTop(demo);
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
    el.textContent = label;
    el.setAttribute('href', waUrl(number, t.waTrial(demo)));
    el.addEventListener('click', function () {
      trackEvent('demo_trial_click', { slug: demo.slug, placement: placement });
    });
  }

  /* Header + footer WhatsApp contact (all states). */
  function wireContact(demo, t) {
    var number = demo ? elyonWhatsApp(demo) : (typeof ELYON_WA_DEFAULT !== 'undefined' ? ELYON_WA_DEFAULT : '');
    if (!number) return;
    var msg = t.waInfo(demo);
    [['wa-header', 'header'], ['foot-wa', 'footer']].forEach(function (pair) {
      var el = $(pair[0]);
      if (!el) return;
      el.setAttribute('href', waUrl(number, msg));
      el.addEventListener('click', function () {
        trackEvent('demo_wa_contact', { slug: demo ? demo.slug : '(none)', placement: pair[1] });
      });
    });
    setText('wa-header', WA_DISPLAY);
    setText('foot-wa', 'WhatsApp ' + WA_DISPLAY);
  }

  /* Scroll-driven UI (reveals + sticky CTA), built as progressive
     enhancement: content is visible by default; JS hides ONLY below-fold
     sections (.pre) and reveals them on scroll, with a safety timeout that
     force-reveals everything. No IntersectionObserver / rAF dependency —
     both can stall in throttled rendering contexts. */
  function setupScrollUI() {
    var reveals = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
    var bar = $('sticky-cta');
    var anchor = $('widget-anchor');
    var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (bar) bar.classList.remove('hidden');

    function vh() { return window.innerHeight || document.documentElement.clientHeight; }

    // Skip pre-hiding entirely when the viewport measurement is degenerate
    // (prerender/background contexts can report ~0 height).
    if (!reduced && vh() < 200) reduced = true;
    if (!reduced) {
      reveals = reveals.filter(function (el) {
        if (el.getBoundingClientRect().top >= vh() * 0.96) {
          el.classList.add('pre');
          return true;
        }
        return false; // already visible: leave it alone
      });
      // Safety net: whatever hasn't revealed after 4s becomes visible.
      setTimeout(function () {
        reveals.forEach(function (el) { el.classList.remove('pre'); el.classList.add('in'); });
        reveals = [];
      }, 4000);
    } else {
      reveals = [];
    }

    var ticking = false;
    function update() {
      ticking = false;
      reveals = reveals.filter(function (el) {
        if (el.getBoundingClientRect().top < vh() * 0.92) {
          el.classList.remove('pre');
          el.classList.add('in');
          return false;
        }
        return true;
      });
      if (bar && anchor) {
        bar.classList.toggle('on', anchor.getBoundingClientRect().bottom < 0);
      }
    }
    function onScroll() {
      if (!ticking) { ticking = true; setTimeout(update, 60); }
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    update();
  }

  function renderActive(demo, t) {
    var number = elyonWhatsApp(demo);

    // <head>
    document.title = t.title(demo);
    document.documentElement.lang = demo.language || 'es';

    // header
    var brand = $('brand-name');
    if (brand) {
      brand.textContent = '';
      brand.appendChild(document.createTextNode(t.brandTop(demo)));
      var sub = t.brandSub(demo);
      if (sub) {
        var sm = document.createElement('small');
        sm.textContent = sub;
        brand.appendChild(sm);
      }
    }

    // hero: pain-first headline, then Sofía as the answer, CTA immediately
    setText('badge-text', t.badge);
    setParts('headline', t.headlineParts(demo));
    setParts('lede', t.ledeParts(demo), 'b');
    wireTrialCta('cta-hero', demo, t, number, 'hero', t.heroCta(demo));
    fillTrustLine('trust-hero', t.trust);

    // meta pills (after the CTA; generic demos have no city)
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

    // widget card persona identity
    setText('rcp-name', demo.rName);
    setText('rcp-role', t.personaRole);
    setText('status-text', t.personaStatus);

    buildList($('steps'), t.steps(demo));
    setText('qs-label', t.qsLabel);
    buildList($('qs-list'), demo.questions || t.questions);
    setText('demo-notice', t.notice);
    setText('loading-text', t.loading(demo));

    // benefits: short checkmark lines + closing statement + mid CTA
    setText('bf-eyebrow', t.bfEyebrow);
    setText('bf-h', t.bfH(demo));
    buildList($('benefits-list'), t.checklist);
    setText('bf-close', t.bfClose);
    wireTrialCta('cta-benefits', demo, t, number, 'benefits', t.benefitsCta(demo));

    // how the trial works (3 steps, last one highlighted)
    setText('hw-eyebrow', t.hwEyebrow);
    setText('hw-h', t.hwH(demo));
    var hg = $('how-grid');
    if (hg) {
      hg.innerHTML = '';
      t.howSteps(demo).forEach(function (s) {
        var div = document.createElement('div');
        div.className = 'how-step' + (s.hl ? ' hl' : '');
        var h = document.createElement('h3');
        h.textContent = s.t;
        var p = document.createElement('p');
        p.textContent = s.p;
        div.appendChild(h);
        div.appendChild(p);
        hg.appendChild(div);
      });
    }

    // FAQ
    setText('fq-eyebrow', t.fqEyebrow);
    setText('fq-h', t.fqH);
    var fl = $('faq-list');
    if (fl) {
      fl.innerHTML = '';
      t.faq(demo).forEach(function (f) {
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

    // closing conversion band
    setText('cv-h', t.convertH);
    setText('cv-p', t.convertP(demo));
    fillTrustLine('trust-convert', t.trust);
    wireTrialCta('cta-trial', demo, t, number, 'bottom', t.ctaTrial);
    var tech = $('cta-tech');
    if (tech) {
      tech.textContent = t.ctaTech;
      tech.setAttribute('href', waUrl(number, t.waTech(demo)));
      tech.addEventListener('click', function () {
        trackEvent('demo_tech_click', { slug: demo.slug });
      });
    }

    // sticky CTA (revealed on scroll past the widget)
    wireTrialCta('cta-sticky', demo, t, number, 'sticky', t.ctaSticky(demo));

    show('view-active');
    setupScrollUI(); // after show(): measurements need the section visible
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
      var p = document.createElement('p'); p.textContent = t.wErrBody(demo);
      var a = document.createElement('a'); a.className = 'btn fill'; a.style.marginTop = '1rem';
      a.textContent = t.wErrBtn; a.setAttribute('href', waUrl(number, t.waTech(demo)));
      a.setAttribute('target', '_blank'); a.setAttribute('rel', 'noopener');
      box.appendChild(h); box.appendChild(p); box.appendChild(a);
      zone.appendChild(box);
      trackEvent('demo_widget_error', { slug: demo.slug });
    }

    if (!elyonWidgetConfigured(demo)) {
      if (loading) loading.classList.add('hidden');
      zone.setAttribute('data-widget-state', 'error');
      var box = document.createElement('div');
      box.className = 'w-msg';
      box.innerHTML = '<div class="t">Widget sin configurar</div>' +
        '<p>Pega el código del widget de voz en <code>demo-config.js</code> para activar esta demo.</p>';
      zone.appendChild(box);
      return;
    }

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

    if (demo) {
      demo.rName = demo.receptionistName ||
        (typeof ELYON_RECEPTIONIST !== 'undefined' ? ELYON_RECEPTIONIST : 'Sofía');
    }

    wireContact(demo, t); // header + footer WhatsApp, in every state

    if (!demo || demo.status !== 'active') {
      renderNotFound(COPY.es);
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
