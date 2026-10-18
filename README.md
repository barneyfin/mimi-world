# MeeMee World

Maths and phonics games for a five-year-old, set in space with the family's three cats: Scruffles (the hero), Moggles and Snuffles. The MeeMee are the lost kittens they rescue.

- **MeeMee Rescue**: number bonds to 10 on the part–whole diagram. Play opens the MeeMee World map; the MeeMee Rescue planet starts a round of five questions chosen from the bonds that need work. The player answers by dragging MeeMee into the empty circle to count, or, in numbers mode (a grown-up's choice in Settings), by dragging a number tile from 0 to 10. On the crew screen the player gives Moggles and Snuffles their jobs (lookout, engineer, navigator, commander), and each job has a moment in a round. Grown-ups see which bonds are secure, for each way of answering.
- **MeeMee Rockets**: the class's tricky words and each week's other words, half-term by half-term (autumn 1 and autumn 2, weeks 1 to 5 of each). The indigo planet starts a round of five words: find each word among three rockets on the launch pad, then build it by dragging its tiles into the rocket's portholes (sound tiles, which say their sounds as they are picked up, then single letters, then harder letters); the built rocket launches with its lights chasing along the hull. Grown-ups pick the half-term and the week in play, all of that half-term's weeks ("Weeks 1–5") or the whole term ("All of autumn"), and see each word's step. The crew's jobs have their own moments here too.
- **Take MeeMee Home**: subtraction within 10 on the part–whole diagram, the sequel to MeeMee Rescue: Scruffles takes the rescued MeeMee home. The small peach planet starts a round of five questions in one of three steps, which a grown-up picks in the game's Subtraction tab: take away (drag the MeeMee going home out of the whole into their part, then tap Scruffles), how many are left (drag a number tile into the empty circle or the number sentence's gap) and numbers (numbered MeeMee, with the gap anywhere in the sentence). Every right answer shows and says the number sentence ("Seven take away four is three.") as the MeeMee going home hop off to their houses. Each step keeps its own progress, apart from MeeMee Rescue's. The crew's jobs have their moments here too.
- **MeeMee Station**: number bonds within 10 on the class's ten frame and bar model: the MeeMee come aboard a space station, which is itself the ten frame (ten windows, filling the top row first), with its long hull modules as the bar model. The map's space station starts a round of five questions in one of three steps, which a grown-up picks in the game's Station tab: bring them aboard (drag MeeMee from the landing deck onto the station until it holds the whole on its tower, then tap Scruffles), how many more (drag a number tile into the empty berth of the bar model under the station) and numbers (the bar model alone, the empty berth in any of its three places). Every right answer shows and says MeeMee Rescue's number sentence ("Three and four make seven."). Whichever cat is the commander stands by and smiles on each right answer. Each step keeps its own progress, apart from MeeMee Rescue's.

Live at https://barneyfin.github.io/mimi-world/ (the recording page is at /mimi-world/record/).

**The rules for every game are in [MEEMEE.md](MEEMEE.md).** Claude Code builds games with the `meemee-world` skill (`.claude/skills/meemee-world/`); `CLAUDE.md` points it there.

## What's where

