/* ==========================================================================
   NORTHSTAR OS — ADPILOT SERVICE VIEW
   Amazon Ads Agent app: 4-tier campaigns, Search Term Harvester, Bid
   Optimizer (ACoS bands), Placements, Bulk Ops CSV in/out (fixture).
   Zero network; Amazon Ads API read / bulk upload are gated and never fired.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function onMount() {
    var data = NS.DEMO();
    if (!data || !data.adpilot) return;
    var ad = data.adpilot;

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

    // keywords (harvester) table
    var tbody = document.getElementById('ap-kw-body');
    if (tbody) {
      tbody.innerHTML = (ad.keywords || []).map(function (k) {
        var mov = movementPill(k.movement);
        var guard = k.auto ? '<span class="pill green">autonomous</span>' : '<span class="pill gold">needs approval</span>';
        return '<tr class="row-card" data-kw="' + NS.escapeHtml(k.kw) + '" data-tier="' + NS.escapeHtml(k.tier) + '">' +
          '<td>' + NS.escapeHtml(k.kw) + '</td>' +
          '<td class="num">' + NS.fmt(k.impressions) + '</td>' +
          '<td class="num">' + NS.fmt(k.clicks) + '</td>' +
          '<td class="num">' + NS.fmt(k.orders) + '</td>' +
          '<td class="num">' + (k.acos == null ? '<span class="unk">—</span>' : NS.fmt(k.acos) + '%') + '</td>' +
          '<td>' + mov + '</td>' +
          '<td>' + guard + '</td>' +
          '<td class="dim">' + NS.escapeHtml(k.autoAction || '') + '</td>' +
          '</tr>';
      }).join('');
    }

    // ACoS bands
    var bands = document.getElementById('ap-acos-bands');
    if (bands) {
      bands.innerHTML = (ad.acosBands || []).map(function (b) {
        return '<div class="compliance-row" data-band="' + NS.escapeHtml(b.band) + '"><span class="pill ' + b.kind + '">' + NS.escapeHtml(b.band) + '</span> → ' + NS.escapeHtml(b.action) + '</div>';
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

    // bulk ops fixture table
    var bulkBody = document.getElementById('ap-bulk-body');
    if (bulkBody) {
      bulkBody.innerHTML = (ad.bulkRows || []).map(function (r) {
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
    }

    // gate banners
    ['adpilot_ads_read', 'adpilot_bulk_exec'].forEach(function (g) {
      var el = document.getElementById('gate-' + g);
      if (el) NS.renderGateBanner(el, g);
    });
  }

  function movementPill(m) {
    if (m === 'PROMOTED') return '<span class="pill green">PROMOTED</span>';
    if (m === 'DEMOTED') return '<span class="pill crimson">DEMOTED</span>';
    return '<span class="pill dim">NO_CHANGE</span>';
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'adpilot') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.ap = { onMount: onMount };
})();