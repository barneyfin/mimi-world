# Phase 3: code kit and trial round

Built overnight 8–9 October 2026. Version 0.3.0.

Agreed the night before: the page at the bookmark opens into a five-question trial round of Mimi Rescue, built only from the kit, so Eli can try it. The kit's checks sit behind the grown-ups lock. The full game (solar-system map, crew jobs, progress grid, zero bonds) is still phase 4.

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
- Eli drags Mimi from the asteroid into the waiting circle; its pill counts them. A Mimi dropped anywhere else floats back to its spot.
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

## Not checked here (needs the tablets)

- How the voice, effects and music sound on each speaker, and whether the music level is right.
- Touch feel and timing on the real hardware, especially the Fire.
- That the Fire's Kids browser moves from the old test page to the game by itself. If it doesn't, closing and reopening the bookmark does it.

## Open questions for Barney (phase 4)

1. **Answer check.** Now: as soon as the count is right (no explaining needed, but Eli never has to decide when to stop). The other option is in Settings: he taps Scruffles to check, which brings in "too many" and the hint after two wrong checks, and would need one new recording ("Tap Scruffles when you're ready"). Try both with Eli.
2. **Music level.** 12 dB under the voice, 22 dB under while a line is spoken. Louder or quieter?
3. **Question mix.** About 1 in 4 asks for the whole. Keep, or start with missing parts only?
4. **The sentence joins.** Do the built sentences sound natural, or should the num-mid pieces be re-recorded with more lift?
