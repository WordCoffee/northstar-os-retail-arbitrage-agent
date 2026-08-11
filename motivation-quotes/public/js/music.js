// Japanese Trap Beat Engine — 4 generative lo-fi beats using Web Audio API
// Each beat loops ~70-100s with auto crossfade

class TrapBeats {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.isPlaying = false;
    this.currentTrack = 0;
    this.timer = null;
    this.volume = 0.35;
    this.onTrackChange = null;
  }

  async init() {
    if (this.ctx) return;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();

    this.master = this.ctx.createGain();
    this.master.gain.value = 0;

    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -16;
    comp.knee.value = 20;
    comp.ratio.value = 8;
    comp.attack.value = 0.004;
    comp.release.value = 0.12;

    const lp = this.ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 12000;
    lp.Q.value = 0.3;

    this.master.connect(lp);
    lp.connect(comp);
    comp.connect(this.ctx.destination);

    // Pre-generate noise buffer
    this.noiseBuf = this.ctx.createBuffer(1, this.ctx.sampleRate * 0.15, this.ctx.sampleRate);
    const nd = this.noiseBuf.getChannelData(0);
    for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
  }

  // ── Sound Synthesis ──

  _kick(t) {
    const c = this.ctx;
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = 'sine';
    o.frequency.setValueAtTime(160, t);
    o.frequency.exponentialRampToValueAtTime(42, t + 0.09);
    g.gain.setValueAtTime(0.95, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
    o.connect(g); g.connect(this.master);
    o.start(t); o.stop(t + 0.4);
  }

  _snare(t) {
    const c = this.ctx;
    // Noise snap
    const src = c.createBufferSource();
    src.buffer = this.noiseBuf;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass'; bp.frequency.value = 3200; bp.Q.value = 0.7;
    const ng = c.createGain();
    ng.gain.setValueAtTime(0.55, t);
    ng.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
    src.connect(bp); bp.connect(ng); ng.connect(this.master);
    src.start(t); src.stop(t + 0.15);
    // Body
    const o = c.createOscillator();
    const og = c.createGain();
    o.type = 'triangle'; o.frequency.value = 190;
    og.gain.setValueAtTime(0.45, t);
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.07);
    o.connect(og); og.connect(this.master);
    o.start(t); o.stop(t + 0.08);
  }

  _hat(t, vol = 0.16) {
    const c = this.ctx;
    const src = c.createBufferSource();
    src.buffer = this.noiseBuf;
    const hp = c.createBiquadFilter();
    hp.type = 'highpass'; hp.frequency.value = 9500;
    const g = c.createGain();
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.035);
    src.connect(hp); hp.connect(g); g.connect(this.master);
    src.start(t); src.stop(t + 0.04);
  }

  _hatRoll(t, vol = 0.1) {
    for (let i = 0; i < 3; i++) {
      this._hat(t + i * 0.017, vol * (1 - i * 0.25));
    }
  }

  _bass(t, freq, dur) {
    const c = this.ctx;
    const o = c.createOscillator();
    const o2 = c.createOscillator();
    const g = c.createGain();
    // Saturation
    const ws = c.createWaveShaper();
    const curve = new Float32Array(256);
    for (let i = 0; i < 256; i++) { const x = (i*2)/256-1; curve[i] = Math.tanh(x*2.5); }
    ws.curve = curve;
    o.type = 'sine'; o.frequency.value = freq;
    o2.type = 'sine'; o2.frequency.value = freq * 1.002;
    g.gain.setValueAtTime(0.45, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(ws); o2.connect(ws);
    ws.connect(g); g.connect(this.master);
    o.start(t); o.stop(t + dur + 0.01);
    o2.start(t); o2.stop(t + dur + 0.01);
  }

  _koto(t, freq, dur) {
    const c = this.ctx;
    const o = c.createOscillator();
    const o2 = c.createOscillator();
    const g = c.createGain();
    const f = c.createBiquadFilter();
    o.type = 'triangle'; o.frequency.value = freq;
    o2.type = 'sine'; o2.frequency.value = freq * 3;
    f.type = 'lowpass';
    f.frequency.setValueAtTime(freq * 5, t);
    f.frequency.exponentialRampToValueAtTime(freq * 1.2, t + dur);
    g.gain.setValueAtTime(0.22, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(f); o2.connect(f);
    f.connect(g); g.connect(this.master);
    o.start(t); o.stop(t + dur + 0.01);
    o2.start(t); o2.stop(t + dur + 0.01);
  }

  _pad(t, freqs, dur) {
    freqs.forEach(fr => {
      const c = this.ctx;
      const o = c.createOscillator();
      const o2 = c.createOscillator();
      const g = c.createGain();
      o.type = 'sine'; o.frequency.value = fr * 0.998;
      o2.type = 'sine'; o2.frequency.value = fr * 1.002;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.028, t + 2);
      g.gain.setValueAtTime(0.028, t + dur - 2);
      g.gain.linearRampToValueAtTime(0, t + dur);
      o.connect(g); o2.connect(g); g.connect(this.master);
      o.start(t); o.stop(t + dur + 0.1);
      o2.start(t); o2.stop(t + dur + 0.1);
    });
  }

  _crackle(t, dur) {
    const c = this.ctx;
    const buf = c.createBuffer(1, c.sampleRate * dur, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) {
      d[i] = (Math.random() * 2 - 1) * 0.008;
      if (Math.random() < 0.0005) d[i] = (Math.random() - 0.5) * 0.15;
    }
    const src = c.createBufferSource();
    src.buffer = buf;
    const bp = c.createBiquadFilter();
    bp.type = 'bandpass'; bp.frequency.value = 2500; bp.Q.value = 0.4;
    const g = c.createGain();
    g.gain.value = 0.6;
    src.connect(bp); bp.connect(g); g.connect(this.master);
    src.start(t);
  }

  // ── Track Builder ──

  _build(cfg) {
    const { bpm, bars, kick, snare, hihat, bass, melody, pads, name } = cfg;
    const st = 15 / bpm;
    const barDur = st * 16;
    const events = [];

    for (let bar = 0; bar < bars; bar++) {
      const bo = bar * barDur;
      const bp = bar % 4;

      kick.forEach(p => events.push({ fn: '_kick', t: bo + p * st }));
      snare.forEach(p => events.push({ fn: '_snare', t: bo + p * st }));

      const hPattern = hihat[bp % hihat.length] || hihat[0];
      hPattern.forEach(p => {
        if (p.r) events.push({ fn: '_hatRoll', t: bo + p.p * st, v: p.v });
        else events.push({ fn: '_hat', t: bo + p.p * st, v: p.v });
      });

      const bn = bass[bar % bass.length];
      if (bn) events.push({ fn: '_bass', t: bo, f: bn.f, d: bn.d * st });

      const mn = melody[bar % melody.length];
      if (mn) mn.forEach(n => events.push({ fn: '_koto', t: bo + n.p * st, f: n.f, d: n.d * st }));

      const pi = Math.floor(bar / 4) % pads.length;
      if (bar % 4 === 0) {
        const pd = pads[pi];
        events.push({ fn: '_pad', t: bo, f: pd.f, d: pd.d * barDur });
      }
    }

    events.push({ fn: '_crackle', t: 0, d: bars * barDur });
    return { name, events, dur: bars * barDur };
  }

  // ── Playback ──

  _play(idx) {
    if (!this.ctx || !this.isPlaying) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    this.currentTrack = idx;
    const track = BEATS[idx];
    const now = this.ctx.currentTime + 0.05;

    track.events.forEach(ev => {
      const t = now + ev.t;
      if (t > now + track.dur + 1) return;
      this[ev.fn](t, ev.f || ev.d, ev.d, ev.v);
    });

    this.master.gain.cancelScheduledValues(this.ctx.currentTime);
    this.master.gain.setValueAtTime(0, this.ctx.currentTime);
    this.master.gain.linearRampToValueAtTime(this.volume, this.ctx.currentTime + 3);

    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      if (!this.isPlaying) return;
      this.master.gain.cancelScheduledValues(this.ctx.currentTime);
      this.master.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 3);
      setTimeout(() => this._play((idx + 1) % BEATS.length), 3000);
    }, Math.max((track.dur - 5) * 1000, 5000));

    if (this.onTrackChange) this.onTrackChange(track.name, idx);
  }

  play() {
    this.init().then(() => {
      this.isPlaying = true;
      if (this.ctx.state === 'suspended') this.ctx.resume();
      this._play(this.currentTrack);
    });
  }

  pause() {
    this.isPlaying = false;
    if (this.timer) clearTimeout(this.timer);
    if (this.master && this.ctx) {
      this.master.gain.cancelScheduledValues(this.ctx.currentTime);
      this.master.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 1.5);
    }
  }

  toggle() { if (this.isPlaying) this.pause(); else this.play(); }

  setVolume(v) {
    this.volume = v;
    if (this.isPlaying && this.master && this.ctx) {
      this.master.gain.cancelScheduledValues(this.ctx.currentTime);
      this.master.gain.linearRampToValueAtTime(v, this.ctx.currentTime + 0.1);
    }
  }

  next() {
    if (!this.isPlaying) return;
    this.master.gain.cancelScheduledValues(this.ctx.currentTime);
    this.master.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 2);
    setTimeout(() => this._play((this.currentTrack + 1) % BEATS.length), 2000);
  }

  getTrackList() { return BEATS.map((b, i) => ({ name: b.name, index: i })); }
}

