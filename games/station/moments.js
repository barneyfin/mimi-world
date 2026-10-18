/* MeeMee Station: the crew's job moments (0.9.0). Take MeeMee Home's four (games/takehome/moments.js is the example this
   follows), at the same points in a round. The commander isn't a moment here: it stands on the deck (step 1) or at the
   track's right-hand end (steps 2 and 3) all round, and smiles on each right answer (game.js). A cat with any other job
   appears briefly at its own moment, with no words, never over the station, the deck's MeeMee, the hull modules, the
   berth, the number sentence or the commander. Where Take MeeMee Home's place would be over one of them, it moves clear:
     lookout    as a round starts, spots the station. Step 1: it rises from the stage's foot below the station, left of
                the deck (Take MeeMee Home's rose from behind its home planet, where the deck now is), mirrored, so it
                faces the station (its telescope points left, roughly level). Steps 2 and 3: it peeks up from behind
                the number track, as in Take MeeMee Home, but further left (the commander stands at the track's
                right-hand end), mirrored to face the station. It ducks 1.8 s into the first question, and at once on
                a right answer, so it is never up with the number sentence;
     engineer   on a right answer, gives a tap with the spanner while the ship's lights flash. Step 2: Take MeeMee
                Home's place, by the ship's left fin (a few px lower, clear of the station's right wing). Steps 1 and
                3: the station's right wing (step 1) and the hull modules' right end (step 3) are where it stood, and
                there is no room by the ship clear of the ship and the commander, so it stands just under the
                picture's right-hand end instead, a little smaller (110 wide, to fit the room there): step 1 under
                the station, left of the deck and above where the sentence shows; step 3 under the berth's right end,
                left of the ship's fin. Never mirrored;
     navigator  as a star turns peach, holds up the star map and points to the next one. Take MeeMee Home's place
                under the stars is over the station in steps 1 and 2 and the whole's hull module in step 3, so it
                stands a little further right, under the stars' right end, above the ship's dome;
     commander  on the end screen, the radio grows in and calls (three arcs from its aerial) at the commander's place,
                exactly as Take MeeMee Home's (0.9.0, part A).
   A job no cat has has no moment. With reduce motion the cats fade in and out instead of moving (the kit's moment
   styles). */
(function () {
  'use strict';
  const MW = window.MW;

  const SCOPE = { x: 89, y: 2, size: 150 };
  const L = MW.LAYOUT.stationMoments = {
    lookout: {
      // step 1: from the stage's foot, between the grown-ups lock's corner and the deck (724); mirrored
      aboard: { x: 420, y: 548, w: 220, box: 250, scope: SCOPE, flip: true },
      // steps 2 and 3: behind the track (its top 694 hides the cat's lower half), left of the commander (1110); mirrored
      track: { x: 856, y: 519, w: 220, show: 175, box: 250, scope: SCOPE, flip: true }
    },
    engineer: {
      more: { x: 700, y: 326, w: 140, spanner: { x: 100, y: 84, size: 88 } },                 // by the ship's left fin
      // under the picture's right-hand end, 110 wide (the spanner in proportion): step 1 under the station (its foot
      // 505), left of the deck (724), above the sentence (700); step 3 under the berth's right end, clear of the hint's
      // small station (679, while it fades) and below the ship (500)
      aboard: { x: 545, y: 530, w: 110, spanner: { x: 79, y: 66, size: 69 } },
      numbers: { x: 700, y: 530, w: 110, spanner: { x: 79, y: 66, size: 69 } }
    },
    navigator: { x: 784, y: 92, w: 120, map: { x: 64, y: 50, size: 80 } },                     // under the stars' right end
    // end screen: the radio's box (Take MeeMee Home's commander place), its call rising above it; never flipped
    commander: { size: 104, moggles: { x: 254, y: 494 }, snuffles: { x: 770, y: 494 } }
  };
  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }
  function size(svg, s) { svg.setAttribute('width', s); svg.setAttribute('height', s); return svg; }
  function drop(el, ms) { setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, ms); }

  // opts: { game: the game screen, lowBefore: what the lookout goes behind (the game's scene; the number track comes
  //         later, so it is behind that too), over: the layer the engineer and navigator go under (in front of the
  //         ship), stars: MW.stars on the game screen, end: the end screen, endCats: { moggles: box, snuffles: box } }
  MW.stationMoments = function (opts) {
    const m = {};
    let timers = [];
    const low = MW.make('div', 'mw-layer mw-fill mw-moments');       // behind the scene and the track: the lookout
    opts.game.insertBefore(low, opts.lowBefore);
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
    // step: 'aboard' (from the stage's foot below the station), 'more' or 'numbers' (behind the number track)
    m.lookoutUp = function (step) {
      m.lookoutDown(true);
      const at = step === 'aboard' ? 'aboard' : 'track', k = L.lookout[at], cat = catFor('lookout', k.w);
      if (!cat) return false;
      const box = place(MW.make('div', 'mw-moment mw-peek', { 'data-moment': 'lookout' }), k.x, k.y);
      box.style.width = k.box + 'px'; box.style.height = (k.show || MW.stage.H - k.y) + 'px';
      if (k.flip) box.classList.add('station-peek-flip');
      const inner = MW.make('div', 'mw-peek-inner');
      inner.appendChild(cat);
      const scope = place(size(MW.art('held-telescope'), k.scope.size), k.scope.x, k.scope.y);
      scope.setAttribute('class', 'mw-held-scope');
      inner.appendChild(scope);
      box.appendChild(inner);
      low.appendChild(box);
      peek = box;
      show(box);
      MW.log('moment', 'lookout ' + at);
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

    // ---------------------------------------------------------------- engineer
    m.engineer = function (step) {
      const k = L.engineer[step] || L.engineer.more, cat = catFor('engineer', k.w);
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
      MW.log('moment', 'engineer ' + step);
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

    // ---------------------------------------------------------------- commander (end screen)
    // The kit's commander-call, exactly as Take MeeMee Home's (0.9.0, part A): the radio grows in at the commander's
    // place (its 104 box), with its call, three arcs from the aerial, rising above it: the drawing is 104 wide and 1.42
    // times as tall
    m.commander = function () {
      const who = MW.crew.who('commander');
      if (!who) return false;
      const k = L.commander, at = k[who], h = Math.round(k.size * 1.42);
      const call = place(MW.make('div', 'mw-moment mw-commander-call', { 'data-moment': 'commander' }), at.x, at.y - (h - k.size));
      call.style.width = k.size + 'px'; call.style.height = h + 'px';
      const art = MW.art('commander-call'); art.setAttribute('width', k.size); art.setAttribute('height', h);
      call.appendChild(art);
      endLayer.appendChild(call);
      show(call);
      if (opts.endCats && opts.endCats[who]) opts.endCats[who].hop(0);
      MW.sparkles(endLayer, at.x + k.size / 2, at.y + k.size / 2, 70);
      MW.log('moment', 'commander');
      return true;
    };

    // the in-round cats leave when the next question starts
    m.settle = function () {
      Array.prototype.forEach.call(high.querySelectorAll('.is-shown'), function (el) { el.classList.remove('is-shown'); drop(el, 400); });
    };
    // leaving, or a new round: everything goes at once
    m.clear = function () {
      timers.forEach(clearTimeout); timers = [];
      peek = null;
      [low, high, endLayer].forEach(function (l) { l.innerHTML = ''; });
    };
    return m;
  };
})();
