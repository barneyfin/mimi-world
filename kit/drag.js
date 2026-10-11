/* MeeMee World kit: counters and dragging.
   A counter (a MeeMee) is drawn at 80 stage px inside an invisible 120 px grab circle.
   A thing that isn't round (a long tile) carries its own pick-up box instead: grab = { w, h }, centred on it.
   One finger drags at a time; where pick-up areas overlap, the thing whose centre is nearest the finger is picked up. */
(function () {
  'use strict';
  const MW = window.MW;
  const GRAB_R = 60;          // half of mimi-grab (120)
  const BASE = 80;            // mimi-size

  // ---------------------------------------------------------------- counters
  MW.counter = function (layer, opts) {
    opts = opts || {};
    const el = MW.make('div', 'mw-mimi' + (opts.fixed ? ' is-fixed' : ''), { role: 'img', 'aria-label': 'MeeMee' });
    const art = MW.art('mimi');
    el.appendChild(art);
    layer.appendChild(el);
    const c = { el: el, art: art, x: 0, y: 0, size: BASE, draggable: !opts.fixed, home: null, where: null, data: {} };
    c.moveTo = function (x, y, size, animate) {
      c.x = x; c.y = y;
      if (size) c.size = size;
      el.classList.toggle('is-moving', !!animate && !MW.reduceMotion);
      el.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
      art.style.transform = 'scale(' + (c.size / BASE * (c.lifted ? 1.12 : 1)) + ')';
    };
    c.lift = function (on) { c.lifted = !!on; el.classList.toggle('is-lifted', !!on); };
    c.remove = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    c.moveTo(opts.x || 0, opts.y || 0, opts.size || BASE, false);
    return c;
  };

  // Counting patterns (design system: CountingPatterns): offsets from a circle's centre, and the MeeMee size.
  MW.pattern = function (n) {
    if (n <= 0) return { size: BASE, pts: [] };
    if (n === 1) return { size: 80, pts: [[0, 0]] };
    if (n === 2) return { size: 80, pts: [[-45, 0], [45, 0]] };
    if (n === 3) return { size: 80, pts: [[0, -46], [-45, 34], [45, 34]] };
    if (n === 4) return { size: 80, pts: [[-45, -45], [45, -45], [-45, 45], [45, 45]] };
    if (n === 5) return { size: 56, pts: [[-46, -46], [46, -46], [0, 0], [-46, 46], [46, 46]] };
    if (n === 6) return { size: 56, pts: [[-64, -32], [0, -32], [64, -32], [-64, 32], [0, 32], [64, 32]] };
    const four = [-81, -27, 27, 81], three = [-54, 0, 54];
    const row = function (xs, y) { return xs.map(function (x) { return [x, y]; }); };
    if (n === 7) return { size: 46, pts: row(four, -27).concat(row(three, 27)) };
    if (n === 8) return { size: 46, pts: row(four, -27).concat(row(four, 27)) };
    if (n === 9) return { size: 46, pts: row(three, -54).concat(row(three, 0), row(three, 54)) };
    return { size: 46, pts: row(three, -54).concat(row(four, 0), row(three, 54)) };
  };
  // Positions for n counters in a circle centred at (cx, cy); k scales the pattern (0.9 in the smaller whole circle).
  MW.layout = function (cx, cy, n, k) {
    k = k || 1;
    const p = MW.pattern(Math.min(10, n));
    return p.pts.map(function (d) { return { x: cx + d[0] * k, y: cy + d[1] * k, size: p.size * k }; });
  };

  // ---------------------------------------------------------------- dragging
  // MW.dragger(stageEl, { counters: () => [...], onPick(c), onDrop(c, x, y), grab: radius in stage px (default 60) })
  // Anything with x, y (its centre), draggable, el, lift(on) and moveTo(x, y, size, animate) can be dragged.
  // Each thing is picked up within its own box if it has one (c.grab = { w, h }, in stage px, centred on x, y), or
  // else within the dragger's grab radius. Where they overlap, the thing whose centre is nearest the finger wins.
  const draggers = [];
  MW.dragger = function (surface, opts) {
    let drag = null;
    const stats = MW.dragStats = MW.dragStats || { last: null };

    function nearest(p) {
      const r = opts.grab || GRAB_R;
      let best = null, bestD = Infinity;
      opts.counters().forEach(function (c) {
        if (!c.draggable) return;
        const dx = Math.abs(c.x - p.x), dy = Math.abs(c.y - p.y), d = Math.hypot(dx, dy);
        const inside = c.grab ? dx <= c.grab.w / 2 && dy <= c.grab.h / 2 : d <= r;
        if (inside && d <= bestD) { best = c; bestD = d; }
      });
      return best;
    }

    surface.addEventListener('pointerdown', function (e) {
      if (drag || (opts.enabled && !opts.enabled())) return;
      if (e.button !== undefined && e.button > 0) return;
      const p = MW.stage.toStage(e.clientX, e.clientY);
      const c = nearest(p);
      if (!c) return;
      e.preventDefault();
      try { surface.setPointerCapture(e.pointerId); } catch (err) {}
      drag = { c: c, id: e.pointerId, dx: c.x - p.x, dy: c.y - p.y, tx: c.x, ty: c.y, frames: [], lastT: null, raf: 0 };
      c.lift(true);
      c.el.classList.remove('is-moving');
      c.size = BASE;
      c.moveTo(c.x, c.y, BASE, false);   // .is-lifted puts it above the other counters
      if (opts.onPick) opts.onPick(c);
      MW.lastInput = e.pointerType || 'unknown';
      drag.raf = requestAnimationFrame(frame);
    });

    function frame(t) {
      if (!drag) return;
      if (drag.lastT !== null) drag.frames.push(t - drag.lastT);
      drag.lastT = t;
      drag.c.moveTo(drag.tx, drag.ty, BASE, false);
      drag.raf = requestAnimationFrame(frame);
    }

    surface.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      const p = MW.stage.toStage(e.clientX, e.clientY);
      drag.tx = Math.max(0, Math.min(MW.stage.W, p.x + drag.dx));
      drag.ty = Math.max(0, Math.min(MW.stage.H, p.y + drag.dy));
    }, { passive: true });

    // cancelled: the touch was taken away (a system swipe, the tablet turning) rather than lifted.
    function end(e, cancelled) {
      if (!drag || (e && e.pointerId !== drag.id)) return;
      cancelAnimationFrame(drag.raf);
      const d = drag; drag = null;
      d.c.lift(false);
      d.c.moveTo(d.tx, d.ty, BASE, false);
      record(d.frames);
      if (opts.onDrop) opts.onDrop(d.c, d.tx, d.ty, !!cancelled);
    }
    surface.addEventListener('pointerup', function (e) { end(e, false); });
    surface.addEventListener('pointercancel', function (e) { end(e, true); });
    surface.addEventListener('lostpointercapture', function (e) { end(e, true); });

    function record(frames) {
      if (frames.length < 5) return;
      let sum = 0, worst = 0, slow = 0;
      frames.forEach(function (f) { sum += f; if (f > worst) worst = f; if (f > 34) slow++; });
      stats.last = { fps: Math.round(1000 / (sum / frames.length)), worst: Math.round(worst), slow: slow, n: frames.length };
    }

    const api = { dragging: function () { return !!drag; }, cancel: function () { if (drag) end(null, true); },
      holding: function () { return drag ? drag.c : null; } };
    draggers.push(api);
    return api;
  };
  // Let go of any of these things that a finger is holding, in whichever dragger holds it: its onDrop gets cancelled
  // (as when the tablet takes the touch away), so it goes back. MW.numberTrack's hide() uses it for its tiles.
  MW.dragger.release = function (things) {
    draggers.forEach(function (d) { const c = d.holding(); if (c && things.indexOf(c) >= 0) d.cancel(); });
  };
})();
