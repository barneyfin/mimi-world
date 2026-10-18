/* MeeMee Station: the station and its hull modules (0.9.0). The approved drawing from mock-up rounds 12 to 15 (the
   design system's MeeMeeStation card), copied from the round's code, not redrawn: truss, wings, hab, collar,
   antenna, dish, station, mast, cells, pods, hullSvg, bars, deck and whole (the round's docking port, which no screen
   shows, is left out). Only how they reach the page changed: each
   scene function takes the element to draw into, and pods and bars hand back what the game needs to change later (a
   window's state, the empty berth). Colour tokens only (classes f-…, s-…).
   The station is the ten frame (2 rows of 5 habitat modules, filling left to right along the top row, then the bottom
   row); its long hull modules are the bar model. Nothing countable near the maths (MEEMEE.md): no lights, windows or
   seams on the hull modules, and only the ten windows on the station. */
(function () {
  'use strict';
  const MW = window.MW;
  const NS = 'http://www.w3.org/2000/svg';
  let uid = 0;

  const D = MW.stationDraw = {};

  function el(tag, cls, css, text) {
    const e = MW.make(tag, cls);
    if (css) e.setAttribute('style', css);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  // an svg over the whole stage, in stage px
  D.layer = function (parent, inner) {
    const e = document.createElementNS(NS, 'svg');
    e.setAttribute('class', 'station-svg');
    e.setAttribute('width', 1280); e.setAttribute('height', 800); e.setAttribute('viewBox', '0 0 1280 800');
    e.setAttribute('aria-hidden', 'true');
    e.style.left = '0px'; e.style.top = '0px';
    e.innerHTML = inner;
    parent.appendChild(e);
    return e;
  };
  const n = function (v) { return Math.round(v * 10) / 10; };

  // ---------------------------------------------------------------- station parts (svg strings, stage px)
  // A lattice truss from xa to xb, centred on y: mint rails with a darker zigzag (the station's frame: the maths'
  // structure colour, like the ship's hull).
  function truss(xa, xb, y, th, vertical) {
    if (vertical) {          // xa, xb are the top and bottom, y the middle x
      const g = '<rect class="f-mint-deep s-ink" x="' + n(y - th / 2) + '" y="' + xa + '" width="' + th + '" height="' + (xb - xa) + '" rx="' + n(th / 3) + '" stroke-width="4"/>';
      let z = '';
      for (let k = xa + 4, i = 0; k < xb - 4; k += th, i++) z += (i ? 'L' : 'M') + n(i % 2 ? y + th / 2 - 4 : y - th / 2 + 4) + ' ' + n(k);
      return g + '<path class="s-mint-light" fill="none" d="' + z + '" stroke-width="3" stroke-linejoin="round"/>';
    }
    const g = '<rect class="f-mint-deep s-ink" x="' + xa + '" y="' + n(y - th / 2) + '" width="' + (xb - xa) + '" height="' + th + '" rx="' + n(th / 3) + '" stroke-width="4"/>';
    let z = '';
    for (let k = xa + 4, i = 0; k < xb - 4; k += th, i++) z += (i ? 'L' : 'M') + n(k) + ' ' + n(i % 2 ? y + th / 2 - 4 : y - th / 2 + 4);
    return g + '<path class="s-mint-light" fill="none" d="' + z + '" stroke-width="3" stroke-linejoin="round"/>';
  }
  // Solar wings: two indigo panels on a mast, above and below the truss at x.
  function wings(x, y, P, th, h) {
    const w = P * 0.74, gap = 8;
    h = h || P * 0.95;
    let g = '<rect class="f-steel s-ink" x="' + n(x - 6) + '" y="' + n(y - th / 2 - gap - h - 6) + '" width="12" height="' + n(2 * (h + gap + 6) + th) + '" rx="5" stroke-width="3.5"/>';
    [-1, 1].forEach(function (side) {
      const top = side < 0 ? y - th / 2 - gap - h : y + th / 2 + gap;
      g += '<rect class="f-planet-indigo s-ink" x="' + n(x - w / 2) + '" y="' + n(top) + '" width="' + n(w) + '" height="' + n(h) + '" rx="6" stroke-width="4"/>';
      let lines = 'M' + n(x) + ' ' + n(top + 3) + ' V' + n(top + h - 3) + ' ';
      for (let k = 1; k < 4; k++) lines += 'M' + n(x - w / 2 + 3) + ' ' + n(top + k * h / 4) + ' H' + n(x + w / 2 - 3) + ' ';
      g += '<path class="s-planet-indigo-light" d="' + lines + '" stroke-width="2.5" opacity="0.85"/>';
      g += '<path class="s-planet-indigo-light" d="M' + n(x - w / 2 + 6) + ' ' + n(top + 7) + ' H' + n(x - w / 2 + 20) + '" stroke-width="4" stroke-linecap="round"/>';
    });
    g += '<circle class="f-steel s-ink" cx="' + n(x) + '" cy="' + n(y) + '" r="' + n(th * 0.85) + '" stroke-width="3.5"/>';
    return g;
  }
  // One habitat module: a moon hull with a shaded lower band and a glint (its window is the pod, drawn over it).
  function hab(cx, cy, m) {
    const x = cx - m / 2, y = cy - m / 2, r = m * 0.2, band = m * 0.24;
    return '<rect class="f-moon" x="' + n(x) + '" y="' + n(y) + '" width="' + m + '" height="' + m + '" rx="' + n(r) + '"/>'
      + '<path class="f-white-shade" d="M' + n(x) + ' ' + n(y + m - band) + ' H' + n(x + m) + ' V' + n(y + m - r)
      + ' A' + n(r) + ' ' + n(r) + ' 0 0 1 ' + n(x + m - r) + ' ' + n(y + m) + ' H' + n(x + r) + ' A' + n(r) + ' ' + n(r) + ' 0 0 1 ' + n(x) + ' ' + n(y + m - r) + ' Z"/>'
      + '<rect class="s-ink" fill="none" x="' + n(x) + '" y="' + n(y) + '" width="' + m + '" height="' + m + '" rx="' + n(r) + '" stroke-width="5"/>'
      + '<path class="s-highlight" fill="none" d="M' + n(x + m * 0.12) + ' ' + n(y + m * 0.34) + ' A' + n(m * 0.3) + ' ' + n(m * 0.3) + ' 0 0 1 ' + n(x + m * 0.32) + ' ' + n(y + m * 0.12) + '" stroke-width="4" stroke-linecap="round" opacity="0.65"/>';
  }
  // A mint collar joining two modules side by side (the ten frame's lines are the collars and the truss).
  function collar(x, cy, w, h) {
    return '<rect class="f-mint s-ink" x="' + n(x - w / 2) + '" y="' + n(cy - h / 2) + '" width="' + n(w) + '" height="' + n(h) + '" rx="4" stroke-width="3.5"/>'
      + '<path class="s-mint-deep" d="M' + n(x) + ' ' + n(cy - h / 2 + 4) + ' V' + n(cy + h / 2 - 4) + '" stroke-width="3"/>';
  }
  function antenna(x, yTop, len) {
    return '<path class="s-ink" d="M' + n(x) + ' ' + n(yTop) + ' V' + n(yTop - len) + '" stroke-width="7" stroke-linecap="round"/>'
      + '<path class="s-steel" d="M' + n(x) + ' ' + n(yTop - 2) + ' V' + n(yTop - len + 2) + '" stroke-width="3" stroke-linecap="round"/>'
      + '<circle class="f-spark s-ink" cx="' + n(x) + '" cy="' + n(yTop - len - 7) + '" r="9" stroke-width="3.5"/>';
  }
  function dish(x, yTop, r) {
    return '<path class="s-ink" d="M' + n(x) + ' ' + n(yTop) + ' V' + n(yTop - r * 0.7) + '" stroke-width="7" stroke-linecap="round"/>'
      + '<g transform="rotate(-28 ' + n(x) + ' ' + n(yTop - r * 0.8) + ')">'
      + '<path class="f-moon-dim s-ink" d="M' + n(x - r) + ' ' + n(yTop - r * 0.8) + ' A' + n(r) + ' ' + n(r * 0.62) + ' 0 0 0 ' + n(x + r) + ' ' + n(yTop - r * 0.8) + ' Z" stroke-width="4" stroke-linejoin="round"/>'
      + '<path class="s-ink" d="M' + n(x) + ' ' + n(yTop - r * 0.8) + ' V' + n(yTop - r * 1.35) + '" stroke-width="3"/>'
      + '<circle class="f-spark s-ink" cx="' + n(x) + '" cy="' + n(yTop - r * 1.4) + '" r="4.5" stroke-width="2.5"/></g>';
  }
  D.truss = truss; D.wings = wings; D.hab = hab; D.collar = collar; D.antenna = antenna; D.dish = dish;

  // ---------------------------------------------------------------- the station (the ten frame)
  // f: { x, y } its top-left, P the pitch (one module and its join), m a module's size; d a window's size.
  // o: { wings, tower, dish, wingH }: the station's own bits. Returns the svg string.
  D.station = function (f, o) {
    o = o || {};
    const P = f.P, m = f.m, th = Math.round(P * 0.15);
    const cx = function (c) { return f.x + P * (c + 0.5); }, cy = function (r) { return f.y + P * (r + 0.5); };
    const mid = f.y + P, right = f.x + 5 * P;
    let g = '';
    const ws = o.wings || [];
    const ta = ws.length ? Math.min.apply(null, ws) : f.x + P * 0.25;
    const tb = ws.length > 1 ? Math.max.apply(null, ws) : right - P * 0.25;
    g += truss(ta, tb, mid, th);
    ws.forEach(function (x) { g += wings(x, mid, P, th, o.wingH); });
    if (o.tower) {                                         // the command tower: the whole shows on its screen
      const t = o.tower, tw = t.w || 150, r = 28;
      g += antenna(t.cx + tw * 0.28, t.top + 2, 34)
        + '<rect class="f-moon s-ink" x="' + n(t.cx - tw / 2) + '" y="' + t.top + '" width="' + tw + '" height="' + (f.y + 16 - t.top) + '" rx="' + r + '" stroke-width="5"/>'
        + '<rect class="f-white-shade" x="' + n(t.cx + tw / 2 - 26) + '" y="' + (t.top + 14) + '" width="18" height="' + (f.y - t.top - 10) + '" rx="8"/>'
        + '<path class="s-highlight" fill="none" d="M' + n(t.cx - tw / 2 + 14) + ' ' + (t.top + 40) + ' A26 26 0 0 1 ' + n(t.cx - tw / 2 + 40) + ' ' + (t.top + 14) + '" stroke-width="4" stroke-linecap="round" opacity="0.65"/>';
    }
    if (o.dish) g += dish(cx(4) + m * 0.12, cy(0) - m / 2 + 2, P * 0.24);
    for (let r = 0; r < 2; r++) {
      for (let c = 0; c < 4; c++) g += collar(f.x + P * (c + 1), cy(r), P - m + 14, m * 0.4);
      for (let c = 0; c < 5; c++) g += hab(cx(c), cy(r), m);
    }
    return g;
  };
  // a vertical mast (a truss) from y0 down to y1 at x: the svg string
  D.mast = function (x, y0, y1, w) { return truss(y0, y1, x, w || 18, true); };

  // centres of the ten windows: left to right, top row first (the way a ten frame fills)
  D.cells = function (f) {
    const out = [];
    for (let r = 0; r < 2; r++) for (let c = 0; c < 5; c++) out.push({ x: f.x + f.P * (c + 0.5), y: f.y + f.P * (r + 0.5) });
    return out;
  };
  // The ten windows, drawn into parent: [{ x, y, el, state, set(state) }], in ten-frame order. A window's state is ''
  // (open), 'arrived' (a peach rim and the success ring), 'hinting' (a mint rim and halo) or 'closed' (the shutter).
  D.pods = function (parent, f, states) {
    const d = f.d;
    return D.cells(f).map(function (c, i) {
      const p = el('div', 'station-pod', 'left:' + (c.x - d / 2) + 'px;top:' + (c.y - d / 2) + 'px;width:' + d + 'px;height:' + d + 'px');
      p.setAttribute('data-window', i);
      parent.appendChild(p);
      const w = { x: c.x, y: c.y, d: d, el: p, state: '' };
      w.set = function (state) {
        state = state || '';
        w.state = state;
        p.classList.remove('is-arrived', 'is-closed', 'is-hinting');
        if (state) p.classList.add('is-' + state);
        p.setAttribute('data-state', state);
        const sh = p.querySelector('.station-shutter');
        if (state === 'closed' && !sh) {
          const s = MW.make('div', 'station-shutter'); const a = MW.art('station-shutter');
          a.setAttribute('width', d); a.setAttribute('height', d); s.appendChild(a); p.appendChild(s);
        } else if (state !== 'closed' && sh) p.removeChild(sh);
      };
      w.set(states && states[i]);
      return w;
    });
  };

  // ---------------------------------------------------------------- the bar model: the station's long hull modules
  // One hull module, w x h: a moon hull with mint docking rings at both ends, a shaded lower band and a glint.
  // No windows or lights on it: nothing the child might count.
  D.hullSvg = function (w, h, whole) {
    const r = Math.min(h * 0.32, 30), cw = whole ? 20 : 16, band = h * 0.24, id = 'station-hull-' + (++uid);
    const g = '<clipPath id="' + id + '"><rect x="0" y="0" width="' + w + '" height="' + h + '" rx="' + n(r) + '"/></clipPath>'
      + '<g clip-path="url(#' + id + ')">'
      + '<rect class="f-moon" x="0" y="0" width="' + w + '" height="' + h + '"/>'
      + '<rect class="f-white-shade" x="0" y="' + n(h - band) + '" width="' + w + '" height="' + n(band) + '"/>'
      + '<rect class="f-mint" x="0" y="0" width="' + cw + '" height="' + h + '"/>'
      + '<rect class="f-mint" x="' + (w - cw) + '" y="0" width="' + cw + '" height="' + h + '"/>'
      + '<rect class="f-mint-dark" x="0" y="' + n(h - band) + '" width="' + cw + '" height="' + n(band) + '"/>'
      + '<rect class="f-mint-dark" x="' + (w - cw) + '" y="' + n(h - band) + '" width="' + cw + '" height="' + n(band) + '"/>'
      + '</g>'
      + '<path class="s-ink" d="M' + cw + ' 0 V' + h + ' M' + (w - cw) + ' 0 V' + h + '" stroke-width="3.5"/>'
      + '<path class="s-highlight" d="M' + (cw + 14) + ' ' + n(h * 0.17) + ' H' + n(Math.min(w - cw - 14, cw + 14 + w * 0.35)) + '" stroke-width="4" stroke-linecap="round" opacity="0.6"/>'
      + '<rect class="s-ink" fill="none" x="2.5" y="2.5" width="' + (w - 5) + '" height="' + (h - 5) + '" rx="' + n(r - 2) + '" stroke-width="5"/>';
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '" aria-hidden="true" style="position:absolute;left:0;top:0">' + g + '</svg>';
  };
  // The bar model, drawn into parent. b: { x, y, w, h, gap }; whole, parts [a, b]; missing: 'whole' | 0 | 1 | null;
  // opts: { minW, big }. Returns { whole, left, right }: each { el, x, y, w, h, isWhole, value, fill(v) }, where fill
  // turns the empty berth into a hull module showing v (with the success ring, as a right answer docks).
  D.bars = function (parent, b, whole, parts, missing, opts) {
    opts = opts || {};
    const unit = b.w / whole, minW = opts.minW || 130;
    let w0 = Math.max(minW, Math.round(parts[0] * unit));
    w0 = Math.min(w0, b.w - minW);
    const widths = [w0, b.w - w0];
    const numW = opts.big ? 'numeral-sign' : 'equation', numP = opts.big ? 'equation' : 'numeral-part';
    const r = Math.min(b.h * 0.32, 30);
    function mod(x, y, w, h, isWhole, value, waiting) {
      const box = el('div', 'station-bar' + (waiting ? ' is-waiting' : ''),
        'left:' + x + 'px;top:' + y + 'px;width:' + w + 'px;height:' + h + 'px;border-radius:' + n(r) + 'px');
      const m = { el: box, x: x, y: y, w: w, h: h, isWhole: isWhole, value: waiting ? null : value };
      function draw(v) {
        box.innerHTML = D.hullSvg(w, h, isWhole);
        box.appendChild(el('span', (isWhole ? numW : numP) + ' station-bar-n', null, String(v)));
      }
      if (!waiting) draw(value);
      m.fill = function (v) {
        box.classList.remove('is-waiting', 'is-hinting');
        draw(v);
        m.value = v;
        box.classList.add('is-success');
      };
      parent.appendChild(box);
      return m;
    }
    // the clamps holding the parts under the whole (mint, at each part's middle)
    let g = '';
    const py = b.y + b.h + b.gap;
    let x = b.x;
    widths.forEach(function (w) { g += '<rect class="f-mint-deep s-ink" x="' + n(x + w / 2 - 14) + '" y="' + n(b.y + b.h - 8) + '" width="28" height="' + n(b.gap + 16) + '" rx="4" stroke-width="3.5"/>'; x += w; });
    D.layer(parent, g);
    const out = {};
    out.whole = mod(b.x, b.y, b.w, b.h, true, whole, missing === 'whole');
    x = b.x;
    parts.forEach(function (v, i) {
      out[i ? 'right' : 'left'] = mod(x + (i ? 3 : 0), py, widths[i] - 3, b.h, false, v, missing === i);
      x += widths[i];
    });
    return out;
  };

  // ---------------------------------------------------------------- the landing deck and the tower's screen
  // the station's landing deck, bottom right, where the MeeMee wait to come aboard: the svg string
  D.deck = function () {
    return '<rect class="f-night-raised s-ink" x="730" y="732" width="520" height="34" rx="14" stroke-width="5"/>'
      + '<rect class="f-night-button s-ink" x="724" y="642" width="532" height="104" rx="44" stroke-width="5"/>'
      + '<path class="s-text-3" d="M780 666 H1200" stroke-width="3" stroke-dasharray="2 18" stroke-linecap="round" opacity="0.6"/>';
  };
  // the whole on the tower's round screen (step 1), drawn into parent
  D.whole = function (parent, value, cx, cy) {
    const d = 118;
    const p = el('div', 'station-whole', 'left:' + (cx - d / 2) + 'px;top:' + (cy - d / 2) + 'px;width:' + d + 'px;height:' + d + 'px');
    p.appendChild(el('span', 'numeral-sign', null, String(value)));
    parent.appendChild(p);
    return p;
  };
})();
