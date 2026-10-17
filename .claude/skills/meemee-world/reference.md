# MeeMee World kit reference (kit 0.8)

Everything a game needs, in the order you'll need it. `games/_template/` (the starter game, id `starter`) shows each part working; `games/rescue/` is the full example.

## The page

The build (`tools/build.py`) makes one page, `docs/index.html`, holding the kit and every game: the kit's scripts first (`KIT_JS` in build.py, `world.js` last), then each game's scripts in the order of their places on the map, each game in its own `<script>` (so a mistake in one game's code leaves the world and the other games working). When the page has loaded, the world starts: it builds the start screen, the map (five places; each game takes one), the crew screen, then calls each game's `build()`, then shows the start screen. Everything is drawn on a 1280 × 800 stage (`MW.stage`, scaled to fit; `MW.stage.toStage(clientX, clientY)` turns a touch into stage px).

The page's version (`VERSION` in `tools/build.py`, shown as "Page version" in the grown-ups Checks tab and in the offline copy's name) is Barney's: he sets it for each release. A new game, or a change to one, never changes it.

## A game's folder

```
games/<id>/
  game.json     who it is (below)
  lines.json    every line it says (Voice lines)
  game.js       its code (any number of scripts, listed in game.json)
  art.py        optional: its own drawings (Drawings)
  game.css      optional: its own styles (colour tokens only)
```

`game.json`:

| Key | What it is |
|---|---|
| `id` | short lower-case letters, the same as the folder name: `"words"` |
| `name` | its title, for its place's label, its title banner and the recording page: `"MeeMee Words"` |
| `planet` | which of the map's five places is its (the key keeps its old name): `0` the ringed mint planet (MeeMee Rescue's), `1` the indigo planet (MeeMee Rockets'), `2` the small peach planet (Take MeeMee Home's), `3` the cluster of rocks in the asteroid belt, `4` the space station. No two games share one (the build checks) |
| `badge` | the drawing on its place's badge and at the left of its title banner: a kit drawing (`"mimi"`) or one from its `art.py` (`"words-badge"`), drawn in a 100 × 100 box like the template's (the banner shows a game's own badge at 112 px, the kit's MeeMee at 104) |
| `say` | the line said when its place is tapped (its name), while its title banner shows: `"words-name"` |
| `scripts` | its code files, in loading order: `["game.js"]`; a data file goes first (below) |

