"""MeeMee World tokens: the single source for tokens.json and the colour classes in bundle.css."""

COLOURS = [
    # Ground
    ("night", "#171A45", "The sky: the ground of every screen. Text on it: moon (14.4:1), text-2 (9.1:1), text-3 (6.8:1)."),
    ("night-raised", "#1C2052", "Nebula shapes in the sky and the grown-ups panel, one step up from night. text-2 on it 8.4:1."),
    ("night-button", "#262B66", "Fill of round navigation buttons (Home, Music) and grown-ups cells; moon icons and text on it 11.3:1."),
    ("ink", "#0F1236", "Outlines of the crew, the pod and the asteroid, pupils, and the solid shadow under navigation buttons."),
    # Surfaces that hold numbers
    ("moon", "#F4EFE1", "Filled circles, number pills and small stars. Numerals on it in numeral (13.7:1)."),
    ("moon-dim", "#E9E4D4", "A circle or pill still waiting for its answer, always with a dashed rim. Numerals on it 12.4:1."),
    ("numeral", "#1B1E4A", "Numerals and icons on moon, moon-dim, peach (9.1:1) and mint (9.5:1)."),
    # Structure and action
    ("mint", "#7FD9C4", "The maths' structure: diagram lines, circle and pill rims, the current-question star, the pod, focus rings. 9.9:1 on night."),
    ("mint-dark", "#5CC2AD", "The pod's rim and the middle band of mint planets."),
    ("teal-band", "#1B6F67", "Scruffles's headset band."),
    ("peach", "#FFB48A", "Actions and reward: the Hear-again and Play buttons, earned stars, the success ring, + and = in the equation, pod lights. 9.6:1 on night."),
    ("peach-dark", "#B9724E", "The solid shadow under peach buttons."),
    ("star-empty", "#6268B0", "Outline of a progress star not earned yet (3.3:1 on night)."),
    ("spark", "#FFE8B0", "Four-point sparkles in the sky and in celebrations."),
    ("glass", "#CDEFF0", "The pod's glass dome, used at 18% opacity."),
    # Grown-ups text
    ("text-2", "#B9BEE8", "Secondary text and captions for grown-ups on night (9.1:1) and night-raised (8.4:1)."),
    ("text-3", "#9DA2DF", "Labels, the grown-ups lock icon and its ring on night (6.8:1)."),
    # The MeeMee
    ("mimi", "#8C7CD6", "Body of every MeeMee, and the outer glow of lilac galaxies. 4.7:1 on night, 3.1:1 on the asteroid."),
    ("mimi-outline", "#3E3380", "A MeeMee's outline: 9.2:1 on moon circles."),
    ("mimi-muzzle", "#C9BEF0", "A MeeMee's muzzle."),
    ("mimi-nose", "#F29BB0", "A MeeMee's nose."),
    ("mimi-eye", "{night}", "A MeeMee's eyes."),
    # The crew
    ("scruffles-grey", "#8E909E", "Scruffles's grey cap, ears, back and tail (5.2:1 on night)."),
    ("cat-white", "#F7F5F2", "White fur on Scruffles and Snuffles, and the highlights in every eye."),
    ("ear-pink", "#EDE6EE", "Scruffles's inner ears."),
    ("nose-pink", "#E8A0A8", "Pink noses: Scruffles and Snuffles."),
    ("scruffles-eye", "#C8B65A", "Scruffles's amber-green eyes."),
    ("moggles-black", "#1E1E28", "Black fur: Moggles, and Snuffles's back and patches."),
    ("moggles-rim", "#7479BC", "The pale outline around black fur, so it reads against night (4.1:1)."),
    ("fur-shade", "#34343F", "Shading lines on black fur."),
    ("nose-dark", "#4A4A5A", "Moggles's nose."),
    ("moggles-ear", "#4A3446", "Moggles's inner ears."),
    ("snuffles-ear", "#6A4A5A", "Snuffles's inner ears."),
    ("moggles-eye", "#CFD64A", "Moggles's yellow-green eyes."),
    ("snuffles-eye", "#E3C23C", "Snuffles's yellow eyes."),
    ("mouth", "#E0607A", "An open, happy mouth."),
    # Sky and planets
    ("planet-indigo-light", "#5450AA", "Light (top-left) band of indigo planets."),
    ("planet-indigo", "#403C8E", "Middle band of indigo planets."),
    ("planet-indigo-dark", "#2E2A6E", "Dark (bottom-right) band of indigo planets."),
    ("planet-peach-light", "#FFC9AA", "Light band of peach planets."),
    ("planet-peach", "#E8A07E", "Middle band of peach planets."),
    ("planet-peach-dark", "#C47A60", "Dark band of peach planets."),
    ("planet-mint-light", "#A8E8DA", "Light band of mint planets."),
    ("planet-mint", "{mint-dark}", "Middle band of mint planets."),
    ("planet-mint-dark", "#3E9C8A", "Dark band of mint planets."),
    ("galaxy", "#B9A6F2", "Inner glow of lilac galaxies (35% opacity)."),
    ("galaxy-peach", "#FFD3B5", "Inner glow of peach galaxies (28% opacity)."),
    ("galaxy-mint", "#B5EDE0", "Inner glow of mint galaxies (30% opacity)."),
    ("asteroid", "#3A3474", "The asteroid tray where waiting MeeMee sit."),
    ("asteroid-crater", "#2C2760", "Craters on the asteroid, and the empty slots in its ten-frame."),
]

