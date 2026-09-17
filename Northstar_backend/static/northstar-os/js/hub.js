/* ==========================================================================
   NORTHSTAR OS — HUB VIEW
   Suite overview: global KPIs + one card per service + activity feed.
   Zero network.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  // Trend colors
  NS.TREND_UP = 'up'; NS.TREND_DOWN = 'down';

  function renderKpis(demoHub) {
    var strip = document.getElementById('hub-kpis');
    if (!strip || !demoHub) return;
    var html = (demoHub.kpis || []).map(function (k) {
      var trendCls = '';
      if (k.trend) {
        trendCls = 'trend ' + k.trend;
        // Show arrow indicator only on hover/focus for accessibility
      }
      return '<div class="kpi-card-enhanced" data-kpi="' + NS.escapeHtml(k.label) + '">' +
        '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' +
        '<div class="val ' + NS.escapeHtml(k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' +
        '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div>' +
        '<span class="trend ' + k.trend + '">' + (k.trend === 'up' ? '▲' : k.trend === 'down' ? '▼' : '') + '</span>' +
        '</div>';
    }).join('');
    strip.innerHTML = html;
  }

  function renderActivityFeed(activity) {
    var list = document.getElementById('feed-list');
    var count = document.getElementById('feed-count');
    if (!list) return;
    if (!activity || activity.length === 0) {
      list.innerHTML = '<li style="color:var(--ink-dim);padding:var(--sp-4);text-align:center;">No activity yet.</li>';
      if (count) count.textContent = '0';
      return;
    }
    if (count) count.textContent = activity.length;
    var html = activity.map(function (ev) {
      var icon = '⚙️'; // default
      if (ev.service === 'SourceScout') icon = '🔍';
      else if (ev.service === 'ListingForge') icon = '✍️';
      else if (ev.service === 'AdPilot') icon = '📈';
      else if (ev.service === 'SocialPulse') icon = '📱';
      return '<li>' +
        '<span class="icon">' + icon + '</span>' +
        '<div class="detail">' +
        '<span class="service">' + NS.escapeHtml(ev.service) + '</span>' +
        '<span class="time">' + NS.escapeHtml(ev.time || '') + '</span>' +
        '</div>' +
        '</li>';
    }).join('');
    list.innerHTML = html;
  }

  function renderServiceStatus(statuses) {
    var grid = document.getElementById('service-status');
    if (!grid || !statuses) return;
    var html = Object.entries(statuses).map(function ([service, state]) {
      var dotClass = 'good';
      if (state === 'warning') dotClass = 'warning';
      else if (state === 'blocked') dotClass = 'blocked';
      return '<div class="service-card">' +
        '<span class="status-dot ' + dotClass + '"></span>' +
        '<span class="status-label">' + NS.escapeHtml(service) + '</span>' +
        '<span class="last-run">Last run: demo</span>' +
        '</div>';
    }).join('');
    grid.innerHTML = html;
  }

  function renderHub(demoHub) {
    renderKpis(demoHub);
    if (NS.onActivityFeed) renderActivityFeed(NS.onActivityFeed());
    renderServiceStatus(demoHub && demoHub.serviceStatus ? demoHub.serviceStatus : {});
  }

  // hook into mount lifecycle
  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'hub') {
      var data = NS.DEMO ? NS.DEMO() : null;
      if (data) renderHub(data.hub);
    }
    if (prevOnMount) prevOnMount(route);
  };
})();