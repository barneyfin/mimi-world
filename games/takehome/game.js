/* Take MeeMee Home: subtraction within 10 on the part–whole diagram (0.8.0; the design system's TakeMeeMeeHome card,
   mock-up rounds 10 and 11). A sequel to MeeMee Rescue: Scruffles takes the rescued MeeMee home, and the ones going
   home hop off to their houses on the home planet.
   MeeMee Rescue's screen (GameScreen): the diagram on the left, Scruffles's ship top right, no asteroid. The right part
   is the MeeMee going home, the left part the MeeMee staying. The number sentence (the kit's MW.equation, minus) reads
   whole − going home = left: 7 − 4 = 3. A round is five questions in one of three steps, which a grown-up picks in the
   game's grown-ups tab, Subtraction (a change starts with the next round):
     take     Take away. The whole holds its MeeMee; the pill under the going-home part says how many go. The child drags
              that many into the going-home part, then taps Scruffles. The rest slide into the other part as they are
              counted aloud (0.8.1), and the sentence shows under the diagram.
     left     How many are left. The whole and the going-home part show their MeeMee; the staying part waits, and so
              does the sentence's gap, under Scruffles. The child drags a number tile from the track into the empty
              circle or the gap, then taps Scruffles.
     numbers  Numbers. A numbered MeeMee in each given circle (MeeMee Rescue's numbers mode); the gap can be in any of the
              sentence's three places.
   Two wrong checks bring the hint (not for an answer of zero). Every right answer ends the same way: the answer is
   carried, the track slides away, the sentence ends up complete under the diagram and is said, the home planet shows,
   and the MeeMee going home hop off to their houses (with reduce motion they fade). The sentence's words take turns
   (0.8.1): take away, subtract and minus, and is and equals ("Seven subtract four equals three."). A tap on Scruffles
   while he is still answering a check does nothing (0.8.1), so a double tap is one try.
   facts.js chooses the questions and keeps each step's progress (apart from MeeMee Rescue's); moments.js has the crew's
   job moments. Everything this game owns starts with its id, takehome. */
