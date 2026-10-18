---
name: meemee-world
description: Make, change or fix a MeeMee World game (the tablet maths and phonics games for a five-year-old in this folder) using the MeeMee World kit, the world shell (home map, crew, grown-ups area), Barney's recorded voice lines, the night-sky look and the one-page build. Use for every game request here, e.g. "make the tricky-words game", "add a hint", "the round is too long", "add a line for Scruffles to say".
---

# MeeMee World

Every game in this folder is built on the MeeMee World kit (`kit/`). The kit already provides everything games share: the start screen (sound and full screen start on the first tap), the home map where each game takes one of five places (three planets, a cluster of rocks and a space station; a place with no game says so when tapped), the title banners (MeeMee World's name after Play, each game's name and badge as its place is tapped, taken from its `game.json`), the crew screen, pausing (grown-ups area open, tablet upright, screen off), the grown-ups area and its lock, the voice and music players, dragging, Scruffles's ship, progress stars, sparkles, saving, the offline copy and updates. A game supplies only its own play, its own lines and its own drawings. Never rebuild what the kit does.

Read `MEEMEE.md` (in the folder root) first: it holds the rules every game follows. Then, before writing any code, read both files beside this one:
- [reference.md](reference.md): how a game joins the world, the kit's functions, the voice lines, the build and the tests.
- [design.md](design.md): the look and the words: colours, layout, characters, motion, what Scruffles says and how.

For a finished example, read `games/rescue/` (MeeMee Rescue: number bonds on the part–whole diagram; `rescue.js` shows a full round, hints, celebrations, grown-ups tabs, and a second way of answering, numbers mode, chosen in Settings, with its own progress). `games/takehome/` (Take MeeMee Home, subtraction) is the newest game on the same diagram: three steps a grown-up picks, each with its own progress, and the minus sentence. Start a new game from `games/_template/`, which is small and shows every part a game needs. Learn from their structure; do not copy MeeMee Rescue's play, lines or art into another game.

## Folder

```
Mimi World/                (the folder keeps the old spelling; the set is spelt MeeMee World)
  MEEMEE.md                the rules for every game
  kit/                     shared: world.js, the shell, sound, dragging, screen pieces, kit.css, page.template.html,
                           lines.json (the world's own lines). Never edit for one game.
  design/                  the drawings (gen_art.py, gen_scenes.py) and colour tokens (gen_tokens.py). Never edit for one game.
  games/<id>/              one game: game.json, lines.json, its scripts, and optionally art.py and game.css
  games/_template/         the starting point for a new game (the build skips folders starting with "_")
  voice/<line-id>.wav      Barney's recordings; voice/script.json is written by the build
  docs/                    the built website (GitHub Pages). Generated: never edit by hand.
  tools/build.py           the build and its checks; tools/tests/ the headless checks
```

## Making a new game

1. **Agree it first.** A new game needs a PRD that Barney has approved (MEEMEE.md, "How a new game gets made"). If there isn't one, stop and ask.
2. **Name it.** An invented title in the MeeMee World style ("MeeMee Rescue"), and a short lower-case id ("words"). The id goes in front of everything the game owns: its line ids (`words-…`), screen ids (`screen-words-…`), drawing names (`words-…`), grown-ups tab ids and saved data.
3. **Copy** `games/_template/` to `games/<id>/`. The template's id is `starter`: change every `starter` in every file (`game.json`, `lines.json`, `game.js`, `art.py`, `game.css`) to the new id, and its name "Starter game" to the new title. Pick a free place on the map for `planet` in `game.json` (0 to 4, reference.md; 0 is MeeMee Rescue's, 1 MeeMee Rockets', 2 Take MeeMee Home's and 4 MeeMee Station's, and the build stops if two games share one). Then replace the starter's placeholder play (tap the star three times) with the real game.
4. **Write the lines** in `lines.json`, all `"pending": true`, before the code (reference.md, Voice lines). Keep them short, warm and in the class's words (design.md, Words).
5. **Write the game** in its own scripts, joined to the world with `MW.world.game({...})`. Use the kit for screens, buttons, speech, dragging, saving and the grown-ups tab.
6. **Draw** anything new in `art.py` with colour tokens only, in the design system's style (design.md). New drawings should go into the design system too: tell Barney.
7. **Test.** Add checks for the game's main path to `tools/tests/test_game.py` (reference.md, Tests). Build and run both suites (below).
8. **Check** everything on the checklist, then tell Barney (below).

Leave the version alone: the page's version (`VERSION` in `tools/build.py`) is Barney's, set for each release. A new game, or a change to one, doesn't change it.

## Reading the mock-up boards

