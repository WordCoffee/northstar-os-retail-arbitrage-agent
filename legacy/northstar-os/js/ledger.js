/* ==========================================================================
   NORTHSTAR OS — THE LEDGER SERVICE VIEW
   Profitability dashboard: portfolio P&L KPIs, a monthly net-profit chart,
   and a per-SKU P&L table. Zero network; a live P&L needs Amazon settlement +
   ads spend read (both gated) so everything here is a labeled demo fixture.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function getEl(id) { return document.getElementById(id); }
  function money(v) { return v == null ? '<span class="unk">—</span>' : '$' + NS.fmt(v); }
  function pct(v) { return v == null ? '<span class="unk">—</span>' : NS.fmt(v) + '%'; }

  function renderKpis(data) {
    var strip = getEl('led-kpis');
    if (!strip) return;
    strip.innerHTML = (data.kpis || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
    }).join('');
  }

  function renderMonthly(monthly) {
    var el = getEl('led-monthly');
    if (!el) return;
    NS.renderInkPlot(el, 'Net profit by month (demo)', monthly || []);
  }

  function marginClass(m) {
    if (m == null) return '';
    return m >= 20 ? 'text-green' : m >= 10 ? '' : 'text-red';
  }

  function renderSkus(skus) {
    var tbody = getEl('led-sku-body');
    if (!tbody) return;
    if (!skus || !skus.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="service-empty">No P&L rows in this fixture.</td></tr>';
      return;
    }
    tbody.innerHTML = skus.map(function (s) {
      return '<tr class="row-card" data-sku="' + NS.escapeHtml(s.sku) + '">' +
        '<td class="img-cell">' + NS.img(s.image, s.name, 'img-tile') + '</td>' +
        '<td class="dim">' + NS.escapeHtml(s.sku) + '</td>' +
        '<td>' + NS.escapeHtml(s.name) + '</td>' +
        '<td class="num">' + NS.fmt(s.units) + '</td>' +
        '<td class="num">' + money(s.revenue) + '</td>' +
        '<td class="num">' + money(s.cogs) + '</td>' +
        '<td class="num">' + money(s.fees) + '</td>' +
        '<td class="num">' + money(s.ads) + '</td>' +
        '<td class="num">' + money(s.net) + '</td>' +
        '<td class="num ' + marginClass(s.margin) + '">' + pct(s.margin) + '</td>' +
        '</tr>';
    }).join('');
  }

  function onMount() {
    var data = NS.DEMO ? NS.DEMO() : null;
    var led = data && data.ledger;
    if (!led) return;
    renderKpis(led);
    renderMonthly(led.monthly);
    renderSkus(led.skus);
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'theledger') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.ledger = { onMount: onMount, renderSkus: renderSkus };
})();