(function () {
  'use strict';
  const MW = window.MW;
  const W = MW.world;
  const F = MW.takehomeFacts;
  const L = MW.LAYOUT;
  const ID = 'takehome';
  const PLAY = 'screen-takehome-play', END = 'screen-takehome-end';
  const ROUND = 5;
  const P = { starting: 'takehome-starting', asking: 'takehome-asking', open: 'takehome-open', celebrate: 'takehome-celebrate', done: 'takehome-done' };
  const GOING = 'right', STAYING = 'left';                 // the diagram's parts: the right one goes home, the left one stays
  const GAP = { whole: 0, right: 1, left: 2 };             // where each circle's number is in the sentence (w − t = r)
  const NAMES = { take: 'Take away', left: 'How many are left', numbers: 'Numbers' };
  const PRAISE = ['praise-found-it', 'praise-thats-right', 'praise-super-counting', 'praise-well-done'];   // MeeMee Rescue's
  const HOME_THEY_GO = 'takehome-home-they-go';            // mixed in with the praise once it is recorded
  const MOVE = 'takehome-move-them', FIND = 'takehome-find-number';
  // The number sentence's words take turns, question by question (0.8.1; the class uses every subtraction word): the
  // next of take away, subtract and minus, and the next of is and equals, so six questions say every pairing. A word not
  // recorded yet sits out its turn, so the sentence is never missing one (take away and is are always recorded).
  const TAKE_WORDS = ['takehome-take-away', 'takehome-subtract', 'takehome-minus'];
  const IS_WORDS = ['takehome-is', 'takehome-equals'];
  const N = function (n) { return 'num-mid-' + n; };
  const E = function (n) { return 'num-end-' + n; };
  // The home planet (takehome-home), bottom right; the end screen's ground (takehome-home-wide) across the bottom.
  const HOME = { x: 600, y: 560 }, GROUND = { x: 0, y: 560 };
  // The way home (boards s1-right, s2-right, s3-right): the path from the going-home circle's edge (706, 520) down to the
  // houses (963, 628). Each MeeMee, at 64 px, makes two hops of 340 ms, one journey: onto the path (via, one of the
  // boards' points on it), then into its house's door (art.py's houses on the planet's curve, as stage px), shrinking as
  // it goes in. Two hops of about a third of a second each, close to the kit's own hop (420 ms), so it reads as hopping
  // home rather than skipping. The houses take turns, the furthest first (the right one, the middle, the left), and the
  // MeeMee nearest the way out goes first, so they hop in file and none catches up with another. They go one after
  // another (stagger, squeezed so the last sets off within spread), about a second in all. A MeeMee that appears from the
  // circle (step 3, where the circle keeps its numbered MeeMee) starts at the circle's edge (from).
  const HOP = { size: 64, from: [706, 520], via: [782, 556], rise: 30, step: 340, stagger: 140, spread: 420,
    doors: [[1160, 670], [1030, 652], [900, 666]] };
  const SLIDE = 200;                                       // step 1: the MeeMee left in the whole slide out one by one
  const LOOKOUT = { min: 1200, duck: 450 };               // steps 2 and 3: the lookout's least time up, and its duck
  // The end screen (board end; MeeMee Rescue's end layout on the home planet's gentle curve)
  const ENDS = { stars: [450, 40, 60], pod: [380, 110, 400], moggles: [70, 330], snuffles: [790, 330], cat: 240, again: [1080, 400],
    mimi: [[370, 726], [560, 736], [664, 724], [768, 738], [1040, 728]], mimiSize: 68 };

  const st = { step: null, round: null, qi: 0, q: null, target: null, answer: 0, tries: 0, misses: 0, hinted: false,
    counters: [], fixed: [], dimmed: [], hoppers: [], ghosts: null, prompt: null, praise: [], placed: null,
    talking: false, hintTimers: [], timers: [] };
  const R = MW.takehome = { st: st, nextRound: null };
  let diagram, pod, equation, stars, track, home, ghostLayer, layer, fxLayer, dragger, moments;
  let endPod, endStars, again;
  const endMimi = [], endCats = {};
  let view = null;                                         // the grown-ups tab's "Showing progress for": which step
  let talk = 0;                                            // counts what's said after a check (afterCheck)

  // ---------------------------------------------------------------- joining the world
  W.game({
    id: ID,
    build: function () {
      buildGame();
      buildEnd();
      moments = MW.takehomeMoments({ game: MW.$(PLAY), lowBefore: home, over: ghostLayer, stars: stars, end: MW.$(END), endCats: endCats });
    },
    start: function () { startRound(); },
    sections: [{ id: 'takehome-subtraction', title: 'Subtraction', render: renderTab }],
    onPause: function () { clearHint(); if (dragger) dragger.cancel(); },
    onResume: function () { if (MW.shell.screen === PLAY && answering()) W.speak(st.prompt); },
    onHome: leave
  });

  function answering() { return W.st.phase === P.asking || W.st.phase === P.open; }

  // ---------------------------------------------------------------- saved data (this game's own, on the tablet)
  // games.takehome = { step, wholes, answers: { take: [...], left: [...], numbers: [...] }, gapTurn }: one record per
  // step, apart from MeeMee Rescue's. Read without creating it (MW.store.peek); MW.store.game only to change it.
  // Each step keeps its last KEEP answers, so the game keeps at most 3000 in all, as MeeMee Rescue does: the whole of
  // the tablet's saving is one entry, rewritten on every answer, so it stays small. Three different days right first
  // time is far inside 1000 answers, and a fact a round keeps asking (secure ones come up in every round) keeps its
  // recent answers. gapTurn is where step 3's next round starts taking the gap's three places in turn (0, 1 or 2); it
  // moves on with every step 3 answer, so the places stay spread for ever, however long the list has been full.
  // wordTurn (0 to 5) is which words the next number sentence uses (TAKE_WORDS, IS_WORDS); it moves on with every
  // answer in any step and carries on across rounds. Clear leaves both turns alone.
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
    return t === 0 || t === 1 || t === 2 ? t : answers('numbers').length % 3;   // (none saved yet: from the list, as before)
  }
  function wordTurn() {
    const t = saved().wordTurn;
    return Number.isInteger(t) && t >= 0 ? t % 6 : 0;
  }
  // The sentence's words for a turn: the turn-th of those recorded, of each kind.
  function sentenceWords(turn) {
    const pick = function (list) {
      const ok = list.filter(function (id) { return MW.audio.recorded(id); });
      const from = ok.length ? ok : list.slice(0, 1);
      return from[turn % from.length];
    };
    return { take: pick(TAKE_WORDS), is: pick(IS_WORDS) };
  }
  function recordAnswer(q, s) {
    const turn = gapTurn(), words = wordTurn();
    const g = MW.store.game(ID);
    g.wordTurn = (words + 1) % 6;
    if (!g.answers || typeof g.answers !== 'object' || Array.isArray(g.answers)) g.answers = {};
    const list = Array.isArray(g.answers[s]) ? g.answers[s] : (g.answers[s] = []);
    list.push({ t: Date.now(), whole: q.whole, take: q.take, missing: q.missing, tries: st.tries, misses: st.misses, hint: st.hinted });
    if (list.length > KEEP) list.splice(0, list.length - KEEP);
    if (s === 'numbers') g.gapTurn = (turn + 1) % 3;
    MW.store.save();
  }

  // ---------------------------------------------------------------- the screens
  function buildGame() {
    const s = W.screen(PLAY, 'Take MeeMee Home');
    diagram = MW.diagram(s);
    pod = MW.pod(s, L.pod.x, L.pod.y, L.pod.w);
    MW.onTap(pod.el, onPodTap);
    // the home planet, bottom right: in front of the lookout's window (moments.js puts it just before this)
    home = MW.make('div', 'mw-abs takehome-home', { style: 'left:' + HOME.x + 'px;top:' + HOME.y + 'px' });
    home.appendChild(MW.art('takehome-home'));
    s.appendChild(home);
    equation = MW.equation(s);
    stars = MW.stars(s, L.stars.x, L.stars.y);
    ghostLayer = MW.make('div', 'mw-layer mw-fill'); s.appendChild(ghostLayer);
    layer = MW.make('div', 'mw-layer mw-fill mw-counters'); s.appendChild(layer);
    // the number track (steps 2 and 3): above the MeeMee, so a dropped tile shows over the circle and the hint's MeeMee
    track = MW.numberTrack(s);
    track.el.classList.add('mw-off');
    fxLayer = MW.make('div', 'mw-layer mw-fill mw-fx'); s.appendChild(fxLayer);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: hearAgain });
    dragger = MW.dragger(s, {
      counters: function () { return step() === 'take' ? st.counters : track.tiles; },
      enabled: function () { return !W.st.paused && answering(); },
      onPick: function (c) { MW.log('pick', c.where || 'tile ' + c.n); },
      onDrop: drop
    });
    // Step 1: any MeeMee will do, so a touch anywhere in the whole picks up the one nearest the finger. The MeeMee are
    // small there (about 41 px for 7), so the nearest comes to the finger first; the dragger (listening after this)
    // then picks it up.
    s.addEventListener('pointerdown', pickInWhole, true);
  }

  function buildEnd() {
    const s = W.screen(END, 'All the MeeMee home');
    const ground = MW.make('div', 'mw-abs takehome-home', { style: 'left:' + GROUND.x + 'px;top:' + GROUND.y + 'px' });
    ground.appendChild(MW.art('takehome-home-wide'));
    s.appendChild(ground);
    endStars = MW.stars(s, ENDS.stars[0], ENDS.stars[1], ENDS.stars[2]);
    const mog = MW.make('div', 'mw-abs mw-crew', { style: 'left:' + ENDS.moggles[0] + 'px;top:' + ENDS.moggles[1] + 'px' });
    mog.appendChild(endCats.moggles = MW.crew.cat('moggles', ENDS.cat)); s.appendChild(mog);
    const p = endPod = MW.pod(s, ENDS.pod[0], ENDS.pod[1], ENDS.pod[2]); p.face('got-it'); p.el.disabled = true; p.el.tabIndex = -1;
    const snu = MW.make('div', 'mw-abs mw-crew', { style: 'left:' + ENDS.snuffles[0] + 'px;top:' + ENDS.snuffles[1] + 'px' });
    snu.appendChild(endCats.snuffles = MW.crew.cat('snuffles', ENDS.cat)); s.appendChild(snu);
    ENDS.mimi.forEach(function (q) {                          // five MeeMee by their houses
      const h = ENDS.mimiSize / 2;
      const m = MW.make('div', 'mw-abs takehome-end-mimi', { style: 'left:' + (q[0] - h) + 'px;top:' + (q[1] - h) + 'px' });
      const a = MW.art('mimi'); a.setAttribute('width', ENDS.mimiSize); a.setAttribute('height', ENDS.mimiSize);
      m.appendChild(a); s.appendChild(m);
      endMimi.push(a);
    });
    again = MW.make('button', 'mw-btn mw-btn--play mw-abs', { type: 'button', 'aria-label': 'Another trip', id: 'takehome-again',
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
  // a question given by the tests: { whole, take, missing } (missing as the step has it, if not given)
  function fromTest(q) {
    return { whole: q.whole, take: q.take, left: q.whole - q.take, missing: q.missing || F.missing(step()), status: q.status || 'notyet' };
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
    showMode(st.step);
    blank(st.step);
    W.st.phase = P.starting;
    const s = st.step, up = performance.now();
    moments.lookoutUp(s === 'take' ? 'home' : 'track');      // the lookout spots the home planet
    MW.log('round', JSON.stringify({ step: s, round: st.round }));
    await W.speak([['takehome-round-ready']]);
    if (!(await W.ok(token))) return;
    // Steps 2 and 3: the sentence waits under Scruffles during a question, where the lookout peeks up from behind the
    // track, so it ducks before the first question comes up (never over the sentence).
    if (s !== 'take' && moments.lookoutShown()) {
      const left = LOOKOUT.min - (performance.now() - up);
      if (left > 0) { await MW.wait(left); if (!(await W.ok(token))) return; }
      moments.lookoutDown();
      await MW.wait(LOOKOUT.duck);
      if (!(await W.ok(token))) return;
    }
    nextQuestion(token);
  }

  // The round's step on the screen: the home planet in step 1, the number track in steps 2 and 3.
  function showMode(s) {
    const nums = s !== 'take';
    track.el.classList.toggle('mw-off', !nums);
    if (nums && track.away()) track.show();
    showHome(!nums);
  }
  function showHome(on) { home.classList.toggle('is-hidden', !on); }
  // Until the first question: the diagram empty, in the step's look (step 1 with its pills, steps 2 and 3 without).
  function blank(s) {
    const none = s === 'take' ? '' : null;                   // the numbers look carries nothing for null
    diagram.look(s === 'take' ? 'counting' : 'numbers');
    diagram.set({ whole: none, left: none, right: none, missing: null });
  }

  function clearBoard() {
    clearHint();
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    st.counters.concat(st.fixed, st.hoppers).forEach(function (c) { c.remove(); });
    st.counters = []; st.fixed = []; st.hoppers = []; st.dimmed = [];
    st.placed = null;
    talk++; st.talking = false;                              // a new question (or leaving): nothing said after a check is going on
    track.reset();                                           // every number tile back in its place
    equation.hide();
  }

  function value(q, k) { return k === 'whole' ? q.whole : (k === GOING ? q.take : q.left); }
  function asDiagram(q) { return { whole: q.whole, left: q.left, right: q.take, missing: q.missing }; }

  // Put question q on the screen, in the round's step (nothing said).
  function setUp(q) {
    const s = step();
    st.q = q;
    st.target = q.missing;
    st.answer = value(q, q.missing);
    st.tries = 0; st.misses = 0; st.hinted = false;
    clearBoard();
    pod.face('thinking');
    pod.lightsOff();                                         // never still flashing into the next question
    stars.set(st.qi);
    if (s === 'take') setTake(q); else setNumbers(q, s);
    st.prompt = promptFor(q, s);
  }

  // Step 1 (board s1-ask): the whole holds its MeeMee in their counting pattern; the going-home part is the waiting
  // circle, its pill saying how many go; the staying part is empty, its pill a waiting "?".
  function setTake(q) {
    diagram.look('counting');
    diagram.set(asDiagram(q));
    diagram.count('whole', q.whole);                        // the whole shows its MeeMee, not its numeral
    pill(GOING, String(q.take), false);
    pill(STAYING, '?', true);
    diagram.slots('whole', q.whole).forEach(function (p, i) {
      const c = MW.counter(layer, { x: p.x, y: p.y, size: p.size });
      c.home = p; c.where = 'whole'; c.idx = i;
      arriving(c);
      st.counters.push(c);
    });
    equation.at('under');                                    // where the sentence shows after a right answer
    showMode('take');
  }
  // A pill's text and look, whatever the circle above it is doing (step 1: the going-home pill keeps its number while
  // its circle waits; the staying pill waits with "?" though its circle doesn't).
  function pill(k, text, waiting) {
    const p = diagram.pills[k];
    p.querySelector('span').textContent = text;
    p.classList.toggle('is-waiting', !!waiting);
  }

  // Steps 2 and 3 (boards s2-ask, s3-ask, s3-whole): the diagram's numbers look (no pills, no "?"), the empty circle
  // waiting; in step 2 the whole and the going-home part hold their MeeMee rather than numbered MeeMee. The sentence
  // waits under Scruffles with its gap where the empty circle's number goes; the number track along the bottom.
  function setNumbers(q, s) {
    diagram.look('numbers');
    diagram.set(asDiagram(q));
    if (s === 'left') {
      diagram.carry('whole', null); diagram.carry(GOING, null);
      lay('whole', q.whole); lay(GOING, q.take);
    }
    showMode(s);
    equation.at('ship');
    showGap();
  }
  // MeeMee (not to drag) in circle k, in its counting pattern
  function lay(k, n, fade) {
    diagram.slots(k, n).forEach(function (p, i) {
      const c = MW.counter(layer, { fixed: true, x: p.x, y: p.y, size: p.size });
      c.where = k; c.idx = i;
      if (fade) arriving(c);
      st.fixed.push(c);
    });
  }
  function arriving(c) {
    c.el.classList.add('is-arriving');                       // they fade in (the arrival holds them visible: let it go)
    c.el.addEventListener('animationend', function () { c.el.classList.remove('is-arriving'); }, { once: true });
  }
  // The sentence with its gap: 7 − 4 = ○ (or 7 − ○ = 3, ○ − 4 = 3)
  function showGap() { const q = st.q; equation.minus(q.whole, q.take, q.left, GAP[q.missing]); }

  async function nextQuestion(token) {
    const q = st.round[st.qi], s = step();
    setUp(q);
    if (st.qi === 0 && s === 'take') later(token, 1800, function () { moments.lookoutDown(); });   // spotted it
    else moments.settle();
    W.st.phase = P.asking;
    MW.log('question', JSON.stringify(Object.assign({ step: s }, q)));
    await W.speak(st.prompt);
    if (token !== W.st.token) return;
    if (W.st.phase === P.asking) W.st.phase = P.open;
  }

  // What's said for a question (lines.md, How they join up): "Seven… MeeMee. Four… are going home." and so on. The first
  // two questions of a round add "Move them into the dotted circle." (step 1) or "Find the number." (steps 2 and 3), and
  // "Tap Scruffles when you're ready." Those two new lines are left out until they are recorded, so a missing recording
  // never silences the question (as MeeMee Rescue's "Find the number.").
  function promptFor(q, s) {
    const whole = [N(q.whole), 'takehome-meemee'];
    const going = [N(q.take), q.take === 1 ? 'takehome-is-going' : 'takehome-are-going'];
    const staying = [N(q.left), q.left === 1 ? 'takehome-is-staying' : 'takehome-are-staying'];
    let p;
    if (s === 'take') p = [whole, going];
    else if (q.missing === STAYING) p = [whole, going, ['takehome-how-many-left']];
    else if (q.missing === GOING) p = [whole, staying, ['takehome-how-many-going']];
    else p = [going, staying, ['takehome-how-many-altogether']];
    if (st.qi < 2) {
      const extra = s === 'take' ? MOVE : FIND;
      if (MW.audio.recorded(extra)) p = p.concat([[extra]]);
      p = p.concat([['tap-scruffles']]);
    }
    return p;
  }

  // ---------------------------------------------------------------- step 1: moving MeeMee
  function inGoing() { return st.counters.filter(function (c) { return c.where === GOING; }); }
  function pickInWhole(e) {
    if (step() !== 'take' || W.st.paused || !answering() || !dragger || dragger.dragging()) return;
    if (e.button !== undefined && e.button > 0) return;
    const p = MW.stage.toStage(e.clientX, e.clientY), w = L.whole;
    if (Math.hypot(p.x - w.x, p.y - w.y) > w.r + L.dropSlack) return;
    let best = null, bestD = Infinity;
    st.counters.forEach(function (c) {
      if (c.where !== 'whole') return;
      const d = Math.hypot(c.x - p.x, c.y - p.y);
      if (d < bestD) { best = c; bestD = d; }
    });
    if (best) best.moveTo(p.x, p.y, best.size, false);
  }
  // The going-home part's MeeMee in its counting pattern (after the hint, in the hint's places while they fit).
  function tidy(animate) {
    const placed = inGoing(), n = placed.length;
    const slots = diagram.slots(GOING, st.hinted && n <= st.answer ? st.answer : n);
    placed.forEach(function (c, i) { c.moveTo(slots[i].x, slots[i].y, slots[i].size, animate); });
    pod.ready(n > 0 && W.st.phase !== P.celebrate);         // the ship's lights glow while there's something to check
  }
  function floatHome(c) {
    c.where = 'whole';
    c.moveTo(c.home.x, c.home.y, c.home.size, true);
  }
  // A drop from the dragger: a number tile (steps 2 and 3) or a MeeMee (step 1).
  function drop(c, x, y, cancelled) {
    if (track.tiles.indexOf(c) >= 0) onTileDrop(c, x, y, cancelled); else onDrop(c, x, y, cancelled);
  }
  // A MeeMee dropped in the going-home part takes that part's counting pattern; anywhere else it floats back to its
  // place in the whole (taken back out of the going-home part, too). A tap or a short drag that ends inside the whole (a
  // child touching the MeeMee to count them) puts it back quietly, as a nudge on MeeMee Rescue's asteroid does.
  function onDrop(c, x, y, cancelled) {
    if (st.counters.indexOf(c) < 0) return;                 // left over from a question that has ended
    const was = c.where;
    if (cancelled || W.st.paused || !answering()) {          // not answering now: just put it back
      if (was === GOING) tidy(true); else floatHome(c);
      return;
    }
    if (diagram.hit(x, y) === GOING) {
      if (was === GOING) { tidy(true); return; }
      c.where = GOING;
      MW.audio.sfx('pop');
      tidy(true);
      pod.face('thinking');
      MW.log('drop', 'in ' + inGoing().length);
      return;
    }
    const nudge = diagram.hit(x, y) === 'whole' || Math.hypot(x - c.home.x, y - c.home.y) <= 70;
    floatHome(c);
    if (was === GOING) { tidy(true); MW.audio.sfx('whoosh'); MW.log('drop', 'out ' + inGoing().length); return; }
    if (nudge) return;                                       // a tap or a nudge in the whole isn't anything
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');                                  // checked by tapping Scruffles, so never a try
  }

  // ---------------------------------------------------------------- steps 2 and 3: number tiles
  // A tile dropped in the empty circle or on the sentence's gap sits in the circle, and the gap shows its number. One
  // tile at a time: another sends the first back. Taken out (dropped anywhere else), it floats back to the track and the
  // sentence has its gap again.
  function onTileDrop(t, x, y, cancelled) {
    const was = t === st.placed;
    if (cancelled || W.st.paused || step() === 'take' || !answering()) {
      if (was) placeTile(t); else t.goHome(true);
      return;
    }
    if (diagram.hit(x, y) === st.target || onGap(x, y)) {
      if (was) { placeTile(t); return; }                     // moved about: back to the circle's middle
      if (st.placed) { st.placed.goHome(true); showGap(); }  // the circle holds one tile: the first goes back
      st.placed = t;
      placeTile(t);
      equation.fill(t.n);
      MW.audio.sfx('pop');
      pod.face('thinking');
      MW.log('drop', 'tile ' + t.n + (diagram.hit(x, y) === st.target ? '' : ' on the gap'));
      pod.ready(true);                                       // the lights glow while there's a tile to check
      return;
    }
    t.goHome(true);
    if (was) { st.placed = null; showGap(); pod.ready(false); MW.audio.sfx('whoosh'); MW.log('drop', 'out'); return; }
    if (Math.hypot(x - t.home.x, y - t.home.y) <= 70) return;  // a nudge on the track isn't anything
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');                                  // checked by tapping Scruffles, so never a try
  }
  function placeTile(t) { const c = L[st.target]; t.moveTo(c.x, c.y, 0, true); }
  // Is (x, y) on the sentence's gap? While it holds a tile's number, where that number is counts too (a tile picked
  // back up and put down there again stays). A little slack round it, as round the circles.
  function onGap(x, y) {
    let g = equation.gap();
    if (!g && st.placed) {
      const part = equation.el.children[2 * GAP[st.target]];
      if (part && equation.el.classList.contains('is-shown')) {
        const r = part.getBoundingClientRect();
        const c = MW.stage.toStage(r.left + r.width / 2, r.top + r.height / 2);
        g = { x: c.x - 42, y: c.y - 42, w: 84, h: 84 };      // a ring-sized box round the number
      }
    }
    if (!g) return false;
    const s = L.dropSlack;
    return x >= g.x - s && x <= g.x + g.w + s && y >= g.y - s && y <= g.y + g.h + s;
  }

  // ---------------------------------------------------------------- checking: tap Scruffles
  function onPodTap() {
    if (W.st.paused || !answering()) return;
    if (dragger && dragger.dragging()) return;              // one hand holding something, the other tapping
    // While Scruffles is still answering a check (a try-again line, too many, the hint), a tap does nothing, so a double
    // tap is one try, not two (0.8.1, B2; MeeMee Rescue does the same)
    if (st.talking) { MW.log('check', 'still answering'); return; }
    if (step() === 'take') {
      const n = inGoing().length;
      MW.log('check', n + ' of ' + st.answer);
      if (n === st.answer) { success(); return; }
      wrongTry(n > st.answer ? 'too-many' : 'too-few');
      return;
    }
    if (!st.placed) {
      // nothing to check: the question again, not a try, but only once Scruffles is quiet (as MeeMee Rescue's numbers mode)
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
    st.placed = null;                                        // a wrong number floats back to the track, the gap comes back
    t.goHome(true);
    showGap();
    pod.ready(false);
    MW.audio.sfx('whoosh');
    wrongTry('number');
  }

  // A wrong check. No red, no buzzer: Scruffles's try-again face, a calm line, and the hint after the second (not for an
  // answer of zero, as in MeeMee Rescue's numbers mode). Too many MeeMee gets its own line.
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
    const hints = st.answer !== 0;
    if (hints && st.tries >= 2 && !st.hinted) { hint(); return; }
    if (hints && st.tries >= 2) return;
    afterCheck(W.speak([[kind === 'number' ? 'again-try-again' : 'again-look-again']]));
  }

  // ---------------------------------------------------------------- the hint: count them together
  // "Count them with me. One, two, three…"
  //   step 1     the places in the going-home part light up (ghosts) as the MeeMee to move are counted (each hops);
  //   steps 2-3  the numbers come back as MeeMee (step 3); in the whole, the ones not going where the answer goes fade,
  //              and the rest are counted into the empty circle with ghosts (each hops as its ghost lights). For the
  //              whole, both parts' MeeMee are counted into it.
  // The answer still has to be given. The MeeMee and ghosts stay until it is; cut short (Hear-again, a pause), the hint
  // is taken away so the next wrong check gives it again in full.
  async function hint() {
    const q = st.q, s = step(), token = W.st.token, qi = st.qi;
    st.hinted = true;
    MW.log('hint', s + ' ' + q.missing);
    diagram.hinting(st.target, true);
    const lines = [['again-count-with-me']], actions = [null];
    const count = function (n, act) {
      for (let i = 1; i <= n; i++) {
        lines.push([i === n ? E(i) : N(i)]);
        actions.push((function (j) { return function () { act(j); }; })(i - 1));
      }
    };
    if (st.ghosts) st.ghosts.clear();
    if (s === 'take') {
      tidy(true);
      const placed = inGoing().length;
      const toMove = st.counters.filter(function (c) { return c.where === 'whole'; });
      st.ghosts = MW.ghosts(ghostLayer, diagram.slots(GOING, Math.max(st.answer, placed)).slice(placed, st.answer));
      count(st.answer, function (j) {
        const inside = inGoing();
        if (j < inside.length) { hop(inside[j]); return; }
        if (st.ghosts) st.ghosts.light(j - placed);
        hop(toMove[j - placed]);
      });
    } else {
      if (s === 'numbers') bringBack(q);
      const from = countFrom(q);
      st.ghosts = MW.ghosts(ghostLayer, diagram.slots(st.target, st.answer));
      count(st.answer, function (j) { hop(from[j]); if (st.ghosts) st.ghosts.light(j); });
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
  // Cut short: everything as before the hint.
  function takeHint() {
    const q = st.q, s = step();
    clearHint();
    st.hinted = false;
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    diagram.hinting(st.target, false);
    undim();
    if (s === 'numbers') takeBack(q); else if (s === 'take') tidy(true);
  }
  // Step 3's hint: the given numbers as MeeMee in their counting patterns, in place of their numbered MeeMee ...
  function bringBack(q) {
    ['whole', STAYING, GOING].forEach(function (k) {
      if (k === q.missing) return;
      diagram.carry(k, null);
      lay(k, value(q, k), true);
    });
  }
  // ... and back to their numbered MeeMee.
  function takeBack(q) {
    st.fixed.forEach(function (c) { c.remove(); });
    st.fixed = []; st.dimmed = [];
    ['whole', STAYING, GOING].forEach(function (k) { if (k !== q.missing) diagram.carry(k, value(q, k)); });
  }
  // The MeeMee counted into the empty circle, in order. From the whole: the ones going home are the rightmost of its
  // pattern (the going-home part is on the right), the ones staying the leftmost; the others fade. Into the whole: the
  // staying part's, then the going-home part's.
  function countFrom(q) {
    const of = function (k) { return st.fixed.filter(function (c) { return c.where === k; }).sort(function (a, b) { return a.idx - b.idx; }); };
    if (q.missing === 'whole') return of(STAYING).concat(of(GOING));
    const whole = of('whole');
    const byX = whole.slice().sort(function (a, b) { return (b.x - a.x) || (a.y - b.y); });   // rightmost first
    const going = byX.slice(0, q.take);
    const fade = q.missing === STAYING ? going : whole.filter(function (c) { return going.indexOf(c) < 0; });
    fade.forEach(function (c) { c.el.classList.add('takehome-dim'); st.dimmed.push(c); });
    return whole.filter(function (c) { return fade.indexOf(c) < 0; });
  }
  function undim() { st.dimmed.forEach(function (c) { c.el.classList.remove('takehome-dim'); }); st.dimmed = []; }
  function clearHint() { st.hintTimers.forEach(clearTimeout); st.hintTimers = []; }
  function hop(c) {
    if (!c) return;
    c.el.classList.remove('is-hop'); void c.el.offsetWidth; c.el.classList.add('is-hop');
  }

  // ---------------------------------------------------------------- a right answer
  // Every right answer ends the same way (boards s1-right, s2-right, s3-right): the answer is carried; Scruffles's
  // got-it face, the ship's lights and the success ring; in steps 2 and 3 the track slides away and the complete
  // sentence moves under the diagram, and the home planet shows; praise; in step 1 the MeeMee left in the whole slide
  // into the staying part and are counted, then the sentence shows; the sentence is said; the star; the MeeMee going
  // home hop off to their houses. Then the next question, or the end screen.
  async function success() {
    if (W.st.phase === P.celebrate) return;
    const token = W.st.token, q = st.q, s = step();
    W.st.phase = P.celebrate;
    clearHint();
    moments.lookoutDown();                                   // a quick first answer: the lookout makes way for the engineer
    const words = sentenceWords(wordTurn());                 // this answer's turn of the sentence's words
    recordAnswer(q, s);
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    undim();
    if (s !== 'take') {
      st.placed = null;                                      // the tile goes back as the track slides down out of sight
      track.hide();
      if (s === 'numbers' && st.fixed.length) {
        // the hint's MeeMee have done their job: they fade, and the given circles carry their numbers again
        st.fixed.forEach(function (m) { m.el.classList.remove('is-arriving'); m.el.classList.add('is-rescued'); });
        ['whole', STAYING, GOING].forEach(function (k) { if (k !== q.missing) diagram.carry(k, value(q, k)); });
      }
      if (equation.gap()) equation.fill(st.answer);          // (it has its number already: the tile filled it)
      equation.at('under', true);
      later(token, 300, function () { showHome(true); });   // once the track has gone
    }
    diagram.success(st.target, st.answer);                   // steps 2 and 3: a numbered MeeMee pops up to carry it
    const c = L[st.target];
    MW.sparkles(fxLayer, c.x, c.y, c.r + 34);
    pod.face('got-it');
    pod.celebrate();                                         // the ship's lights flash for about 4 s
    moments.engineer();                                      // the engineer taps the ship with the spanner
    MW.audio.sfx('chime');
    MW.log('success', JSON.stringify(Object.assign({ step: s }, q)));
    await MW.wait(550);
    if (!(await W.ok(token))) return;
    await W.speak([[nextPraise()]]);
    if (!(await W.ok(token))) return;
    if (s === 'take') {
      if (!(await slideRest(token))) return;
      equation.minus(q.whole, q.take, q.left, null);         // under the diagram, where MeeMee Rescue's shows
    }
    MW.log('words', words.take + ' ' + words.is);
    await W.speak([[N(q.whole), words.take, N(q.take), words.is, E(q.left)]]);
    if (!(await W.ok(token))) return;
    stars.set(st.qi + 1);
    MW.audio.sfx('twinkle');
    moments.navigator(st.qi + 1 < st.round.length ? st.qi + 1 : null);   // the navigator points to the next star
    await MW.wait(800);
    if (!(await W.ok(token))) return;
    await MW.wait(goHome());                                 // the MeeMee going home hop off to their houses
    if (!(await W.ok(token))) return;
    await MW.wait(300);
    if (!(await W.ok(token))) return;
    st.qi++;
    if (st.qi < st.round.length) nextQuestion(token); else endRound(token);
  }
  // MeeMee Rescue's praise and, once it is recorded, "Home they go!" (a praise line on its own would be silent until then)
  function praiseLines() { return PRAISE.concat(MW.audio.recorded(HOME_THEY_GO) ? [HOME_THEY_GO] : []); }
  function nextPraise() {
    if (!st.praise.length) st.praise = MW.shuffle(praiseLines());
    return st.praise.pop();
  }

  // Step 1, right: the MeeMee still in the whole slide into the staying part's pattern one by one, each as its number is
  // said ("One, two, three.", MeeMee Rescue's number recordings; 0.8.1, B1), its pill counting them; then the whole shows
  // its number. If the counting is cut short or can't be heard, the rest slide over one by one as before. Resolves false
  // if the player left meanwhile.
  async function slideRest(token) {
    const rest = st.counters.filter(function (c) { return c.where === 'whole'; }).sort(function (a, b) { return a.idx - b.idx; });
    const slots = diagram.slots(STAYING, rest.length);
    const qi = st.qi;
    pill(STAYING, '?', false);
    let moved = 0;
    // up to and including the i-th, in order and once each, and only while this question is still on
    const slide = function (i) {
      while (moved <= i && moved < rest.length && token === W.st.token && qi === st.qi) slideOne(moved);
    };
    const slideOne = function (i) {
      const c = rest[i];
      c.where = STAYING; c.draggable = false;
      c.moveTo(slots[i].x, slots[i].y, slots[i].size, true);
      hop(c);
      diagram.count(STAYING, i + 1);
      if (i === rest.length - 1) diagram.count('whole', 0); // the whole is empty: its number shows
      MW.log('slide', String(i + 1));
      moved++;
    };
    // one sentence, so the count runs at a counting pace (the hint's count, one sentence a number, is slower, to count along)
    const count = rest.map(function (c, i) { return i === rest.length - 1 ? E(i + 1) : N(i + 1); });
    await W.speak([count], {
      onStart: function (timeline) {
        timeline.forEach(function (clip, i) { later(token, clip.at * 1000, function () { slide(i); }); });
      }
    });
    if (!(await W.ok(token))) return false;
    while (moved < rest.length) {                            // any not slid over yet
      slide(moved);
      await MW.wait(SLIDE);
      if (!(await W.ok(token))) return false;
    }
    await MW.wait(260);
    return W.ok(token);
  }

  // The MeeMee going home hop off to their houses (two hops each: HOP), one after another (about a second in all); with
  // reduce motion they fade from the circle and into the houses instead. Steps 1 and 2: the MeeMee in the going-home
  // part; step 3: as many plain MeeMee as it holds come out from it (its numbered MeeMee stays). Nobody hops for 0.
  // Every hop is started at once, each waiting its turn (the animation's own delay), so a busy moment on the tablet can't
  // send two off together. Returns how long it all takes.
  function goHome() {
    const s = step(), q = st.q;
    let list;
    if (s === 'take') list = inGoing();
    else if (s === 'left') list = st.fixed.filter(function (c) { return c.where === GOING; });
    else {
      list = [];
      for (let i = 0; i < q.take; i++) {
        const c = MW.counter(layer, { fixed: true, x: HOP.from[0], y: HOP.from[1], size: HOP.size });
        c.el.style.opacity = '0';
        c.appear = true;
        list.push(c);
      }
    }
    const n = list.length;
    if (!n) return 0;
    const out = function (c) { return Math.hypot(c.x - HOP.from[0], c.y - HOP.from[1]); };
    list = list.slice().sort(function (a, b) { return out(a) - out(b); });   // the nearest the way out first
    const stagger = n > 1 ? Math.min(HOP.stagger, HOP.spread / (n - 1)) : 0;
    list.forEach(function (c, i) {
      c.draggable = false;
      st.hoppers.push(c);
      hopOff(c, routeFor(i, [c.x, c.y], c.appear), Math.round(i * stagger));
    });
    MW.log('home', n + ' going home');
    return Math.round((n - 1) * stagger + 2 * HOP.step + 100);
  }
  // From where it is, onto the path, then into the house its turn gives it (the right one first, then the middle, then
  // the left): two hops
  function routeFor(i, from, appear) {
    return [appear ? HOP.from : from, HOP.via, HOP.doors[i % HOP.doors.length]];
  }
  // One MeeMee's way home, starting after delay ms. Until then it stays where it is (fill 'both').
  function hopOff(c, route, delay) {
    c.el.classList.remove('is-moving', 'is-arriving', 'is-hop');
    const segs = route.length - 1, end = route[segs];
    if (MW.reduceMotion) {
      // a fade instead: out of the circle, and in and out again by its house, at its turn
      if (!c.appear) { c.el.style.transitionDelay = delay + 'ms'; c.el.classList.add('takehome-gone'); }
      const m = MW.counter(layer, { fixed: true, x: end[0], y: end[1] - 14, size: HOP.size });
      st.hoppers.push(m);
      m.el.animate([{ opacity: 0 }, { opacity: 1, offset: 0.35 }, { opacity: 1, offset: 0.65 }, { opacity: 0 }],
        { duration: segs * HOP.step + 200, delay: delay, fill: 'both' });
      MW.log('home', 'fade');
      return;
    }
    // it hops at 64 px: a MeeMee from the circle grows or shrinks to that on its first hop, then shrinks into the door
    const k = HOP.size / c.size;
    const at = function (p, sc) { return 'translate3d(' + p[0] + 'px,' + p[1] + 'px,0) scale(' + sc + ')'; };
    const frames = [];
    for (let i = 0; i < segs; i++) {
      const a = route[i], b = route[i + 1];
      frames.push({ offset: i / segs, transform: at(a, i === 0 ? 1 : k), opacity: i === 0 && c.appear ? 0 : 1, easing: 'ease-out' });
      frames.push({ offset: (i + 0.5) / segs, transform: at([(a[0] + b[0]) / 2, Math.min(a[1], b[1]) - HOP.rise], k), opacity: 1, easing: 'ease-in' });
    }
    frames.push({ offset: 1, transform: at(end, 0.4 * k), opacity: 0 });
    c.el.style.opacity = '';
    c.el.animate(frames, { duration: segs * HOP.step, delay: delay, fill: 'both' });
    MW.log('hop', delay + ' ' + route.map(function (p) { return Math.round(p[0]) + ',' + Math.round(p[1]); }).join(' '));
  }

  // ---------------------------------------------------------------- the end of a round
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
    await W.speak([['takehome-round-done']]);
    if (!(await W.ok(token))) return;
    hopEnd(160);                                             // the MeeMee home by their houses hop once each, left to right
    await MW.wait(500);
    if (!(await W.ok(token))) return;
    if (moments.commander()) {                               // the commander's radio calls; the MeeMee hop again
      await MW.wait(450);
      hopEnd(120);
      await MW.wait(900);
      if (!(await W.ok(token))) return;
    }
    await W.speak([['takehome-round-another']]);
  }
  function hopEnd(gap) {
    endMimi.forEach(function (m, i) {
      setTimeout(function () { m.classList.remove('is-hop'); void m.getBoundingClientRect(); m.classList.add('is-hop'); }, i * gap);
    });
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

  // ---------------------------------------------------------------- grown-ups: the Subtraction tab (boards grownups, grid-final)
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
        MW.log('setting', 'takehome step ' + s);
      }, 'gu-choice');
      b.setAttribute('data-step', s);
    });
    paintStep();
    G.p(el, '<b>Take away</b> (the first step): the MeeMee sit in the whole. Your child drags the ones going home into their part, then taps Scruffles. The rest slide into the other part, and the number sentence shows.');
    G.p(el, '<b>How many are left:</b> the whole and the part going home show their MeeMee, and the number sentence waits for its answer. Your child drags a number tile into the empty circle, and it fills the gap in the sentence. Two wrong tries: the MeeMee going home fade, and the ones left are counted together.');
    G.p(el, '<b>Numbers:</b> each circle shows a MeeMee holding its number, and the gap can be anywhere in the sentence: <span class="takehome-nw">7 − 4 = ?</span>, <span class="takehome-nw">7 − ? = 3</span> or <span class="takehome-nw">? − 4 = 3</span>.');
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
        MW.log('setting', 'takehome wholes ' + on.join(','));
      }, 'mw-chip gu-chip takehome-whole');
    }
    paintW();
    G.p(el, 'Questions use only the wholes switched on. Changes start with the next round.', 'gu-note');   // as MeeMee Rescue's (0.8.1, B5)

    const prog = MW.make('div', 'takehome-progress');
    el.appendChild(prog);
    renderProgress(prog);

    const row = G.row(el);
    let armed = 0;
    G.btn(row, 'Clear this tablet\'s progress', function (b) {
      if (Date.now() - armed < 4000) {
        const g = MW.store.game(ID); delete g.answers; MW.store.save();   // this game's answers only; its step and wholes stay
        MW.log('takehome', 'progress cleared');
        armed = 0; b.textContent = 'Clear this tablet\'s progress';
        renderProgress(prog);
      } else {
        armed = Date.now(); b.textContent = 'Tap again to clear';
        setTimeout(function () { b.textContent = 'Clear this tablet\'s progress'; }, 4000);
      }
    }, 'gu-quiet takehome-clear');
  }
  // "Showing progress for": which step's grid shows (each step keeps its own progress), its summary, the grid, the
  // legend and the notes. The Numbers grid adds each whole's zero facts.
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
    // the summary counts the 45 facts in every step; in Numbers the zero facts have a line of their own (0.8.1, B4)
    const n = { secure: 0, practising: 0, total: 0 }, zero = { secure: 0, practising: 0, total: 0 };
    const grid = MW.make('div', 'gu-grid');
    for (let w = 2; w <= 10; w++) {
      const rowEl = MW.make('div', 'gu-grid-row');
      rowEl.appendChild(MW.make('span', 'gu-grid-whole', null, String(w)));
      F.facts(w, shown === 'numbers').forEach(function (t) {
        const status = F.status(map, w, t);
        const tally = t === 0 || t === w ? zero : n;
        tally.total++;
        if (status === 'secure') tally.secure++; else if (status === 'practising') tally.practising++;
        rowEl.appendChild(cell(status, w + ' − ' + t));
      });
      grid.appendChild(rowEl);
    }
    G.p(box, list.length
      ? 'Secure: ' + n.secure + ' of ' + n.total + ' facts. Practising: ' + n.practising + '. Questions answered this step on this tablet: ' + list.length + '.'
      : 'No questions answered this step on this tablet yet.', 'gu-lead');
    if (list.length && zero.total) {
      G.p(box, 'Zero facts: ' + zero.secure + ' of ' + zero.total + ' secure. Practising: ' + zero.practising + '.', 'gu-lead takehome-zero-lead');
    }
    box.appendChild(grid);
    const legend = MW.make('div', 'gu-legend');
    legend.appendChild(cell('secure', 'Secure'));
    legend.appendChild(cell('practising', 'Practising'));
    legend.appendChild(cell('notyet', 'Not yet'));
    box.appendChild(legend);
    G.p(box, '<b>Secure</b> means right first time (no wrong check and no hint) on three different days. A wrong answer moves a fact back to practising, and its three days start again. Each step keeps its own progress, separate from MeeMee Rescue\'s.', 'gu-note');
    G.p(box, '<b>Zero facts</b> (such as 7 − 0 and 7 − 7) come up in Numbers only, once the other facts of that number are secure; that step\'s grid shows them.', 'gu-note');
  }

  // ---------------------------------------------------------------- test hooks
  R.drop = drop; R.podTap = onPodTap; R.start = startRound; R.home = W.home; R.makeRound = makeRound; R.step = step;
  R.diagram = function () { return diagram; }; R.track = function () { return track; }; R.equation = function () { return equation; };
  R.homePlanet = function () { return home; }; R.answers = answers; R.gapTurn = gapTurn; R.praiseLines = praiseLines;
  R.wordTurn = wordTurn; R.sentenceWords = sentenceWords;
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
    setUp(st.round[0]);
    W.st.phase = P.open;
    return W.st.token;
  };
})();
