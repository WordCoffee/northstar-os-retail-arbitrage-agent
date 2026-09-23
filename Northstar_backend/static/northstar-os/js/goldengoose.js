/* ==========================================================================
   NORTHSTAR OS — GOLDEN GOOSE SERVICE VIEW (standalone)
   Breakdown scan: scan config, tiered results (A clears every gate, D fails),
   evidence manifest (typed, honest), dry-run affordance. Product thumbnails
   load from real image URLs with a branded local fallback tile.
   Zero live pull; a real scan needs the Costco live-pull gate approved.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function getEl(id) { return document.getElementById(id); }
  function money(v) { return v == null ? '<span class="unk">—</span>' : '$' + NS.fmt(v); }

  function healthBadge(h) {
    return '<span class="health-badge health-badge--' + NS.escapeHtml(h) + '" title="' + NS.escapeHtml(h) + '"></span>';
  }
  function logisticsTag(l) {
    return '<span class="logistics-tag logistics-tag--' + NS.escapeHtml(l) + '">' + NS.escapeHtml(l) + '</span>';
  }
  function qualifiedBadge(q) {
    return q ? '<span class="badge badge-green">Yes</span>' : '<span class="badge badge-muted">No</span>';
  }

  function renderKpis(kpis) {
    var strip = getEl('gg-kpis');
    if (!strip) return;
    strip.innerHTML = (kpis || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
    }).join('');
  }

  function renderRows(rows) {
    var grid = getEl('gg-grid');
    if (!grid) return;
    var header = '<div class="data-grid-header">' +
      '<div></div><div>Product</div><div>Tier</div><div>Health</div><div class="num">Est. Monthly</div>' +
      '<div class="num">Net Profit</div><div>Logistics</div><div>Qualified</div></div>';
    var body = (rows || []).map(function (r) {
      var tierCls = 'tier-pill tier-pill--' + (r.tier || 'C');
      var netCls = r.net != null && r.net < 0 ? 'text-red' : 'text-gold';
      return '<div class="data-grid-row" data-gg="' + NS.escapeHtml(r.id) + '" data-tier="' + NS.escapeHtml(r.tier) + '">' +
        '<div>' + NS.img(r.image, r.name, 'img-tile gg-tile') + '</div>' +
        '<div><strong>' + NS.escapeHtml(r.name) + '</strong><span class="dim" style="display:block;font-size:10px">' + NS.escapeHtml(r.asin) + '</span></div>' +
        '<div><span class="' + tierCls + '">' + NS.escapeHtml(r.tier) + '</span></div>' +
        '<div>' + healthBadge(r.health) + '</div>' +
        '<div class="num">' + NS.fmt(r.estMonthly) + '</div>' +
        '<div class="num ' + netCls + '">' + money(r.net) + '</div>' +
        '<div>' + logisticsTag(r.logistics) + '</div>' +
        '<div>' + qualifiedBadge(r.qualified) + '</div>' +
        '</div>';
    }).join('');
    grid.innerHTML = header + body;
  }

  function renderManifest(m) {
    var host = getEl('gg-manifest');
    if (!host) return;
    var statusPill = m.status === 'success' ? '<span class="pill green">success</span>'
      : m.status === 'partial' ? '<span class="pill gold">partial</span>'
      : '<span class="pill crimson">' + NS.escapeHtml(m.status || 'unknown') + '</span>';
    host.innerHTML =
      '<div class="editor-meta">' + statusPill +
      '<span class="hint">resolved ' + NS.fmt(m.resolved) + ' / requested ' + NS.fmt(m.requested) +
      ' · last run ' + NS.escapeHtml(m.lastRun || '—') + '</span></div>' +
      '<div class="notice" style="margin-top:10px">' + NS.escapeHtml(m.note || '') + '</div>';
  }

  function bindControls() {
    var run = getEl('gg-dryrun');
    if (run && !run._ggBound) {
      run._ggBound = true;
      run.addEventListener('click', function () {
        if (NS.spin) NS.spin(run, 900, 'Scanning…');
        var stamp = new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
        var meta = getEl('gg-last-run');
        if (meta) meta.textContent = 'last dry-run: ' + stamp;
        if (NS.toast) NS.toast('Dry-run scan complete (demo) — ' + 12 + ' candidates screened, no live pull.', 'success');
      });
    }
    // scan config selects (apply on next scan)
    ['gg-profit', 'gg-sellers', 'gg-category'].forEach(function (id) {
      var el = getEl(id);
      if (el && !el._ggSelBound) {
        el._ggSelBound = true;
        el.addEventListener('change', function () {
          if (NS.toast) NS.toast('Scan threshold updated: ' + id.replace('gg-', '') + ' = ' + el.value + ' (applies on next scan).', 'note');
        });
      }
    });
    // the Prospector "Golden Goose" tab now opens this standalone screen
    var tab = document.querySelector('[data-src-tab="gg"]');
    if (tab && !tab._ggNavBound) {
      tab._ggNavBound = true;
      tab.addEventListener('click', function () { NS.go('goldengoose'); });
    }
  }

  function onMount() {
    var data = NS.DEMO ? NS.DEMO() : null;
    var gg = data && data.goldengoose;
    if (!gg) return;
    renderKpis(gg.kpis);
    renderRows(gg.rows);
    renderManifest(gg.manifest);
    var gate = getEl('gate-goldengoose_live');
    if (gate) NS.renderGateBanner(gate, 'sourcescout_live_pull');
    bindControls();
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'goldengoose') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.gg = { onMount: onMount, renderRows: renderRows };
})();