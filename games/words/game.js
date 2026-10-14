/* MeeMee Rockets: the tricky-words game.
   A round is five words. Each word is found, then built, and earns a star:
     Find   three rockets on the launch pad, each with a word. "Find the word… one." He taps one.
     Build  the word's rocket lies on its side with empty portholes; its tiles are loose in the tray. "Now build the
            word… one." He drags the tiles into the portholes, left to right. In the sound tiles step a tile says its
            sound as it is picked up. The last tile lights the engines and the launch lights, and the rocket launches.
   The words, their tiles, sounds and spares are in words.js, by term, half-term and week; each word's step, what's in
   play and how rounds are chosen in steps.js; the crew's job moments in moments.js.
   It joins the world with MW.world.game below: the world gives it the start screen, the map, pausing, Home and the
   grown-ups area (its Words tab is at the end of this file). */
(function () {
  'use strict';
  const MW = window.MW;
  const W = MW.world;
  const S = MW.wordSteps;
  const ID = 'words';
  const FIND = 'screen-words-find', BUILD = 'screen-words-build', END = 'screen-words-end';
  const ROUND = 5;
  const PRAISE = ['words-found-it', 'words-super-reading', 'words-well-done'];

  // Where things go (stage px), from the round 6 boards. The drawings' own sizes are in art.py.
  const ROCKETS = { xs: [197, 490, 783], base: 693, at: [160, 560], panel: [49, 301.7, 222, 112.5], wordMax: 60 };   // art.py: ROCKET_AT, rocket_panel()
  const D = 104, GAP = 16, H = D + 84, NOSE = H * 0.82, BACK = [200, 70], NOSE_X = 12;   // the rocket on its side
  const SHIP = { x: 150, y: 195, right: 1250, slack: 34 };
  // The cargo tray: one place and size for every word, below the rocket and left of Scruffles. One row of tiles when
  // they fit; two rows of up to five when they don't (harder letters always).
  const TRAY = { x: 110, y: 462, w: 656, h: 290, pad: 28, gap: 20, perRow: 5, one: [150], two: [88, 212] };
  const POD = { find: [965, 337, 270], build: [951, 450, 290] };
  // The launch lights (LaunchLights card): 22 px lights along the hull's peach-dark stripe and its top edge, 92 apart,
  // the two rows half a step apart (rocket units, the hull's back top corner at 0, 0), numbered from the back to the nose
  // and split into three groups in turn. Each is on for a third of a second and off for two thirds; the groups start a
  // third of a second apart, so they chase from the back to the nose (game.css). Lit and steady with reduce motion.
  const LAMPS = { step: 92, rows: [[44, 168], [90, 15]], end: 25, groups: 3, stagger: 1000 / 3, art: 23 };

  const BOOK = S.read(MW.wordsData || { terms: [], words: {} });
  const st = { round: [], qi: 0, item: null, prompt: null, praise: [], timers: [], tapped: 0, drops: 0, hinted: false,
    trickySaid: false, rockets: [], tiles: [], places: [], next: 0, ship: null, plan: null,
    pool: null, choice: null, marks: null, repeat: null, pauses: 0, lamps: [] };
  const G = MW.wordsGame = { st: st, book: BOOK, nextRound: null };
  let findPod, buildPod, endPod, findStars, buildStars, endStars, findFx, buildFx, tileLayer, trayEl, shipLayer, dragger, again, endRockets;
  let moments = null;

  W.game({
    id: ID,
    build: function () {
      buildFind(); buildBuild(); buildEnd();
      moments = MW.wordsMoments({ find: MW.$(FIND), findBefore: findFx, build: MW.$(BUILD), routeBefore: shipLayer, buildBefore: buildFx,
        stars: buildStars, end: MW.$(END), endBefore: again });
      G.moments = moments;
    },
    start: function () { startRound(); },
    sections: [{ id: 'words-progress', title: 'Words', render: renderProgress }],
    onPause: function () { st.pauses++; clearTimers(); if (dragger) dragger.cancel(); },
    onResume: function () {                                     // carry on: ask again
      if ((MW.shell.screen === FIND && W.st.phase === 'words-find') || (MW.shell.screen === BUILD && W.st.phase === 'words-build')) {
        findPod.face('thinking'); buildPod.face('thinking');
        W.speak(st.prompt);
        // the pause cleared the lookout's duck: it ducks as it would have, once the first question has been asked again
        if (MW.shell.screen === FIND && moments.lookoutShown()) later(W.st.token, 1800, function () { moments.lookoutDown(); });
      }
    },
    onHome: leave,
    init: moveToStart
  });

  // ---------------------------------------------------------------- saved data (this game's own, on the tablet)
  // Read without creating it (MW.store.peek), so a tablet that has never played keeps nothing for this game.
  function saved() { return MW.store.peek(ID); }
  function answers() { return Array.isArray(saved().answers) ? saved().answers : []; }
  // What's in play, as a grown-up picked it in the Words tab and checked against the words file (S.choice): a week of a
  // half-term { half, week }, a half-term's weeks together { half, week: S.ALL }, or a whole term { term }. Nothing
  // picked, a choice saved before 0.7.0 (it has no half-term) or one the file no longer has: the file's start.
  function choice() { return S.choice(BOOK, saved()); }
  function week() { const c = choice(); return c.term ? null : c.week; }
  // The one-time move to the file's start (0.7.0, question 1): a tablet whose saved choice has no half-term in it (a
  // week or "all" saved by 0.6.0) moves to the start (Autumn 2, week 1), which is then saved; its answers stay as they
  // are. A tablet that has saved nothing for this game keeps nothing (it plays the start anyway).
  function moveToStart() {
    const v = saved();
    if (!Object.keys(v).length || (v.half !== undefined && v.half !== null) || (v.term !== undefined && v.term !== null)) return;
    const s = S.start(BOOK), g = MW.store.game(ID);
    g.half = s.half; g.week = s.week;
    MW.store.save();
    MW.log('words', 'moved to the start: ' + s.half + ' ' + s.week);
  }
  function recorded(w) { return MW.audio.recorded(line(w)); }
  function line(w) { return S.line(w); }
  // The words in play: the choice's words, once their recordings are on the page.
  function inPlay() { return S.inPlay(BOOK, choice()).filter(recorded); }
  // A round keeps the words, the choice and the marking it started with: a choice made in the grown-ups area starts
  // with the next round.
  function roundPool() { return st.pool || inPlay(); }
  function roundChoice() { return st.choice || choice(); }
  // Is a word marked tricky in the half-term in play (D1)? Where it isn't, none of its tiles is marked.
  function marked(w) { const m = (st.marks || S.marks(BOOK, roundChoice()))[w]; return m ? m.tricky : true; }

  // ---------------------------------------------------------------- the screens
  function buildFind() {
    const s = W.screen(FIND, 'MeeMee Rockets: find the word');
    const pad = MW.art('words-pad'); pad.classList.add('mw-layer'); s.appendChild(pad);
    st.rockets = ROCKETS.xs.map(function (cx, i) {
      const b = MW.make('button', 'words-rocket mw-abs', { type: 'button', 'aria-label': 'A rocket' });
      b.style.left = (cx - 135) + 'px'; b.style.top = '140px';
      const art = MW.art('words-rocket');
      art.setAttribute('class', 'words-rocket-art');
      art.style.left = (135 - ROCKETS.at[0]) + 'px'; art.style.top = (ROCKETS.base - ROCKETS.at[1] - 140) + 'px';
      b.appendChild(art);
      const p = ROCKETS.panel;
      const panel = MW.make('span', 'words-panel');
      panel.style.left = (p[0] + 135 - ROCKETS.at[0]) + 'px'; panel.style.top = (p[1] + ROCKETS.base - ROCKETS.at[1] - 140) + 'px';
      panel.style.width = p[2] + 'px'; panel.style.height = p[3] + 'px';
      const word = MW.make('span', 'words-panel-word');
      panel.appendChild(word);
      b.appendChild(panel);
      s.appendChild(b);
      const r = { el: b, wordEl: word, word: null, cx: cx, i: i };
      MW.onTap(b, function () { tapRocket(r); });
      return r;
    });
    findPod = MW.pod(s, POD.find[0], POD.find[1], POD.find[2]);
    MW.onTap(findPod.el, hearAgain);
    findStars = MW.stars(s, MW.LAYOUT.stars.cx, MW.LAYOUT.stars.y, null, { centre: true });   // centred, however many words
    findFx = MW.make('div', 'mw-layer mw-fill'); s.appendChild(findFx);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: hearAgain });
  }

  function buildBuild() {
    const s = W.screen(BUILD, 'MeeMee Rockets: build the word');
    trayEl = MW.make('div', 'words-tray mw-abs', { 'aria-hidden': 'true' });
    trayEl.style.left = TRAY.x + 'px'; trayEl.style.top = TRAY.y + 'px'; trayEl.style.width = TRAY.w + 'px'; trayEl.style.height = TRAY.h + 'px';
    trayEl.appendChild(MW.make('span', 'words-tray-light'));
    trayEl.appendChild(MW.make('span', 'words-tray-light words-tray-light--r'));
    s.appendChild(trayEl);
    shipLayer = MW.make('div', 'mw-layer mw-fill'); s.appendChild(shipLayer);
    buildPod = MW.pod(s, POD.build[0], POD.build[1], POD.build[2]);
    MW.onTap(buildPod.el, function () { if (!(dragger && dragger.dragging())) hearAgain(); });
    buildStars = MW.stars(s, MW.LAYOUT.stars.cx, MW.LAYOUT.stars.y, null, { centre: true });
    tileLayer = MW.make('div', 'mw-layer mw-fill words-tiles'); s.appendChild(tileLayer);
    buildFx = MW.make('div', 'mw-layer mw-fill'); s.appendChild(buildFx);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: hearAgain });
    dragger = MW.dragger(s, {
      counters: function () { return st.tiles.filter(function (c) { return !c.placed; }); },
      enabled: function () { return !W.st.paused && W.st.phase === 'words-build' && MW.shell.screen === BUILD; },
      onPick: function (c) { MW.log('pick', c.text); sayTile(c); },
      onDrop: onDrop                                           // each tile is picked up in its own box (makeTile)
    });
  }

  function buildEnd() {
    const s = W.screen(END, 'All the rockets launched');
    endStars = MW.stars(s, 640, 40, 60, { centre: true });
    endPod = MW.pod(s, 380, 120, 400); endPod.face('got-it'); endPod.el.disabled = true; endPod.el.tabIndex = -1;
    endRockets = MW.make('div', 'mw-abs words-end-rockets', { style: 'left:300px;top:590px' });
    s.appendChild(endRockets);
    again = MW.make('button', 'mw-btn mw-btn--play mw-abs', { type: 'button', 'aria-label': 'Another go', id: 'words-again', style: 'left:1080px;top:420px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    again.appendChild(icon);
    MW.onTap(again, function () { if (W.st.phase === 'words-done') { MW.audio.unlock(); MW.shell.fullscreen(); startRound(); } });
    s.appendChild(again);
    MW.shell.buttons(s, ['home', 'music'], { home: W.home });
  }

  function setStars(stars, done) { stars.set(done, st.round.length || ROUND); }

  // ---------------------------------------------------------------- a round
  function makeRound() {
    if (G.nextRound) {
      const r = G.nextRound; G.nextRound = null;
      const map = S.statuses(answers());
      return r.map(function (x) {
        const w = typeof x === 'string' ? x : x.word;
        const s = (typeof x === 'object' && x.step) || S.step(map, w);
        return { word: w, step: s === 'notyet' ? 'tiles' : s };
      });
    }
    const c = choice();
    if (S.wide(c)) return S.pickRound({ words: inPlay(), answers: answers(), size: ROUND, lowest: true });
    return S.pickRound({ words: inPlay(), answers: answers(), size: ROUND, own: S.ownWords(BOOK, c.half, c.week) });
  }

  async function startRound() {
    const token = ++W.st.token;
    clearBoard();
    st.round = makeRound();
    st.pool = inPlay();
    st.choice = choice();
    st.marks = S.marks(BOOK, st.choice);
    st.qi = 0;
    st.trickySaid = false;
    st.praise = [];
    MW.log('words', 'round ' + JSON.stringify(st.round));
    if (!st.round.length) {
      // nothing in the choice in play is recorded yet (a new half-term before its recordings): back to the map, and say
      // so with the world's own line, as the map does for a planet that isn't ready (kit/world.js, notReady)
      MW.log('words', 'no words in play');
      W.home();
      if (W.st.phase === 'map' && !W.st.paused) W.speak([['map-not-ready']]);
      return;
    }
    W.st.phase = 'words-starting';
    moments.clear();
    await fontReady();                                         // measure the words in bold Andika itself, not a stand-in
    if (token !== W.st.token) return;
    setFind(st.round[0]);
    MW.shell.show(FIND);
    moments.lookoutUp();                                       // the lookout peeks up from the bottom right
    await W.speak([['words-round-ready']]);
    if (!(await W.ok(token))) return;
    askFind();
  }

  function clearTimers() { st.timers.forEach(clearTimeout); st.timers = []; }
  function later(token, ms, fn) { st.timers.push(setTimeout(function () { if (token === W.st.token) fn(); }, ms)); }

  // ---------------------------------------------------------------- Find
  function setFind(item) {
    const words = S.choices(item.word, roundPool(), Math.random, 3);
    st.repeat = null;
    st.rockets.forEach(function (r, i) {
      r.word = words[i] || null;
      r.el.style.visibility = r.word ? '' : 'hidden';
      r.el.classList.remove('is-lit', 'is-hint');
      r.wordEl.textContent = r.word || '';
      r.el.setAttribute('aria-label', r.word ? 'The word ' + r.word : 'A rocket');
    });
    sizeWords();
    // the bold type not loaded yet (it should be, after fontReady): size the words again once it has
    if (!fontLoaded()) fontReady().then(sizeWords);
    findPod.face('thinking');
    findPod.lightsOff();
  }
  function sizeWords() {
    st.rockets.forEach(function (r) { r.wordEl.style.fontSize = fit(r.word || '', ROCKETS.panel[2] - 28, ROCKETS.wordMax) + 'px'; });
  }
  // The biggest size (up to max) at which a word fits the panel, in the game's own type (Andika, bold). It must be
  // measured in Andika itself: until the bold type has loaded, the browser measures a stand-in that is narrower.
  const FONT = '700 ' + ROCKETS.wordMax + 'px Andika';
  function fontLoaded() { try { return !document.fonts || document.fonts.check(FONT); } catch (e) { return true; } }
  function fontReady() {
    try { if (document.fonts && document.fonts.load) return document.fonts.load(FONT).then(function () {}, function () {}); } catch (e) { /* no font loading API */ }
    return Promise.resolve();
  }
  let measurer = null;
  function fit(word, width, max) {
    if (!word) return max;
    measurer = measurer || document.createElement('canvas').getContext('2d');
    measurer.font = '700 ' + max + 'px Andika';
    const w = measurer.measureText(word).width;
    return w > width ? Math.floor(max * width / w) : max;
  }

  // Ask the round's next word: Find first. (showFind sets the screen up; the tests use it on its own too.)
  async function askFind() {
    const token = W.st.token;
    showFind(st.round[st.qi]);
    if (st.qi === 0) later(token, 1800, function () { moments.lookoutDown(); });   // spotted them
    else moments.settle();
    await W.speak(st.prompt);
  }
  function showFind(item) {
    st.item = item;
    st.tapped = 0; st.drops = 0; st.hinted = false;
    if (!st.rockets.some(function (r) { return r.word === item.word; })) setFind(item);
    MW.shell.show(FIND);
    setStars(findStars, st.qi);
    st.prompt = [['words-find', line(item.word)]];
    W.st.phase = 'words-find';
    MW.log('words', 'find ' + item.word + ' among ' + st.rockets.map(function (r) { return r.word; }).join(' '));
  }

  function tapRocket(r) {
    if (W.st.paused || W.st.phase !== 'words-find' || !r.word) return;
    if (r.word === st.item.word) { found(r); return; }
    // the same wrong rocket again while it is still saying "That word is… my.": one try, not two (a double tap)
    if (st.repeat && st.repeat.r === r && performance.now() < st.repeat.until) { MW.log('words', 'tap ' + r.word + ' again (same try)'); return; }
    // a wrong tap: the word he tapped says itself, then "Let's try again." (and the question), or the hint
    st.tapped++;
    MW.log('words', 'tap ' + r.word + ' (wrong ' + st.tapped + ')');
    tryAgainFace(findPod);
    const lines = [['words-that-word', line(r.word)]];
    if (st.tapped === 1) lines.push(['words-try-again'], st.prompt[0]);
    else if (st.tapped === 2) {
      lines.push(['words-look-together']);
      st.hinted = true;
      st.rockets.forEach(function (x) { if (x.word === st.item.word) x.el.classList.add('is-hint'); });
      MW.log('words', 'hint ' + st.item.word);
    }
    // repeat taps on this rocket count as this try until "That word is… my." has been said (or is cut short)
    const repeat = st.repeat = { r: r, until: Infinity };
    W.speak(lines, {
      onStart: function (timeline) { const w = timeline[1]; repeat.until = performance.now() + (w.at + w.dur + 0.1) * 1000; }
    }).then(function () { repeat.until = 0; });
  }
  function tryAgainFace(pod) {
    pod.face('try-again');
    const token = W.st.token, qi = st.qi;
    later(token, 1600, function () { if (qi === st.qi && (W.st.phase === 'words-find' || W.st.phase === 'words-build')) pod.face('thinking'); });
  }

  async function found(r) {
    const token = W.st.token;
    W.st.phase = 'words-found';
    MW.log('words', 'found ' + r.word);
    r.el.classList.remove('is-hint');
    r.el.classList.add('is-lit');                             // the engines light
    MW.audio.sfx('chime');
    findPod.face('got-it');
    findPod.celebrate();
    MW.sparkles(findFx, r.cx, 420, 175);
    if (!moments.engineer(r.cx)) moments.lookoutDown();        // the engineer taps the rocket's clamp
    await MW.wait(550);
    if (!(await W.ok(token))) return;
    st.praise = st.praise.length ? st.praise : MW.shuffle(PRAISE);
    await W.speak([[st.praise.pop()]]);
    if (!(await W.ok(token))) return;
    await MW.wait(300);
    if (!(await W.ok(token))) return;
    askBuild();
  }

  // ---------------------------------------------------------------- Build
  function tileW(k) { return k === 1 ? D : D + (k - 1) * 0.46 * D; }
  function kOf(text, mode) { return mode === 'tiles' ? Math.min(text.length, 4) : 1; }

  function clearBoard() {
    if (dragger) dragger.cancel();
    clearTimers();
    st.tiles.forEach(function (c) { c.remove(); });
    st.tiles = []; st.places = []; st.next = 0; st.plan = null; st.lamps = [];
    if (st.ship) { st.ship.el.remove(); st.ship = null; }
  }

  // The rocket on its side, made for this word: the back, as much hull as its portholes need, the nose, a socket per
  // place. Scaled down only if a long word would run off the stage.
  function makeShip(places, mode) {
    const widths = places.map(function (p) { return tileW(kOf(p.text, mode)); });
    const L = widths.reduce(function (a, b) { return a + b; }, 0) + GAP * (widths.length - 1) + 96;
    const scale = Math.min(1, (SHIP.right - SHIP.x) / (L + NOSE));
    const el = MW.make('div', 'words-ship mw-abs');
    el.style.left = SHIP.x + 'px'; el.style.top = SHIP.y + 'px';
    el.style.width = ((L + NOSE) * scale) + 'px'; el.style.height = (H * scale) + 'px';
    const inner = MW.make('div', 'words-ship-inner');
    inner.style.transform = 'scale(' + scale + ')';
    el.appendChild(inner);
    const back = MW.art('words-ship-back');
    back.setAttribute('class', 'words-part'); back.style.left = (-BACK[0]) + 'px'; back.style.top = (-BACK[1]) + 'px';
    inner.appendChild(back);
    const hull = MW.art('words-ship-hull');
    hull.setAttribute('class', 'words-part');
    hull.setAttribute('width', L + 4); hull.setAttribute('height', H + 8);
    hull.setAttribute('viewBox', '-4 -4 ' + (L + 4) + ' ' + (H + 8));
    hull.style.left = '-4px'; hull.style.top = '-4px';
    inner.appendChild(hull);
    const nose = MW.art('words-ship-nose');
    nose.setAttribute('class', 'words-part'); nose.style.left = (L - NOSE_X) + 'px'; nose.style.top = '0px';
    inner.appendChild(nose);
    st.lamps = makeLamps(inner, L);
    const slots = [];
    let x = 78;
    widths.forEach(function (w, i) {
      const sock = MW.art('words-socket-' + kOf(places[i].text, mode));
      sock.setAttribute('class', 'words-part'); sock.style.left = (x - 8) + 'px'; sock.style.top = (H / 2 - D / 2 - 8) + 'px';
      inner.appendChild(sock);
      slots.push({ x: x + w / 2, y: H / 2 });                // its middle, in the rocket's own units
      x += w + GAP;
    });
    shipLayer.appendChild(el);
    return { el: el, inner: inner, scale: scale, L: L, slots: slots,
      box: { x: SHIP.x, y: SHIP.y, w: (L + NOSE) * scale, h: H * scale } };
  }
  // The launch lights along this rocket's hull (LAMPS): off until the engines light, then the groups chase (game.css).
  function makeLamps(inner, L) {
    const pts = [];
    LAMPS.rows.forEach(function (row) { for (let x = row[0]; x < L - LAMPS.end; x += LAMPS.step) pts.push([x, row[1]]); });
    pts.sort(function (a, b) { return a[0] - b[0]; });
    return pts.map(function (p, i) {
      const lamp = MW.art('words-lamp');
      const g = i % LAMPS.groups;
      lamp.setAttribute('class', 'words-part words-lamp');
      lamp.setAttribute('data-group', g);
      lamp.style.left = (p[0] - LAMPS.art) + 'px'; lamp.style.top = (p[1] - LAMPS.art) + 'px';
      lamp.querySelector('.words-lamp-on').style.animationDelay = Math.round(g * LAMPS.stagger) + 'ms';
      inner.appendChild(lamp);
      return { x: p[0], y: p[1], group: g, el: lamp };
    });
  }
  function onShip(x, y) {
    const b = st.ship.box;
    return x >= b.x - SHIP.slack && x <= b.x + b.w + SHIP.slack && y >= b.y - SHIP.slack && y <= b.y + b.h + SHIP.slack;
  }

  function makeTile(t, k) {
    const w = tileW(k);
    const el = MW.make('div', 'words-tile' + (t.tricky ? ' is-tricky' : ''), { role: 'img', 'aria-label': t.text });
    el.style.width = w + 'px'; el.style.height = D + 'px';
    el.style.marginLeft = (-w / 2) + 'px'; el.style.marginTop = (-D / 2) + 'px';
    const body = MW.make('div', 'words-tile-body');
    body.appendChild(MW.art('words-tile-' + k));
    body.appendChild(MW.make('span', 'words-tile-text', null, MW.esc(t.text)));
    el.appendChild(body);
    tileLayer.appendChild(el);
    // its pick-up box (MW.dragger): 10 px each side, so neighbours' boxes meet halfway across the tray's 20 px gap and a
    // finger anywhere on a long tile picks that tile; 20 px above and below, for a forgiving pick-up
    const c = { el: el, text: t.text, tricky: t.tricky, spare: t.spare, sound: t.sound || null, k: k, w: w, x: 0, y: 0, draggable: true,
      placed: false, home: null, grab: { w: w + TRAY.gap, h: D + 40 } };
    c.moveTo = function (x, y, size, animate) {
      c.x = x; c.y = y;
      el.classList.toggle('is-moving', !!animate && !MW.reduceMotion);
      el.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
    };
    c.lift = function (on) { c.lifted = !!on; el.classList.toggle('is-lifted', !!on); };
    c.glow = function (on) { el.classList.toggle('is-glow', !!on); };
    c.remove = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    return c;
  }

  // The tiles in the tray: one row while they fit (up to five); otherwise two rows of up to five, and always two for
  // harder letters. Each tile keeps its own place in the tray; the tray itself never moves.
  function layTray(tiles) {
    const inner = TRAY.w - 2 * TRAY.pad;
    const rowWidth = function (row) { return row.reduce(function (a, c) { return a + c.w; }, 0) + TRAY.gap * Math.max(0, row.length - 1); };
    const one = st.plan.mode !== 'harder' && tiles.length <= TRAY.perRow && rowWidth(tiles) <= inner;
    const half = Math.ceil(tiles.length / 2);
    const rows = one ? [tiles] : [tiles.slice(0, half), tiles.slice(half)];
    const ys = one ? TRAY.one : TRAY.two;
    rows.forEach(function (row, ri) {
      let x = TRAY.x + TRAY.pad;
      row.forEach(function (c) {
        c.home = { x: x + c.w / 2, y: TRAY.y + ys[ri] };
        c.moveTo(c.home.x, c.home.y, 0, false);
        x += c.w + TRAY.gap;
      });
    });
  }

  async function askBuild() {
    showBuild(st.item);
    await W.speak(st.prompt);
  }
  function showBuild(item) {
    st.item = item;
    clearBoard();
    st.plan = S.plan(BOOK, item.word, item.step, S.fillFrom(BOOK, roundChoice(), item.word, roundPool()), Math.random, marked(item.word));
    st.places = st.plan.places;
    st.next = 0;
    st.drops = 0;
    st.ship = makeShip(st.places, st.plan.mode);
    st.tiles = st.plan.tray.map(function (t) { return makeTile(t, kOf(t.text, st.plan.mode)); });
    layTray(st.tiles);
    buildPod.face('thinking');
    buildPod.lightsOff();
    MW.shell.show(BUILD);
    setStars(buildStars, st.qi);
    st.prompt = [['words-build', line(item.word)]];
    W.st.phase = 'words-build';
    MW.log('words', 'build ' + item.word + ' ' + st.plan.mode + ': ' + st.plan.tray.map(function (t) { return t.text; }).join(' '));
  }

  function onDrop(c, x, y, cancelled) {
    if (st.tiles.indexOf(c) < 0 || c.placed) return;           // left over from a word that has ended
    if (cancelled || W.st.paused || W.st.phase !== 'words-build') { floatHome(c); return; }
    if (!onShip(x, y)) {                                        // not on the word: back to the tray, not a try
      const far = Math.hypot(x - c.home.x, y - c.home.y) > 70;
      floatHome(c);
      if (far) MW.audio.sfx('whoosh');
      return;
    }
    const need = st.places[st.next];
    if (c.text === need.text) { place(c, x, y); return; }    // a tile with the same letters is just as good
    floatHome(c);
    MW.audio.sfx('whoosh');
    wrongDrop(c);
  }
  function floatHome(c) { c.moveTo(c.home.x, c.home.y, 0, true); }

  // In the sound tiles step only, a tile says its sound as it is picked up, once per pick-up (not again as it snaps in).
  // A recorded sound stops anything being said; one not recorded yet does nothing and stops nothing; the e of a split
  // pair says nothing (answers 13, 21 and 22 of the 0.6.0 PRD).
  function sayTile(c) {
    if (!st.plan || st.plan.mode !== 'tiles') return;
    const id = S.soundLine(soundOf(c));
    if (!id) { MW.log('words', 'sound ' + c.text + ': none'); return; }
    if (!MW.audio.recorded(id)) { MW.log('words', 'sound ' + id + ' not recorded yet'); return; }
    MW.log('words', 'sound ' + id);
    W.speak([[id]]);
  }

  // What a tile says as it is picked up. Tiles with the same letters are just as good as each other, so where a word has
  // a tile twice that says different things (0.7.0: "these", "even"), the one picked up says the sound of the next place
  // still waiting for those letters, left to right: the first e of "these" placed says "ee", the other says nothing.
  function soundOf(c) {
    for (let i = st.next; i < st.places.length; i++) if (st.places[i].text === c.text) return st.places[i].sound;
    return c.sound;
  }

  function wrongDrop(c) {
    st.drops++;
    MW.log('words', 'drop ' + c.text + ' (wrong ' + st.drops + (c.spare ? ', a spare' : '') + ')');
    tryAgainFace(buildPod);
    if (st.drops === 1) { W.speak([['words-try-again']]); return; }
    // the second wrong drop: "Let's look together." and the next tile glows; after that, each wrong drop lights it again
    st.hinted = true;
    hintTile();
    if (st.drops === 2) W.speak([['words-look-together']]);
  }
  function hintTile() {
    const need = st.places[st.next];
    const free = st.tiles.filter(function (t) { return !t.placed && t.text === need.text; });
    const pick = free.filter(function (t) { return t.tricky === need.tricky; })[0] || free[0];
    st.tiles.forEach(function (t) { t.glow(t === pick); });
    if (pick) MW.log('words', 'hint ' + pick.text);
  }

  function place(c, x, y) {
    const i = st.next;
    const ship = st.ship, slot = ship.slots[i], need = st.places[i];
    c.placed = true; c.draggable = false;
    st.tiles.forEach(function (t) { t.glow(false); });
    MW.audio.sfx('pop');
    // into the rocket: from where it was dropped to its porthole (it now moves with the rocket)
    ship.inner.appendChild(c.el);
    c.el.classList.add('is-set');
    c.el.classList.toggle('is-tricky', need.tricky);          // the place's marking (a same-letter spare takes it)
    c.moveTo((x - SHIP.x) / ship.scale, (y - SHIP.y) / ship.scale, 0, false);
    void c.el.offsetWidth;
    c.moveTo(slot.x, slot.y, 0, true);
    st.next++;
    MW.log('words', 'place ' + c.text + ' ' + st.next + ' of ' + st.places.length);
    const tricky = need.tricky && !st.trickySaid;
    if (tricky) st.trickySaid = true;                          // "That's the tricky bit." once a round
    if (st.next === st.places.length) { built(tricky); return; }
    if (tricky) W.speak([['words-tricky-bit']]);
  }

  async function built(tricky) {
    const token = W.st.token, item = st.item;
    W.st.phase = 'words-built';
    clearTimers();
    record(item);
    buildPod.face('got-it');
    buildPod.celebrate();
    MW.audio.sfx('chime');
    await MW.wait(280);                                         // the last tile settles, then the engines light
    if (!(await W.ok(token))) return;
    st.ship.el.classList.add('is-launch');
    MW.sparkles(buildFx, SHIP.x + st.ship.box.w / 2, SHIP.y + st.ship.box.h / 2 - 40, Math.min(330, st.ship.box.w / 2));
    if (tricky) {
      await W.speak([['words-tricky-bit']]);
      if (!(await W.ok(token))) return;
    }
    if (!(await sayThrough([['words-you-built', line(item.word)]], token))) return;
    setStars(buildStars, st.qi + 1);
    MW.audio.sfx('twinkle');
    moments.navigator(st.qi + 1 < st.round.length ? st.qi + 1 : null);   // the navigator points the way to the next star
    await MW.wait(700);
    if (!(await W.ok(token))) return;
    st.ship.el.classList.add('is-away');                       // off it goes
    await MW.wait(1300);
    if (!(await W.ok(token))) return;
    st.qi++;
    if (st.qi < st.round.length) {
      setFind(st.round[st.qi]);
      askFind();
    } else endRound(token);
  }

  // Say lines to the end: if a pause cuts them off, say them again once it is over. False if the player left.
  async function sayThrough(lines, token) {
    for (;;) {
      const pauses = st.pauses;
      const heard = await W.speak(lines);
      if (!(await W.ok(token))) return false;
      if (heard || st.pauses === pauses) return true;          // said, or can't be (not recorded yet): carry on
    }
  }

  function record(item) {
    const a = { t: Date.now(), w: item.word, step: item.step, mode: st.plan.mode, tapped: st.tapped, drops: st.drops, hint: st.hinted };
    const g = MW.store.game(ID);
    g.answers = Array.isArray(g.answers) ? g.answers : [];
    g.answers.push(a);
    if (g.answers.length > 3000) g.answers.splice(0, g.answers.length - 3000);
    MW.store.save();
    MW.log('words', 'built ' + JSON.stringify(a));
  }

  // ---------------------------------------------------------------- the end of a round
  async function endRound(token) {
    W.st.phase = 'words-done';
    clearBoard();
    MW.shell.show(END);
    const n = st.round.length;
    endStars.set(n, n);
    endRockets.innerHTML = '';
    for (let i = 0; i < n; i++) {
      const r = MW.make('div', 'words-end-rocket');
      r.appendChild(MW.art('words-rocket-mini'));
      r.style.animationDelay = (i * 160) + 'ms';
      endRockets.appendChild(r);
    }
    endRockets.style.left = Math.round(580 - (100 * n + 24 * (n - 1)) / 2) + 'px';
    again.classList.remove('mw-pulse');
    MW.audio.sfx('tune');
    endPod.celebrate();
    await MW.wait(300);
    if (!(await W.ok(token))) return;
    await W.speak([['words-round-done']]);
    if (!(await W.ok(token))) return;
    await MW.wait(500);
    if (!(await W.ok(token))) return;
    if (moments.cook()) {                                      // the cook brings a pan of fish for the MeeMee
      await MW.wait(1300);
      if (!(await W.ok(token))) return;
    }
    again.classList.add('mw-pulse');                           // tap here for another go
    await W.speak([['words-round-another']]);
  }

  function hearAgain() {
    if (W.st.paused) return;
    if (W.st.phase === 'words-find' || W.st.phase === 'words-build') W.speak(st.prompt);
  }

  // Home (from any screen, this game's or the world's): put everything away. The world has moved the token on.
  function leave() {
    clearBoard();
    st.rockets.forEach(function (r) { r.el.classList.remove('is-lit', 'is-hint'); });
    [findPod, buildPod, endPod].forEach(function (p) { if (p) p.lightsOff(); });
    if (again) again.classList.remove('mw-pulse');
    if (moments) moments.clear();
    st.item = null; st.prompt = null; st.pool = null; st.choice = null; st.marks = null; st.repeat = null;
  }

  // ---------------------------------------------------------------- grown-ups: the Words tab
  const TAGS = { tiles: 'ay', letters: 'a·y', harder: 'a·y+' };
  function cell(step, text) {
    const c = MW.make('span', 'words-cell is-' + step);
    if (step === 'secure') {
      const tick = MW.art('icon-tick'); tick.setAttribute('width', 16); tick.setAttribute('height', 16);
      c.appendChild(tick);
    } else if (TAGS[step]) c.appendChild(MW.make('span', 'words-tag', null, TAGS[step]));
    c.appendChild(document.createTextNode(text));
    return c;
  }
  function weeksText(list) {
    if (list.length === 1) return 'Week ' + list[0];
    const run = list.every(function (w, i) { return i === 0 || w === list[i - 1] + 1; });
    return 'Weeks ' + (run ? list[0] + ' to ' + list[list.length - 1] : list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1]);
  }
  const COUNT = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];
  // The grown-up's choice, saved on the tablet (it starts with the next round). The saved half-term and week stay
  // while a whole term is on, so picking a half-term again goes back to them.
  function pickHalf(GU, h) {
    const c = choice(), g = MW.store.game(ID);
    const prev = c.term ? saved().week : c.week;
    // the same week in this half-term if it has one (or its weeks together), otherwise its first week
    const keep = prev === S.ALL ? !!S.allLabel(h) : !!S.weekOf(h, +prev);
    delete g.term;
    g.half = h.id;
    g.week = keep ? (prev === S.ALL ? S.ALL : +prev) : (h.weeks.length ? h.weeks[0].week : null);
    MW.store.save();
    MW.log('words', 'half ' + h.id + ' ' + g.week);
    GU.show('words-progress');
  }
  function pickTerm(GU, tm) {
    const c = choice(), g = MW.store.game(ID);
    if (!c.term) { g.half = c.half; g.week = c.week; }
    g.term = tm.id;
    MW.store.save();
    MW.log('words', 'term ' + tm.id);
    GU.show('words-progress');
  }
  function pickWeek(GU, h, value) {
    const g = MW.store.game(ID);
    delete g.term;
    g.half = h.id; g.week = value;
    MW.store.save();
    MW.log('words', 'week ' + value);
    GU.show('words-progress');
  }
  function renderProgress(el) {
    const GU = MW.grownups;
    const map = S.statuses(answers());
    const c = choice();
    const term = c.term ? S.term(BOOK, c.term) : null;
    const half = term ? null : S.half(BOOK, c.half);
    const all = S.wide(c);
    const wk = term ? null : c.week;
    const allLabel = S.allLabel(half);
    const marks = S.marks(BOOK, c);
    // the half-terms, each term's after its half-terms ("Autumn 1", "Autumn 2", "All of autumn"), named from the file
    GU.h3(el, 'Half-term');
    const hr = GU.row(el);
    BOOK.terms.forEach(function (tm) {
      tm.halves.forEach(function (h) {
        GU.btn(hr, h.name, function () { pickHalf(GU, h); }, 'gu-choice words-half' + (half && h.id === half.id ? ' is-on' : ''));
      });
      const label = S.termLabel(tm);
      if (label) GU.btn(hr, label, function () { pickTerm(GU, tm); }, 'gu-choice words-half words-term' + (term && term.id === tm.id ? ' is-on' : ''));
    });
    // the picked half-term's weeks, then all of them together ("Weeks 1–5"); not shown with a whole term on
    if (half) {
      GU.h3(el, 'Week in play');
      const r = GU.row(el);
      half.weeks.forEach(function (x) {
        GU.btn(r, 'Week ' + x.week, function () { pickWeek(GU, half, x.week); }, 'gu-choice words-week' + (x.week === wk ? ' is-on' : ''));
      });
      if (allLabel) GU.btn(r, allLabel, function () { pickWeek(GU, half, S.ALL); }, 'gu-choice words-week words-week-all' + (wk === S.ALL ? ' is-on' : ''));
    }
    if (term) {
      const n = term.halves.length;
      GU.p(el, MW.esc(term.all) + ' plays every word from ' + (n === 2 ? 'both half-terms' : 'all ' + (COUNT[n] || n) + ' half-terms') + ', '
        + S.inPlay(BOOK, c).length + ' in all, leaning on the ones that need the most work. A change starts with the next round.', 'gu-note');
    } else if (all) {
      const n = half.weeks.length;
      GU.p(el, MW.esc(allLabel) + ' plays every word from all ' + (COUNT[n] || n) + ' weeks, leaning on the ones that need the most work. '
        + 'A change starts with the next round.', 'gu-note');
    } else if (half) {
      const tricky = half.weeks.filter(function (x) { return !x.other.length; }).map(function (x) { return x.week; });
      GU.p(el, MW.esc(half.name) + ', week ' + wk + ': this week\'s words, then the tricky words of the weeks before it. '
        + (tricky.length ? weeksText(tricky) + ': tricky words only until their other words are recorded. ' : '') + 'A change starts with the next round.', 'gu-note');
    }
    // nothing in the choice in play recorded yet: the game won't start (it says "That planet isn't ready yet.")
    if (S.inPlay(BOOK, c).length && !inPlay().length) {
      const what = term ? term.name : half.name + ', ' + (all ? allLabel : 'week ' + wk);
      GU.p(el, 'Nothing in ' + MW.esc(what) + ' is recorded yet, so MeeMee Rockets won\'t start until it is.', 'gu-note');
    }

    // the grid: each word once, with its step
    const grid = MW.make('div', 'words-grid');
    const shown = {};
    const row = function (label, words) {
      words = words.filter(function (w, i, list) { return BOOK.words[w] && !shown[w] && list.indexOf(w) === i; });
      if (!words.length) return;
      words.forEach(function (w) { shown[w] = true; });
      grid.appendChild(MW.make('div', 'words-grid-label label', null, MW.esc(label)));
      const cells = MW.make('div', 'words-grid-cells');
      words.forEach(function (w) { cells.appendChild(cell(S.step(map, w), w)); });
      grid.appendChild(cells);
    };
    const flat = function (weeks, pick) { return [].concat.apply([], weeks.map(pick)); };
    if (all) {
      // a half-term's weeks or a whole term: every tricky word, then every other word, in the order the file first lists
      // them; a word's row is where the half-term that decides its marking puts it (go is a tricky word in autumn 1 and
      // another word in autumn 2, so with all of autumn it is with the other words)
      const words = S.inPlay(BOOK, c);
      row('Tricky words', words.filter(function (w) { return marks[w] && marks[w].tricky; }));
      row('Other words', words.filter(function (w) { return !(marks[w] && marks[w].tricky); }));
    } else if (half) {
      const now = S.weekOf(half, wk) || { tricky: [], other: [] };
      row('Tricky words', now.tricky);
      row('Week ' + wk + ' words', now.other);
      row('Earlier weeks', flat(half.weeks.filter(function (x) { return x.week < wk; }), function (x) { return x.tricky; }));
      row('Later weeks', flat(half.weeks.filter(function (x) { return x.week > wk; }), function (x) { return x.tricky.concat(x.other); }));
    }
    el.appendChild(grid);
    const legend = MW.make('div', 'words-legend');
    S.STEPS.forEach(function (s) { legend.appendChild(cell(s, S.NAMES[s])); });
    el.appendChild(legend);
    const earlierOther = !all && half && half.weeks.some(function (x) { return x.week < wk && x.other.length; });
    GU.p(el, 'Each word is built with <b>sound tiles</b> until it is right first time (no wrong tap or drop, no hint) on three different days. '
      + 'Then it moves to <b>letters</b>: one tile per letter, with a spare or two; then to <b>harder letters</b>, with the tray filled to '
      + BOOK.harderTray + ' tiles. Three more days right first time at each step; after harder letters it is <b>secure</b>. '
      + 'A secure word goes back to harder letters after two slips in a row (answers not right first time); a right answer in between clears the first slip. '
      + (all ? 'Each round has five words: one or two secure ones to review, then the words on the lowest step first. '
        : 'Each round has five words, at least three of them from the week in play (all of its words, if fewer are recorded): '
          + 'one or two secure ones to review and the rest needing work. ')
      + 'When there aren\'t enough words that need work, more secure ones fill the round.'
      + (!all && half && half.weeks.some(function (x) { return x.week > wk; }) ? ' Later weeks are not in play.' : '')
      + (earlierOther && allLabel ? ' Earlier weeks\' other words come up with ' + MW.esc(allLabel) + '.' : ''), 'gu-note');
    const waiting = BOOK.order.filter(function (w) { return !recorded(w); });
    if (waiting.length) GU.p(el, 'Waiting for a recording, so not in play yet: ' + MW.esc(waiting.join(', ')) + '.', 'gu-note');
    const quiet = S.soundLines(BOOK).filter(function (id) { return !MW.audio.recorded(id); });
    if (quiet.length) GU.p(el, 'Tile sounds waiting for a recording (those tiles are quiet until then): '
      + MW.esc(quiet.map(function (id) { return id.slice(8); }).join(', ')) + '.', 'gu-note');
    if (BOOK.problems.length) GU.p(el, 'To fix in the words file (games/words/words.js): ' + MW.esc(BOOK.problems.join('; ')) + '.', 'gu-note');
    const n = answers().length;
    GU.p(el, n ? 'Words built on this tablet: ' + n + '.' : 'No words built on this tablet yet.', 'gu-note');
    const clear = GU.row(el);
    let armed = 0;
    GU.btn(clear, 'Clear this tablet\'s progress', function (b) {
      if (Date.now() - armed < 4000) {
        const g = MW.store.game(ID); delete g.answers; MW.store.save();   // this game's answers only; the choice stays
        MW.log('words', 'progress cleared');
        GU.show('words-progress');
      } else {
        armed = Date.now(); b.textContent = 'Tap again to clear';
        setTimeout(function () { b.textContent = 'Clear this tablet\'s progress'; }, 4000);
      }
    }, 'gu-quiet');
  }

  // ---------------------------------------------------------------- test hooks
  G.start = startRound; G.showFind = showFind; G.showBuild = showBuild; G.setFind = setFind; G.drop = onDrop; G.tapRocket = tapRocket; G.home = W.home; G.makeRound = makeRound;
  G.inPlay = inPlay; G.week = week; G.choice = choice; G.marked = marked; G.answers = answers; G.sayTile = sayTile; G.LAMPS = LAMPS;
})();
