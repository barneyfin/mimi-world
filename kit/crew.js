/* MeeMee World kit: the crew (phase 4, 0.4.1).
   Moggles and Snuffles each get a job (lookout, engineer, navigator or cook) on the crew screen, by dragging the cat
   onto the job's picture: one job per cat, never the same job for both. Each tablet remembers the jobs. A cat wears its
   job as a badge on its chest on the map, the crew screen and the end screen; the game gives each job a moment.
   Layout from the design canvas's round 4 (Crew4). */
(function () {
  'use strict';
  const MW = window.MW;
  const CATS = ['moggles', 'snuffles'];
  const JOBS = ['lookout', 'engineer', 'navigator', 'cook'];
  const C = MW.crew = { CATS: CATS, JOBS: JOBS };

  // ---------------------------------------------------------------- the jobs, saved on this tablet
  C.jobs = function () {
    const saved = MW.store.setting('crew') || {};
    const out = {};
    CATS.forEach(function (c) { out[c] = JOBS.indexOf(saved[c]) >= 0 ? saved[c] : null; });
    if (out.moggles && out.moggles === out.snuffles) out.snuffles = null;    // never the same job twice
    return out;
  };
  C.save = function (jobs) { MW.store.setting('crew', { moggles: jobs.moggles || null, snuffles: jobs.snuffles || null }); };
  C.who = function (job) { const j = C.jobs(); return CATS.filter(function (c) { return j[c] === job; })[0] || null; };
  C.ready = function () { const j = C.jobs(); return CATS.every(function (c) { return !!j[c]; }); };
  // "Moggles… is the… lookout."
  C.line = function (cat, job) { return ['name-' + cat, 'is-the', 'job-' + job]; };

  // ---------------------------------------------------------------- a cat with a place for its badge
  // MW.crew.cat('moggles', 112) -> a box w wide; box.setJob('cook') puts the badge on its chest (null takes it off).
  C.cat = function (who, w) {
    const h = Math.round(w * 340 / 260);
    const box = MW.make('div', 'mw-cat', { 'data-who': who });
    box.style.width = w + 'px'; box.style.height = h + 'px';
    const body = MW.make('div', 'mw-cat-body');
    const pic = MW.art(who); pic.setAttribute('width', w); pic.setAttribute('height', h);
    body.appendChild(pic);
    box.appendChild(body);
    const b = Math.max(26, Math.round(w * 0.26));
    let badge = null;
    box.w = w; box.h = h; box.body = body;
    box.setJob = function (job) {
      if (badge) { body.removeChild(badge); badge = null; }
      box.setAttribute('data-job', job || '');
      if (!job) return;
      badge = MW.art('badge-' + job);
      badge.setAttribute('width', b); badge.setAttribute('height', b);
      badge.setAttribute('class', 'mw-badge');
      badge.style.left = Math.round(w * 130 / 260 - b / 2) + 'px';
      badge.style.top = Math.round(h * 238 / 340 - b / 2) + 'px';
      body.appendChild(badge);
    };
    box.hop = function (delay) {
      setTimeout(function () { body.classList.remove('is-hop'); void body.getBoundingClientRect(); body.classList.add('is-hop'); }, delay || 0);
    };
    return box;
  };

  // ---------------------------------------------------------------- the crew screen
  const L = MW.LAYOUT.crew = {
    ship: { x: 530, y: 40, w: 220 },
    deck: { moggles: { x: 220, y: 368 }, snuffles: { x: 380, y: 368 } },     // where each cat's feet go before it has a job
    stations: [{ job: 'lookout', x: 40 }, { job: 'engineer', x: 350 }, { job: 'navigator', x: 660 }, { job: 'cook', x: 970 }],
    top: 420, w: 270, h: 340, disc: 124, pic: 98, spotY: 726,
    cat: 136, foot: 173,          // a cat's width, and how far below the top of its picture its feet are
    dropY: 430,                   // a cat let go with its middle below this line takes the nearest job
    grab: 92                      // the cats are big: a finger anywhere on one picks it up
  };
  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }

  // opts: { speak(lines), onHome(), enabled() }
  C.screen = function (parent, opts) {
    const scr = {};
    const art = MW.art('crew'); art.setAttribute('class', 'mw-layer');
    parent.appendChild(art);
    const ship = MW.art('pod');
    ship.setAttribute('width', L.ship.w); ship.setAttribute('height', Math.round(L.ship.w * 430 / 400));
    Array.prototype.forEach.call(ship.querySelectorAll('[data-face]'), function (g) { g.style.display = g.getAttribute('data-face') === 'thinking' ? '' : 'none'; });
    const shipBox = place(MW.make('div', 'mw-abs mw-map-crew'), L.ship.x, L.ship.y);
    shipBox.appendChild(ship);
    parent.appendChild(shipBox);

    const stations = L.stations.map(function (s) {
      const el = place(MW.make('div', 'mw-station mw-abs', { 'data-job': s.job }), s.x, L.top);
      el.style.width = L.w + 'px'; el.style.height = L.h + 'px';
      const disc = place(MW.make('div', 'mw-station-disc mw-abs'), (L.w - L.disc) / 2, 14);
      const pic = MW.art('job-' + s.job); pic.setAttribute('width', L.pic); pic.setAttribute('height', L.pic);
      disc.appendChild(pic);
      el.appendChild(disc);
      const sy = L.spotY - L.top;
      el.insertAdjacentHTML('beforeend', '<svg class="mw-station-spot" width="' + L.w + '" height="' + L.h + '" viewBox="0 0 ' + L.w + ' ' + L.h + '" aria-hidden="true">'
        + '<ellipse class="f-mint mw-spot-fill" cx="' + (L.w / 2) + '" cy="' + sy + '" rx="92" ry="17"/>'
        + '<ellipse class="s-mint mw-spot-rim" fill="none" stroke-width="3" stroke-linecap="round" cx="' + (L.w / 2) + '" cy="' + sy + '" rx="92" ry="17"/></svg>');
      parent.appendChild(el);
      return { job: s.job, cx: s.x + L.w / 2, el: el };
    });

    const cats = {};
    CATS.forEach(function (who) {
      const box = C.cat(who, L.cat);
      box.classList.add('mw-crew-cat');
      parent.appendChild(box);
      const c = { el: box, who: who, x: 0, y: 0, size: 80, draggable: true };
      c.moveTo = function (x, y, size, animate) {
        c.x = x; c.y = y;
        box.classList.toggle('is-moving', !!animate && !MW.reduceMotion);
        box.style.transform = 'translate3d(' + (x - box.w / 2) + 'px,' + (y - box.h / 2) + 'px,0)';
      };
      c.lift = function (on) { box.classList.toggle('is-lifted', !!on); };
      cats[who] = c;
    });
    scr.cats = cats; scr.stations = stations;

    const nav = MW.shell.buttons(parent, ['home', 'music', 'hear'], {
      home: function () { if (opts.onHome) opts.onHome(); },
      hear: function () { scr.intro(); }
    });

    function feet(who, job) {
      if (!job) return L.deck[who];
      const s = stations.filter(function (x) { return x.job === job; })[0];
      return { x: s.cx, y: L.spotY };
    }
    function layout(animate) {
      const jobs = C.jobs();
      CATS.forEach(function (who) {
        const f = feet(who, jobs[who]), c = cats[who];
        c.moveTo(f.x, f.y - L.foot + c.el.h / 2, 80, animate);
        c.el.setJob(jobs[who]);
      });
      stations.forEach(function (s) {
        s.el.classList.toggle('is-taken', CATS.some(function (w) { return jobs[w] === s.job; }));
      });
      nav.home.classList.toggle('mw-pulse', C.ready());       // the crew are ready: back to the map
    }
    scr.layout = layout;

    function onDrop(c, x, y, cancelled) {
      if (cancelled || (opts.enabled && !opts.enabled())) { layout(true); return; }
      const jobs = C.jobs();
      const was = jobs[c.who];
      const other = CATS.filter(function (w) { return w !== c.who; })[0];
      let job = null;
      if (y > L.dropY) {
        let best = Infinity;
        stations.forEach(function (s) { const d = Math.abs(x - s.cx); if (d < best) { best = d; job = s.job; } });
      }
      let swapped = false;
      if (job && job !== was && jobs[other] === job) { jobs[other] = was; swapped = true; }   // the two cats swap places
      jobs[c.who] = job;
      C.save(jobs);
      layout(true);
      MW.log('crew', c.who + ' ' + (job || 'no job') + (swapped ? ', ' + other + ' ' + (jobs[other] || 'no job') : ''));
      if (!job) { if (was) MW.audio.sfx('whoosh'); return; }
      MW.audio.sfx('pop');
      c.el.hop(260);
      const lines = [C.line(c.who, job)];
      if (swapped && jobs[other]) lines.push(C.line(other, jobs[other]));
      if (C.ready() && (job !== was || swapped)) lines.push(['crew-ready']);   // not again for a tap on a cat
      if (opts.speak) opts.speak(lines);
    }
    scr.dragger = MW.dragger(parent, {
      counters: function () { return CATS.map(function (w) { return cats[w]; }); },
      enabled: function () { return !opts.enabled || opts.enabled(); },
      onDrop: onDrop,
      grab: L.grab
    });

    // what the screen says when it opens, and again on Hear-again
    scr.intro = function () {
      const jobs = C.jobs();
      if (C.ready()) return opts.speak(CATS.map(function (w) { return C.line(w, jobs[w]); }));
      return opts.speak([['crew-jobs']]);
    };
    scr.enter = function () { layout(false); scr.intro(); };
    layout(false);
    return scr;
  };
})();
