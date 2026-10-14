/* MeeMee Rockets: the words. The one file to edit for a new half-term or term (no code changes).

   terms       the school terms, in order. Each has an id ('autumn'), a name ('Autumn'), all: the name of the choice
               that plays the whole term ('All of autumn', shown in the Words tab once the term has two half-terms or
               more), and its half-terms (halves), in order. Each half-term has an id ('autumn-2'), a name
               ('Autumn 2') and its weeks:
     weeks     each week of the class's list: its tricky words, then its other words (the sounded-out ones). The Words
               tab offers each half-term, then the whole term; under a half-term, each of its weeks, then all of them
               together, named from its first and last weeks here ("Weeks 1–5"). A week's words, once picked, are in
               play with the tricky words of the same half-term's earlier weeks (not another half-term's).
               A word may be listed in more than one week, in one half-term ("time", weeks 3 and 5) or in several
               (go, autumn 1 and autumn 2): it has one entry in words below, and one step wherever it is played. It is
               marked tricky only where the half-term in play lists it as tricky; with a whole term in play, the last
               half-term that lists it decides. A word listed twice in the same week is a mistake.
   start       the half-term and week in play until a grown-up picks another in the grown-ups area (Words tab). A tablet
               with nothing picked, or with a choice this file no longer has, plays this. Changing it later doesn't move
               a tablet that already has a choice saved (every tablet that had played by 0.7.0 has Autumn 2, week 1
               saved): for a new half-term, pick it in the Words tab on each tablet.
   harderTray  how many tiles the tray holds in harder letters: the word's letters, its spares, then letters from
               other words (the week in play's; with a half-term's weeks or a whole term in play, the word's own week's
               first). A capital letter never fills another word's tray.
   sounds      what each tile says when it is picked up in the sound tiles step: its usual sound, as a sound id. Each
               id is a recording: the line "words-s-" and the id in lines.json ("ai" is "words-s-ai"), recorded on the
               recording page. Letters that make one sound share it: c and k both say "k"; ai, ay and ey say "ai".
               oo has no usual sound (it says "oo" as in food, or "oo" as in took): each word with oo says which.
   words       every word once, with:
     tiles     its sound tiles, left to right, with a space between them: 'c ar t oo n'. Letters that make one
               sound ('ar', 'ay', 'ere') are one tile. Square brackets mark the tricky part: 'h [ere]'.
               A split pair marks both its tiles ('s [o] m [e]'); a whole tricky word marks every tile ('[o] [ne]').
               Capital letters are written as the class writes them ('[M] [r] [s]'): a capital is a tile like any
               other, but it only ever goes into its own word's tray. Two words that differ only in capitals are a
               mistake.
     sounds    the tiles that say something other than their usual sound in this word, as { tile: sound id }:
               { ere: 'ear' }. Every tricky tile says what it says in this word ("ai" in "said" says "e"), so each
               tricky tile is listed here. '-' is a tile that says nothing (the e of a split pair: in "some" the o
               says the pair's sound, "u", and the e says nothing). A tile that appears more than once can say
               something different each time: a list, one sound per time it appears, left to right
               (these: { e: ['ee', '-'] }). One sound, not in a list, covers every time the tile appears.
     spares    the extra letters for letters mode, with a space between them: 'i e'. Small letters only (a capital is
               never a spare). Pick letters the word doesn't have. A spare that repeats a letter of the word is just as
               good as the word's own letter, so it isn't a wrong choice ("you" keeps o, decided 10 October 2026); a
               small m is a different letter from a capital M, so it is a wrong choice for Mr, Mrs and Ms.
     says      what the tricky part says (for grown-ups; the game doesn't show it).

   Every word also needs its line in lines.json ("words-w-" and the word in small letters, such as "words-w-magnet"
   and "words-w-mrs"), recorded on the recording page. A word whose recording isn't there yet stays out of play until it
   is, and a tile whose sound isn't recorded yet is quiet. The grown-ups' Words tab lists both, and anything in this
   file that doesn't add up. */
