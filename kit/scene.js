/* MeeMee World kit: the pieces of a game screen.
   The part–whole diagram (counting look, and the numbers look of MeeMee Rescue's numbers mode), the asteroid tray, the
   number track, Scruffles's pod, progress stars, the equation, sparkles and hint ghosts.
   Positions follow the design system's GameScreen and NumbersMode (1280x800 stage). */
(function () {
  'use strict';
  const MW = window.MW;

  const L = MW.LAYOUT = {
    whole: { x: 380, y: 205, r: 115, k: 0.9 },
    left: { x: 210, y: 470, r: 125, k: 1 },
    right: { x: 550, y: 470, r: 125, k: 1 },
    pillTop: 612,
    pod: { x: 830, y: 70, w: 400 },
    tray: { x: 745, y: 515 },
    traySlots: [],
    equation: { x: 180, y: 700, w: 400, h: 80 },
    stars: { x: 517, y: 34, cx: 640 },     // x: the left edge of five stars; cx: the middle, for MW.stars(…, { centre: true })
    dropSlack: 22,            // a drop this far outside a circle's rim still counts as inside
    // numbers mode (0.6.0): the numbered MeeMee in a circle (the whole's drawn at 0.86), and the number track along the
    // bottom: tiles 0 to 10, 84 across, 94 apart from x 128, their tops at 686, each picked up in a 120 box
    numbered: { whole: 0.86, part: 1 },
    track: { x: 128, top: 686, step: 94, tile: 84, grab: 120, rail: { x: 114, y: 674 }, away: 140 }
  };
  for (let row = 0; row < 2; row++) for (let i = 0; i < 5; i++) L.traySlots.push({ x: L.tray.x + 82 + i * 94, y: L.tray.y + (row ? 180 : 85) });

  function abs(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }

  // ---------------------------------------------------------------- part–whole diagram
  MW.diagram = function (parent) {
    const d = {};
    const svgNS = 'http://www.w3.org/2000/svg';
    const lines = document.createElementNS(svgNS, 'svg');
    lines.setAttribute('class', 'mw-layer'); lines.setAttribute('width', '1280'); lines.setAttribute('height', '800');
    lines.setAttribute('viewBox', '0 0 1280 800'); lines.setAttribute('aria-hidden', 'true');
    lines.innerHTML = '<g class="s-mint" stroke-width="10" stroke-linecap="round" opacity="0.75">'
      + '<line x1="' + L.whole.x + '" y1="' + L.whole.y + '" x2="' + L.left.x + '" y2="' + L.left.y + '"/>'
      + '<line x1="' + L.whole.x + '" y1="' + L.whole.y + '" x2="' + L.right.x + '" y2="' + L.right.y + '"/></g>';
    parent.appendChild(lines);

    const circles = {}, pills = {}, nums = {};
    ['whole', 'left', 'right'].forEach(function (k) {
      const c = L[k];
      const el = abs(MW.make('div', 'mw-circle ' + (k === 'whole' ? 'mw-circle--whole' : 'mw-circle--part')), c.x - c.r, c.y - c.r);
      parent.appendChild(el);
      circles[k] = el;
      if (k === 'whole') {
        nums.whole = MW.make('span', 'numeral-whole');
        el.appendChild(nums.whole);
      } else {
        const p = abs(MW.make('div', 'mw-pill'), c.x - 45, L.pillTop);
        nums[k] = MW.make('span', 'numeral-part');
        p.appendChild(nums[k]);
        parent.appendChild(p);
        pills[k] = p;
      }
    });
    d.circles = circles; d.pills = pills;

    // The look: 'counting' (the usual: numbers in the whole circle and the pills, "?" where the answer goes) or
    // 'numbers' (MeeMee Rescue's numbers mode, NumbersMode card): no pills and no "?"; each given circle holds a
    // numbered MeeMee carrying its number, and the waiting circle is empty until a number tile is dropped in it.
    let look = 'counting';
    const carriers = {};
    let last = pills.right;                                   // the numbered MeeMee go just above the diagram's circles
    function carrier(k) {
      if (!carriers[k]) {
        const c = L[k];
        const m = carriers[k] = MW.numberedMimi(k === 'whole' ? L.numbered.whole : L.numbered.part);
        m.place(c.x, c.y);
        parent.insertBefore(m.el, last.nextSibling);
        last = m.el;
      }
      return carriers[k];
    }
    d.look = function (name) {
      if (name === undefined) return look;
      look = name === 'numbers' ? 'numbers' : 'counting';
      const off = look === 'numbers';
      pills.left.classList.toggle('mw-off', off); pills.right.classList.toggle('mw-off', off);
      nums.whole.classList.toggle('mw-off', off);
      if (!off) Object.keys(carriers).forEach(function (k) { carriers[k].hide(); });
      return look;
    };
    // A numbered MeeMee carrying n in circle k ('whole', 'left' or 'right'); n null takes it away (numbers look only).
    // pop: it pops up into the circle, as when a right answer is carried (a fade with reduce motion).
    d.carry = function (k, n, pop) {
      if (look !== 'numbers') return;
      if (n === null || n === undefined) { if (carriers[k]) carriers[k].hide(); return; }
      carrier(k).show(n, pop);
    };
    // What circle k's numbered MeeMee is carrying, or null (for checks).
    d.carried = function (k) { return carriers[k] ? carriers[k].shown() : null; };

    // q = { whole, left, right, missing: 'left' | 'right' | 'whole' }
    d.set = function (q) {
      ['whole', 'left', 'right'].forEach(function (k) {
        const waiting = q.missing === k;
        circles[k].classList.toggle('is-waiting', waiting);
        circles[k].classList.remove('is-success', 'is-hinting');
        if (pills[k]) pills[k].classList.toggle('is-waiting', waiting);
        if (pills[k]) pills[k].classList.remove('is-success');
        nums[k].textContent = waiting ? '?' : String(q[k]);
        nums[k].style.visibility = '';
        circles[k].setAttribute('aria-label', k === 'whole' ? 'The whole' : 'A part');
        if (look === 'numbers') d.carry(k, waiting ? null : q[k]);
      });
    };
    // The live count in the waiting circle: its pill shows the number of MeeMee in it ("?" when empty).
    d.count = function (k, n) {
      if (k === 'whole') nums.whole.style.visibility = (n > 0 || circles.whole.classList.contains('is-hinting')) ? 'hidden' : '';
      else nums[k].textContent = n > 0 ? String(n) : '?';
    };
    // The circle is answered: the success ring, and its number shows (in the numbers look, a numbered MeeMee pops up
    // to carry it).
    d.success = function (k, value) {
      circles[k].classList.remove('is-waiting', 'is-hinting');
      circles[k].classList.add('is-success');
      nums[k].textContent = String(value);
      nums[k].style.visibility = '';
      if (pills[k]) { pills[k].classList.remove('is-waiting'); pills[k].classList.add('is-success'); }
      if (look === 'numbers') d.carry(k, value, true);
    };
    d.hinting = function (k, on) {
      circles[k].classList.toggle('is-hinting', !!on);
      if (k === 'whole' && on) nums.whole.style.visibility = 'hidden';   // the ghosts take the "?"'s place
      if (k === 'whole' && !on && !circles.whole.classList.contains('is-success')) nums.whole.style.visibility = '';
    };
    // Which circle a drop landed in, or null.
    d.hit = function (x, y) {
      let found = null;
      ['whole', 'left', 'right'].forEach(function (k) {
        const c = L[k];
        if (Math.hypot(x - c.x, y - c.y) <= c.r + L.dropSlack) found = k;
      });
      return found;
    };
    d.slots = function (k, n) { const c = L[k]; return MW.layout(c.x, c.y, n, c.k); };
    return d;
  };

  // ---------------------------------------------------------------- the asteroid tray
  MW.tray = function (parent) {
    const el = abs(MW.art('tray'), L.tray.x, L.tray.y);
    el.classList.add('mw-abs');
    parent.appendChild(el);
    return { el: el, slots: L.traySlots };
  };

  // ---------------------------------------------------------------- a numbered MeeMee (numbers mode)
  // A MeeMee holding up a peach sign with a number on it (the "numbered-mimi" drawing, 140 x 209, and the number in
  // numeral-sign). k scales it: 1 in a part circle, 0.86 in the whole. MW.diagram's numbers look makes these itself.
  MW.numberedMimi = function (k) {
    k = k || 1;
    const el = MW.make('div', 'mw-numbered mw-abs mw-off', { role: 'img' });
    el.style.transform = 'scale(' + k + ')';
    el.appendChild(MW.art('numbered-mimi'));
    const sign = MW.make('span', 'mw-numbered-sign numeral-sign');
    el.appendChild(sign);
    let shown = null;
    return {
      el: el, k: k,
      // centre it on (cx, cy): the middle of a circle
      place: function (cx, cy) { abs(el, cx - 70, cy - 102.5); },
      show: function (n, pop) {
        shown = n;
        sign.textContent = String(n);
        el.setAttribute('aria-label', 'A MeeMee carrying ' + n);
        el.classList.remove('mw-off', 'is-popping');
        if (pop) { void el.offsetWidth; el.classList.add('is-popping'); }
      },
      hide: function () { shown = null; el.classList.add('mw-off'); el.classList.remove('is-popping'); },
      shown: function () { return shown; }
    };
  };

  // ---------------------------------------------------------------- the number track (numbers mode)
  // Tiles 0 to 10 in order along the bottom on an asteroid rail (NumbersMode card). Each tile is a draggable thing for
  // MW.dragger: x, y (its middle), draggable, el, lift(on), moveTo(x, y, size, animate), with a 120 pick-up box.
  // While a tile is away from its place, the place shows a dashed ring. The game says what a drop does: put the tile
  // in a circle (tile.moveTo(x, y, 0, true)) or send it back (tile.goHome(true)).
  // hide() lets go of a tile a finger is holding (its dragger's onDrop gets cancelled), sends any tile that is out back
  // to its place at once, then slides the track down out of sight (260 ms; a fade with reduce motion); show() brings
  // it back. While it is away its tiles can't be picked up.
  MW.numberTrack = function (parent) {
    const T = L.track;
    const el = MW.make('div', 'mw-track mw-layer mw-fill');
    const rail = abs(MW.art('number-track'), T.rail.x, T.rail.y);
    rail.classList.add('mw-abs');
    el.appendChild(rail);
    const tiles = [];
    for (let n = 0; n <= 10; n++) {
      const x = T.x + n * T.step;
      const place = abs(MW.make('div', 'mw-track-place'), x + 6, T.top + 6);
      el.appendChild(place);
      tiles.push(numberTile(el, n, { x: x + T.tile / 2, y: T.top + T.tile / 2 }, place));
    }
    parent.appendChild(el);
    let away = false;
    const track = {
      el: el, tiles: tiles,
      tile: function (n) { return tiles[n]; },
      away: function () { return away; },
      // every tile back in its place at once
      reset: function () { tiles.forEach(function (t) { t.lift(false); t.goHome(false); }); },
      hide: function () {
        MW.dragger.release(tiles);                            // a tile held as the track goes: let go of it first
        track.reset();
        away = true;
        tiles.forEach(function (t) { t.draggable = false; });
        void el.offsetWidth;                                  // slide from where it is now, even if it has only just been drawn
        el.classList.add('is-away');
        MW.log('track', 'away');
      },
      show: function () {
        away = false;
        tiles.forEach(function (t) { t.draggable = true; });
        void el.offsetWidth;
        el.classList.remove('is-away');
        MW.log('track', 'back');
      }
    };
    return track;
  };
  // One number tile: the "number-tile" drawing with its number in numeral-part, 84 across, in a 120 pick-up box.
  function numberTile(layer, n, home, place) {
    const el = MW.make('div', 'mw-number-tile', { role: 'img', 'aria-label': String(n) });
    const body = MW.make('div', 'mw-number-tile-body');
    body.appendChild(MW.art('number-tile'));
    body.appendChild(MW.make('span', 'mw-number-tile-n numeral-part', null, String(n)));
    el.appendChild(body);
    layer.appendChild(el);
    const t = { el: el, n: n, home: home, x: home.x, y: home.y, size: L.track.tile, draggable: true,
      grab: { w: L.track.grab, h: L.track.grab } };
    t.moveTo = function (x, y, size, animate) {
      t.x = x; t.y = y;
      el.classList.toggle('is-moving', !!animate && !MW.reduceMotion);
      el.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
      place.classList.toggle('is-out', Math.abs(x - home.x) > 0.5 || Math.abs(y - home.y) > 0.5);
    };
    t.lift = function (on) { t.lifted = !!on; el.classList.toggle('is-lifted', !!on); };
    t.goHome = function (animate) { t.moveTo(home.x, home.y, 0, animate); };
    t.out = function () { return place.classList.contains('is-out'); };
    t.moveTo(home.x, home.y, 0, false);
    return t;
  }

  // ---------------------------------------------------------------- Scruffles in the pod
  MW.pod = function (parent, x, y, w) {
    const btn = abs(MW.make('button', 'mw-pod', { type: 'button', 'aria-label': 'Scruffles' }), x, y);
    const art = MW.art('pod');
    art.setAttribute('width', w); art.setAttribute('height', Math.round(w * 430 / 400));
    btn.appendChild(art);
    parent.appendChild(btn);
    const pod = { el: btn };
    pod.face = function (name) {
      Array.prototype.forEach.call(art.querySelectorAll('[data-face]'), function (g) {
        g.style.display = g.getAttribute('data-face') === name ? '' : 'none';
      });
      btn.setAttribute('data-face', name);
    };
    // The ship's lights flash for about 4 seconds (kit.css). Small lights only, each under 2 flashes a second;
    // with reduce motion they just stay lit for those 4 seconds.
    let lightsTimer = null;
    pod.lightsOff = function () {
      clearTimeout(lightsTimer);
      btn.classList.remove('is-celebrating', 'is-ready');
    };
    // "Ready to check": the lights glow steadily (no flashing) while there is something for Scruffles to check.
    pod.ready = function (on) { btn.classList.toggle('is-ready', !!on && !btn.classList.contains('is-celebrating')); };
    pod.celebrate = function () {
      pod.lightsOff();
      void btn.getBoundingClientRect();                    // so the flashing starts again from the beginning
      btn.classList.add('is-celebrating');
      lightsTimer = setTimeout(pod.lightsOff, 4100);
    };
    pod.face('thinking');
    return pod;
  };

  // ---------------------------------------------------------------- progress stars
  // MW.stars(parent, x, y, size): x is the row's left edge. MW.stars(parent, cx, y, size, { centre: true }): the row is
  // centred on cx, however many stars set(done, total) shows (MW.LAYOUT.stars.cx is the usual middle, 640). Either
  // way the row's left edge is set in px, so its offsetLeft and its place on screen agree.
  MW.stars = function (parent, x, y, size, opts) {
    const centre = !!(opts && opts.centre);
    const el = abs(MW.make('div', 'mw-stars', { role: 'img' }), x, y);
    parent.appendChild(el);
    const STAR = '24,5 29.3,17.7 43,18.8 32.6,27.8 35.8,41.2 24,34 12.2,41.2 15.4,27.8 5,18.8 18.7,17.7';
    const cls = { done: 'class="f-peach s-peach" stroke-width="3"', current: 'class="f-night s-mint" stroke-width="4"',
      todo: 'class="s-star-empty" fill="none" stroke-width="3"' };
    size = size || 38;
    return {
      el: el,
      set: function (done, total) {
        total = total || 5;
        let html = '';
        for (let i = 0; i < total; i++) {
          const s = i < done ? 'done' : (i === done ? 'current' : 'todo');
          html += '<svg width="' + size + '" height="' + size + '" viewBox="0 0 48 48" aria-hidden="true" data-state="' + s + '">'
            + '<polygon ' + cls[s] + ' stroke-linejoin="round" points="' + STAR + '"/></svg>';
        }
        el.innerHTML = html;
        el.setAttribute('aria-label', 'Question ' + Math.min(done + 1, total) + ' of ' + total);
        if (centre) el.style.left = (x - (total * size + (total - 1) * starGap()) / 2) + 'px';
      }
    };
  };

  // the gap between stars: the space-s token (14 px), read from the page's tokens
  let gapPx = null;
  function starGap() {
    if (gapPx === null) gapPx = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--space-s')) || 14;
    return gapPx;
  }

  // ---------------------------------------------------------------- the equation
  MW.equation = function (parent) {
    const e = L.equation;
    const el = abs(MW.make('div', 'mw-equation equation', { 'aria-live': 'polite' }), e.x, e.y);
    el.style.width = e.w + 'px'; el.style.height = e.h + 'px';
    parent.appendChild(el);
    return {
      el: el,
      show: function (a, b, w) {
        el.innerHTML = '<span>' + a + '</span><span class="op">+</span><span>' + b + '</span><span class="op">=</span><span>' + w + '</span>';
        el.classList.add('is-shown');
      },
      hide: function () { el.classList.remove('is-shown'); el.innerHTML = ''; }
    };
  };

  // ---------------------------------------------------------------- sparkles: grow in 300 ms, fade by 1.2 s, never blink
  MW.sparkles = function (parent, cx, cy, r) {
    const n = 5;
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + i * (2 * Math.PI / n) + 0.3;
      const s = MW.art('spark');
      s.classList.add('mw-spark');
      const size = i % 2 ? 30 : 40;
      s.setAttribute('width', size); s.setAttribute('height', size);
      abs(s, cx + Math.cos(a) * r - size / 2, cy + Math.sin(a) * r - size / 2);
      parent.appendChild(s);
      setTimeout(function () { if (s.parentNode) s.parentNode.removeChild(s); }, 1300);
    }
  };

  // ---------------------------------------------------------------- hint ghosts: where the missing MeeMee would go
  MW.ghosts = function (parent, positions) {
    const els = positions.map(function (p) {
      const g = MW.make('div', 'mw-ghost');
      g.style.width = g.style.height = p.size + 'px';
      abs(g, p.x - p.size / 2, p.y - p.size / 2);
      parent.appendChild(g);
      return g;
    });
    return {
      light: function (i) { if (els[i]) els[i].classList.add('is-lit'); },
      clear: function () { els.forEach(function (g) { if (g.parentNode) g.parentNode.removeChild(g); }); }
    };
  };
})();
