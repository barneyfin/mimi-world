/* MeeMee World kit: core.
   The 1280x800 stage and its scaling, what each tablet remembers, and small helpers.
   Every other kit file adds to window.MW. */
(function () {
  'use strict';
  const MW = window.MW = window.MW || {};

  // ---------------------------------------------------------------- the stage
  // Every screen is drawn on a 1280x800 stage and scaled to fit (0.82 on the Fire, 1.0 on the Doogee).
  const stage = MW.stage = { el: null, W: 1280, H: 800, scale: 1, offX: 0, offY: 0 };
  stage.fit = function () {
    const w = window.innerWidth, h = window.innerHeight;
    stage.scale = Math.min(w / stage.W, h / stage.H);
    stage.offX = (w - stage.W * stage.scale) / 2;
    stage.offY = (h - stage.H * stage.scale) / 2;
    if (stage.el) stage.el.style.transform = 'translate(' + stage.offX + 'px,' + stage.offY + 'px) scale(' + stage.scale + ')';
  };
  stage.toStage = function (clientX, clientY) {
    return { x: (clientX - stage.offX) / stage.scale, y: (clientY - stage.offY) / stage.scale };
  };
  stage.init = function (el) {
    stage.el = el;
    stage.fit();
    window.addEventListener('resize', stage.fit);
    window.addEventListener('orientationchange', function () { setTimeout(stage.fit, 250); });
  };

  // ---------------------------------------------------------------- reduce motion
  const rm = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  MW.reduceMotion = !!(rm && rm.matches);
  if (rm && rm.addEventListener) rm.addEventListener('change', function () { MW.reduceMotion = rm.matches; });

  // ---------------------------------------------------------------- what this tablet remembers
  // One localStorage entry. Browser storage can be cleared, so this is a convenience, not a record.
  // music and settings are the world's (and MeeMee Rescue's settings, from before phase 5); answers are MeeMee
  // Rescue's; games.<id> is each newer game's own saved data (MW.store.game).
  const KEY = 'mimi-world';
  const DEFAULTS = { v: 1, music: true, settings: { check: 'tap', wholes: [2, 3, 4, 5, 6, 7, 8, 9, 10] }, answers: [], games: {} };
  let data = null;
  function load() {
    if (data) return data;
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { saved = null; }
    data = JSON.parse(JSON.stringify(DEFAULTS));
    if (saved && saved.v === 1) {
      if (typeof saved.music === 'boolean') data.music = saved.music;
      if (saved.settings) Object.assign(data.settings, saved.settings);
      if (Array.isArray(saved.answers)) data.answers = saved.answers;
      if (saved.games && typeof saved.games === 'object' && !Array.isArray(saved.games)) data.games = saved.games;
    }
    return data;
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(data)); MW.store.ok = true; } catch (e) { MW.store.ok = false; }
  }
  MW.store = {
    ok: null,
    get: function (k) { return load()[k]; },
    setting: function (k, v) {
      const s = load().settings;
      if (v === undefined) return s[k];
      s[k] = v; save(); return v;
    },
    setMusic: function (on) { load().music = !!on; save(); },
    // A game's own saved data: an object it can change freely, then MW.store.save() to keep the change.
    game: function (id) {
      const g = load().games;
      if (!g[id] || typeof g[id] !== 'object' || Array.isArray(g[id])) g[id] = {};
      return g[id];
    },
    // Forget a game's saved data (for its own "clear this tablet's progress" button).
    clearGame: function (id) { delete load().games[id]; save(); },
    save: function () { load(); save(); return MW.store.ok; },
    recordAnswer: function (a) {
      const d = load();
      d.answers.push(a);
      if (d.answers.length > 3000) d.answers.splice(0, d.answers.length - 3000);
      save();
    },
    clear: function () {
      const d = load();
      d.answers = [];
      save();
    },
    bytes: function () { try { return (localStorage.getItem(KEY) || '').length; } catch (e) { return 0; } },
    check: function () {
      try {
        localStorage.setItem(KEY + '-test', '1');
        const ok = localStorage.getItem(KEY + '-test') === '1';
        localStorage.removeItem(KEY + '-test');
        MW.store.ok = ok;
      } catch (e) { MW.store.ok = false; }
      return MW.store.ok;
    }
  };

  // ---------------------------------------------------------------- helpers
  MW.$ = function (id) { return document.getElementById(id); };
  MW.make = function (tag, cls, attrs, html) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (html !== undefined) el.innerHTML = html;
    return el;
  };
  // A tap on a button the player uses. Detected from the finger lifting on the button rather than from "click",
  // which browsers sometimes swallow right after a drag. The keyboard still works (Enter or Space).
  // Lifting the finger counts as a user gesture, so full screen and sound can start from here.
  MW.onTap = function (el, fn) {
    let down = null;
    el.addEventListener('pointerdown', function (e) {
      if (e.button > 0) return;
      down = { id: e.pointerId, x: e.clientX, y: e.clientY, t: performance.now() };
    });
    el.addEventListener('pointerup', function (e) {
      if (!down || e.pointerId !== down.id) return;
      const d = down; down = null;
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > 40 || performance.now() - d.t > 1500) return;
      const r = el.getBoundingClientRect();
      if (e.clientX < r.left - 8 || e.clientX > r.right + 8 || e.clientY < r.top - 8 || e.clientY > r.bottom + 8) return;
      if (el.disabled) return;
      fn(e);
    });
    el.addEventListener('pointercancel', function () { down = null; });
    el.addEventListener('click', function (e) { if (e.detail === 0 && !el.disabled) fn(e); });
  };
  // A copy of a drawing. Its ids (clip paths) get a number of their own, so the same drawing can be on the page twice.
  let artCopies = 0;
  MW.art = function (name) {
    const t = document.getElementById('art-' + name);
    if (!t) throw new Error('No art called ' + name);
    const el = t.content.firstElementChild.cloneNode(true);
    const named = el.querySelectorAll('[id]');
    if (named.length) {
      const n = ++artCopies, map = {};
      Array.prototype.forEach.call(named, function (e) { map[e.id] = e.id + '-' + n; e.id = map[e.id]; });
      // every reference to them: clip-path, mask, filter, fill or stroke url(#…), and <use href="#…">
      Array.prototype.forEach.call(el.querySelectorAll('*'), function (e) {
        Array.prototype.forEach.call(e.attributes, function (a) {
          if (a.value.indexOf('url(#') >= 0) {
            const v = a.value.replace(/url\(#([^)]+)\)/g, function (all, id) { return map[id] ? 'url(#' + map[id] + ')' : all; });
            if (v !== a.value) e.setAttribute(a.name, v);
          } else if ((a.name === 'href' || a.name === 'xlink:href') && a.value.charAt(0) === '#' && map[a.value.slice(1)]) {
            e.setAttribute(a.name, '#' + map[a.value.slice(1)]);
          }
        });
      });
    }
    return el;
  };
  MW.wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  MW.pick = function (list) { return list[Math.floor(Math.random() * list.length)]; };
  MW.shuffle = function (list) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  };
  MW.esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  };

  // A short log of what happened, read by the tests and the grown-ups checks.
  MW.events = [];
  MW.log = function (type, detail) {
    MW.events.push({ t: Math.round(performance.now()), type: type, detail: detail });
    if (MW.events.length > 800) MW.events.splice(0, 200);
  };
})();
