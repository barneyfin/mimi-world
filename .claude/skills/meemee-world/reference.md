# MeeMee World kit reference (kit 0.5)

Everything a game needs, in the order you'll need it. `games/_template/` (the starter game, id `starter`) shows each part working; `games/rescue/` is the full example.

## The page

The build (`tools/build.py`) makes one page, `docs/index.html`, holding the kit and every game: the kit's scripts first (`KIT_JS` in build.py, `world.js` last), then each game's scripts in planet order, each game in its own `<script>` (so a mistake in one game's code leaves the world and the other games working). When the page has loaded, the world starts: it builds the start screen, the map (a planet for each game), the crew screen, then calls each game's `build()`, then shows the start screen. Everything is drawn on a 1280 × 800 stage (`MW.stage`, scaled to fit; `MW.stage.toStage(clientX, clientY)` turns a touch into stage px).

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
| `name` | its title, for the planet's label and the recording page: `"MeeMee Words"` |
| `planet` | which planet on the map is its: `0` ringed mint (MeeMee Rescue's), `1` indigo, `2` small peach |
| `badge` | the drawing on its planet's badge: a kit drawing (`"mimi"`) or one from its `art.py` (`"words-badge"`) |
| `say` | the line said when its planet is tapped (its name): `"words-name"` |
| `scripts` | its code files, in loading order: `["game.js"]` |

Everything the game owns starts with its id: line ids `words-…`, screen ids `screen-words-…`, drawing names `words-…`, grown-ups tab ids `words-…`, its phase names. The build checks lines, screens and drawings. (MeeMee Rescue is older than this rule; don't copy its unprefixed names.)

## Joining the world: `MW.world.game(def)`

Call it once, when the script loads:

```js
(function () {
  'use strict';
  const MW = window.MW, W = MW.world;
  W.game({
    id: 'words',
    build: build,            // once, when the page opens: make the screens (W.screen) and their buttons
    start: start,            // the planet was tapped and its name said: show a screen, begin
    sections: [{ id: 'words-progress', title: 'Words', render: function (el) { /* grown-ups tab */ } }],
    onPause: function (why) { /* stop anything moving: cancel drags, clear timers */ },
    onResume: function () { /* carry on: usually say the current instruction again, if this game's screen is showing */ },
    onHome: function () { /* the player went home, from any screen: put things away, reset */ },
    init: function () { /* optional: after every game is built */ }
  });
  // ...
})();
```

`build` and `start` are required. The world calls `onPause`, `onResume` and `onHome` on every game, so check which screen is showing before acting (`MW.shell.screen`). Don't change `W.st` in `onHome`: the world moves the token on before calling it and sets the phase to `'map'` after. If one of these calls throws, the world logs it (`game-error` in `MW.events`), shows it in the console (so the tests fail) and carries on with the other games; an error in `start` sends the player back to the map.

## The world: `MW.world`

| | |
|---|---|
| `W.screen(id, label)` | makes a screen (`<section class="mw-screen">`) and returns it; `id` is `screen-<gameid>-<name>`, `label` is read by screen readers |
| `MW.shell.show(id)` | shows that screen (and only it) |
| `W.home()` | back to the map. Use it as the Home button's action and at the end of a game. It moves the token on, stops speech and calls every game's `onHome` |
| `W.speak(lines, opts)` | says lines (below) once any pause is over; does nothing if the player has left meanwhile. Resolves `true` if they played to the end |
| `W.ok(token)` | waits while paused; `false` if the token has changed (the player left) |
| `W.st.token` | changes whenever the player leaves what they were doing. Read it before anything that waits, then check it after |
| `W.st.phase` | one phase for the page. The world uses `'idle'` (start screen), `'map'`, `'opening'` and `'crew'`; a game sets its own (`'words-asking'`, `'words-done'`) when it starts |
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

When the game itself starts something new (another round from its end screen, a fresh question set), move the token on first so the old round's waits stop: `const token = ++W.st.token;` (MeeMee Rescue's `startRound` does this). The world does it for Home and for opening a planet.

## Speech and sound: `MW.audio`

- `MW.audio.say(sentences, { onStart(timeline) })`: `sentences` is a list of sentences, each a list of line ids played back to back: `[['q-lets-make', 'num-end-7'], ['q-how-many-more']]`. A short gap goes between pieces and a longer one between sentences. It stops anything already being said. Resolves `true` when finished, `false` if cut short. `onStart` gets `[{ id, at, dur }]` (seconds from the start) for timing pictures to the voice (MeeMee Rescue's hint does this). In a game, use `W.speak`, which also waits out pauses.
- If any line in a `say` call isn't recorded yet, nothing in that call is said: it is logged as `audio-fail` and resolves `false` straight away, so the game works (silently) before Barney records it. Keep a line that might be pending in its own call if the rest should still be heard.
- `MW.audio.hush()` stops speech; `MW.audio.speaking()`; `MW.audio.lengthOf(sentences)` is the time in seconds.
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
- The world's own lines (`kit/lines.json`) can be used by any game: `map-welcome`, `map-not-ready`, the crew lines (`crew-jobs`, `crew-ready`, `name-moggles`, `name-snuffles`, `is-the`, `job-lookout`, `job-engineer`, `job-navigator`, `job-cook`). MeeMee Rescue's lines (numbers `num-mid-0`…`num-end-10`, `and`, `make`, praise, try-again) belong to it; to share one, ask Barney first.
- The build writes `voice/script.json` from all the `lines.json` files; don't edit it by hand.

## Buttons, taps and screens

- `MW.shell.buttons(screen, ['home', 'music', 'hear'], { home: W.home, hear: fn })` puts the standard buttons in their places and returns `{ home, music, hear }`. Every game screen has Home and Music; a screen where the child is asked something also has Hear-again.
- `MW.onTap(el, fn)`: a tap on a button (works straight after a drag, and from the keyboard). Use it instead of `click`.
- `MW.make(tag, classes, attrs, html)`, `MW.$(id)`, `MW.art(name)` (a copy of a drawing, as an `<svg>`; set its `width` and `height`), `MW.wait(ms)`, `MW.pick(list)`, `MW.shuffle(list)`, `MW.esc(text)`.
- Classes: `mw-abs` (absolutely placed: set `left` and `top` in stage px), `mw-layer mw-fill` (a full-stage layer that lets taps through), `mw-btn mw-btn--play` / `--main` / `--nav` (the kit's round buttons), `mw-pulse` (a slow pulse: the one way to say "tap here").
- Type styles are classes: `numeral-whole`, `equation`, `numeral-part` (for the child: big, bold Andika), `title`, `button-label`, `body`, `label` (grown-ups).
- Every token is a CSS variable, for a game's own `game.css`: colours (`var(--moon)`, `var(--numeral)`, `var(--mint)`…), sizes (`--button-nav` 84px, `--button-main` 96px, `--button-play` 160px, `--mimi-size`, `--mimi-grab`, `--pill-height`), radii (`--radius-round`, `--radius-pill`, `--radius-panel`, `--radius-cell`), shadows (`--press-ink`, `--press-peach`, `--halo-mint` for "tap me", `--ring-success` for a right answer, `--lift` under something dragged) and opacities (`--opacity-locked`). Use these rather than writing a colour or shadow by hand: the build stops on raw colours, including inside `rgba()`.
- For example, a card with a word on it: `.words-card { background: var(--moon); color: var(--numeral); border: var(--rim) solid var(--mint); border-radius: var(--radius-pill); box-shadow: var(--press-ink); }` with the class `equation` for the word. (A new game's look comes from its mock-up round; this is a starting point.)

## Pieces on the stage

- `MW.pod(parent, x, y, w)`: Scruffles in the rescue ship, a button. `.face('thinking' | 'got-it' | 'try-again')`, `.celebrate()` (lights flash about 4 s), `.ready(on)` (lights glow steadily), `.lightsOff()`, `.el`. `MW.LAYOUT.pod` is its usual place.
- `MW.stars(parent, x, y, size)`: progress stars; `.set(done, total)` (`total` defaults to 5).
- `MW.sparkles(parent, cx, cy, r)`: five sparkles round a point, gone by 1.2 s.
- `MW.counter(layer, { x, y, size, fixed })`: a MeeMee; `.moveTo(x, y, size, animate)`, `.remove()`, `.el`. `MW.pattern(n)` and `MW.layout(cx, cy, n, k)` give counting-pattern positions.
- `MW.dragger(screen, { counters: () => list, enabled: () => bool, onPick(c), onDrop(c, x, y, cancelled), grab })`: one-finger dragging of anything with `x`, `y` (its middle), `draggable`, `el`, `lift(on)` and `moveTo(x, y, size, animate)`. `grab` is the pick-up radius (60 px, for things drawn about 80 px). `onDrop` gets `cancelled` when the tablet took the touch away: put the thing back. Returns `{ dragging(), cancel() }`; call `cancel()` in `onPause` and `onHome`.
- `MW.ghosts(parent, positions)`: faint outlines showing where things go (hints); `.light(i)`, `.clear()`.
- MeeMee Rescue's own pieces (`MW.diagram`, `MW.tray`, `MW.equation`) are in the kit too; use them only for part–whole maths.

## The crew: `MW.crew`

`MW.crew.jobs()` (`{ moggles: 'lookout' | 'engineer' | 'navigator' | 'cook' | null, snuffles: … }`), `MW.crew.who(job)` (the cat with that job, or `null`), `MW.crew.ready()`, `MW.crew.cat(who, width)` (a cat drawing with `.setJob(job)` for its badge and `.hop(delay)`). The world owns the crew screen; a game may give a job a short wordless moment (see `games/rescue/moments.js`), never over the thing being worked on.

## Saving: `MW.store`

`MW.store.game(id)` returns the game's own saved object (created empty the first time); change it, then call `MW.store.save()`. `MW.store.clearGame(id)` forgets it (for the game's own "Clear this tablet's progress" button in its grown-ups tab; MeeMee Rescue's button clears only its own answers). It lives on the tablet only (browser storage can be cleared, so it's a convenience, not a record). Don't add settings at the top level (`MW.store.setting`): those are the world's and MeeMee Rescue's.

## The grown-ups area

Each entry in `sections` becomes a tab: `{ id: 'words-progress', title: 'Words', render(el) }`. `render` is called each time the tab opens; fill `el` with `MW.grownups.p(el, html, 'gu-lead' | 'gu-note')`, `.h3(el, text)`, `.row(el)`, `.btn(row, label, fn, 'gu-choice' | 'gu-quiet')`, `.table(el, rows)`. Grown-ups text is British English, sentence case, no exclamation marks. The world adds the Checks and Sound tabs itself.

## Drawings

`art.py` in the game's folder:

```python
from gen_art import tok, mimi, planet, star, spark   # design/gen_art.py's helpers

def templates():
    return {"words-badge": '<svg width="56" height="56" viewBox="0 0 100 100" aria-hidden="true">'
            + tok('<circle cx="50" cy="50" r="40" fill="@peach" stroke="@ink" stroke-width="5"/>') + '</svg>'}
```

Each drawing goes on the page as a template; `MW.art('words-badge')` returns a fresh copy. Colours are written `fill="@token"` and `stroke="@token"`; `tok()` turns them into classes and stops the build on a raw colour or an unknown token. Give clip paths, masks, gradients and other ids a unique name; `MW.art` renumbers them in each copy, with every `url(#…)` and `href="#…"` that points at them. The kit's own drawings include `mimi`, `pod`, `spark`, `moggles`, `snuffles`, `icon-<home|hear|music|music-off|lock|play|full|tick>`, `job-<job>`, `badge-<job>`.

## Motion and reduce motion

`MW.reduceMotion` is `true` when the tablet asks for less movement; the CSS media query `(prefers-reduced-motion: reduce)` does the same in styles. Use `mw-hop` for a bounce (`animation: mw-hop 420ms ease-out`) and turn it off under reduce motion. Repeating animations take at least a second per cycle (the build checks).

## Logging and tests

- `MW.log(type, detail)` adds to `MW.events`, which the tests read (`say` entries are every line spoken). Log your game's main steps (`MW.log('words', 'asked here')`).
- `tools/tests/test_game.py` runs the page in Chromium at the Fire's size (1046 × 653 at 1.22×) and the Doogee's (1280 × 800 at 2×), with touches sent the way a finger would. Add an `async def test_<id>(p)` and call it from `main()`. Useful pieces: `open_tablet(p, name, vw, vh, dpr, extra_args=(), mode="auto")` returns `(browser, ctx, page, t, problems, requests)` (`mode` sets MeeMee Rescue's answer check; pass `mode=None` for another game); `t.tap(x, y)` and `t.drag(x0, y0, x1, y1)` in stage px; `t.said()` (every line spoken); `t.wait_screen(id)`; `check(name, ok, detail)`; screenshots into `SHOTS`. Tap Play at `PLAY`, then your planet at `MW.LAYOUT.map.planets[<planet>]` (x, y). End with a "no console errors" check (`problems`).
- `tools/tests/test_update.py` checks updates and offline (it needs a copy of `docs/` from commit beaf3b0, the phase 0 page); `tools/tests/test_build.py` checks the build's own checks. The tests pick free planets themselves, so they keep working as games are added.
- `python tools/build.py --no-audio --out FOLDER --extra-game games/_template` builds a test copy with the starter game on the map (the template test does this).

## What the build checks

It stops with a list of problems if: a line has no recording and isn't pending; the page loads anything from outside; anything repeats faster than once a second; a page says a private name; a game's `game.json` or `lines.json` doesn't add up (id, planet, badge, spoken name, scripts; every line's id, group, words and how); a game's lines, screens or drawings don't start with its id; a game's JS, CSS or `art.py` (in any subfolder too) sets a raw colour (a hex value, a colour function such as `rgb()`, or a colour name such as `white`, wherever a colour is being set; selectors such as `'#screen-words-play'` and comments are fine); a game's JS plays sound itself or contains `</script>`.
