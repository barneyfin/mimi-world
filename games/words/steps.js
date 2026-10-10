/* MeeMee Rockets: the words file read into a form the game uses, each word's step, and which words go into a round.

   Each word's step (decided 10 October):
     notyet    never asked;
     tiles     built from sound tiles ('c ar t oo n'), until it is right first time on three different days;
     letters   then built from single letters with its spares, three more days;
     harder    then from single letters with the tray filled to 10 tiles, three more days;
     secure    right first time in harder letters too. Secure words come back for review, in harder letters.
   Right first time: found and built with no wrong tap, no wrong drop and no hint. A wrong try restarts that step's
   three days; a word never goes back a step.
   A round: five different words (or every word in play, if fewer), one or two secure ones for review and the rest
   not yet secure, as MeeMee Rescue picks its bonds. The words in play are the chosen week's words plus the tricky
   words of the weeks before it.
   Pure functions of the words file and the saved answers, so they are easy to test. */
(function () {
  'use strict';
  const MW = window.MW;
  const S = MW.wordSteps = {};

  S.STEPS = ['notyet', 'tiles', 'letters', 'harder', 'secure'];
  S.NAMES = { notyet: 'Not yet', tiles: 'Sound tiles', letters: 'Letters', harder: 'Harder letters', secure: 'Secure' };
  function rank(step) { return S.STEPS.indexOf(step); }

  function day(t) {
    const d = new Date(t);
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();      // the tablet's own calendar day
  }
  S.day = day;
  function shuffle(list, rand) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  S.shuffle = shuffle;

  // ---------------------------------------------------------------- the words file
  // 'h [ere]' -> [{ text: 'h', tricky: false }, { text: 'ere', tricky: true }]
  S.tiles = function (spec) {
    return String(spec).trim().split(/\s+/).map(function (t) {
      const m = /^\[([a-z]+)\]$/.exec(t);
      return m ? { text: m[1], tricky: true } : { text: t, tricky: false };
    });
  };
  // Every word with its week, whether it is one of that week's tricky words, its tiles, letters and spares.
  // Problems in the file (a word with no tiles, tiles that don't spell it) are listed, not thrown, so the tests and
  // the grown-ups area can say what is wrong.
  S.read = function (data) {
    const out = { words: {}, order: [], weeks: [], problems: [], harderTray: +data.harderTray || 10, startWeek: +data.startWeek || 1 };
    (data.weeks || []).forEach(function (wk) {
      const n = +wk.week;
      out.weeks.push({ week: n, tricky: (wk.tricky || []).slice(), other: (wk.other || []).slice() });
      [['tricky', true], ['other', false]].forEach(function (kind) {
        (wk[kind[0]] || []).forEach(function (w) {
          const spec = (data.words || {})[w];
          if (!spec || !spec.tiles) { out.problems.push(w + ': no tiles in the words file'); return; }
          if (out.words[w]) { out.problems.push(w + ': in two weeks'); return; }
          const tiles = S.tiles(spec.tiles);
          if (tiles.map(function (t) { return t.text; }).join('') !== w) out.problems.push(w + ': its tiles spell ' + tiles.map(function (t) { return t.text; }).join(''));
          if (!/^[a-z]+$/.test(w)) out.problems.push(w + ': only lower-case letters, please');
          const letters = [];
          tiles.forEach(function (t) { t.text.split('').forEach(function (ch) { letters.push({ text: ch, tricky: t.tricky }); }); });
          const spares = String(spec.spares || '').trim().split(/\s+/).filter(Boolean);
          spares.forEach(function (s) { if (!/^[a-z]$/.test(s)) out.problems.push(w + ': the spare ' + s + ' should be one letter'); });
          out.words[w] = { word: w, week: n, tricky: kind[1], tiles: tiles, letters: letters, spares: spares, says: spec.says || '' };
          out.order.push(w);
        });
      });
    });
    out.weeks.sort(function (a, b) { return a.week - b.week; });
    if (!out.weeks.some(function (wk) { return wk.week === out.startWeek; }) && out.weeks.length) out.startWeek = out.weeks[out.weeks.length - 1].week;
    return out;
  };

  // The words in play for a week: that week's words (tricky, then other) and the tricky words of the weeks before it.
  S.inPlay = function (book, week) {
    const out = [];
    book.weeks.forEach(function (wk) {
      if (wk.week === week) out.push.apply(out, wk.tricky.concat(wk.other));
    });
    book.weeks.forEach(function (wk) {
      if (wk.week < week) out.push.apply(out, wk.tricky);
    });
    return out.filter(function (w) { return book.words[w]; });
  };

  // ---------------------------------------------------------------- steps
  S.firstTime = function (a) { return !a.tapped && !a.drops && !a.hint; };
  // answers: [{ t, w, step, tapped, drops, hint }] -> { word: { step, days: [...], answers: n } }
  S.statuses = function (answers) {
    const by = {};
    (answers || []).filter(function (a) {
      return a && typeof a.t === 'number' && typeof a.w === 'string';
    }).sort(function (x, y) { return x.t - y.t; }).forEach(function (a) {
      const s = by[a.w] || (by[a.w] = { step: 'tiles', days: [], answers: 0 });
      s.answers++;
      // an answer saved at a later step than the replay has reached (older answers were trimmed): carry on from there
      if (rank(a.step) > rank(s.step)) { s.step = a.step; s.days = []; }
      if (s.step === 'secure') return;                      // a word never goes back a step
      if (S.firstTime(a)) { const d = day(a.t); if (s.days.indexOf(d) < 0) s.days.push(d); }
      else s.days = [];
      if (s.days.length >= 3) { s.step = S.STEPS[rank(s.step) + 1]; s.days = []; }
    });
    return by;
  };
  S.step = function (map, w) { return map[w] ? map[w].step : 'notyet'; };
  // How a word is built at each step: sound tiles until it is secure with them, then letters, then harder letters.
  S.mode = function (step) { return step === 'letters' ? 'letters' : (step === 'harder' || step === 'secure') ? 'harder' : 'tiles'; };

  // ---------------------------------------------------------------- a round
  // opts: { words: the words in play, answers, size: 5, rand } -> [{ word, step }]
  S.pickRound = function (opts) {
    const rand = opts.rand || Math.random;
    const size = Math.min(opts.size || 5, opts.words.length);
    const map = S.statuses(opts.answers);
    const secure = shuffle(opts.words.filter(function (w) { return S.step(map, w) === 'secure'; }), rand);
    const work = shuffle(opts.words.filter(function (w) { return S.step(map, w) !== 'secure'; }), rand);
    let nSecure = Math.min(rand() < 0.5 ? 1 : 2, secure.length);
    const nWork = Math.min(size - nSecure, work.length);
    nSecure = Math.min(size - nWork, secure.length);         // too few to practise: more secure ones
    const chosen = shuffle(secure.slice(0, nSecure).concat(work.slice(0, nWork)), rand);
    return chosen.map(function (w) { const s = S.step(map, w); return { word: w, step: s === 'notyet' ? 'tiles' : s }; });
  };

  // Find: the word asked for and two others from the words in play, in a random order.
  S.choices = function (word, words, rand, n) {
    rand = rand || Math.random;
    const others = shuffle(words.filter(function (w) { return w !== word; }), rand).slice(0, (n || 3) - 1);
    return shuffle([word].concat(others), rand);
  };

  // Build: the places in the rocket and the tiles in the tray, for a word at a step.
  //   tiles    one tile per sound ('ay'), no spares;
  //   letters  one tile per letter, with the word's spares;
  //   harder   as letters, then the tray filled up to book.harderTray with letters from the week's other words
  //            (fill: the words to take them from, in order of preference), each a letter not already in the tray.
  // -> { mode, places: [{ text, tricky }], tray: [{ text, tricky, spare }] } (the tray shuffled)
  S.plan = function (book, word, step, fill, rand) {
    rand = rand || Math.random;
    const e = book.words[word];
    const mode = S.mode(step);
    const places = (mode === 'tiles' ? e.tiles : e.letters).map(function (t) { return { text: t.text, tricky: t.tricky }; });
    const tray = places.map(function (p) { return { text: p.text, tricky: p.tricky, spare: false }; });
    if (mode !== 'tiles') e.spares.forEach(function (s) { tray.push({ text: s, tricky: false, spare: true }); });
    if (mode === 'harder') {
      const have = {};
      tray.forEach(function (t) { have[t.text] = true; });
      (fill || []).forEach(function (group) {
        const letters = [];
        group.filter(function (w) { return w !== word && book.words[w]; }).forEach(function (w) {
          w.split('').forEach(function (ch) { if (!have[ch] && letters.indexOf(ch) < 0) letters.push(ch); });
        });
        shuffle(letters, rand).forEach(function (ch) {
          if (tray.length >= book.harderTray || have[ch]) return;
          have[ch] = true;
          tray.push({ text: ch, tricky: false, spare: true });
        });
      });
    }
    return { mode: mode, places: places, tray: shuffle(tray, rand) };
  };
  // Where harder letters' extra letters come from, in order: the other words of the week in play, then the other
  // words in play, then any word in the file (only needed when a week has very few letters).
  S.fillFrom = function (book, week) {
    const wk = book.weeks.filter(function (x) { return x.week === week; })[0];
    return [wk ? wk.tricky.concat(wk.other) : [], S.inPlay(book, week), book.order];
  };

  // Every question the game can ask for a week: each word in play, to find and to build at each step.
  S.allQuestions = function (book, week) {
    const out = [];
    S.inPlay(book, week).forEach(function (w) {
      out.push({ word: w, kind: 'find' });
      ['tiles', 'letters', 'harder'].forEach(function (m) { out.push({ word: w, kind: 'build', mode: m }); });
    });
    return out;
  };
})();
