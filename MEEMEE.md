# MeeMee World

Barney's maths and phonics games for a five-year-old, set in space with the family's three cats. MeeMee World is the set; each game takes a place on its home map. MeeMee Rescue (number bonds to 10) is the first game and the worked example for every game after it.

This file holds the rules for every MeeMee World game. MeeMee World is a sibling of Barney's browser arcade, not part of it: it takes the arcade's way of working and its safety rules (ARCADE.md, in the Retro Games folder) and adapts them for a young child on a tablet. The kit's own docs (`README.md`, `CLAUDE.md` and the skill in `.claude/skills/meemee-world/`) add to these rules and never loosen them. If the two disagree, stop and ask Barney which wins. These rules change only when Barney decides.

## What MeeMee World is made of

1. **A design system**: the MeeMee World Design System artifact (https://claude.ai/artifact/7u4TCYp4hQ3ia695MpegK7) holds the colour tokens, type, sizes, characters, components and the rules for motion and sound. It is the spec. Change it first, then the code, so the two never drift apart.
2. **A code kit** (`kit/`): the world shell (start screen, home map, crew screen, pausing, grown-ups area, updates), the stage and scaling, sound, dragging, the screen pieces, the offline copy, the fonts, and the page template. `design/` holds the drawings and colours, from the design system.
3. **Games** (`games/<id>/`): each game is a folder with `game.json`, `lines.json` and its scripts. It joins the world by itself; the kit never names a game. `games/_template/` is the starting point for a new one.
4. **Voice** (`voice/`): Barney's recordings, one WAV per line, recorded on the recording page.
5. **A build and tests** (`tools/`): `tools/build.py` turns everything into one web page in `docs/` (published by GitHub Pages) and stops on anything that breaks these rules; `tools/tests/` checks the page headlessly at both tablets' screen sizes.
6. **A Claude Code skill** (`.claude/skills/meemee-world/`): `SKILL.md` (rules and checklist), `design.md` (the look) and `reference.md` (the kit's functions and how a game joins). A fresh Claude with only the skill must be able to build a correct game.

One page holds every game (decided 10 October 2026): one bookmark, one approval on the Fire's Kids profile, one offline copy, and the crew and progress shared across games.

## Rules for every game

- **The player is five.** Two tablets, always held sideways: a Fire HD 8 Kids (opened from a bookmark in an Amazon Kids profile) and a Doogee T30 Pro. Touch only: tap and drag, one finger at a time. Played alone or with a parent.
- **Nothing to read.** The only text on a game screen is numerals and, in a phonics game, the letters and words being practised. A title banner may show the set's or a game's name, always spoken with it (decided 10 October 2026). Every instruction is spoken, and Hear-again repeats it.
- **Every word is Barney's voice.** Each line is a recording listed in a `lines.json`; there is no synthetic speech. Sentences are built from pieces where that saves recording ("Moggles… is the… lookout."). A new line is marked pending until it is recorded, and the game skips it till then.
- **Nothing punishes.** No timers, lives, scores or losing. A wrong answer is a try: a calm line ("Let's try again."), then a hint after the second try. No red, no buzzer.
- **The class's way.** Words, diagrams, letter shapes and number sentences match how the child's class teaches them. Check against a homework sheet before calling a game done.
- **Word lists in a data file.** A phonics game keeps its word lists in a data file in its own folder. The file holds every half-term, and a grown-up picks the half-term and the week, so a new half-term means editing that file and recording the new words, with no code change. Letters are shown in Andika, the kit's typeface, checked against the child's reading book (both decided 10 October 2026).
- **No names in public.** The website and this repository are public, so neither ever names the child: not in a recording, a page, a file or a commit message. The build checks the pages against `tools/private-names.txt`, which stays on the PC and out of git.
- **Invented names and art.** Scruffles, Moggles and Snuffles are the family's own cats; the MeeMee, the planets and the games are invented. Nothing from films, shows, apps or school schemes, and no character gets a helmet, hood, cloak or armour. If a drawing starts to resemble a famous character, change it.
- **The kit's look.** Every colour is a token from the design system (no raw colours in a game; the build checks). Drawings are flat shapes with outlines, in the design system's style. Sound goes only through the kit (`MW.audio`), so every sound is at one loudness and the music dips under speech.
- **Offline, nothing leaves the tablet.** No outside addresses, accounts, adverts or tracking. The page works with Wi-Fi off after the first visit.
- **Safety and accessibility.** The whole screen never flashes; nothing bigger than a character flashes more than 3 times a second; small lights may flash up to 3 times a second, and anything else that repeats takes at least a second (decided 10 October 2026); the reduce-motion setting is honoured. Grown-ups text has at least 4.5:1 contrast.
- **The grown-ups area** sits behind the lock (hold for 3 seconds), so the child can't open it by accident. Each game can add a tab there. Progress is kept on each tablet.
- **Games use the kit and never edit it.** If the kit lacks something a game needs, finish the game without it and tell Barney what the kit should gain. Changing the kit is its own job, done only when Barney asks; afterwards every game is rebuilt and retested.
- **Done means:** it builds with no problems, both test suites pass (with checks for the new game's main path), the console is clean, and it has been played on both tablets.

## How a new game gets made

1. **Interview first.** What it teaches, how the class teaches it (bring a homework sheet), the words and sounds involved, and what will make the child want to play it. Ask; don't fill gaps with assumptions.
2. **Mock it up.** A round on the design canvas showing the game's screens in the MeeMee World look. Barney picks and refines until he says it's right. New drawings go into the design system.
3. **Write a short PRD**: problem, success criteria, scope and what's out of scope, constraints, a phased plan, open questions. Nothing is built until Barney explicitly approves it.
4. **Lines first.** Put every line in the game's `lines.json` as pending, so Barney can record them on the recording page while the game is built.
5. **Build from the skill**, in phases, with a review after each. Say what was checked and what couldn't be.
6. **Check with the child** on both tablets, and against the class's homework.
7. **Commit at the end of each phase.** Git is Barney's: he runs the commands.

## Open decisions

These are Barney's to decide. Raise them when they become relevant; don't settle them alone.

- **More than five places.** The map has five places: three planets, a cluster of rocks in the asteroid belt and a space station (decided 15 October 2026). A game takes one; the rest stay locked and say so when tapped. A sixth needs a new map layout.
- **Progress across tablets.** Kept separately on each tablet for now; sharing it would need an account or a sync, which the "nothing leaves the tablet" rule rules out today.