| Path | What it is |
| --- | --- |
| `MEEMEE.md` | The rules for every MeeMee World game, and how a new one gets made. |
| `docs/` | The website that GitHub Pages publishes: one page with every game. **Built by `tools/build.py`: don't edit it by hand.** |
| `kit/` | The MeeMee World code kit. `world.js` is the world shell every game joins: the start screen, the home map (five places: three planets, a cluster of rocks and a space station; each game takes one), the title banners, the crew screen, pausing, the grown-ups area and updates. Also: stage and scaling, sound, dragging, the screen pieces, the offline copy, styles, the page template, the world's own voice lines (`lines.json`) and fonts (Andika, under the SIL Open Font Licence in `kit/Andika-OFL.txt`). |
| `games/<id>/` | One game: `game.json` (its name, its place on the map, badge and spoken name), `lines.json` (every line it says), its scripts, and optionally `art.py` and `game.css`. |
| `games/rescue/` | MeeMee Rescue: the bonds and how rounds are chosen (`bonds.js`), the crew's job moments (`moments.js`), and the game itself (`rescue.js`). The worked example for new games. |
| `games/words/` | MeeMee Rockets: the word lists with their tiles, tile sounds and spares (`words.js`, the one file to edit for a new half-term), each word's step and how rounds are chosen (`steps.js`), the crew's job moments (`moments.js`), the game (`game.js`), its drawings (`art.py`) and styles (`game.css`). |
| `games/station/` | MeeMee Station: the facts, how secure each is and how rounds are chosen (`facts.js`), the station and its hull modules (`draw.js`, the mock-up's approved drawing), the crew's job moments (`moments.js`), the game and its Station tab (`game.js`), its badge and window shutter (`art.py`) and styles (`game.css`). |
| `games/takehome/` | Take MeeMee Home: the subtraction facts, how secure each is and how rounds are chosen (`facts.js`), the crew's job moments (`moments.js`), the game and its Subtraction tab (`game.js`), its drawings (`art.py`: the home planet, its houses and the badge) and styles (`game.css`). |
| `games/_template/` | The starting point for a new game (a tiny "starter" game; the build skips it). |
| `design/` | The drawings and colours from the MeeMee World design system (`gen_art.py`, `gen_tokens.py`), and the scenes built from them (`gen_scenes.py`). |
| `voice/` | Barney's recordings (WAV, one per line). `script.json` lists every line of every game; the build writes it from the `lines.json` files. |
| `music/` | "Paws in the Milky Way", Barney's track, as made. The build makes the looping web copy. |
| `tools/` | The build and its checks, the audio maker, the recording page's template, and the tests. |
| `notes/` | Results of each phase's checks, `all-questions.md`: every question MeeMee Rescue can ask, `all-questions-words.md`: every question MeeMee Rockets can ask, `all-questions-takehome.md`: every question Take MeeMee Home can ask, step by step, and `all-questions-station.md`: every question MeeMee Station can ask, step by step (all made by the tests). |
| `.claude/skills/meemee-world/` | The Claude Code skill: rules and checklist, the look, and the kit's reference. |
| `SETUP-HOSTING.md` | Step-by-step: publish `docs/` with GitHub Pages and open it on both tablets. |

The plan (PRD) lives in Claude, in the "MeeMee World PRD — kit and MeeMee Rescue" doc. The look is defined in the MeeMee World design system: https://claude.ai/artifact/7u4TCYp4hQ3ia695MpegK7

## Building

Claude runs the build; you don't need to. It needs Python 3.10+, ffmpeg, and the packages numpy, scipy, pyloudnorm and playwright.

```
python tools/build.py              # everything: voice script, audio, pages, offline copy, icons, checks
python tools/build.py --no-audio   # reuse docs/audio as it is
python tools/tests/test_game.py    # the headless checks (Fire and Doogee screen sizes)
python tools/tests/test_build.py   # the build's own checks, each broken on purpose
```

The build stops if a line in any `lines.json` has no recording and isn't marked pending, if a page would load anything from outside the site, if anything repeats faster than once a second, if a page says a name listed in `tools/private-names.txt` (kept on the PC, never committed), or if a game breaks the rules a build can see (a raw colour, its own sound code, a `game.json` that doesn't add up, names without the game's id in front).

## Rules that already apply

The full list is in [MEEMEE.md](MEEMEE.md). In short:

- Played on two tablets, held sideways: Fire HD 8 Kids (Amazon Kids profile, opened from a bookmark) and Doogee T30 Pro. The first tap goes full screen.
- Everything is invented. No characters, pictures, sounds or fonts copied from shows, apps or school schemes.
- The website and this repository are public, so neither names the child who plays.
- Nothing leaves the tablet: no accounts, adverts, tracking or outside links.
- The whole screen never flashes, and nothing bigger than a character flashes more than 3 times a second.
- Every sound is at one loudness reference: voice clips match each other, effects sit a little under the voice, and the music sits well under both and dips while a line is spoken.
