/* MeeMee Rockets: the words. The one file to edit for a new half-term (no code changes).

   weeks       each week of the class's list: its tricky words, then its other words (the sounded-out ones). The Words
               tab offers each week, then all of them together, named from the first and last weeks here ("Weeks 1–5").
   startWeek   the week in play until a grown-up picks another in the grown-ups area (Words tab).
   harderTray  how many tiles the tray holds in harder letters: the word's letters, its spares, then letters from
               other words (the week in play's; with every week in play, the word's own week's first).
   sounds      what each tile says when it is picked up in the sound tiles step: its usual sound, as a sound id. Each
               id is a recording: the line "words-s-" and the id in lines.json ("ai" is "words-s-ai"), recorded on the
               recording page. Letters that make one sound share it: c and k both say "k"; ai, ay and ey say "ai".
               oo has no usual sound (it says "oo" as in food, or "oo" as in took): each word with oo says which.
   words       every word, with:
     tiles     its sound tiles, left to right, with a space between them: 'c ar t oo n'. Letters that make one
               sound ('ar', 'ay', 'ere') are one tile. Square brackets mark the tricky part: 'h [ere]'.
               A split pair marks both its tiles ('s [o] m [e]'); a whole tricky word marks every tile ('[o] [ne]').
     sounds    the tiles that say something other than their usual sound in this word, as { tile: sound id }:
               { ere: 'ear' }. Every tricky tile says what it says in this word ("ai" in "said" says "e"), so each
               tricky tile is listed here. '-' is a tile that says nothing (the e of a split pair: in "some" the o
               says the pair's sound, "u", and the e says nothing).
     spares    the extra letters for letters mode, with a space between them: 'i e'. Pick letters the word doesn't
               have. A spare that repeats a letter of the word is just as good as the word's own letter, so it isn't
               a wrong choice ("you" keeps o, decided 10 October 2026).
     says      what the tricky part says (for grown-ups; the game doesn't show it).

   Every word also needs its line in lines.json ("words-w-" and the word, such as "words-w-magnet"), recorded on the
   recording page. A word whose recording isn't there yet stays out of play until it is, and a tile whose sound isn't
   recorded yet is quiet. The grown-ups' Words tab lists both, and anything in this file that doesn't add up. */
(function () {
  'use strict';
  window.MW.wordsData = {
    startWeek: 5,
    harderTray: 10,
    weeks: [
      { week: 1, tricky: ['go', 'my', 'into', 'out'], other: ['feel', 'food', 'sort', 'down', 'right', 'hard', 'took', 'hear'] },
      { week: 2, tricky: ['what', 'she', 'me', 'love'], other: ['misses', 'chain', 'queen', 'chair', 'year', 'cobweb', 'goats', 'farmyard'] },
      { week: 3, tricky: ['they', 'some', 'were', 'sure'], other: ['green', 'brown', 'train', 'thinks', 'drum', 'splat', 'paint', 'frog'] },
      { week: 4, tricky: ['said', 'you', 'like', 'push'], other: ['day', 'cloud', 'boy', 'read', 'play', 'sound', 'joy', 'treat'] },
      { week: 5, tricky: ['all', 'of', 'one', 'here'], other: ['magnet', 'cartoon', 'rabbit', 'spray', 'popcorn', 'proud', 'toy', 'say'] }
    ],
    sounds: {
      a: 'a', b: 'b', c: 'k', d: 'd', e: 'e', f: 'f', g: 'g', h: 'h', i: 'i', j: 'j', k: 'k', l: 'l', m: 'm',
      n: 'n', o: 'o', p: 'p', r: 'r', s: 's', t: 't', u: 'u', v: 'v', w: 'w', y: 'y',
      ai: 'ai', air: 'air', ar: 'ar', ay: 'ai', ch: 'ch', ea: 'ee', ear: 'ear', ee: 'ee', igh: 'igh', ll: 'l',
      oa: 'oa', or: 'or', ou: 'ow', ow: 'ow', oy: 'oy', qu: 'qu', sh: 'sh', ss: 's', th: 'th', ure: 'ure'
    },
    words: {
      // week 5
      all: { tiles: '[a] ll', sounds: { a: 'or' }, spares: 'o', says: 'a says "or"' },
      of: { tiles: 'o [f]', sounds: { f: 'v' }, spares: 'v', says: 'f says "v"' },
      one: { tiles: '[o] [ne]', sounds: { o: 'wu', ne: 'n' }, spares: 'w', says: 'the whole word: o says "w-u", ne says "n"' },
      here: { tiles: 'h [ere]', sounds: { ere: 'ear' }, spares: 'a', says: 'ere says "ear"' },
      magnet: { tiles: 'm a g n e t', spares: 'i' },
      cartoon: { tiles: 'c ar t oo n', sounds: { oo: 'oo-long' }, spares: 'k' },
      rabbit: { tiles: 'r a b b i t', spares: 'd' },
      spray: { tiles: 's p r ay', spares: 'i e' },
      popcorn: { tiles: 'p o p c or n', spares: 'k' },
      proud: { tiles: 'p r ou d', spares: 'w' },
      toy: { tiles: 't oy', spares: 'i' },
      say: { tiles: 's ay', spares: 'i' },
      // week 1
      go: { tiles: 'g [o]', sounds: { o: 'oa' }, spares: 'a', says: 'o says "oa"' },
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
      what: { tiles: '[wh] [a] t', sounds: { wh: 'w', a: 'o' }, spares: 'o', says: 'wh says "w", a says "o"' },
      she: { tiles: 'sh [e]', sounds: { e: 'ee' }, spares: 'c', says: 'e says "ee"' },
      me: { tiles: 'm [e]', sounds: { e: 'ee' }, spares: 'n', says: 'e says "ee"' },
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
      some: { tiles: 's [o] m [e]', sounds: { o: 'u', e: '-' }, spares: 'u', says: 'o-e says "u" (a split pair)' },
      were: { tiles: 'w [ere]', sounds: { ere: 'ur' }, spares: 'u', says: 'ere says "ur"' },
      sure: { tiles: '[s] [ure]', sounds: { s: 'sh', ure: 'ure' }, spares: 'h', says: 'the whole word: s says "sh"' },
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
      like: { tiles: 'l [i] k [e]', sounds: { i: 'igh', e: '-' }, spares: 'c', says: 'i-e says "igh" (a split pair)' },
      push: { tiles: 'p [u] sh', sounds: { u: 'oo-short' }, spares: 'o', says: 'u says "oo", as in book' },
      day: { tiles: 'd ay', spares: 'i' },
      cloud: { tiles: 'c l ou d', spares: 'w' },
      boy: { tiles: 'b oy', spares: 'i' },
      read: { tiles: 'r ea d', spares: 'b' },
      play: { tiles: 'p l ay', spares: 'i' },
      sound: { tiles: 's ou n d', spares: 'w' },
      joy: { tiles: 'j oy', spares: 'i' },
      treat: { tiles: 't r ea t', spares: 'i' }
    }
  };
})();