Everything the game owns starts with its id: line ids `words-…`, screen ids `screen-words-…`, drawing names `words-…`, grown-ups tab ids `words-…`, its phase names. The build checks lines, screens and drawings. (MeeMee Rescue is older than this rule; don't copy its unprefixed names.)

### A data file (word lists and the like)

Data a grown-up edits without touching code (a phonics game's week-by-week word lists: MEEMEE.md, Rules) goes in a script of its own, listed first in `game.json`'s `scripts`, that sets one object on `window.MW` and does nothing else. MeeMee Rockets does this: `games/words/words.js` is

```js
/* MeeMee Rockets: the words. The one file to edit for a new half-term or term (no code changes). … */
(function () {
  'use strict';
  window.MW.wordsData = {
    harderTray: 10,
    start: { half: 'autumn-2', week: 1 },          // the half-term and week in play until a grown-up picks another
    terms: [
      { id: 'autumn', name: 'Autumn', all: 'All of autumn', halves: [
        { id: 'autumn-1', name: 'Autumn 1', weeks: [ { week: 1, tricky: ['go', …], other: ['feel', …] }, … ] },
        { id: 'autumn-2', name: 'Autumn 2', weeks: [ … ] } ] }
    ],
    sounds: { … },                                 // each tile's usual sound ('ie': 'igh', 'M': 'm')
    words: { … }                                   // every word once: its tiles, its own sounds, its spares
  };
})();
```

with `"scripts": ["words.js", "steps.js", "moments.js", "game.js"]`. Since 0.7.0 the file holds every half-term, and a grown-up picks the half-term and the week (MEEMEE.md, Rules): every name the Words tab shows ("Autumn 1", "Weeks 1–5", "All of autumn") comes from the file, so a new half-term or term is data only. `start` is only for a tablet with no choice saved (or one the file no longer has): changing it later doesn't move tablets that already have a choice saved, so for a new half-term a grown-up picks it in the Words tab on each tablet. A word has one entry in `words` and may be listed in several weeks and half-terms (one step wherever it is played; it is marked tricky only where the half-term in play lists it as tricky). Words and tiles may use capitals (Mr), each word's line id is in small letters (`words-w-mr`), and a tile that appears twice in a word can say a different sound each time (`these: { sounds: { e: ['ee', '-'] } }`). The comment at the top of `words.js` explains the rest. The game's own scripts load after it and read `MW.wordsData` (check it's there: `MW.wordsData || { terms: [], words: {} }`). Explain the file's format in a comment at its top, for whoever edits it next; check what's in it when the game loads and list any problems in the game's grown-ups tab rather than failing. The build checks it like any of the game's scripts (raw colours, sound, `</script>`). Name the object after the game (`MW.<id>Data`).

## Joining the world: `MW.world.game(def)`

Call it once, when the script loads:

```js
(function () {
  'use strict';
  const MW = window.MW, W = MW.world;
  W.game({
    id: 'words',
    build: build,            // once, when the page opens: make the screens (W.screen) and their buttons
    start: start,            // its place was tapped and its title banner has gone: show a screen, begin
    sections: [{ id: 'words-progress', title: 'Words', render: function (el) { /* grown-ups tab */ } }],
    onPause: function (why) { /* stop anything moving: cancel drags, clear timers */ },
    onResume: function () { /* carry on: usually say the current instruction again, if this game's screen is showing */ },
    onHome: function () { /* the player went home, from any screen: put things away, reset */ },
    init: function () { /* optional: after every game is built */ }
  });
  // ...
})();
```

`build` and `start` are required. The world calls `onPause`, `onResume` and `onHome` on every game, so check which screen is showing before acting (`MW.shell.screen`). A game does nothing for its title banner (below): `start` is called once it has gone. Don't change `W.st` in `onHome`: the world moves the token on before calling it and sets the phase to `'map'` after. If one of these calls throws, the world logs it (`game-error` in `MW.events`), shows it in the console (so the tests fail) and carries on with the other games; an error in `start` sends the player back to the map.

## The world: `MW.world`

| | |
|---|---|
| `W.screen(id, label)` | makes a screen (`<section class="mw-screen">`) and returns it; `id` is `screen-<gameid>-<name>`, `label` is read by screen readers |
| `MW.shell.show(id)` | shows that screen (and only it) |
| `W.home()` | back to the map. Use it as the Home button's action and at the end of a game. It moves the token on, stops speech and calls every game's `onHome` |
| `W.speak(lines, opts)` | says lines (below) once any pause is over; does nothing if the player has left meanwhile. Resolves `true` if they played to the end |
| `W.ok(token)` | waits while paused; `false` if the token has changed (the player left) |
| `W.st.token` | changes whenever the player leaves what they were doing. Read it before anything that waits, then check it after |
| `W.st.phase` | one phase for the page. The world uses `'idle'` (start screen), `'map'`, `'welcome'` (MeeMee World's banner on the map), `'opening'` (a game's banner) and `'crew'`; a game sets its own (`'words-asking'`, `'words-done'`) when it starts |
| `W.st.paused` | `true` while the grown-ups area is open, the tablet is upright or the screen is off |

The pattern for anything that waits:

```js
async function celebrate() {
  const token = W.st.token;
  MW.audio.sfx('chime');
  await W.speak([['words-well-done']]);
  if (!(await W.ok(token))) return;       // the player left (Home) while that played: stop here
  nextQuestion();
}
```

Timers too: `setTimeout(function () { if (token === W.st.token) ... }, ms)`.

### The map (the world's; a game does nothing)

Five places (decided 15 October 2026; design system, SolarMap): `0` the ringed mint planet, `1` the indigo planet, `2` the small peach planet, `3` a cluster of rocks at the bottom of the asteroid belt, `4` a space station on the outer orbit. A game takes the one its `game.json` names (`planet`); the world does the rest.
- A place with a game is drawn in full colour with a soft `mint` halo, and has its badge (`badge`, from `game.json`); tapping the place or its badge opens the game, with its title banner.
- A place with no game is dimmed (a planet to 45%, the rocks and the station to 62%) with a lock badge. Tapping it says "That place isn't ready yet." (`map-place-not-ready`). Had that line been pending, the world would say the older "That planet isn't ready yet." (`map-not-ready`) instead, so a tap is never silent: it checks `MW.audio.recorded` before the call (the line was recorded on 16 October 2026).
- Where each place is: `MW.LAYOUT.map.planets[i]` (`x`, `y` its middle, `tap` its tap area across, `badge` and `lock` boxes; the key keeps its old name), drawn from `design/gen_scenes.py`'s `MAP` (the same positions; `MAP["places"]` holds 3 and 4). The layout of existing places never moves; a sixth place needs a new map layout (MEEMEE.md, Open decisions).

### Title banners (the world's; a game does nothing)

The only words the child sees apart from numerals and the letters being practised (MEEMEE.md, Nothing to read; design system, TitleBanner). The world shows them; a game never adds words of its own.
- A banner shows only when its line is recorded (`MW.audio.recorded`), because it is always spoken with its name. While a game's name line is still pending, tapping its place starts the game straight away with no banner (as before 0.6.0); while `map-welcome` is, the map opens with no banner.
- **MeeMee World's**, once a visit: when the map first opens after Play, while "Welcome to MeeMee World!" (`map-welcome`) plays. The phase is `'welcome'` until it has gone; then the map is ready (and the cats hop if they have no jobs).
- **A game's**, when its place is tapped, while its name line (`say`) plays: its `name` and `badge` from `game.json`, so a new game gets its banner by itself. The phase is `'opening'`; the game's `start()` is called once the banner has gone.
- A banner stays for its line and at least 2 seconds (`W.BANNER.min`), then fades out (260 ms) by itself. It fades and grows in over 260 ms; with reduce motion it only fades. Taps under it do nothing (it covers the stage); the grown-ups lock still works above it.
- A pause (grown-ups area, tablet upright, screen off) or Home takes it away at once, and the player stays on the map (no game starts). `W.banner.up()` is `true` while one shows. Each logs `banner` events (`up <name>`, `going <name>`, `gone <name>`, `cancelled`).

When the game itself starts something new (another round from its end screen, a fresh question set), move the token on first so the old round's waits stop: `const token = ++W.st.token;` (MeeMee Rescue's `startRound` does this). The world does it for Home and for opening a game's place.

