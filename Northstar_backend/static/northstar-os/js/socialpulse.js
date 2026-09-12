/* ==========================================================================
   NORTHSTAR OS — SOCIALPULSE SERVICE VIEW
   Social Media Agent app: brand voices, Content Studio (fixture-template
   caption generator, deterministic per voice/channel), Calendar (click a
   draft to move it into a slot), Creative Prompts, Creator Outreach
   (TOS-compliant), Attribution strip.
   Zero network; publishing / attribution are gated and never fired.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var csStep = 0;            // content-studio regeneration step
  var HASHTAG_SETS = {
    meta: ['#WordCoffee', '#MomLife', '#MorningRitual'],
    instagram: ['#AnalogWellness', '#MentalRefill', '#GetUnstuck'],
    tiktok: ['#WordCoffee', '#SelfCareGifts', '#MorningRitual'],
  };
  var CHANNEL_INDEX = { meta: 0, instagram: 1, tiktok: 2 };
  var WEEK = [
    { day: 'Mon', time: '9:00 AM' },
    { day: 'Tue', time: '8:30 AM' },
    { day: 'Wed', time: '8:30 AM' },
    { day: 'Thu', time: '9:00 AM' },
    { day: 'Fri', time: '12:00 PM' },
    { day: 'Sat', time: '10:00 AM' },
    { day: 'Sun', time: '11:00 AM' },
  ];

  function spData() { return (NS.DEMO() && NS.DEMO().socialpulse) || null; }
  function voices() { return (spData() && spData().voices) || []; }
  function posts() { return (spData() && spData().posts) || []; }
  function findVoice(id) { return voices().filter(function (v) { return v.id === id; })[0] || null; }
  function findPost(id) { return posts().filter(function (p) { return p.id === id; })[0] || null; }

  function slotLabel(s) { return s.day + ' ' + s.time; }

  /* pure, deterministic generator: channel -> exact voice tagline + channel
   * hashtag set (fixture "templates at first"). step cycles for regen. */
  function generateCaption(voiceId, channel, step) {
    var v = findVoice(voiceId);
    if (!v) return null;
    var idx = (CHANNEL_INDEX[channel] || 0) + ((step || 0) % v.taglines.length);
    var tagline = v.taglines[idx % v.taglines.length];
    return { caption: tagline, hashtags: HASHTAG_SETS[channel] || ['#WordCoffee'] };
  }

  /* first free calendar slot (in-memory); occupied = saved posts' slots */
  function nextFreeSlot() {
    var taken = {};
    posts().forEach(function (p) { if (p.saved && p.slot) taken[p.slot] = true; });
    for (var i = 0; i < WEEK.length; i++) {
      var lbl = slotLabel(WEEK[i]);
      if (!taken[lbl]) return lbl;
    }
    return null;
  }

  function hashtagChips(set, clickable) {
    return (set || []).map(function (h) {
      return '<span class="hashtag" data-hashtag="' + NS.escapeHtml(h) + '"' + (clickable ? ' role="button" tabindex="0"' : '') + '>' + NS.escapeHtml(h) + '</span>';
    }).join('');
  }

  function renderPosts() {
    var host = document.getElementById('soc-posts');
    if (!host) return;
    host.innerHTML = posts().map(function (p) {
      var chips = hashtagChips(p.hashtags, !p.saved);
      var saved = p.saved ? '<span class="pill green">scheduled</span>' : '<span class="pill dim">draft</span>';
      var schedule = p.saved ? '' : '<button id="schedule-' + NS.escapeHtml(p.id) + '" class="btn small gold" data-schedule="' + NS.escapeHtml(p.id) + '">Schedule ✓ (demo)</button>';
      return '<div class="panel" data-post="' + NS.escapeHtml(p.id) + '">' +
        '<div class="panel-head"><h3>' + NS.escapeHtml(p.channel) + '</h3>' + saved + '</div>' +
        '<div class="caption-card">' + NS.escapeHtml(p.copy) + '</div>' +
        '<div style="margin-top:8px">' + chips + '</div>' +
        '<div class="dim" style="margin-top:8px">Slot: ' + NS.escapeHtml(p.slot) + '</div>' +
        (schedule ? '<div class="editor-meta" style="margin:8px 0 0">' + schedule + '</div>' : '') +
        '</div>';
    }).join('');
    posts().forEach(function (p) { bindSchedule(p.id); });
  }

  function bindSchedule(postId) {
    var btn = document.getElementById('schedule-' + postId);
    if (!btn || btn._socBound) return;
    btn._socBound = true;
    btn.addEventListener('click', function () { schedule(postId); });
  }

  /* move a draft into the next free calendar slot; in-memory only */
  function schedule(postId) {
    var p = findPost(postId);
    if (!p || p.saved) return false;
    var slot = nextFreeSlot();
    if (!slot) return false;
    p.saved = true;
    p.slot = slot;
    renderPosts();
    renderCalendar();
    return true;
  }

  function renderCalendar() {
    var host = document.getElementById('soc-calendar');
    if (!host) return;
    var bySlot = {};
    posts().forEach(function (p) { if (p.saved && p.slot) bySlot[p.slot] = p; });
    host.innerHTML = WEEK.map(function (s) {
      var lbl = slotLabel(s);
      var p = bySlot[lbl];
      if (p) {
        return '<div class="day-slot filled" data-slot="' + NS.escapeHtml(lbl) + '" data-filled="' + NS.escapeHtml(p.id) + '">' +
          '<div class="day">' + NS.escapeHtml(s.day) + ' ' + NS.escapeHtml(s.time) + '</div>' +
          '<div class="slot-copy">' + NS.escapeHtml(p.copy) + '</div>' +
          '<div class="slot-hash">' + (p.hashtags || []).map(NS.escapeHtml).join(' ') + '</div>' +
          '</div>';
      }
      return '<div class="day-slot" data-slot="' + NS.escapeHtml(lbl) + '"><div class="day">' + NS.escapeHtml(s.day) + ' ' + NS.escapeHtml(s.time) + '</div><div class="dim" style="font-size:9px">open</div></div>';
    }).join('');
  }

  function renderStudio() {
    var host = document.getElementById('soc-cs-output');
    if (!host) return;
    var channel = 'meta';
    var sel = document.getElementById('soc-cs-channel');
    if (sel && sel.value) channel = sel.value;
    var g = generateCaption('word_coffee', channel, csStep);
    if (!g) return;
    host.innerHTML =
      '<div class="caption-card">' + NS.escapeHtml(g.caption) + '</div>' +
      '<div style="margin-top:8px">' + hashtagChips(g.hashtags, true) + '</div>' +
      '<div class="hint" style="margin-top:8px">Generated from the Word Coffee voice tagline set (demo template) — editable in a later pass; publishing stays gated.</div>';
  }

  function onMount() {
    var sp = spData();
    if (!sp) return;

    // KPI strip
    var kpiStrip = document.getElementById('soc-kpis');
    if (kpiStrip) {
      kpiStrip.innerHTML = (sp.kpis || []).map(function (k) {
        return '<div class="kpi-card" data-kpi="' + NS.escapeHtml(k.label) + '">' + '<div class="lbl">' + NS.escapeHtml(k.label) + '</div>' + '<div class="val ' + (k.kind || '') + '">' + NS.escapeHtml(k.value) + '</div>' + '<div class="sub">' + NS.escapeHtml(k.sub || '') + '</div></div>';
      }).join('');
    }

    // voices
    var voicesHost = document.getElementById('soc-voices');
    if (voicesHost) {
      voicesHost.innerHTML = voices().map(function (v) {
        var note = v.notBeverage ? '<div class="notice block">Rule enforced: Word Coffee is NOT a beverage. Never reference coffee beans, k-cups, or drinking the product.</div>' : '';
        return '<div class="panel" data-voice="' + NS.escapeHtml(v.id) + '">' +
          '<div class="panel-head"><h3>' + NS.escapeHtml(v.brand) + '</h3><span class="voice-chip">voice module</span></div>' +
          '<p class="dim">' + NS.escapeHtml(v.tone) + '</p>' +
          '<p class="dim">Taglines: ' + v.taglines.map(NS.escapeHtml).join(' · ') + '</p>' +
          note + '</div>';
      }).join('');
    }

    // calendar (in-memory occupancy derived from saved posts)
    renderCalendar();

    // posts (studio drafts + scheduling affordance)
    renderPosts();

    // content studio controls
    var genBtn = document.getElementById('soc-cs-generate');
    if (genBtn && !genBtn._socBound) {
      genBtn._socBound = true;
      genBtn.addEventListener('click', function () {
        csStep += 1;
        renderStudio();
      });
    }
    var schBtn = document.getElementById('soc-cs-schedule');
    if (schBtn && !schBtn._socBound) {
      schBtn._socBound = true;
      schBtn.addEventListener('click', function () {
        var sel = document.getElementById('soc-cs-channel');
        var channel = sel && sel.value ? sel.value : 'meta';
        var g = generateCaption('word_coffee', channel, csStep);
        if (!g) return;
        var slot = nextFreeSlot();
        if (!slot) { renderStudio(); return; }
        posts().push({ id: 'cs' + (posts().length + 1), brand: 'word_coffee', channel: channel, copy: g.caption, hashtags: g.hashtags, slot: slot, saved: true, generated: true });
        renderStudio();
        renderPosts();
        renderCalendar();
      });
    }
    renderStudio();

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

    // gate banners
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
  window.NS.soc = { onMount: onMount, generateCaption: generateCaption, schedule: schedule, nextFreeSlot: nextFreeSlot, week: WEEK };
})();