/* MeeMee World kit: the world shell (phase 5; title banners from 0.6.0).
   What every game shares, so a game is only its own play:
     the start screen (Play: sound and full screen start on that first tap), the home map with a place for each game,
     the title banners (the set's name as the map first opens, a game's as its place is tapped), the crew screen,
     pausing (grown-ups area open, tablet upright, screen off), the grown-ups area, and updates.
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

  // ---------------------------------------------------------------- title banners (TitleBanner)
  // The set's or a game's name on a plaque, the only words the player sees apart from numerals and the letters being
  // practised, and always spoken with it (MEEMEE.md): so a banner shows only when its line is recorded (a line still
  // pending gives no banner, and the game starts straight away). It stays for its line and at least about 2 seconds, then goes by
  // itself; taps under it do nothing (the grown-ups lock still works). It fades and grows in over 260 ms and fades out
  // over 260 ms (a fade only, with reduce motion). Pausing or going Home takes it away at once.
  const BANNER = W.BANNER = { min: 2000, fade: 260, top: 292,
    sparks: [[300, -12, 1.4], [985, 168, 1.1], [1000, -22, 0.8]],     // x, y below the plaque's top, size (round 8 boards)
    art: { mimi: 104 }, gameArt: 112, worldArt: 96 };                // a kit drawing, a game's own badge, the MeeMee at each end
  let banner = null, bannerRun = null;
  function buildBanner(stageEl) {
    const el = MW.make('div', 'mw-banner', { id: 'banner' });
    const card = MW.make('div', 'mw-banner-card');
    const row = MW.make('div', 'mw-banner-row');
    const plaque = MW.make('div', 'mw-banner-plaque', { role: 'img' });
    row.appendChild(plaque);
    card.appendChild(row);
    BANNER.sparks.forEach(function (s) {
      const sp = MW.make('div', 'mw-banner-spark mw-abs');
      sp.style.left = (s[0] - 14 * s[2]) + 'px'; sp.style.top = (BANNER.top + s[1] - 14 * s[2]) + 'px';
      sp.style.transform = 'scale(' + s[2] + ')';
      const a = MW.art('spark'); a.setAttribute('width', 28); a.setAttribute('height', 28);
      sp.appendChild(a);
      card.appendChild(sp);
    });
    el.appendChild(card);
    // taps under it do nothing (it is above every screen, below the grown-ups lock)
    ['pointerdown', 'pointerup', 'click'].forEach(function (type) { el.addEventListener(type, function (e) { e.stopPropagation(); e.preventDefault(); }); });
    stageEl.appendChild(el);
    function art(name, size) {
      const a = MW.art(name); a.setAttribute('width', size); a.setAttribute('height', size);
      const box = MW.make('div', 'mw-banner-art', { 'data-art': name }); box.appendChild(a);
      return box;
    }
    let timer = 0;
    return {
      el: el,
      // info: { name, left: drawing, right: drawing or null, size: drawn size }
      show: function (info) {
        clearTimeout(timer);
        plaque.innerHTML = '';
        plaque.setAttribute('aria-label', info.name);
        plaque.appendChild(art(info.left, info.size));
        plaque.appendChild(MW.make('span', 'mw-banner-name banner', null, MW.esc(info.name)));
        if (info.right) plaque.appendChild(art(info.right, info.size));
        el.classList.remove('is-in', 'is-going');
        el.classList.add('is-up');
        void el.offsetWidth;                                  // start the fade from the beginning
        el.classList.add('is-in');
      },
      hide: function () {
        if (!el.classList.contains('is-up') || el.classList.contains('is-going')) return;
        el.classList.add('is-going');
        el.classList.remove('is-in');
        clearTimeout(timer);
        timer = setTimeout(function () { el.classList.remove('is-up', 'is-going'); }, BANNER.fade);
      },
      up: function () { return el.classList.contains('is-up'); }
    };
  }
  // Show a banner while its line is said. Resolves true once the banner has gone by itself, or false straight away if
  // a pause or Home took it away first.
  async function titleBanner(info, lines) {
    if (bannerRun) bannerRun.cancelled = true;
    const run = bannerRun = { cancelled: false };
    const shownAt = performance.now();
    banner.show(info);
    MW.log('banner', 'up ' + info.name);
    await MW.audio.say(lines);                                // a pause hushes it; a line not recorded yet says nothing
    while (!run.cancelled && performance.now() - shownAt < BANNER.min) await MW.wait(40);
    if (run.cancelled) return false;
    banner.hide();
    MW.log('banner', 'going ' + info.name);
    await MW.wait(BANNER.fade);
    if (run.cancelled) return false;
    bannerRun = null;
    MW.log('banner', 'gone ' + info.name);
    return true;
  }
  function cancelBanner() {
    if (bannerRun) { bannerRun.cancelled = true; bannerRun = null; MW.log('banner', 'cancelled'); }
    if (banner) banner.hide();
  }
  W.banner = { up: function () { return !!banner && banner.up(); }, cancel: cancelBanner };

  // ---------------------------------------------------------------- pausing
  // Reasons: the grown-ups area is open, the tablet is upright, or the page is hidden (screen off, another app).
  // The world carries on only when none is left; then each game picks up where it was (usually: ask again).
  W.pause = function (why) {
    st.pauses[why] = true;
    st.paused = true;
    cancelBanner();                                           // a banner goes; opening a planet stops on the map
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
  // The first time in a visit (after Play): MeeMee World's banner, with "Welcome to MeeMee World!". Every game is told
  // (onHome) so it can tidy up.
  W.home = function () {
    st.token++;
    cancelBanner();
    MW.audio.hush();                                          // nothing from the last screen carries on over the map
    if (W.crewScreen) W.crewScreen.dragger.cancel();
    each(function (g) { if (g.onHome) g.onHome(); });
    st.phase = 'map';                                         // after the games have tidied up, whatever they did
    W.map.setCrew(MW.crew.jobs());
    MW.shell.show('screen-map');
    if (!st.welcomed) { st.welcomed = true; welcome(); return; }
    if (!MW.crew.ready()) W.map.callCrew();                  // no jobs yet: the cats hop, to say "tap us"
  };
  // MeeMee World's banner: the planets and the crew wait until it has gone (or a pause took it away).
  async function welcome() {
    const token = st.token;
    if (!MW.audio.recorded('map-welcome')) { if (!MW.crew.ready()) W.map.callCrew(); return; }   // no line, no banner
    st.phase = 'welcome';
    await titleBanner({ name: 'MeeMee World', left: 'mimi', right: 'mimi', size: BANNER.worldArt }, [['map-welcome']]);
    if (token !== st.token || st.phase !== 'welcome') return;
    st.phase = 'map';
    if (!MW.crew.ready()) W.map.callCrew();
  }

  // A game's planet: its banner while its name is said ("MeeMee Rescue!"), then, once the banner has gone, the game.
  // The name and badge come from its game.json; a kit drawing as the badge (the MeeMee) is drawn at its design-system
  // size, a game's own badge (drawn in a 100 x 100 box) at 112.
  async function open(g) {
    if (st.phase !== 'map' || st.paused) return;
    st.phase = 'opening';
    const token = ++st.token;
    W.map.bounce(g.planet);
    MW.log('map', g.id);
    if (MW.audio.recorded(g.say)) {                          // a name not recorded yet: no banner, the game starts at once
      const gone = await titleBanner({ name: g.name, left: g.badge, size: BANNER.art[g.badge] || BANNER.gameArt }, [[g.say]]);
      if (token !== st.token) return;
      if (!gone || st.paused) { st.phase = 'map'; return; }   // a pause took the banner away: stay on the map
    } else MW.log('banner', 'none for ' + g.name + ' (' + g.say + ' not recorded yet)');
    try { g.start(); } catch (e) {
      MW.log('game-error', g.id + ': ' + e); console.error('MeeMee World: ' + g.id + ':', e);
      W.home();
    }
  }
  // A place with no game yet: "That place isn't ready yet." (0.8.0). While that line is still pending, the older
  // "That planet isn't ready yet." says it instead, so a tap is never silent (checked before the call: say() skips a
  // line that isn't recorded, and stops whatever was being said first).
  function notReady() {
    if (st.phase !== 'map' || st.paused) return;
    MW.log('map', 'locked');
    W.speak([[MW.audio.recorded('map-place-not-ready') ? 'map-place-not-ready' : 'map-not-ready']]);
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
  // Nothing to read: MeeMee World's name is shown (and said) by its banner after Play (decided 10 October 2026).
  function buildStart() {
    const s = MW.$('screen-start');
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
    banner = buildBanner(stageEl);
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
