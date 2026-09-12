/* ==========================================================================
   NORTHSTAR OS — LISTINGFORGE SERVICE VIEW
   Listing Optimizer Agent app: Listing Studio, Scoring dials, Compliance
   guardrails, Media/A+ prompter, Keyword Bridge, Feedback Loop.
   Zero network; copy/media live calls are gated and never fired.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var currentAsin = null;

  function listingData(data) {
    return (data && data.listingforge && data.listingforge.listings) || [];
  }
  function findListing(asin) { return listingData(NS.DEMO()).filter(function (l) { return l.asin === asin; })[0]; }

  function onMount() {
    var data = NS.DEMO();
    if (!data || !data.listingforge) return;
    var listings = data.listingforge.listings;
    currentAsin = listings[0] ? listings[0].asin : null;

    // KPI strip
    var kpiStrip = document.getElementById('lf-kpis');
    if (kpiStrip) {
      kpiStrip.innerHTML = (data.listingforge.kpis || []).map(function (k) {
        return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' + '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' + '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' + '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
      }).join('');
    }

    // listing selector
    var sel = document.getElementById('lf-asin-select');
    if (sel) {
      sel.innerHTML = listings.map(function (l) { return '<option value="' + NS.escapeHtml(l.asin) + '">' + NS.escapeHtml(l.asin) + ' — ' + NS.escapeHtml(l.product) + '</option>'; }).join('');
      sel.value = currentAsin;
      sel.addEventListener('change', function () { currentAsin = sel.value; renderListing(); });
    }

    renderListing();

    // gate banners
    ['listingforge_copy', 'listingforge_media'].forEach(function (g) {
      var el = document.getElementById('gate-' + g);
      if (el) NS.renderGateBanner(el, g);
    });

    NS.bindKnobs(document.getElementById('view-listingforge'));
  }

  function renderListing() {
    var l = findListing(currentAsin);
    if (!l) return;
    var detail = document.getElementById('lf-detail');
    if (!detail) return;

    var scorePills = Object.keys(l.scores).filter(function (k) { return k !== 'total' && k !== 'rufusReadiness'; }).map(function (k) {
      return '<div class="kpi-card" data-score="' + NS.escapeHtml(k) + '"><div class="lbl">' + NS.escapeHtml(k) + '</div><div class="val gold">' + NS.escapeHtml(l.scores[k]) + '</div></div>';
    }).join('');
    scorePills += '<div class="kpi-card" data-score="rufusReadiness"><div class="lbl">Rufus Readiness</div><div class="val gold">' + NS.escapeHtml(l.scores.rufusReadiness) + '</div></div>';

    var bullets = l.bullets.map(function (b, i) {
      return '<div class="bullet-row" data-bullet="' + (i + 1) + '">' + NS.escapeHtml(b) + '</div>';
    }).join('');

    var compliance = l.compliance.map(function (c) {
      var cls = c.severity === 'block' ? 'crimson' : 'gold';
      return '<div class="compliance-row" data-rule="' + NS.escapeHtml(c.rule) + '" data-severity="' + NS.escapeHtml(c.severity) + '">' +
        '<span class="pill ' + cls + '">' + NS.escapeHtml(c.severity) + '</span> ' +
        '<span class="dim">"</span>' + NS.escapeHtml(c.term) + '<span class="dim">"</span> — ' + NS.escapeHtml(c.message) + '</div>';
    }).join('') || '<div class="compliance-row clean">No compliance flags.</div>';

    var gallery = l.mediaPlan.gallery.map(function (g) { return '<div class="media-tile" data-media-kind="gallery"><span class="icon">&#128247;</span>' + NS.escapeHtml(g) + '</div>'; }).join('');
    var video = l.mediaPlan.video.map(function (g) { return '<div class="media-tile" data-media-kind="video"><span class="icon">&#9654;</span>' + NS.escapeHtml(g) + '</div>'; }).join('');
    var aPlus = l.mediaPlan.aPlus.map(function (g) { return '<div class="media-tile" data-media-kind="aplus"><span class="icon">&#9733;</span>' + NS.escapeHtml(g) + '</div>'; }).join('');

    var terms = l.backendTerms.map(function (t) { return '<span class="hashtag" data-backend-term="' + NS.escapeHtml(t) + '">' + NS.escapeHtml(t) + '</span>'; }).join('');

    detail.innerHTML =
      '<div class="panel"><div class="panel-head"><h3>' + NS.escapeHtml(l.title) + '</h3><span class="voice-chip">' + NS.escapeHtml(l.brand) + ' voice</span></div>' +
      '<p class="view-sub">' + NS.escapeHtml(l.asin) + ' · provenance: <span class="agent-chip">' + NS.escapeHtml(l.provenance) + '</span> · <span class="demo-badge">demo</span></p></div>' +

      '<div class="panel"><div class="panel-head"><h3>Scoring Engine</h3><span class="hint">SEO 30 · Conv 25 · Compl 20 · Visual 10 · Rufus 15</span></div>' +
      '<div class="kpi-strip">' + scorePills + '</div>' +
      '<div class="knob-wrap"><div class="knob" data-min="0" data-max="100" data-step="1" data-unit="" data-value="' + NS.escapeHtml(l.scores.total) + '" data-score-total></div><span class="knob-label">Total Score</span><span class="knob-value">' + NS.escapeHtml(l.scores.total) + '</span></div>' +
      '</div>' +

      '<div class="panel"><div class="panel-head"><h3>Listing Studio</h3><span class="hint">current copy (fixture)</span></div>' +
      '<div class="bullets">' + bullets + '</div>' +
      '<div class="notice">The full editing surface (live rewrite) is gated below — no live Claude call is made by this screen.</div>' +
      '</div>' +

      '<div class="panel"><div class="panel-head"><h3>Compliance Guardrails</h3><span class="hint">rule-based screening</span></div>' + compliance + '</div>' +

      '<div class="panel"><div class="panel-head"><h3>Keyword Bridge</h3><span class="hint">backend terms · 250-byte cap</span></div>' +
      '<div class="terms">' + terms + '</div></div>' +

      '<div class="panel"><div class="panel-head"><h3>A+ / Media Prompts</h3><span class="hint">7 gallery · 4 video · 5 A+</span></div>' +
      '<div class="media-grid" data-media="gallery">' + gallery + '</div>' +
      '<div class="media-grid" data-media="video">' + video + '</div>' +
      '<div class="media-grid" data-media="aplus">' + aPlus + '</div></div>';

    var gateCopy = document.createElement('div');
    gateCopy.id = 'gate-listingforge_copy';
    gateCopy.className = 'gate-banner';
    gateCopy.setAttribute('data-gate', 'listingforge_copy');
    gateCopy.style.marginTop = '14px';
    var gateMedia = document.createElement('div');
    gateMedia.id = 'gate-listingforge_media';
    gateMedia.className = 'gate-banner';
    gateMedia.setAttribute('data-gate', 'listingforge_media');
    gateMedia.style.marginTop = '14px';
    detail.appendChild(gateCopy);
    detail.appendChild(gateMedia);
    NS.renderGateBanner(gateCopy, 'listingforge_copy');
    NS.renderGateBanner(gateMedia, 'listingforge_media');
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'listingforge') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.lf = { onMount: onMount, findListing: findListing };
})();