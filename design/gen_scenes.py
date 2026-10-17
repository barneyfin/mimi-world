"""Scene art for the games, composed from gen_art.py (the design system's own drawings).

Each function returns an SVG string. Colours are classes (f-*, s-*) bound to tokens, so the pages and the
design system share one palette."""
import math

from gen_art import (ICONS, JOBS, commander_call, cross_star, galaxy, held_telescope, icon, job_badge, job_picture, mimi, moggles, nebula,
                     number_tile, number_track, numbered_mimi, planet, scruffles_pod, sky_art, snuffles, spark, starfield, tok, tray)


def sky(uid="sky"):
    """The night sky behind every screen (the design system's Backdrop): a nebula, a starfield, galaxies, planets with
    craters and a shooting star, kept to the corners and edges, clear of the diagram, the tray and the buttons."""
    return '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">' + sky_art(uid) + '</svg>'


# The home map (phase 4; a planet per game from phase 5; five places from 0.8.0): where things sit on the 1280 x 800
# stage. kit/map.js puts its buttons over these. A game names its place (0 to 4) as "planet" in its game.json: the
# three planets first, then the places that aren't planets (decided 15 October 2026, mock-up rounds 10 and 11).
MAP = {
    "planets": [(330, 300, 58, "mint"),       # 0: the ringed mint planet with a moon (MeeMee Rescue)
                (1010, 560, 46, "indigo"),    # 1: the indigo planet (MeeMee Rockets)
                (1150, 250, 30, "peach")],    # 2: the small peach planet
    "places": [(690, 628, "asteroids"),       # 3: a cluster of big rocks at the bottom of the asteroid belt
               (860, 182, "station")],        # 4: a space station on the outer orbit, above the big planet
    "clear": {"asteroids": 130, "station": 120},   # the belt's dots keep this far from each place
    "sun": (640, 430, 64),
    "crew_spot": (250, 598),
}


def map_art(uid="map", taken=(0,)):
    """The home map: an alien solar system. Its own night ground, so it covers the game screens' sky.
    taken: the places that have a game, drawn lit with a halo; the others are dimmed (still to come): a planet to 45%,
    the rocks and the station to 62%."""
    sky = (nebula() + starfield(21, 110, [(180, 150, 940, 560)]) + galaxy(1130, 90, 20, 0.8, "lilac", 4)
           + galaxy(140, 120, -24, 0.62, "peach", 6) + galaxy(150, 700, -30, 0.7, "mint", 9)
           + cross_star(860, 90, 0.8) + cross_star(470, 700, 0.7) + spark(1230, 420, 0.7) + spark(70, 330, 0.6))
    sx, sy, sr = MAP["sun"]
    orbits = "".join(f'<ellipse cx="{sx}" cy="{sy}" rx="{rx}" ry="{ry}" fill="none" stroke="@night-button" stroke-width="3" stroke-dasharray="6 10"/>'
                     for rx, ry in [(200, 80), (330, 135), (600, 250)])
    belt = ""
    for i in range(52):
        a = i / 52 * 2 * math.pi
        x = sx + 470 * math.cos(a) + (7 if i % 3 == 0 else -5)
        y = sy + 190 * math.sin(a) + (4 if i % 2 == 0 else -3)
        if 140 < x < 520 and 330 < y < 600:
            continue                           # the crew's corner stays clear
        if any(math.hypot(x - px, y - py) < MAP["clear"][kind] for px, py, kind in MAP["places"]):
            continue                           # and so do the rocks and the station
        belt += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{3 + (i * 7 % 5)}" fill="@{"asteroid" if i % 2 else "planet-indigo-light"}"/>'
    cx, cy = MAP["crew_spot"]

    def lit(i):
        x, y, r, ramp = MAP["planets"][i]
        halo = tok(f'<circle cx="{x}" cy="{y}" r="{r + 20}" fill="none" stroke="@mint" stroke-width="10" opacity="0.3"/>')
        if i == 0:   # the ringed planet, with craters and a little moon
            return (halo + planet(x, y, r, ramp, f"{uid}-rescue", bands=5, ring=True, craters=[(0.3, 0.35, 0.12), (-0.35, 0.1, 0.08)])
                    + planet(x - 98, y - 68, 14, "peach", f"{uid}-moon", bands=4, rim=False))
        return halo + planet(x, y, r, ramp, f"{uid}-p{i}", bands=6 if r > 40 else 5, craters=[(0.2, -0.3, 0.14)] if r > 40 else ())

    def dim(k, i):
        x, y, r, ramp = MAP["planets"][i]
        return planet(x, y, r, ramp, f"{uid}-l{k}", bands=6 if r > 40 else 5, craters=[(0.2, -0.3, 0.14)] if r > 40 else ())

    # the places that aren't planets (3 and 4): lit as a planet is, with a mint halo, or dimmed to 62%
    places_dim, places_lit = "", ""
    for k, (x, y, kind) in enumerate(MAP["places"]):
        pic = asteroid_cluster(x, y) if kind == "asteroids" else station(x, y)
        if len(MAP["planets"]) + k in taken:
            places_lit += tok(f'<circle cx="{x}" cy="{y}" r="104" fill="none" stroke="@mint" stroke-width="10" opacity="0.3"/>') + pic
        else:
            places_dim += pic

    planets = range(len(MAP["planets"]))
    empty = [i for i in planets if i not in taken]
    return (
        '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">'
        + tok('<rect width="1280" height="800" fill="@night"/>') + sky
        + tok(orbits + belt
              + f'<circle cx="{sx}" cy="{sy}" r="112" fill="@peach" opacity="0.10"/><circle cx="{sx}" cy="{sy}" r="86" fill="@peach" opacity="0.16"/>')
        + planet(sx, sy, sr, "peach", f"{uid}-sun", bands=6)
        + "".join(lit(i) for i in sorted(taken) if i in planets)
        + ('<g opacity="0.45">' + "".join(dim(k, i) for k, i in enumerate(empty)) + '</g>' if empty else '')
        + ('<g opacity="0.62">' + places_dim + '</g>' if places_dim else '') + places_lit
        + tok(f'<ellipse cx="{cx}" cy="{cy}" rx="210" ry="26" fill="@mint" opacity="0.12"/>'
              f'<ellipse cx="{cx}" cy="{cy}" rx="210" ry="26" fill="none" stroke="@mint" stroke-width="3" stroke-dasharray="2 12" '
              'stroke-linecap="round" opacity="0.7"/>')
        + '</svg>'
    )


