/* MeeMee Rescue: number bonds to 10 on the part–whole diagram (phases 3 to 5).
   The first MeeMee World game, and the worked example for new ones. It joins the world (kit/world.js) with
   MW.world.game below; the world gives it the start screen, the map, the crew screen, pausing and the grown-ups area.
   Its planet starts a round of five part–whole questions in Barney's voice, chosen from the bonds that need work
   (bonds.js). The player drags MeeMee from the asteroid into the waiting circle. Each crew job has its moment in a
   round (moments.js). Grown-ups see the progress grid.
   Numbers mode (0.6.0; NumbersMode card, round 8's Numbers8 boards), which a grown-up turns on in Settings ("How your
   child answers"): each given circle holds a MeeMee carrying its number, and the player drags a number tile (0 to 10)
   from the number track along the bottom into the waiting circle. Two wrong tries bring the MeeMee back to count on (never for a zero answer).
   Each way keeps its own progress: every answer is saved with its mode.
   Older than the rules for new games, so some names don't have the game's prefix: its screens are screen-game and
   screen-end, its voice lines have no "rescue-" in front, and its saved answers and settings sit at the top level. */
(function () {
  'use strict';
  const MW = window.MW;
  const ROUND = 5;
  const PRAISE = ['praise-found-it', 'praise-thats-right', 'praise-super-counting', 'praise-brilliant-rescuing', 'praise-well-done'];
  const N = function (n) { return 'num-mid-' + n; };
  const E = function (n) { return 'num-end-' + n; };
  const OTHER = { left: 'right', right: 'left' };
  const FIND = 'rescue-find-number';                         // "Find the number." (numbers mode)
  // the two ways of answering, as the grown-ups area names them (Settings and the Progress tab's switch)
  const WAYS = [['counting', 'MeeMee to count'], ['numbers', 'Numbers']];

  const W = MW.world;
  const st = { hintTimers: [], round: null, qi: 0, q: null, target: null, answer: 0,
    counters: [], fixed: [], tries: 0, misses: 0, hinted: false, ghosts: null, prompt: null, praise: [], check: null,
    mode: null, placed: null,                                // numbers mode: the way of answering, and the tile in the circle
    talking: false };                                        // Scruffles is saying something after a check (afterCheck)
  // the token, the phase and pausing belong to the world (one of each for the page); st reads and writes them there
  ['token', 'phase', 'paused'].forEach(function (k) {
    Object.defineProperty(st, k, { enumerable: true, get: function () { return W.st[k]; }, set: function (v) { W.st[k] = v; } });
  });
  const R = MW.rescue = { st: st, nextRound: null };
  let diagram, stars, equation, pod, endPod, layer, ghostLayer, fxLayer, endStars, endMimi, dragger, tray, track, moments;
  let view = null;                                           // the Progress tab's switch: which way's progress it shows
  let talk = 0;                                              // counts what's said after a check (afterCheck)
  const endCats = {};
  const speak = W.speak, ok = W.ok;

  // ---------------------------------------------------------------- joining the world
  W.game({
    id: 'rescue',
    build: function () {
      buildGame();
      buildEnd();
      moments = MW.moments({ game: MW.$('screen-game'), tray: tray.el, over: ghostLayer, stars: stars, end: MW.$('screen-end'), endCats: endCats });
      // 9 October: "tap Scruffles to check" became the default. A tablet still on the old default moves to it once;
      // a mode a grown-up picks in Settings from now on is kept.
      if (!MW.store.setting('checkPicked') && MW.store.setting('check') !== 'tap') MW.store.setting('check', 'tap');
    },
    start: function () { startRound(); },
    sections: [progressSection(), settingsSection()],
    onPause: function () { clearHint(); if (dragger) dragger.cancel(); },
    onResume: function () { if (MW.shell.screen === 'screen-game' && (st.phase === 'open' || st.phase === 'asking')) speak(st.prompt); },
    onHome: leave
  });

  function buildGame() {
    const s = W.screen('screen-game', 'MeeMee Rescue');
    diagram = MW.diagram(s);
    // the ship goes in before the asteroid (they don't overlap), so the lookout can peek out between them
    pod = MW.pod(s, MW.LAYOUT.pod.x, MW.LAYOUT.pod.y, MW.LAYOUT.pod.w);
    tray = MW.tray(s);
    MW.onTap(pod.el, onPodTap);
    equation = MW.equation(s);
    stars = MW.stars(s, MW.LAYOUT.stars.x, MW.LAYOUT.stars.y);
    ghostLayer = MW.make('div', 'mw-layer mw-fill'); s.appendChild(ghostLayer);
    layer = MW.make('div', 'mw-layer mw-fill mw-counters'); s.appendChild(layer);
    // numbers mode's number track (the kit's): above the counters, so a tile dropped in a circle shows over it and over
    // the hint's MeeMee, and in front of the lookout. Hidden in counting mode, as the asteroid is in numbers mode.
    track = MW.numberTrack(s);
    track.el.classList.add('mw-off');
    fxLayer = MW.make('div', 'mw-layer mw-fill mw-fx'); s.appendChild(fxLayer);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: W.home, hear: hearAgain });
    dragger = MW.dragger(s, {
      counters: function () { return numbers() ? track.tiles : st.counters; },
      enabled: function () { return !st.paused && (st.phase === 'asking' || st.phase === 'open'); },
      onPick: function (c) { MW.log('pick', c.where || 'tile ' + c.n); },
      onDrop: drop
    });
  }

  function buildEnd() {
    const s = W.screen('screen-end', 'All the MeeMee rescued');
    endStars = MW.stars(s, 450, 40, 60);
    const mog = MW.make('div', 'mw-abs mw-crew', { style: 'left:70px;top:330px' }); mog.appendChild(endCats.moggles = MW.crew.cat('moggles', 240)); s.appendChild(mog);
    const p = endPod = MW.pod(s, 380, 130, 400); p.face('got-it'); p.el.disabled = true; p.el.tabIndex = -1;
    const snu = MW.make('div', 'mw-abs mw-crew', { style: 'left:790px;top:330px' }); snu.appendChild(endCats.snuffles = MW.crew.cat('snuffles', 240)); s.appendChild(snu);
    endMimi = MW.make('div', 'mw-abs mw-start-mimi', { style: 'left:352px;top:600px' });
    for (let i = 0; i < 5; i++) endMimi.appendChild(MW.art('mimi'));
    s.appendChild(endMimi);
    const play = MW.make('button', 'mw-btn mw-btn--play mw-abs', { type: 'button', 'aria-label': 'Another rescue', id: 'again', style: 'left:1080px;top:420px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    play.appendChild(icon);
    MW.onTap(play, function () { MW.audio.unlock(); MW.shell.fullscreen(); startRound(); });
    s.appendChild(play);
    MW.shell.buttons(s, ['home', 'music'], { home: W.home });
  }

  // ---------------------------------------------------------------- a round
  function makeRound() {
    if (R.nextRound) { const r = R.nextRound; R.nextRound = null; return r.map(function (q) { return Object.assign({}, q); }); }
    let wholes = (MW.store.setting('wholes') || []).filter(function (w) { return w >= 2 && w <= 10; });
    if (!wholes.length) wholes = [2, 3, 4, 5, 6, 7, 8, 9, 10];
    // With MeeMee to count, zero bonds are answered with an empty circle, so they come up only when the answer is checked
    // by tapping Scruffles; in numbers mode there is a 0 tile, so they come up whichever check is set. Each way of
    // answering has its own progress, so a round picks from its own way's answers.
    const m = mode();
    return MW.bonds.pickRound({ wholes: wholes, answers: MW.bonds.ofMode(MW.store.get('answers') || [], m), size: ROUND,
      zero: m === 'numbers' || check() === 'tap' });
  }

  async function startRound() {
    const token = ++st.token;
    st.check = savedCheck();
    st.mode = savedMode();
    st.round = makeRound();
    st.qi = 0;
    clearBoard(true);
    showMode();
    moments.clear();
    MW.shell.show('screen-game');
    stars.set(0);
    st.phase = 'starting';
    moments.lookoutUp(numbers() ? 'track' : null);           // the lookout peeks over the asteroid (or the number track)
    MW.log('round', JSON.stringify(st.round));
    await speak([['round-ready']]);
    if (!(await ok(token))) return;
    nextQuestion(token);
  }

  function clearBoard(all) {
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    st.counters.concat(st.fixed).forEach(function (c) { c.remove(); });
    st.counters = []; st.fixed = [];
    st.placed = null;
    talk++; st.talking = false;                              // a new question (or leaving): nothing said after a check is going on
    track.reset();                                           // every number tile back in its place
    if (all) { equation.hide(); }
  }
  // The round's way of answering on the screen: the diagram's look, and the asteroid or the number track.
  function showMode() {
    const n = numbers();
    diagram.look(n ? 'numbers' : 'counting');
    tray.el.classList.toggle('mw-off', n);
    track.el.classList.toggle('mw-off', !n);
    if (n && track.away()) track.show();
  }

  async function nextQuestion(token) {
    const q = st.q = st.round[st.qi];
    st.target = q.missing;
    st.answer = q.missing === 'whole' ? q.whole : q[q.missing];
    st.tries = 0; st.misses = 0; st.hinted = false;
    clearBoard(true);
    diagram.set(q);
    pod.face('thinking');
    pod.lightsOff();                                         // never still flashing into the next question
    if (st.qi === 0) setTimeout(function () { if (token === st.token) moments.lookoutDown(); }, 1800);   // spotted them
    else moments.settle();
    stars.set(st.qi);
    if (numbers()) {
      // numbers mode: the given circles hold numbered MeeMee (diagram.set did that), and the track is back for this question
      if (track.away()) track.show();
    } else {
      // the MeeMee already rescued: the given part(s), in their counting pattern
      ['left', 'right'].forEach(function (k) {
        if (k === q.missing) return;
        diagram.slots(k, q[k]).forEach(function (p) {
          st.fixed.push(MW.counter(layer, { fixed: true, x: p.x, y: p.y, size: p.size }));
        });
      });
      // ten MeeMee waiting on the asteroid: more than any answer needs
      MW.LAYOUT.traySlots.forEach(function (p, i) {
        const c = MW.counter(layer, { x: p.x, y: p.y });
        c.home = p; c.where = 'tray'; c.slot = i;
        c.el.classList.add('is-arriving');
        c.el.addEventListener('animationend', function () { c.el.classList.remove('is-arriving'); }, { once: true });
        st.counters.push(c);
      });
    }
    st.prompt = promptFor(q);
    // numbers mode: the first two questions of a round say "Find the number." after the question. Left out until it is
    // recorded, so a missing recording never silences the question.
    if (numbers() && st.qi < 2 && MW.audio.recorded(FIND)) st.prompt = st.prompt.concat([[FIND]]);
    // tap mode: the first two questions of a round end with "Tap Scruffles when you're ready.", and so does any question
    // whose answer is zero (with MeeMee to count the answer is an empty circle and a tap on Scruffles; in numbers mode
    // the check works the same way, as Settings says)
    if (check() === 'tap' && (st.qi < 2 || st.answer === 0)) st.prompt = st.prompt.concat([['tap-scruffles']]);
    st.phase = 'asking';
    MW.log('question', JSON.stringify(q));
    await speak(st.prompt);
    if (token !== st.token) return;
    if (st.phase === 'asking') st.phase = 'open';
  }

  function promptFor(q) {
    if (q.missing === 'whole') return [['q-weve-got', N(q.left), 'and', E(q.right)], ['q-how-many-altogether']];
    const given = q[OTHER[q.missing]];
    return [['q-lets-make', E(q.whole)], ['q-weve-got', E(given)], ['q-how-many-more']];
  }

  // ---------------------------------------------------------------- dragging and dropping
  function inTarget() { return st.counters.filter(function (c) { return c.where === st.target; }); }
  function tidy(animate) {
    const placed = inTarget();
    const n = placed.length;
    const slots = diagram.slots(st.target, st.hinted && n <= st.answer ? st.answer : n);
    placed.forEach(function (c, i) { c.moveTo(slots[i].x, slots[i].y, slots[i].size, animate); });
    diagram.count(st.target, n);
    pod.ready(check() === 'tap' && n > 0 && st.phase !== 'celebrate');
  }
  // How answers are checked. A round keeps the mode it started with (its zero bonds need tap mode);
  // a change in Settings starts with the next round.
  function savedCheck() { return MW.store.setting('check') === 'tap' ? 'tap' : 'auto'; }
  function check() { return st.check || savedCheck(); }
  // How the player answers: 'counting' (MeeMee to count, the usual way) or 'numbers' (a number tile). Like the check, a
  // round keeps the way it started with; a change in Settings starts with the next round.
  function savedMode() { return MW.store.setting('answerMode') === 'numbers' ? 'numbers' : 'counting'; }
  function mode() { return st.mode || savedMode(); }
  function numbers() { return mode() === 'numbers'; }

  // A drop from the dragger: a number tile (numbers mode) or a MeeMee.
  function drop(c, x, y, cancelled) {
    if (track.tiles.indexOf(c) >= 0) onTileDrop(c, x, y, cancelled); else onDrop(c, x, y, cancelled);
  }

  function onDrop(c, x, y, cancelled) {
    if (st.counters.indexOf(c) < 0) return;                 // left over from a question that has ended
    const was = c.where;
    // Not answering now (paused, celebrating, or a touch taken away by the tablet): just put it back.
    if (cancelled || st.paused || !(st.phase === 'open' || st.phase === 'asking')) {
      if (was === st.target) tidy(true);                    // it was already in the circle: back to its place there
      else floatHome(c);
      return;
    }
    const hit = diagram.hit(x, y);
    if (hit === st.target) {
      if (was === st.target) { tidy(true); return; }
      if (check() === 'auto' && inTarget().length >= st.answer) { floatHome(c); return; }
      c.where = st.target;
      MW.audio.sfx('pop');
      tidy(true);
      pod.face('thinking');
      MW.log('drop', 'in ' + inTarget().length);
      if (check() === 'auto' && inTarget().length === st.answer) success();
      return;
    }
    // anywhere else: the MeeMee floats back to its own spot on the asteroid
    const far = Math.hypot(x - c.home.x, y - c.home.y) > 70;
    floatHome(c);
    if (was === st.target) { tidy(true); MW.audio.sfx('whoosh'); MW.log('drop', 'out ' + inTarget().length); return; }
    if (!far) return;                       // a nudge on the asteroid isn't a try
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');
    if (check() === 'auto') wrongTry('miss');
  }
  function floatHome(c) {
    c.where = 'tray';
    c.moveTo(c.home.x, c.home.y, 80, true);
  }

  // Numbers mode: a number tile dropped. Anywhere inside the waiting circle's rim puts it there (one tile at a time: a
  // second one sends the first back); anywhere else, it floats back to its place on the track.
  function onTileDrop(t, x, y, cancelled) {
    const was = t === st.placed;
    // Not answering now (paused, celebrating, or a touch taken away by the tablet): just put it back.
    if (cancelled || st.paused || !numbers() || !(st.phase === 'open' || st.phase === 'asking')) {
      if (was) placeTile(t); else t.goHome(true);
      return;
    }
    if (diagram.hit(x, y) === st.target) {
      if (was) { placeTile(t); return; }                     // moved about inside the circle: back to its middle
      if (st.placed) st.placed.goHome(true);                 // the circle holds one tile: the first goes back
      st.placed = t;
      placeTile(t);
      MW.audio.sfx('pop');
      pod.face('thinking');
      MW.log('drop', 'tile ' + t.n);
      pod.ready(check() === 'tap');                          // tap mode: the lights glow while there's a tile to check
      if (check() === 'auto') checkTile();
      return;
    }
    t.goHome(true);
    if (was) { st.placed = null; pod.ready(false); MW.audio.sfx('whoosh'); MW.log('drop', 'out'); return; }   // taken back out
    if (Math.hypot(x - t.home.x, y - t.home.y) <= 70) return;  // a nudge on the track isn't a try
    MW.audio.sfx('whoosh');
    MW.log('drop', 'miss');
    if (check() === 'auto') wrongTry('miss');               // as a far-off MeeMee: a try only when checked as it lands
  }
  function placeTile(t) { const c = MW.LAYOUT[st.target]; t.moveTo(c.x, c.y, 0, true); }
  // Numbers mode: the tile in the circle is checked (as it lands, or when Scruffles is tapped).
  function checkTile() {
    const t = st.placed;
    MW.log('check', 'tile ' + t.n + ' for ' + st.answer);
    if (t.n === st.answer) { success(); return; }
    st.placed = null;                                        // a wrong number floats back to the track
    t.goHome(true);
    pod.ready(false);
    MW.audio.sfx('whoosh');
    wrongTry('number');
  }

  // Tapping Scruffles: checks the answer in "tap" mode; otherwise asks the question again.
  function onPodTap() {
    if (st.paused || !(st.phase === 'open' || st.phase === 'asking')) return;
    if (dragger && dragger.dragging()) return;              // one hand holding a MeeMee, the other tapping
    if (check() !== 'tap') { hearAgain(); return; }
    // While Scruffles is still answering a check (a try-again line, too many, the hint), a tap does nothing, so a double
    // tap is one try, not two (decided by Barney, 16 October 2026, 0.8.1; Take MeeMee Home does the same)
    if (st.talking) { MW.log('check', 'still answering'); return; }
    if (numbers()) {
      if (!st.placed) {
        // nothing to check: the question again, not a try, but only once Scruffles is quiet. While he's saying "Let's try
        // again." or giving the hint (or asking), a tap (a double tap's second, an impatient one) does nothing.
        if (st.talking || MW.audio.speaking()) { MW.log('check', 'no tile, waiting'); return; }
        MW.log('check', 'no tile');
        hearAgain();
        return;
      }
      checkTile();
      return;
    }
    const n = inTarget().length;
    MW.log('check', n + ' of ' + st.answer);
    if (n === st.answer) { success(); return; }
    wrongTry(n > st.answer ? 'too-many' : 'too-few');
  }

  // A wrong try: a wrong check (tap mode), a wrong number (numbers mode) or a MeeMee or tile dropped away from the waiting
  // circle (a miss, when the answer is checked as it lands).
  // No red, no buzzer: Scruffles's try-again face, a calm line, and the hint after the second one (not for a zero answer
  // in numbers mode).
  // What Scruffles says after a check (the try-again line, the hint): st.talking is true from the moment it's asked for
  // until it ends or is cut short, so a tap on him meanwhile can wait for it (numbers mode, no tile in the circle).
  function afterCheck(saying) {
    const n = ++talk;
    st.talking = true;
    saying.then(function () { if (n === talk) st.talking = false; });
    return saying;
  }
  function wrongTry(kind) {
    if (kind === 'miss') st.misses++; else st.tries++;
    const count = kind === 'miss' ? st.misses : st.tries;
    pod.face('try-again');
    const token = st.token, qi = st.qi;
    setTimeout(function () { if (token === st.token && qi === st.qi && st.phase !== 'celebrate') pod.face('thinking'); }, 1600);
    if (kind === 'too-many') { afterCheck(speak([['too-many']])); return; }
    // Numbers mode, an answer of zero (5 + ? = 5): never the hint, however many tries; each gets "Let's try again." (decided
    // by Barney, 11 October 2026: counting on by nothing shows nothing). Counting mode is as before.
    const hints = !(numbers() && st.answer === 0);
    if (hints && count >= 2 && !st.hinted) { hint(); return; }
    if (hints && count >= 2) return;
    afterCheck(speak([[kind === 'miss' || kind === 'number' ? 'again-try-again' : 'again-look-again']]));
  }

  // ---------------------------------------------------------------- the hint: count on together
  // Numbers mode (Numbers8Hint): the given part (both parts, for a missing whole) comes back as MeeMee in its counting
  // pattern and the whole keeps its numbered MeeMee; the waiting circle counts on with ghosts, with the same lines. The
  // player still drags the number. The MeeMee and ghosts stay until the question is answered.
  async function hint() {
    const q = st.q, token = st.token, qi = st.qi, nums = numbers();
    st.hinted = true;
    MW.log('hint', q.missing);
    diagram.hinting(st.target, true);
    if (nums) bringBack(q); else tidy(true);
    const placed = nums ? 0 : inTarget().length;
    const slots = diagram.slots(st.target, Math.max(st.answer, placed));
    if (st.ghosts) st.ghosts.clear();
    st.ghosts = MW.ghosts(ghostLayer, slots.slice(placed, st.answer));
    let lines, actions;
    if (q.missing === 'whole') {
      // "Count them with me. One, two, three…": each MeeMee in the parts hops as its number is said
      const order = st.fixed.slice();
      lines = [['again-count-with-me']];
      actions = [null];
      for (let i = 1; i <= q.whole; i++) {
        lines.push([i === q.whole ? E(i) : N(i)]);
        actions.push((function (c, j) { return function () { hop(c); if (st.ghosts) st.ghosts.light(j - placed); }; })(order[i - 1], i - 1));
      }
    } else {
      // "Let's count on from three. Four, five, six, seven."
      const given = q[OTHER[q.missing]];
      lines = [['q-count-on-from', E(given)]];
      actions = [null];
      for (let i = 1; i <= st.answer; i++) {
        lines.push([given + i === q.whole ? E(given + i) : N(given + i)]);
        actions.push((function (j) {
          return function () {
            const inside = nums ? [] : inTarget();
            if (j < inside.length) hop(inside[j]); else if (st.ghosts) st.ghosts.light(j - placed);
          };
        })(i - 1));
      }
    }
    const heard = await afterCheck(speak(lines, {
      onStart: function (timeline) {
        // one entry per clip; the first line may have two clips
        let k = 0;
        lines.forEach(function (sent, si) {
          const at = timeline[k].at;
          k += sent.length;
          if (actions[si]) st.hintTimers.push(setTimeout(function () { if (token === st.token && qi === st.qi) actions[si](); }, at * 1000));
        });
      }
    }));
    // Cut short (Hear-again, a pause): take the hint away so the next wrong try gives it again in full.
    if (!heard && token === st.token && qi === st.qi && st.phase !== 'celebrate') {
      clearHint();
      st.hinted = false;
      if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
      diagram.hinting(st.target, false);
      if (nums) takeBack(q); else tidy(true);
    }
  }
  // Numbers mode's hint: the given part(s) as MeeMee in their counting pattern, in place of their numbered MeeMee ...
  function bringBack(q) {
    ['left', 'right'].forEach(function (k) {
      if (k === q.missing) return;
      diagram.carry(k, null);
      diagram.slots(k, q[k]).forEach(function (p) {
        const c = MW.counter(layer, { fixed: true, x: p.x, y: p.y, size: p.size });
        c.el.classList.add('is-arriving');                   // they fade in (the arrival holds them visible: let it go)
        c.el.addEventListener('animationend', function () { c.el.classList.remove('is-arriving'); }, { once: true });
        st.fixed.push(c);
      });
    });
  }
  // ... and back to their numbered MeeMee (a hint cut short, so the next wrong try gives it again in full).
  function takeBack(q) {
    st.fixed.forEach(function (c) { c.remove(); });
    st.fixed = [];
    ['left', 'right'].forEach(function (k) { if (k !== q.missing) diagram.carry(k, q[k]); });
  }
  function clearHint() {
    st.hintTimers.forEach(clearTimeout);
    st.hintTimers = [];
  }
  function hop(c) {
    if (!c) return;
    c.el.classList.remove('is-hop'); void c.el.offsetWidth; c.el.classList.add('is-hop');
  }

  // ---------------------------------------------------------------- a right answer
  async function success() {
    if (st.phase === 'celebrate') return;
    const token = st.token, q = st.q;
    st.phase = 'celebrate';
    clearHint();
    moments.lookoutDown();                                   // a quick first answer: the lookout makes way for the engineer
    MW.store.recordAnswer({ t: Date.now(), whole: q.whole, left: q.left, right: q.right, missing: q.missing,
      tries: st.tries, misses: st.misses, hint: st.hinted, check: check(), mode: mode() });
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    if (numbers()) {
      // Numbers8Right: a MeeMee pops up to carry the number (diagram.success, below) in place of the tile, which goes
      // back as the track slides down out of sight
      st.placed = null;
      track.hide();
      // the hint's MeeMee have done their job: they fly up to the ship, and the given parts carry their numbers again
      st.fixed.forEach(function (m) {
        m.el.classList.remove('is-arriving');
        m.el.classList.add('is-rescued');
        if (!MW.reduceMotion) m.moveTo(1030 + (Math.random() * 60 - 30), 300, 30, true);   // reduce motion: just fade
      });
      if (st.fixed.length) ['left', 'right'].forEach(function (k) { if (k !== q.missing) diagram.carry(k, q[k]); });
    }
    diagram.success(st.target, st.answer);
    const c = MW.LAYOUT[st.target];
    MW.sparkles(fxLayer, c.x, c.y, c.r + 34);
    pod.face('got-it');
    pod.celebrate();                                         // the ship's lights flash for about 4 s
    moments.engineer();                                      // the engineer taps the ship with the spanner
    MW.audio.sfx('chime');
    MW.log('success', JSON.stringify(q));
    await MW.wait(550);
    if (!(await ok(token))) return;
    st.praise = st.praise.length ? st.praise : MW.shuffle(PRAISE);
    await speak([[st.praise.pop()]]);
    if (!(await ok(token))) return;
    equation.show(q.left, q.right, q.whole);
    await speak([[N(q.left), 'and', N(q.right), 'make', E(q.whole)]]);
    if (!(await ok(token))) return;
    stars.set(st.qi + 1);
    MW.audio.sfx('twinkle');
    moments.navigator(st.qi + 1 < ROUND ? st.qi + 1 : null); // the navigator points to the next star
    await MW.wait(800);
    if (!(await ok(token))) return;
    // the rescued MeeMee fly up into the pod (numbers mode: the hint's went as the answer came)
    if (!numbers()) inTarget().concat(st.fixed).forEach(function (m) {
      m.el.classList.add('is-rescued');
      if (!MW.reduceMotion) m.moveTo(1030 + (Math.random() * 60 - 30), 300, 30, true);   // reduce motion: just fade
    });
    await MW.wait(650);
    if (!(await ok(token))) return;
    st.qi++;
    if (st.qi < ROUND) nextQuestion(token); else endRound(token);
  }

  async function endRound(token) {
    st.phase = 'done';
    clearBoard(true);
    MW.shell.show('screen-end');
    endStars.set(ROUND, ROUND);
    const jobs = MW.crew.jobs();
    MW.crew.CATS.forEach(function (w) { endCats[w].setJob(jobs[w]); });
    MW.audio.sfx('tune');
    endPod.celebrate();
    await MW.wait(300);
    await speak([['round-rescued-all']]);
    if (!(await ok(token))) return;
    // the rescued MeeMee hop once each, left to right
    Array.prototype.forEach.call(endMimi.children, function (m, i) {
      setTimeout(function () { m.classList.remove('is-hop'); void m.getBoundingClientRect(); m.classList.add('is-hop'); }, i * 160);
    });
    await MW.wait(500);
    if (!(await ok(token))) return;
    if (moments.commander()) {                               // the commander's radio calls; the MeeMee hop again
      await MW.wait(450);
      Array.prototype.forEach.call(endMimi.children, function (m, i) {
        setTimeout(function () { m.classList.remove('is-hop'); void m.getBoundingClientRect(); m.classList.add('is-hop'); }, i * 120);
      });
      await MW.wait(900);
      if (!(await ok(token))) return;
    }
    await speak([['round-another']]);
  }

  function hearAgain() {
    if (st.paused) return;
    if (st.phase === 'open' || st.phase === 'asking') { clearHint(); speak(st.prompt); }
  }
  // Home (from any screen, this game's or the world's): put everything away. The world has moved on the token,
  // so speech and timers from the round stop themselves.
  function leave() {
    clearHint();
    if (dragger) dragger.cancel();
    st.check = null; st.mode = null;
    pod.lightsOff(); endPod.lightsOff();
    clearBoard(true);
    if (moments) moments.clear();
  }

  // ---------------------------------------------------------------- grown-ups: progress and settings
  function sentence(a) {
    if (a.missing === 'whole') return a.left + ' + ' + a.right + ' = ?';
    if (a.missing === 'left') return '? + ' + a.right + ' = ' + a.whole;
    return a.left + ' + ? = ' + a.whole;
  }
  // one cell of the progress grid: a tick for secure, a dashed edge for practising, faint for not yet
  function cell(status, text) {
    const c = MW.make('span', 'mw-cell label is-' + status);
    if (status === 'secure') {
      const tick = MW.art('icon-tick'); tick.setAttribute('width', 16); tick.setAttribute('height', 16);
      c.appendChild(tick);
    }
    c.appendChild(document.createTextNode(text));
    return c;
  }
  function progressSection() {
    return {
      id: 'progress', title: 'Progress',
      render: function (el) {
        const G = MW.grownups;
        // which way's progress shows (Grownups8Progress): each way of answering keeps its own
        const shown = view || savedMode();
        G.h3(el, 'Showing progress for');
        const r0 = G.row(el);
        WAYS.forEach(function (m) {
          const b = G.btn(r0, m[1], function () { view = m[0]; MW.grownups.show('progress'); }, 'gu-choice');
          b.classList.toggle('is-on', m[0] === shown);
          b.setAttribute('data-way', m[0]);
        });
        G.p(el, 'Each way keeps its own progress: a bond secure with MeeMee to count starts again with numbers.');
        const all = MW.store.get('answers') || [];
        const answers = MW.bonds.ofMode(all, shown);
        const map = MW.bonds.statuses(answers);
        let nSecure = 0, nPractising = 0, total = 0;
        // the progress grid (the design system's BondGrid): every bond of 2 to 10, smaller part first
        const grid = MW.make('div', 'gu-grid');
        for (let w = 2; w <= 10; w++) {
          const row = MW.make('div', 'gu-grid-row');
          row.appendChild(MW.make('span', 'gu-grid-whole', null, String(w)));
          MW.bonds.pairs(w).forEach(function (pr) {
            const status = MW.bonds.status(map, w, pr[0]);
            total++;
            if (status === 'secure') nSecure++; else if (status === 'practising') nPractising++;
            row.appendChild(cell(status, pr[0] + ' + ' + pr[1]));
          });
          grid.appendChild(row);
        }
        G.p(el, answers.length
          ? 'Secure: ' + nSecure + ' of ' + total + ' bonds. Practising: ' + nPractising + '. Questions answered this way on this tablet: ' + answers.length + '.'
          : 'No questions answered this way on this tablet yet.', 'gu-lead');
        el.appendChild(grid);
        const legend = MW.make('div', 'gu-legend');
        legend.appendChild(cell('secure', 'Secure'));
        legend.appendChild(cell('practising', 'Practising'));
        legend.appendChild(cell('notyet', 'Not yet'));
        el.appendChild(legend);
        G.p(el, '<b>Secure</b> means right first time (no wrong check and no hint) on three different days. A wrong answer moves a bond back to practising, and its three days start again. Each round has 1 or 2 secure bonds and 3 or 4 that need work.', 'gu-note');
        G.p(el, '<b>Zero bonds</b> (such as 0 + 7) join the rounds once the other bonds of that number are secure. With MeeMee to count they come up only when your child taps Scruffles to check (Settings), because the answer is an empty circle. With numbers they come up whichever check is set, because there is a 0 tile.', 'gu-note');

        G.h3(el, 'Wholes in play');
        const r2 = G.row(el);
        const paintW = function () {
          const on = MW.store.setting('wholes') || [];
          Array.prototype.forEach.call(r2.children, function (b) { b.classList.toggle('is-on', on.indexOf(+b.textContent) >= 0); });
        };
        for (let w = 2; w <= 10; w++) {
          G.btn(r2, String(w), function () {
            let on = (MW.store.setting('wholes') || []).slice();
            if (on.indexOf(w) >= 0) { if (on.length > 1) on = on.filter(function (x) { return x !== w; }); }
            else on.push(w);
            on.sort(function (a, b) { return a - b; });
            MW.store.setting('wholes', on);
            paintW();
          }, 'mw-chip gu-chip');
        }
        paintW();
        G.p(el, 'Questions use only the wholes switched on. Changes start with the next round.', 'gu-note');

        // the answers given the way that's showing, like the grid and the summary
        if (answers.length) {
          G.h3(el, 'Recent answers');
          const rows = answers.slice(-25).reverse().map(function (a) {
            const d = new Date(a.t);
            const when = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
            const parts = [], nums = MW.bonds.modeOf(a) === 'numbers';
            const wrong = nums ? ' wrong number' : ' wrong check';
            if (a.tries) parts.push(a.tries + wrong + (a.tries === 1 ? '' : 's'));
            if (a.misses) parts.push(a.misses + (a.misses === 1 ? ' missed drop' : ' missed drops'));
            if (a.hint) parts.push('with the hint');
            const how = (parts.length ? parts.join(', ') : 'First time') + (a.check === 'tap' ? ' (tap Scruffles)' : '');
            return [when, sentence(a) + '   (answer ' + (a.missing === 'whole' ? a.whole : a[a.missing]) + ')', how.charAt(0).toUpperCase() + how.slice(1)];
          });
          const t = MW.make('table', 'gu-table gu-table--3 label');
          t.innerHTML = '<tr><th>When</th><th>Question</th><th>How it went</th></tr>' + rows.map(function (r) {
            return '<tr><td>' + MW.esc(r[0]) + '</td><td>' + MW.esc(r[1]) + '</td><td>' + MW.esc(r[2]) + '</td></tr>';
          }).join('');
          el.appendChild(t);
        }
        const row = G.row(el);
        let armed = 0;
        MW.grownups.btn(row, 'Clear this tablet\'s progress', function (b) {
          if (Date.now() - armed < 4000) {
            MW.store.clear(); MW.grownups.show('progress');
          } else {
            armed = Date.now(); b.textContent = 'Tap again to clear';
            setTimeout(function () { b.textContent = 'Clear this tablet\'s progress'; }, 4000);
          }
        }, 'gu-quiet');
      }
    };
  }

  function settingsSection() {
    return {
      id: 'settings', title: 'Settings',
      render: function (el) {
        const G = MW.grownups;
        // how the child answers (Grownups8Settings): MeeMee to count, or numbers
        G.h3(el, 'How your child answers');
        const r0 = G.row(el);
        const paintWay = function () {
          Array.prototype.forEach.call(r0.children, function (b, i) { b.classList.toggle('is-on', WAYS[i][0] === savedMode()); });
        };
        WAYS.forEach(function (m) {
          const b = G.btn(r0, m[1], function () { MW.store.setting('answerMode', m[0]); view = null; paintWay(); MW.log('setting', 'answer ' + m[0]); }, 'gu-choice');
          b.setAttribute('data-way', m[0]);
        });
        paintWay();
        G.p(el, '<b>MeeMee to count</b> (the usual way): your child drags MeeMee into the empty circle, counting as they go.');
        G.p(el, '<b>Numbers:</b> each circle shows a MeeMee holding its number, and your child drags a number tile (0 to 10) into the empty circle. Two wrong tries bring the MeeMee back, so they can count them (not when the answer is zero). Each way keeps its own progress (Progress tab).');

        G.h3(el, 'Answer check');
        const r1 = G.row(el);
        const modes = [['tap', 'When your child taps Scruffles'], ['auto', 'As soon as the count is right']];
        const paint = function () {
          Array.prototype.forEach.call(r1.children, function (b, i) { b.classList.toggle('is-on', modes[i][0] === savedCheck()); });
        };
        modes.forEach(function (m) {
          G.btn(r1, m[1], function () { MW.store.setting('check', m[0]); MW.store.setting('checkPicked', true); paint(); MW.log('setting', 'check ' + m[0]); }, 'gu-choice');
        });
        paint();
        G.p(el, '<b>When your child taps Scruffles</b> (the usual way): they put in as many MeeMee as they think, then tap Scruffles to check. The first two questions of each round end with "Tap Scruffles when you\'re ready." (so does any question whose answer is zero), and the ship\'s lights glow once there is a MeeMee in the circle. Too many gets "That\'s too many. Take one back."; two wrong checks bring the counting-on hint.', 'gu-note');
        G.p(el, '<b>As soon as the count is right:</b> the question completes when the waiting circle holds the right number of MeeMee. No deciding when to stop, so it is easier but teaches less.', 'gu-note');

        G.p(el, 'A change starts with the next round. With numbers, the answer check works the same way, and zero bonds come up either way. Which numbers are in play is on the Progress tab.', 'gu-note');
      }
    };
  }

  // ---------------------------------------------------------------- test hooks
  R.drop = drop; R.podTap = onPodTap; R.start = startRound; R.home = W.home; R.map = W.home; R.makeRound = makeRound;
  R.track = function () { return track; }; R.diagram = function () { return diagram; }; R.mode = mode;
  // Ask one question straight away, as a round of its own in the way set in Settings, with nothing said (the tests use
  // it to put every bond on the screen in numbers mode without playing whole rounds).
  R.ask = function (q) {
    const token = ++st.token;
    clearHint();
    if (dragger) dragger.cancel();
    st.check = savedCheck(); st.mode = savedMode();
    st.round = [Object.assign({}, q)]; st.qi = 0;
    clearBoard(true);
    showMode();
    MW.shell.show('screen-game');
    st.q = st.round[0]; st.target = q.missing; st.answer = q.missing === 'whole' ? q.whole : q[q.missing];
    st.tries = 0; st.misses = 0; st.hinted = false;
    diagram.set(st.q);
    pod.face('thinking'); pod.lightsOff();
    if (track.away()) track.show();
    st.prompt = promptFor(st.q);
    st.phase = 'open';
    return token;
  };
  R.crew = function () { return W.crewScreen; };
})();
