/* MeeMee Rescue: the crew's job moments (phase 4, 0.4.1; the design canvas's round 4, Moments4).
   A cat with a job appears briefly at its own moment, with no words, never over the diagram or the tray:
     lookout    as a round starts, peeks over the asteroid with the telescope and spots the MeeMee;
     engineer   on a right answer, gives the ship a tap with the spanner while the lights flash;
     navigator  as a star turns peach, holds up the star map and points to the next one;
     cook       on the end screen, brings fish for the rescued MeeMee.
   A job no cat has has no moment. With reduce motion the cats fade in and out instead of moving. */
(function () {
  'use strict';
  const MW = window.MW;

  const L = MW.LAYOUT.moments = {
    lookout: { x: 690, y: 390, w: 220, show: 175, box: 250, scope: { x: 89, y: 2, size: 150 } },   // behind the asteroid
    engineer: { x: 700, y: 318, w: 140, spanner: { x: 100, y: 84, size: 88 } },                     // by the ship's left fin
    navigator: { x: 686, y: 124, w: 120, map: { x: 64, y: 50, size: 80 } },                         // under the stars
    cook: { size: 104, moggles: { x: 254, y: 494, flip: true }, snuffles: { x: 770, y: 494, flip: false } }   // end screen
  };
  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }
  function size(svg, s) { svg.setAttribute('width', s); svg.setAttribute('height', s); return svg; }
  function drop(el, ms) { setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, ms); }

  // opts: { game: the game screen, tray: the asteroid's element, over: the layer the moments go under,
  //         stars: MW.stars on the game screen, end: the end screen, endCats: { moggles: box, snuffles: box } }
  MW.moments = function (opts) {
    const m = {};
    let timers = [];
    const low = MW.make('div', 'mw-layer mw-fill mw-moments');       // behind the asteroid: the lookout
    opts.game.insertBefore(low, opts.tray);
    const high = MW.make('div', 'mw-layer mw-fill mw-moments');      // over the ship: the engineer and the navigator
    opts.game.insertBefore(high, opts.over);
    const endLayer = MW.make('div', 'mw-layer mw-fill mw-moments');
    opts.end.appendChild(endLayer);
    let peek = null;

    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
    function catFor(job, w) {
      const who = MW.crew.who(job);
      if (!who) return null;
      const c = MW.crew.cat(who, w);
      c.setJob(job);
      return c;
    }
    function show(el) { void el.getBoundingClientRect(); el.classList.add('is-shown'); }
    function hide(el, after) { later(function () { el.classList.remove('is-shown'); drop(el, 400); }, after); }

    // ---------------------------------------------------------------- lookout
    m.lookoutUp = function () {
      m.lookoutDown(true);
      const k = L.lookout, cat = catFor('lookout', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-peek', { 'data-moment': 'lookout' }), k.x, k.y);
      box.style.width = k.box + 'px'; box.style.height = k.show + 'px';
      const inner = MW.make('div', 'mw-peek-inner');
      inner.appendChild(cat);
      const scope = place(size(MW.art('held-telescope'), k.scope.size), k.scope.x, k.scope.y);
      scope.setAttribute('class', 'mw-held-scope');
      inner.appendChild(scope);
      box.appendChild(inner);
      low.appendChild(box);
      peek = box;
      show(box);
      MW.log('moment', 'lookout');
      return true;
    };
    m.lookoutDown = function (now) {
      if (!peek) return;
      const b = peek; peek = null;
      if (now) { drop(b, 0); return; }
      b.classList.remove('is-shown');
      drop(b, 600);
    };

    // ---------------------------------------------------------------- engineer
    m.engineer = function () {
      const k = L.engineer, cat = catFor('engineer', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-moment-pop', { 'data-moment': 'engineer' }), k.x, k.y);
      box.appendChild(cat);
      const sp = MW.make('div', 'mw-spanner');
      place(sp, k.spanner.x, k.spanner.y);
      sp.appendChild(size(MW.art('job-engineer'), k.spanner.size));
      box.appendChild(sp);
      high.appendChild(box);
      show(box);
      later(function () { sp.classList.add('is-tapping'); }, 250);           // two taps on the hull
      hide(box, 3700);                                                       // gone as the lights stop (about 4 s)
      MW.log('moment', 'engineer');
      return true;
    };

    // ---------------------------------------------------------------- navigator
    // next: the star to point at (0 to 4), or null after the last question
    m.navigator = function (next) {
      const k = L.navigator, cat = catFor('navigator', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-moment-pop', { 'data-moment': 'navigator' }), k.x, k.y);
      box.appendChild(cat);
      const mp = place(MW.make('div', 'mw-star-map'), k.map.x, k.map.y);
      mp.appendChild(size(MW.art('job-navigator'), k.map.size));
      box.appendChild(mp);
      const star = next !== null && next !== undefined ? opts.stars.el.children[next] : null;
      if (star) {
        // a dotted route from the top of the map to the star (positions on the 1280 x 800 stage)
        const k2 = MW.stage.scale || 1, box0 = opts.stars.el.getBoundingClientRect(), r = star.getBoundingClientRect();
        const sx = opts.stars.el.offsetLeft + (r.left - box0.left + r.width / 2) / k2;
        const sy = opts.stars.el.offsetTop + (r.bottom - box0.top) / k2 + 4;
        const fx = k.x + k.map.x + k.map.size * 0.62, fy = k.y + k.map.y + 6;
        const route = MW.make('div', 'mw-layer mw-fill mw-route');
        route.innerHTML = '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true"><path class="s-mint" fill="none" stroke-width="5" '
          + 'stroke-dasharray="2 14" stroke-linecap="round" d="M' + fx + ' ' + fy + ' Q ' + ((fx + sx) / 2 + 30) + ' ' + Math.min(fy, sy) + ' ' + sx + ' ' + sy + '"/></svg>';
        route.classList.add('mw-moment-pop');
        high.appendChild(route);
        later(function () { show(route); }, 250);
        hide(route, 1900);
      }
      high.appendChild(box);
      show(box);
      hide(box, 2100);
      MW.log('moment', 'navigator ' + (star ? next : 'end'));
      return true;
    };

    // ---------------------------------------------------------------- cook (end screen)
    m.cook = function () {
      const who = MW.crew.who('cook');
      if (!who) return false;
      const k = L.cook, at = k[who];
      const pan = place(MW.make('div', 'mw-moment mw-cook-pan' + (at.flip ? ' is-flipped' : ''), { 'data-moment': 'cook' }), at.x, at.y);
      pan.appendChild(size(MW.art('job-cook'), k.size));
      endLayer.appendChild(pan);
      show(pan);
      if (opts.endCats && opts.endCats[who]) opts.endCats[who].hop(0);
      MW.sparkles(endLayer, at.x + k.size / 2, at.y + k.size / 2, 70);
      MW.log('moment', 'cook');
      return true;
    };

    // the in-round cats leave when the next question starts
    m.settle = function () {
      Array.prototype.forEach.call(high.querySelectorAll('.is-shown'), function (el) { el.classList.remove('is-shown'); drop(el, 400); });
    };
    // leaving: everything goes at once
    m.clear = function () {
      timers.forEach(clearTimeout); timers = [];
      peek = null;
      [low, high, endLayer].forEach(function (l) { l.innerHTML = ''; });
    };
    return m;
  };
})();