# The map's two places that aren't planets (0.8.0; the design system's SolarMap, mock-up rounds 10 and 11).
ROCK = "M30 120 C 20 60, 90 20, 170 28 C 250 14, 350 30, 375 90 C 398 150, 362 210, 280 214 C 200 226, 110 222, 60 200 C 30 186, 34 160, 30 120 Z"


def rock(cx, cy, w, h, rot, craters=()):
    """One small asteroid: shaded underside, lit top, a crater or two, ink outline (the tray's rock, small)."""
    sx, sy = w / 400, h / 232
    t = f'translate({cx - w / 2:.1f} {cy - h / 2:.1f}) rotate({rot} {w / 2:.1f} {h / 2:.1f})'
    body = (f'<g transform="{t}">'
            f'<path transform="scale({sx:.4f} {sy:.4f})" d="{ROCK}" fill="@asteroid-crater"/>'
            f'<path transform="translate({-w * 0.03:.1f} {-h * 0.07:.1f}) scale({sx * 0.94:.4f} {sy * 0.86:.4f})" d="{ROCK}" fill="@asteroid"/>'
            f'<path transform="translate({w * 0.12:.1f} {h * 0.06:.1f}) scale({sx * 0.62:.4f} {sy * 0.3:.4f})" d="{ROCK}" fill="@asteroid-light" opacity="0.8"/>')
    for (dx, dy, r) in craters:
        body += (f'<ellipse cx="{w * dx:.1f}" cy="{h * dy:.1f}" rx="{r:.1f}" ry="{r * 0.62:.1f}" fill="@asteroid-deep"/>'
                 f'<path d="M{w * dx - r:.1f} {h * dy:.1f} A{r:.1f} {r * 0.62:.1f} 0 0 0 {w * dx + r:.1f} {h * dy:.1f}" fill="none" stroke="@asteroid-light" stroke-width="1.5"/>')
    body += f'<path transform="scale({sx:.4f} {sy:.4f})" d="{ROCK}" fill="none" stroke="@ink" stroke-width="{3.5 / sx:.1f}"/></g>'
    return body


