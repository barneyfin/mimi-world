/* MeeMee World kit: the home map (phase 4).
   An alien solar system: each game is a planet. The drawing is the "map" art (design/gen_scenes.py, whose MAP holds
   the same positions); this file puts the buttons over it. Tapping a game's planet says its name and opens it;
   a planet still to come says "That planet isn't ready yet." The crew wait by Scruffles's ship. */
(function () {
  'use strict';
  const MW = window.MW;

  const M = MW.LAYOUT.map = {
    rescue: { x: 330, y: 300, tap: 180 },                     // tap area at least 120 stage px across (design system)
    badge: { x: 368, y: 166, d: 84 },
    locked: [{ x: 1010, y: 560, tap: 130, lock: { x: 1056, y: 470, d: 60, icon: 30 } },
      { x: 1150, y: 250, tap: 120, lock: { x: 1186, y: 196, d: 50, icon: 24 } }],
    ship: { x: 155, y: 400, w: 190 },
    crew: [{ who: 'moggles', x: 44, y: 456, w: 112 }, { who: 'snuffles', x: 344, y: 456, w: 112 }]
  };

  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }

  // opts: { onRescue: fn, onLocked: fn }
  MW.map = function (parent, opts) {
    const map = {};
    const art = MW.art('map');
    art.setAttribute('class', 'mw-layer');
    parent.appendChild(art);

    // the crew by the ship (pictures only for now; tapping them opens the crew screen from 0.4.1)
    const ship = MW.art('pod');
    ship.setAttribute('width', M.ship.w); ship.setAttribute('height', Math.round(M.ship.w * 430 / 400));
    Array.prototype.forEach.call(ship.querySelectorAll('[data-face]'), function (g) { g.style.display = g.getAttribute('data-face') === 'thinking' ? '' : 'none'; });
    const shipBox = place(MW.make('div', 'mw-abs mw-map-crew'), M.ship.x, M.ship.y);
    shipBox.appendChild(ship);
    parent.appendChild(shipBox);
    map.crew = {};
    M.crew.forEach(function (c) {
      const box = place(MW.make('div', 'mw-abs mw-map-crew', { 'data-who': c.who }), c.x, c.y);
      const pic = MW.art(c.who);
      pic.setAttribute('width', c.w); pic.setAttribute('height', Math.round(c.w * 340 / 260));
      box.appendChild(pic);
      parent.appendChild(box);
      map.crew[c.who] = box;
    });

    // MeeMee Rescue: the planet and its badge are one big button
    const r = M.rescue;
    const rescue = place(MW.make('button', 'mw-planet mw-abs', { type: 'button', 'aria-label': 'MeeMee Rescue' }), r.x - r.tap / 2, r.y - r.tap / 2);
    rescue.style.width = rescue.style.height = r.tap + 'px';
    parent.appendChild(rescue);
    const badge = place(MW.make('button', 'mw-planet-badge mw-abs', { type: 'button', 'aria-label': 'MeeMee Rescue' }), M.badge.x, M.badge.y);
    badge.style.width = badge.style.height = M.badge.d + 'px';
    const mm = MW.art('mimi'); mm.setAttribute('width', 56); mm.setAttribute('height', 56);
    badge.appendChild(mm);
    parent.appendChild(badge);
    [rescue, badge].forEach(function (b) { MW.onTap(b, function () { if (opts.onRescue) opts.onRescue(); }); });
    map.rescue = rescue; map.badge = badge;

    // planets still to come: dimmed, with a lock
    map.locked = M.locked.map(function (l) {
      const b = place(MW.make('button', 'mw-planet mw-abs', { type: 'button', 'aria-label': 'A planet that isn\'t ready yet' }), l.x - l.tap / 2, l.y - l.tap / 2);
      b.style.width = b.style.height = l.tap + 'px';
      parent.appendChild(b);
      const lock = place(MW.make('div', 'mw-planet-lock mw-abs'), l.lock.x, l.lock.y);
      lock.style.width = lock.style.height = l.lock.d + 'px';
      const icon = MW.art('icon-lock'); icon.setAttribute('width', l.lock.icon); icon.setAttribute('height', l.lock.icon);
      lock.appendChild(icon);
      parent.appendChild(lock);
      MW.onTap(b, function () { if (opts.onLocked) opts.onLocked(); });
      MW.onTap(lock, function () { if (opts.onLocked) opts.onLocked(); });
      return b;
    });

    // a little bounce on the badge when its planet is chosen
    map.bounce = function () {
      badge.classList.remove('is-hop'); void badge.getBoundingClientRect(); badge.classList.add('is-hop');
    };
    return map;
  };
})();
