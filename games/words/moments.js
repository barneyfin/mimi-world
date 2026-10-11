/* MeeMee Rockets: the crew's job moments (0.6.0; the design canvas's round 7, board Moments7, as drawn).
   A cat with a job appears briefly at its own moment, with no words, never over the word being found or built:
     lookout    as a round starts, peeks up from the bottom right of Find with the telescope (below Scruffles's ship);
     engineer   on a right tap in Find, pops up under the launch pad below that rocket and taps its clamp with the spanner;
     navigator  as the star lights after the launch, holds up the star map on the cargo tray and points the way to the next
                star (the dotted route goes behind the rocket, so it never crosses the word);
     cook       on the end screen, brings a pan of fish for the MeeMee in the little rockets.
   A job no cat has has no moment (MW.crew.who). With reduce motion the cats fade in and out instead of moving (the kit's
   moment styles), and the spanner doesn't swing.
   Positions are stage px from the board (each of its panels is a 1280 x 800 stage drawn at half size). MeeMee Rescue's
   moments.js is the example this follows; Rockets has its own, because its screens are its own. */
(function () {
  'use strict';
  const MW = window.MW;

  const L = MW.LAYOUT.wordsMoments = {
    // a 210-wide cat facing left, its head and the telescope showing above the stage's bottom edge
    lookout: { x: 1000, y: 640, w: 210, scope: { x: 85, y: 2, size: 143 }, clip: { x: 960, w: 320 } },
    // under the pad below the tapped rocket (dx from its centre line); the spanner held up to the clamp, turned 40 degrees
    engineer: { dx: -83, y: 676, w: 160, spanner: { dx: 29, y: 620, size: 84, turn: -40 } },
    // standing on the cargo tray, the star map held up; the route starts at the top of the map
    navigator: { x: 600, y: 470, w: 140, map: { x: 650, y: 440, size: 96 }, from: { dx: 50, dy: 12 }, below: 24 },
    // beside the little rockets, facing them, the pan held out to the last one
    cook: { x: 880, y: 560, w: 170, pan: { x: 800, y: 630, size: 120 } }
  };
  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }
  function size(svg, s) { svg.setAttribute('width', s); svg.setAttribute('height', s); return svg; }
  function drop(el, ms) { setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, ms); }
  function layer(parent, before) {
    const l = MW.make('div', 'mw-layer mw-fill mw-moments');
    if (before) parent.insertBefore(l, before); else parent.appendChild(l);
    return l;
  }

  // opts: { find: Find's screen, findBefore: the layer the lookout and engineer go under (in front of the rockets and
  //         the pad), build: Build's screen, routeBefore: the rocket's layer (the route goes behind it), buildBefore: the
  //         layer the navigator goes under (in front of the tray and its tiles), stars: Build's MW.stars,
  //         end: the end screen, endBefore: what the cook goes under (the Play button) }
  MW.wordsMoments = function (opts) {
    const m = {};
    let timers = [];
    const findLayer = layer(opts.find, opts.findBefore);
    const routeLayer = layer(opts.build, opts.routeBefore);
    const buildLayer = layer(opts.build, opts.buildBefore);
    const endLayer = layer(opts.end, opts.endBefore);
    let peek = null;

    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
    function catFor(job, w) {
      const who = MW.crew.who(job);
      if (!who) return null;
      const c = MW.crew.cat(who, w);
      c.setJob(job);
      return c;
    }
    // a box w x h at (x, y) whose drawings face the other way (the board's cats facing left)
    function flipBox(x, y, w, h) {
      const f = place(MW.make('div', 'words-moment-flip'), x, y);
      f.style.width = w + 'px'; f.style.height = h + 'px';
      return f;
    }
    function show(el) { void el.getBoundingClientRect(); el.classList.add('is-shown'); }
    function hide(el, after) { later(function () { el.classList.remove('is-shown'); drop(el, 400); }, after); }

    // ---------------------------------------------------------------- lookout (Find, as a round starts)
    m.lookoutUp = function () {
      m.lookoutDown(true);
      const k = L.lookout, cat = catFor('lookout', k.w);
      if (!cat) return false;
      // a box clipped at the stage's bottom edge, the cat rising inside it (a fade with reduce motion)
      const box = place(MW.make('div', 'mw-moment mw-peek', { 'data-moment': 'lookout' }), k.clip.x, k.y);
      box.style.width = k.clip.w + 'px'; box.style.height = (MW.stage.H - k.y) + 'px';
      const inner = MW.make('div', 'mw-peek-inner');
      const flip = flipBox(k.x - k.clip.x, 0, k.w, cat.h);
      flip.appendChild(cat);
      const scope = place(MW.make('div', 'words-moment-held'), k.scope.x, k.scope.y);
      scope.appendChild(size(MW.art('held-telescope'), k.scope.size));
      flip.appendChild(scope);
      inner.appendChild(flip);
      box.appendChild(inner);
      findLayer.appendChild(box);
      peek = box;
      show(box);
      MW.log('moment', 'lookout');
      return true;
    };
    m.lookoutShown = function () { return !!peek; };
    m.lookoutDown = function (now) {
      if (!peek) return;
      const b = peek; peek = null;
      if (now) { drop(b, 0); return; }
      b.classList.remove('is-shown');
      drop(b, 600);
    };

    // ---------------------------------------------------------------- engineer (Find, a right tap)
    // cx: the tapped rocket's centre line
    m.engineer = function (cx) {
      const k = L.engineer, cat = catFor('engineer', k.w);
      if (!cat) return false;
      m.lookoutDown();                                        // a quick first answer: the lookout makes way
      const box = place(MW.make('div', 'mw-moment mw-peek', { 'data-moment': 'engineer' }), cx + k.dx, k.y);
      box.style.width = k.w + 'px'; box.style.height = (MW.stage.H - k.y) + 'px';
      const inner = MW.make('div', 'mw-peek-inner');
      inner.appendChild(cat);
      box.appendChild(inner);
      // the spanner: it pops up (the kit's moment style), turned as on the board, and swings from its ring to tap
      const sp = place(MW.make('div', 'mw-moment mw-moment-pop', { 'data-moment': 'engineer-spanner' }), cx + k.spanner.dx, k.spanner.y);
      const turn = MW.make('div', 'words-spanner');
      turn.style.transform = 'rotate(' + k.spanner.turn + 'deg)';
      const swing = MW.make('div', 'words-spanner-swing');
      swing.appendChild(size(MW.art('job-engineer'), k.spanner.size));
      turn.appendChild(swing);
      sp.appendChild(turn);
      findLayer.appendChild(box);
      findLayer.appendChild(sp);
      show(box);
      later(function () { show(sp); }, 200);
      later(function () { swing.classList.add('is-tapping'); }, 450);   // two taps on the clamp
      hide(box, 2600); hide(sp, 2600);
      MW.log('moment', 'engineer ' + Math.round(cx));
      return true;
    };

    // ---------------------------------------------------------------- navigator (Build, as the star lights)
    // next: the star to point at, or null after the last word
    m.navigator = function (next) {
      const k = L.navigator, cat = catFor('navigator', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-moment-pop', { 'data-moment': 'navigator' }), k.x, k.y);
      box.style.width = k.w + 'px'; box.style.height = cat.h + 'px';
      box.appendChild(cat);
      const mp = place(MW.make('div', 'mw-moment mw-moment-pop words-moment-held', { 'data-moment': 'navigator-map' }), k.map.x, k.map.y);
      mp.appendChild(size(MW.art('job-navigator'), k.map.size));
      const star = next !== null && next !== undefined ? opts.stars.el.children[next] : null;
      if (star) {
        // a dotted route from the top of the map to just below the star (stage px), behind the rocket
        const s = MW.stage.scale || 1, box0 = opts.stars.el.getBoundingClientRect(), r = star.getBoundingClientRect();
        const sx = Math.round(opts.stars.el.offsetLeft + (r.left - box0.left + r.width / 2) / s);
        const sy = Math.round(opts.stars.el.offsetTop + (r.bottom - box0.top) / s + k.below);
        const fx = k.map.x + k.from.dx, fy = k.map.y + k.from.dy;
        const route = MW.make('div', 'mw-layer mw-fill mw-route mw-moment-pop', { 'data-moment': 'navigator-route' });
        route.innerHTML = '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true"><path class="s-mint" fill="none" stroke-width="6" '
          + 'stroke-dasharray="2 14" stroke-linecap="round" d="M' + fx + ' ' + fy + ' Q ' + (fx - 10) + ' ' + Math.round(sy + 0.38 * (fy - sy)) + ' ' + sx + ' ' + sy + '"/></svg>';
        routeLayer.appendChild(route);
        later(function () { show(route); }, 250);
        hide(route, 1900);
      }
      buildLayer.appendChild(box);
      buildLayer.appendChild(mp);
      show(box);
      later(function () { show(mp); }, 120);
      hide(box, 2100); hide(mp, 2100);
      MW.log('moment', 'navigator ' + (star ? next : 'end'));
      return true;
    };

    // ---------------------------------------------------------------- cook (the end screen)
    m.cook = function () {
      const k = L.cook, cat = catFor('cook', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-moment-pop', { 'data-moment': 'cook' }), k.x, k.y);
      box.style.width = k.w + 'px'; box.style.height = cat.h + 'px';
      const flip = flipBox(0, 0, k.w, cat.h);
      flip.appendChild(cat);
      box.appendChild(flip);
      const pan = place(MW.make('div', 'mw-moment mw-cook-pan', { 'data-moment': 'cook-pan' }), k.pan.x, k.pan.y);
      pan.appendChild(size(MW.art('job-cook'), k.pan.size));
      endLayer.appendChild(box);
      endLayer.appendChild(pan);
      show(box);
      later(function () { show(pan); MW.sparkles(endLayer, k.pan.x + k.pan.size / 2, k.pan.y + k.pan.size / 2, 70); }, 250);
      MW.log('moment', 'cook');
      return true;
    };

    // the in-round cats leave when the next word starts
    m.settle = function () {
      m.lookoutDown();
      [findLayer, routeLayer, buildLayer].forEach(function (l) {
        Array.prototype.forEach.call(l.querySelectorAll('.is-shown'), function (el) { el.classList.remove('is-shown'); drop(el, 400); });
      });
    };
    // leaving, or a new round: everything goes at once
    m.clear = function () {
      timers.forEach(clearTimeout); timers = [];
      peek = null;
      [findLayer, routeLayer, buildLayer, endLayer].forEach(function (l) { l.innerHTML = ''; });
    };
    m.layers = { find: findLayer, route: routeLayer, build: buildLayer, end: endLayer };
    return m;
  };
})();