## Speech and sound: `MW.audio`

- `MW.audio.say(sentences, { onStart(timeline) })`: `sentences` is a list of sentences, each a list of line ids played back to back: `[['q-lets-make', 'num-end-7'], ['q-how-many-more']]`. A short gap goes between pieces and a longer one between sentences. It stops anything already being said. Resolves `true` when finished, `false` if cut short. `onStart` gets `[{ id, at, dur }]` (seconds from the start) for timing pictures to the voice (MeeMee Rescue's hint does this). In a game, use `W.speak`, which also waits out pauses.
- If any line in a `say` call isn't recorded yet, nothing in that call is said: it is logged as `audio-fail` and resolves `false` straight away, so the game works (silently) before Barney records it. Keep a line that might be pending in its own call if the rest should still be heard.
- `MW.audio.hush()` stops speech; `MW.audio.speaking()`; `MW.audio.lengthOf(sentences)` is the time in seconds.
- `MW.audio.recorded(id)`: `true` if the line is recorded (on the page), `false` while it is still pending. Use it to leave out something that only makes sense with its line (the world shows a title banner only when its line is recorded). `say` stops whatever is being said before it checks its lines, so when a line that may be pending must not cut anything off, check `MW.audio.recorded(id)` first and leave the call out until it is (MeeMee Rockets does this for its tile sounds: a sound still pending does nothing and stops nothing).
- `MW.audio.sfx(name)`: `pop`, `whoosh`, `chime`, `twinkle`, `tune` (design.md, Sound).
- Music is the kit's: a Music button on each screen turns it on and off, and it dips while a line is spoken.
- `MW.audio.unlock()` and `MW.shell.fullscreen()` are for a button the child taps to start; the world's Play button already does both.

## Voice lines

`lines.json`:

```json
{
  "about": "…",
  "lines": [
    { "id": "words-name", "group": "Map", "words": "MeeMee Words!", "how": "Announcing the game's name.", "pending": true },
    { "id": "words-find", "group": "Questions", "words": "Find the word…", "how": "Keep the voice up: a word follows.", "pending": true }
  ]
}
```

- `group` sorts the recording page; `how` tells Barney how to say it (lift for a piece mid-sentence, fall at the end).
- New lines are `"pending": true`. The recording page (`docs/record/index.html`, also online at /mimi-world/record/) lists every line under its game's name; Barney records each one there into `voice/` (one WAV per id). Then remove `pending` and run the full build, which turns the WAVs into web audio at one loudness. A line still pending stays off the game page, even if an older recording of it exists.
- A line whose words change keeps its id and is not marked pending: the old recording plays until Barney records over it. Tell him which lines to redo.
- The world's own lines (`kit/lines.json`) can be used by any game: `map-welcome`, `map-not-ready` ("That planet isn't ready yet."; the map no longer says it once `map-place-not-ready` is recorded, but it stays in use, because MeeMee Rockets says it when nothing in its chosen weeks is recorded, so never remove it as unused), `map-place-not-ready` ("That place isn't ready yet.", recorded 16 October 2026), the crew lines (`crew-jobs`, `crew-ready`, `name-moggles`, `name-snuffles`, `is-the`, `job-lookout`, `job-engineer`, `job-navigator`, `job-cook`). MeeMee Rescue's lines (numbers `num-mid-0`…`num-end-10`, `and`, `make`, praise, try-again) belong to it; to share one, ask Barney first.
- The build writes `voice/script.json` from all the `lines.json` files; don't edit it by hand.

## Buttons, taps and screens

- `MW.shell.buttons(screen, ['home', 'music', 'hear'], { home: W.home, hear: fn })` puts the standard buttons in their places and returns `{ home, music, hear }`. Every game screen has Home and Music; a screen where the child is asked something also has Hear-again.
- `MW.onTap(el, fn)`: a tap on a button (works straight after a drag, and from the keyboard). Use it instead of `click`.
- `MW.make(tag, classes, attrs, html)`, `MW.$(id)`, `MW.art(name)` (a copy of a drawing, as an `<svg>`; set its `width` and `height`), `MW.wait(ms)`, `MW.pick(list)`, `MW.shuffle(list)`, `MW.esc(text)`.
- Classes: `mw-abs` (absolutely placed: set `left` and `top` in stage px), `mw-layer mw-fill` (a full-stage layer that lets taps through), `mw-btn mw-btn--play` / `--main` / `--nav` (the kit's round buttons), `mw-pulse` (a slow pulse: the one way to say "tap here").
- Type styles are classes: `numeral-whole`, `equation`, `numeral-part`, `numeral-sign` (for the child: big, bold Andika), `banner` (the kit's title banners only), `title`, `button-label`, `body`, `label` (grown-ups).
- Every token is a CSS variable, for a game's own `game.css`: colours (`var(--moon)`, `var(--numeral)`, `var(--mint)`…), sizes (`--button-nav` 84px, `--button-main` 96px, `--button-play` 160px, `--mimi-size`, `--mimi-grab`, `--pill-height`), radii (`--radius-round`, `--radius-pill`, `--radius-panel`, `--radius-cell`), shadows (`--press-ink`, `--press-peach`, `--halo-mint` for "tap me", `--ring-success` for a right answer, `--lift` under something dragged) and opacities (`--opacity-locked`). Use these rather than writing a colour or shadow by hand: the build stops on raw colours, including inside `rgba()`.
- For example, a card with a word on it: `.words-card { background: var(--moon); color: var(--numeral); border: var(--rim) solid var(--mint); border-radius: var(--radius-pill); box-shadow: var(--press-ink); }` with the class `equation` for the word. (A new game's look comes from its mock-up round; this is a starting point.)

## Pieces on the stage

- `MW.pod(parent, x, y, w)`: Scruffles in the rescue ship, a button. `.face('thinking' | 'got-it' | 'try-again')`, `.celebrate()` (lights flash about 4 s), `.ready(on)` (lights glow steadily), `.lightsOff()`, `.el`. `MW.LAYOUT.pod` is its usual place.
- `MW.stars(parent, x, y, size)`: progress stars, the row's left edge at `x`; `.set(done, total)` (`total` defaults to 5). For rounds of other than five, centre the row on a point instead: `MW.stars(parent, MW.LAYOUT.stars.cx, MW.LAYOUT.stars.y, null, { centre: true })` keeps the row centred on 640 whatever `total` is (`size` defaults to 38; MeeMee Rockets' end screen uses `MW.stars(s, 640, 40, 60, { centre: true })`). Each `set()` places the row's left edge in px, so `stars.el.offsetLeft` is where the row starts on the stage (MeeMee Rescue's navigator moment reads it to point at a star).
- `MW.sparkles(parent, cx, cy, r)`: five sparkles round a point, gone by 1.2 s.
- `MW.counter(layer, { x, y, size, fixed })`: a MeeMee; `.moveTo(x, y, size, animate)`, `.remove()`, `.el`. `MW.pattern(n)` and `MW.layout(cx, cy, n, k)` give counting-pattern positions.
- `MW.dragger(screen, { counters: () => list, enabled: () => bool, onPick(c), onDrop(c, x, y, cancelled), grab })`: one-finger dragging of anything with `x`, `y` (its middle), `draggable`, `el`, `lift(on)` and `moveTo(x, y, size, animate)`. A thing is picked up within its own pick-up box if it has one, `c.grab = { w, h }` (stage px, centred on `x`, `y`), or else within the dragger's `grab` radius (60 px, for things drawn about 80 px). Give anything that isn't round a box: a tile `w` wide gets about `{ w: w + 20, h: its height + 40 }` (MeeMee Rockets' tiles; 10 px each side meets the next tile's box halfway across a 20 px gap, so a finger anywhere on a long tile picks that tile, never its neighbour). Where boxes overlap, the thing whose middle is nearest the finger is picked up. `onDrop` gets `cancelled` when the tablet took the touch away (or the kit let go of it): put the thing back. Returns `{ dragging(), cancel(), holding() }` (`holding()` is the thing held, or null); call `cancel()` in `onPause` and `onHome`. `MW.dragger.release(things)` lets go of any of `things` that any dragger is holding.
- `MW.ghosts(parent, positions)`: faint outlines showing where things go (hints); `.light(i)`, `.clear()`.
- MeeMee Rescue's own pieces (`MW.diagram`, `MW.tray`, `MW.equation`, and numbers mode's `MW.numberTrack` and `MW.numberedMimi`) are in the kit too; use them only for part–whole maths. A game can't add drawings to MeeMee Rescue's diagram, so they are the kit's. The number sentence has its own section below, with its minus form for subtraction (0.8.0).

### The number sentence: `MW.equation(parent)` (Equation card)

The sentence for part–whole maths, read aloud as it shows. Its numbers are in `moon`, `+`, `−` and `=` in `peach`, 22 px apart, in the `equation` type style (64 px). Create it once on the game's screen: `const e = MW.equation(screen)`.
- `e.show(a, b, w)`: MeeMee Rescue's "3 + 4 = 7" (part, part, whole), shown after a right answer, never as a question. `e.hide()` takes the sentence away. Both are as they were before 0.8.0.
- `e.minus(w, t, r, gap)` (0.8.0): "7 − 4 = 3": the whole, then the part going, then what is left. The minus is the minus sign (U+2212), never a hyphen. `gap` is `null` for the whole sentence, or `0`, `1` or `2` to put the gap ring in that number's place (`e.minus(7, 4, 3, 2)` is "7 − 4 = ○"): a tile-sized ring, 84 across, `moon-dim` with a 5 px dashed `mint` rim, where the answer goes. It shows at once, as `show` does.
- `e.fill(n)`: the gap's number has arrived (a tile was dropped on the ring, or in the diagram's empty circle): the ring becomes `n`. Nothing happens if there is no gap.
- `e.gap()`: the ring's box in stage px, `{ x, y, w, h }`, or `null` if there is no ring showing. Use it to see whether a tile was dropped on the ring. It gives the ring's place even while the sentence is still moving there.
- `e.at(place, animate)`: where the sentence sits. `'under'` is its usual place under the diagram (`MW.LAYOUT.equation`: left 180, top 700, 400 × 80), where it starts; `'ship'` is under Scruffles (`MW.LAYOUT.equationShip`: left 790, top 528, 440 × 100), clear of the number track. With `animate` it moves over 260 ms (the snap's ease-out); with reduce motion it fades in at its new place instead. Without, it is there at once. The sentence keeps its place until `at` is called again: after `at('ship')`, `show`, `minus` and `hide` don't move it back under the diagram, so a game calls `at('under')` itself.
- It logs `equation` events, which the tests read: `minus 7-4=?` (a `?` where the gap is), `fill 3`, `at ship`.
- Take MeeMee Home (`games/takehome/game.js`) is the game that uses the minus sentence: shown complete under the diagram after a right answer in step 1; in steps 2 and 3 waiting with its gap under Scruffles during the question (a tile dropped on `gap()` or in the empty circle goes in the circle and `fill`s the gap; taken out or replaced, `minus` with the gap again), then `at('under', true)` as the track slides away.

### Numbers mode's pieces (MeeMee Rescue; NumbersMode card)

- `MW.diagram(parent)` has two looks. `d.look('counting')` is the usual (numbers in the whole circle and the pills, "?" where the answer goes). `d.look('numbers')`: no pills and no "?"; `d.set(q)` puts a numbered MeeMee carrying its number in each given circle (the whole's drawn at 0.86 of a part's) and leaves the waiting circle empty and dashed. `d.carry(k, n, pop)` puts one carrying `n` in circle `k` (`'whole'`, `'left'`, `'right'`), or takes it away with `n` null (the hint brings the MeeMee back to count: take the given part's away, then lay counters with `d.slots`). `d.success(k, value)` gives the success ring and, in the numbers look, a numbered MeeMee pops up carrying the answer (260 ms, the snap's ease-out; a fade with reduce motion). `d.carried(k)` is what circle `k` holds, or null. `d.look()` says which look is on. The counting look is exactly as before.
- `MW.numberTrack(parent)`: the number track along the bottom, tiles 0 to 10 in order (`MW.LAYOUT.track`: x 128 + 94 × n, tops at 686), clear of the grown-ups lock. `.tiles` (or `.tile(n)`) are draggable things for `MW.dragger` (`counters: () => track.tiles`): each has `n`, `x`, `y`, `home`, `draggable`, `grab` (a 120 box), `lift(on)` (grows to 1.1, tilts and lifts), `moveTo(x, y, size, animate)`, `goHome(animate)` and `out()`. While a tile is away from its place, the place shows a dashed ring. The game decides what a drop does: put the tile in the waiting circle (`tile.moveTo(MW.LAYOUT.right.x, MW.LAYOUT.right.y, 0, true)`, `d.hit(x, y)` says which circle) or send it back (`tile.goHome(true)`). `.hide()` first lets go of a tile a finger is holding (`MW.dragger.release(track.tiles)`: its dragger's `onDrop` gets `cancelled`, as when the tablet takes a touch away), puts every tile back in its place at once, then slides the track down out of sight (260 ms; a fade with reduce motion), and its tiles can't be picked up until `.show()` brings it back; `.reset()` puts every tile back; `.away()` says whether it's hidden. It logs `track` events (`away`, `back`). Create it after the diagram, so a tile dropped in a circle shows above the circle.
- `MW.numberedMimi(k)`: one numbered MeeMee on its own (the diagram makes its own): `.place(cx, cy)` centres it on a point, `.show(n, pop)`, `.hide()`, `.shown()`, `.el`. `k` scales it (1 in a part circle, 0.86 in the whole).
- MeeMee Rescue's numbers mode (`games/rescue/rescue.js`) uses them: a grown-up picks it in Settings ("How your child answers", saved as the `answerMode` setting, `'numbers'` or `'counting'`), and a change starts with the next round. One dragger serves both ways (`counters: () => numbers ? track.tiles : MeeMee`); the track sits above the counters' layer, so a dropped tile shows over the circle and the hint's MeeMee, and the lookout peeks up from behind its right-hand end. Every answer is saved with its `mode`; one saved before 0.6.0 has none and counts as counting (`MW.bonds.ofMode`), and each way has its own secure, practising and not yet.
- Take MeeMee Home (`games/takehome/`, 0.8.0) uses them for subtraction: the counting look in step 1 (it sets the pills' text itself through `d.pills`, since the going-home pill keeps its number while its circle waits), the numbers look in steps 2 and 3 (in step 2 it takes the given circles' numbered MeeMee away with `d.carry(k, null)` and lays MeeMee counters with `d.slots`, so `d.success` still pops a numbered MeeMee up to carry the answer), and the track. Its right part is the MeeMee going home, its left part the MeeMee staying.

## The crew: `MW.crew`

`MW.crew.jobs()` (`{ moggles: 'lookout' | 'engineer' | 'navigator' | 'cook' | null, snuffles: … }`), `MW.crew.who(job)` (the cat with that job, or `null`), `MW.crew.ready()`, `MW.crew.cat(who, width)` (a cat drawing with `.setJob(job)` for its badge and `.hop(delay)`). The world owns the crew screen; a game may give a job a short wordless moment (see `games/rescue/moments.js`; MeeMee Rockets has its own, `games/words/moments.js`, on its own screens, and so does Take MeeMee Home, `games/takehome/moments.js`, at MeeMee Rescue's places on its own screen), never over the thing being worked on. The kit's moment styles in `kit.css` do the movement and its reduce-motion fade: `mw-moment` (an absolutely placed holder that taps pass through), `mw-peek` with an `mw-peek-inner` inside it (rises into a window), `mw-moment-pop` (pops up) and `mw-cook-pan` (grows in); add `is-shown` to show one and remove it to hide it. A game adds only what is its own, such as a cat facing the other way or a spanner turned as on its board.

## Saving: `MW.store`

`MW.store.game(id)` returns the game's own saved object (created empty the first time, and kept on the next save); change it, then call `MW.store.save()`. Use it only where the game changes something. To read without creating anything, use `MW.store.peek(id)`: the saved object, or an empty one if the game has saved nothing, so a tablet that has never played the game keeps nothing for it (MeeMee Rockets reads its answers and the half-term and week in play this way; its grown-ups tab too). Don't change what `peek` returns. `MW.store.clearGame(id)` forgets it (for the game's own "Clear this tablet's progress" button in its grown-ups tab; MeeMee Rescue's button clears only its own answers). It lives on the tablet only (browser storage can be cleared, so it's a convenience, not a record). Don't add settings at the top level (`MW.store.setting`): those are the world's and MeeMee Rescue's.

## The grown-ups area

Each entry in `sections` becomes a tab: `{ id: 'words-progress', title: 'Words', render(el) }`. `render` is called each time the tab opens; fill `el` with `MW.grownups.p(el, html, 'gu-lead' | 'gu-note')`, `.h3(el, text)`, `.row(el)`, `.btn(row, label, fn, 'gu-choice' | 'gu-quiet')`, `.table(el, rows)`. Grown-ups text is British English, sentence case, no exclamation marks. The world adds the Checks and Sound tabs itself.

Where a game's tabs sit: the games' tabs come first, game by game in the order of their places (place 0's first, then 1, and so on), each game's in the order of its `sections`; then the world's Checks and Sound. Today that is Progress and Settings (MeeMee Rescue, planet 0), Words (MeeMee Rockets, planet 1), Subtraction (Take MeeMee Home, planet 2), Checks, Sound. The area opens on the first tab (or the one last open).

## Drawings

`art.py` in the game's folder:

```python
from gen_art import tok, mimi, planet, star, spark   # design/gen_art.py's helpers

def templates():
    return {"words-badge": '<svg width="56" height="56" viewBox="0 0 100 100" aria-hidden="true">'
            + tok('<circle cx="50" cy="50" r="40" fill="@peach" stroke="@ink" stroke-width="5"/>') + '</svg>'}
```

Each drawing goes on the page as a template; `MW.art('words-badge')` returns a fresh copy. Colours are written `fill="@token"` and `stroke="@token"`; `tok()` turns them into classes and stops the build on a raw colour or an unknown token. Give clip paths, masks, gradients and other ids a unique name; `MW.art` renumbers them in each copy, with every `url(#…)` and `href="#…"` that points at them. The kit's own drawings include `mimi`, `pod`, `tray`, `spark`, `moggles`, `snuffles`, `icon-<home|hear|music|music-off|lock|play|full|tick>`, `job-<job>`, `badge-<job>`, and numbers mode's `numbered-mimi`, `number-tile` and `number-track` (their numbers go on top as text).

Sizing a copy: a drawing is an `<svg>` with `width`, `height` and a `viewBox` (the box its shapes are drawn in).
- **Another size, same picture:** set `width` and `height` (keep their ratio): `const b = MW.art('words-badge'); b.setAttribute('width', 112); b.setAttribute('height', 112);`.
- **A drawing that changes size per word** (a rocket hull as long as the word's portholes): draw the part that stretches as a plain shape in `art.py`, then set `width`, `height` and the `viewBox` together, so one unit in the viewBox stays one stage px and more or less of the drawing shows: `hull.setAttribute('width', L + 4); hull.setAttribute('height', H + 8); hull.setAttribute('viewBox', '-4 -4 ' + (L + 4) + ' ' + (H + 8));` (MeeMee Rockets' `makeShip`, with fixed-size ends from their own drawings). Give an `<svg>` that draws outside its box `overflow="visible"` in `art.py`.
- To scale a group of drawings together, wrap them in an element and scale that (`transform: scale(k)`), as MeeMee Rockets does when a long word's rocket would run off the stage.

## Motion and reduce motion

`MW.reduceMotion` is `true` when the tablet asks for less movement; the CSS media query `(prefers-reduced-motion: reduce)` does the same in styles. Use `mw-hop` for a bounce (`animation: mw-hop 420ms ease-out`) and turn it off under reduce motion. Repeating animations take at least a second per cycle (the build checks anything that repeats forever); only small lights may flash faster, up to 3 times a second, and only for a few seconds (MEEMEE.md).

## Logging and tests

- `MW.log(type, detail)` adds to `MW.events`, which the tests read (`say` entries are every line spoken). Log your game's main steps (`MW.log('words', 'asked here')`).
- `tools/tests/test_game.py` runs the page in Chromium at the Fire's size (1046 × 653 at 1.22×) and the Doogee's (1280 × 800 at 2×), with touches sent the way a finger would. Add an `async def test_<id>(p)` and call it from `main()`. Useful pieces: `open_tablet(p, name, vw, vh, dpr, extra_args=(), mode="auto")` returns `(browser, ctx, page, t, problems, requests)` (`mode` sets MeeMee Rescue's answer check; pass `mode=None` for another game; Rescue's numbers mode is `MW.store.setting('answerMode', 'numbers')`, and `MW.rescue.ask(q)` puts one question on the screen with nothing said); `t.tap(x, y)` and `t.drag(x0, y0, x1, y1)` in stage px; `t.said()` (every line spoken); `t.wait_screen(id)`; `t.wait_banner()`; `check(name, ok, detail)`; screenshots into `SHOTS`. Tap Play at `PLAY`, then `await t.wait_screen("screen-map")` (it also waits for MeeMee World's banner to go: taps under a banner do nothing), then your place at `MW.LAYOUT.map.planets[<planet>]` (x, y); your game starts once its own banner has gone, about 2.3 seconds later. End with a "no console errors" check (`problems`).
- Tests that reach a game's screens through its test hooks (`MW.wordsGame.showBuild(…)`) skip the banners; tests of the banners themselves are `test_banners` and `test_banner_motion`, of the kit's other 0.6.0 pieces `test_kit_pieces`, and of 0.8.0's map and number sentence `test_places`, `test_equation` and `test_equation_motion`. Take MeeMee Home's are the `test_takehome_…` checks; `MW.takehome.ask(q, step)` puts one of its questions on the screen with nothing said, and `MW.takehome.nextRound` sets the next round.
- `tools/tests/test_update.py` checks updates and offline (it needs a copy of `docs/` from commit beaf3b0, the phase 0 page); `tools/tests/test_build.py` checks the build's own checks. The tests pick free places themselves, so they keep working as games are added.
- `python tools/build.py --no-audio --out FOLDER --extra-game games/_template` builds a test copy with the starter game on the map (the template test does this).

## What the build checks

It stops with a list of problems if: a line has no recording and isn't pending; the page loads anything from outside; anything repeats faster than once a second; a page says a private name; a game's `game.json` or `lines.json` doesn't add up (id, planet: 0 to 4 and no other game's, badge, spoken name, scripts; every line's id, group, words and how); a game's lines, screens or drawings don't start with its id; a game's JS, CSS or `art.py` (in any subfolder too) sets a raw colour (a hex value, a colour function such as `rgb()`, or a colour name such as `white`, wherever a colour is being set; selectors such as `'#screen-words-play'` and comments are fine); a game's JS plays sound itself or contains `</script>`.
