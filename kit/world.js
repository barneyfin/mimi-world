/* MeeMee World kit: the world shell (phase 5).
   What every game shares, so a game is only its own play:
     the start screen (Play: sound and full screen start on that first tap), the home map with a planet for each game,
     the crew screen, pausing (grown-ups area open, tablet upright, screen off), the grown-ups area, and updates.
   One page holds every game (decided 10 October). A game joins by calling MW.world.game({...}) when its script loads;
   its folder's game.json (read by the build, here as MW_GAMES) says its name, planet, badge and spoken name.
   The meemee-world skill (.claude/skills/meemee-world/reference.md) documents all of this. */
(function () {
  'use strict';
  const MW = window.MW;
  const W = MW.world = { games: [], map: null, crewScreen: null };
  // One state for the page: a token that changes whenever the player leaves what they were doing (speech and timers
  // from before check it), the current phase ('idle' start screen, 'map', 'opening', 'crew', or the game's own),
  // and the reasons the world is paused.
  const st = W.st = { token: 0, phase: 'idle', paused: false, pauses: {}, welcomed: false };

  // One game going wrong never stops the others: each call into a game is caught, logged and shown in the console.
  function each(fn) {
    W.games.forEach(function (g) {
      try { fn(g); } catch (e) { MW.log('game-error', g.id + ': ' + e); console.error('MeeMee World: ' + g.id + ':', e); }
    });
  }

  // ---------------------------------------------------------------- games join
  // def: { id, build(), start(), sections: [{ id, title, render(el) }], onPause(why), onResume(), onHome(), init() }
  // id must match a games/<id>/game.json; name, planet, badge and say come from there.
  W.game = function (def) {
    const m = (window.MW_GAMES || []).filter(function (g) { return g.id === def.id; })[0];
    if (!m) throw new Error('MW.world.game: no games/' + def.id + '/game.json in this build');
    if (typeof def.build !== 'function' || typeof def.start !== 'function') throw new Error('MW.world.game: ' + def.id + ' needs build() and start()');
    const g = Object.assign({}, m, def);
    W.games.push(g);
    W.games.sort(function (a, b) { return a.planet - b.planet; });
    return g;
  };

  // A screen of the game's own: <section class="mw-screen">, after the others, under the grown-ups area.
  W.screen = function (id, label) {
    const stage = MW.$('stage');
    const s = MW.make('section', 'mw-screen', { id: id, 'aria-label': label });
    const screens = stage.querySelectorAll('.mw-screen');
    const last = screens[screens.length - 1];
    if (last && last.nextSibling) stage.insertBefore(s, last.nextSibling); else stage.appendChild(s);
    return s;
  };

  // ---------------------------------------------------------------- speaking and waiting
  // Wait while paused; false if the player has left (the token changed) meanwhile.
  W.ok = async function (token) {
    while (st.paused) await MW.wait(200);
    return token === st.token;
  };
  // Say lines, after any pause; nothing if the player left first. Resolves true if the lines played to the end.
  W.speak = async function (lines, opts) {
    const token = st.token;
    if (!(await W.ok(token))) return false;
    return MW.audio.say(lines, opts);
  };

  // ---------------------------------------------------------------- pausing
  // Reasons: the grown-ups area is open, the tablet is upright, or the page is hidden (screen off, another app).
  // The world carries on only when none is left; then each game picks up where it was (usually: ask again).
  W.pause = function (why) {
    st.pauses[why] = true;
    st.paused = true;
    MW.audio.hush();
    if (W.crewScreen) W.crewScreen.dragger.cancel();        // a cat held when the screen goes off goes back to its place
    each(function (g) { if (g.onPause) g.onPause(why); });
    MW.log('pause', why);
  };
  W.resume = function (why) {
    if (!st.pauses[why]) return;
    delete st.pauses[why];
    if (Object.keys(st.pauses).length) return;
    st.paused = false;
    MW.log('resume', why);
    if (MW.shell.screen === 'screen-crew' && st.phase === 'crew') W.crewScreen.intro();
    else each(function (g) { if (g.onResume) g.onResume(); });
  };
  function openGrownups() { W.pause('grown-ups'); MW.grownups.openPanel(); }

  // ---------------------------------------------------------------- home: the map
  // "Welcome to MeeMee World!" the first time in a visit. Every game is told (onHome) so it can tidy up.
  W.home = function () {
    st.token++;
    MW.audio.hush();                                          // nothing from the last screen carries on over the map
    if (W.crewScreen) W.crewScreen.dragger.cancel();
    each(function (g) { if (g.onHome) g.onHome(); });
    st.phase = 'map';                                         // after the games have tidied up, whatever they did
    W.map.setCrew(MW.crew.jobs());
    MW.shell.show('screen-map');
    if (!st.welcomed) { st.welcomed = true; W.speak([['map-welcome']]); }
    if (!MW.crew.ready()) W.map.callCrew();                  // no jobs yet: the cats hop, to say "tap us"
  };

  // A game's planet: say its name ("MeeMee Rescue!"), then start it.
  async function open(g) {
    if (st.phase !== 'map' || st.paused) return;
    st.phase = 'opening';
    const token = ++st.token;
    W.map.bounce(g.planet);
    MW.log('map', g.id);
    await W.speak([[g.say]]);
    if (token !== st.token) return;
    if (st.paused) { st.phase = 'map'; return; }             // the grown-ups area opened (or the screen went off) meanwhile
    try { g.start(); } catch (e) {
      MW.log('game-error', g.id + ': ' + e); console.error('MeeMee World: ' + g.id + ':', e);
      W.home();
    }
  }
  function notReady() {
    if (st.phase !== 'map' || st.paused) return;
    MW.log('map', 'locked');
    W.speak([['map-not-ready']]);
  }
  // The crew screen: "Let's give the crew their jobs!" The player drags each cat onto a job.
  function openCrew() {
    if (st.phase !== 'map' || st.paused) return;
    st.token++;
    st.phase = 'crew';
    MW.log('map', 'crew');
    MW.shell.show('screen-crew');
    W.crewScreen.enter();
  }

  // ---------------------------------------------------------------- the start screen
  function buildStart() {
    const s = MW.$('screen-start');
    s.appendChild(MW.make('div', 'mw-abs label mw-caption', { style: 'left:40px;top:34px' }, 'MeeMee World'));
    const p = MW.pod(s, 240, 150, 420);
    p.el.disabled = true; p.el.tabIndex = -1;
    const play = MW.make('button', 'mw-btn mw-btn--play mw-abs mw-pulse', { type: 'button', 'aria-label': 'Play', id: 'play', style: 'left:820px;top:300px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    play.appendChild(icon);
    MW.onTap(play, function () { MW.audio.unlock(); MW.shell.fullscreen(); W.home(); });
    // If a browser didn't count the finger lifting as a tap for full screen, the click that follows tries again.
    play.addEventListener('click', function () { MW.audio.unlock(); if (MW.device.fullOk === false) MW.shell.fullscreen(); });
    s.appendChild(play);
    const row = MW.make('div', 'mw-abs mw-start-mimi', { style: 'left:770px;top:520px' });
    for (let i = 0; i < 3; i++) row.appendChild(MW.art('mimi'));
    s.appendChild(row);
    MW.shell.buttons(s, ['music'], {});
  }

  // ---------------------------------------------------------------- set-up, once every game has joined
  function init() {
    const stageEl = MW.$('stage');
    MW.stage.init(stageEl);
    buildStart();
    const mapEl = MW.$('screen-map');
    W.map = MW.map(mapEl, {
      games: W.games.map(function (g) { return { planet: g.planet, badge: g.badge, name: g.name, onOpen: function () { open(g); } }; }),
      onLocked: notReady,
      onCrew: openCrew
    });
    MW.shell.buttons(mapEl, ['music'], {});
    W.crewScreen = MW.crew.screen(MW.$('screen-crew'), {
      speak: W.speak,
      onHome: W.home,
      enabled: function () { return !st.paused && MW.shell.screen === 'screen-crew'; }
    });
    each(function (g) { g.build(); });
    MW.shell.gate(stageEl, openGrownups);
    MW.grownups.init(stageEl, {
      title: 'Grown-ups',
      sections: [].concat.apply([], W.games.map(function (g) { return g.sections || []; })),
      onClose: function () { W.resume('grown-ups'); }
    });
    MW.shell.watchSideways(function () { W.pause('sideways'); }, function () { W.resume('sideways'); });
    // The screen going off, or switching to another app, pauses; it carries on when it comes back.
    document.addEventListener('visibilitychange', function () { if (document.hidden) W.pause('hidden'); else W.resume('hidden'); });
    each(function (g) { if (g.init) g.init(); });
    MW.shell.registerOffline();
    MW.audio.preloadAll();
    MW.shell.show('screen-start');
    window.addEventListener('load', function () {
      const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
      MW.device.loadMs = nav ? Math.round(nav.loadEventStart || performance.now()) : Math.round(performance.now());
    });
  }
  // The games' scripts come after this one in the page (each in its own <script>, so a mistake in one game's code
  // leaves the others working), so wait for the page to finish loading them.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else setTimeout(init, 0);
})();