A game's look comes from its mock-up round on the design canvas, given to you as boards (pictures, often with their HTML) and the design system's cards.
- **Boards drawn as HTML on the 1280 × 800 stage** (a `.dc.html` whose new parts are absolutely placed elements): their HTML gives every position and size in stage px (`left`, `top`, `width`, `height`; or the script that drew them). Take the numbers from there, not from the picture.
- **Screenshot boards** (a picture of the real page with the change painted in) give no positions: keep the existing layout, and take any new positions from the design system's card for the piece. Don't measure the picture.
- If a position you need is in neither, ask Barney rather than guess.

## Changing an existing game

Read the game's folder first, change only what was asked, rebuild and run the test suites. If a line's words change, keep its id and tell Barney to record it again (the old recording plays until he does); a new line is pending. Never edit `docs/` files.

## Build and test

From the MeeMee World folder (Barney's PC: use the full Python path from CLAUDE.md):

```
python tools/build.py --no-audio            # quick: the page, using the audio already in docs/audio
python tools/build.py                       # full: also turns new recordings into web audio (needs ffmpeg)
python tools/tests/test_game.py             # the headless checks at both tablets' sizes
python tools/tests/test_update.py PHASE0    # how updates reach a tablet. PHASE0 is docs/ as at commit beaf3b0:
                                            #   git archive --format=zip -o ../phase0.zip beaf3b0 docs (only reads
                                            #   the repository), unzip it outside this folder, pass its docs folder
python tools/tests/test_build.py            # the build's own checks
```

## Rules that are not optional

- **Nothing to read, everything spoken.** No words on a game screen except numerals and the letters or words being practised. The one exception is the kit's title banner, which shows the set's or a game's name while it is spoken (MEEMEE.md); the kit shows it from `game.json`, and a game never adds words of its own. Every instruction is a line in `lines.json`, in Barney's voice; Hear-again repeats the current one.
- **No timers, lives, scores or losing.** A wrong answer gets a calm line; the second gets a hint. No red, no buzzer, no sad faces.
- **Join the world; don't rebuild it.** A game never makes its own start screen, map, Home behaviour, pause handling or grown-ups lock. Home is `MW.world.home`; pausing comes to the game through `onPause` and `onResume`.
- **Respect the world's token.** Anything that waits (speech, a timer, a celebration) checks the token it started with (`MW.world.ok(token)`), so nothing happens after the player has left.
- **Colour tokens only.** In JS, CSS and drawings: token classes (`f-mint`, `s-ink`), `var(--token)`, or `@token` in `art.py`. Never a hex value, `rgb()` or a colour name. The build stops on raw colours.
- **Sound only through the kit.** `MW.world.speak` / `MW.audio.say` for lines, `MW.audio.sfx` for effects. Never `AudioContext`, `<audio>` or speech synthesis. The build stops on them.
- **Big, forgiving targets.** Anything tapped or dragged is at least 84 stage px (120 px grab area for things that are dragged), at least 24 px from the edge, and away from the grown-ups lock (bottom left).
- **Safe motion.** Nothing bigger than a character flashes more than 3 times a second; small lights may flash up to 3 times a second, and anything else that repeats over and over takes at least a second for each repeat (a one-off movement, such as the MeeMee hopping home, isn't a repeat); the whole screen never flashes. With reduce motion, movement becomes a fade or an instant change.
- **Names.** Invented names and art; no character from films, shows or apps; no helmet, hood, cloak or armour on anyone. Never the child's name, anywhere in the folder.
- **Don't change `kit/` or `design/`** to make one game work. If the kit lacks something, finish the game without it and tell Barney what the kit should gain.
- **Read saved data without creating it.** `MW.store.peek(id)` reads; `MW.store.game(id)` is only for changing it (it creates the game's entry).

## Checklist before saying a game is done

- [ ] `python tools/build.py --no-audio` ends with the "MeeMee World …" line and no "Build checks failed".
- [ ] The test suites pass, including new checks for this game's main path, and the console has no errors or warnings.
- [ ] Every line the game says is in its `lines.json`; new ones are pending, and you have listed them for Barney to record.
- [ ] Every id the game owns starts with its own id (lines, screens, drawings, grown-ups tabs, saved data).
- [ ] Hear-again repeats the current instruction; Home works from every screen; pausing mid-round and coming back carries on sensibly.
- [ ] It looks right at both sizes: take screenshots at 1046 × 653 (Fire) and 1280 × 800 (Doogee) and look at them.
- [ ] Nothing for the child to read; nothing punishes; no raw colours; nothing flashes fast; reduce motion works.

## Telling Barney

Barney is learning to build software. Say what you made and why in plain words, in a few lines: the game in one sentence, how it plays, the lines he needs to record (on the recording page, under the game's name), what to try on each tablet, and anything you could not test. No jargon without a short explanation. Git is his: give him the commands (CLAUDE.md).
