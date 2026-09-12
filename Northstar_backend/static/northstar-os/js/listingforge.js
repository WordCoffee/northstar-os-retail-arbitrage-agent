/* ==========================================================================
   NORTHSTAR OS — LISTINGFORGE SERVICE VIEW
   Listing Optimizer Agent app: Listing Studio, Scoring dials + weighted-sum
   breakdown, Compliance guardrails, Media/A+ prompter, Keyword Bridge with
   byte/duplicate checks, Feedback Loop (learning-signal log).
   Zero network; Claude copy / media generation live calls are gated and
   never fired. All editing is a labeled demo draft.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var currentAsin = null;
  var drafts = {};      // asin -> { title, ... } demo drafts (in-memory only)
  var feedback = [];    // learning-signal log (in-memory only)
  var seq = 0;

  // Scoring model — five categories, weighted toward the Amazon listing
  // contract (master plan). raw is 0-100 per category; total = weighted sum.
  var WEIGHTS = { seo: 0.30, conversion: 0.25, compliance: 0.20, visual: 0.10, rufus: 0.15 };
  var LIMITS = { titleMax: 200, titleIdeal: 131, backendBytes: 250 };

  function listingData(data) {
    return (data && data.listingforge && data.listingforge.listings) || [];
  }
  function findListing(asin) { return listingData(NS.DEMO()).filter(function (l) { return l.asin === asin; })[0]; }

  /* pure scoring: weighted sum of raw (0-100) category scores, 1 decimal */
  function weightedTotal(raws) {
    if (!raws) return null;
    var sum = 0;
    ['seo', 'conversion', 'compliance', 'visual', 'rufus'].forEach(function (k) {
      var v = parseFloat(raws[k]);
      if (isNaN(v)) return;
      sum += v * (WEIGHTS[k] || 0);
    });
    return Math.round(sum * 10) / 10;
  }
  /* pure byte length (VM-safe, no TextEncoder dependency) */
  function byteLen(s) {
    s = String(s == null ? '' : s);
    var n = 0, i, c;
    for (i = 0; i < s.length; i++) {
      c = s.charCodeAt(i);
      n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4;
    }
    return n;
  }

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

    bindTabs();
    renderListing();

    // gate banners
    ['listingforge_copy', 'listingforge_media'].forEach(function (g) {
      var el = document.getElementById('gate-' + g);
      if (el) NS.renderGateBanner(el, g);
    });

    NS.bindKnobs(document.getElementById('view-listingforge'));
  }

  /* ---------- sub-view tabs: overview shows every panel; a named tab
   * isolates one panel so the work surface stays dense (Analyst's Desk) */
  function bindTabs() {
    var tabs = document.getElementById('lf-tabs');
    if (!tabs || tabs._lfBound) return;
    tabs._lfBound = true;
    var btns = [];
    if (tabs.querySelectorAll) btns = Array.prototype.slice.call(tabs.querySelectorAll('.lf-tab[data-lf-tab]'));
    btns.forEach(function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-lf-tab')); });
    });
  }
  function setTab(tab) {
    var detail = document.getElementById('lf-detail');
    if (!detail) return;
    var panels = [];
    if (detail.querySelectorAll) panels = Array.prototype.slice.call(detail.querySelectorAll('.lf-panel[data-panel]'));
    var tabsEl = document.getElementById('lf-tabs');
    if (tabsEl && tabsEl.querySelectorAll) {
      Array.prototype.slice.call(tabsEl.querySelectorAll('.lf-tab')).forEach(function (b) {
        var on = tab === 'overview' || b.getAttribute('data-lf-tab') === tab;
        b.classList.toggle('active', on);
      });
    }
    panels.forEach(function (p) {
      var show = tab === 'overview' || p.getAttribute('data-panel') === tab;
      if (show) p.classList.remove('hidden'); else p.classList.add('hidden');
    });
  }

  function renderListing() {
    var l = findListing(currentAsin);
    if (!l) return;
    var detail = document.getElementById('lf-detail');
    if (!detail) return;

    var draftTitle = (drafts[currentAsin] && drafts[currentAsin].title) || l.title;

    /* ---- scoring: 6 dials (5 categories + rufus readiness) ---- */
    var scorePills = Object.keys(l.scores).filter(function (k) { return k !== 'total' && k !== 'rufusReadiness'; }).map(function (k) {
      return '<div class="kpi-card" data-score="' + NS.escapeHtml(k) + '"><div class="lbl">' + NS.escapeHtml(k) + '</div><div class="val gold">' + NS.escapeHtml(l.scores[k]) + '</div></div>';
    }).join('');
    scorePills += '<div class="kpi-card" data-score="rufusReadiness"><div class="lbl">Rufus Readiness</div><div class="val gold">' + NS.escapeHtml(l.scores.rufusReadiness) + '</div></div>';

    /* ---- weighted-sum breakdown (real math on fixture raws) ---- */
    var breakdown = ['seo', 'conversion', 'compliance', 'visual', 'rufus'].map(function (k) {
      var raw = l.scoreRaws ? parseFloat(l.scoreRaws[k]) : null;
      var w = WEIGHTS[k];
      var contrib = (raw == null || isNaN(raw)) ? null : Math.round(raw * w * 10) / 10;
      var width = raw == null ? 0 : Math.max(3, Math.round(raw));
      return '<div class="cat-row" data-cat="' + NS.escapeHtml(k) + '">' +
        '<span class="lbl">' + NS.escapeHtml(k) + '</span>' +
        '<span class="dim">weight ' + Math.round(w * 100) + '%</span>' +
        '<div class="cat-bar"><div class="cat-fill ' + (k === 'compliance' ? 'gold' : 'steel') + '" style="width:' + width + '%"></div></div>' +
        (raw == null ? '<span class="unk">—</span>' : '<span class="val">' + NS.escapeHtml(raw) + '/100</span>') +
        '<span class="contrib">' + (contrib == null ? '—' : '+' + contrib) + '</span>' +
        '</div>';
    }).join('');

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

    var feedbackRows = feedback.length
      ? feedback.map(function (f, i) {
          return '<div class="feedback-row" data-feedback="' + f.asin + '" data-fb-kind="' + NS.escapeHtml(f.kind) + '">' +
            '<span class="pill dim">#' + (i + 1) + '</span> ' +
            '<span class="dim">' + NS.escapeHtml(f.asin) + '</span> — ' + NS.escapeHtml(f.note) +
            (f.title ? '<div class="caption-card" style="margin-top:6px">' + NS.escapeHtml(f.title) + '</div>' : '') +
            '</div>';
        }).join('')
      : '<div class="service-empty">No edits recorded yet. Save a Studio draft or add a backend term to seed the learning loop.</div>';

    detail.innerHTML =
      '<div class="panel lf-panel" data-panel="scoring"><div class="panel-head"><h3>Scoring Engine</h3><span class="hint">' + NS.escapeHtml(l.asin) + ' · provenance ' + NS.escapeHtml(l.provenance) + ' · SEO 30% · Conv 25% · Compl 20% · Visual 10% · Rufus 15%</span></div>' +
      '<div class="kpi-strip">' + scorePills + '</div>' +
      '<div class="knob-wrap"><div class="knob" data-min="0" data-max="100" data-step="1" data-unit="" data-value="' + NS.escapeHtml(l.scores.total) + '" data-score-total></div><span class="knob-label">Total Score</span><span class="knob-value">' + NS.escapeHtml(l.scores.total) + '</span></div>' +
      '<div class="cat-breakdown" data-breakdown>' + breakdown + '</div>' +
      '<div class="notice" style="margin-top:10px">Total = weighted sum of category raw scores (0-100 each) — fixture <code>scoreRaws</code>, disclosed as demo. <span class="pill steel" data-total-badge>' + NS.escapeHtml((l.scores.total)) + '</span></div>' +
      '</div>' +

      '<div class="panel lf-panel" data-panel="studio"><div class="panel-head"><h3>Listing Studio</h3><span class="hint">demo draft · live rewrite gated</span></div>' +
      '<label class="editor-lbl" for="lf-title-edit">Title</label>' +
      '<textarea id="lf-title-edit" class="editor" rows="2" maxlength="' + LIMITS.titleMax + '"></textarea>' +
      '<div class="editor-meta"><span class="char-count" id="lf-title-count">' + draftTitle.length + ' / ' + LIMITS.titleMax + ' chars · ideal &le; ' + LIMITS.titleIdeal + '</span>' +
      '<span class="hint" id="lf-title-suggest">' + (draftTitle.length > LIMITS.titleIdeal ? 'Over the ' + LIMITS.titleIdeal + '-char shop-placement ideal.' : 'Length within the recommended band.') + '</span>' +
      '<button class="btn gold" id="lf-title-save">Save draft (demo)</button></div>' +
      '<div class="bullets">' + bullets + '</div>' +
      '<div class="notice">The full editing surface (live rewrite) is gated below — no live Claude call is made by this screen. Drafts stay in this tab\u2019s memory only.</div>' +
      '</div>' +

      '<div class="panel lf-panel" data-panel="compliance"><div class="panel-head"><h3>Compliance Guardrails</h3><span class="hint">rule-based screening · block vs warn</span></div>' + compliance + '</div>' +

      '<div class="panel lf-panel" data-panel="media"><div class="panel-head"><h3>A+ / Media Prompts</h3><span class="hint">7 gallery · 4 video · 5 A+</span></div>' +
      '<div class="media-grid" data-media="gallery">' + gallery + '</div>' +
      '<div class="media-grid" data-media="video">' + video + '</div>' +
      '<div class="media-grid" data-media="aplus">' + aPlus + '</div></div>' +

      '<div class="panel lf-panel" data-panel="bridge"><div class="panel-head"><h3>Keyword Bridge</h3><span class="hint">backend terms · ' + LIMITS.backendBytes + '-byte cap · duplicate detection</span></div>' +
      '<div class="terms">' + terms + '</div>' +
      '<div class="editor-meta"><input id="lf-term-input" class="editor" type="text" placeholder="new backend term (demo)">' +
      '<span class="char-count" id="lf-term-count">0 / ' + LIMITS.backendBytes + ' bytes</span>' +
      '<button class="btn steel" id="lf-term-add">Add (demo)</button></div>' +
      '<div class="hint" id="lf-term-status"></div></div>' +

      '<div class="panel lf-panel" data-panel="feedback"><div class="panel-head"><h3>Feedback Loop</h3><span class="hint">edits &amp; corrections as learning signals</span></div>' + feedbackRows + '</div>';

    var titleEdit = document.getElementById('lf-title-edit');
    if (titleEdit) {
      titleEdit.value = draftTitle;
      titleEdit.addEventListener('input', function () {
        drafts[currentAsin] = drafts[currentAsin] || {};
        drafts[currentAsin].title = titleEdit.value;
        updateTitleMeta(titleEdit, l);
      });
    }

    var titleSave = document.getElementById('lf-title-save');
    if (titleSave) titleSave.addEventListener('click', function () {
      seq += 1;
      var t = (drafts[currentAsin] && drafts[currentAsin].title) || l.title;
      feedback.push({ asin: currentAsin, kind: 'title_draft', seq: seq, title: t, note: 'Title draft saved (demo, not submitted ' + l.brand + ' voice).' });
      renderListing();
    });

    var termInput = document.getElementById('lf-term-input');
    if (termInput) {
      termInput.addEventListener('input', function () { updateTermMeta(termInput, l); });
    }
    var termAdd = document.getElementById('lf-term-add');
    if (termAdd) termAdd.addEventListener('click', function () {
      var term = termInput.value.trim();
      var status = document.getElementById('lf-term-status');
      if (!term) { if (status) status.textContent = 'Enter a term first.'; return; }
      if (byteLen(term) > LIMITS.backendBytes) { if (status) status.textContent = 'Over the ' + LIMITS.backendBytes + '-byte cap — shorten it.'; return; }
      if (l.backendTerms.some(function (t) { return t.toLowerCase() === term.toLowerCase(); })) {
        if (status) status.textContent = 'Duplicate detected — that term is already bridged.';
        return;
      }
      l.backendTerms.push(term);
      seq += 1;
      feedback.push({ asin: currentAsin, kind: 'backend_term', seq: seq, note: 'Added backend term "' + term + '" (demo draft).' });
      renderListing();
    });

    updateTitleMeta(titleEdit, l);
    updateTermMeta(termInput, l);

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

  function updateTitleMeta(edit, l) {
    if (!edit) return;
    var count = document.getElementById('lf-title-count');
    var suggest = document.getElementById('lf-title-suggest');
    var n = edit.value.length;
    if (count) {
      count.textContent = n + ' / ' + LIMITS.titleMax + ' chars · ideal &le; ' + LIMITS.titleIdeal;
      count.className = 'char-count' + (n > LIMITS.titleMax ? ' over' : n > LIMITS.titleIdeal ? ' warn' : ' ok');
    }
    if (suggest) suggest.textContent = n > LIMITS.titleIdeal
      ? 'Over the ' + LIMITS.titleIdeal + '-char shop-placement ideal.'
      : 'Length within the recommended band.';
  }

  function updateTermMeta(input, l) {
    if (!input) return;
    var count = document.getElementById('lf-term-count');
    var status = document.getElementById('lf-term-status');
    var term = input.value.trim();
    var b = byteLen(term);
    if (count) {
      count.textContent = b + ' / ' + LIMITS.backendBytes + ' bytes';
      count.className = 'char-count' + (b > LIMITS.backendBytes ? ' over' : b >= LIMITS.backendBytes - 20 ? ' warn' : ' ok');
    }
    if (status) {
      if (b > LIMITS.backendBytes) status.textContent = 'Over the ' + LIMITS.backendBytes + '-byte cap — shorten or split.';
      else if (term && l.backendTerms.some(function (t) { return t.toLowerCase() === term.toLowerCase(); })) status.textContent = 'Duplicate — already bridged.';
      else if (term) status.textContent = 'Byte count fine; no duplicate. Ready to add (demo).';
      else status.textContent = '';
    }
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'listingforge') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.lf = { onMount: onMount, findListing: findListing, weightedTotal: weightedTotal, byteLen: byteLen, setTab: setTab, feedback: feedback, weights: WEIGHTS, limits: LIMITS };
})();