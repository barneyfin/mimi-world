/* MeeMee Station: number bonds within 10 on the class's ten frame and bar model (0.9.0; the design system's
   MeeMeeStation card, mock-up rounds 12 to 15). The MeeMee come aboard a space station: the station itself is the ten
   frame (ten windows in 2 rows of 5, filling left to right along the top row, then the bottom row), and its long hull
   modules are the bar model (the whole on top, the part already aboard and the rest docked under it, in proportion).
   Scruffles's ship is top right, as in every game; whoever has the commander's job stands on the landing deck (step 1)
   or at the number track's right-hand end (steps 2 and 3), and blinks, then smiles, on each right answer.
   A round is five questions in one of three steps, which a grown-up picks in the game's grown-ups tab, Station (a change
   starts with the next round):
     aboard   Bring them aboard. The whole is on the tower's screen and some MeeMee are already in the first windows;
              enough MeeMee wait on the deck to fill every window. The child drags MeeMee onto the station (each goes
              into the next empty window) until it holds the whole, then taps Scruffles. All ten windows are open.
     more     How many more. A smaller station with the part already aboard, the hull modules under it (the whole, that
              part and an empty berth), and the number track. The child drags a tile onto the berth, then taps Scruffles.
     numbers  Numbers. The hull modules alone; the berth can be either part or the whole.
   Two wrong checks bring the hint: the windows past the whole shut and the rest are counted on together (in step 3 a
   small station comes back to count on). Every right answer ends the same way: praise, then MeeMee Rescue's number
   sentence (3 + 4 = 7) under the picture, said "Three and four make seven.". A tap on Scruffles while he is still
   answering a check does nothing, so a double tap is one try (as Take MeeMee Home).
   facts.js chooses the questions and keeps each step's progress (apart from MeeMee Rescue's); draw.js draws the station
   and its hull modules; moments.js has the crew's job moments. Everything this game owns starts with its id, station. */
