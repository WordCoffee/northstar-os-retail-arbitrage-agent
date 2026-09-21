/* ==========================================================================
   NORTHSTAR OS — BRAIN (dual-engine model switch)   Phase H / H3
   The per-request provider (Local | Cloud) + tier (T1/T2/T3) selector.
   Reads the unified catalog from /api/v1/models (never invents model ids),
   persists the choice locally, and exposes NS.brain.buildRequest() so every
   service can attach {provider, tier} to its calls.

   Offline-safe: if the catalog cannot be fetched, the control still renders
   the persisted choice and honestly shows "offline". Zero live calls here.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS = window.NS || {};
  var KEY = 't2.brain.v1';
  var catalog = null;
  var state = { provider: 'local', tier: 'T2' };

  function $id(id) { return document.getElementById(id); }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var s = JSON.parse(raw);
        if (s && s.provider) state.provider = s.provider;
        if (s && s.tier) state.tier = s.tier;
      }
    } catch (e) { /* noop */ }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* noop */ }
  }

  function defaultsFor(provider) {
    if (!catalog) return {};
    var box = provider === 'cloud' ? catalog.cloud : catalog.local;
    return (box && box.defaults) || {};
  }

  function renderState() {
    var el = $id('brain-state');
    if (!el) return;
    var model = '—';
    if (catalog) {
      model = defaultsFor(state.provider)[state.tier] || 'n/a';
      if (state.provider === 'cloud' && catalog.cloud && catalog.cloud.live_armed === false) {
        model = 'not armed';
      }
    } else {
      model = 'offline';
    }
    el.textContent = state.provider + ' · ' + state.tier + ' · ' + model;
  }

  function populate(c) {
    var ps = $id('brain-provider');
    var ts = $id('brain-tier');
    if (ps && c.providers) {
      ps.innerHTML = c.providers.map(function (p) {
        return '<option value="' + p + '">' + (p === 'cloud' ? 'Cloud' : 'Local') + '</option>';
      }).join('');
      ps.value = state.provider;
    }
    if (ts && c.tiers) {
      var textTiers = c.tiers.filter(function (t) { return t.charAt(0) === 'T'; });
      ts.innerHTML = textTiers.map(function (t) {
        return '<option value="' + t + '">' + t + (t === 'T1' ? ' Fast' : t === 'T2' ? ' Core' : ' Seam') + '</option>';
      }).join('');
      ts.value = state.tier;
    }
  }

  function init() {
    load();
    var ps = $id('brain-provider');
    var ts = $id('brain-tier');
    if (ps) {
      ps.value = state.provider;
      if (!ps._brainBound) {
        ps._brainBound = true;
        ps.addEventListener('change', function () { NS.brain.set(ps.value, null); });
      }
    }
    if (ts) {
      ts.value = state.tier;
      if (!ts._brainBound) {
        ts._brainBound = true;
        ts.addEventListener('change', function () { NS.brain.set(null, ts.value); });
      }
    }
    renderState();
    if (typeof fetch === 'function') {
      try {
        fetch('/api/v1/models').then(function (r) { return r.json(); }).then(function (b) {
          var c = b && b.data;
          if (!c) return;
          catalog = c;
          populate(c);
          renderState();
        }).catch(function () { renderState(); });
      } catch (e) { renderState(); }
    }
  }

  NS.brain = {
    init: init,
    state: function () { return { provider: state.provider, tier: state.tier }; },
    catalog: function () { return catalog; },
    set: function (provider, tier) {
      if (provider) state.provider = provider;
      if (tier) state.tier = tier;
      save();
      renderState();
      return NS.brain.state();
    },
    buildRequest: function () { return { provider: state.provider, tier: state.tier }; },
    renderState: renderState
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
