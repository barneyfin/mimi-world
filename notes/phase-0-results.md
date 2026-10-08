# Phase 0 results: tablet test

Tested 8–9 October 2026 with the tablet test page (v0.1.0 to v0.1.2) at https://barneyfin.github.io/mimi-world/.

**Status:** both tablets passed every check. Phase 0 is complete.

## Fire HD 8 Kids (12th gen), Amazon Kids profile

| Check | Result |
| --- | --- |
| Browser | Silk 150.2.3 on Android 11 (Fire OS) |
| Screen | 1280×800 panel. Page area 1046×653 at 1.22x, so the 1280×800 stage is drawn at 0.82 scale. |
| Mimi size | 80 screen pixels, about 11 mm. Invisible grab area about 16 mm; drop circle about 34 mm. |
| Touch | 5 touch points, pointer events supported |
| Drag smoothness | 60 frames a second; slowest frame 17 ms; 0 slow frames out of 92 |
| Opens in | 0.7 s |
| Sound | Plays after a tap. The first chime was too quiet (made at half volume from low notes); fixed in v0.1.1. |
| Full screen | Works after a tap, and locks to landscape |
| Home-screen icon | Not offered by the Kids browser; a bookmark works instead |
| Offline | Opens from the bookmark with Wi-Fi off |
| Saving progress | Works |

## Doogee T30 Pro

| Check | Result |
| --- | --- |
| Browser | Chrome 154. It reports itself as a desktop browser ("not Android"), because Chrome shows large tablets the desktop version of websites. Mimi World doesn't depend on that. |
| Screen | Page area 1280×800 at 2x, so the stage is drawn at 1.0 scale. |
| Mimi size | 160 screen pixels, about 15 mm (275 pixels per inch). |
| Touch | 5 touch points, pointer events supported |
| Drag smoothness | 57 frames a second; slowest frame 34 ms; 0 slow frames out of 40 |
| Opens in | 1.9 s (well inside the 3-second target) |
| Sound | Plays after a tap |
| Full screen | Works after a tap, and locks to landscape |
| Home-screen icon | Installs as an app from Chrome, and opens full screen from its icon |
| Offline | Opens from the home-screen icon with Wi-Fi off |
| Saving progress | Works |

## Decisions that follow

- **Full screen on the first tap.** The Fire opens Mimi World from a bookmark, not an icon, so the first screen asks for full screen and landscape on Eli's first tap. Browsers only allow full screen after a tap. On the Doogee the installed app is already full screen, so the request does nothing there, harmlessly.
- **One layout for both.** Both tablets are 16:10 and show the whole 1280×800 stage: the Fire at 0.82 scale, the Doogee at 1.0.
- **Sizes stand.** The Fire, the smaller screen, gets 11 mm counters and a 16 mm grab area at the planned sizes. No need to enlarge them.
- **Every sound is normalised.** All sounds play at full, consistent loudness. Voice lines are brought to the same level in phase 2; the music sits well below them.
- **Updates reach a tablet the second time it opens Mimi World.** The offline copy fetches new files straight from the server, so an update pushed soon after a visit isn't saved with old files.
