/* MeeMee World kit: the pieces of a game screen.
   The part–whole diagram, the asteroid tray, Scruffles's pod, progress stars, the equation, sparkles and hint ghosts.
   Positions follow the design system's GameScreen (1280x800 stage). */
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
    stars: { x: 517, y: 34 },
    dropSlack: 22             // a drop this far outside a circle's rim still counts as inside
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
      });
    };
    // The live count in the waiting circle: its pill shows the number of MeeMee in it ("?" when empty).
    d.count = function (k, n) {
      if (k === 'whole') nums.whole.style.visibility = (n > 0 || circles.whole.classList.contains('is-hinting')) ? 'hidden' : '';
      else nums[k].textContent = n > 0 ? String(n) : '?';
    };
    d.success = function (k, value) {
      circles[k].classList.remove('is-waiting', 'is-hinting');
      circles[k].classList.add('is-success');
      nums[k].textContent = String(value);
      nums[k].style.visibility = '';
      if (pills[k]) { pills[k].classList.remove('is-waiting'); pills[k].classList.add('is-success'); }
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
    // The ship's lights flash for about 2 seconds (kit.css). Small lights only, each under 2 flashes a second;
    // with reduce motion they just stay lit for those 2 seconds.
    let lightsOff = null;
    pod.celebrate = function () {
      clearTimeout(lightsOff);
      btn.classList.remove('is-celebrating');
      void btn.getBoundingClientRect();                    // so the flashing starts again from the beginning
      btn.classList.add('is-celebrating');
      lightsOff = setTimeout(function () { btn.classList.remove('is-celebrating'); }, 2100);
    };
    pod.face('thinking');
    return pod;
  };

  // ---------------------------------------------------------------- progress stars
  MW.stars = function (parent, x, y, size) {
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
      }
    };
  };

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
