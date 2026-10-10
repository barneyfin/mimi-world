/* MeeMee Rockets: the words. The one file to edit for a new half-term (no code changes).

   weeks       each week of the class's list: its tricky words, then its other words (the sounded-out ones).
   startWeek   the week in play until a grown-up picks another in the grown-ups area (Words tab).
   harderTray  how many tiles the tray holds in harder letters: the word's letters, its spares, then letters from
               the week's other words.
   words       every word, with:
     tiles     its sound tiles, left to right, with a space between them: 'c ar t oo n'. Letters that make one
               sound ('ar', 'ay', 'ere') are one tile. Square brackets mark the tricky part: 'h [ere]'.
               A split pair marks both its tiles ('s [o] m [e]'); a whole tricky word marks every tile ('[o] [ne]').
     spares    the extra letters for letters mode, with a space between them: 'i e'. A spare may repeat a letter
               of the word (the extra e in 'she').
     says      what the tricky part says (for grown-ups; the game doesn't show it).

   Every word also needs its line in lines.json ("words-w-" and the word, such as "words-w-magnet"), recorded on the
   recording page. A word whose recording isn't there yet stays out of play until it is. */
(function () {
  'use strict';
  window.MW.wordsData = {
    startWeek: 5,
    harderTray: 10,
    weeks: [
      { week: 1, tricky: ['go', 'my', 'into', 'out'], other: [] },
      { week: 2, tricky: ['what', 'she', 'me', 'love'], other: [] },
      { week: 3, tricky: ['they', 'some', 'were', 'sure'], other: [] },
      { week: 4, tricky: ['said', 'you', 'like', 'push'], other: [] },
      { week: 5, tricky: ['all', 'of', 'one', 'here'], other: ['magnet', 'cartoon', 'rabbit', 'spray', 'popcorn', 'proud', 'toy', 'say'] }
    ],
    words: {
      // week 5
      all: { tiles: '[a] ll', spares: 'o', says: 'a says "or"' },
      of: { tiles: 'o [f]', spares: 'v', says: 'f says "v"' },
      one: { tiles: '[o] [ne]', spares: 'w', says: 'the whole word: o says "w-u", ne says "n"' },
      here: { tiles: 'h [ere]', spares: 'a', says: 'ere says "ear"' },
      magnet: { tiles: 'm a g n e t', spares: 'i' },
      cartoon: { tiles: 'c ar t oo n', spares: 'k' },
      rabbit: { tiles: 'r a b b i t', spares: 'd' },
      spray: { tiles: 's p r ay', spares: 'i e' },
      popcorn: { tiles: 'p o p c or n', spares: 'k' },
      proud: { tiles: 'p r ou d', spares: 'w' },
      toy: { tiles: 't oy', spares: 'i' },
      say: { tiles: 's ay', spares: 'i' },
      // week 1
      go: { tiles: 'g [o]', spares: 'a', says: 'o says "oa"' },
      my: { tiles: 'm [y]', spares: 'i', says: 'y says "igh"' },
      into: { tiles: 'i n t [o]', spares: 'u', says: 'o says "oo"' },
      out: { tiles: '[ou] t', spares: 'w', says: 'ou says "ow"' },
      // week 2
      what: { tiles: '[wh] [a] t', spares: 'o', says: 'wh says "w", a says "o"' },
      she: { tiles: 'sh [e]', spares: 'e', says: 'e says "ee"' },
      me: { tiles: 'm [e]', spares: 'e', says: 'e says "ee"' },
      love: { tiles: 'l [o] [ve]', spares: 'u', says: 'o says "u", ve says "v"' },
      // week 3
      they: { tiles: 'th [ey]', spares: 'a', says: 'ey says "ai"' },
      some: { tiles: 's [o] m [e]', spares: 'u', says: 'o-e says "u" (a split pair)' },
      were: { tiles: 'w [ere]', spares: 'u', says: 'ere says "ur"' },
      sure: { tiles: '[s] [ure]', spares: 'h', says: 'the whole word: s says "sh"' },
      // week 4
      said: { tiles: 's [ai] d', spares: 'e', says: 'ai says "e"' },
      you: { tiles: 'y [ou]', spares: 'o', says: 'ou says "oo"' },
      like: { tiles: 'l [i] k [e]', spares: 'c', says: 'i-e says "igh" (a split pair)' },
      push: { tiles: 'p [u] sh', spares: 'o', says: 'u says "oo", as in book' }
    }
  };
})();
