/* ==========================================================================
   NORTHSTAR OS — ADPILOT SERVICE VIEW
   Amazon Ads Agent app: 4-tier campaigns, Search Term Harvester (movement
   sortable), Bid Optimizer (ACoS band rule engine → per-keyword bid delta),
   Placements, Guardrail Matrix, Bulk Ops CSV dock (parse → annotated rows).
   Zero network; Amazon Ads API read / bulk upload are gated and never fired.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var sortDir = 'asc'; // movement column sort direction
  var bulkRows = null; // active bulk rows (fixture default until CSV parse)

  /* ---------- ACoS band rule engine (pure) ----------
   * Mirrors the master-plan band table. Low data (<10 clicks) is reported
   * as hold, never disguised as an action.
   */
  function bandFor(acos, clicks) {
    if (acos == null || isNaN(acos)) return { band: 'no ACoS', action: '—', kind: 'dim', lowData: false };
    if ((clicks == null || clicks < 10)) return { band: 'low data', action: 'hold — under 10 clicks', kind: 'dim', lowData: true };
    if (acos > 45) return { band: '>45% and ≥10 clicks', action: '−10 to −30% bid', kind: 'crimson', lowData: false };
    if (acos > 30) return { band: '30–45%', action: '−5 to −10% bid', kind: 'gold', lowData: false };
    if (acos >= 15) return { band: '15–30%', action: '+5 to +15% bid', kind: 'steel', lowData: false };
    return { band: '<15%', action: '+15 to +30% bid', kind: 'gold', lowData: false };
  }

  /* ---------- movement rank for sorting ---------- */
  function movRank(m) {
    if (m === 'PROMOTED') return 0;
    if (m === 'DEMOTED') return 2;
    return 1;
  }
  function movementPill(m) {
    if (m === 'PROMOTED') return '<span class="pill green">PROMOTED</span>';
    if (m === 'DEMOTED') return '<span class="pill crimson">DEMOTED</span>';
    return '<span class="pill dim">NO_CHANGE</span>';
  }
  function bidDeltaCell(k) {
    var b = bandFor(k.acos, k.clicks);
    if (b.lowData) return '<td class="num"><span class="unk">low data</span></td>';
    if (k.acos == null) return '<td class="num"><span class="unk">—</span></td>';
    return '<td class="num"><span class="pill ' + b.kind + '" data-bid-delta="applied">' + NS.escapeHtml(b.action) + '</span></td>';
  }

  /* ---------- mini CSV parser (handles double-quoted commas) ---------- */
  function parseLine(line) {
    var out = [], cur = '', inQ = false, i, c;
    for (i = 0; i < line.length; i++) {
      c = line[i];
      if (inQ) {
        if (c === '"') {
          if (line[i + 1] === '"') { cur += '"'; i++; } else inQ = false;
        } else cur += c;
      } else if (c === '"') inQ = true;
      else if (c === ',') { out.push(cur); cur = ''; }
      else cur += c;
    }
    out.push(cur);
    return out;
  }
  /* Parse an Amazon-style bulk sheet (header + rows) into bulkRow objects.
   * Columns: sku, campaign, keyword or targeting, match type, bid,
   * decision, reason. Bids that are empty/blank become null (never zero). */
  function parseBulkCsv(text) {
    if (!text) return [];
    var lines = String(text).split(/\r?\n/).filter(function (l) { return l.trim() !== ''; });
    if (lines.length < 2) return [];
    var header = parseLine(lines[0]).map(function (h) { return h.trim().toLowerCase(); });
    function idx(aliases) {
      for (var a = 0; a < aliases.length; a++) {
        var found = header.indexOf(aliases[a]);
        if (found !== -1) return found;
      }
      return -1;
    }
    var iSku = idx(['sku']);
    var iCamp = idx(['campaign']);
    var iKw = idx(['keyword or targeting', 'keyword-or-targeting', 'keyword', 'kw or targeting']);
    var iMatch = idx(['match type', 'match']);
    var iBid = idx(['bid']);
    var iDec = idx(['decision']);
    var iReason = idx(['reason']);
    return lines.slice(1).map(function (line) {
      var v = parseLine(line);
      var bidRaw = v[iBid] != null ? String(v[iBid]).trim() : '';
      return {
        sku: iSku >= 0 ? String(v[iSku] || '').trim() : '',
        campaign: iCamp >= 0 ? String(v[iCamp] || '').trim() : '',
        kwOrTargeting: iKw >= 0 ? String(v[iKw] || '').trim() : '',
        matchType: iMatch >= 0 ? String(v[iMatch] || '').trim() : '',
        bid: bidRaw === '' ? null : parseFloat(bidRaw),
        decision: iDec >= 0 ? String(v[iDec] || '').trim() : '',
        reason: iReason >= 0 ? String(v[iReason] || '').trim() : '',
      };
    });
  }

  /* fixture bulk sheet — same rows as the demo fixture, quoted commas in
   * reasons exercise the parser */
  var FIXTURE_CSV = 'sku,campaign,keyword or targeting,match type,bid,decision,reason\n' +
    'WC-MOMS-V1,WCF-WinnersExact,affirmation cards for women,exact,1.05,increase-10pct,"ACoS 27%, orders>0"\n' +
    'WC-MOMS-V1,WCF-AlmostWinners,mom affirmation cards,phrase,0.42,decrease-8pct,ACoS 41%\n' +
    'WC-WOMEN-V2,WCF-BenchAuto,free printable affirmation cards,negative,,add-negative,"0 orders, repeat non-converter"';

  function renderKeywords(keywords) {
    var tbody = document.getElementById('ap-kw-body');
    if (!tbody) return;
    var sorted = keywords.slice().sort(function (a, b) {
      var d = sortDir === 'desc' ? -1 : 1;
      return (movRank(a.movement) - movRank(b.movement)) * d;
    });
    tbody.innerHTML = sorted.map(function (k) {
      var mov = movementPill(k.movement);
      var guard = k.auto ? '<span class="pill green">autonomous</span>' : '<span class="pill gold">needs approval</span>';
      return '<tr class="row-card" data-kw="' + NS.escapeHtml(k.kw) + '" data-tier="' + NS.escapeHtml(k.tier) + '" data-movement="' + NS.escapeHtml(k.movement) + '">' +
        '<td>' + NS.escapeHtml(k.kw) + '</td>' +
        '<td class="num">' + NS.fmt(k.impressions) + '</td>' +
        '<td class="num">' + NS.fmt(k.clicks) + '</td>' +
        '<td class="num">' + NS.fmt(k.orders) + '</td>' +
        '<td class="num">' + (k.acos == null ? '<span class="unk">—</span>' : NS.fmt(k.acos) + '%') + '</td>' +
        '<td>' + mov + '</td>' +
        '<td>' + guard + '</td>' +
        '<td class="dim">' + NS.escapeHtml(k.autoAction || '') + '</td>' +
        bidDeltaCell(k) +
        '</tr>';
    }).join('');
  }

  function renderBulkRows(rows) {
    var bulkBody = document.getElementById('ap-bulk-body');
    if (!bulkBody) return;
    bulkBody.innerHTML = rows.map(function (r) {
      var cls = r.decision === 'add-negative' ? 'crimson' : r.decision.indexOf('increase') !== -1 ? 'green' : 'gold';
      return '<tr data-bulk="' + NS.escapeHtml(r.sku) + '">' +
        '<td>' + NS.escapeHtml(r.sku) + '</td>' +
        '<td>' + NS.escapeHtml(r.campaign) + '</td>' +
        '<td>' + NS.escapeHtml(r.kwOrTargeting) + '</td>' +
        '<td class="dim">' + NS.escapeHtml(r.matchType || '—') + '</td>' +
        '<td class="num">' + (r.bid == null ? '<span class="unk">—</span>' : '$' + NS.fmt(r.bid)) + '</td>' +
        '<td><span class="pill ' + cls + '">' + NS.escapeHtml(r.decision) + '</span></td>' +
        '<td class="dim">' + NS.escapeHtml(r.reason) + '</td>' +
        '</tr>';
    }).join('');
    var count = document.getElementById('ap-bulk-count');
    if (count) count.textContent = rows.length + ' row' + (rows.length === 1 ? '' : 's') + ' parsed · decisions annotated (demo)';
  }

  function onMount() {
    var data = NS.DEMO();
    if (!data || !data.adpilot) return;
    var ad = data.adpilot;
    if (!bulkRows) bulkRows = ad.bulkRows;

    // KPI strip
    var kpiStrip = document.getElementById('ap-kpis');
    if (kpiStrip) {
      kpiStrip.innerHTML = (ad.kpis || []).map(function (k) {
        return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' + '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' + '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' + '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
      }).join('');
    }

    // tiers
    var tierBox = document.getElementById('ap-tiers');
    if (tierBox) {
      tierBox.innerHTML = (ad.tiers || []).map(function (t) {
        return '<div class="kpi-card" data-tier="' + t.tier + '"><div class="lbl">Tier ' + t.tier + ' · ' + NS.escapeHtml(t.name) + '</div>' +
          '<div class="val gold">$' + t.budget + '/day</div>' +
          '<div class="sub">' + NS.escapeHtml(t.purpose) + ' · ' + NS.escapeHtml(t.strategy) + '</div></div>';
      }).join('');
    }

    // keywords (harvester) table — sortable by movement
    renderKeywords(ad.keywords || []);
    var sortTh = document.getElementById('ap-sort-movement');
    if (sortTh && !sortTh._apSortBound) {
      sortTh._apSortBound = true;
      sortTh.addEventListener('click', function () {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        updateSortInd();
        renderKeywords(ad.keywords || []);
      });
    }
    updateSortInd();

    // ACoS bands + per-keyword band preview (Bid Optimizer)
    var bands = document.getElementById('ap-acos-bands');
    if (bands) {
      bands.innerHTML = (ad.acosBands || []).map(function (b) {
        return '<div class="compliance-row" data-band="' + NS.escapeHtml(b.band) + '"><span class="pill ' + b.kind + '">' + NS.escapeHtml(b.band) + '</span> → ' + NS.escapeHtml(b.action) + '</div>';
      }).join('');
    }
    var bandPrev = document.getElementById('ap-band-previews');
    if (bandPrev) {
      bandPrev.innerHTML = (ad.keywords || []).filter(function (k) { return k.acos != null; }).map(function (k) {
        var b = bandFor(k.acos, k.clicks);
        return '<div class="compliance-row" data-band-preview="' + NS.escapeHtml(k.kw) + '"><span class="pill ' + b.kind + '">' + NS.escapeHtml(b.band) + '</span> ' + NS.escapeHtml(k.kw) + ' → ' + NS.escapeHtml(b.action) + '</div>';
      }).join('');
    }

    // placement ink-plot
    NS.renderInkPlot(document.getElementById('ap-placement-plot'), 'Placement Share (demo)', ad.placements || []);

    // guardrails
    var guardrailBox = document.getElementById('ap-guardrails');
    if (guardrailBox) {
      guardrailBox.innerHTML = (ad.guardrails || []).map(function (g) {
        var cls = g.zone === 'autonomous' ? 'green' : 'gold';
        return '<div class="compliance-row" data-guard="' + NS.escapeHtml(g.action) + '"><span class="pill ' + cls + '">' + NS.escapeHtml(g.zone) + '</span> ' + NS.escapeHtml(g.action) + '</div>';
      }).join('');
    }

    // bulk ops: fixture table + CSV dock
    renderBulkRows(bulkRows);
    var csvSrc = document.getElementById('ap-csv-src');
    if (csvSrc) {
      csvSrc.value = FIXTURE_CSV;
      if (!csvSrc._apCsvBound) {
        csvSrc._apCsvBound = true;
        csvSrc.addEventListener('input', function () {
          var rows = parseBulkCsv(csvSrc.value);
          renderBulkRows(rows);
        });
      }
    }
    var parseBtn = document.getElementById('ap-parse-csv');
    if (parseBtn && !parseBtn._apParseBound) {
      parseBtn._apParseBound = true;
      parseBtn.addEventListener('click', function () {
        var rows = parseBulkCsv(csvSrc ? csvSrc.value : FIXTURE_CSV);
        bulkRows = rows;
        renderBulkRows(rows);
      });
    }

    // gate banners
    ['adpilot_ads_read', 'adpilot_bulk_exec'].forEach(function (g) {
      var el = document.getElementById('gate-' + g);
      if (el) NS.renderGateBanner(el, g);
    });
  }

  function updateSortInd() {
    var ind = document.getElementById('ap-sort-ind');
    if (ind) ind.textContent = sortDir === 'desc' ? '\u25bc' : '\u25b2';
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'adpilot') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.ap = { onMount: onMount, bandFor: bandFor, parseBulkCsv: parseBulkCsv, sortDir: function () { return sortDir; } };
})();