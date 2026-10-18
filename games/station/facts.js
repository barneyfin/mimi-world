/* MeeMee Station: the facts, how secure each one is, and which go into a round (0.9.0).

   A fact is a whole and the part already aboard: 7 with 3 aboard ("3 + 4") and 7 with 4 aboard ("4 + 3") are two facts,
   so wholes 2 to 10 have 45, w with a from 1 to w − 1 (no zero facts: open question 1). The rest, b = w − a, is the
   part to bring aboard (step 1), the part to find (step 2), or in step 3 whichever of the whole and the two parts the
   empty berth is in.
   Secure, practising, not yet: MeeMee Rescue's rule (games/rescue/bonds.js), kept for each step on its own, apart from
   MeeMee Rescue's:
     secure      right first time (no wrong check, no hint) on three different days;
     practising  answered, but not yet three days right first time; a wrong answer moves a secure fact back here and
                 its days start again;
     not yet     never asked.
   In step 3 a fact counts whichever place its berth was in.
   A round of five: MeeMee Rescue's rule. 1 or 2 secure facts, the rest practising or not met yet; at most two from one
   whole while there are others to take; the same whole not twice in a row while that can be helped; only the wholes in
   play. The wholes in play come up equally (no weighting): each list is dealt a whole at a time, the wholes in a
   shuffled order, so a whole with nine facts (10) is no likelier to come up than a whole with one (2). In step 3 the
   berth's place (the whole, the part aboard or the rest) is spread about equally across a round and across rounds, as
   Take MeeMee Home spreads its gap: a round takes the three places in turn, starting where the last round left off
   (turn), in a shuffled order.
   Pure functions of the saved answers, so they are easy to test.

   The steps: 'aboard' (Bring them aboard), 'more' (How many more), 'numbers' (Numbers).
   A question: { whole, a, b, missing, status }: a the part already aboard (the bar model's left part), b the rest (its
   right part), missing where the answer goes ('right' in steps 1 and 2; any of 'whole', 'left' and 'right' in step 3).
   A saved answer: { t, whole, a, missing, tries, misses, hint }, in the game's own record for its step. */
