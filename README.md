# Mimi World

Maths and phonics games for a five-year-old, set in space with the family's three cats: Scruffles (the hero), Moggles and Snuffles. The Mimi are the lost kittens they rescue.

- **Mimi Rescue** (in progress): number bonds to 10 on the part–whole diagram. A five-question trial round is live; the full game comes in phase 4.
- Tricky-words game: next.

Live at https://barneyfin.github.io/mimi-world/ (the recording page is at /mimi-world/record/).

## What's where

| Path | What it is |
| --- | --- |
| `docs/` | The website that GitHub Pages publishes. **Built by `tools/build.py`: don't edit it by hand.** |
| `kit/` | The Mimi World code kit: stage and scaling, sound, dragging, the part–whole diagram and other screen pieces, the shell (screens, full screen, buttons, grown-ups lock), the grown-ups area, the offline copy, styles and fonts (Andika, under the SIL Open Font Licence in `kit/Andika-OFL.txt`). |
| `games/rescue/` | Mimi Rescue: the page template and the game itself. |
| `design/` | The drawings and colours from the Mimi World design system (`gen_art.py`, `gen_tokens.py`), and the scenes built from them (`gen_scenes.py`). |
| `voice/` | Barney's recordings (WAV) and the script they follow. |
| `music/` | "Paws in the Milky Way", Barney's track, as made. The build makes the looping web copy. |
| `tools/` | The build, the audio maker, the recording page's template, and the tests. |
| `notes/` | Results of each phase's checks. |
| `SETUP-HOSTING.md` | Step-by-step: publish `docs/` with GitHub Pages and open it on both tablets. |

The plan (PRD) lives in Claude, in the "Mimi World PRD — kit and Mimi Rescue" doc. The look is defined in the Mimi World design system: https://claude.ai/artifact/7u4TCYp4hQ3ia695MpegK7

## Building

Claude runs the build; you don't need to. It needs Python 3.10+, ffmpeg, and the packages numpy, scipy, pyloudnorm and playwright.

```
python tools/build.py              # everything: audio, pages, offline copy, icons, checks
python tools/build.py --no-audio   # reuse docs/audio as it is
python tools/tests/test_game.py    # the headless checks (Fire and Doogee screen sizes)
```

The build stops if a recording in `voice/script.json` is missing, if a page would load anything from outside the site, if anything repeats faster than once a second, or if a page says a name listed in `tools/private-names.txt` (kept on the PC, never committed).

## Rules that already apply

- Played on two tablets, held sideways: Fire HD 8 Kids (Amazon Kids profile, opened from a bookmark) and Doogee T30 Pro. The first tap goes full screen.
- Everything is invented. No characters, pictures, sounds or fonts copied from shows, apps or school schemes.
- The website and this repository are public, so neither names the child who plays.
- Nothing leaves the tablet: no accounts, adverts, tracking or outside links.
- The whole screen never flashes, and nothing bigger than a character flashes more than 3 times a second.
- Every sound is at one loudness reference: voice clips match each other, effects sit a little under the voice, and the music sits well under both and dips while a line is spoken.