def asteroid_cluster(cx, cy):
    """A cluster of big rocks in the belt: a future asteroid game's place on the map."""
    k = 1.55
    return tok(rock(cx - 50 * k, cy + 16 * k, 44 * k, 30 * k, -12, [(0.6, 0.55, 6)])
               + rock(cx + 6 * k, cy - 6 * k, 78 * k, 50 * k, 6, [(0.35, 0.5, 9), (0.7, 0.62, 6)])
               + rock(cx + 56 * k, cy - 34 * k, 32 * k, 22 * k, 24, [(0.5, 0.55, 4.5)])
               + rock(cx + 50 * k, cy + 30 * k, 26 * k, 18 * k, -20)
               + spark(cx - 30 * k, cy - 36 * k, 0.6))


def station(x, y, k=1.11):
    """A small space station on the map (place 4), drawn 6 px below the place's middle (0.9.0, mock-up round 14). At 1.11
    (Barney, 17 October 2026) every point of it, outlines included, is within 111.5 px of the place's middle, inside its
    240 tap circle, so a tap anywhere on it is heard."""
    return f'<g transform="translate({x} {y + 6}) scale({k})">' + _station(0, 0) + '</g>'


def _station(cx, cy):
    """MeeMee Station as the game draws it (0.9.0, mock-up round 14; SolarMap and MeeMeeStation cards), small: a
    mint-deep truss with a mint-light zigzag, an indigo solar wing at each end on a steel mast, ten moon modules in 2 rows
    of 5 joined by mint collars (three windows lit spark), a command tower with its round screen, an antenna and a dish."""
    def X(v):
        return f"{cx + v:.1f}"

    def Y(v):
        return f"{cy + v:.1f}"
    g = ''
    # the truss, between the two rows and out to the wings
    g += (f'<rect x="{X(-84)}" y="{Y(-3.5)}" width="168" height="7" rx="2.3" fill="@mint-deep" stroke="@ink" stroke-width="2.5"/>'
          f'<path d="M{X(-80)} {Y(-1.5)}' + "".join(f' L{X(-80 + 7 * k)} {Y(1.5 if k % 2 else -1.5)}' for k in range(1, 23)) + '" fill="none" stroke="@mint-light" stroke-width="1.4" stroke-linejoin="round"/>')
    # solar wings at both ends, on a mast
    for wx in (-82, 82):
        g += f'<rect x="{X(wx - 2.2)}" y="{Y(-30.5)}" width="4.4" height="61" rx="2" fill="@steel" stroke="@ink" stroke-width="2"/>'
        for top in (-28.5, 6.5):
            g += (f'<rect x="{X(wx - 12)}" y="{Y(top)}" width="24" height="22" rx="2.5" fill="@planet-indigo" stroke="@ink" stroke-width="2.5"/>'
                  f'<path d="M{X(wx)} {Y(top + 1.5)} V{Y(top + 20.5)} M{X(wx - 10.5)} {Y(top + 7.3)} H{X(wx + 10.5)} M{X(wx - 10.5)} {Y(top + 14.7)} H{X(wx + 10.5)}" stroke="@planet-indigo-light" stroke-width="1.3"/>')
        g += f'<circle cx="{X(wx)}" cy="{Y(0)}" r="4.5" fill="@steel" stroke="@ink" stroke-width="2"/>'
    # the command tower above the middle, with its round screen, and an antenna
    g += (f'<path d="M{X(6)} {Y(-34)} V{Y(-45)}" stroke="@ink" stroke-width="2.6" stroke-linecap="round"/>'
          f'<circle cx="{X(6)}" cy="{Y(-48)}" r="3.4" fill="@spark" stroke="@ink" stroke-width="1.8"/>'
          f'<rect x="{X(-12)}" y="{Y(-35)}" width="24" height="22" rx="5" fill="@moon" stroke="@ink" stroke-width="2.5"/>'
          f'<circle cx="{X(0)}" cy="{Y(-24.5)}" r="6.2" fill="@moon" stroke="@mint" stroke-width="2.4"/>')
    # a dish on the top right module
    g += (f'<path d="M{X(40)} {Y(-17)} V{Y(-21)}" stroke="@ink" stroke-width="2.4"/>'
          f'<path d="M{X(33.5)} {Y(-24)} A6.5 4 0 0 0 {X(46.5)} {Y(-24)} Z" fill="@moon-dim" stroke="@ink" stroke-width="2" transform="rotate(-25 {X(40)} {Y(-23)})"/>')
    # the ten modules, joined by mint collars, with their windows
    lit = {(0, 1), (3, 0), (4, 1)}
    for r, my in enumerate((-9, 9)):
        for c in range(4):
            g += f'<rect x="{X(-36 + 18 * c - 2.5)}" y="{Y(my - 3)}" width="5" height="6" rx="1" fill="@mint" stroke="@ink" stroke-width="1.4"/>'
        for c in range(5):
            mx = -36 + 18 * c
            g += (f'<rect x="{X(mx - 8)}" y="{Y(my - 8)}" width="16" height="16" rx="3.4" fill="@moon" stroke="@ink" stroke-width="2.2"/>'
                  f'<circle cx="{X(mx)}" cy="{Y(my)}" r="4.6" fill="@{"spark" if (c, r) in lit else "night-raised"}" stroke="@steel" stroke-width="1.6"/>')
    return tok(g)


