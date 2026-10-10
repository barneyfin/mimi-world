/* MeeMee World kit: sound.
   Voice lines built from Barney's recorded pieces, sound effects, and the looping music that dips under speech.
   All files are at one loudness reference (-20 LUFS, made by tools/make_audio.py), so mixing is plain gains.

   Browsers only allow sound after a tap: call MW.audio.unlock() from the first tap (TapToStart does). */
(function () {
  'use strict';
  const MW = window.MW;
  const A = MW.audio = {};
  const CONFIG = A.config = {
    base: 'audio/',
    pieceGap: 0.03,        // seconds between pieces inside a sentence ("three" "and" "four")
    sentenceGap: 0.35,     // seconds between sentences
    musicDb: -12,          // music under everything
    musicDuckDb: -22,      // music while a line is spoken
    musicFadeIn: 1.5,
    musicRate: 32000       // music is decoded at 32 kHz mono to keep memory low on the Fire (about 20 MB)
  };
  const manifest = window.MW_AUDIO || { voice: {}, effects: {}, music: null };
  A.manifest = manifest;

  let ctx = null, voiceBus = null, sfxBus = null, musicUser = null, musicDuck = null;
  const buffers = {};
  const waiting = {};
  const failed = [];
  let unlocked = false;

  function dbToGain(db) { return Math.pow(10, db / 20); }

  // ---------------------------------------------------------------- loading and decoding
  // Files are fetched and decoded straight away (before the first tap) in offline contexts,
  // which browsers allow without a tap. The decoded buffers then play in the real context.
  const dec = {};
  function decoder(rate) {
    if (!dec[rate]) {
      const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      dec[rate] = new OAC(1, 1, rate);
    }
    return dec[rate];
  }
  function decode(bytes, rate) {
    return new Promise(function (resolve, reject) {
      const p = decoder(rate).decodeAudioData(bytes, resolve, reject);
      if (p && p.catch) p.catch(reject);
    });
  }
  let queue = Promise.resolve();
  A.load = function (key) {
    if (buffers[key]) return Promise.resolve(buffers[key]);
    if (waiting[key]) return waiting[key];
    const rate = key === 'music' ? CONFIG.musicRate : 44100;
    const bytes = fetch(CONFIG.base + key + '.mp3').then(function (r) {
      if (!r.ok) throw new Error(r.status + ' for ' + key);
      return r.arrayBuffer();
    });
    // decode one file at a time so the Fire stays smooth
    waiting[key] = queue = queue.then(function () { return bytes; }).then(function (b) { return decode(b, rate); })
      .then(function (buf) { buffers[key] = buf; return buf; })
      .catch(function (err) { failed.push(key); MW.log('audio-fail', key + ': ' + err); delete waiting[key]; return null; });
    return waiting[key];
  };
  A.ready = function (keys) { return Promise.all(keys.map(A.load)); };
  A.preloadAll = function () {
    const keys = Object.keys(manifest.effects || {}).map(function (k) { return 'sfx/' + k; })
      .concat(Object.keys(manifest.voice || {}).map(function (k) { return 'voice/' + k; }));
    const all = A.ready(keys);
    if (manifest.music) all.then(function () { return A.load('music'); }).then(function () { if (unlocked) A.music.start(); });
    return all;
  };
  A.status = function () {
    const total = Object.keys(manifest.voice || {}).length + Object.keys(manifest.effects || {}).length + (manifest.music ? 1 : 0);
    return { state: ctx ? ctx.state : 'not started', rate: ctx ? ctx.sampleRate : null,
      decoded: Object.keys(buffers).length, total: total, failed: failed.slice() };
  };
  A.has = function (key) { return !!buffers[key]; };

  // ---------------------------------------------------------------- the first tap
  A.unlock = function () {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return 'no web audio';
    if (!ctx) {
      try { ctx = new AC(); } catch (e) { MW.log('audio-fail', 'context: ' + e.message); return 'failed'; }
      voiceBus = ctx.createGain(); voiceBus.connect(ctx.destination);
      sfxBus = ctx.createGain(); sfxBus.connect(ctx.destination);
      musicDuck = ctx.createGain(); musicDuck.gain.value = dbToGain(CONFIG.musicDb); musicDuck.connect(ctx.destination);
      musicUser = ctx.createGain(); musicUser.gain.value = 0; musicUser.connect(musicDuck);
    }
    if (ctx.state === 'suspended') { const p = ctx.resume(); if (p && p.catch) p.catch(function () {}); }
    if (!unlocked) {
      unlocked = true;
      if (buffers.music) A.music.start();
    }
    return ctx.state;
  };
  A.running = function () { return !!ctx && ctx.state === 'running'; };
  A.now = function () { return ctx ? ctx.currentTime : 0; };

  // Pause sound when the tablet hides the page; carry on when it comes back.
  document.addEventListener('visibilitychange', function () {
    if (!ctx) return;
    if (document.hidden) { ctx.suspend(); } else if (unlocked) { ctx.resume(); }
  });
  // Some tablets suspend sound after the screen sleeps: any tap wakes it.
  window.addEventListener('pointerdown', function () { if (unlocked && ctx && ctx.state === 'suspended') ctx.resume(); }, true);

  // ---------------------------------------------------------------- voice
  // A line is a list of sentences; a sentence is a list of clip ids.
  // say([['q-lets-make', 'num-end-7'], ['q-weve-got', 'num-end-3'], ['q-how-many-more']])
  const speech = { token: 0, sources: [], resolve: null, endsAt: 0, timer: 0 };
  A.say = function (sentences, opts) {
    opts = opts || {};
    A.hush();
    const token = speech.token;
    const ids = [].concat.apply([], sentences);
    MW.log('say', ids.join(' '));
    // a line that isn't recorded yet (not on the page) is skipped, so a game can be built before its recordings
    const unrecorded = ids.filter(function (id) { return !(manifest.voice || {})[id]; });
    if (unrecorded.length) { MW.log('audio-fail', 'not recorded yet: ' + unrecorded.join(', ')); return Promise.resolve(false); }
    return A.ready(ids.map(function (id) { return 'voice/' + id; })).then(function () {
      if (token !== speech.token) return false;
      if (!A.running()) return false;
      const missing = ids.filter(function (id) { return !buffers['voice/' + id]; });
      if (missing.length) { MW.log('audio-fail', 'missing ' + missing.join(', ')); return false; }
      const start = ctx.currentTime + 0.06;
      let t = start;
      const timeline = [];
      sentences.forEach(function (sent, si) {
        if (si > 0) t += CONFIG.sentenceGap;
        sent.forEach(function (id, pi) {
          if (pi > 0) t += CONFIG.pieceGap;
          const b = buffers['voice/' + id];
          const s = ctx.createBufferSource();
          s.buffer = b; s.connect(voiceBus); s.start(t);
          speech.sources.push(s);
          timeline.push({ id: id, at: t - start, dur: b.duration });
          t += b.duration;
        });
      });
      speech.endsAt = t;
      duck(true, start);
      if (opts.onStart) opts.onStart(timeline);
      return new Promise(function (resolve) {
        speech.resolve = resolve;
        const finish = function () {
          if (token !== speech.token || !speech.resolve) return;
          speech.resolve = null; speech.sources = [];
          clearTimeout(speech.timer);
          duck(false);
          resolve(true);
        };
        speech.sources[speech.sources.length - 1].onended = finish;
        // In case a browser never fires onended: check the audio clock (which stops while the tablet sleeps).
        const backstop = function () {
          if (token !== speech.token || !speech.resolve) return;
          if (ctx.state === 'running' && ctx.currentTime >= t + 0.3) finish();
          else speech.timer = setTimeout(backstop, 500);
        };
        speech.timer = setTimeout(backstop, (t - ctx.currentTime) * 1000 + 600);
      });
    });
  };
  A.hush = function () {
    speech.token++;
    speech.sources.forEach(function (s) { try { s.onended = null; s.stop(); } catch (e) {} });
    speech.sources = [];
    clearTimeout(speech.timer);
    if (ctx) duck(false);
    if (speech.resolve) { const r = speech.resolve; speech.resolve = null; r(false); }
  };
  A.speaking = function () { return !!speech.resolve; };
  // How long a line will take, in seconds (for timing pictures to the voice).
  A.lengthOf = function (sentences) {
    let t = 0;
    sentences.forEach(function (sent, si) {
      if (si > 0) t += CONFIG.sentenceGap;
      sent.forEach(function (id, pi) {
        if (pi > 0) t += CONFIG.pieceGap;
        const b = buffers['voice/' + id];
        t += b ? b.duration : ((manifest.voice[id] || {}).dur || 0.8);
      });
    });
    return t;
  };

  function duck(down, at) {
    if (!musicDuck) return;
    const g = musicDuck.gain, now = ctx.currentTime;
    g.cancelScheduledValues(now);
    g.setValueAtTime(g.value, now);
    if (down) g.setTargetAtTime(dbToGain(CONFIG.musicDuckDb), Math.max(now, (at || now) - 0.1), 0.04);
    else g.setTargetAtTime(dbToGain(CONFIG.musicDb), now + 0.15, 0.25);
  }

  // ---------------------------------------------------------------- effects
  A.sfx = function (name) {
    const b = buffers['sfx/' + name];
    MW.log('sfx', name);
    if (!b || !A.running()) return 0;
    const s = ctx.createBufferSource();
    s.buffer = b; s.connect(sfxBus); s.start();
    return b.duration;
  };

  // ---------------------------------------------------------------- music
  // "Paws in the Milky Way" loops: each copy's last 1.5 s fades (baked into the file) while the next copy starts.
  const music = { sources: [], next: 0, timer: 0, playing: false };
  A.music = {
    isOn: function () { return MW.store.get('music') !== false; },
    setOn: function (on) {
      MW.store.setMusic(on);
      MW.log('music', on ? 'on' : 'off');
      if (on) A.music.start(); else A.music.stop();
      document.dispatchEvent(new CustomEvent('mw-music', { detail: on }));
    },
    start: function (offset) {
      if (!A.music.isOn() || !ctx || !buffers.music) return false;
      if (music.playing && offset === undefined) return true;
      stopSources(0);
      const buf = buffers.music;
      const fade = (manifest.music && manifest.music.fade) || 1.5;
      let t = ctx.currentTime + 0.05, off = offset || 0;
      const plan = function () {
        const s = ctx.createBufferSource();
        s.buffer = buf; s.connect(musicUser); s.start(t, off);
        const end = t + (buf.duration - off);
        music.sources.push({ s: s, end: end });
        t = end - fade; off = 0;
        music.next = t;
      };
      plan(); plan();
      clearInterval(music.timer);
      music.timer = setInterval(function () {
        if (!ctx) return;
        music.sources = music.sources.filter(function (x) { return x.end > ctx.currentTime; });
        if (music.next - ctx.currentTime < 40) plan();
      }, 4000);
      const g = musicUser.gain, now = ctx.currentTime;
      g.cancelScheduledValues(now); g.setValueAtTime(offset ? 1 : 0, now);
      if (!offset) g.linearRampToValueAtTime(1, now + CONFIG.musicFadeIn);
      music.playing = true;
      MW.log('music', 'start ' + (offset || 0).toFixed(1));
      return true;
    },
    stop: function () {
      if (!ctx) return;
      const g = musicUser.gain, now = ctx.currentTime;
      g.cancelScheduledValues(now); g.setValueAtTime(g.value, now); g.linearRampToValueAtTime(0, now + 0.4);
      stopSources(0.45);
      music.playing = false;
    },
    // For the grown-ups check: start 6 seconds before a loop join.
    jumpToJoin: function () {
      if (!buffers.music) return false;
      const fade = (manifest.music && manifest.music.fade) || 1.5;
      return A.music.start(Math.max(0, buffers.music.duration - fade - 6));
    },
    playing: function () { return music.playing; },
    level: function () { return musicUser && musicDuck ? musicUser.gain.value * musicDuck.gain.value : 0; }
  };
  function stopSources(after) {
    clearInterval(music.timer);
    const when = ctx ? ctx.currentTime + after : 0;
    music.sources.forEach(function (x) { try { x.s.stop(when); } catch (e) {} });
    music.sources = [];
  }
})();
