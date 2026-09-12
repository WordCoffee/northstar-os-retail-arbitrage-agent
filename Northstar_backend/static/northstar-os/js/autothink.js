/* ==========================================================================
   NORTHSTAR OS — AUTOTHINK SURFACE MODULE
   Surface integration for the premium AutothinK workspace: service
   quick-invocation buttons (prefill the composer so the Master Brain
   router sees "Ask <Service>" verb + domain), a local-brain readiness lamp
   (pure config state — never probed at build time, zero network), and a
   demo copy affordance. The chat workspace itself lives at
   autothink/ui/index.html (hosted via iframe / new-tab link).
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var SERVICE_NAMES = {
    sourcescout: 'SourceScout',
    listingforge: 'ListingForge',
    adpilot: 'AdPilot',
    socialpulse: 'SocialPulse',
  };
  var EXAMPLE_ASK = {
    sourcescout: 'find sourcing candidates',
    listingforge: 'rewrite this listing in Word Coffee voice',
    adpilot: 'optimize campaign bids by band',
    socialpulse: 'draft a social post',
  };

  function prefill(service) {
    var name = SERVICE_NAMES[service];
    if (!name) return null;
    var text = 'Ask ' + name + ': ' + (EXAMPLE_ASK[service] || 'assist in the domain') + ' (demo prefill)';
    var composer = document.getElementById('at-composer');
    if (composer) composer.value = text;
    return text;
  }

  function renderLamp() {
    var dot = document.getElementById('at-lamp-dot');
    var val = document.getElementById('at-lamp-value');
    var state = (NS.config && NS.config.autothinkBackend) || 'offline';
    if (dot) { dot.classList.remove('offline', 'detected'); dot.classList.add(state); }
    if (val) { val.textContent = state; val.className = 'lamp-value ' + state; }
    return state;
  }

  function copyNote(text) {
    var note = document.getElementById('at-copy-note');
    if (note) note.textContent = text;
  }

  // Lazy workspace mount: the shell boots without an iframe fetch. The
  // workspace mounts (once) on the first visit to the AutothinK view.
  function mountWorkspace() {
    var frame = document.getElementById('at-workspace');
    if (!frame || frame.getAttribute('src')) return;
    var lazySrc = frame.getAttribute('data-src');
    if (lazySrc) frame.setAttribute('src', lazySrc);
  }

  function bindControls() {
    Object.keys(SERVICE_NAMES).forEach(function (svc) {
      var btn = document.getElementById('at-quick-' + svc);
      if (!btn || btn._atBound) return;
      btn._atBound = true;
      btn.addEventListener('click', function () { prefill(svc); });
    });
    var copyBtn = document.getElementById('at-copy');
    if (copyBtn && !copyBtn._atBound) {
      copyBtn._atBound = true;
      copyBtn.addEventListener('click', function () {
        var composer = document.getElementById('at-composer');
        var text = composer && composer.value ? composer.value : '';
        try {
          if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            navigator.clipboard.writeText(text);
          }
        } catch (e) { /* demo only — never surfaces */ }
        copyNote(text ? 'Copied (demo)' : 'Nothing to copy yet.');
      });
    }
  }

  function onMount() {
    mountWorkspace();
    renderLamp();
    bindControls();
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'autothink') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.autothink = { prefill: prefill, renderLamp: renderLamp, serviceNames: SERVICE_NAMES, mountWorkspace: mountWorkspace };
})();