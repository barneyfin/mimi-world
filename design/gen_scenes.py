"""Scene art for the games, composed from gen_art.py (the design system's own drawings).

Each function returns an SVG string. Colours are classes (f-*, s-*) bound to tokens, so the pages and the
design system share one palette."""
import math

from gen_art import (ICONS, cross_star, galaxy, icon, mimi, moggles, nebula, planet, scruffles_pod, sky_art, snuffles, spark, starfield,
                     tok, tray)


def sky(uid="sky"):
    """The night sky behind every screen (the design system's Backdrop): a nebula, a starfield, galaxies, planets with
    craters and a shooting star, kept to the corners and edges, clear of the diagram, the tray and the buttons."""
    return '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">' + sky_art(uid) + '</svg>'


# The home map (phase 4): where things sit on the 1280 x 800 stage. kit/map.js puts its buttons over these.
MAP = {
    "rescue": (330, 300, 58),                  # MeeMee Rescue: the ringed mint planet
    "locked": [(1010, 560, 46, "indigo"), (1150, 250, 30, "peach")],   # games still to come
    "sun": (640, 430, 64),
    "crew_spot": (250, 598),
}


def map_art(uid="map"):
    """The home map: an alien solar system. Its own night ground, so it covers the game screens' sky."""
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
    rx, ry, rr = MAP["rescue"]
    cx, cy = MAP["crew_spot"]
    return (
        '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">'
        + tok('<rect width="1280" height="800" fill="@night"/>') + sky
        + tok(orbits + belt
              + f'<circle cx="{sx}" cy="{sy}" r="112" fill="@peach" opacity="0.10"/><circle cx="{sx}" cy="{sy}" r="86" fill="@peach" opacity="0.16"/>')
        + planet(sx, sy, sr, "peach", f"{uid}-sun", bands=6)
        + tok(f'<circle cx="{rx}" cy="{ry}" r="{rr + 20}" fill="none" stroke="@mint" stroke-width="10" opacity="0.3"/>')
        + planet(rx, ry, rr, "mint", f"{uid}-rescue", bands=5, ring=True, craters=[(0.3, 0.35, 0.12), (-0.35, 0.1, 0.08)])
        + planet(rx - 98, ry - 68, 14, "peach", f"{uid}-moon", bands=4, rim=False)
        + '<g opacity="0.45">' + "".join(planet(x, y, r, ramp, f"{uid}-l{i}", bands=6 if r > 40 else 5, craters=[(0.2, -0.3, 0.14)] if r > 40 else ())
                                         for i, (x, y, r, ramp) in enumerate(MAP["locked"])) + '</g>'
        + tok(f'<ellipse cx="{cx}" cy="{cy}" rx="210" ry="26" fill="@mint" opacity="0.12"/>')
        + '</svg>'
    )


def pod_faces(w=400):
    """Scruffles in the rescue ship with all three faces; the kit shows one at a time (data-face)."""
    return scruffles_pod("all", w, uid="ship")


def spark_svg():
    return '<svg viewBox="-14 -14 28 28" aria-hidden="true">' + spark(0, 0) + '</svg>'


def templates():
    """Every drawing the kit clones at run time, as <template id="art-NAME"> elements.
    MW.art gives each copy's ids (clip paths) a number of its own, so a drawing can be on screen more than once."""
    art = {
        "mimi": mimi(80),
        "pod": pod_faces(400),
        "tray": tray("tray"),
        "spark": spark_svg(),
        "moggles": moggles(240),
        "snuffles": snuffles(240),
        "map": map_art(),
    }
    for name in ICONS:
        art["icon-" + name] = icon(name, 48, 4.5, fill_play=(name == "play"))
    return "\n".join(f'<template id="art-{k}">{v}</template>' for k, v in art.items())
