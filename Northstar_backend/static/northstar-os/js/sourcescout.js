/* ==========================================================================
   NORTHSTAR OS — SOURCESCOUT SERVICE VIEW
   Retail Arbitrage Agent app (shell layer). The full tested workbench lives
   at ../index.html (Northstar_backend/static/index.html) and is reachable
   via "Open full workbench". This shell view renders a labeled demo table,
   rich sourcing facets (ROI / units / net margin / buy-box / invoice /
   risk-clean / consumables-first), worksheet export in the honest shape
   (missing -> None), a typed live-pull failure-taxonomy banner fed by an
   evidence manifest (never fabricates success), and a hub global-KPI
   pass-through. All zero-network.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var state = { rows: [], filtered: [] };

  function allRows(demo) {
    return (demo && demo.sourcescout && demo.sourcescout.rows) || [];
  }
  function getEl(id) { return document.getElementById(id); }

  /* net margin % = (Amazon Price - COGS) / Amazon Price, 1 decimal */
  function marginPct(r) {
    if (!r || !r.amazonPrice || !r.cost) return null;
    return Math.round(((r.amazonPrice - r.cost) / r.amazonPrice) * 1000) / 10;
  }

  /* pure facet predicate: every enabled facet must pass; null values fail */
  NS.ss = NS.ss || {};
  NS.ss.matchesFilters = function (r) {
    var roiMin = parseFloat(getEl('facet-roi') ? getEl('facet-roi').value : 0) || 0;
    var unitsMin = parseInt(getEl('facet-units') ? getEl('facet-units').value : 0, 10) || 0;
    var marginMin = parseFloat(getEl('facet-margin') ? getEl('facet-margin').value : 0) || 0;
    var wantBuyBox = !!(getEl('facet-buybox') && getEl('facet-buybox').checked);
    var wantInvoice = !!(getEl('facet-invoice') && getEl('facet-invoice').checked);
    var wantRiskClean = !!(getEl('facet-risk') && getEl('facet-risk').checked);
    var q = NS.globalQuery;

    if (roiMin > 0 && (r.roi == null || r.roi < roiMin)) return false;
    if (unitsMin > 0 && (r.estMonthly == null || r.estMonthly < unitsMin)) return false;
    if (marginMin > 0) { var m = marginPct(r); if (m == null || m < marginMin) return false; }
    if (wantBuyBox && !r.buyBox) return false;
    if (wantInvoice && r.invoice !== 'clean') return false;
    if (wantRiskClean && !r.riskClean) return false;
    if (q) {
      var hay = ((r.name || '') + ' ' + (r.asin || '')).toLowerCase();
      if (hay.indexOf(q) === -1) return false;
    }
    return true;
  };

  function renderKpis(data) {
    var strip = getEl('ss-kpis');
    if (!strip) return;
    strip.innerHTML = (data.kpis || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
    }).join('');
  }

  /* hub global-KPI pass-through (spec 04 extension 4) */
  function renderPortfolio(demo) {
    var host = getEl('ss-portfolio');
    if (!host) return;
    host.innerHTML = ((demo && demo.hub && demo.hub.kpis) || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
    }).join('');
  }

  function renderLivePull(demo) {
    var el = getEl('ss-live-banner');
    if (el) NS.renderGateBanner(el, 'sourcescout_live_pull');
    var meta = getEl('ss-live-meta');
    if (meta && demo && demo.sourcescout) {
      var lp = demo.sourcescout.livePull || {};
      meta.textContent = lp.provider || '';
    }
  }

  /* typed failure taxonomy from an evidence manifest — a partial run is
   * reported as partial with per-status counts. Nothing is ever marked
   * complete/success against a manifest that does not say so. */
  function renderLiveStatus(demo) {
    var host = getEl('ss-live-status');
    if (!host) return;
    var lp = (demo && demo.sourcescout && demo.sourcescout.livePull) || {};
    var failures = lp.failures || [];
    var statusPill = lp.status === 'success' ? '<span class="pill green">success</span>'
      : lp.status === 'partial' ? '<span class="pill gold">partial</span>'
      : '<span class="pill ' + (lp.status === 'failed' ? 'crimson' : 'dim') + '">' + NS.escapeHtml(lp.status || 'unknown') + '</span>';
    var rows = failures.map(function (f) {
      return '<div class="compliance-row" data-live-failure="' + NS.escapeHtml(f.status) + '">' +
        '<span class="pill crimson">' + NS.escapeHtml(f.status) + '</span> × ' + NS.fmt(f.count) +
        (f.detail ? ' <span class="dim">— ' + NS.escapeHtml(f.detail) + '</span>' : '') +
        '</div>';
    }).join('');
    host.innerHTML =
      '<div class="panel" style="margin-top:14px">' +
      '<div class="panel-head"><h3>Live-Pull Status</h3><span class="hint">typed failure taxonomy · evidence manifest (fixture)</span></div>' +
      '<div class="editor-meta">' + statusPill +
      '<span class="hint">resolved ' + NS.fmt(lp.resolved == null ? '—' : lp.resolved) + ' / requested ' + NS.fmt(lp.requested == null ? '—' : lp.requested) +
      ' · last run ' + NS.escapeHtml(lp.lastRun || '—') + '</span></div>' +
      (rows || '<div class="service-empty">No failures recorded in this manifest.</div>') +
      '<div class="notice">Nothing is marked complete on this manifest: every unresolved item stays typed and unmarked until fresh evidence arrives. ' +
      NS.escapeHtml((lp.note || '')) + '</div>' +
      '</div>';
  }

  function renderTable(rows) {
    var tbody = getEl('ss-table-body');
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="service-empty">No rows match the current facets.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function (r) {
      var tier = tierPill(r.tier);
      return '<tr class="row-card" data-asin="' + NS.escapeHtml(r.asin) + '" data-name="' + NS.escapeHtml(r.name) + '" data-roi="' + (r.roi == null ? '' : r.roi) + '" data-margin="' + (marginPct(r) == null ? '' : marginPct(r)) + '">' +
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
    NS.pinTableRows(getEl('ss-table'));
  }

  function tierPill(tier) {
    if (!tier) return '<span class="pill dim">unscored</span>';
    var kind = tier === 'Pass' ? 'green' : tier === 'Hold' ? 'gold' : tier === 'Reject' ? 'crimson' : 'steel';
    return '<span class="pill ' + kind + '">' + NS.escapeHtml(tier) + '</span>';
  }
  function money(v) { return v == null ? '<span class="unk">—</span>' : '$' + NS.fmt(v); }
  function pct(v) { return v == null ? '<span class="unk">—</span>' : NS.fmt(v) + '%'; }

  function applyFilters() {
    state.filtered = state.rows.filter(NS.ss.matchesFilters);
    // "Prefer consumables" is a sort preference — consumables first, all rows kept
    if (getEl('facet-consumable') && getEl('facet-consumable').checked) {
      state.filtered.sort(function (a, b) { return (b.consumable ? 1 : 0) - (a.consumable ? 1 : 0); });
    }
    renderTable(state.filtered);
    var count = getEl('ss-result-count');
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

  function onMount() {
    var data = NS.DEMO ? NS.DEMO() : null;
    if (!data || !data.sourcescout) return;
    renderKpis(data.sourcescout);
    renderPortfolio(data);
    renderLivePull(data);
    renderLiveStatus(data);
    state.rows = allRows(data);
    applyFilters();
    NS.bindKnobs(getEl('view-sourcescout'));

    // facet listeners (guarded so remounts never stack duplicates)
    ['facet-roi', 'facet-units', 'facet-margin', 'facet-buybox', 'facet-invoice', 'facet-risk', 'facet-consumable'].forEach(function (id) {
      var el = getEl(id);
      if (el && !el._ssBound) {
        el._ssBound = true;
        el.addEventListener('change', applyFilters);
      }
    });
    var exp = getEl('ss-export');
    if (exp && !exp._ssBound) { exp._ssBound = true; exp.addEventListener('click', exportWorksheet); }
    var open = getEl('ss-open-workbench');
    if (open && !open._ssBound) { open._ssBound = true; open.addEventListener('click', function () { window.location.href = '../index.html'; }); }
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'sourcescout') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.ss = { applyFilters: applyFilters, exportWorksheet: exportWorksheet, matchesFilters: NS.ss.matchesFilters, marginPct: marginPct, state: state };
})();