"""Scene art for the games, composed from gen_art.py (the design system's own drawings).

Each function returns an SVG string. Colours are classes (f-*, s-*) bound to tokens, so the pages and the
design system share one palette."""
from gen_art import ICONS, icon, mimi, moggles, scruffles_pod, sky_art, snuffles, spark, tray


def sky(uid="sky"):
    """The night sky behind every screen (the design system's Backdrop): a nebula, a starfield, galaxies, planets with
    craters and a shooting star, kept to the corners and edges, clear of the diagram, the tray and the buttons."""
    return '<svg width="1280" height="800" viewBox="0 0 1280 800" aria-hidden="true">' + sky_art(uid) + '</svg>'


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
    }
    for name in ICONS:
        art["icon-" + name] = icon(name, 48, 4.5, fill_play=(name == "play"))
    return "\n".join(f'<template id="art-{k}">{v}</template>' for k, v in art.items())
