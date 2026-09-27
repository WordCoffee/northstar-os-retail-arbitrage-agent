/* ==========================================================================
   NORTHSTAR OS — COMMAND DECK + PALETTE   Phase H / H9 (UI polish)
   Two operator-facing surfaces on the Hub:
     1. Alpha Command Deck — engines (local/cloud), gate posture, tier caps,
        and the launch checks, assembled from live shell state (no network).
     2. Command palette (Ctrl/Cmd+K) — keyboard jump to any service.

   Zero network: it reads NS.brain.catalog() (already fetched by brain.js),
   NS.gates, and the demo subscriber. Nothing here invents data.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS = window.NS || {};

  function $id(id) { return document.getElementById(id); }

  var SERVICES = [
    { route: 'hub', label: 'Operations Hub', hint: 'portfolio overview' },
    { route: 'theledger', label: 'The Ledger', hint: 'profitability (coming soon)' },
    { route: 'sourcescout', label: 'Prospector', hint: 'sourcing · product finder' },
    { route: 'goldengoose', label: 'Golden Goose', hint: 'breakdown scan' },
    { route: 'listingforge', label: 'OfferChisel', hint: 'listing optimization' },
    { route: 'adpilot', label: 'The Auctioneer', hint: 'amazon ads' },
    { route: 'socialpulse', label: 'The Town Crier', hint: 'social media' },
    { route: 'thewatch', label: 'The Watch', hint: 'listing guardian (coming soon)' },
    { route: 'rankledger', label: 'RankLedger', hint: 'rank tracking (coming soon)' },
    { route: 'rivalboard', label: 'The Rival Board', hint: 'competitor monitor (coming soon)' },
    { route: 'autothink', label: 'AutothinK', hint: 'AI workspace' },
    { route: 'account', label: 'Account', hint: 'plans · entitlements' },
  ];

  var DISPLAY_NAMES = {
    sourcescout: 'Prospector', goldengoose: 'Golden Goose', listingforge: 'OfferChisel',
    adpilot: 'The Auctioneer', socialpulse: 'The Town Crier', thewatch: 'The Watch',
    rankledger: 'RankLedger', rivalboard: 'The Rival Board', theledger: 'The Ledger',
    autothink: 'AutothinK', commandcenter: 'Command Center',
  };

  function engineCards() {
    var cat = (NS.brain && NS.brain.catalog && NS.brain.catalog()) || null;
    var state = (NS.brain && NS.brain.state && NS.brain.state()) || { provider: 'local', tier: 'T2' };
    var cards = [];

    var localModel = cat ? ((cat.local.defaults || {})[state.tier] || '—') : 'offline';
    cards.push({
      key: 'local', tone: 'steel',
      label: 'Local engine',
      value: 'qwen (Ollama)',
      sub: localModel + ' · free · private',
    });

    var armed = !!(cat && cat.cloud && cat.cloud.live_armed);
    var keyPresent = !!(cat && cat.cloud && cat.cloud.key_present);
    var cloudModel = cat ? ((cat.cloud.defaults || {})[state.tier] || 'n/a') : 'offline';
    cards.push({
      key: 'cloud', tone: armed ? 'gold' : 'crimson',
      label: 'Cloud engine',
      value: armed ? 'ARMED' : (keyPresent ? 'key present · disarmed' : 'no key'),
      sub: (armed ? cloudModel : 'stays off until CLOUD_MODEL_LIVE=1') + ' · DeepSeek lane',
    });
    return cards;
  }

  function gateCard() {
    var names = Object.keys(NS.gates || {});
    var off = names.filter(function (n) { return NS.gateState(n).off; }).length;
    return { key: 'gates', tone: off === names.length ? 'green' : 'gold',
             label: 'Live gates', value: off + ' / ' + names.length + ' closed',
             sub: 'a plan entitles — it never flips a gate' };
  }

  function planCard() {
    var plan = (NS.activePlan && NS.activePlan()) || null;
    var caps = plan && plan.caps ? plan.caps : null;
    var capText = caps ? (caps.gg_scan + ' scans · ' + caps.listing + ' listings · ' + caps.post + ' posts')
                       : 'caps load from the plan catalog';
    return { key: 'plan', tone: 'gold', label: 'Current plan',
             value: plan ? plan.name : '—', sub: capText };
  }

  function launchCard() {
    var steps = [
      'Bring up: backend + Ollama + tunnel',
      'Arm cloud: CLOUD_MODEL_LIVE=1 (when testing cloud)',
      'Walk every service on Local, then Cloud',
      'Word Coffee: dry-run plan → approve cuts → measure',
    ];
    return { key: 'launch', tone: 'steel', label: 'Launch checks', value: steps.length + ' steps',
             sub: 'see PRIVATE_ALPHA_DEPLOY.md', steps: steps };
  }

  function renderDeck() {
    var grid = $id('deck-grid');
    if (!grid) return;
    var cards = engineCards().concat([gateCard(), planCard(), launchCard()]);
    grid.innerHTML = cards.map(function (c) {
      var steps = c.steps ? '<ul class="deck-steps">' + c.steps.map(function (s) {
        return '<li>' + NS.escapeHtml(s) + '</li>';
      }).join('') + '</ul>' : '';
      return '<div class="deck-card deck-' + c.tone + '" data-deck="' + NS.escapeHtml(c.key) + '">' +
        '<span class="deck-label">' + NS.escapeHtml(c.label) + '</span>' +
        '<span class="deck-value">' + NS.escapeHtml(String(c.value)) + '</span>' +
        '<span class="deck-sub">' + NS.escapeHtml(c.sub) + '</span>' + steps + '</div>';
    }).join('');

    var map = $id('deck-map');
    if (map) {
      map.innerHTML = '<span class="deck-map-label">Suite map</span>' +
        Object.keys(DISPLAY_NAMES).map(function (k) {
          return '<span class="deck-chip">' + NS.escapeHtml(DISPLAY_NAMES[k]) + '</span>';
        }).join('');
    }
  }

  /* ---------------- command palette ---------------- */

  var paletteOpen = false;

  function paletteMatches(q) {
    q = (q || '').toLowerCase().trim();
    if (!q) return SERVICES;
    return SERVICES.filter(function (s) {
      return s.label.toLowerCase().indexOf(q) !== -1 ||
             s.route.indexOf(q) !== -1 ||
             s.hint.toLowerCase().indexOf(q) !== -1;
    });
  }

  function renderPalette(q) {
    var list = $id('palette-list');
    if (!list) return;
    var matches = paletteMatches(q);
    list.innerHTML = matches.length ? matches.map(function (s, i) {
      return '<button type="button" class="palette-item' + (i === 0 ? ' active' : '') +
        '" data-palette-route="' + NS.escapeHtml(s.route) + '">' +
        '<span class="palette-name">' + NS.escapeHtml(s.label) + '</span>' +
        '<span class="palette-hint">' + NS.escapeHtml(s.hint) + '</span></button>';
    }).join('') : '<div class="palette-empty">No match.</div>';
    return matches;
  }

  function openPalette() {
    var ov = $id('palette');
    if (!ov) return;
    ov.hidden = false;
    paletteOpen = true;
    var input = $id('palette-input');
    if (input) { input.value = ''; if (input.focus) input.focus(); }
    renderPalette('');
  }

  function closePalette() {
    var ov = $id('palette');
    if (!ov) return;
    ov.hidden = true;
    paletteOpen = false;
  }

  function choose(route) {
    closePalette();
    if (route && NS.go) NS.go(route);
  }

  function bindPalette() {
    var ov = $id('palette');
    var input = $id('palette-input');
    var list = $id('palette-list');
    if (input && !input._deckBound) {
      input._deckBound = true;
      input.addEventListener('input', function () { renderPalette(input.value); });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          var first = paletteMatches(input.value)[0];
          if (first) choose(first.route);
        } else if (e.key === 'Escape') {
          closePalette();
        }
      });
    }
    if (list && !list._deckBound) {
      list._deckBound = true;
      list.addEventListener('click', function (e) {
        var btn = e.target && e.target.closest ? e.target.closest('[data-palette-route]') : null;
        if (btn) choose(btn.getAttribute('data-palette-route'));
      });
    }
    if (ov && !ov._deckBound) {
      ov._deckBound = true;
      ov.addEventListener('click', function (e) {
        if (e.target === ov) closePalette();
      });
    }
    if (document.addEventListener && !NS._deckKeyBound) {
      NS._deckKeyBound = true;
      document.addEventListener('keydown', function (e) {
        var k = e.key || '';
        if ((e.ctrlKey || e.metaKey) && (k === 'k' || k === 'K')) {
          e.preventDefault();
          if (paletteOpen) closePalette(); else openPalette();
        } else if (k === 'Escape' && paletteOpen) {
          closePalette();
        }
      });
    }
  }

  function init() {
    renderDeck();
    bindPalette();
  }

  NS.deck = {
    init: init,
    renderDeck: renderDeck,
    openPalette: openPalette,
    closePalette: closePalette,
    isPaletteOpen: function () { return paletteOpen; },
    services: function () { return SERVICES.slice(); },
    paletteMatches: paletteMatches,
    displayNames: function () { return Object.assign({}, DISPLAY_NAMES); },
  };
})();
