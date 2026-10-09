"""Scene art for the games, composed from gen_art.py (the design system's own drawings).

Each function returns an SVG string. Colours are classes (f-*, s-*) bound to tokens, so the pages and the
design system share one palette."""
from gen_art import (FACES, asteroid, galaxy, icon, mimi, moggles, planet, scruffles_pod, snuffles, spark, stars, ICONS)


def sky(uid="sky"):
    """The night sky behind every screen (the design system's GameScreen backdrop): planets and galaxies
    kept to the corners and edges, clear of the diagram, the tray and the buttons."""
    return (
        '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">'
        '<path class="f-night-raised" d="M820 -40 C 960 -60, 1180 -20, 1300 60 L 1300 380 C 1180 330, 1020 300, 920 220 C 840 160, 760 -20, 820 -40 Z"/>'
        + galaxy(640, 160, -18, 0.8, "lilac") + galaxy(900, 50, 26, 0.6, "peach") + galaxy(70, 300, -40, 0.62, "mint")
        + stars([(160, 300, 2.2), (250, 96, 1.8), (300, 320, 1.4), (40, 240, 1.6), (660, 120, 2.2), (720, 250, 1.6),
                 (820, 30, 1.8), (1000, 40, 2), (1240, 600, 2.2), (680, 760, 1.8), (120, 560, 2), (590, 40, 1.6),
                 (20, 640, 2), (1010, 460, 1.6), (760, 330, 1.4)])
        + spark(216, 330) + spark(735, 190, 0.8)
        + planet(60, 830, 175, "indigo", f"{uid}-a")
        + planet(150, 215, 32, "peach", f"{uid}-b", ring=True)
        + planet(690, 300, 18, "mint", f"{uid}-c")
        + '</svg>'
    )


def tray():
    """The asteroid tray: 520 x 260 with ten crater slots (two rows of five, 94 apart): a ten-frame."""
    slots = [(82 + i * 94, ry) for ry in (85, 180) for i in range(5)]
    return ('<svg width="520" height="260" viewBox="0 0 520 260" aria-hidden="true">' + asteroid(520, 260)
            + "".join(f'<circle class="f-asteroid-crater s-asteroid-crater" stroke-width="3" cx="{x}" cy="{y}" r="34" opacity="0.7"/>' for x, y in slots)
            + '</svg>')


def pod_faces(w=400):
    """Scruffles in the pod with all three faces; the kit shows one at a time (data-face)."""
    base = scruffles_pod("thinking", w)
    assert base.count(FACES["thinking"]) == 1
    groups = "".join(f'<g data-face="{name}">{svg}</g>' for name, svg in FACES.items())
    return base.replace(FACES["thinking"], groups)


def spark_svg():
    return '<svg viewBox="-14 -14 28 28" aria-hidden="true">' + spark(0, 0) + '</svg>'


def templates():
    """Every drawing the kit clones at run time, as <template id="art-NAME"> elements."""
    art = {
        "mimi": mimi(80),
        "pod": pod_faces(400),
        "tray": tray(),
        "spark": spark_svg(),
        "moggles": moggles(240),
        "snuffles": snuffles(240),
    }
    for name in ICONS:
        art["icon-" + name] = icon(name, 48, 4.5, fill_play=(name == "play"))
    return "\n".join(f'<template id="art-{k}">{v}</template>' for k, v in art.items())
