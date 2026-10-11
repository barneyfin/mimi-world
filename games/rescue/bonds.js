/* MeeMee Rescue: the number bonds, how secure each one is, and which go into a round (phase 4).

   A bond is a whole and its two parts in either order: 3 + 4 and 4 + 3 are the same bond, "7: 3 and 4".
   Secure, practising, not yet (decided 9 October):
     secure      right first time (no wrong check, no hint) on three different days;
     practising  answered, but not yet three days right first time; a wrong answer moves a secure bond back here
                 and its days start again;
     not yet     never asked.
   A round of five: 1 or 2 bonds he is secure on, the rest he is practising or hasn't met. If there aren't enough of
   one kind, the other fills in. At most two bonds come from one whole, and the same whole isn't asked twice in a row,
   while there are enough wholes in play. A whole's zero bond (5 and 0) joins once its other bonds are secure. With MeeMee
   to count it comes only when the answer is checked by tapping Scruffles (an empty circle is the answer to "how many
   more?"); in numbers mode it comes whichever check is set, because there is a 0 tile (decided 10 October 2026).
   Each way of answering keeps its own progress (decided 10 October 2026): every answer is saved with its mode
   ('counting' or 'numbers'); an answer saved before numbers mode has none and counts as counting. The game passes
   pickRound and statuses one mode's answers (ofMode).
   Pure functions of the saved answers, so they are easy to test. */
(function () {
  'use strict';
  const MW = window.MW;

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

  const B = MW.bonds = {};

  B.key = function (w, a, b) { return w + ':' + Math.min(a, b); };
  // Which way an answer was given: 'numbers', or 'counting' (also for answers saved before 0.6.0, which have no mode).
  B.modeOf = function (ans) { return ans && ans.mode === 'numbers' ? 'numbers' : 'counting'; };
  // One way's answers: each way has its own secure, practising and not yet.
  B.ofMode = function (answers, mode) { return (answers || []).filter(function (a) { return B.modeOf(a) === mode; }); };
  B.firstTime = function (ans) { return !ans.tries && !ans.hint; };

  // Every bond of a whole, smaller part first: 7 -> [0,7] [1,6] [2,5] [3,4]
  B.pairs = function (w) {
    const out = [];
    for (let a = 0; a <= Math.floor(w / 2); a++) out.push([a, w - a]);
    return out;
  };

  // { '7:3': { status: 'secure' | 'practising', days: [...], answers: n } } from the answers saved on this tablet
  B.statuses = function (answers) {
    const by = {};
    (answers || []).filter(function (a) {
      return a && typeof a.t === 'number' && a.whole >= 1 && a.left >= 0 && a.right >= 0 && a.left + a.right === a.whole;
    }).sort(function (x, y) { return x.t - y.t; }).forEach(function (a) {
      const k = B.key(a.whole, a.left, a.right);
      const s = by[k] || (by[k] = { status: 'practising', days: [], answers: 0 });
      s.answers++;
      if (B.firstTime(a)) { const d = day(a.t); if (s.days.indexOf(d) < 0) s.days.push(d); }
      else s.days = [];
      s.status = s.days.length >= 3 ? 'secure' : 'practising';
    });
    return by;
  };
  B.status = function (map, w, a) { const s = map[B.key(w, a, w - a)]; return s ? s.status : 'notyet'; };

  // A whole's zero bond is open once every other bond of that whole is secure.
  B.zeroOpen = function (map, w) {
    return B.pairs(w).every(function (p) { return p[0] === 0 || B.status(map, w, p[0]) === 'secure'; });
  };

  // The bonds a round can draw from: every bond of the wholes in play, zero bonds only when allowed and open.
  B.candidates = function (wholes, map, zero) {
    const out = [];
    wholes.forEach(function (w) {
      B.pairs(w).forEach(function (p) {
        if (p[0] === 0 && !(zero && B.zeroOpen(map, w))) return;
        out.push({ whole: w, a: p[0], b: p[1], status: B.status(map, w, p[0]) });
      });
    });
    return out;
  };

  // opts: { wholes: [2..10], answers: one mode's [...], size: 5, zero: true in numbers mode or with tap Scruffles, rand: Math.random }
  // -> [{ whole, left, right, missing: 'whole' | 'left' | 'right', status }]
  B.pickRound = function (opts) {
    const rand = opts.rand || Math.random;
    const size = opts.size || 5;
    const map = B.statuses(opts.answers);
    const cands = B.candidates(opts.wholes, map, !!opts.zero);
    const secure = shuffle(cands.filter(function (c) { return c.status === 'secure'; }), rand);
    const work = shuffle(cands.filter(function (c) { return c.status !== 'secure'; }), rand);
    let nSecure = Math.min(rand() < 0.5 ? 1 : 2, secure.length);
    const nWork = Math.min(size - nSecure, work.length);
    nSecure = Math.min(size - nWork, secure.length);                   // too few to practise: more secure ones
    const chosen = take(secure, nSecure, []);
    Array.prototype.push.apply(chosen, take(work, nWork, chosen));
    // very few wholes in play: every bond is already in, so go round them again in turn
    const again = shuffle(cands, rand);
    for (let i = 0; chosen.length < size; i++) chosen.push(again[i % again.length]);
    // the same whole twice in a row only when it can't be helped: a search over a shuffled order finds an order
    // with no repeats whenever there is one (a round is only five long)
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
    return best.map(function (c) {
      const swap = rand() < 0.5;
      const r = rand();
      return { whole: c.whole, left: swap ? c.b : c.a, right: swap ? c.a : c.b,
        missing: r < 0.25 ? 'whole' : (r < 0.625 ? 'left' : 'right'), status: c.status };
    });
  };

  // Every question the game can ask for these wholes (tests and the grown-ups' list).
  B.allQuestions = function (wholes, zero) {
    const out = [];
    wholes.forEach(function (w) {
      for (let left = zero ? 0 : 1; left <= (zero ? w : w - 1); left++) {
        ['whole', 'left', 'right'].forEach(function (m) { out.push({ whole: w, left: left, right: w - left, missing: m }); });
      }
    });
    return out;
  };
})();
