# Phase 5 results: the skill, the docs and the rules

Phase 5 makes the kit ready for the next game to be built from a skill alone (criterion 9). Plan signed off 10 October (it is in the PRD). Barney's decisions that night: one page holds every game; one recording page, grouped by game; no throwaway test game, so the tricky-words game is the first real test of the skill; its first version starts with week 5's words.

## 0.5.0 (10 October): MeeMee World and its games, apart

Nothing changes for the child: MeeMee Rescue looks, sounds and plays exactly as in 0.4.1, and saved progress and crew jobs carry over.

- **The world shell** (`kit/world.js`) now holds what every game shares: the start screen, the home map, the crew screen, pausing (grown-ups area, tablet upright, screen off), the grown-ups area and Home. A game joins with one call, `MW.world.game({...})`, and the world never names a game.
- **A game is a folder** `games/<id>/`: `game.json` (its name, its planet, its badge, the line said when its planet is tapped, its scripts), `lines.json` (every line it says), its code, and optionally `art.py` (its drawings) and `game.css`. MeeMee Rescue is now built this way (`games/rescue/`).
- **The map** draws a planet for each game, lit with a halo and its badge; the others stay dimmed with a lock. With only MeeMee Rescue, the drawing is byte-for-byte the same as before.
- **Voice lines** live with their owners: `kit/lines.json` (the map and the crew) and each game's `lines.json`. The build writes `voice/script.json` from them, and the recording page shows each game's lines under the game's name.
- **Saved data:** a newer game keeps its own (`MW.store.game(id)`), beside MeeMee Rescue's answers and the world's settings.
- **Robustness:** each game runs in its own `<script>`, and the world catches anything a game throws, so one game going wrong leaves the others working. A line that hasn't been recorded yet is skipped quietly instead of being fetched. A line marked pending stays off the page even if an older recording exists.
- **The page template** moved from `games/rescue/` to `kit/page.template.html`.

## The build's new checks

The build now also stops on: a raw colour in a game (a hex value, a colour function or a colour name wherever a colour is set; selectors and comments are fine); a game playing sound itself; `</script>` in a game's code; a `game.json` or `lines.json` that doesn't add up; lines, screens or drawings without the game's id in front; and repeating animations written the long way. `tools/tests/test_build.py` breaks each rule on purpose and checks the build says so, and checks that things which only look like colours (`'#screen-words-play'`, `'#bead'`, a comment about `rgba()`) pass.

## Rules, skill and template

- **`MEEMEE.md`**: the rules for every MeeMee World game, modelled on the arcade's ARCADE.md and adapted for a five-year-old on a tablet: touch only, nothing to read, every word in Barney's voice, nothing that punishes, the class's way, no names in public, the kit's look and sound, offline, safety. Also how a new game gets made, and the open decisions that are Barney's.
- **`CLAUDE.md`**: a short pointer for Claude Code.
- **The `meemee-world` skill** (`.claude/skills/meemee-world/`): `SKILL.md` (making and changing a game, the rules, a checklist, telling Barney), `design.md` (the look and the words), `reference.md` (how a game joins, the kit's functions, voice lines, drawings, saving, the grown-ups area, tests and what the build checks).
- **`games/_template/`**: a tiny "starter" game (tap the star three times) showing every part a game needs. The build skips it; the tests build it into a test copy of the page.

## Checks

- **The split changed nothing:** all 236 checks from 0.4.1 passed against the split before any test was touched.
- **Tests made ready for more games:** the map test now finds an empty planet itself instead of assuming planets 1 and 2 are empty, so adding the tricky-words game won't break it.
- **New tests:** a tablet's saved data from 0.4.1 carries over (music, answer check, wholes, crew jobs, answers, secure bonds); the starter game builds into a test copy, takes a free planet, opens, plays, saves, goes home and shows its grown-ups tab, beside MeeMee Rescue.
- **Totals:** `test_game.py` 249 of 249; `test_build.py` 27 of 27; `test_update.py` 7 of 7.
- **Review:** an independent review found the split faithful. It found, and these were fixed:
  - Three tests assumed planets 1 and 2 would stay empty.
  - The docs misdescribed pending lines.
  - One failing game could stop the others.
  - The colour check had false alarms (selectors such as `#add-card`) and gaps (colour names, `oklch()`, subfolders).
  - A rename instruction for the template would have broken its drawings. The template's id is now `starter`.
  - Some smaller points in the docs.
- **To check on the tablets:** 0.5.0 is held back until the child's solo-round check on 0.4.1 is done; after the push, one round of MeeMee Rescue on each tablet confirms nothing changed.
