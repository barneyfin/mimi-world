"""Scene art for the games, composed from gen_art.py (the design system's own drawings).

Each function returns an SVG string. Colours are classes (f-*, s-*) bound to tokens, so the pages and the
design system share one palette."""
import math

from gen_art import (ICONS, JOBS, cross_star, galaxy, held_telescope, icon, job_badge, job_picture, mimi, moggles, nebula, planet,
                     scruffles_pod, sky_art, snuffles, spark, starfield, tok, tray)


def sky(uid="sky"):
    """The night sky behind every screen (the design system's Backdrop): a nebula, a starfield, galaxies, planets with
    craters and a shooting star, kept to the corners and edges, clear of the diagram, the tray and the buttons."""
    return '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">' + sky_art(uid) + '</svg>'


# The home map (phase 4; a planet per game from phase 5): where things sit on the 1280 x 800 stage. kit/map.js puts
# its buttons over these. A game names its planet (0, 1 or 2) in its game.json.
MAP = {
    "planets": [(330, 300, 58, "mint"),       # 0: the ringed mint planet with a moon (MeeMee Rescue)
                (1010, 560, 46, "indigo"),    # 1
                (1150, 250, 30, "peach")],    # 2
    "sun": (640, 430, 64),
    "crew_spot": (250, 598),
}


def map_art(uid="map", taken=(0,)):
    """The home map: an alien solar system. Its own night ground, so it covers the game screens' sky.
    taken: the planets that have a game, drawn lit with a halo; the others are dimmed (still to come)."""
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

    empty = [i for i in range(len(MAP["planets"])) if i not in taken]
    return (
        '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">'
        + tok('<rect width="1280" height="800" fill="@night"/>') + sky
        + tok(orbits + belt
              + f'<circle cx="{sx}" cy="{sy}" r="112" fill="@peach" opacity="0.10"/><circle cx="{sx}" cy="{sy}" r="86" fill="@peach" opacity="0.16"/>')
        + planet(sx, sy, sr, "peach", f"{uid}-sun", bands=6)
        + "".join(lit(i) for i in sorted(taken))
        + ('<g opacity="0.45">' + "".join(dim(k, i) for k, i in enumerate(empty)) + '</g>' if empty else '')
        + tok(f'<ellipse cx="{cx}" cy="{cy}" rx="210" ry="26" fill="@mint" opacity="0.12"/>'
              f'<ellipse cx="{cx}" cy="{cy}" rx="210" ry="26" fill="none" stroke="@mint" stroke-width="3" stroke-dasharray="2 12" '
              'stroke-linecap="round" opacity="0.7"/>')
        + '</svg>'
    )


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
    taken: the map's planets that have a game. extra: the games' own drawings, {name: svg}."""
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