(function () {
  'use strict';
  const MW = window.MW;

  const STEPS = ['aboard', 'more', 'numbers'];
  const PLACES = ['whole', 'left', 'right'];

  function day(t) {
    const d = new Date(t);
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();      // the tablet's own calendar day
  }
  function shuffle(list, rand) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  // A list dealt a whole at a time: the wholes in a shuffled order, each whole's facts shuffled, one from each whole in
  // turn. Its first n come from n different wholes when there are that many, each whole as likely as any other.
  function byWhole(list, rand) {
    const groups = {};
    list.forEach(function (c) { (groups[c.whole] = groups[c.whole] || []).push(c); });
    const order = shuffle(Object.keys(groups), rand).map(function (w) { return shuffle(groups[w], rand); });
    const out = [];
    for (let i = 0; out.length < list.length; i++) order.forEach(function (g) { if (i < g.length) out.push(g[i]); });
    return out;
  }
  // the first n of a list, but at most two from one whole while there are others to take
  function take(list, n, already) {
    const count = {}, out = [], later = [];
    already.forEach(function (c) { count[c.whole] = (count[c.whole] || 0) + 1; });
    list.forEach(function (c) {
      if (out.length >= n) return;
      if ((count[c.whole] || 0) >= 2) { later.push(c); return; }
      out.push(c); count[c.whole] = (count[c.whole] || 0) + 1;
    });
    for (let i = 0; out.length < n && i < later.length; i++) out.push(later[i]);
    return out;
  }

  const F = MW.stationFacts = { STEPS: STEPS, PLACES: PLACES };

  F.key = function (w, a) { return w + ':' + a; };
  F.firstTime = function (ans) { return !ans.tries && !ans.hint; };
  // The step a saved name stands for ('aboard' if it isn't one).
  F.step = function (s) { return STEPS.indexOf(s) >= 0 ? s : 'aboard'; };

  // Every fact of a whole, by the part already aboard: 7 -> 1 to 6.
  F.facts = function (w) {
    const out = [];
    for (let a = 1; a <= w - 1; a++) out.push(a);
    return out;
  };

  // { '7:3': { status: 'secure' | 'practising', days: [...], answers: n } } from one step's answers on this tablet
  F.statuses = function (answers) {
    const by = {};
    (answers || []).filter(function (x) {
      return x && typeof x.t === 'number' && x.whole >= 2 && x.whole <= 10 && x.a >= 1 && x.a <= x.whole - 1;
    }).sort(function (x, y) { return x.t - y.t; }).forEach(function (x) {
      const k = F.key(x.whole, x.a);
      const s = by[k] || (by[k] = { status: 'practising', days: [], answers: 0 });
      s.answers++;
      if (F.firstTime(x)) { const d = day(x.t); if (s.days.indexOf(d) < 0) s.days.push(d); }
      else s.days = [];
      s.status = s.days.length >= 3 ? 'secure' : 'practising';
    });
    return by;
  };
  F.status = function (map, w, a) { const s = map[F.key(w, a)]; return s ? s.status : 'notyet'; };

  // The facts a round can draw from: every fact of the wholes in play.
  F.candidates = function (wholes, map) {
    const out = [];
    wholes.forEach(function (w) {
      F.facts(w).forEach(function (a) { out.push({ whole: w, a: a, status: F.status(map, w, a) }); });
    });
    return out;
  };

  // Step 3's berth places for a round of n: the three places in turn from turn (so across rounds each comes up as often
  // as the others), in a shuffled order.
  F.gaps = function (n, turn, rand) {
    const out = [];
    for (let i = 0; i < n; i++) out.push(PLACES[((turn || 0) + i) % 3]);
    return shuffle(out, rand || Math.random);
  };

  // Where steps 1 and 2 put the answer: the rest, the bar model's right part. Step 3 chooses per question.
  F.missing = function () { return 'right'; };

  // opts: { step, wholes: [2..10], answers: that step's [...], size: 5, turn: where step 3's berth places start, rand }
  // -> [{ whole, a, b, missing, status }]
  F.pickRound = function (opts) {
    const rand = opts.rand || Math.random;
    const size = opts.size || 5;
    const step = F.step(opts.step);
    const map = F.statuses(opts.answers);
    const cands = F.candidates(opts.wholes, map);
    const secure = byWhole(cands.filter(function (c) { return c.status === 'secure'; }), rand);
    const work = byWhole(cands.filter(function (c) { return c.status !== 'secure'; }), rand);
    let nSecure = Math.min(rand() < 0.5 ? 1 : 2, secure.length);
    const nWork = Math.min(size - nSecure, work.length);
    nSecure = Math.min(size - nWork, secure.length);                   // too few to practise: more secure ones
    const chosen = take(secure, nSecure, []);
    Array.prototype.push.apply(chosen, take(work, nWork, chosen));
    // very few wholes in play: every fact is already in, so go round them again in turn
    const again = byWhole(cands, rand);
    for (let i = 0; chosen.length < size; i++) chosen.push(again[i % again.length]);
    // the same whole twice in a row only when it can't be helped (a search over a shuffled order; a round is only five)
    const pool = shuffle(chosen, rand);
    let best = null, bestRuns = Infinity;
    (function place(order, left, runs) {
      if (runs >= bestRuns) return;
      if (!left.length) { best = order; bestRuns = runs; return; }
      for (let i = 0; i < left.length && bestRuns > 0; i++) {
        const same = order.length && order[order.length - 1].whole === left[i].whole ? 1 : 0;
        place(order.concat([left[i]]), left.slice(0, i).concat(left.slice(i + 1)), runs + same);
      }
    })([], pool, 0);
    const gaps = step === 'numbers' ? F.gaps(best.length, opts.turn, rand) : null;
    return best.map(function (c, i) {
      return { whole: c.whole, a: c.a, b: c.whole - c.a, missing: gaps ? gaps[i] : F.missing(step), status: c.status };
    });
  };

  // Every question a step can ask for these wholes (the tests' list for grown-ups): 45 in steps 1 and 2, and in step 3
  // the 45 with the berth in each of its three places (135).
  F.allQuestions = function (step, wholes) {
    step = F.step(step);
    const out = [];
    wholes.forEach(function (w) {
      F.facts(w).forEach(function (a) {
        (step === 'numbers' ? PLACES : [F.missing(step)]).forEach(function (m) {
          out.push({ whole: w, a: a, b: w - a, missing: m });
        });
      });
    });
    return out;
  };
})();
