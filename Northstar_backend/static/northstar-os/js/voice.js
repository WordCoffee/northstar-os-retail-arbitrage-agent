/* ==========================================================================
   NORTHSTAR OS — VOICE INPUT (microphone icons on every input)
   Adds a clickable mic button beside every text input / textarea / editor.
   Click to dictate; the Web Speech API transcribes into the field and fires
   input/change so the app reacts. Free, offline, no server, Chrome/Edge.
   Falls back to a toast when the browser has no SpeechRecognition.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  var MIC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4M8 22h8"/></svg>';

  function support() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  var recog = null;
  var activeBtn = null;

  function stop() {
    if (recog) { try { recog.stop(); } catch (e) { /* noop */ } }
    if (activeBtn) {
      activeBtn.classList.remove('rec');
      activeBtn.setAttribute('aria-label', 'Dictate');
      activeBtn.title = 'Dictate with your voice';
    }
    activeBtn = null;
  }

  function appendText(host, text) {
    if (!host) return;
    var sep = host.tagName === 'INPUT' ? ' ' : ' ';
    host.value = host.value ? host.value.replace(/\s+$/, '') + sep + text : text;
    try {
      host.dispatchEvent(new Event('input', { bubbles: true }));
      host.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) { /* noop */ }
  }

  function toggle(btn, host) {
    if (!support()) {
      if (NS.toast) NS.toast('Voice input needs Chrome or Edge (Web Speech API).', 'info');
      return;
    }
    if (activeBtn === btn) { stop(); return; }
    stop();
    if (!recog) {
      var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      recog = new SR();
      recog.continuous = false;
      recog.interimResults = false;
      recog.lang = 'en-US';
      recog.onresult = function (ev) {
        var text = '';
        for (var i = 0; i < ev.results.length; i++) text += ev.results[i][0].transcript;
        appendText(host, text);
        stop();
      };
      recog.onerror = function () { stop(); };
      recog.onend = function () { stop(); };
    }
    activeBtn = btn;
    btn.classList.add('rec');
    btn.setAttribute('aria-label', 'Stop dictation');
    btn.title = 'Listening — click to stop';
    try { recog.start(); } catch (e) { stop(); }
  }

  function makeMic(host) {
    var wrap = document.createElement('span');
    wrap.className = 'voice-wrap';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'voice-input';
    btn.setAttribute('aria-label', 'Dictate');
    btn.title = 'Dictate with your voice';
    btn.innerHTML = MIC;
    btn.addEventListener('click', function () { toggle(btn, host); });
    var parent = host.parentNode;
    if (parent) parent.replaceChild(wrap, host); // swap host for wrap
    wrap.appendChild(host);                      // then move host inside wrap
    wrap.appendChild(btn);                       // mic button after the field
  }

  function bind(scope) {
    var root = scope || document;
    var targets = root.querySelectorAll('textarea, input[type="text"]');
    Array.prototype.forEach.call(targets, function (el) {
      if (el._voiceBound) return;
      el._voiceBound = true;
      if (el.closest && el.closest('.voice-wrap')) return;
      makeMic(el);
    });
  }

  NS.voice = { bind: bind, support: support, stop: stop };
  NS.bindVoice = bind;

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (prevOnMount) prevOnMount(route);
    bind(document); // voice mics on dynamically-rendered inputs too
  };
})();