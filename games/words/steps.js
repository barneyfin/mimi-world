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
   the first slip. A word has one step wherever it is played (0.7.0, D1): progress is kept by word.
   What's in play (0.7.0): a grown-up's choice, one of
     a week        { half, week }: that week's words and the tricky words of the same half-term's earlier weeks;
     its weeks     { half, week: 'all' }: every word of one half-term (the Words tab's "Weeks 1–5");
     a whole term  { term }: every word of all its half-terms, each once ("All of autumn").
   A word is marked tricky only where the half-term in play lists it as tricky; with a whole term in play, the last of
   its half-terms that lists it decides (D1). Where it isn't tricky, none of its tiles is marked; what each says is
   the same.
   A round: five different words (or every word in play, if fewer), one or two secure ones for review and the rest not
   yet secure.
     One week:          the rest at random, and at least 3 of the 5 from the chosen week's own words while it has that
                        many in play (answer 10).
     Its weeks, a term: the rest from the lowest step first (not yet, sound tiles, letters, harder letters), at random
                        within a step (answer 8; 0.7.0 question 12).
   Pure functions of the words file and the saved answers, so they are easy to test. No half-term, term or week is
   named here: they all come from the words file. */
(function () {
  'use strict';
  const MW = window.MW;
  const S = MW.wordSteps = {};

  S.STEPS = ['notyet', 'tiles', 'letters', 'harder', 'secure'];
  S.NAMES = { notyet: 'Not yet', tiles: 'Sound tiles', letters: 'Letters', harder: 'Harder letters', secure: 'Secure' };
  S.ALL = 'all';                 // every week of a half-term in play (saved as the week)
  S.SILENT = '-';                // a tile that says nothing (the e of a split pair)
  S.SLIPS = 2;                   // slips in a row that take a secure word back to harder letters
  function rank(step) { return S.STEPS.indexOf(step); }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

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
  // A capital letter ('M'): it only ever goes into its own word's tray.
  S.isCapital = function (ch) { return ch !== ch.toLowerCase(); };
  // A word's line: "words-w-" and the word in small letters ("words-w-mrs").
  S.line = function (w) { return 'words-w-' + String(w).toLowerCase(); };

  // ---------------------------------------------------------------- the words file
  // 'h [ere]' -> [{ text: 'h', tricky: false }, { text: 'ere', tricky: true }]
  S.tiles = function (spec) {
    return String(spec).trim().split(/\s+/).map(function (t) {
      const m = /^\[([A-Za-z]+)\]$/.exec(t);
      return m ? { text: m[1], tricky: true } : { text: t, tricky: false };
    });
  };
  // The file's terms, their half-terms and weeks, and every word listed in them (once each), with its tiles (each with
  // what it says), letters and spares. Problems in the file (a word with no tiles, tiles that don't spell it, a tile
  // with no sound, a word twice in one week) are listed, not thrown, so the tests and the grown-ups area can say what
  // is wrong.
  //   book.terms   [{ id, name, all, halves: [half, ...] }]
  //   book.halves  every half-term, in the file's order: [{ id, name, term, weeks: [{ week, tricky: [...], other: [...] }] }]
  //   book.words   { word: { word, line, tiles, letters, spares, says } }; book.order: every word once, as first listed
  //   book.start   { half, week }: the file's start (a half-term and week it has)
  S.read = function (data) {
    data = data && typeof data === 'object' ? data : {};
    const out = { words: {}, order: [], terms: [], halves: [], problems: [], harderTray: +data.harderTray || 10,
      start: null, sounds: {} };
    const problem = function (text) { out.problems.push(text); };
    const usual = data.sounds && typeof data.sounds === 'object' ? data.sounds : {};
    const goodId = function (id) { return id === S.SILENT || /^[a-z]+(-[a-z]+)*$/.test(String(id)); };
    Object.keys(usual).forEach(function (g) {
      if (goodId(usual[g])) out.sounds[g] = usual[g];
      else problem('sounds: ' + g + ' should be a sound id, such as "ai"');
    });
    const specs = data.words && typeof data.words === 'object' ? data.words : {};
    const tried = {}, lower = {};
    // a word's entry, read the first time it is listed (null if it has none)
    function entry(w) {
      if (has(tried, w)) return out.words[w] || null;
      tried[w] = true;
      const spec = has(specs, w) ? specs[w] : null;
      if (!spec || !spec.tiles) { problem(w + ': no tiles in the words file'); return null; }
      const tiles = S.tiles(spec.tiles);
      const spelt = tiles.map(function (t) { return t.text; }).join('');
      if (spelt !== w) problem(w + ': its tiles spell ' + spelt);
      if (!/^[A-Za-z]+$/.test(w)) problem(w + ': only letters, please');
      const low = w.toLowerCase();
      if (has(lower, low)) problem(w + ' and ' + lower[low] + ': two words that differ only in capitals (they would share a recording)');
      else lower[low] = w;
      // what each tile says: the word's own sound for it (one for each time the tile appears, if a list), or its usual
      // sound
      const own = spec.sounds && typeof spec.sounds === 'object' ? spec.sounds : {};
      Object.keys(own).forEach(function (k) {
        const n = tiles.filter(function (t) { return t.text === k; }).length;
        if (!n) problem(w + ': its sounds name ' + k + ', which isn\'t one of its tiles');
        else if (Array.isArray(own[k])) {
          if (own[k].length !== n) problem(w + ': its sounds for ' + k + ' list ' + own[k].length + ', but it has ' + n + ' ' + k + ' tile' + (n === 1 ? '' : 's'));
          if (!own[k].every(goodId)) problem(w + ': each sound for ' + k + ' should be a sound id, such as "ai", or "-"');
        } else if (!goodId(own[k])) problem(w + ': the sound for ' + k + ' should be a sound id, such as "ai", or "-"');
      });
      const times = {};
      tiles.forEach(function (t) {
        const i = times[t.text] = (times[t.text] || 0) + 1;      // the i-th time this tile appears, from the left
        let mine = null;
        if (has(own, t.text)) {
          const v = Array.isArray(own[t.text]) ? own[t.text][i - 1] : own[t.text];
          if (v !== undefined && goodId(v)) mine = v;
        }
        t.sound = mine !== null ? mine : (out.sounds[t.text] || null);
        if (t.tricky && mine === null) problem(w + ': say what its tricky tile ' + t.text + ' says in its sounds');
        else if (!t.sound) problem(w + ': no sound for its tile ' + t.text);
      });
      const letters = [];
      tiles.forEach(function (t) { t.text.split('').forEach(function (ch) { letters.push({ text: ch, tricky: t.tricky }); }); });
      const spares = String(spec.spares || '').trim().split(/\s+/).filter(Boolean);
      spares.forEach(function (s) { if (!/^[a-z]$/.test(s)) problem(w + ': the spare ' + s + ' should be one small letter (a capital is never a spare)'); });
      out.words[w] = { word: w, line: S.line(w), tiles: tiles, letters: letters, spares: spares, says: spec.says || '' };
      return out.words[w];
    }
    if (!Array.isArray(data.terms)) problem('terms: the words file needs its terms, each with its half-terms and their weeks');
    const termIds = {}, halfIds = {};
    (Array.isArray(data.terms) ? data.terms : []).forEach(function (tm, ti) {
      if (!tm || typeof tm !== 'object') { problem('terms: term ' + (ti + 1) + ' isn\'t a term'); return; }
      const id = String(tm.id || '');
      if (!id || has(termIds, id)) { problem('terms: term ' + (ti + 1) + ' needs an id of its own'); return; }
      termIds[id] = true;
      const term = { id: id, name: String(tm.name || id), all: typeof tm.all === 'string' ? tm.all : '', halves: [] };
      out.terms.push(term);
      (Array.isArray(tm.halves) ? tm.halves : []).forEach(function (hf, hi) {
        const hid = hf && typeof hf === 'object' ? String(hf.id || '') : '';
        if (!hid || has(halfIds, hid)) { problem(term.name + ': half-term ' + (hi + 1) + ' needs an id of its own'); return; }
        halfIds[hid] = true;
        const half = { id: hid, name: String(hf.name || hid), term: id, weeks: [] };
        const nums = {};
        (Array.isArray(hf.weeks) ? hf.weeks : []).forEach(function (wk) {
          const n = wk && typeof wk === 'object' ? +wk.week : NaN;
          if (!(n >= 1) || Math.floor(n) !== n || has(nums, n)) { problem(half.name + ': each week needs a number of its own (1, 2, 3…)'); return; }
          nums[n] = true;
          const week = { week: n, tricky: [], other: [] };
          const listed = {};
          ['tricky', 'other'].forEach(function (kind) {
            (Array.isArray(wk[kind]) ? wk[kind] : []).forEach(function (w) {
              w = String(w);
              if (has(listed, w)) { problem(half.name + ', week ' + n + ': ' + w + ' is listed twice'); return; }
              listed[w] = true;
              if (!entry(w)) return;
              week[kind].push(w);
              if (out.order.indexOf(w) < 0) out.order.push(w);
            });
          });
          half.weeks.push(week);
        });
        half.weeks.sort(function (a, b) { return a.week - b.week; });
        term.halves.push(half);
        out.halves.push(half);
      });
    });
    // the start: a half-term and a week the file has (or else the last half-term's first week)
    const st = data.start && typeof data.start === 'object' ? data.start : {};
    const sh = S.half(out, st.half);
    if (sh && S.weekOf(sh, +st.week)) out.start = { half: sh.id, week: +st.week };
    else {
      problem('start: the words file has no ' + (sh ? sh.name + ', week ' + st.week : 'half-term ' + (st.half || '(none given)')));
      const last = out.halves.filter(function (h) { return h.weeks.length; }).slice(-1)[0];
      if (last) out.start = { half: last.id, week: last.weeks[0].week };
    }
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

  // ---------------------------------------------------------------- half-terms, terms and choices
  S.half = function (book, id) { return book.halves.filter(function (h) { return h.id === id; })[0] || null; };
  S.term = function (book, id) { return book.terms.filter(function (t) { return t.id === id; })[0] || null; };
  S.weekOf = function (half, n) { return half ? half.weeks.filter(function (x) { return x.week === n; })[0] || null : null; };
  // A half-term's all-weeks choice's name, from the words file: "Weeks 1–5" (an en dash), or null with fewer than two weeks.
  S.allLabel = function (half) {
    if (!half || half.weeks.length < 2) return null;
    return 'Weeks ' + half.weeks[0].week + '–' + half.weeks[half.weeks.length - 1].week;
  };
  // A term's whole-term choice's name, from the words file ("All of autumn"), or null: a term with fewer than two
  // half-terms (its one half-term's weeks are the same words), or with no name for it.
  S.termLabel = function (term) { return term && term.all && term.halves.length >= 2 ? term.all : null; };
  S.start = function (book) { return book.start ? { half: book.start.half, week: book.start.week } : { half: null, week: null }; };
  // A grown-up's choice as saved, checked against the words file: { term } (a whole term), { half, week } (a week, or
  // S.ALL for the half-term's weeks together). Anything else (nothing saved, a choice saved before 0.7.0 with no
  // half-term in it, or one the file no longer has) is the file's start.
  S.choice = function (book, saved) {
    saved = saved && typeof saved === 'object' ? saved : {};
    if (saved.term !== undefined && saved.term !== null) {
      const t = S.term(book, saved.term);
      return S.termLabel(t) ? { term: t.id } : S.start(book);
    }
    const h = S.half(book, saved.half);
    if (h && saved.week === S.ALL && S.allLabel(h)) return { half: h.id, week: S.ALL };
    if (h && saved.week !== S.ALL && S.weekOf(h, +saved.week)) return { half: h.id, week: +saved.week };
    return S.start(book);
  };
  S.wide = function (c) { return !!(c.term || c.week === S.ALL); };      // every word of a half-term or a term in play
  // The half-terms a choice covers: its half-term, or each half-term of its term.
  S.halvesOf = function (book, c) {
    if (c.term) { const t = S.term(book, c.term); return t ? t.halves : []; }
    const h = S.half(book, c.half);
    return h ? [h] : [];
  };
  // Each word's marking for a choice: { half, week, tricky }: the half-term that decides it (the one in play; with a
  // whole term, the last of its half-terms that lists the word), whether that half-term lists it as tricky, and the
  // word's own week there (the first week that lists it: "time" is week 3's). A word the choice doesn't cover (only
  // through the test hooks) is decided as if every half-term in the file were in play.
  S.marks = function (book, c) {
    const out = {};
    const scan = function (halves) {
      halves.forEach(function (h) {
        const seen = {};
        h.weeks.forEach(function (wk) {
          [['tricky', true], ['other', false]].forEach(function (k) {
            wk[k[0]].forEach(function (w) {
              if (!seen[w]) { seen[w] = true; out[w] = { half: h.id, week: wk.week, tricky: k[1] }; }
              else if (k[1]) out[w].tricky = true;
            });
          });
        });
      });
    };
    scan(book.halves);
    scan(S.halvesOf(book, c));
    return out;
  };
  // Is the word marked tricky with this choice in play?
  S.marked = function (book, c, w) { const m = S.marks(book, c)[w]; return m ? m.tricky : true; };

  // The words in play for a choice (before recordings are checked), each once:
  //   a week       that week's words (tricky, then other), then the tricky words of its half-term's earlier weeks;
  //   its weeks    every word of the half-term, week by week (each week's tricky words, then its other words);
  //   a term       every word of its half-terms, half-term by half-term, in the order the file first lists it.
  S.inPlay = function (book, c) {
    const out = [];
    const add = function (list) { list.forEach(function (w) { if (book.words[w] && out.indexOf(w) < 0) out.push(w); }); };
    if (S.wide(c)) {
      S.halvesOf(book, c).forEach(function (h) { h.weeks.forEach(function (wk) { add(wk.tricky); add(wk.other); }); });
      return out;
    }
    const h = S.half(book, c.half);
    if (!h) return out;
    h.weeks.forEach(function (wk) { if (wk.week === c.week) { add(wk.tricky); add(wk.other); } });
    h.weeks.forEach(function (wk) { if (wk.week < c.week) add(wk.tricky); });
    return out;
  };
  // A week's own words (its tricky words and its other words), in a half-term.
  S.ownWords = function (book, half, week) {
    const wk = S.weekOf(S.half(book, half), week);
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
  //         lowest: true with a half-term's weeks or a whole term in play (the words on the lowest step first),
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
  //            (fill: the words to take them from, in order of preference), each a letter not already in the tray and
  //            never a capital (a capital only ever goes into its own word's tray).
  // marked: false when the half-term in play doesn't list the word as tricky: then no place or tile is marked (S.marked).
  // -> { mode, places: [{ text, tricky, sound }], tray: [{ text, tricky, spare, sound }] } (the tray shuffled)
  S.plan = function (book, word, step, fill, rand, marked) {
    rand = rand || Math.random;
    const e = book.words[word];
    const mode = S.mode(step);
    const mark = marked !== false;
    const places = (mode === 'tiles' ? e.tiles : e.letters).map(function (t) {
      return { text: t.text, tricky: mark && t.tricky, sound: mode === 'tiles' ? t.sound : null };
    });
    const tray = places.map(function (p) { return { text: p.text, tricky: p.tricky, spare: false, sound: p.sound }; });
    if (mode !== 'tiles') e.spares.forEach(function (s) { tray.push({ text: s, tricky: false, spare: true, sound: null }); });
    if (mode === 'harder') {
      const have = {};
      tray.forEach(function (t) { have[t.text] = true; });
      (fill || []).forEach(function (group) {
        const letters = [];
        group.filter(function (w) { return w !== word && book.words[w]; }).forEach(function (w) {
          w.split('').forEach(function (ch) { if (!S.isCapital(ch) && !have[ch] && letters.indexOf(ch) < 0) letters.push(ch); });
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
  //   one week in play           that week's words, then the other words in play, then any word in the file;
  //   its weeks, or a whole term the word's own week's words (in the half-term that decides its marking), then any
  //                              word in play, then any word in the file (answer 9).
  // pool: the words in play this round (the recorded ones); without it, every word in play.
  S.fillFrom = function (book, c, word, pool) {
    const inPlay = pool || S.inPlay(book, c);
    if (S.wide(c)) {
      const m = S.marks(book, c)[word];
      return [m ? S.ownWords(book, m.half, m.week) : [], inPlay, book.order];
    }
    return [S.ownWords(book, c.half, c.week), inPlay, book.order];
  };

  // Every question the game can ask for a choice: each word in play, to find and to build at each step.
  S.allQuestions = function (book, c) {
    const out = [];
    S.inPlay(book, c).forEach(function (w) {
      out.push({ word: w, kind: 'find' });
      ['tiles', 'letters', 'harder'].forEach(function (m) { out.push({ word: w, kind: 'build', mode: m }); });
    });
    return out;
  };
})();
