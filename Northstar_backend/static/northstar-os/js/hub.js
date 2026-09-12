/* ==========================================================================
   NORTHSTAR OS — HUB VIEW
   Suite overview: global KPIs + one card per service. Zero network.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function renderKpis(demoHub) {
    var strip = document.getElementById('hub-kpis');
    if (!strip || !demoHub) return;
    var html = (demoHub.kpis || []).map(function (k) {
      return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + (k.kind ? NS.escapeHtml(k.kind) : '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div>' +
        '</div>';
    }).join('');
    strip.innerHTML = html;
  }

  function renderServices(demoHub) {
    var grid = document.getElementById('hub-services');
    if (!grid || !demoHub) return;
    var html = (demoHub.services || []).map(function (s) {
      return '<div class="svc-card panel" data-service="' + NS.escapeHtml(s.id) + '">' +
        '<div class="panel-head"><h3>' + NS.escapeHtml(s.name) + '</h3><span class="demo-badge">demo</span></div>' +
        '<p class="svc-agent">' + NS.escapeHtml(s.agent) + '</p>' +
        '<p class="svc-desc">' + NS.escapeHtml(s.desc) + '</p>' +
        '<button class="btn gold" data-open-service="' + NS.escapeHtml(s.id) + '">Open ' + NS.escapeHtml(s.name) + '</button>' +
        '</div>';
    }).join('');
    grid.innerHTML = html;
    // bind open buttons
    Array.prototype.slice.call(grid.querySelectorAll('[data-open-service]')).forEach(function (btn) {
      btn.addEventListener('click', function () { NS.go(btn.getAttribute('data-open-service')); });
    });
  }

  function onMount() {
    var data = NS.DEMO ? NS.DEMO() : null;
    if (!data) return;
    renderKpis(data.hub);
    renderServices(data.hub);
    if (NS.insights.length === 0) {
      NS.showInsight('Profit Spike', 'Portfolio KPIs are demo fixtures — no live data has been loaded.', true);
    }
  }

  if (NS) {
    NS.hub = { onMount: onMount };
  }

  // hook into mount lifecycle
  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'hub') onMount();
    if (prevOnMount) prevOnMount(route);
  };
})();