/* ==========================================================================
   ELYON · SAFE VOICE-WIDGET LOADER
   --------------------------------------------------------------------------
   A dedicated, provider-agnostic loader for an embedded Voice AI widget.
   It is given the raw embed snippet (verbatim from the provider) and a mount
   element, and it:

     • Recreates <script> nodes so they actually execute (scripts injected
       via innerHTML never run) and places them INSIDE the mount, so a widget
       configured as Embedded / Inline anchors to the card, not the page body.
     • Loads each external script only ONCE per page, even across client-side
       navigations or repeat mounts (deduped by URL globally).
     • Preserves every attribute on the original embed (data-*, async, etc.).
     • Shows a loading state, then a helpful error + WhatsApp fallback if the
       script fails to load or nothing initializes within a timeout.
     • Never starts audio or requests the microphone on its own — that only
       happens after the visitor presses the provider's Call button.

   No private keys are handled here; the loader only moves the exact markup
   the provider gave you. Public API: ElyonWidget.mount(options).
   ========================================================================== */
(function (global) {
  'use strict';

  // Track external scripts already requested this page load: src -> Promise.
  var loadedScripts = {};

  function loadExternalScript(srcEl, target) {
    var src = srcEl.src;
    if (loadedScripts[src]) return loadedScripts[src];

    loadedScripts[src] = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      // Copy every attribute from the original embed script, verbatim.
      for (var i = 0; i < srcEl.attributes.length; i++) {
        var a = srcEl.attributes[i];
        s.setAttribute(a.name, a.value);
      }
      s.setAttribute('data-elyon-widget', '1');
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error('Failed to load ' + src)); };
      (target || document.head).appendChild(s);
    });
    return loadedScripts[src];
  }

  function runInlineScript(scriptEl, target) {
    var s = document.createElement('script');
    for (var i = 0; i < scriptEl.attributes.length; i++) {
      var a = scriptEl.attributes[i];
      s.setAttribute(a.name, a.value);
    }
    s.text = scriptEl.textContent;
    (target || document.body).appendChild(s);
  }

  /**
   * mount(options)
   *   mount     : element that hosts the widget markup + scripts
   *   embedHtml : raw provider embed snippet (string)
   *   onError() : called when the widget cannot load
   *   onReady() : called when the widget has rendered
   *   timeoutMs : how long to wait for the widget to render (default 15s)
   */
  function mount(options) {
    var host = options.mount;
    var embedHtml = options.embedHtml || '';
    var onError = typeof options.onError === 'function' ? options.onError : function () {};
    var onReady = typeof options.onReady === 'function' ? options.onReady : function () {};
    var timeoutMs = options.timeoutMs || 15000;

    if (!host) return;

    // Slot the provider markup + scripts render into. Watching it tells us
    // whether the widget actually initialized inline.
    var slot = document.createElement('div');
    slot.className = 'ew-slot';
    host.appendChild(slot);

    var settled = false;
    function fail(reason) {
      if (settled) return;
      settled = true;
      onError(reason);
    }
    function succeed() {
      if (settled) return;
      settled = true;
      host.setAttribute('data-widget-state', 'ready');
      onReady();
    }
    function rendered() {
      // The provider injected real DOM into the slot (iframe, button, custom
      // element, etc.) beyond the markup we placed there ourselves.
      var el = slot.querySelector('iframe, button, canvas, chat-widget, [class*="widget"], [id*="widget"], [class*="call"], [class*="voice"]');
      if (!el) return false;
      // It must actually occupy space INSIDE the card — an embedded/inline
      // widget. A floating widget mounts a zero-size host here and pins its
      // UI to the viewport corner instead; that does not count as inline and
      // should surface the fallback so the widget gets switched to Inline.
      return el.offsetWidth > 20 && el.offsetHeight > 20;
    }

    // Split the embed into scripts vs. everything else, preserving order.
    var tpl = document.createElement('template');
    tpl.innerHTML = embedHtml;
    var frag = tpl.content;
    var scripts = [];
    Array.prototype.forEach.call(frag.querySelectorAll('script'), function (sc) {
      scripts.push(sc);
      sc.parentNode.removeChild(sc);
    });

    // Place the non-script markup (the widget container / custom element).
    slot.appendChild(frag);

    // Flip to "ready" the moment the widget paints into the slot.
    var observer = null;
    if (global.MutationObserver) {
      observer = new MutationObserver(function () {
        if (!settled && rendered()) { observer.disconnect(); succeed(); }
      });
      observer.observe(slot, { childList: true, subtree: true });
    }

    // Load external scripts (once each), then run inline scripts in order.
    // Scripts go INTO the slot so an inline widget anchors to the card.
    var chain = Promise.resolve();
    var hadExternal = false;
    scripts.forEach(function (sc) {
      if (sc.src) {
        hadExternal = true;
        chain = chain.then(function () { return loadExternalScript(sc, slot); });
      } else {
        chain = chain.then(function () { runInlineScript(sc, slot); });
      }
    });

    chain.then(function () {
      // Scripts are in and none errored. Give a fast follow-up check in case
      // the widget rendered synchronously before the observer attached.
      if (!settled && rendered()) { if (observer) observer.disconnect(); succeed(); }
    }).catch(function () {
      if (observer) observer.disconnect();
      fail('script_error'); // a required script failed to load
    });

    // Timeout guard: scripts loaded but nothing rendered in the card. This is
    // usually a network problem or a widget still set to floating placement.
    global.setTimeout(function () {
      if (settled) return;
      if (rendered()) { if (observer) observer.disconnect(); succeed(); return; }
      if (observer) observer.disconnect();
      fail(hadExternal ? 'timeout' : 'no_scripts');
    }, timeoutMs);
  }

  global.ElyonWidget = { mount: mount };
})(typeof window !== 'undefined' ? window : this);
