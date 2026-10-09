/* MeeMee Rescue (trial round, phase 3).
   Five part–whole questions in Barney's voice. The player drags MeeMee from the asteroid into the waiting circle.
   Built only from the kit (kit/*.js); phase 4 adds the solar-system map, the crew screen and the progress grid. */
(function () {
  'use strict';
  const MW = window.MW;
  const ROUND = 5;
  const PRAISE = ['praise-found-it', 'praise-thats-right', 'praise-super-counting', 'praise-brilliant-rescuing', 'praise-well-done'];
  const N = function (n) { return 'num-mid-' + n; };
  const E = function (n) { return 'num-end-' + n; };
  const OTHER = { left: 'right', right: 'left' };

  const st = { token: 0, paused: false, pauses: {}, hintTimers: [], phase: 'idle', round: null, qi: 0, q: null, target: null, answer: 0,
    counters: [], fixed: [], tries: 0, misses: 0, hinted: false, ghosts: null, prompt: null, praise: [] };
  const R = MW.rescue = { st: st, nextRound: null };
  let diagram, stars, equation, pod, layer, ghostLayer, fxLayer, endStars, endMimi, dragger;

  // ---------------------------------------------------------------- set-up
  function init() {
    const stageEl = MW.$('stage');
    MW.stage.init(stageEl);
    buildStart();
    buildGame();
    buildEnd();
    MW.shell.gate(stageEl, openGrownups);
    MW.grownups.init(stageEl, { title: 'Grown-ups', sections: [progressSection(), settingsSection()], onClose: function () { resume('grown-ups'); } });
    MW.shell.watchSideways(function () { pause('sideways'); }, function () { resume('sideways'); });
    // The screen going off, or switching to another app, pauses the game; it carries on when it comes back.
    document.addEventListener('visibilitychange', function () { if (document.hidden) pause('hidden'); else resume('hidden'); });
    MW.shell.registerOffline();
    MW.audio.preloadAll();
    MW.shell.show('screen-start');
    window.addEventListener('load', function () {
      const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
      MW.device.loadMs = nav ? Math.round(nav.loadEventStart || performance.now()) : Math.round(performance.now());
    });
  }

  function buildStart() {
    const s = MW.$('screen-start');
    s.appendChild(MW.make('div', 'mw-abs label mw-caption', { style: 'left:40px;top:34px' }, 'MeeMee Rescue'));
    const p = MW.pod(s, 240, 150, 420);
    p.el.disabled = true; p.el.tabIndex = -1;
    const play = MW.make('button', 'mw-btn mw-btn--play mw-abs mw-pulse', { type: 'button', 'aria-label': 'Play', id: 'play', style: 'left:820px;top:300px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    play.appendChild(icon);
    MW.onTap(play, function () { MW.audio.unlock(); MW.shell.fullscreen(); startRound(); });
    // If a browser didn't count the finger lifting as a tap for full screen, the click that follows tries again.
    play.addEventListener('click', function () { MW.audio.unlock(); if (MW.device.fullOk === false) MW.shell.fullscreen(); });
    s.appendChild(play);
    const row = MW.make('div', 'mw-abs mw-start-mimi', { style: 'left:770px;top:520px' });
    for (let i = 0; i < 3; i++) row.appendChild(MW.art('mimi'));
    s.appendChild(row);
    MW.shell.buttons(s, ['music'], {});
  }

  function buildGame() {
    const s = MW.$('screen-game');
    diagram = MW.diagram(s);
    MW.tray(s);
    pod = MW.pod(s, MW.LAYOUT.pod.x, MW.LAYOUT.pod.y, MW.LAYOUT.pod.w);
    MW.onTap(pod.el, onPodTap);
    equation = MW.equation(s);
    stars = MW.stars(s, MW.LAYOUT.stars.x, MW.LAYOUT.stars.y);
    ghostLayer = MW.make('div', 'mw-layer mw-fill'); s.appendChild(ghostLayer);
    layer = MW.make('div', 'mw-layer mw-fill mw-counters'); s.appendChild(layer);
    fxLayer = MW.make('div', 'mw-layer mw-fill mw-fx'); s.appendChild(fxLayer);
    MW.shell.buttons(s, ['home', 'music', 'hear'], { home: goHome, hear: hearAgain });
    dragger = MW.dragger(s, {
      counters: function () { return st.counters; },
      enabled: function () { return !st.paused && (st.phase === 'asking' || st.phase === 'open'); },
      onPick: function (c) { MW.log('pick', c.where); },
      onDrop: onDrop
    });
  }

  function buildEnd() {
    const s = MW.$('screen-end');
    endStars = MW.stars(s, 450, 40, 60);
    const mog = MW.make('div', 'mw-abs mw-crew', { style: 'left:70px;top:330px' }); mog.appendChild(MW.art('moggles')); s.appendChild(mog);
    const p = MW.pod(s, 380, 130, 400); p.face('got-it'); p.el.disabled = true; p.el.tabIndex = -1;
    const snu = MW.make('div', 'mw-abs mw-crew', { style: 'left:790px;top:330px' }); snu.appendChild(MW.art('snuffles')); s.appendChild(snu);
    endMimi = MW.make('div', 'mw-abs mw-start-mimi', { style: 'left:352px;top:600px' });
    for (let i = 0; i < 5; i++) endMimi.appendChild(MW.art('mimi'));
    s.appendChild(endMimi);
    const play = MW.make('button', 'mw-btn mw-btn--play mw-abs', { type: 'button', 'aria-label': 'Another rescue', id: 'again', style: 'left:1080px;top:420px' });
    const icon = MW.art('icon-play'); icon.setAttribute('width', 84); icon.setAttribute('height', 84);
    play.appendChild(icon);
    MW.onTap(play, function () { MW.audio.unlock(); MW.shell.fullscreen(); startRound(); });
    s.appendChild(play);
    MW.shell.buttons(s, ['home', 'music'], { home: goHome });
  }

  // ---------------------------------------------------------------- pausing
  // Reasons: the grown-ups area is open, the tablet is upright, or the page is hidden (screen off, another app).
  // The game carries on only when none is left, and then asks the question again.
  function pause(why) {
    st.pauses[why] = true;
    st.paused = true;
    clearHint();
    MW.audio.hush();
    if (dragger) dragger.cancel();
    MW.log('pause', why);
  }
  function resume(why) {
    if (!st.pauses[why]) return;
    delete st.pauses[why];
    if (Object.keys(st.pauses).length) return;
    st.paused = false;
    MW.log('resume', why);
    if (MW.shell.screen === 'screen-game' && (st.phase === 'open' || st.phase === 'asking')) speak(st.prompt);
  }
  function openGrownups() { pause('grown-ups'); MW.grownups.openPanel(); }
  // Wait while paused; false if the player has left this round meanwhile.
  async function ok(token) {
    while (st.paused) await MW.wait(200);
    return token === st.token;
  }
  async function speak(lines, opts) {
    const token = st.token;
    if (!(await ok(token))) return false;
    return MW.audio.say(lines, opts);
  }

  // ---------------------------------------------------------------- a round
  function makeRound() {
    if (R.nextRound) { const r = R.nextRound; R.nextRound = null; return r.map(function (q) { return Object.assign({}, q); }); }
    let wholes = (MW.store.setting('wholes') || []).filter(function (w) { return w >= 2 && w <= 10; });
    if (!wholes.length) wholes = [2, 3, 4, 5, 6, 7, 8, 9, 10];
    const pool = [];
    wholes.forEach(function (w) { for (let a = 1; a < w; a++) pool.push([w, a]); });
    const qs = [];
    let guard = 0;
    while (qs.length < ROUND && guard++ < 1000) {
      const pick = MW.pick(pool), w = pick[0], a = pick[1];
      const same = qs.some(function (q) { return q.whole === w && (q.left === a || q.right === a); });
      if (same && pool.length >= ROUND * 2) continue;
      if (qs.length && qs[qs.length - 1].whole === w && wholes.length > 1 && guard < 500) continue;
      const r = Math.random();
      qs.push({ whole: w, left: a, right: w - a, missing: r < 0.25 ? 'whole' : (r < 0.625 ? 'left' : 'right') });
    }
    return qs;
  }

  async function startRound() {
    const token = ++st.token;
    st.round = makeRound();
    st.qi = 0;
    clearBoard(true);
    MW.shell.show('screen-game');
    stars.set(0);
    st.phase = 'starting';
    MW.log('round', JSON.stringify(st.round));
    await speak([['round-ready']]);
    if (!(await ok(token))) return;
    nextQuestion(token);
  }

  function clearBoard(all) {
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    st.counters.concat(st.fixed).forEach(function (c) { c.remove(); });
    st.counters = []; st.fixed = [];
    if (all) { equation.hide(); }
  }

  async function nextQuestion(token) {
    const q = st.q = st.round[st.qi];
    st.target = q.missing;
    st.answer = q.missing === 'whole' ? q.whole : q[q.missing];
    st.tries = 0; st.misses = 0; st.hinted = false;
    clearBoard(true);
    diagram.set(q);
    pod.face('thinking');
    stars.set(st.qi);
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
    st.prompt = promptFor(q);
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
  }
  function check() { return MW.store.setting('check') === 'tap' ? 'tap' : 'auto'; }

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

  // Tapping Scruffles: checks the answer in "tap" mode; otherwise asks the question again.
  function onPodTap() {
    if (st.paused || !(st.phase === 'open' || st.phase === 'asking')) return;
    if (dragger && dragger.dragging()) return;              // one hand holding a MeeMee, the other tapping
    if (check() !== 'tap') { hearAgain(); return; }
    const n = inTarget().length;
    MW.log('check', n + ' of ' + st.answer);
    if (n === st.answer) { success(); return; }
    wrongTry(n > st.answer ? 'too-many' : 'too-few');
  }

  // A wrong try: a wrong check (tap mode) or a MeeMee dropped away from the waiting circle (a miss).
  // No red, no buzzer: Scruffles's try-again face, a calm line, and the hint after the second one.
  function wrongTry(kind) {
    if (kind === 'miss') st.misses++; else st.tries++;
    const count = kind === 'miss' ? st.misses : st.tries;
    pod.face('try-again');
    const token = st.token, qi = st.qi;
    setTimeout(function () { if (token === st.token && qi === st.qi && st.phase !== 'celebrate') pod.face('thinking'); }, 1600);
    if (kind === 'too-many') { speak([['too-many']]); return; }
    if (count >= 2 && !st.hinted) { hint(); return; }
    if (count >= 2) return;
    speak([[kind === 'miss' ? 'again-try-again' : 'again-look-again']]);
  }

  // ---------------------------------------------------------------- the hint: count on together
  async function hint() {
    const q = st.q, token = st.token, qi = st.qi;
    st.hinted = true;
    MW.log('hint', q.missing);
    diagram.hinting(st.target, true);
    tidy(true);
    const placed = inTarget().length;
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
            const inside = inTarget();
            if (j < inside.length) hop(inside[j]); else if (st.ghosts) st.ghosts.light(j - placed);
          };
        })(i - 1));
      }
    }
    const heard = await speak(lines, {
      onStart: function (timeline) {
        // one entry per clip; the first line may have two clips
        let k = 0;
        lines.forEach(function (sent, si) {
          const at = timeline[k].at;
          k += sent.length;
          if (actions[si]) st.hintTimers.push(setTimeout(function () { if (token === st.token && qi === st.qi) actions[si](); }, at * 1000));
        });
      }
    });
    // Cut short (Hear-again, a pause): take the hint away so the next wrong try gives it again in full.
    if (!heard && token === st.token && qi === st.qi && st.phase !== 'celebrate') {
      clearHint();
      st.hinted = false;
      if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
      diagram.hinting(st.target, false);
      tidy(true);
    }
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
    MW.store.recordAnswer({ t: Date.now(), whole: q.whole, left: q.left, right: q.right, missing: q.missing,
      tries: st.tries, misses: st.misses, hint: st.hinted, check: check() });
    if (st.ghosts) { st.ghosts.clear(); st.ghosts = null; }
    diagram.success(st.target, st.answer);
    const c = MW.LAYOUT[st.target];
    MW.sparkles(fxLayer, c.x, c.y, c.r + 34);
    pod.face('got-it');
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
    await MW.wait(800);
    if (!(await ok(token))) return;
    // the rescued MeeMee fly up into the pod
    inTarget().concat(st.fixed).forEach(function (m) {
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
    MW.audio.sfx('tune');
    await MW.wait(300);
    await speak([['round-rescued-all']]);
    if (!(await ok(token))) return;
    // the rescued MeeMee hop once each, left to right
    Array.prototype.forEach.call(endMimi.children, function (m, i) {
      setTimeout(function () { m.classList.remove('is-hop'); void m.getBoundingClientRect(); m.classList.add('is-hop'); }, i * 160);
    });
    await MW.wait(500);
    if (!(await ok(token))) return;
    await speak([['round-another']]);
  }

  function hearAgain() {
    if (st.paused) return;
    if (st.phase === 'open' || st.phase === 'asking') { clearHint(); speak(st.prompt); }
  }
  function goHome() {
    clearHint();
    if (dragger) dragger.cancel();
    st.token++;
    st.phase = 'idle';
    MW.audio.hush();
    clearBoard(true);
    MW.shell.show('screen-start');
  }

  // ---------------------------------------------------------------- grown-ups: this trial
  function sentence(a) {
    if (a.missing === 'whole') return a.left + ' + ' + a.right + ' = ?';
    if (a.missing === 'left') return '? + ' + a.right + ' = ' + a.whole;
    return a.left + ' + ? = ' + a.whole;
  }
  function progressSection() {
    return {
      id: 'progress', title: 'Progress',
      render: function (el) {
        const answers = MW.store.get('answers') || [];
        const firstTime = answers.filter(function (a) { return !a.tries && !a.hint; }).length;
        MW.grownups.p(el, answers.length
          ? 'Questions answered on this tablet: ' + answers.length + '. Right first time: ' + firstTime + '.'
          : 'No questions answered on this tablet yet.', 'gu-lead');
        MW.grownups.p(el, 'This is the phase 3 trial. The full progress screen, showing which bonds are secure, comes with the finished game.', 'gu-note');
        if (answers.length) {
          const rows = answers.slice(-25).reverse().map(function (a) {
            const d = new Date(a.t);
            const when = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
            const parts = [];
            if (a.tries) parts.push(a.tries + (a.tries === 1 ? ' wrong check' : ' wrong checks'));
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
        const row = MW.grownups.row(el);
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
        G.h3(el, 'Answer check');
        const r1 = G.row(el);
        const modes = [['auto', 'As soon as the count is right'], ['tap', 'When your child taps Scruffles']];
        const paint = function () {
          Array.prototype.forEach.call(r1.children, function (b, i) { b.classList.toggle('is-on', modes[i][0] === check()); });
        };
        modes.forEach(function (m) { G.btn(r1, m[1], function () { MW.store.setting('check', m[0]); paint(); MW.log('setting', 'check ' + m[0]); }, 'gu-choice'); });
        paint();
        G.p(el, '<b>As soon as the count is right:</b> the question completes when the waiting circle holds the right number of MeeMee. No explaining needed, but your child never has to decide when to stop.', 'gu-note');
        G.p(el, '<b>When your child taps Scruffles:</b> they put in as many MeeMee as they think, then tap Scruffles to check. Too many gets "That\'s too many. Take one back."; two wrong checks bring the counting-on hint. Show them once: there is no spoken instruction for it yet.', 'gu-note');

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
        G.p(el, 'Questions use only the wholes switched on. Zero bonds (such as 7 + 0) aren\'t asked yet. Changes start with the next round.', 'gu-note');
      }
    };
  }

  // ---------------------------------------------------------------- test hooks
  R.drop = onDrop; R.podTap = onPodTap; R.start = startRound; R.home = goHome;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
