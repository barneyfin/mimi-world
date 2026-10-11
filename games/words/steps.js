/* MeeMee Rockets: the words file read into a form the game uses, each word's step, and which words go into a round.

   Each word's step (decided 10 October):
     notyet    never asked;
     tiles     built from sound tiles ('c ar t oo n'), until it is right first time on three different days;
     letters   then built from single letters with its spares, three more days;
     harder    then from single letters with the tray filled to 10 tiles, three more days;
     secure    right first time in harder letters too. Secure words come back for review, in harder letters.
   Right first time: found and built with no wrong tap, no wrong drop and no hint. A wrong try restarts that step's
   three days. A word goes back only from secure (answer 12 of the 0.6.0 PRD): two slips in a row (answers not right
   first time) take it back to harder letters, for three more days right first time; a right answer in between clears
   the first slip.
   What's in play: one week (that week's words and the tricky words of the weeks before it), or every week ('all', the
   Words tab's "Weeks 1–5").
   A round: five different words (or every word in play, if fewer), one or two secure ones for review and the rest not
   yet secure.
     One week: the rest at random, and at least 3 of the 5 from the chosen week's own words while it has that many in
               play (answer 10).
     All weeks: the rest from the lowest step first (not yet, sound tiles, letters, harder letters), at random within a
               step (answer 8).
   Pure functions of the words file and the saved answers, so they are easy to test. */
