/* ==========================================================================
   NORTHSTAR OS — SHELL ENGINE
   Shared: hash router, drawer navigation, bulletin board, paperclip
   assistant, global search, rotary knobs, ink-plot charts, gate banners,
   and demo-data loading.  Zero network calls by design.
   Exposed as window.NS for tests.
   ========================================================================== */
(function () {
  'use strict';

  // ---- tiny DOM helpers ----
  function $id(id) { return document.getElementById(id); }
  function $q(sel, root) { return (root || document).querySelector(sel); }
  function $qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  var NS = {};
  NS.DEMO = function () { return null; }; // replaced by demo-data loader

  // ---------------- AUTHORIZATION / GATE CONTRACT ----------------
  // Every gate is OFF by default. The UI only ever *marks* a control as
  // gated; nothing performs a live call.
  NS.gates = {
    sourcescout_live_pull:  { off: true, label: 'Costco live-pull (Bright Data / Firecrawl)' },
    sourcescout_enrich:     { off: true, label: 'Enrichment (Easyparser / RapidAPI / DataForSEO)' },
    listingforge_copy:      { off: true, label: 'Claude copy rewrite' },
    listingforge_media:     { off: true, label: 'Image / video generation API' },
    adpilot_bulk_exec:      { off: true, label: 'Amazon Bulk Operations upload' },
    adpilot_ads_read:       { off: true, label: 'Amazon Ads API read' },
    socialpulse_publish:    { off: true, label: 'Meta / TikTok / Instagram publish' },
    socialpulse_attrib:     { off: true, label: 'Amazon Attribution generation' },
  };
  NS.gateState = function (name) {
    var g = NS.gates[name];
    return { name: name, off: !!(g && g.off), label: g ? g.label : name };
  };
  NS.renderGateBanner = function (el, gateName) {
    if (!el) return;
    var s = NS.gateState(gateName);
    el.setAttribute('data-gate', gateName);
    el.className = 'gate-banner' + (s.off ? '' : ' blocked');
    el.innerHTML =
      '<svg class="shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' +
      '<span class="gate-text">' + s.label + '</span>' +
      '<span class="gate-state">' + (s.off ? 'Authorization required' : 'LIVE authorized') + '</span>';
  };

  // ---------------- ROUTER ----------------
  var ROUTES = ['hub', 'sourcescout', 'listingforge', 'adpilot', 'socialpulse', 'autothink'];
  NS.currentRoute = function () {
    var h = (location.hash || '').replace(/^#\/?/, '');
    return ROUTES.indexOf(h) !== -1 ? h : 'hub';
  };
  NS.go = function (route) {
    if (ROUTES.indexOf(route) === -1) route = 'hub';
    location.hash = '#/' + route; // hashchange listener updates the views
    NS.mount(route); // immediate (idempotent with hashchange)
  };
  NS.mount = function (route) {
    var r = route || NS.currentRoute();
    ROUTES.forEach(function (name) {
      var v = $id('view-' + name);
      if (v) {
        v.classList.toggle('active', name === r);
        v.setAttribute('aria-hidden', name === r ? 'false' : 'true');
      }
      var nav = $id('nav-' + name);
      if (nav) {
        nav.classList.toggle('active', name === r);
        nav.setAttribute('aria-current', name === r ? 'page' : 'false');
      }
    });
    if (NS.onMount) NS.onMount(r);
  };

  // ---------------- DRAWER ----------------
  NS.bindDrawer = function () {
    $qa('.nav-item[data-route]').forEach(function (item) {
      item.addEventListener('click', function () { NS.go(item.getAttribute('data-route')); });
    });
  };

  // ---------------- BULLETIN BOARD ----------------
  NS.board = [];
  NS.pin = function (text, kind) {
    kind = kind || 'note';
    var id = 'pin-' + Date.now() + '-' + NS.board.length;
    NS.board.push({ id: id, text: text, kind: kind });
    NS.renderBoard();
    return id;
  };
  NS.unpin = function (id) {
    NS.board = NS.board.filter(function (p) { return p.id !== id; });
    NS.renderBoard();
  };
  NS.renderBoard = function () {
    var list = $id('board-list');
    var empty = $id('board-empty');
    var count = $id('pin-count');
    if (count) count.textContent = NS.board.length + (NS.board.length === 1 ? ' pinned' : ' pinned');
    if (!list) return;
    var html = '';
    NS.board.forEach(function (p) {
      html +=
        '<div class="pin" data-pin-id="' + p.id + '">' +
        '<button class="pin-x" data-unpin="' + p.id + '" aria-label="unpin">&#10005;</button>' +
        '<span class="pin-text">' + escapeHtml(p.text) + '</span>' +
        '<span class="pin-meta">' + escapeHtml(p.kind) + '</span>' +
        '</div>';
    });
    list.innerHTML = html;
    if (empty) empty.style.display = NS.board.length ? 'none' : '';
    // delegate unpin
    $qa('[data-unpin]', list).forEach(function (b) {
      b.addEventListener('click', function () { NS.unpin(b.getAttribute('data-unpin')); });
    });
  };
  NS.pinTableRows = function (tableEl) {
    if (!tableEl) return;
    $qa('tbody tr.row-card .pin-btn', tableEl).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tr = btn.closest('tr');
        if (!tr) return;
        var asin = tr.getAttribute('data-asin') || tr.getAttribute('data-id') || 'row';
        var name = tr.getAttribute('data-name') || asin;
        btn.classList.toggle('pinned');
        tr.classList.toggle('pinned');
        if (btn.classList.contains('pinned')) NS.pin(name + ' (' + asin + ')', 'pinned');
      });
    });
  };

  // ---------------- PAPERCLIP ----------------
  NS.insights = [];
  NS.showInsight = function (kicker, body, persist) {
    var note = $id('pc-note');
    var k = $id('pc-kicker');
    var b = $id('pc-body');
    if (note && k && b) {
      k.textContent = kicker || 'Insight';
      b.textContent = body;
      note.classList.add('show');
    }
    if (persist) NS.insights.push({ kicker: kicker, body: body });
  };
  NS.dismissInsight = function () {
    var note = $id('pc-note');
    if (note) note.classList.remove('show');
  };
  NS.bindPaperclip = function () {
    var fig = $id('paperclip-figure');
    var close = $id('pc-close');
    if (fig) fig.addEventListener('click', function () {
      if (NS.insights.length) {
        var i = NS.insights[NS.insights.length - 1];
        NS.showInsight(i.kicker, i.body);
      }
    });
    if (close) close.addEventListener('click', NS.dismissInsight);
  };

  // ---------------- GLOBAL SEARCH ----------------
  NS.globalQuery = '';
  NS.bindSearch = function () {
    var input = $id('global-search');
    if (!input) return;
    input.addEventListener('input', function () {
      NS.globalQuery = input.value.trim().toLowerCase();
      if (NS.onSearch) NS.onSearch(NS.globalQuery);
    });
  };

  // ---------------- ROTARY KNOB ----------------
  NS.bindKnobs = function (root) {
    $qa('.knob[data-min][data-max]', root).forEach(function (knob) {
      var min = parseFloat(knob.getAttribute('data-min'));
      var max = parseFloat(knob.getAttribute('data-max'));
      var step = parseFloat(knob.getAttribute('data-step') || '1');
      var unit = knob.getAttribute('data-unit') || '';
      var cur = NS.knobValue(knob);
      knob.addEventListener('wheel', function (ev) {
        ev.preventDefault();
        var next = cur + (ev.deltaY < 0 ? step : -step);
        setupValue(knob, Math.min(max, Math.max(min, roundStep(next, step))), unit);
      });
      knob.addEventListener('click', function () {
        var next = cur + step;
        if (next > max) next = min;
        setupValue(knob, roundStep(next, step), unit);
      });
    });
  };
  function roundStep(v, step) { var d = String(step).indexOf('.') >= 0 ? String(step).split('.')[1].length : 0; var f = Math.pow(10, d); return Math.round(v * f) / f; }
  function setupValue(knob, val, unit) {
    knob.setAttribute('data-value', val + unit);
    var out = $q('.knob-value', knob.parentNode);
    if (out) out.textContent = val + unit;
    if (NS.onKnob) NS.onKnob(knob, val);
  }
  NS.knobValue = function (knob) {
    var raw = knob.getAttribute('data-value') || knob.getAttribute('data-min') || '0';
    return parseFloat(String(raw).replace(/[^0-9.+-]/g, '')) || 0;
  };

  // ---------------- INK-PLOT ----------------
  // el: container with .ip-bars; data: [{label, value, color?}]
  NS.renderInkPlot = function (el, title, data, maxValue) {
    if (!el) return;
    var max = maxValue || 1;
    data.forEach(function (d) { if (d.value > max) max = d.value; });
    var bars = data.map(function (d) {
      var h = max > 0 ? Math.max(3, Math.round((d.value / max) * 100)) : 3;
      return '<div class="ip-bar" data-label="' + escapeHtml(d.label) + '" data-value="' + escapeHtml(d.value) + '">' +
        '<div class="bar ' + (d.color || '') + '" style="height:' + h + 'px"></div>' +
        '<span class="v">' + fmt(d.value) + '</span>' +
        '<span class="lbl">' + escapeHtml(d.label) + '</span>' +
        '</div>';
    }).join('');
    var shell = $q('.ip-bars', el);
    if (!shell) {
      el.innerHTML = '<div class="ip-title">' + escapeHtml(title || '') + '</div><div class="ip-bars">' + bars + '</div>';
    } else {
      $q('.ip-title', el).textContent = title || '';
      shell.innerHTML = bars;
    }
  };

  // ---------------- HELPERS ----------------
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(n) {
    if (n == null) return '—';
    var num = parseFloat(n);
    if (isNaN(num)) return String(n);
    if (num === 0) return '0';
    if (num >= 1000) return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (Math.abs(num) < 0.01 && num !== 0) return num.toExponential(1);
    return String(Math.round(num * 100) / 100);
  }
  NS.escapeHtml = escapeHtml;
  NS.fmt = fmt;
  NS.displayUnknown = function (v) { return v == null || v === '' ? '—' : String(v); };

  // ---------------- BOOT ----------------
  NS.init = function () {
    NS.bindDrawer();
    NS.bindPaperclip();
    NS.bindSearch();
    $qa('.gate-banner[data-gate]').forEach(function (el) {
      NS.renderGateBanner(el, el.getAttribute('data-gate'));
    });
    window.addEventListener('hashchange', function () { NS.mount(); });
    NS.mount();
  };

  window.NS = NS;
})();