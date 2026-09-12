/* ==========================================================================
   NORTHSTAR OS — SOURCESCOUT SERVICE VIEW
   Retail Arbitrage Agent app (shell layer). The full tested workbench lives
   at ../index.html (Northstar_backend/static/index.html) and is reachable
   via "Open full workbench". This shell view renders a labeled demo table,
   sourcing facets, worksheet export, and the live-pull gate banner —
   all zero-network.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var state = { rows: [], filtered: [] };

  function allRows(demo) {
    return (demo && demo.sourcescout && demo.sourcescout.rows) || [];
  }

  function renderKpis(data) {
    var strip = document.getElementById('ss-kpis');
    if (!strip) return;
    strip.innerHTML = (data.kpis || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
    }).join('');
  }

  function renderTable(rows) {
    var tbody = document.getElementById('ss-table-body');
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="service-empty">No rows match the current facets.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function (r) {
      var tier = tierPill(r.tier);
      return '<tr class="row-card" data-asin="' + NS.escapeHtml(r.asin) + '" data-name="' + NS.escapeHtml(r.name) + '" data-roi="' + (r.roi == null ? '' : r.roi) + '" data-margin="' + (r.amazonPrice && r.cost ? Math.round(((r.amazonPrice - r.cost) / r.amazonPrice) * 1000) / 10 : '') + '">' +
        '<td><button class="pin-btn" data-pin-row aria-label="pin">&#9825;</button></td>' +
        '<td class="dim">' + NS.escapeHtml(r.asin) + '</td>' +
        '<td>' + NS.escapeHtml(r.name) + '</td>' +
        '<td class="num">' + money(r.cost) + '</td>' +
        '<td class="num">' + money(r.amazonPrice) + '</td>' +
        '<td class="num">' + money(r.net) + '</td>' +
        '<td class="num">' + pct(r.roi) + '</td>' +
        '<td>' + NS.escapeHtml(r.competition || '—') + '</td>' +
        '<td class="num">' + NS.displayUnknown(r.estMonthly) + '</td>' +
        '<td>' + tier + '</td>' +
        '</tr>';
    }).join('');
    NS.pinTableRows(document.getElementById('ss-table'));
  }

  function tierPill(tier) {
    if (!tier) return '<span class="pill dim">unscored</span>';
    var kind = tier === 'Pass' ? 'green' : tier === 'Hold' ? 'gold' : tier === 'Reject' ? 'crimson' : 'steel';
    return '<span class="pill ' + kind + '">' + NS.escapeHtml(tier) + '</span>';
  }
  function money(v) { return v == null ? '<span class="unk">—</span>' : '$' + NS.fmt(v); }
  function pct(v) { return v == null ? '<span class="unk">—</span>' : NS.fmt(v) + '%'; }

  function applyFilters() {
    var minROI = parseFloat(document.getElementById('facet-roi') ? document.getElementById('facet-roi').value : 0) || 0;
    var minUnits = parseInt(document.getElementById('facet-units') ? document.getElementById('facet-units').value : 0, 10) || 0;
    var q = NS.globalQuery;
    state.filtered = state.rows.filter(function (r) {
      if (minROI > 0 && (r.roi == null || r.roi < minROI)) return false;
      if (minUnits > 0 && (r.estMonthly == null || r.estMonthly < minUnits)) return false;
      if (q) {
        var hay = ((r.name || '') + ' ' + (r.asin || '')).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    renderTable(state.filtered);
    var count = document.getElementById('ss-result-count');
    if (count) count.textContent = state.filtered.length + ' of ' + state.rows.length + ' rows';
  }

  function exportWorksheet() {
    var rows = state.filtered;
    var header = ['ASIN', 'Name', 'Costco Cost', 'Amazon Price', 'Net Profit', 'ROI %', 'Competition', 'Est. Monthly', 'Tier'];
    var lines = [header.join(',')];
    rows.forEach(function (r) {
      lines.push([r.asin, '"' + String(r.name).replace(/"/g, '""') + '"', r.cost == null ? 'None' : r.cost, r.amazonPrice == null ? 'None' : r.amazonPrice, r.net == null ? 'None' : r.net, r.roi == null ? 'None' : r.roi, r.competition || 'None', r.estMonthly == null ? 'None' : r.estMonthly, r.tier || 'Unscored'].join(','));
    });
    var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    var a = document.createElement('a');
    a.setAttribute('href', URL.createObjectURL(blob));
    a.setAttribute('download', 'sourcescout-worksheet.csv');
    a.click();
  }

  function renderLivePull(demo) {
    var el = document.getElementById('ss-live-banner');
    if (!el) return;
    NS.renderGateBanner(el, 'sourcescout_live_pull');
    var meta = document.getElementById('ss-live-meta');
    if (meta && demo && demo.sourcescout) {
      var lp = demo.sourcescout.livePull || {};
      meta.textContent = lp.provider || '';
    }
  }

  function onMount() {
    var data = NS.DEMO ? NS.DEMO() : null;
    if (!data || !data.sourcescout) return;
    renderKpis(data.sourcescout);
    renderLivePull(data);
    state.rows = allRows(data);
    applyFilters();
    NS.bindKnobs(document.getElementById('view-sourcescout'));
    // facet listeners
    ['facet-roi', 'facet-units'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', applyFilters);
    });
    var exp = document.getElementById('ss-export');
    if (exp) exp.addEventListener('click', exportWorksheet);
    var open = document.getElementById('ss-open-workbench');
    if (open) open.addEventListener('click', function () { window.location.href = '../index.html'; });
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'sourcescout') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.ss = { applyFilters: applyFilters, exportWorksheet: exportWorksheet, state: state };
})();