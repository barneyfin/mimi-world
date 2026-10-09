# Phase 3: code kit and trial round

Built overnight 8–9 October 2026. Version 0.3.0.

Agreed the night before: the page at the bookmark opens into a five-question trial round of Mimi Rescue, built only from the kit, so it could be tried with the player straight away. The kit's checks sit behind the grown-ups lock. The full game (solar-system map, crew jobs, progress grid, zero bonds) is still phase 4.

## What's in the kit (`kit/`)

| Piece | What it does |
| --- | --- |
| Stage (`core.js`) | Draws every screen on 1280×800 and scales it to fit: 0.82 on the Fire, 1.0 on the Doogee. Also the store for what each tablet remembers, and a tap helper that still works right after a drag. |
| Sound (`audio.js`) | Loads and decodes every sound before the first tap, then plays after it. Builds spoken lines from the recorded pieces. Effects. The music loops (the last 1.5 s of each copy fades while the next starts), sits 12 dB under the voice and dips a further 10 dB while a line is spoken. Sound pauses when the screen goes off. |
| Dragging (`drag.js`) | One finger at a time; the nearest Mimi to the finger is picked up from a 120 px grab circle; the counting patterns 1–10. |
| Screen pieces (`scene.js`) | The part–whole diagram (whole, two parts, lines, pills), the asteroid tray as a ten-frame, Scruffles's pod with three faces, progress stars, the equation, sparkles, hint ghosts. |
| Shell (`shell.js`) | Screens; full screen and landscape on the first tap; "turn the tablet sideways"; Home, Music and Hear-again buttons; the grown-ups lock (one finger held still for 3 s); the offline copy and updates. |
| Grown-ups area (`grownups.js`) | Checks (this tablet's results, like phase 0) and Sound (every clip, sample sentences, music loop and dip, effects). The game adds Progress and Settings. |
| Offline copy (`sw.template.js`) | Saves all 55 files. A new version is saved in the background and switches over at the start screen, never mid-round. A tablet still on the phase 0 test page moves to the game by itself. |

## The trial round (`games/rescue/`)

- Tap Play: full screen, sound on, "Ready for a rescue?", then five questions from wholes 2–10 (no zero bonds yet). About 3 in 4 ask for a missing part (left or right side), 1 in 4 for the whole.
- Missing part: "Let's make seven. We've got three. How many more?" Missing whole: "We've got three and four. How many altogether?"
- The player drags Mimi from the asteroid into the waiting circle; its pill counts them. A Mimi dropped anywhere else floats back to its spot.
- Right answer: the circle rings peach, sparkles, Scruffles's "got it" face, the chime, praise, then "Three and four make seven" with 3 + 4 = 7 on screen; the star turns peach; the Mimi fly into the pod.
- Wrong tries: Scruffles's "try again" face and "Let's try again"; after two, the counting-on hint ("Let's count on from three. Four, five, six, seven", with ghost Mimi lighting up in the circle) or, for a missing whole, "Count them with me" over every Mimi.
- After five: the crew screen, "You rescued all the Mimi!", the end tune, "Another rescue?" and a Play button.
- Grown-ups area › Progress lists every question answered on this tablet. Settings: the answer check (below), wholes in play, music.

## Checks run here

Headless Chromium at the Fire's page size (1046×653 at 1.22x) and the Doogee's (1280×800 at 2x), with touch input:

- `tools/tests/test_game.py`: 83 of 83 pass. A full round on each size, the wrong-drop path and hints, taking a Mimi back out, tap-Scruffles mode (too many, too few, hint, success), music dip and return, music off remembered, the grown-ups lock (quick tap, two fingers, sliding thumb, 3-second hold), screen off and back, Home mid-drag, an interrupted hint, offline reload with all sound, no outside requests, no console errors, portrait, reduce motion.
- `tools/tests/test_update.py`: 7 of 7 pass. Phase 0 test page → game with no second visit, newer version at the start screen, no reload mid-round, offline afterwards.
- A separate review of the code found five bugs, all fixed and covered by the tests above:
  - picked-up Mimi briefly vanished;
  - a quick two-finger touch could open the grown-ups area;
  - with the screen off, the game moved on silently;
  - a Mimi let go after Home or mid-celebration was still acted on;
  - an interrupted hint never came back.
- Build checks: every recording present, no outside addresses, no fast repeating animation, no child's name on the website.

## On the tablets (9 October, morning)

Barney committed and pushed at 07:10. By 07:41 both tablets were on 0.3.0; the Fire moved from the old test page to the game by itself.

| Check | Fire HD 8 (Silk 152, Kids profile, bookmark) | Doogee T30 Pro (Chrome 154, installed app) |
| --- | --- | --- |
| Page | 1046×653 at 1.22x, scale 0.82, Mimi 80 screen pixels | 1280×800 at 2x, scale 1.00, Mimi 160 screen pixels |
| Drag smoothness | 60 frames a second, slowest 20 ms, 0 slow of 20 | 59 frames a second, slowest 22 ms, 0 slow of 641 |
| Opens in | 0.4 s | 0.2 s |
| Sound | On (48 kHz), 50 of 50 files ready | On (48 kHz), 50 of 50 files ready |
| Full screen | Yes, locked to landscape | Yes (app), locked to landscape |
| Offline copy | Opened from the saved copy | Opened from the saved copy |
| Saving progress | Works | Works |

- **Voice (phase 2's gate):** clear on the Fire's speaker, and the built sentences sound like real sentences. Barney may re-record some lines with more expression.
- **The first trial:** the player worked out each question, sometimes with a little help, and never added Mimi at random.

**Status:** phases 2 and 3 pass their gates.

## Decisions from the trial (9 October)

1. **Answer check: switch to "tap Scruffles to check".** Needs one new recording, and the plan for when it plays is agreed before building.
2. **Music level:** about right; unchanged.
3. **Question mix:** keep about 1 in 4 asking for the whole.
4. **Sentence joins:** natural. Re-recording for more expression is optional.
5. **The child's name:** taken out of the repository files. The website check now reads its names from `tools/private-names.txt`, which stays on the PC and is never committed. Older commits still contain the name; removing it from history would mean rewriting it.

## 0.3.1 (9 October, evening)

- **New spelling: MeeMee.** The little cats are now spelt MeeMee, and the titles are MeeMee World and MeeMee Rescue. Changed wherever people read it: the game, the grown-ups area, the app's name, the recording page, the README and the setup guide. The design system and the PRD follow with the older look. Unchanged: the web address, the folder on the PC, names inside the code, saved progress and the recordings (the name sounds the same). The notes above are left as they were written. The Doogee may ask once to accept the app's new name.
- **The tap-Scruffles plan is signed off.** Its line, "Tap Scruffles when you're ready.", is now on the recording page, marked *pending*: the build leaves a pending line out of the game until it has been recorded. The game still checks as soon as the count is right; tap-Scruffles arrives in a later update with the recording.
- **The older look** (round 3 of the mock-ups) was chosen. It comes in the next update.
- Checks: `test_game.py` 83 of 83, `test_update.py` 7 of 7 (it now reads the version from the build instead of assuming 0.3.0).

