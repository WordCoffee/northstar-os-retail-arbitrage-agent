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

  /* ==========================================================================
   * Phase 2 · renderHubServices — the four Phase-1 agent cards into #hub-services
   * (the ANALYST'S HUB wants its four primary services as clickable cards).
   * Phase 2 contract: exactly 4 cards, each data-service + signature accent,
   * SourceScout first elegantly. Zero network. Pure demo.
   * ========================================================================== */
  function renderHubServices(services) {
    var grid = document.getElementById('hub-services');
    if (!grid) return;
    if (!services || !services.length) {
      grid.innerHTML = '<p class="service-empty">No services registered yet (demo shell).</p>';
      return;
    }
    var html = services.map(function (svc) {
      var route = svc.route || svc.id || 'hub';
      var accent = svc.sig || '--sig-demo';
      var name = svc.name || route;
      var chip = svc.agent || svc.chip || 'agent';
      var icon = svc.icon || '◇';
      var blurb = svc.desc || '';
      return '<div class="service-card phase2 service-card--agent" data-service="' + NS.escapeHtml(name) + '" ' +
        'data-route="' + NS.escapeHtml(route) + '" ' +
        'style="--sig-accent:' + NS.escapeHtml(accent) + ';--sig-accent-dim:' + NS.escapeHtml(svc.sigDim || accent) + '">' +
        '<div class="service-icon">' + icon + '</div>' +
        '<div class="service-name">' + NS.escapeHtml(name) + '</div>' +
        '<div class="service-chip">' + NS.escapeHtml(chip) + '</div>' +
        (blurb ? '<div class="service-blurb">' + NS.escapeHtml(blurb) + '</div>' : '') +
        '<span class="demo-badge">demo</span>' +
        '</div>';
    }).join('');
    grid.innerHTML = html;

    /* bind open → nav */
    Array.prototype.slice.call(grid.querySelectorAll('.service-card[data-route]')).forEach(function (card) {
      card.addEventListener('click', function () {
        /* open-from-hub: honor both data-route (shell cards) and */
        /* data-open-service (open-from-hub buttons) so any hub    */
        /* entry point navigates to its agent view.                 */
        var route = card.getAttribute('data-open-service') || card.getAttribute('data-route');
        if (route && NS.go) NS.go(route);
      });
    });
  }

  function renderHub(demoHub) {
    renderKpis(demoHub);
    if (NS.onMountFeed) renderActivityFeed(NS.onActivityFeed ? NS.onActivityFeed() : null);
    renderServiceStatus(demoHub && demoHub.statuses);
    if (demoHub && demoHub.services) renderHubServices(demoHub.services);
  }

  /* ------------------------------------------------------------------
   * Phase 2 · PUBLIC API — NS.hub
   * The analyst's hub exposes a per-agent module (same shape as the other
   * four agents) so the shell can mount it on demand and so the suite's
   * "hub: open-service buttons bound" contract stays deterministic.
   * onMount() re-renders the whole hub surface (KPIs, feed, status,
   * service grid) using the current demo fixture. Zero network.
   * ------------------------------------------------------------------ */
  NS.hub = {
    onMount: function () {
      var data = NS.DEMO ? NS.DEMO() : null;
      if (data && data.hub) renderHub(data.hub);
    }
  };

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