# The crew screen (phase 4, 0.4.1): where the cats wait before they have jobs. kit/crew.js puts the job stations,
# the ship and the cats over it.
CREW = {"deck": (300, 372), "spots": {"moggles": (220, 368), "snuffles": (380, 368)}}


def crew_art(uid="crew"):
    """The crew screen's own sky and the deck the cats wait on."""
    dx, dy = CREW["deck"]
    sky = (nebula() + starfield(33, 70, [(30, 410, 1230, 380), (500, 20, 280, 280)]) + galaxy(200, 140, -20, 0.7, "lilac", 7)
           + galaxy(980, 300, 18, 0.55, "mint", 8) + cross_star(380, 240, 0.8) + spark(860, 110, 0.6))
    spots = "".join(f'<ellipse cx="{x}" cy="{y}" rx="64" ry="11" fill="none" stroke="@mint" stroke-width="3" stroke-dasharray="2 10" '
                    'stroke-linecap="round" opacity="0.7"/>' for x, y in CREW["spots"].values())
    return (
        '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">'
        + tok('<rect width="1280" height="800" fill="@night"/>') + sky
        + tok(f'<ellipse cx="{dx}" cy="{dy}" rx="200" ry="22" fill="@night-raised"/>'
              f'<ellipse cx="{dx}" cy="{dy}" rx="200" ry="22" fill="none" stroke="@night-button" stroke-width="3"/>' + spots)
        + '</svg>'
    )


def pod_faces(w=400):
    """Scruffles in the rescue ship with all three faces; the kit shows one at a time (data-face)."""
    return scruffles_pod("all", w, uid="ship")


def spark_svg():
    return '<svg viewBox="-14 -14 28 28" aria-hidden="true">' + spark(0, 0) + '</svg>'


def templates(taken=(0,), extra=None):
    """Every drawing the kit clones at run time, as <template id="art-NAME"> elements.
    MW.art gives each copy's ids (clip paths) a number of its own, so a drawing can be on screen more than once.
    taken: the map's places that have a game. extra: the games' own drawings, {name: svg}."""
    return "\n".join(f'<template id="art-{k}">{v}</template>' for k, v in art_dict(taken, extra).items())


def art_dict(taken=(0,), extra=None):
    art = {
        "mimi": mimi(80),
        "pod": pod_faces(400),
        "tray": tray("tray"),
        "spark": spark_svg(),
        "moggles": moggles(240),
        "snuffles": snuffles(240),
        "map": map_art(taken=taken),
        "crew": crew_art(),
        "held-telescope": held_telescope(100),
        # the commander's moment on every game's end screen (0.9.0): the radio and its call (viewBox 0 -42 100 142)
        "commander-call": commander_call(100),
        # MeeMee Rescue's numbers mode (0.6.0): the kit's diagram and number track use these (kit/scene.js)
        "numbered-mimi": numbered_mimi(),
        "number-tile": number_tile(),
        "number-track": number_track(),
    }
    for job in JOBS:
        art["job-" + job] = job_picture(job, 100)
        art["badge-" + job] = job_badge(job, 56)
    for name in ICONS:
        art["icon-" + name] = icon(name, 48, 4.5, fill_play=(name == "play"))
    for name, svg in (extra or {}).items():
        if name in art:
            raise ValueError(f"a game's drawing is called {name}, which the kit already uses")
        art[name] = svg
    return art
