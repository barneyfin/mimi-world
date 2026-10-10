/* MeeMee World kit: the home map (phase 4; a planet per game from phase 5).
   An alien solar system: each game is a planet. The drawing is the "map" art (design/gen_scenes.py, whose MAP holds
   the same positions, and draws a game's planet lit and an empty one dimmed); this file puts the buttons over it.
   Three planets: 0 the ringed mint planet (MeeMee Rescue), 1 the indigo planet, 2 the small peach planet. A game says
   which is its own in its game.json. Tapping a game's planet (or its badge) opens it; an empty planet says
   "That planet isn't ready yet." The crew wait by Scruffles's ship, wearing their job badges; tapping them opens the
   crew screen (kit/crew.js). */
(function () {
  'use strict';
  const MW = window.MW;

  const M = MW.LAYOUT.map = {
    // tap: the tap area across (at least 120 stage px, design system); badge: where a game's picture sits;
    // lock: what an empty planet shows instead
    planets: [
      { x: 330, y: 300, tap: 180, badge: { x: 368, y: 166, d: 84, pic: 56 }, lock: { x: 368, y: 190, d: 60, icon: 30 } },
      { x: 1010, y: 560, tap: 130, badge: { x: 1040, y: 446, d: 84, pic: 56 }, lock: { x: 1056, y: 470, d: 60, icon: 30 } },
      { x: 1150, y: 250, tap: 120, badge: { x: 1172, y: 158, d: 72, pic: 48 }, lock: { x: 1186, y: 196, d: 50, icon: 24 } }
    ],
    ship: { x: 155, y: 400, w: 190 },
    crew: [{ who: 'moggles', x: 44, y: 456, w: 112 }, { who: 'snuffles', x: 344, y: 456, w: 112 }],
    crewTap: { x: 34, y: 392, w: 432, h: 236 }                // the ship and both cats
  };

  function place(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; return el; }

  // opts: { games: [{ planet, badge, name, onOpen }], onLocked: fn, onCrew: fn }
  MW.map = function (parent, opts) {
    const map = { badges: {} };
    const art = MW.art('map');
    art.setAttribute('class', 'mw-layer');
    parent.appendChild(art);

    // the crew by the ship: one big button that opens the crew screen
    const ship = MW.art('pod');
    ship.setAttribute('width', M.ship.w); ship.setAttribute('height', Math.round(M.ship.w * 430 / 400));
    Array.prototype.forEach.call(ship.querySelectorAll('[data-face]'), function (g) { g.style.display = g.getAttribute('data-face') === 'thinking' ? '' : 'none'; });
    const shipBox = place(MW.make('div', 'mw-abs mw-map-crew'), M.ship.x, M.ship.y);
    shipBox.appendChild(ship);
    parent.appendChild(shipBox);
    map.crew = {};
    M.crew.forEach(function (c) {
      const box = place(MW.make('div', 'mw-abs mw-map-crew', { 'data-who': c.who }), c.x, c.y);
      const cat = MW.crew.cat(c.who, c.w);
      box.appendChild(cat);
      parent.appendChild(box);
      map.crew[c.who] = cat;
    });
    const t = M.crewTap;
    const crewBtn = place(MW.make('button', 'mw-map-crew-btn mw-abs', { type: 'button', 'aria-label': 'The crew' }), t.x, t.y);
    crewBtn.style.width = t.w + 'px'; crewBtn.style.height = t.h + 'px';
    parent.appendChild(crewBtn);
    MW.onTap(crewBtn, function () { if (opts.onCrew) opts.onCrew(); });
    map.crewBtn = crewBtn;
    // their job badges, as given on the crew screen
    map.setCrew = function (jobs) { MW.crew.CATS.forEach(function (w) { map.crew[w].setJob(jobs[w]); }); };
    // no jobs yet: the cats hop, to say "tap us"
    map.callCrew = function () { map.crew.moggles.hop(0); map.crew.snuffles.hop(180); };

    // the planets: a game's is one big button with its badge; an empty one is dimmed, with a lock
    map.planets = M.planets.map(function (p, i) {
      const g = (opts.games || []).filter(function (x) { return x.planet === i; })[0];
      const b = place(MW.make('button', 'mw-planet mw-abs', { type: 'button', 'aria-label': g ? g.name : 'A planet that isn\'t ready yet' }), p.x - p.tap / 2, p.y - p.tap / 2);
      b.style.width = b.style.height = p.tap + 'px';
      parent.appendChild(b);
      const go = function () { if (g) { if (g.onOpen) g.onOpen(); } else if (opts.onLocked) opts.onLocked(); };
      MW.onTap(b, go);
      if (g) {
        const badge = place(MW.make('button', 'mw-planet-badge mw-abs', { type: 'button', 'aria-label': g.name }), p.badge.x, p.badge.y);
        badge.style.width = badge.style.height = p.badge.d + 'px';
        const pic = MW.art(g.badge); pic.setAttribute('width', p.badge.pic); pic.setAttribute('height', p.badge.pic);
        badge.appendChild(pic);
        parent.appendChild(badge);
        MW.onTap(badge, go);
        map.badges[i] = badge;
      } else {
        const lock = place(MW.make('div', 'mw-planet-lock mw-abs'), p.lock.x, p.lock.y);
        lock.style.width = lock.style.height = p.lock.d + 'px';
        const icon = MW.art('icon-lock'); icon.setAttribute('width', p.lock.icon); icon.setAttribute('height', p.lock.icon);
        lock.appendChild(icon);
        parent.appendChild(lock);
        MW.onTap(lock, go);
      }
      return b;
    });

    // a little bounce on a planet's badge when it is chosen
    map.bounce = function (i) {
      const badge = map.badges[i];
      if (!badge) return;
      badge.classList.remove('is-hop'); void badge.getBoundingClientRect(); badge.classList.add('is-hop');
    };
    return map;
  };
})();
