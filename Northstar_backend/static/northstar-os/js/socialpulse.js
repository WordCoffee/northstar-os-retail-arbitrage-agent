/* ==========================================================================
   NORTHSTAR OS — SOCIALPULSE SERVICE VIEW
   Social Media Agent app: brand voices, Content Studio, Calendar,
   Creative Prompts, Creator Outreach (TOS-compliant), Attribution strip.
   Zero network; publishing / attribution are gated and never fired.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function onMount() {
    var data = NS.DEMO();
    if (!data || !data.socialpulse) return;
    var sp = data.socialpulse;

    // KPI strip
    var kpiStrip = document.getElementById('soc-kpis');
    if (kpiStrip) {
      kpiStrip.innerHTML = (sp.kpis || []).map(function (k) {
        return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' + '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' + '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' + '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
      }).join('');
    }

    // voices
    var voices = document.getElementById('soc-voices');
    if (voices) {
      voices.innerHTML = (sp.voices || []).map(function (v) {
        var note = v.notBeverage ? '<div class="notice block">Rule enforced: Word Coffee is NOT a beverage. Never reference coffee beans, k-cups, or drinking the product.</div>' : '';
        return '<div class="panel" data-voice="' + NS.escapeHtml(v.id) + '">' +
          '<div class="panel-head"><h3>' + NS.escapeHtml(v.brand) + '</h3><span class="voice-chip">voice module</span></div>' +
          '<p class="dim">' + NS.escapeHtml(v.tone) + '</p>' +
          '<p class="dim">Taglines: ' + v.taglines.map(NS.escapeHtml).join(' · ') + '</p>' +
          note + '</div>';
      }).join('');
    }

    // posts (studio + calendar)
    var posts = document.getElementById('soc-posts');
    if (posts) {
      posts.innerHTML = (sp.posts || []).map(function (p) {
        var tags = p.hashtags.map(function (h) { return '<span class="hashtag">' + NS.escapeHtml(h) + '</span>'; }).join('');
        var saved = p.saved ? '<span class="pill green">scheduled</span>' : '<span class="pill dim">draft</span>';
        return '<div class="panel" data-post="' + NS.escapeHtml(p.id) + '">' +
          '<div class="panel-head"><h3>' + NS.escapeHtml(p.channel) + '</h3>' + saved + '</div>' +
          '<div class="caption-card">' + NS.escapeHtml(p.copy) + '</div>' +
          '<div style="margin-top:8px">' + tags + '</div>' +
          '<div class="dim" style="margin-top:8px">Slot: ' + NS.escapeHtml(p.slot) + '</div></div>';
      }).join('');
    }

    // creative prompts
    var creatives = document.getElementById('soc-creatives');
    if (creatives) {
      creatives.innerHTML = (sp.creatives || []).map(function (c) {
        return '<div class="media-tile" data-creative="' + NS.escapeHtml(c.kind) + '" style="aspect-ratio:auto;padding:12px;text-align:left;align-items:flex-start"><strong>' + NS.escapeHtml(c.kind) + '</strong> · ' + NS.escapeHtml(c.aspect) + '<br><span class="dim">' + NS.escapeHtml(c.prompt) + '</span></div>';
      }).join('');
    }

    // outreach
    var outreach = document.getElementById('soc-outreach');
    if (outreach) {
      outreach.innerHTML = (sp.outreach || []).map(function (o) {
        var badge = o.compliant ? '<span class="pill green">TOS-compliant</span>' : '<span class="pill gold">review copy</span>';
        return '<div class="panel" data-outreach="' + NS.escapeHtml(o.kind) + '">' +
          '<div class="panel-head"><h3>' + NS.escapeHtml(o.kind) + '</h3>' + badge + '</div>' +
          '<div class="caption-card">' + NS.escapeHtml(o.template) + '</div>' +
          '<div class="dim" style="margin-top:8px">Macros: ' + o.macros.map(NS.escapeHtml).join(', ') + '</div></div>';
      }).join('');
    }

    // attribution strip
    var attrib = document.getElementById('soc-attribution');
    if (attrib) {
      attrib.innerHTML =
        '<div class="notice">External-traffic strategy: Amazon Attribution (maas=) tags boost organic rank. Run only when Amazon PPC is stable (ACoS &lt; 30% consistently) and blended ACoS &lt; 40%.</div>' +
        '<div class="kpi-strip" style="margin-top:12px">' +
        '<div class="kpi-card"><div class="lbl">PPC Stability</div><div class="val gold">28.4% ACoS</div><div class="sub">stable &lt; 30% (demo)</div></div>' +
        '<div class="kpi-card"><div class="lbl">Blended ACoS Threshold</div><div class="val gold">&lt; 40%</div><div class="sub">target band (demo)</div></div>' +
        '<div class="kpi-card"><div class="lbl">Attribution Tags</div><div class="val" style="color:var(--crimson-bright)">GATED</div><div class="sub">generation requires approval</div></div>' +
        '</div>';
    }

    // gate banner
    var gate = document.getElementById('gate-socialpulse_publish');
    if (gate) NS.renderGateBanner(gate, 'socialpulse_publish');
    var gateA = document.getElementById('gate-socialpulse_attrib');
    if (gateA) NS.renderGateBanner(gateA, 'socialpulse_attrib');
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'socialpulse') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.soc = { onMount: onMount };
})();