/* ==========================================================================
   NORTHSTAR OS — LIVE STATUS (runtime, honest)
   Fetches /api/v1/status once at boot and, when the warehouse holds live rows,
   surfaces REAL live-warehouse status in the Operations Hub KPI strip —
   replacing the hardcoded "Demo Mode" card. Service tables stay labeled demo
   (they render fixtures); this only reports the live warehouse honestly.
   If the fetch fails or the warehouse is empty, the shell stays in demo mode.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;
  if (!NS) return;

  NS.live = null;

  function applyLive(status) {
    if (!status) return;
    NS.live = status;
    var wh = status.warehouse || {};
    var liveRows = wh.live_rows || 0;
    if (liveRows <= 0) return; // honest: empty warehouse -> stay demo

    var demo = (typeof NS.DEMO === 'function') ? NS.DEMO() : null;
    if (demo && demo.hub && demo.hub.kpis) {
      demo.hub.kpis = demo.hub.kpis.map(function (k) {
        if (k.label === 'Demo Mode') {
          return {
            label: 'Live Warehouse',
            value: liveRows + ' items',
            kind: 'good',
            sub: 'stocked · ' + (wh.fresh_rows || 0) + ' fresh · ' + (wh.pulls || 0) + ' live pulls',
          };
        }
        return k;
      });
    }
    if (NS.currentRoute && NS.currentRoute() === 'hub' && NS.hub && NS.hub.onMount) {
      NS.hub.onMount();
    }
  }

  function load() {
    try {
      fetch('/api/v1/status')
        .then(function (r) { return r.json(); })
        .then(function (b) { applyLive(b && b.data ? b.data : b); })
        .catch(function () { /* offline / error -> stay demo (honest) */ });
    } catch (e) { /* no fetch -> stay demo */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }

  NS.liveStatus = { apply: applyLive, load: load };
})();
