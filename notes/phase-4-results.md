# Phase 4 results: the full MeeMee Rescue

Phase 4 turns the trial round into the full game, in two releases (plan signed off 9 October; it is in the PRD).

## Before the build (9 October, evening)

- The nine crew lines went on the recording page as *pending*, and Barney recorded them the same evening.
- Round 4 of the design canvas mocked up the crew screen, the four job badges on the map and the job moments in a round. Barney approved it that evening; it is built in 0.4.1.

## 0.4.0 (9 October, night): the map, rounds that follow progress, zero bonds, the progress grid

- **The map.** Play now opens the home map: an alien solar system with a peach sun, dashed orbits and an asteroid belt. MeeMee Rescue is the ringed mint planet with a MeeMee badge; Scruffles's ship is parked by it with Moggles and Snuffles; two dimmed planets with locks wait for later games. The first visit says "Welcome to MeeMee World!". Tapping the planet (or its badge) says "MeeMee Rescue!" and starts a round; a locked planet says "That planet isn't ready yet." The map has the music button and the grown-ups lock, and no Home button. Home in a round, or on the end screen, goes back to the map. The start screen's title is now MeeMee World.
- **Rounds that follow progress.** Each round of five has 1 or 2 bonds he is secure on and 3 or 4 that need work (practising or not met yet). If there aren't enough of one kind, the other fills in. A bond is never asked twice in a round when there are enough to choose from; at most two bonds come from one whole, and the same whole isn't asked twice in a row. About 1 in 4 questions still asks for the whole.
- **Secure.** A bond (3 and 4, either way round) is secure once it is right first time (no wrong check, no hint) on three different days. A wrong answer moves it back to practising and its three days start again. The answers saved on each tablet since 9 October count.
- **Zero bonds.** A whole's zero bond (5 and 0) joins the rounds once its other bonds are secure, in tap-Scruffles mode only: the answer to "Let's make five. We've got five. How many more?" is an empty circle and a tap on Scruffles. A question whose answer is zero always ends with "Tap Scruffles when you're ready.", and the ship's lights don't glow with the circle empty, so they don't give the answer away. Putting a MeeMee in gets "That's too many. Take one back."
- **One mode for a whole round.** A change to the answer check in Settings now starts with the next round, so a round with a zero bond can always be finished.
- **The progress grid.** Grown-ups › Progress is now the design system's BondGrid: all 34 bonds for 2 to 10 (zero bonds included) marked secure (mint, with a tick), practising (dashed peach) or not yet, with a count, a key, what secure means, the wholes-in-play switches (moved here from Settings), the last 25 answers and the clear button.
- **Every question listed.** The tests write `notes/all-questions.md`: all 189 questions the game can ask (135 without zero bonds), with the number sentence, the answer and what Scruffles says, to compare with a homework sheet.
- **Recordings.** The nine crew lines are in the build now (54 clips); the game starts using them in 0.4.1.
- **Updates** still wait for a quiet screen: the start screen or the map.
- **Review.** An independent review found that switching the answer check mid-round could leave a zero question with no way to answer it, and that a pause during "MeeMee Rescue!" could start a round unseen. Both are fixed and tested. When only one or two wholes are in play, rounds now share out the few bonds evenly.
- **Checks:** `test_game.py` 175 of 175 (new: the map and its planets, the welcome once a visit, a double tap starting one round, a pause on the map, zero bonds answered with an empty circle, the secure rule across days, 2,000 rounds checked for the mix, the zero-bond rule in each mode, the grid at both screen sizes), `test_update.py` 7 of 7.
- **To check on the tablets:** the map and a round on each; the progress grid after a few days of play (criterion 7).