// ── Scale Frequencies ──
const F = {
  E2:82.41,A2:110,B2:123.47,
  E3:164.81,F3:174.61,G3:196,A3:220,B3:246.94,
  C4:261.63,Cs4:277.18,D4:293.66,Ds4:311.13,E4:329.63,F4:349.23,G4:390,Gs4:415.30,A4:440,As4:466.16,B4:493.88,
  C5:523.25,Cs5:554.37,D5:587.33,Ds5:622.25,E5:659.25,F5:698.46,G5:783.99,Gs5:830.61,A5:880
};

// ── Track Definitions ──
const BEATS = [
  // ── Track 1: Tokyo Nights (75 BPM, E minor) ──
  {
    name: 'Tokyo Nights',
    dur: 0, // computed below
    events: (() => {
      const bpm = 75, bars = 32;
      const st = 15/bpm, barDur = st*16;
      const ev = [];

      // Melody — E Hirajoshi (E F G B C)
      const mel8 = [
        [[F.E4,0,3],[F.G4,8,2]],
        [[F.B3,0,3],[F.C4,6,2],[F.E4,10,3]],
        null,
        [[F.G4,0,2],[F.E4,6,3]],
        [[F.F4,0,3],[F.E4,8,2]],
        [[F.C4,0,3],[F.B3,6,3]],
        null,
        [[F.E4,2,2],[F.G4,8,3]]
      ];
      // Bass
      const bass = [{f:F.E2,d:8},{f:F.E2,d:8},{f:F.A2,d:8},{f:F.A2,d:8},{f:F.B2,d:8},{f:F.B2,d:8},{f:F.A2,d:8},{f:F.A2,d:8}];
      // Pads
      const pads = [{f:[F.E3,F.G3,F.B3],d:8},{f:[F.A2,F.C4,F.E3],d:8},{f:[F.B2,F.Ds4,F.Fs4||F.G3],d:8},{f:[F.A2,F.C4,F.E3],d:8}];
      // Hi-hat patterns (per bar within 4-bar cycle)
      const hh = [
        [{p:0},{p:2},{p:4},{p:6},{p:8,r:1,v:0.08},{p:9,r:1,v:0.06},{p:10},{p:12},{p:14},{p:15,r:1,v:0.08}],
        [{p:0},{p:2},{p:4},{p:6},{p:8},{p:10},{p:12},{p:14}],
        [{p:0},{p:2},{p:4},{p:6},{p:8,r:1,v:0.08},{p:9,r:1,v:0.06},{p:10},{p:12},{p:14},{p:15,r:1,v:0.08}],
        [{p:0},{p:2},{p:4},{p:6},{p:8},{p:10},{p:12},{p:14}]
      ];
      const kick = [0,6,10,15];
      const snare = [4,12];

      for (let bar = 0; bar < bars; bar++) {
        const bo = bar * barDur;
        const bp = bar % 4;

        kick.forEach(p => ev.push({fn:'_kick',t:bo+p*st}));
        snare.forEach(p => ev.push({fn:'_snare',t:bo+p*st}));
        hh[bp].forEach(h => ev.push(h.r ? {fn:'_hatRoll',t:bo+h.p*st,v:h.v||0.1} : {fn:'_hat',t:bo+h.p*st,v:h.v||0.16}));

        const bn = bass[bar % bass.length];
        ev.push({fn:'_bass',t:bo,f:bn.f,d:bn.d*st});

        const mn = mel8[bar % mel8.length];
        if (mn) mn.forEach(n => ev.push({fn:'_koto',t:bo+n[1]*st,f:n[0],d:n[2]*st}));

        if (bar % 4 === 0) {
          const pd = pads[Math.floor(bar/4)%pads.length];
          ev.push({fn:'_pad',t:bo,f:pd.f,d:pd.d*barDur});
        }
      }
      ev.push({fn:'_crackle',t:0,d:bars*barDur});
      BEATS[0].dur = bars * barDur;
      return ev;
    })()
  },

  // ── Track 2: Sakura Drift (85 BPM, A minor) ──
  {
    name: 'Sakura Drift',
    dur: 0,
    events: (() => {
      const bpm = 85, bars = 32;
      const st = 15/bpm, barDur = st*16;
      const ev = [];

      const mel8 = [
        [[F.A4,0,3],[F.C5,6,2]],
        [[F.E5,0,3],[F.C5,8,2]],
        [[F.B4,0,3],[F.A4,6,3]],
        [[F.F5,0,2],[F.E5,6,3]],
        null,
        [[F.A4,2,2],[F.C5,8,3]],
        [[F.E5,0,3]],
        [[F.C5,6,2],[F.A4,10,3]]
      ];
      const bass = [{f:F.A2,d:8},{f:F.A2,d:8},{f:F.F3,d:8},{f:F.F3,d:8},{f:F.C4,d:8},{f:F.C4,d:8},{f:F.G3,d:8},{f:F.G3,d:8}];
      const pads = [{f:[F.A3,F.C4,F.E4],d:8},{f:[F.F3,F.A3,F.C4],d:8},{f:[F.C4,F.E4,F.G3],d:8},{f:[F.G3,F.B3,F.D4],d:8}];
      const hh = [
        [{p:0},{p:4},{p:8},{p:12}],
        [{p:0},{p:2},{p:4},{p:8},{p:10},{p:12}],
        [{p:0},{p:4},{p:8},{p:12}],
        [{p:0},{p:2},{p:4},{p:8},{p:10},{p:12}]
      ];
      const kick = [0,6,11];
      const snare = [4,12];

      for (let bar = 0; bar < bars; bar++) {
        const bo = bar * barDur;
        const bp = bar % 4;
        kick.forEach(p => ev.push({fn:'_kick',t:bo+p*st}));
        snare.forEach(p => ev.push({fn:'_snare',t:bo+p*st}));
        hh[bp].forEach(h => ev.push({fn:'_hat',t:bo+h.p*st,v:h.v||0.13}));
        const bn = bass[bar % bass.length];
        ev.push({fn:'_bass',t:bo,f:bn.f,d:bn.d*st});
        const mn = mel8[bar % mel8.length];
        if (mn) mn.forEach(n => ev.push({fn:'_koto',t:bo+n[1]*st,f:n[0],d:n[2]*st}));
        if (bar % 4 === 0) { const pd = pads[Math.floor(bar/4)%pads.length]; ev.push({fn:'_pad',t:bo,f:pd.f,d:pd.d*barDur}); }
      }
      ev.push({fn:'_crackle',t:0,d:bars*barDur});
      BEATS[1].dur = bars * barDur;
      return ev;
    })()
  },

  // ── Track 3: Neon District (90 BPM, C# minor) ──
  {
    name: 'Neon District',
    dur: 0,
    events: (() => {
      const bpm = 90, bars = 32;
      const st = 15/bpm, barDur = st*16;
      const ev = [];

      const mel8 = [
        [[F.Cs5,0,2],[F.Ds5,2,2],[F.E5,6,3]],
        [[F.Gs5,0,2],[F.A5,4,2],[F.E5,10,3]],
        [[F.Cs5,0,3],[F.A5,6,2],[F.Gs5,10,2]],
        [[F.E5,0,3],[F.Ds5,6,3]],
        [[F.A5,0,2],[F.Gs5,2,2],[F.E5,6,3]],
        [[F.Cs5,0,2],[F.Ds5,6,2],[F.Cs5,10,3]],
        null,
        [[F.E5,0,3],[F.A5,10,2]]
      ];
      const bass = [{f:F.Cs4,d:8},{f:F.Cs4,d:8},{f:F.A2,d:8},{f:F.A2,d:8},{f:F.E2,d:8},{f:F.E2,d:8},{f:F.B2,d:8},{f:F.B2,d:8}];
      const pads = [{f:[F.Cs4,F.E4,F.Gs4],d:8},{f:[F.A3,F.Cs4,F.E4],d:8},{f:[F.E3,F.Gs3,F.B3],d:8},{f:[F.B2,F.Ds4,F.Fs4||F.G3],d:8}];
      const hh = [
        [{p:0,r:1,v:0.07},{p:1,r:1,v:0.06},{p:2},{p:4,r:1,v:0.07},{p:5,r:1,v:0.06},{p:6},{p:8,r:1,v:0.07},{p:9,r:1,v:0.06},{p:10},{p:12},{p:14}],
        [{p:0},{p:2},{p:4},{p:6},{p:8},{p:10},{p:12},{p:14},{p:15,r:1,v:0.08}],
        [{p:0,r:1,v:0.07},{p:1,r:1,v:0.06},{p:2},{p:4,r:1,v:0.07},{p:5,r:1,v:0.06},{p:6},{p:8,r:1,v:0.07},{p:9,r:1,v:0.06},{p:10},{p:12},{p:14}],
        [{p:0},{p:2},{p:4},{p:6},{p:8},{p:10},{p:12},{p:14},{p:15,r:1,v:0.08}]
      ];
      const kick = [0,3,6,10,15];
      const snare = [4,12];

      for (let bar = 0; bar < bars; bar++) {
        const bo = bar * barDur;
        const bp = bar % 4;
        kick.forEach(p => ev.push({fn:'_kick',t:bo+p*st}));
        snare.forEach(p => ev.push({fn:'_snare',t:bo+p*st}));
        hh[bp].forEach(h => ev.push(h.r ? {fn:'_hatRoll',t:bo+h.p*st,v:h.v||0.1} : {fn:'_hat',t:bo+h.p*st,v:h.v||0.16}));
        const bn = bass[bar % bass.length];
        ev.push({fn:'_bass',t:bo,f:bn.f,d:bn.d*st});
        const mn = mel8[bar % mel8.length];
        if (mn) mn.forEach(n => ev.push({fn:'_koto',t:bo+n[1]*st,f:n[0],d:n[2]*st}));
        if (bar % 4 === 0) { const pd = pads[Math.floor(bar/4)%pads.length]; ev.push({fn:'_pad',t:bo,f:pd.f,d:pd.d*barDur}); }
      }
      ev.push({fn:'_crackle',t:0,d:bars*barDur});
      BEATS[2].dur = bars * barDur;
      return ev;
    })()
  },

  // ── Track 4: Zen Garden (65 BPM, D minor) ──
  {
    name: 'Zen Garden',
    dur: 0,
    events: (() => {
      const bpm = 65, bars = 24;
      const st = 15/bpm, barDur = st*16;
      const ev = [];

      const mel8 = [
        [[F.D4,0,6]],
        null,
        [[F.A4,0,5]],
        null,
        [[F.E4,0,6]],
        null,
        [[F.F4,0,4],[F.A4,8,3]],
        null
      ];
      const bass = [{f:F.D4,d:16},{f:F.D4,d:16},{f:F.A2,d:16},{f:F.A2,d:16}];
      const pads = [{f:[F.D4,F.F4,F.A4],d:8},{f:[F.A3,F.C4,F.E4],d:8}];
      const hh = [
        [{p:0},{p:8}],
        [{p:0},{p:8}],
        [{p:0},{p:8}],
        [{p:0},{p:4},{p:8},{p:12}]
      ];
      const kick = [0,10];
      const snare = [4,12];

      for (let bar = 0; bar < bars; bar++) {
        const bo = bar * barDur;
        const bp = bar % 4;
        kick.forEach(p => ev.push({fn:'_kick',t:bo+p*st}));
        if (bar % 2 === 0) snare.forEach(p => ev.push({fn:'_snare',t:bo+p*st}));
        hh[bp].forEach(h => ev.push({fn:'_hat',t:bo+h.p*st,v:h.v||0.08}));
        const bn = bass[bar % bass.length];
        ev.push({fn:'_bass',t:bo,f:bn.f,d:bn.d*st});
        const mn = mel8[bar % mel8.length];
        if (mn) mn.forEach(n => ev.push({fn:'_koto',t:bo+n[1]*st,f:n[0],d:n[2]*st}));
        if (bar % 4 === 0) { const pd = pads[Math.floor(bar/4)%pads.length]; ev.push({fn:'_pad',t:bo,f:pd.f,d:pd.d*barDur}); }
      }
      ev.push({fn:'_crackle',t:0,d:bars*barDur});
      BEATS[3].dur = bars * barDur;
      return ev;
    })()
  }
];

const beats = new TrapBeats();