SPACING = [
    ("space-xs", "8px", "Gap between buttons in a row; the gap between MeeMee in a tight pattern."),
    ("space-s", "14px", "Gap between progress stars; padding inside a pill."),
    ("space-m", "24px", "Distance from the screen edge to any button (nothing the player taps sits closer)."),
    ("space-l", "32px", "Grown-ups panel padding; gap between the diagram and the tray."),
    ("space-xl", "48px", "Gap between major zones on a screen."),
]

RADIUS = [
    ("radius-cell", "12px", "Cells in the grown-ups bond grid."),
    ("radius-panel", "28px", "The grown-ups panel and the equation card."),
    ("radius-pill", "35px", "Number pills (90 × 70)."),
    ("radius-round", "50%", "Circles, MeeMee grab areas and every button the player taps."),
]

SIZES = [
    ("stage-width", "1280px", "The stage every screen is drawn on; scaled to fit the tablet (0.82 on the Fire, 1.0 on the Doogee)."),
    ("stage-height", "800px", "Stage height (16:10, both tablets)."),
    ("mimi-size", "80px", "A MeeMee in the tray, while dragged, and in a part with 1–4 (about 11 mm on the Fire)."),
    ("mimi-grab", "120px", "The invisible grab area around a MeeMee (about 16 mm on the Fire)."),
    ("mimi-mid", "56px", "A MeeMee in a part holding 5 or 6."),
    ("mimi-small", "46px", "A MeeMee in a part holding 7–10. Placed MeeMee only; they grow back to mimi-size when lifted."),
    ("circle-whole", "230px", "Diameter of the whole circle."),
    ("circle-part", "250px", "Diameter of a part circle (about 34 mm on the Fire)."),
    ("rim", "7px", "Rim of whole and part circles."),
    ("line-width", "10px", "The lines joining the whole to its parts."),
    ("pill-width", "90px", "Number pill width."),
    ("pill-height", "70px", "Number pill height."),
    ("button-main", "96px", "Hear-again: the one button the player uses most."),
    ("button-nav", "84px", "Home and Music buttons."),
    ("button-play", "160px", "The Play button on the tap-to-start screen."),
    ("button-grownups", "44px", "The grown-ups lock (press and hold for 3 seconds)."),
    ("star-size", "38px", "A progress star."),
]

SHADOWS = [
    ("press-ink", "0 6px 0 #0F1236", "Solid shadow under navigation buttons; drops to 0 2px 0 when pressed."),
    ("press-peach", "0 7px 0 #B9724E", "Solid shadow under peach buttons."),
    ("halo-mint", "0 0 0 12px rgba(127,217,196,0.14)", "Soft halo around given circles and pills."),
    ("ring-success", "0 0 0 16px rgba(255,180,138,0.3)", "The success ring around a circle the player has just completed."),
    ("lift", "0 14px 8px rgba(0,0,0,0.45)", "Under a MeeMee while it is dragged (used as a drop-shadow filter)."),
]

OPACITY = [
    ("opacity-lines", "0.75", "The whole-to-part lines, so they sit behind the circles."),
    ("opacity-glass", "0.18", "The pod's glass dome."),
    ("opacity-locked", "0.45", "A planet on the map whose game isn't built yet."),
]

TYPE_STYLES = {
    "For the player": [
        {"name": "numeral-whole", "fontSize": "140px", "lineHeight": 1, "fontWeight": 700, "sample": "7",
         "usage": "The numeral inside the whole circle, in numeral on moon."},
        {"name": "equation", "fontSize": "64px", "lineHeight": 1, "fontWeight": 700, "sample": "3 + 4 = 7",
         "usage": "The number sentence shown after a correct answer: numbers in moon on night, + and = in peach."},
        {"name": "numeral-part", "fontSize": "52px", "lineHeight": 1, "fontWeight": 700, "sample": "4",
         "usage": "The numeral in a number pill under each part."},
    ],
    "For grown-ups": [
        {"name": "title", "fontSize": "30px", "lineHeight": "36px", "fontWeight": 700, "sample": "MeeMee Rescue progress",
         "usage": "Heading of the grown-ups area, in moon on night-raised."},
        {"name": "button-label", "fontSize": "22px", "lineHeight": "26px", "fontWeight": 700, "sample": "Close",
         "usage": "Words on grown-ups buttons."},
        {"name": "body", "fontSize": "19px", "lineHeight": "27px", "fontWeight": 400, "sample": "Practising: 3 + 4, 2 + 6",
         "usage": "Grown-ups text, in moon or text-2 on night-raised."},
        {"name": "label", "fontSize": "17px", "lineHeight": "22px", "fontWeight": 400, "sample": "Secure",
         "usage": "Grid cells, legends and captions, in text-2 or text-3."},
    ],
}
