# MeeMee World look, feel and words

The design system artifact (https://claude.ai/artifact/7u4TCYp4hQ3ia695MpegK7) is the spec; this is what a game needs from it. If a game needs something the design system doesn't have (a new character, a new kind of screen), it is designed there first, in a mock-up round Barney approves.

## The idea

A deep night sky with a layered nebula, banded planets and spiral galaxies, where Scruffles the rescue pilot (a grey-and-white cat in a mint rescue ship) and the MeeMee (identical lilac kittens) live, with Moggles and Snuffles as crew. Drawn with a little more detail than a picture book, for a child of five to grow into. Calm, warm and never hurried: the child plays at their own pace and is never told off.

## Colour roles

Use token names only (as classes `f-<token>` fill, `s-<token>` stroke, `bg-<token>`, `c-<token>`, as `var(--<token>)` in CSS, or `@<token>` in `art.py`).

- `night` is the ground of every screen; `night-raised` and `night-button` are one and two steps up (panels, nav buttons).
- `mint` is the maths' structure: lines and rims of the diagram, pill rims, the current star, focus rings, halos that say "tap me". Not for decoration.
- `peach` is action and reward: Play and Hear-again buttons, earned stars, the success ring, `+`, `−` and `=`. `peach-dark` is its pressed shadow.
- `moon` holds numbers and words: filled circles, pills and cards, with text in `numeral`. Something still waiting for its answer is `moon-dim` with a dashed rim.
- `mimi` (lilac) is the MeeMee and nothing else, apart from lilac galaxies.
- The cats' colours (`scruffles-grey…`, `moggles-black`, `cat-white` and their eyes and noses) are for the cats only.
- `text-2` and `text-3` are for grown-ups text and quiet icons. `ink` is every outline except black fur, which gets `moggles-rim`.
- `spark` is for sparkles and the ship's lights; `star-empty` for stars not yet earned.
- Planets use the six-step ramps `planet-mint-*`, `planet-peach-*`, `planet-indigo-*`.

## Type

Andika for everything (built into the page): single-storey *a* and *g*; *I*, *l* and *1* clearly different. Bold for anything the child sees.

- For the child: `numeral-whole` (140 px), `equation` (64 px, the number sentence), `numeral-part` (52 px, also on a number tile), `numeral-sign` (84 px, on a numbered MeeMee's sign). A phonics game sets its letters and words in Andika at a similar size, in `numeral` on `moon`. Andika stays for letters too (decided 10 October 2026); check its letter shapes against the child's reading book when the game is played (MEEMEE.md, Rules).
- The kit's title banners are the only other words the child sees: the set's or a game's name, for about 2 seconds while it is spoken, in `banner` (Andika bold, 84 px) in `numeral` on a `moon` plaque with an 8 px `mint` rim, a 4 px `ink` edge and a solid `ink` shadow, centred with its top at 292, the game's badge at its left (design system, TitleBanner). The kit shows them from each `game.json`; a game doesn't. Draw a game's badge in a 100 × 100 box, filling it as the template's star does: the banner shows it at 112 px.
- For grown-ups: `title` (30), `button-label` (22), `body` (19), `label` (17).
- **The number sentence** (Equation card; `MW.equation`): numbers in `moon`, `+`, `−` and `=` in `peach`, 22 px apart. The minus is the minus sign (U+2212), never a hyphen. A subtraction reads whole, then the part going, then what is left (7 − 4 = 3). Its **gap**, where the answer goes while the question is asked, is a tile-sized ring (84 across) of `moon-dim` with a 5 px dashed `mint` rim, and can sit in any of its three places. Its usual place is under the diagram (left 180, top 700, 400 × 80); during a question with the number track at the bottom it sits under Scruffles (left 790, top 528, 440 × 100).

## Size and layout

- Every screen is drawn on a 1280 × 800 stage and scaled to fit the tablet (0.82 on the Fire, 1.0 on the Doogee). Lay things out in stage pixels; never reflow.
- On the Fire, 80 stage px is about 11 mm. Anything tapped is at least `button-nav` (84 px); anything dragged is drawn at about `mimi-size` (80) inside a `mimi-grab` (120) area. Nothing tapped sits closer than `space-m` (24) to the edge.
- Fixed places on every game screen (the kit puts them there): Home top-left (24, 20); Music top-right (1172, 26, or 1052 when Hear-again is there); Hear-again (1160, 20); progress stars top-centre (five from 517, 34: centred on 640 for any other number, `MW.stars(…, { centre: true })`); the grown-ups lock bottom-left (24, 732). Keep these corners clear.
- **The home map** (SolarMap card) has five places, and each game takes one: 0 the ringed mint planet (MeeMee Rescue's), 1 the indigo planet (MeeMee Rockets'), 2 the small peach planet (Take MeeMee Home's), 3 a cluster of four big rocks at the bottom of the asteroid belt (the tray's rock drawn small, in the `asteroid` colours, with a `spark`), 4 a space station on the outer orbit above the big central planet (a `moon` hub with a window band, two `planet-indigo` solar wings, a `spark` antenna light, all outlined in `ink`). A place with a game is in full colour with a soft `mint` halo and its badge; one still to come is dimmed (a planet to 45%, the rocks and the station to 62%) with a `text-3` lock badge, and says "That place isn't ready yet." when tapped. Every place's tap area is at least 120 across, whatever its drawn size; the rocks and the station 240, so a tap anywhere on their drawing is heard (decided 15 October 2026). A new game takes a free place; existing places never move.
- The child's hand comes from the right, so put what they drag from on the right and the thing being worked on (the maths, the word) on the left, where a hand won't cover it. Scruffles's ship usually sits top-right (`MW.LAYOUT.pod`: 830, 70, 400 wide).

## Characters and drawings

- **Scruffles** (grey and white) is the hero of every game and flies the rescue ship (`MW.pod`): three faces (thinking, got it, try again) and lights that flash on a right answer. Keep the grey cap, the white stripe widening into the muzzle, the amber-green eyes and the fluffy white chest.
- **Moggles** (all black, peach scarf) and **Snuffles** (black and white, black patch on one front leg, mint collar) are the crew, with jobs the child gives them (`MW.crew`). A game may give them a short wordless moment.
- **The MeeMee** are identical lilac kittens (`mimi` drawing), the counters. One MeeMee, two MeeMee.
- **MeeMee Rescue's numbers mode** (NumbersMode card; kit drawings): a numbered MeeMee (`numbered-mimi`: a MeeMee 128 across holding up a `peach` sign 140 × 100 with its number in `numeral-sign`; 0.86 of that in the whole circle); number tiles (`number-tile`: a `moon` disc 84 across, `mint` rim, `ink` edge and shadow, the number in `numeral-part`); and the number track (`number-track`: an `asteroid` rail along the bottom holding tiles 0 to 10, 94 apart from x 128, tops at 686, clear of the grown-ups lock). A tile out of the track leaves a dashed `text-3` ring.
- **Take MeeMee Home's drawings** (TakeMeeMeeHome card; `games/takehome/art.py`, the game's own): the top of the MeeMee's home planet, a big six-band `planet-peach` planet with three MeeMee houses on its curve (a `moon` dome with two ear points, a round `night-raised` door and a `spark` glint, outlined in `ink`), its gentle curve across the end screen, and the badge (a house on its planet in a round `night-raised` window).
- **Drawing style:** soft flat shapes with a 4–6 px outline in `ink`, no gradients, and a little detail inside the outline (fur lines, a ring and two glints in each eye, one darker step of shading). Detail stays inside the silhouette; silhouettes stay simple. Planets are three to six hard bands lit from the top left, with craters, no outline.
- **In code:** draw with the helpers in `design/gen_art.py` (`mimi`, `cat`, `scruffles_pod`, `planet`, `star`, `spark`, `icon`, `job_picture`) and `tok()` for your own shapes (reference.md, Drawings).
- Never a helmet, hood, cloak or armour, and nothing that looks like a character from a film, show or app.

## Motion

- Snap into place and tidy into a pattern: 260 ms, cubic-bezier(.2,.8,.2,1). Float back after a wrong drop: 260 ms.
- A dragged thing grows to 1.12 and lifts on a soft shadow; one finger drags at a time.
- Success: the ring (450 ms), sparkles (`MW.sparkles`: grow in 300 ms, gone by 1.2 s), Scruffles's got-it face, the ship's lights (about 4 s), a chime.
- A hop (`mw-hop`, 420 ms) is the one way something bounces for attention.
- A title banner fades and grows in over 260 ms, stays for its line and at least 2 seconds, and fades out over 260 ms. The number track slides down out of sight and back over 260 ms, and the number sentence moves between its two places over 260 ms (the snap's ease-out). A dragged number tile grows to 1.1 and tilts 5 degrees; a numbered MeeMee pops up to carry a right answer (260 ms, the snap's timing). With reduce motion each is a fade. A title banner shows only when its line is recorded: never a silent banner.
- Nothing bigger than a character flashes more than 3 times a second; small lights may flash up to 3 times a second, and anything else repeating takes at least a second per cycle; the whole screen never flashes.
- Reduce motion (`MW.reduceMotion` and the CSS media query): movement becomes a fade or an instant change; flashing lights stay steadily lit.

## Words: what Scruffles says

- Every line is short (under eight words), warm, present tense, using "we" and "you": "Let's make seven.", "How many more?", "Tap Scruffles when you're ready."
- Use the class's words (for MeeMee Rescue: whole, part, make; for Take MeeMee Home, every subtraction word the class uses, taking turns: take away, subtract and minus, is and equals, and "left"). Match the homework.
- Praise the effort and the maths: "You found it!", "Super counting!", "Three and four make seven." Never "Wrong", "Oops" or "No".
- A wrong try gets "Let's try again." or "Let's look again." in the same warm voice; the second wrong try gets a hint that does it together ("Let's count on from three. Four, five…").
- Build sentences from pieces when the same shape repeats with different words (numbers, names, jobs). Pieces in the middle of a sentence are recorded with the voice lifting; the last piece with the voice falling. Say so in the line's `how`.
- Never the child's name.

## Words: grown-ups

British English, sentence case, plain and brief, no exclamation marks: "Secure: right first time on three different days." Only in the grown-ups area.

## Sound

Effects (`MW.audio.sfx`): `pop` (something snaps into place), `whoosh` (something floats back), `chime` (a right answer), `twinkle` (a star earned), `tune` (the end of a round). No buzzers or failure sounds. The music plays quietly under everything and dips while a line is spoken; the kit does this.