(function () {
  'use strict';
  window.MW.wordsData = {
    harderTray: 10,
    start: { half: 'autumn-2', week: 1 },
    terms: [
      { id: 'autumn', name: 'Autumn', all: 'All of autumn', halves: [
        { id: 'autumn-1', name: 'Autumn 1', weeks: [
          { week: 1, tricky: ['go', 'my', 'into', 'out'], other: ['feel', 'food', 'sort', 'down', 'right', 'hard', 'took', 'hear'] },
          { week: 2, tricky: ['what', 'she', 'me', 'love'], other: ['misses', 'chain', 'queen', 'chair', 'year', 'cobweb', 'goats', 'farmyard'] },
          { week: 3, tricky: ['they', 'some', 'were', 'sure'], other: ['green', 'brown', 'train', 'thinks', 'drum', 'splat', 'paint', 'frog'] },
          { week: 4, tricky: ['said', 'you', 'like', 'push'], other: ['day', 'cloud', 'boy', 'read', 'play', 'sound', 'joy', 'treat'] },
          { week: 5, tricky: ['all', 'of', 'one', 'here'], other: ['magnet', 'cartoon', 'rabbit', 'spray', 'popcorn', 'proud', 'toy', 'say'] }
        ] },
        { id: 'autumn-2', name: 'Autumn 2', weeks: [
          { week: 1, tricky: ['their', 'people', 'oh', 'your'], other: ['bird', 'girl', 'pie', 'tried', 'blue', 'true', 'human', 'unit'] },
          { week: 2, tricky: ['Mr', 'Mrs', 'Ms', 'ask'], other: ['both', 'go', 'child', 'kind', 'basic', 'acorn', 'fever', 'me'] },
          { week: 3, tricky: ['could', 'would', 'should', 'our'], other: ['take', 'same', 'time', 'like', 'home', 'woke', 'rude', 'cute'] },
          { week: 4, tricky: ['house', 'mouse', 'water', 'want'], other: ['these', 'even', 'new', 'chew', 'shriek', 'field', 'claw', 'draw'] },
          { week: 5, tricky: ['sure', 'some', 'little', 'what'], other: ['time', 'fried', 'spray', 'game', 'open', 'float', 'being', 'eating'] }
        ] }
      ] }
    ],
    sounds: {
      a: 'a', b: 'b', c: 'k', d: 'd', e: 'e', f: 'f', g: 'g', h: 'h', i: 'i', j: 'j', k: 'k', l: 'l', m: 'm',
      n: 'n', o: 'o', p: 'p', r: 'r', s: 's', t: 't', u: 'u', v: 'v', w: 'w', y: 'y', M: 'm',
      ai: 'ai', air: 'air', ar: 'ar', aw: 'or', ay: 'ai', ch: 'ch', ea: 'ee', ear: 'ear', ee: 'ee', er: 'er',
      ew: 'oo-long', ie: 'igh', igh: 'igh', ir: 'ur', le: 'l', ll: 'l', ng: 'ng', oa: 'oa', or: 'or', ou: 'ow',
      ow: 'ow', oy: 'oy', qu: 'qu', sh: 'sh', ss: 's', th: 'th', tt: 't', ue: 'oo-long', ure: 'ure'
    },
    words: {
      // ---------------------------------------------------------------- autumn 1
      // week 5
      all: { tiles: '[a] ll', sounds: { a: 'or' }, spares: 'o', says: 'a says "or"' },
      of: { tiles: 'o [f]', sounds: { f: 'v' }, spares: 'v', says: 'f says "v"' },
      one: { tiles: '[o] [ne]', sounds: { o: 'wu', ne: 'n' }, spares: 'w', says: 'the whole word: o says "w-u", ne says "n"' },
      here: { tiles: 'h [ere]', sounds: { ere: 'ear' }, spares: 'a', says: 'ere says "ear"' },
      magnet: { tiles: 'm a g n e t', spares: 'i' },
      cartoon: { tiles: 'c ar t oo n', sounds: { oo: 'oo-long' }, spares: 'k' },
      rabbit: { tiles: 'r a b b i t', spares: 'd' },
      spray: { tiles: 's p r ay', spares: 'i e' },                      // autumn 2 too (week 5)
      popcorn: { tiles: 'p o p c or n', spares: 'k' },
      proud: { tiles: 'p r ou d', spares: 'w' },
      toy: { tiles: 't oy', spares: 'i' },
      say: { tiles: 's ay', spares: 'i' },
      // week 1
      go: { tiles: 'g [o]', sounds: { o: 'oa' }, spares: 'a', says: 'o says "oa"' },    // autumn 2 too, not tricky there
      my: { tiles: 'm [y]', sounds: { y: 'igh' }, spares: 'i', says: 'y says "igh"' },
      into: { tiles: 'i n t [o]', sounds: { o: 'oo-long' }, spares: 'u', says: 'o says "oo"' },
      out: { tiles: '[ou] t', sounds: { ou: 'ow' }, spares: 'w', says: 'ou says "ow"' },
      feel: { tiles: 'f ee l', spares: 'a' },
      food: { tiles: 'f oo d', sounds: { oo: 'oo-long' }, spares: 'u' },
      sort: { tiles: 's or t', spares: 'a' },
      down: { tiles: 'd ow n', spares: 'u' },
      right: { tiles: 'r igh t', spares: 'y' },
      hard: { tiles: 'h ar d', spares: 'b' },
      took: { tiles: 't oo k', sounds: { oo: 'oo-short' }, spares: 'c' },
      hear: { tiles: 'h ear', spares: 'i' },
      // week 2
      what: { tiles: '[wh] [a] t', sounds: { wh: 'w', a: 'o' }, spares: 'o', says: 'wh says "w", a says "o"' },   // autumn 2 too
      she: { tiles: 'sh [e]', sounds: { e: 'ee' }, spares: 'c', says: 'e says "ee"' },
      me: { tiles: 'm [e]', sounds: { e: 'ee' }, spares: 'n', says: 'e says "ee"' },    // autumn 2 too, not tricky there
      love: { tiles: 'l [o] [ve]', sounds: { o: 'u', ve: 'v' }, spares: 'u', says: 'o says "u", ve says "v"' },
      misses: { tiles: 'm i ss e s', spares: 'z' },
      chain: { tiles: 'ch ai n', spares: 'y' },
      queen: { tiles: 'qu ee n', spares: 'w' },
      chair: { tiles: 'ch air', spares: 'e' },
      year: { tiles: 'y ear', spares: 'i' },
      cobweb: { tiles: 'c o b w e b', spares: 'd' },
      goats: { tiles: 'g oa t s', spares: 'w' },
      farmyard: { tiles: 'f ar m y ar d', spares: 'b' },
      // week 3
      they: { tiles: 'th [ey]', sounds: { th: 'th-voiced', ey: 'ai' }, spares: 'a', says: 'ey says "ai"' },
      some: { tiles: 's [o] m [e]', sounds: { o: 'u', e: '-' }, spares: 'u', says: 'o-e says "u" (a split pair)' },   // autumn 2 too
      were: { tiles: 'w [ere]', sounds: { ere: 'ur' }, spares: 'u', says: 'ere says "ur"' },
      sure: { tiles: '[s] [ure]', sounds: { s: 'sh', ure: 'ure' }, spares: 'h', says: 'the whole word: s says "sh"' },   // autumn 2 too
      green: { tiles: 'g r ee n', spares: 'a' },
      brown: { tiles: 'b r ow n', spares: 'u' },
      train: { tiles: 't r ai n', spares: 'y' },
      thinks: { tiles: 'th i n k s', spares: 'f' },
      drum: { tiles: 'd r u m', spares: 'b' },
      splat: { tiles: 's p l a t', spares: 'e' },
      paint: { tiles: 'p ai n t', spares: 'e' },
      frog: { tiles: 'f r o g', spares: 'a' },
      // week 4
      said: { tiles: 's [ai] d', sounds: { ai: 'e' }, spares: 'e', says: 'ai says "e"' },
      you: { tiles: 'y [ou]', sounds: { ou: 'oo-long' }, spares: 'o', says: 'ou says "oo"' },
      like: { tiles: 'l [i] k [e]', sounds: { i: 'igh', e: '-' }, spares: 'c', says: 'i-e says "igh" (a split pair)' },   // autumn 2 too, not tricky there
      push: { tiles: 'p [u] sh', sounds: { u: 'oo-short' }, spares: 'o', says: 'u says "oo", as in book' },
      day: { tiles: 'd ay', spares: 'i' },
      cloud: { tiles: 'c l ou d', spares: 'w' },
      boy: { tiles: 'b oy', spares: 'i' },
      read: { tiles: 'r ea d', spares: 'b' },
      play: { tiles: 'p l ay', spares: 'i' },
      sound: { tiles: 's ou n d', spares: 'w' },
      joy: { tiles: 'j oy', spares: 'i' },
      treat: { tiles: 't r ea t', spares: 'i' },

      // ---------------------------------------------------------------- autumn 2 (go, me, like, sure, some, what and
      // spray are above, from autumn 1)
      // week 1
      their: { tiles: 'th [eir]', sounds: { th: 'th-voiced', eir: 'air' }, spares: 'a', says: 'eir says "air"' },
      people: { tiles: 'p [eo] p [le]', sounds: { eo: 'ee', le: 'l' }, spares: 'b', says: 'eo says "ee", le says "l"' },   // le isn't taught yet
      oh: { tiles: '[o] [h]', sounds: { o: 'oa', h: '-' }, spares: 'w', says: 'the whole word: o says "oa", h says nothing' },
      your: { tiles: 'y [our]', sounds: { our: 'or' }, spares: 'e', says: 'our says "or"' },
      bird: { tiles: 'b ir d', spares: 'u' },
      girl: { tiles: 'g ir l', spares: 'u' },
      pie: { tiles: 'p ie', spares: 'y' },
      tried: { tiles: 't r ie d', spares: 'y' },
      blue: { tiles: 'b l ue', spares: 'w' },
      true: { tiles: 't r ue', spares: 'w' },
      human: { tiles: 'h u m a n', sounds: { u: 'yoo' }, spares: 'e' },
      unit: { tiles: 'u n i t', sounds: { u: 'yoo' }, spares: 'y' },
      // week 2: Mr, Mrs and Ms start with a capital M; the tiles stay quiet and the word's recording says it. The spare is
      // a small m, so the capital has to be picked.
      Mr: { tiles: '[M] [r]', sounds: { M: '-', r: '-' }, spares: 'm', says: 'short for "mister"; the tiles stay quiet' },
      Mrs: { tiles: '[M] [r] [s]', sounds: { M: '-', r: '-', s: '-' }, spares: 'm', says: 'short for "missiz"; the tiles stay quiet' },
      Ms: { tiles: '[M] [s]', sounds: { M: '-', s: '-' }, spares: 'm', says: 'said "mizz"; the tiles stay quiet' },
      ask: { tiles: '[a] s k', sounds: { a: 'ar' }, spares: 'c', says: 'a says "ar"' },
      both: { tiles: 'b o th', sounds: { o: 'oa' }, spares: 'f' },
      child: { tiles: 'ch i l d', sounds: { i: 'igh' }, spares: 'y' },
      kind: { tiles: 'k i n d', sounds: { i: 'igh' }, spares: 'c' },
      basic: { tiles: 'b a s i c', sounds: { a: 'ai' }, spares: 'k' },
      acorn: { tiles: 'a c or n', sounds: { a: 'ai' }, spares: 'k' },
      fever: { tiles: 'f e v er', sounds: { e: 'ee' }, spares: 'u' },
      // week 3
      could: { tiles: 'c [oul] d', sounds: { oul: 'oo-short' }, spares: 'k', says: 'oul says "oo", as in book' },
      would: { tiles: 'w [oul] d', sounds: { oul: 'oo-short' }, spares: 'h', says: 'oul says "oo", as in book' },
      should: { tiles: 'sh [oul] d', sounds: { oul: 'oo-short' }, spares: 'e', says: 'oul says "oo", as in book' },
      our: { tiles: '[ou] [r]', sounds: { ou: 'ow', r: 'er' }, spares: 'w', says: 'the whole word: ou says "ow", r says "er"' },
      take: { tiles: 't a k e', sounds: { a: 'ai', e: '-' }, spares: 'c' },
      same: { tiles: 's a m e', sounds: { a: 'ai', e: '-' }, spares: 'c' },
      time: { tiles: 't i m e', sounds: { i: 'igh', e: '-' }, spares: 'y' },             // weeks 3 and 5
      home: { tiles: 'h o m e', sounds: { o: 'oa', e: '-' }, spares: 'a' },
      woke: { tiles: 'w o k e', sounds: { o: 'oa', e: '-' }, spares: 'c' },
      rude: { tiles: 'r u d e', sounds: { u: 'oo-long', e: '-' }, spares: 'o' },
      cute: { tiles: 'c u t e', sounds: { u: 'yoo', e: '-' }, spares: 'k' },
      // week 4
      house: { tiles: 'h ou s [e]', sounds: { e: '-' }, spares: 'w', says: 'e says nothing' },
      mouse: { tiles: 'm ou s [e]', sounds: { e: '-' }, spares: 'w', says: 'e says nothing' },
      water: { tiles: 'w [a] t er', sounds: { a: 'or' }, spares: 'o', says: 'a says "or"' },
      want: { tiles: 'w [a] n t', sounds: { a: 'o' }, spares: 'o', says: 'a says "o"' },
      these: { tiles: 'th e s e', sounds: { th: 'th-voiced', e: ['ee', '-'], s: 'z' }, spares: 'z' },   // e-e split pair
      even: { tiles: 'e v e n', sounds: { e: ['ee', 'e'] }, spares: 'i' },               // the second e says "e"
      new: { tiles: 'n ew', sounds: { ew: 'yoo' }, spares: 'u' },
      chew: { tiles: 'ch ew', spares: 'o' },
      shriek: { tiles: 'sh r ie k', sounds: { ie: 'ee' }, spares: 'c' },
      field: { tiles: 'f ie l d', sounds: { ie: 'ee' }, spares: 'a' },
      claw: { tiles: 'c l aw', spares: 'k' },
      draw: { tiles: 'd r aw', spares: 'b' },
      // week 5
      little: { tiles: 'l i tt [le]', sounds: { le: 'l' }, spares: 'd', says: 'le says "l"' },
      fried: { tiles: 'f r ie d', spares: 'y' },
      game: { tiles: 'g a m e', sounds: { a: 'ai', e: '-' }, spares: 'y' },
      open: { tiles: 'o p e n', sounds: { o: 'oa' }, spares: 'i' },
      float: { tiles: 'f l oa t', spares: 'w' },
      being: { tiles: 'b e i ng', sounds: { e: 'ee' }, spares: 'd' },
      eating: { tiles: 'ea t i ng', spares: 'k' }
    }
  };
})();
