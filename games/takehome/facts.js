/* Take MeeMee Home: the subtraction facts, how secure each one is, and which go into a round (0.8.0).

   A fact is a whole and the number taken away (going home): 7 − 4 and 7 − 3 are two facts (decided 15 October 2026), so
   wholes 2 to 10 have 45 facts, w − t with t from 1 to w − 1. The zero facts (7 − 0 and 7 − 7) come up in step 3
   (Numbers) only, once every other fact of that whole is secure in step 3 (question 6).
   Secure, practising, not yet: MeeMee Rescue's rule (games/rescue/bonds.js), kept for each step on its own:
     secure      right first time (no wrong check, no hint) on three different days;
     practising  answered, but not yet three days right first time; a wrong answer moves a secure fact back here and
                 its days start again;
     not yet     never asked.
   In step 3 a fact counts whichever place its gap was in (question 8).
   A round of five: MeeMee Rescue's rule. 1 or 2 secure facts, the rest practising or not met yet; at most two from one
   whole while there are others to take; the same whole not twice in a row while that can be helped. In step 3 the
   gap's place (the whole, the part going home or the part staying) is spread about equally across a round and across
   rounds: a round takes the three places in turn, starting where the last round left off (turn), in a shuffled order.
   Pure functions of the saved answers, so they are easy to test.

   The steps: 'take' (Take away), 'left' (How many are left), 'numbers' (Numbers).
   A question: { whole, take, left, missing, status }: take is the number going home (the diagram's right part), left
   the number staying (its left part), missing the circle that is empty ('right' in step 1, 'left' in step 2; any of
   'whole', 'right' and 'left' in step 3).
   A saved answer: { t, whole, take, missing, tries, misses, hint }, in the game's own record for its step. */
(function () {
  'use strict';
  const MW = window.MW;

  const STEPS = ['take', 'left', 'numbers'];
  const PLACES = ['whole', 'right', 'left'];              // the sentence's order: w − t = r (gap 0, 1, 2)

  function day(t) {
    const d = new Date(t);
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();      // the tablet's own calendar day
  }
  function shuffle(list, rand) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  // the first n of a shuffled list, but at most two from one whole while there are others to take
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

  const F = MW.takehomeFacts = { STEPS: STEPS, PLACES: PLACES };

  F.key = function (w, t) { return w + ':' + t; };
  F.firstTime = function (ans) { return !ans.tries && !ans.hint; };
  // The step a saved name stands for ('take' if it isn't one).
  F.step = function (s) { return STEPS.indexOf(s) >= 0 ? s : 'take'; };

  // Every fact of a whole, by the number taken away: 7 -> 1 to 6, and with zero 0 to 7.
  F.facts = function (w, zero) {
    const out = [];
    for (let t = zero ? 0 : 1; t <= (zero ? w : w - 1); t++) out.push(t);
    return out;
  };

  // { '7:4': { status: 'secure' | 'practising', days: [...], answers: n } } from one step's answers on this tablet
  F.statuses = function (answers) {
    const by = {};
    (answers || []).filter(function (a) {
      return a && typeof a.t === 'number' && a.whole >= 1 && a.whole <= 10 && a.take >= 0 && a.take <= a.whole;
    }).sort(function (x, y) { return x.t - y.t; }).forEach(function (a) {
      const k = F.key(a.whole, a.take);
      const s = by[k] || (by[k] = { status: 'practising', days: [], answers: 0 });
      s.answers++;
      if (F.firstTime(a)) { const d = day(a.t); if (s.days.indexOf(d) < 0) s.days.push(d); }
      else s.days = [];
      s.status = s.days.length >= 3 ? 'secure' : 'practising';
    });
    return by;
  };
  F.status = function (map, w, t) { const s = map[F.key(w, t)]; return s ? s.status : 'notyet'; };

  // A whole's zero facts are open once every other fact of that whole is secure (in that step's answers).
  F.zeroOpen = function (map, w) {
    return F.facts(w, false).every(function (t) { return F.status(map, w, t) === 'secure'; });
  };

  // The facts a round can draw from: every fact of the wholes in play, the zero facts only when allowed and open.
  F.candidates = function (wholes, map, zero) {
    const out = [];
    wholes.forEach(function (w) {
      F.facts(w, !!zero).forEach(function (t) {
        if ((t === 0 || t === w) && !F.zeroOpen(map, w)) return;
        out.push({ whole: w, take: t, status: F.status(map, w, t) });
      });
    });
    return out;
  };

  // Step 3's gap places for a round of n: the three places in turn from turn (so across rounds each comes up as often
  // as the others), in a shuffled order.
  F.gaps = function (n, turn, rand) {
    const out = [];
    for (let i = 0; i < n; i++) out.push(PLACES[((turn || 0) + i) % 3]);
    return shuffle(out, rand || Math.random);
  };

  // The circle a step leaves empty: step 1 the part going home, step 2 the part staying; step 3 is chosen per question.
  F.missing = function (step) { return step === 'left' ? 'left' : 'right'; };

  // opts: { step, wholes: [2..10], answers: that step's [...], size: 5, turn: where step 3's gap places start, rand }
  // -> [{ whole, take, left, missing, status }]
  F.pickRound = function (opts) {
    const rand = opts.rand || Math.random;
    const size = opts.size || 5;
    const step = F.step(opts.step);
    const map = F.statuses(opts.answers);
    const cands = F.candidates(opts.wholes, map, step === 'numbers');
    const secure = shuffle(cands.filter(function (c) { return c.status === 'secure'; }), rand);
    const work = shuffle(cands.filter(function (c) { return c.status !== 'secure'; }), rand);
    let nSecure = Math.min(rand() < 0.5 ? 1 : 2, secure.length);
    const nWork = Math.min(size - nSecure, work.length);
    nSecure = Math.min(size - nWork, secure.length);                   // too few to practise: more secure ones
    const chosen = take(secure, nSecure, []);
    Array.prototype.push.apply(chosen, take(work, nWork, chosen));
    // very few wholes in play: every fact is already in, so go round them again in turn
    const again = shuffle(cands, rand);
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
      return { whole: c.whole, take: c.take, left: c.whole - c.take, missing: gaps ? gaps[i] : F.missing(step), status: c.status };
    });
  };

  // Every question a step can ask for these wholes (the tests' list for grown-ups). Step 3 with zero: the zero facts too.
  F.allQuestions = function (step, wholes, zero) {
    step = F.step(step);
    const out = [];
    wholes.forEach(function (w) {
      F.facts(w, step === 'numbers' && !!zero).forEach(function (t) {
        (step === 'numbers' ? PLACES : [F.missing(step)]).forEach(function (m) {
          out.push({ whole: w, take: t, left: w - t, missing: m });
        });
      });
    });
    return out;
  };
})();