(function () {
  'use strict';
  const MW = window.MW;
  const W = MW.world;
  const F = MW.stationFacts;
  const D = MW.stationDraw;
  const L = MW.LAYOUT;
  const ID = 'station';
  const PLAY = 'screen-station-play', END = 'screen-station-end';
  const ROUND = 5;
  const P = { starting: 'station-starting', asking: 'station-asking', open: 'station-open', celebrate: 'station-celebrate', done: 'station-done' };
  const NAMES = { aboard: 'Bring them aboard', more: 'How many more', numbers: 'Numbers' };
  const PRAISE = ['praise-found-it', 'praise-thats-right', 'praise-super-counting', 'praise-well-done'];   // MeeMee Rescue's
  const ALL_ABOARD = 'station-all-aboard';                 // mixed in with the praise once it is recorded
  const BRING = 'station-bring-aboard', FIND = 'station-find-number';
  const N = function (n) { return 'num-mid-' + n; };
  const E = function (n) { return 'num-end-' + n; };

  // ---------------------------------------------------------------- the layouts (the mock-up's approved positions)
  // Step 1: the big station, the whole on its tower's screen, the landing deck bottom right.
  const F1 = { x: 160, y: 270, P: 108, m: 96, d: 78 };
  const TOWER1 = { cx: 430, top: 112, w: 160 };
  const F1O = { wings: [80, 778], tower: TOWER1, dish: true };
  // Step 2: smaller, with the hull modules docked under it on two masts.
  const F2 = { x: 214, y: 128, P: 92, m: 80, d: 66 };
  const F2O = { wings: [150, 738], wingH: 76 };
  const BAR2 = { x: 214, y: 364, w: 460, h: 82, gap: 16 };
  // Step 3: the hull modules alone, on the station's truss with a solar wing; the hint's small station under them.
  const BAR3 = { x: 214, y: 176, w: 540, h: 116, gap: 18 };
  const F3H = { x: 299, y: 482, P: 74, m: 64, d: 52 };
  // The end screen: the station along the bottom, every window full.
  const FEND = { x: 420, y: 624, P: 70, m: 62, d: 50 };
  const FENDO = { wings: [372, 818], wingH: 62 };
  // The MeeMee's sizes in a window (step 1, step 2, step 3's hint, the end screen) and on the deck; the hint's ghosts.
  const SIZE = { aboard: 68, more: 56, numbers: 46, end: 46, deck: 72 };
  const GHOST = { aboard: 66, more: 54, numbers: 44 };
  // Step 1's deck: enough MeeMee to fill every window (10 − a), drawn 72, filling the top row first (open question 3).
  const DECK = [];
  for (let i = 0; i < 5; i++) DECK.push({ x: 772 + 80 * i, y: 652 });
  for (let i = 0; i < 4; i++) DECK.push({ x: 812 + 80 * i, y: 722 });
  const ON_STATION = { x0: 40, y0: 100, x1: 820, y1: 500 };          // a MeeMee let go in here goes into the next window
  const ON_DECK = { x0: 716, y0: 600, x1: 1264, y1: 770 };           // a touch in here picks up the nearest waiting MeeMee
  // The commander: on the deck in step 1 (feet on it), at the number track's right-hand end in steps 2 and 3.
  const COMMANDER = { aboard: { x: 1146, y: 598, w: 108 }, track: { x: 1110, y: 498, w: 124 } };
  const BLINK = 150;                                       // the commander's blink: got it, usual, then got it (ms each)
  // The end screen (board round14-end): the end layout every game uses
  const ENDS = { stars: [450, 40, 60], pod: [380, 110, 400], moggles: [70, 330], snuffles: [790, 330], cat: 240, again: [1080, 420] };

  const st = { step: null, round: null, qi: 0, q: null, target: null, answer: 0, tries: 0, misses: 0, hinted: false,
    counters: [], fixed: [], hintMimi: [], windows: [], bars: null, berth: null, hintStation: null, given: 0,
    ghosts: null, prompt: null, praise: [], placed: null, commander: null,
    talking: false, hintTimers: [], timers: [], faceTimers: [] };
  const R = MW.station = { st: st, nextRound: null };
  let pod, equation, stars, track, scene, ghostLayer, layer, fxLayer, dragger, moments, cmdBox;
  let endPod, endStars, again;
  const endCats = {};
  let view = null;                                         // the grown-ups tab's "Showing progress for": which step
  let talk = 0;                                            // counts what's said after a check (afterCheck)

  // ---------------------------------------------------------------- joining the world
  W.game({
    id: ID,
    build: function () {
      buildGame();
      buildEnd();
      moments = MW.stationMoments({ game: MW.$(PLAY), lowBefore: scene, over: ghostLayer, stars: stars, end: MW.$(END), endCats: endCats });
    },
    start: function () { startRound(); },
    sections: [{ id: 'station-tab', title: 'Station', render: renderTab }],
    onPause: function () { clearHint(); if (dragger) dragger.cancel(); },
    onResume: function () { if (MW.shell.screen === PLAY && answering()) W.speak(st.prompt); },
    onHome: leave
  });

  function answering() { return W.st.phase === P.asking || W.st.phase === P.open; }

  // ---------------------------------------------------------------- saved data (this game's own, on the tablet)
  // games.station = { step, wholes, answers: { aboard: [...], more: [...], numbers: [...] }, gapTurn }: one record per
  // step, apart from MeeMee Rescue's. Read without creating it (MW.store.peek); MW.store.game only to change it. Each
  // step keeps its last KEEP answers (3000 in all, as MeeMee Rescue and Take MeeMee Home keep), so the tablet's one
  // storage entry stays small. gapTurn is where step 3's next round starts taking the berth's three places in turn
  // (0, 1 or 2); it moves on with every step 3 answer, so the places stay spread however long the list has been full.
  // Clear leaves it alone.
  const KEEP = 1000;
  function saved() { return MW.store.peek(ID); }
  function savedStep() { return F.step(saved().step); }
  function step() { return st.step || savedStep(); }        // a round keeps the step it started with
  function wholes() {
    const w = (Array.isArray(saved().wholes) ? saved().wholes : []).filter(function (x) { return x >= 2 && x <= 10; });
    return w.length ? w : [2, 3, 4, 5, 6, 7, 8, 9, 10];
  }
  function answers(s) { const a = saved().answers; return a && typeof a === 'object' && Array.isArray(a[s]) ? a[s] : []; }
  function gapTurn() {
    const t = saved().gapTurn;
    return t === 0 || t === 1 || t === 2 ? t : answers('numbers').length % 3;   // (none saved yet: from the list)
  }
  function recordAnswer(q, s) {
    const turn = gapTurn();
    const g = MW.store.game(ID);
    if (!g.answers || typeof g.answers !== 'object' || Array.isArray(g.answers)) g.answers = {};
    const list = Array.isArray(g.answers[s]) ? g.answers[s] : (g.answers[s] = []);
    list.push({ t: Date.now(), whole: q.whole, a: q.a, missing: q.missing, tries: st.tries, misses: st.misses, hint: st.hinted });
    if (list.length > KEEP) list.splice(0, list.length - KEEP);
    if (s === 'numbers') g.gapTurn = (turn + 1) % 3;
    MW.store.save();
  }

  // ---------------------------------------------------------------- the screens
  function buildGame() {
    const s = W.screen(PLAY, 'MeeMee Station');
    // the step's picture (the station, the deck, the hull modules), drawn afresh for each question; the lookout's
    // moment goes in just before it (moments.js), so the scene and the track are in front of it
    scene = MW.make('div', 'mw-layer mw-fill station-scene');
    s.appendChild(scene);
    cmdBox = MW.make('div', 'mw-abs station-commander', { 'data-commander': '' });
    s.appendChild(cmdBox);
    pod = MW.pod(s, L.pod.x, L.pod.y, L.pod.w);
    MW.onTap(pod.el, onPodTap);
    equation = MW.equation(s);                               // MeeMee Rescue's sentence, in its usual place
    stars = MW.stars(s, L.stars.x, L.stars.y);
    ghostLayer = MW.make('div', 'mw-layer mw-fill'); s.appendChild(ghostLayer);
    layer = MW.make('div', 'mw-layer mw-fill mw-counters'); s.appendChild(layer);
    // the number track (steps 2 and 3): above the MeeMee, so a dropped tile shows over the windows
    track = MW.numberTrack(s);
    track.el.classList.add('mw-off');
    fxLayer = MW.make('div', 'mw-layer mw-fill mw-fx'); s.appendChild(fxLayer);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: hearAgain });
    dragger = MW.dragger(s, {
      counters: function () { return step() === 'aboard' ? st.counters : track.tiles; },
      enabled: function () { return !W.st.paused && answering(); },
      onPick: function (c) { MW.log('pick', c.where ? c.where + (c.where === 'aboard' ? ' ' + c.win : '') : 'tile ' + c.n); },
      onDrop: drop
    });
    // Step 1: any MeeMee will do, so a touch anywhere on the deck picks up the waiting MeeMee nearest the finger: it
    // comes to the finger first, and the dragger (listening after this) picks it up.
    s.addEventListener('pointerdown', pickOnDeck, true);
  }

  function buildEnd() {
    const s = W.screen(END, 'All the MeeMee aboard');
    endStars = MW.stars(s, ENDS.stars[0], ENDS.stars[1], ENDS.stars[2]);
    // the station along the bottom, a MeeMee in every window (the mock-up's end scene)
    D.layer(s, D.station(FEND, FENDO));
    D.pods(s, FEND, []).forEach(function (w) {
      const h = SIZE.end / 2;
      const m = MW.make('div', 'mw-abs station-end-mimi', { style: 'left:' + (w.x - h) + 'px;top:' + (w.y - h) + 'px' });
      const a = MW.art('mimi'); a.setAttribute('width', SIZE.end); a.setAttribute('height', SIZE.end);
      m.appendChild(a); s.appendChild(m);
    });
    const mog = MW.make('div', 'mw-abs mw-crew', { style: 'left:' + ENDS.moggles[0] + 'px;top:' + ENDS.moggles[1] + 'px' });
    mog.appendChild(endCats.moggles = MW.crew.cat('moggles', ENDS.cat)); s.appendChild(mog);
    const p = endPod = MW.pod(s, ENDS.pod[0], ENDS.pod[1], ENDS.pod[2]); p.face('got-it'); p.el.disabled = true; p.el.tabIndex = -1;
    const snu = MW.make('div', 'mw-abs mw-crew', { style: 'left:' + ENDS.snuffles[0] + 'px;top:' + ENDS.snuffles[1] + 'px' });
    snu.appendChild(endCats.snuffles = MW.crew.cat('snuffles', ENDS.cat)); s.appendChild(snu);
    again = MW.make('button', 'mw-btn mw-btn--play mw-abs', { type: 'button', 'aria-label': 'Another visit', id: 'station-again',
      style: 'left:' + ENDS.again[0] + 'px;top:' + ENDS.again[1] + 'px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    again.appendChild(icon);
    MW.onTap(again, function () { MW.audio.unlock(); MW.shell.fullscreen(); startRound(); });
    s.appendChild(again);
    MW.shell.buttons(s, ['home', 'music'], { home: W.home });
  }

  // ---------------------------------------------------------------- a round
  function makeRound() {
    if (R.nextRound) { const r = R.nextRound; R.nextRound = null; return r.map(fromTest); }
    const s = step();
    return F.pickRound({ step: s, wholes: wholes(), answers: answers(s), size: ROUND, turn: s === 'numbers' ? gapTurn() : 0 });
  }
  // a question given by the tests: { whole, a, missing } (missing as the step has it, if not given)
  function fromTest(q) {
    return { whole: q.whole, a: q.a, b: q.whole - q.a, missing: q.missing || F.missing(step()), status: q.status || 'notyet' };
  }

  async function startRound() {
    const token = ++W.st.token;
    st.step = savedStep();
    st.round = makeRound();
    st.qi = 0;
    clearTimers();
    clearBoard();
    moments.clear();
    pod.face('thinking');                                    // not still grinning from the last round's last answer
    pod.lightsOff();
    MW.shell.show(PLAY);
    stars.set(0);
    placeCommander(st.step);
    showTrack(st.step);
    blank(st.step);
    W.st.phase = P.starting;
    const s = st.step;
    moments.lookoutUp(s);                                    // the lookout spots the station
    MW.log('round', JSON.stringify({ step: s, round: st.round }));
    await W.speak([['station-round-ready']]);
    if (!(await W.ok(token))) return;
    nextQuestion(token);
  }

  // The number track in steps 2 and 3; none in step 1.
  function showTrack(s) {
    const nums = s !== 'aboard';
    track.el.classList.toggle('mw-off', !nums);
    if (nums && track.away()) track.show();
  }
  // Whoever has the commander's job, with its badge, at its place for the step; nobody if no cat has it.
  function placeCommander(s) {
    clearFace();
    cmdBox.innerHTML = '';
    st.commander = null;
    const who = MW.crew.who('commander');
    cmdBox.setAttribute('data-commander', who || '');
    if (!who) return;
    const k = s === 'aboard' ? COMMANDER.aboard : COMMANDER.track;
    cmdBox.style.left = k.x + 'px'; cmdBox.style.top = k.y + 'px';
    const cat = MW.crew.cat(who, k.w);
    cat.setJob('commander');
    cmdBox.appendChild(cat);
    st.commander = cat;
  }
  // Until the first question: the step's picture with nothing in it (no numbers, no MeeMee).
  function blank(s) {
    scene.innerHTML = '';
    if (s === 'aboard') { D.layer(scene, D.deck() + D.station(F1, F1O)); D.pods(scene, F1, []); D.whole(scene, '', TOWER1.cx, TOWER1.top + 76); }
    else if (s === 'more') { D.layer(scene, masts2() + D.station(F2, F2O)); D.pods(scene, F2, []); }
    else D.layer(scene, wing3());
  }
  function masts2() {
    return [1, 3].map(function (k) { return D.mast(F2.x + F2.P * (k + 0.5), F2.y + 2 * F2.P - 8, BAR2.y + 10, 18); }).join('');
  }
  function wing3() {
    const mid = BAR3.y + BAR3.h + BAR3.gap / 2;
    return D.truss(150, BAR3.x + 20, mid, 18) + D.wings(150, mid, 112, 18, 100);
  }

  function clearBoard() {
    clearHint();
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    st.counters.concat(st.fixed, st.hintMimi).forEach(function (c) { c.remove(); });
    st.counters = []; st.fixed = []; st.hintMimi = [];
    st.placed = null;
    talk++; st.talking = false;                              // a new question (or leaving): nothing said after a check is going on
    track.reset();                                           // every number tile back in its place
    equation.hide();
    scene.innerHTML = '';
    st.windows = []; st.bars = null; st.berth = null; st.hintStation = null;
    clearFace();
  }

  // the answer's value: the rest in steps 1 and 2; in step 3 whichever of the whole and the parts the berth is in
  function value(q, k) { return k === 'whole' ? q.whole : (k === 'left' ? q.a : q.b); }

  // Put question q on the screen, in the round's step (nothing said).
  function setUp(q) {
    const s = step();
    st.q = q;
    st.target = q.missing;
    st.answer = value(q, q.missing);
    st.tries = 0; st.misses = 0; st.hinted = false;
    clearBoard();
    st.given = s === 'numbers' ? 0 : q.a;                    // the windows already holding a MeeMee
    pod.face('thinking');
    pod.lightsOff();                                         // never still flashing into the next question
    stars.set(st.qi);
    equation.at('under');                                    // where the sentence shows after a right answer
    showTrack(s);
    if (s === 'aboard') setAboard(q); else if (s === 'more') setMore(q); else setNumbers(q);
    st.prompt = promptFor(q, s);
  }

  // Step 1 (board s1ask): the big station, the whole on its tower's screen, a MeeMee in each of the first a windows,
  // and 10 − a MeeMee waiting on the deck, enough to fill every window.
  function setAboard(q) {
    D.layer(scene, D.deck() + D.station(F1, F1O));
    st.windows = D.pods(scene, F1, []);
    D.whole(scene, q.whole, TOWER1.cx, TOWER1.top + 76);
    aboardFixed(q.a, SIZE.aboard);
    for (let i = 0; i < 10 - q.a; i++) {
      const p = DECK[i];
      const c = MW.counter(layer, { x: p.x, y: p.y, size: SIZE.deck });
      c.home = { x: p.x, y: p.y, size: SIZE.deck }; c.where = 'deck'; c.slot = i; c.win = null;
      arriving(c);
      st.counters.push(c);
    }
  }
  // the MeeMee already aboard: one in each of the first n windows, not to drag
  function aboardFixed(n, size, list) {
    for (let i = 0; i < n; i++) {
      const w = st.windows[i];
      const c = MW.counter(layer, { fixed: true, x: w.x, y: w.y, size: size });
      c.where = 'window'; c.win = i;
      (list || st.fixed).push(c);
    }
  }
  function arriving(c) {
    c.el.classList.add('is-arriving');                       // they fade in (the arrival holds them visible: let it go)
    c.el.addEventListener('animationend', function () { c.el.classList.remove('is-arriving'); }, { once: true });
  }

  // Step 2 (board s2ask): the smaller station with a MeeMee in each of the first a windows, and under it on two masts
  // the hull modules: the whole, the part aboard and an empty berth for the rest.
  function setMore(q) {
    D.layer(scene, masts2() + D.station(F2, F2O));
    st.windows = D.pods(scene, F2, []);
    aboardFixed(q.a, SIZE.more);
    st.bars = D.bars(scene, BAR2, q.whole, [q.a, q.b], 1, {});
    st.berth = st.bars.right;
  }
  // Step 3 (boards s3ten, s3whole): the hull modules alone on the station's truss, the berth in any of the three places.
  function setNumbers(q) {
    D.layer(scene, wing3());
    st.bars = D.bars(scene, BAR3, q.whole, [q.a, q.b], q.missing === 'whole' ? 'whole' : (q.missing === 'left' ? 0 : 1), { big: true, minW: 150 });
    st.berth = st.bars[q.missing];
  }

  async function nextQuestion(token) {
    const q = st.round[st.qi], s = step();
    setUp(q);
    if (st.qi === 0) later(token, 1800, function () { moments.lookoutDown(); });   // spotted it
    else moments.settle();
    W.st.phase = P.asking;
    MW.log('question', JSON.stringify(Object.assign({ step: s }, q)));
    await W.speak(st.prompt);
    if (token !== W.st.token) return;
    if (W.st.phase === P.asking) W.st.phase = P.open;
  }

  // What's said for a question, in MeeMee Rescue's words: "Let's make… seven. We've got… three." (step 1), with "How
  // many more?" (steps 2 and 3); the whole missing: "We've got… five… and four. How many altogether?". The first two
  // questions of a round add "Bring more MeeMee aboard." (step 1) or "Find the number." (steps 2 and 3), and "Tap
  // Scruffles when you're ready." Those two new lines are left out until they are recorded, so a missing recording never
  // silences the question (as Take MeeMee Home's).
  function promptFor(q, s) {
    let p;
    if (s === 'numbers' && q.missing === 'whole') p = [['q-weve-got', N(q.a), 'and', E(q.b)], ['q-how-many-altogether']];
    else {
      const given = s === 'numbers' && q.missing === 'left' ? q.b : q.a;
      p = [['q-lets-make', E(q.whole)], ['q-weve-got', E(given)]];
      if (s !== 'aboard') p.push(['q-how-many-more']);
    }
    if (st.qi < 2) {
      const extra = s === 'aboard' ? BRING : FIND;
      if (MW.audio.recorded(extra)) p.push([extra]);
      p.push(['tap-scruffles']);
    }
    return p;
  }

  // ---------------------------------------------------------------- step 1: bringing MeeMee aboard
  function inside(box, x, y) { return x >= box.x0 && x <= box.x1 && y >= box.y0 && y <= box.y1; }
  // the newcomers (MeeMee the child brought; not those already aboard), in their windows' order
  function newcomers() {
    return st.counters.filter(function (c) { return c.where === 'aboard'; }).sort(function (p, q) { return p.win - q.win; });
  }
  function aboardCount() { return st.q.a + newcomers().length; }
  function pickOnDeck(e) {
    if (step() !== 'aboard' || W.st.paused || !answering() || !dragger || dragger.dragging()) return;
    if (e.button !== undefined && e.button > 0) return;
    const p = MW.stage.toStage(e.clientX, e.clientY);
    if (!inside(ON_DECK, p.x, p.y)) return;
    let best = null, bestD = Infinity;
    st.counters.forEach(function (c) {
      if (c.where !== 'deck') return;
      const d = Math.hypot(c.x - p.x, c.y - p.y);
      if (d < bestD) { best = c; bestD = d; }
    });
    if (best) best.moveTo(p.x, p.y, best.size, false);
  }
  // The newcomers fill the windows after those already aboard, in ten-frame order and in the order they came (one
  // taken back out leaves no gap: the ones after it close up).
  function tidy(animate) {
    const list = newcomers();
    list.forEach(function (c, i) {
      const w = st.windows[st.q.a + i];
      c.win = st.q.a + i;
      c.moveTo(w.x, w.y, SIZE.aboard, animate);
    });
    pod.ready(list.length > 0 && W.st.phase !== P.celebrate);   // the ship's lights glow while there's something to check
  }
  function floatHome(c) {
    c.where = 'deck'; c.win = null;
    c.moveTo(c.home.x, c.home.y, c.home.size, true);
  }
  // The next window a MeeMee goes into: the first empty one in ten-frame order, or -1 if none is open (the hint has
  // shut the windows past the whole, or all ten are full).
  function nextWindow() {
    const k = aboardCount();
    return k < 10 && st.windows[k].state !== 'closed' ? k : -1;
  }
  // A drop from the dragger: a number tile (steps 2 and 3) or a MeeMee (step 1).
  function drop(c, x, y, cancelled) {
    if (track.tiles.indexOf(c) >= 0) onTileDrop(c, x, y, cancelled); else onDrop(c, x, y, cancelled);
  }
  // A MeeMee let go anywhere on the station goes into the next empty window, with the snap and a pop; let go anywhere
  // else it floats back to its place on the deck. One the child brought can be picked up again from its window: let go
  // on the station it stays in its window; off the station it goes back to the deck, and the ones after it close up. A
  // tap or a short drag that ends on the deck (a child touching the MeeMee to count them) puts it back quietly.
  function onDrop(c, x, y, cancelled) {
    if (st.counters.indexOf(c) < 0) return;                 // left over from a question that has ended
    const was = c.where;
    if (cancelled || W.st.paused || !answering()) {          // not answering now: just put it back
      if (was === 'aboard') tidy(true); else floatHome(c);
      return;
    }
    if (inside(ON_STATION, x, y)) {
      if (was === 'aboard') { tidy(true); return; }
      const k = nextWindow();
      if (k < 0) { floatHome(c); MW.audio.sfx('whoosh'); MW.log('drop', 'no window'); return; }
      c.where = 'aboard'; c.win = k;
      MW.audio.sfx('pop');
      tidy(true);
      pod.face('thinking');
      MW.log('drop', 'in ' + aboardCount());
      return;
    }
    const nudge = inside(ON_DECK, x, y) || Math.hypot(x - c.home.x, y - c.home.y) <= 70;
    floatHome(c);
    if (was === 'aboard') { tidy(true); MW.audio.sfx('whoosh'); MW.log('drop', 'out ' + aboardCount()); return; }
    if (nudge) return;                                       // a tap or a nudge on the deck isn't anything
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');                                  // checked by tapping Scruffles, so never a try
  }

  // ---------------------------------------------------------------- steps 2 and 3: number tiles
  // A tile let go on the berth (or anywhere on the hull modules, or on one of the station's empty windows) docks in
  // the berth. One tile at a time: another sends the first back. Taken out (let go anywhere else), it floats back to
  // the track and the berth is empty again.
  function onTileDrop(t, x, y, cancelled) {
    const was = t === st.placed;
    if (cancelled || W.st.paused || step() === 'aboard' || !answering()) {
      if (was) placeTile(t); else t.goHome(true);
      return;
    }
    if (onTarget(x, y)) {
      if (was) { placeTile(t); return; }                     // moved about: back to the berth's middle
      if (st.placed) st.placed.goHome(true);                 // the berth holds one tile: the first goes back
      st.placed = t;
      placeTile(t);
      MW.audio.sfx('pop');
      pod.face('thinking');
      MW.log('drop', 'tile ' + t.n + (inBar(st.berth, x, y) ? '' : ' near the berth'));
      pod.ready(true);                                       // the lights glow while there's a tile to check
      return;
    }
    t.goHome(true);
    if (was) { st.placed = null; pod.ready(false); MW.audio.sfx('whoosh'); MW.log('drop', 'out'); return; }
    if (Math.hypot(x - t.home.x, y - t.home.y) <= 70) return;  // a nudge on the track isn't anything
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');                                  // checked by tapping Scruffles, so never a try
  }
  function inBar(m, x, y) {
    const s = L.dropSlack;
    return !!m && x >= m.x - s && x <= m.x + m.w + s && y >= m.y - s && y <= m.y + m.h + s;
  }
  // on the hull modules, or on an empty open window of the station on the screen (step 2's, or step 3's hint's)
  function onTarget(x, y) {
    const b = st.bars;
    if (b && (inBar(b.whole, x, y) || inBar(b.left, x, y) || inBar(b.right, x, y))) return true;
    return st.windows.some(function (w, i) {
      return i >= st.given && w.state !== 'closed' && Math.hypot(x - w.x, y - w.y) <= w.d / 2 + L.dropSlack;
    });
  }
  function placeTile(t) { const m = st.berth; t.moveTo(m.x + m.w / 2, m.y + m.h / 2, 0, true); }

  // ---------------------------------------------------------------- checking: tap Scruffles
  function onPodTap() {
    if (W.st.paused || !answering()) return;
    if (dragger && dragger.dragging()) return;              // one hand holding something, the other tapping
    // While Scruffles is still answering a check (a try-again line, too many, the hint), a tap does nothing, so a double
    // tap is one try, not two (as Take MeeMee Home)
    if (st.talking) { MW.log('check', 'still answering'); return; }
    if (step() === 'aboard') {
      const n = aboardCount();
      MW.log('check', n + ' of ' + st.q.whole);
      if (n === st.q.whole) { success(); return; }
      wrongTry(n > st.q.whole ? 'too-many' : 'too-few');
      return;
    }
    if (!st.placed) {
      // nothing to check: the question again, not a try, but only once Scruffles is quiet (as Take MeeMee Home)
      if (st.talking || MW.audio.speaking()) { MW.log('check', 'no tile, waiting'); return; }
      MW.log('check', 'no tile');
      hearAgain();
      return;
    }
    checkTile();
  }
  function checkTile() {
    const t = st.placed;
    MW.log('check', 'tile ' + t.n + ' for ' + st.answer);
    if (t.n === st.answer) { success(); return; }
    st.placed = null;                                        // a wrong number floats back to the track, the berth is empty again
    t.goHome(true);
    pod.ready(false);
    MW.audio.sfx('whoosh');
    wrongTry('number');
  }

  // A wrong check. No red, no buzzer: Scruffles's try-again face, a calm line, and the hint after the second. Too many
  // MeeMee gets its own line every time (a try, never the hint itself), as in MeeMee Rescue and Take MeeMee Home. Too
  // few (or none, step 1) or a wrong number (steps 2 and 3): "Let's try again.". After the hint, any other wrong check
  // only changes Scruffles's face, in every step, as in MeeMee Rescue and Take MeeMee Home (Barney, 17 October 2026).
  // (Step 1 can't have too many after the hint: the windows past the whole are shut.)
  // What Scruffles says after a check: st.talking is true from the moment it's asked for until it ends or is cut short.
  function afterCheck(saying) {
    const n = ++talk;
    st.talking = true;
    saying.then(function () { if (n === talk) st.talking = false; });
    return saying;
  }
  function wrongTry(kind) {
    st.tries++;
    pod.face('try-again');
    const token = W.st.token, qi = st.qi;
    later(token, 1600, function () { if (qi === st.qi && W.st.phase !== P.celebrate) pod.face('thinking'); });
    MW.log('wrong', kind);
    if (kind === 'too-many') { afterCheck(W.speak([['too-many']])); return; }
    if (st.tries >= 2 && !st.hinted) { hint(); return; }
    if (st.tries >= 2) return;                               // after the hint: just the face
    afterCheck(W.speak([['again-try-again']]));
  }

  // ---------------------------------------------------------------- the hint: count on together
  // MeeMee Rescue's counting-on: "Let's count on from… three." and "four, five, six, seven", one window lighting (its
  // ghost) as each number is said; for a missing whole (step 3), "Count them with me." and every MeeMee hops as it is
  // counted. The windows past the whole shut first.
  //   step 1     the newcomers go back to the deck; the windows from a + 1 to w light; the child still brings them;
  //   step 2     the empty windows from a + 1 to w light; the berth gets the counting halo; the number still has to be
  //              dragged;
  //   step 3     a small station hangs under the modules: the given part's MeeMee fill its first windows and the rest
  //              are counted on (or, the whole missing, both parts' MeeMee fill them and every one is counted).
  // The ghosts stay until the answer is given. Cut short (Hear-again, a pause), the hint is taken away so the next wrong
  // check gives it again in full.
  async function hint() {
    const q = st.q, s = step(), token = W.st.token, qi = st.qi;
    st.hinted = true;
    MW.log('hint', s + ' ' + q.missing);
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    const lines = [], actions = [];
    if (s === 'aboard') {
      const back = newcomers();
      back.forEach(floatHome);
      if (back.length) MW.audio.sfx('whoosh');
      tidy(true);
    }
    if (s === 'numbers') showHintStation(q);
    else st.given = q.a;
    if (st.berth) st.berth.el.classList.add('is-hinting');
    st.windows.forEach(function (w, i) { if (i >= q.whole) w.set('closed'); else if (i >= st.given) w.set('hinting'); });
    if (s === 'numbers' && q.missing === 'whole') {
      // "Count them with me. One, two, …": every MeeMee hops as it is counted
      const order = st.hintMimi.slice();
      lines.push(['again-count-with-me']); actions.push(null);
      for (let i = 1; i <= q.whole; i++) {
        lines.push([i === q.whole ? E(i) : N(i)]);
        actions.push((function (c) { return function () { hop(c); }; })(order[i - 1]));
      }
    } else {
      const from = st.given, size = GHOST[s];
      st.ghosts = MW.ghosts(ghostLayer, st.windows.slice(from, q.whole).map(function (w) { return { x: w.x, y: w.y, size: size }; }));
      lines.push(['q-count-on-from', E(from)]); actions.push(null);
      for (let i = from + 1; i <= q.whole; i++) {
        lines.push([i === q.whole ? E(i) : N(i)]);
        actions.push((function (j) {
          return function () {
            const c = s === 'aboard' ? newcomers()[j] : null;
            if (c) hop(c); else if (st.ghosts) st.ghosts.light(j);
          };
        })(i - from - 1));
      }
    }
    const heard = await afterCheck(W.speak(lines, {
      onStart: function (timeline) {
        let k = 0;                                           // one entry per clip
        lines.forEach(function (sent, si) {
          const at = timeline[k].at;
          k += sent.length;
          if (actions[si]) st.hintTimers.push(setTimeout(function () { if (token === W.st.token && qi === st.qi) actions[si](); }, at * 1000));
        });
      }
    }));
    if (!heard && token === W.st.token && qi === st.qi && W.st.phase !== P.celebrate) takeHint();
  }
  // Step 3's hint: a small station on two masts under the modules (the mock-up's place), its first windows holding the
  // given part's MeeMee (or both parts', the whole missing).
  function showHintStation(q) {
    const g = MW.make('div', 'mw-layer mw-fill station-hint');
    const f = F3H;
    const masts = [1, 3].map(function (k) { return D.mast(f.x + f.P * (k + 0.5), BAR3.y + 2 * BAR3.h + BAR3.gap - 8, f.y + 8, 14); }).join('');
    D.layer(g, masts + D.station(f, {}));
    st.windows = D.pods(g, f, []);
    scene.appendChild(g);
    st.hintStation = g;
    st.given = q.missing === 'whole' ? q.whole : (q.missing === 'left' ? q.b : q.a);
    aboardFixed(st.given, SIZE.numbers, st.hintMimi);
    st.hintMimi.forEach(arriving);
  }
  // Cut short: everything as before the hint (step 1's newcomers stay on the deck).
  function takeHint() {
    clearHint();
    st.hinted = false;
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    if (st.berth) st.berth.el.classList.remove('is-hinting');
    if (step() === 'numbers') {
      st.hintMimi.forEach(function (c) { c.remove(); });
      st.hintMimi = [];
      if (st.hintStation && st.hintStation.parentNode) st.hintStation.parentNode.removeChild(st.hintStation);
      st.hintStation = null; st.windows = []; st.given = 0;
    } else st.windows.forEach(function (w, i) { if (i >= st.q.a) w.set(''); });
  }
  function clearHint() { st.hintTimers.forEach(clearTimeout); st.hintTimers = []; }
  function hop(c) {
    if (!c) return;
    c.el.classList.remove('is-hop'); void c.el.offsetWidth; c.el.classList.add('is-hop');
  }

  // ---------------------------------------------------------------- a right answer
  // Every right answer (boards s1right, s2right; round 15's smile): the answer arrives (step 1: the newcomers' windows
  // glow peach; steps 2 and 3: the tile docks and the berth becomes a hull module showing the number, with the success
  // ring, and in step 2 the rest of the MeeMee pop into their windows), the spare windows shut, sparkles, Scruffles's
  // got-it face and the ship's lights, and the commander blinks, then smiles; in steps 2 and 3 the track slides away;
  // praise; then the sentence shows under the picture and is said (the commander smiles until then); the star. Then the
  // next question, or the end screen.
  async function success() {
    if (W.st.phase === P.celebrate) return;
    const token = W.st.token, q = st.q, s = step();
    W.st.phase = P.celebrate;
    clearHint();
    moments.lookoutDown();                                   // a quick first answer: the lookout makes way
    recordAnswer(q, s);
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    if (s === 'aboard') {
      st.windows.forEach(function (w, i) {
        if (i >= q.whole) w.set('closed');
        else if (i >= q.a) { w.set('arrived'); MW.sparkles(fxLayer, w.x, w.y, 54); }
        else w.set('');
      });
      newcomers().forEach(function (c) { c.draggable = false; });
    } else {
      st.placed = null;                                      // the tile goes back as the track slides down out of sight
      track.hide();
      st.berth.fill(st.answer);
      if (s === 'more') {
        st.windows.forEach(function (w, i) {
          if (i >= q.whole) { w.set('closed'); return; }
          if (i < q.a) { w.set(''); return; }
          w.set('arrived');
          const c = MW.counter(layer, { fixed: true, x: w.x, y: w.y, size: SIZE.more });
          c.where = 'window'; c.win = i;
          c.el.classList.add('station-pop');
          st.fixed.push(c);
          MW.sparkles(fxLayer, w.x, w.y, 46);
        });
        MW.audio.sfx('pop');
      } else {
        const m = st.berth;
        MW.sparkles(fxLayer, m.x + m.w / 2, m.y + m.h / 2, Math.min(m.w, m.h) / 2 + 34);
        if (st.hintStation) {                                // the hint's small station has done its job: it fades away
          st.hintStation.classList.add('is-gone');
          st.hintMimi.forEach(function (c) { c.el.classList.remove('is-arriving'); c.el.classList.add('is-rescued'); });
        }
      }
    }
    pod.face('got-it');
    pod.celebrate();                                         // the ship's lights flash for about 4 s
    smile(token);
    moments.engineer(s);                                     // the engineer's tap with the spanner
    MW.audio.sfx('chime');
    MW.log('success', JSON.stringify(Object.assign({ step: s }, q)));
    await MW.wait(550);
    if (!(await W.ok(token))) return;
    await W.speak([[nextPraise()]]);
    if (!(await W.ok(token))) return;
    equation.show(q.a, q.b, q.whole);                        // under the picture, MeeMee Rescue's "3 + 4 = 7"
    await W.speak([[N(q.a), 'and', N(q.b), 'make', E(q.whole)]]);
    if (!(await W.ok(token))) return;
    commanderFace('usual');                                  // the sentence said: the commander looks as before
    clearFace();
    stars.set(st.qi + 1);
    MW.audio.sfx('twinkle');
    moments.navigator(st.qi + 1 < st.round.length ? st.qi + 1 : null);   // the navigator points to the next star
    await MW.wait(800);
    if (!(await W.ok(token))) return;
    await MW.wait(700);                                      // a moment to see the station full
    if (!(await W.ok(token))) return;
    st.qi++;
    if (st.qi < st.round.length) nextQuestion(token); else endRound(token);
  }
  // MeeMee Rescue's four praise lines and, once it is recorded, "All aboard!" (a praise line on its own would be silent
  // until then), taking turns: each once, in a shuffled order, before any comes round again
  function praiseLines() { return PRAISE.concat(MW.audio.recorded(ALL_ABOARD) ? [ALL_ABOARD] : []); }
  function nextPraise() {
    if (!st.praise.length) st.praise = MW.shuffle(praiseLines());
    return st.praise.pop();
  }

  // The commander on a right answer (round 15): it blinks, then smiles. Its got-it face for 150 ms, its usual face for
  // 150 ms, then its got-it face until the sentence has been said (success() puts the usual face back). Nothing moves,
  // so reduce motion changes nothing. Never during a wrong try or a hint. Nobody, if no cat has the job.
  function commanderFace(name) {
    if (!st.commander) return;
    st.commander.face(name);
    MW.log('commander', name);
  }
  function smile(token) {
    if (!st.commander) return;
    clearFace();
    commanderFace('got-it');
    st.faceTimers.push(setTimeout(function () { if (token === W.st.token && W.st.phase === P.celebrate) commanderFace('usual'); }, BLINK));
    st.faceTimers.push(setTimeout(function () { if (token === W.st.token && W.st.phase === P.celebrate) commanderFace('got-it'); }, 2 * BLINK));
  }
  function clearFace() {
    st.faceTimers.forEach(clearTimeout); st.faceTimers = [];
    if (st.commander && st.commander.face() !== 'usual') commanderFace('usual');
  }

  // ---------------------------------------------------------------- the end of a round
  // The end screen (board round14-end): the stars, Scruffles grinning, the crew wearing their badges, the station along
  // the bottom with a MeeMee in every window. "All the MeeMee are aboard!", the commander's moment, then "Another visit?".
  async function endRound(token) {
    W.st.phase = P.done;
    clearBoard();
    MW.shell.show(END);
    endStars.set(ROUND, ROUND);
    const jobs = MW.crew.jobs();
    MW.crew.CATS.forEach(function (w) { endCats[w].setJob(jobs[w]); });
    MW.audio.sfx('tune');
    endPod.celebrate();
    await MW.wait(300);
    if (!(await W.ok(token))) return;
    await W.speak([['station-round-done']]);
    if (!(await W.ok(token))) return;
    await MW.wait(500);
    if (!(await W.ok(token))) return;
    if (moments.commander()) {                               // the commander's radio calls
      await MW.wait(1350);
      if (!(await W.ok(token))) return;
    }
    await W.speak([['station-round-another']]);
  }

  function hearAgain() {
    if (W.st.paused) return;
    if (answering()) { clearHint(); W.speak(st.prompt); }
  }
  function later(token, ms, fn) { st.timers.push(setTimeout(function () { if (token === W.st.token) fn(); }, ms)); }
  function clearTimers() { st.timers.forEach(clearTimeout); st.timers = []; }
  // Home (from any screen, this game's or the world's): put everything away. The world has moved the token on, so
  // speech and timers from the round stop themselves.
  function leave() {
    clearHint();
    clearTimers();
    if (dragger) dragger.cancel();
    st.step = null;
    pod.lightsOff(); endPod.lightsOff();
    clearBoard();
    if (moments) moments.clear();
  }

  // ---------------------------------------------------------------- grown-ups: the Station tab (boards round14-grownups-tab, -grid)
  // Which step; wholes in play; the progress grid for the step picked (BondGrid card); clear this game's progress.
  function cell(status, text) {
    const c = MW.make('span', 'mw-cell label is-' + status);
    if (status === 'secure') {
      const tick = MW.art('icon-tick'); tick.setAttribute('width', 16); tick.setAttribute('height', 16);
      c.appendChild(tick);
    }
    c.appendChild(document.createTextNode(text));
    return c;
  }
  function renderTab(el) {
    const G = MW.grownups;
    G.h3(el, 'Which step');
    const r0 = G.row(el);
    const paintStep = function () {
      Array.prototype.forEach.call(r0.children, function (b) { b.classList.toggle('is-on', b.getAttribute('data-step') === savedStep()); });
    };
    F.STEPS.forEach(function (s) {
      const b = G.btn(r0, NAMES[s], function () {
        const g = MW.store.game(ID); g.step = s; MW.store.save();
        view = null;                                         // the progress below shows the step picked
        paintStep(); renderProgress(prog);
        MW.log('setting', 'station step ' + s);
      }, 'gu-choice');
      b.setAttribute('data-step', s);
    });
    paintStep();
    G.p(el, '<b>Bring them aboard</b> (the first step): the whole shows on the station\'s tower and some MeeMee are already in its ten windows. Your child drags MeeMee in from the deck until the station holds the whole, then taps Scruffles. All ten windows are open, so they have to stop at the right number.');
    G.p(el, '<b>How many more:</b> the ten frame shows the part already aboard, and the bar model under it shows the whole and that part. Your child drags a number tile into the empty part of the bar. Two wrong tries: the windows past the whole close, and the empty ones are counted together.');
    G.p(el, '<b>Numbers:</b> the bar model alone, and the empty space can be a part or the whole.');
    G.p(el, 'A change starts with the next round. Each step keeps its own progress, separate from MeeMee Rescue\'s.', 'gu-note');

    G.h3(el, 'Wholes in play');
    const rw = G.row(el);
    const paintW = function () {
      const on = wholes();
      Array.prototype.forEach.call(rw.children, function (b) { b.classList.toggle('is-on', on.indexOf(+b.textContent) >= 0); });
    };
    for (let w = 2; w <= 10; w++) {
      G.btn(rw, String(w), function () {
        let on = wholes().slice();
        if (on.indexOf(w) >= 0) { if (on.length > 1) on = on.filter(function (x) { return x !== w; }); }
        else on.push(w);
        on.sort(function (a, b) { return a - b; });
        const g = MW.store.game(ID); g.wholes = on; MW.store.save();
        paintW();
        MW.log('setting', 'station wholes ' + on.join(','));
      }, 'mw-chip gu-chip station-whole-chip');
    }
    paintW();
    G.p(el, 'Questions use only the wholes switched on. Changes start with the next round.', 'gu-note');   // MeeMee Rescue's note

    const prog = MW.make('div', 'station-progress');
    el.appendChild(prog);
    renderProgress(prog);

    const row = G.row(el);
    let armed = 0;
    G.btn(row, 'Clear this tablet\'s progress', function (b) {
      if (Date.now() - armed < 4000) {
        const g = MW.store.game(ID); delete g.answers; MW.store.save();   // this game's answers only; its step and wholes stay
        MW.log('station', 'progress cleared');
        armed = 0; b.textContent = 'Clear this tablet\'s progress';
        renderProgress(prog);
      } else {
        armed = Date.now(); b.textContent = 'Tap again to clear';
        setTimeout(function () { b.textContent = 'Clear this tablet\'s progress'; }, 4000);
      }
    }, 'gu-quiet station-clear');
  }
  // "Showing progress for": which step's grid shows (each step keeps its own progress), its summary, the grid (a cell
  // per fact, "3 + 4": the part already aboard + the part to find), the legend and the note.
  function renderProgress(box) {
    const G = MW.grownups;
    box.innerHTML = '';
    const shown = view || savedStep();
    G.h3(box, 'Showing progress for');
    const r = G.row(box);
    F.STEPS.forEach(function (s) {
      const b = G.btn(r, NAMES[s], function () { view = s; renderProgress(box); }, 'gu-choice');
      b.classList.toggle('is-on', s === shown);
      b.setAttribute('data-view', s);
    });
    const list = answers(shown);
    const map = F.statuses(list);
    const n = { secure: 0, practising: 0, total: 0 };
    const grid = MW.make('div', 'gu-grid');
    for (let w = 2; w <= 10; w++) {
      const rowEl = MW.make('div', 'gu-grid-row');
      rowEl.appendChild(MW.make('span', 'gu-grid-whole', null, String(w)));
      F.facts(w).forEach(function (a) {
        const status = F.status(map, w, a);
        n.total++;
        if (status === 'secure') n.secure++; else if (status === 'practising') n.practising++;
        rowEl.appendChild(cell(status, a + ' + ' + (w - a)));
      });
      grid.appendChild(rowEl);
    }
    G.p(box, list.length
      ? 'Secure: ' + n.secure + ' of ' + n.total + ' facts. Practising: ' + n.practising + '. Questions answered this step on this tablet: ' + list.length + '.'
      : 'No questions answered this step on this tablet yet.', 'gu-lead');
    box.appendChild(grid);
    const legend = MW.make('div', 'gu-legend');
    legend.appendChild(cell('secure', 'Secure'));
    legend.appendChild(cell('practising', 'Practising'));
    legend.appendChild(cell('notyet', 'Not yet'));
    box.appendChild(legend);
    G.p(box, '<b>Secure</b> means right first time (no wrong check and no hint) on three different days. A wrong answer moves a fact back to practising, and its three days start again. Each step keeps its own progress, separate from MeeMee Rescue\'s.', 'gu-note');
  }

  // ---------------------------------------------------------------- test hooks
  R.drop = drop; R.podTap = onPodTap; R.start = startRound; R.home = W.home; R.makeRound = makeRound; R.step = step;
  R.track = function () { return track; }; R.equation = function () { return equation; };
  R.windows = function () { return st.windows; }; R.bars = function () { return st.bars; }; R.moments = function () { return moments; };
  R.answers = function (s) { return answers(s); }; R.gapTurn = gapTurn; R.praiseLines = praiseLines;
  // Ask one question straight away, as a round of its own in step s (or the step set in the grown-ups tab), with nothing
  // said (the tests use it to put every question on the screen without playing whole rounds).
  R.ask = function (q, s) {
    ++W.st.token;
    clearHint(); clearTimers();
    if (dragger) dragger.cancel();
    if (moments) moments.clear();
    st.step = s ? F.step(s) : savedStep();
    st.round = [fromTest(q)]; st.qi = 0;
    MW.shell.show(PLAY);
    placeCommander(st.step);
    setUp(st.round[0]);
    W.st.phase = P.open;
    return W.st.token;
  };
})();
