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
- **On the tablets:** Barney pushed 0.4.0 at about 22:20; the live site served it a few minutes later, and Barney reported that everything seemed fine.

## 0.4.1 (9 October, night): the crew screen, job badges and job moments

Built from round 4 of the design canvas, which Barney approved that evening.

- **The crew screen.** Tapping Moggles, Snuffles and the ship on the map opens it: "Let's give the crew their jobs!" The four jobs wait in a row as pictures: a telescope (lookout), a spanner (engineer), a star map (navigator) and a frying pan (cook). The cats start on the deck under Scruffles's ship. Dragging a cat onto a job gives it that job: "Moggles… is the… lookout." Once both have jobs: "The crew are ready!", and the Home button pulses to lead back to the map.
- **One job per cat.** Dropping a cat on the other cat's job swaps them, and both new jobs are said. Dropping a cat back up on the deck takes its job off. Tapping a cat says its job; Hear-again says both. Each tablet remembers the jobs.
- **Job badges.** A cat with a job wears its picture as a badge on its chest: on the map, on the crew screen and on the end screen. Until both cats have jobs, they hop when the map opens, to say "tap us".
- **Job moments** (no words, so a round sounds the same; never over the diagram or the asteroid):
  - *Lookout:* as a round starts, peeks over the asteroid with the telescope, then ducks down once the MeeMee arrive.
  - *Engineer:* on a right answer, comes to the ship's left fin and taps it twice with the spanner while the lights flash; gone as the lights stop.
  - *Navigator:* as a star turns peach, holds up the star map with a dotted route to the next star.
  - *Cook:* on the end screen, holds out a pan of fish beside the rescued MeeMee, who hop again.
  A job no cat has has no moment. With reduce motion the cats fade in and out instead of moving.
- **Art and colours.** The four job pictures, the badges and the held telescope moved from the mock-up into `design/gen_art.py`. Two colour tokens were added for the spanner: `steel` and `steel-dark`, which reuse Scruffles's light and dark greys, so the spanner no longer borrows a token named after his fur. The crew screen has its own sky and deck (`gen_scenes.crew_art`).
- **Design system.** The Crew card now shows the four jobs, their badges and the rules, and the tokens include `steel` and `steel-dark`.
- **Kit.** The dragger takes a grab radius, so a whole cat can be picked up (MeeMee keep 60 stage px). On the game screen the ship is now drawn before the asteroid (they don't overlap), so the lookout can stand between them.
- **Review.** An independent review found nothing serious. It did find four smaller things, all now fixed and tested:
  - On a very quick first answer, the engineer could appear on top of the lookout; the lookout now ducks down first.
  - Pausing didn't let go of a cat being dragged on the crew screen.
  - Crew lines could carry on over the map after Home.
  - After a pause, the crew screen didn't say its opening line again.
- **Size:** the page is about 300 KB (was 257 KB).
- **Checks:** `test_game.py` 236 of 236 (new: the crew screen at both screen sizes, with drags, swaps, a pause mid-drag and the jobs remembered; each moment, where it sits and when it goes; no moments without jobs), `test_update.py` 7 of 7.
- **To check on the tablets:** dragging the cats on the crew screen, on both tablets; whether each moment reads clearly in a real round, and whether any one gets in the way.

