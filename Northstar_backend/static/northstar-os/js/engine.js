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

  // Non-secret runtime configuration (never a credential value). The
  // AutothinK local-brain lamp reads this; defaulting to 'offline' is the
  // honest state until the operator flips it to 'detected' after launch.
  NS.config = { autothinkBackend: 'offline' };

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

  // ---------------- SUBSCRIBER PLAN HELPERS ----------------
  // Reads the demo subscriber fixture (labeled demo; zero network). A plan
  // ENTITLES a gate — it never opens one. Every gate stays `off: true` until
  // a fresh, named operator approval executes the live action.
  function demoSubscriber() {
    var d = (typeof NS.DEMO === 'function') ? NS.DEMO() : null;
    return (d && d.subscriber) ? d.subscriber : null;
  }
  NS.planEntitles = function (gateName) {
    var sub = demoSubscriber();
    if (!sub || !sub.plans) return [];
    var names = [];
    sub.plans.forEach(function (p) {
      if ((p.entitled_gates || []).indexOf(gateName) !== -1) names.push(p.name);
    });
    return names;
  };
  NS.activePlan = function () {
    var sub = demoSubscriber();
    if (!sub || !sub.subscription) return null;
    var pid = sub.subscription.plan;
    var plan = null;
    (sub.plans || []).forEach(function (p) { if (p.id === pid) plan = p; });
    return plan; // plan object or null — never fabricated
  };
  NS.renderSubscriberBadge = function () {
    var pill = $id('ribbon-plan');
    if (!pill) return;
    var plan = NS.activePlan();
    pill.textContent = (plan ? plan.name : '—') + ' (demo)';
  };

  // ---------------- ROUTER ----------------
  var ROUTES = ['hub', 'sourcescout', 'goldengoose', 'listingforge', 'adpilot', 'socialpulse', 'autothink', 'account', 'theledger', 'thewatch', 'rankledger', 'rivalboard'];
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
    NS.renderSubscriberBadge();
    if (NS.onMount) NS.onMount(r);
  };

  // ---------------- DRAWER ----------------
  NS.bindDrawer = function () {
    $qa('.nav-item[data-route]').forEach(function (item) {
      item.addEventListener('click', function () { NS.go(item.getAttribute('data-route')); });
    });
    // collapsible groups
    $qa('.drawer-group-header[data-collapse]').forEach(function (head) {
      head.addEventListener('click', function () {
        var group = head.parentNode;
        if (!group || group.className.indexOf('drawer-group') === -1) return;
        var collapsed = group.classList.toggle('collapsed');
        head.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      });
    });
  };

  // ---------------- THEME (light primary + dark toggle) ----------------
  NS.theme = function () {
    var de = document.documentElement;
    return de.getAttribute ? (de.getAttribute('data-theme') || 'light') : 'light';
  };
  NS.setTheme = function (t) {
    t = (t === 'dark') ? 'dark' : 'light';
    var de = document.documentElement;
    if (de.setAttribute) de.setAttribute('data-theme', t);
    try { localStorage.setItem('northstar_theme', t); } catch (e) {}
    var btn = $id('theme-toggle');
    if (btn) btn.setAttribute('data-theme', t);
    return t;
  };
  NS.toggleTheme = function () {
    return NS.setTheme(NS.theme() === 'dark' ? 'light' : 'dark');
  };
  NS.initTheme = function () {
    var saved = null;
    try { saved = localStorage.getItem('northstar_theme'); } catch (e) {}
    NS.setTheme(saved || 'light');
    var btn = $id('theme-toggle');
    if (btn) btn.addEventListener('click', NS.toggleTheme);
    var chip = $id('account-chip');
    if (chip) chip.addEventListener('click', function () { NS.go('account'); });
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

  // ---------------- TOASTS / INTERACTION STATES (I4) ----------------
  NS.toast = function (message, kind, ms) {
    var host = $id('toast-container');
    if (!host || !document.createElement) return;
    kind = kind || 'info';
    var t = document.createElement('div');
    t.className = 'toast toast-' + kind;
    t.setAttribute('role', 'status');
    t.textContent = message;
    host.appendChild(t);
    var wait = ms || 3600;
    setTimeout(function () {
      if (t.parentNode) t.parentNode.removeChild(t);
    }, wait);
  };
  NS.spin = function (btn, ms, label) {
    if (!btn) return;
    var orig = btn.textContent;
    var wasDisabled = btn.disabled;
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.textContent = (label || 'Working…');
    setTimeout(function () {
      btn.disabled = wasDisabled;
      btn.removeAttribute('aria-busy');
      btn.textContent = orig;
    }, ms || 800);
  };
  NS.bindToastButtons = function () {
    $qa('[data-toast]').forEach(function (btn) {
      if (btn._toastBound) return;
      btn._toastBound = true;
      btn.addEventListener('click', function () {
        var msg = btn.getAttribute('data-toast') || 'Done.';
        NS.toast(msg, btn.getAttribute('data-toast-kind') || 'info');
      });
    });
  };

  // ---------------- PRODUCT IMAGES (I3: real photos + branded fallback) ----------------
  // The suite is online-capable: thumbnails load from real image URLs (lazy)
  // and fall back to a deterministic branded SVG tile when the URL is missing
  // or fails (offline / broken CDN link).
  NS.fallbackDataURI = function (alt) {
    var s = String(alt == null ? 'Product' : alt);
    var h = 0, i;
    for (i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    var hue = 205 + (h % 55);                       /* steel-blue band */
    var init = (s.trim().charAt(0) || 'N').toUpperCase();
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">' +
      '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="hsl(' + hue + ',35%,88%)"/>' +
      '<stop offset="1" stop-color="hsl(' + hue + ',45%,74%)"/></linearGradient></defs>' +
      '<rect width="120" height="120" rx="10" fill="url(#g)"/>' +
      '<path d="M60 22l7 17 18 1-14 12 5 18-16-10-16 10 5-18-14-12 18-1z" fill="hsl(' + hue + ',55%,42%)" opacity=".9"/>' +
      '<text x="60" y="94" font-family="Inter,Segoe UI,sans-serif" font-size="34" font-weight="700" text-anchor="middle" fill="hsl(' + hue + ',45%,30%)">' + init + '</text></svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  };
  NS.fallbackImg = function (img) {
    if (!img) return;
    img.onerror = null;
    img.src = NS.fallbackDataURI(img.getAttribute('alt') || 'Product');
  };
  NS.img = function (src, alt, cls) {
    var a = alt == null ? 'Product' : String(alt);
    var escAlt = a.replace(/"/g, '&quot;');
    var s = src || NS.fallbackDataURI(a);
    return '<img class="' + (cls || 'img-tile') + '" src="' + NS.escapeHtml(s) + '" alt="' + escAlt +
      '" loading="eager" referrerpolicy="no-referrer" onerror="window.NS && NS.fallbackImg(this)">';
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
    NS.initTheme();
    NS.bindDrawer();
    NS.bindPaperclip();
    NS.bindSearch();
    NS.bindToastButtons();
    if (NS.bindVoice) NS.bindVoice(document);
    $qa('.gate-banner[data-gate]').forEach(function (el) {
      NS.renderGateBanner(el, el.getAttribute('data-gate'));
    });
    window.addEventListener('hashchange', function () { NS.mount(); });
    NS.mount();
  };

  window.NS = NS;
})();