(function () {
  'use strict';
  const MW = window.MW;
  const S = MW.wordSteps = {};

  S.STEPS = ['notyet', 'tiles', 'letters', 'harder', 'secure'];
  S.NAMES = { notyet: 'Not yet', tiles: 'Sound tiles', letters: 'Letters', harder: 'Harder letters', secure: 'Secure' };
  S.ALL = 'all';                 // every week in play (saved as the week)
  S.SILENT = '-';                // a tile that says nothing (the e of a split pair)
  S.SLIPS = 2;                   // slips in a row that take a secure word back to harder letters
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
  // Every word with its week, whether it is one of that week's tricky words, its tiles (each with what it says), letters
  // and spares. Problems in the file (a word with no tiles, tiles that don't spell it, a tile with no sound) are listed,
  // not thrown, so the tests and the grown-ups area can say what is wrong.
  S.read = function (data) {
    const out = { words: {}, order: [], weeks: [], problems: [], harderTray: +data.harderTray || 10, startWeek: +data.startWeek || 1,
      sounds: {} };
    const usual = data.sounds && typeof data.sounds === 'object' ? data.sounds : {};
    const goodId = function (id) { return id === S.SILENT || /^[a-z]+(-[a-z]+)*$/.test(String(id)); };
    Object.keys(usual).forEach(function (g) {
      if (goodId(usual[g])) out.sounds[g] = usual[g];
      else out.problems.push('sounds: ' + g + ' should be a sound id, such as "ai"');
    });
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
          // what each tile says: the word's own sound for it, or the tile's usual sound
          const own = spec.sounds && typeof spec.sounds === 'object' ? spec.sounds : {};
          Object.keys(own).forEach(function (k) {
            if (!tiles.some(function (t) { return t.text === k; })) out.problems.push(w + ': its sounds name ' + k + ', which isn\'t one of its tiles');
            else if (!goodId(own[k])) out.problems.push(w + ': the sound for ' + k + ' should be a sound id, such as "ai", or "-"');
          });
          tiles.forEach(function (t) {
            const mine = Object.prototype.hasOwnProperty.call(own, t.text) && goodId(own[t.text]);
            t.sound = mine ? own[t.text] : (out.sounds[t.text] || null);
            if (t.tricky && !mine) out.problems.push(w + ': say what its tricky tile ' + t.text + ' says in its sounds');
            else if (!t.sound) out.problems.push(w + ': no sound for its tile ' + t.text);
          });
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
  // A tile's recorded sound: the line id, or null for a tile that says nothing.
  S.soundLine = function (sound) { return sound && sound !== S.SILENT ? 'words-s-' + sound : null; };
  // Every sound the words use, as line ids (for the grown-ups' list of sounds waiting for a recording).
  S.soundLines = function (book) {
    const out = [];
    book.order.forEach(function (w) {
      book.words[w].tiles.forEach(function (t) { const id = S.soundLine(t.sound); if (id && out.indexOf(id) < 0) out.push(id); });
    });
    return out;
  };
  // The all-weeks choice's name, from the words file: "Weeks 1–5" (an en dash), or null with fewer than two weeks.
  S.allLabel = function (book) {
    if (book.weeks.length < 2) return null;
    return 'Weeks ' + book.weeks[0].week + '–' + book.weeks[book.weeks.length - 1].week;
  };

  // The words in play for a week: that week's words (tricky, then other) and the tricky words of the weeks before it.
  // For 'all', every word, week by week (each week's tricky words, then its other words).
  S.inPlay = function (book, week) {
    const out = [];
    if (week === S.ALL) {
      book.weeks.forEach(function (wk) { out.push.apply(out, wk.tricky.concat(wk.other)); });
    } else {
      book.weeks.forEach(function (wk) {
        if (wk.week === week) out.push.apply(out, wk.tricky.concat(wk.other));
      });
      book.weeks.forEach(function (wk) {
        if (wk.week < week) out.push.apply(out, wk.tricky);
      });
    }
    return out.filter(function (w) { return book.words[w]; });
  };
  // A week's own words (its tricky words and its other words).
  S.ownWords = function (book, week) {
    const wk = book.weeks.filter(function (x) { return x.week === week; })[0];
    return wk ? wk.tricky.concat(wk.other).filter(function (w) { return book.words[w]; }) : [];
  };

  // ---------------------------------------------------------------- steps
  S.firstTime = function (a) { return !a.tapped && !a.drops && !a.hint; };
  // answers: [{ t, w, step, tapped, drops, hint }] -> { word: { step, days: [...], answers: n, slips: n } }
  S.statuses = function (answers) {
    const by = {};
    (answers || []).filter(function (a) {
      return a && typeof a.t === 'number' && typeof a.w === 'string';
    }).sort(function (x, y) { return x.t - y.t; }).forEach(function (a) {
      const s = by[a.w] || (by[a.w] = { step: 'tiles', days: [], answers: 0, slips: 0 });
      s.answers++;
      // Each answer was saved at the step its word was on, so the replay follows it where they differ (only when the
      // oldest answers have been trimmed away, at 3,000):
      //   saved at a later step than the replay has reached: carry on from there;
      //   saved at an earlier one: the word went back from secure (two slips, the first one trimmed away), so it is on
      //   that step again (its days start from this answer).
      const r = rank(a.step);
      if (r > rank(s.step) || (r >= rank('tiles') && r < rank(s.step))) { s.step = a.step; s.days = []; s.slips = 0; }
      if (s.step === 'secure') {
        // a secure word: two slips in a row take it back to harder letters; a right answer in between clears one
        if (S.firstTime(a)) s.slips = 0;
        else if (++s.slips >= S.SLIPS) { s.step = 'harder'; s.days = []; s.slips = 0; }
        return;
      }
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
  // opts: { words: the words in play, answers, size: 5, rand,
  //         lowest: true with every week in play (the words on the lowest step first),
  //         own: the chosen week's own words in play (one week in play: at least 3 of them a round) } -> [{ word, step }]
  S.pickRound = function (opts) {
    const rand = opts.rand || Math.random;
    const size = Math.min(opts.size || 5, opts.words.length);
    const map = S.statuses(opts.answers);
    const isSecure = function (w) { return S.step(map, w) === 'secure'; };
    const secure = shuffle(opts.words.filter(isSecure), rand);
    let work = shuffle(opts.words.filter(function (w) { return !isSecure(w); }), rand);
    if (opts.lowest) {                                        // the lowest step first, at random within a step
      const keyed = work.map(function (w, i) { return { w: w, r: rank(S.step(map, w)), i: i }; });
      keyed.sort(function (a, b) { return a.r - b.r || a.i - b.i; });
      work = keyed.map(function (k) { return k.w; });
    }
    let nSecure = Math.min(rand() < 0.5 ? 1 : 2, secure.length);
    const nWork = Math.min(size - nSecure, work.length);
    nSecure = Math.min(size - nWork, secure.length);         // too few to practise: more secure ones
    const chosen = secure.slice(0, nSecure).concat(work.slice(0, nWork));
    if (opts.own && opts.own.length) {
      // one week in play: at least 3 of the round from the week's own words (all of them, if it has fewer in play).
      // Bring in its words that need work first, then its secure ones, each in place of another week's word of the
      // same kind where there is one.
      const own = opts.own.filter(function (w) { return opts.words.indexOf(w) >= 0; });
      const mine = function (w) { return own.indexOf(w) >= 0; };
      const need = Math.min(3, chosen.length, own.length);
      const out = function (list) { return list.filter(function (w) { return chosen.indexOf(w) < 0; }); };
      const bring = shuffle(out(own).filter(function (w) { return !isSecure(w); }), rand)
        .concat(shuffle(out(own).filter(isSecure), rand));
      while (chosen.filter(mine).length < need && bring.length) {
        const w = bring.shift();
        const others = chosen.filter(function (x) { return !mine(x); });
        const same = others.filter(function (x) { return isSecure(x) === isSecure(w); });
        const drop = (same.length ? same : others).slice(-1)[0];
        chosen[chosen.indexOf(drop)] = w;
      }
    }
    return shuffle(chosen, rand).map(function (w) { const s = S.step(map, w); return { word: w, step: s === 'notyet' ? 'tiles' : s }; });
  };

  // Find: the word asked for and two others from the words in play, in a random order.
  S.choices = function (word, words, rand, n) {
    rand = rand || Math.random;
    const others = shuffle(words.filter(function (w) { return w !== word; }), rand).slice(0, (n || 3) - 1);
    return shuffle([word].concat(others), rand);
  };

  // Build: the places in the rocket and the tiles in the tray, for a word at a step.
  //   tiles    one tile per sound ('ay'), no spares; each says its sound in this word when picked up (sound);
  //   letters  one tile per letter, with the word's spares;
  //   harder   as letters, then the tray filled up to book.harderTray with letters from other words
  //            (fill: the words to take them from, in order of preference), each a letter not already in the tray.
  // -> { mode, places: [{ text, tricky, sound }], tray: [{ text, tricky, spare, sound }] } (the tray shuffled)
  S.plan = function (book, word, step, fill, rand) {
    rand = rand || Math.random;
    const e = book.words[word];
    const mode = S.mode(step);
    const places = (mode === 'tiles' ? e.tiles : e.letters).map(function (t) {
      return { text: t.text, tricky: t.tricky, sound: mode === 'tiles' ? t.sound : null };
    });
    const tray = places.map(function (p) { return { text: p.text, tricky: p.tricky, spare: false, sound: p.sound }; });
    if (mode !== 'tiles') e.spares.forEach(function (s) { tray.push({ text: s, tricky: false, spare: true, sound: null }); });
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
          tray.push({ text: ch, tricky: false, spare: true, sound: null });
        });
      });
    }
    return { mode: mode, places: places, tray: shuffle(tray, rand) };
  };
  // Where harder letters' extra letters come from, in order of preference:
  //   one week in play   that week's words, then the other words in play, then any word in the file;
  //   every week (all)   the word's own week's words, then any word in play, then any word in the file (answer 9).
  // pool: the words in play this round (the recorded ones); without it, every word in play.
  S.fillFrom = function (book, week, word, pool) {
    const inPlay = pool || S.inPlay(book, week);
    if (week === S.ALL) {
      const e = book.words[word];
      return [e ? S.ownWords(book, e.week) : [], inPlay, book.order];
    }
    return [S.ownWords(book, week), inPlay, book.order];
  };

  // Every question the game can ask for a week (or 'all'): each word in play, to find and to build at each step.
  S.allQuestions = function (book, week) {
    const out = [];
    S.inPlay(book, week).forEach(function (w) {
      out.push({ word: w, kind: 'find' });
      ['tiles', 'letters', 'harder'].forEach(function (m) { out.push({ word: w, kind: 'build', mode: m }); });
    });
    return out;
  };
})();
