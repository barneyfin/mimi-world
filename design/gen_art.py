"""SVG builders for MeeMee World: the older look (round 3 of the mock-ups, chosen 9 October 2026).

Shapes in hard colour bands with ink outlines, a little more detail than the first look: banded planets with
craters, galaxies with arms and stars, a nebula, the rescue ship with lights, fur and markings on the crew.

Every colour is a token. Drawings are written with fill="@token" and stroke="@token"; tok() turns those into classes
(f-token, s-token) that the token CSS colours. A raw colour, or a token that doesn't exist, stops the build.
"""
import math
import random
import re

from gen_tokens import COLOURS

TOKENS = {n for n, _, _ in COLOURS}


def f(n):
    return f"{n:.1f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- @token colours -> classes
_TAG = re.compile(r"<[a-zA-Z][^<>]*>")
_COLOUR = re.compile(r'\s(fill|stroke)="([^"]*)"')


def tok(svg):
    def tag(m):
        t = m.group(0)
        classes = []

        def colour(a):
            kind, val = a.group(1), a.group(2)
            if val.startswith("@"):
                if val[1:] not in TOKENS:
                    raise ValueError(f"no token called {val[1:]}: {t[:90]}")
                classes.append(("f-" if kind == "fill" else "s-") + val[1:])
                return ""
            if val in ("none", "currentColor") or val.startswith("url("):
                return a.group(0)
            raise ValueError(f"raw colour {val} (use a token): {t[:90]}")

        t = _COLOUR.sub(colour, t)
        if classes:
            c = re.search(r'\sclass="([^"]*)"', t)
            if c:
                t = t[:c.start()] + f' class="{c.group(1)} {" ".join(classes)}"' + t[c.end():]
            else:
                t = re.sub(r"^<([a-zA-Z]+)", lambda n: f'<{n.group(1)} class="{" ".join(classes)}"', t)
        return t

    return _TAG.sub(tag, svg)


# ---------------------------------------------------------------- the MeeMee (same silhouette, a little more detail)

def mimi(size=80, extra=""):
    return f'<svg class="mw-mimi-art" width="{size}" height="{size}" viewBox="0 0 80 80" aria-hidden="true"{extra}>' + mimi_body() + '</svg>'


def mimi_body():
    """The MeeMee's shapes, in an 80 x 80 box (for drawings that hold a MeeMee)."""
    return tok(
        '<path d="M14 32 L12 6 L33 21 Z" fill="@mimi" stroke="@mimi-outline" stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M66 32 L68 6 L47 21 Z" fill="@mimi" stroke="@mimi-outline" stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M17 25 L16 13 L27 21 Z" fill="@mimi-muzzle"/><path d="M63 25 L64 13 L53 21 Z" fill="@mimi-muzzle"/>'
        '<path d="M9 45 C 9 28, 23 17, 40 17 C 57 17, 71 28, 71 45 C 73 47, 72 51, 70 52 C 67 64, 55 73, 40 73 C 25 73, 13 64, 10 52 '
        'C 8 51, 7 47, 9 45 Z" fill="@mimi" stroke="@mimi-outline" stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M26 24 C 31 21, 36 21, 40 23 C 44 21, 49 21, 54 24" fill="none" stroke="@mimi-shade" stroke-width="2.4" stroke-linecap="round"/>'
        '<path d="M15 56 C 22 66, 32 70, 40 70 C 48 70, 58 66, 65 56 C 58 62, 50 64, 40 64 C 30 64, 22 62, 15 56 Z" fill="@mimi-shade" opacity="0.7"/>'
        '<ellipse cx="40" cy="55" rx="14" ry="10" fill="@mimi-muzzle"/>'
        '<circle cx="29" cy="41" r="5.4" fill="@mimi-eye"/><circle cx="51" cy="41" r="5.4" fill="@mimi-eye"/>'
        '<circle cx="27.4" cy="39.2" r="1.9" fill="@highlight"/><circle cx="49.4" cy="39.2" r="1.9" fill="@highlight"/>'
        '<circle cx="30.6" cy="43" r="0.9" fill="@highlight"/><circle cx="52.6" cy="43" r="0.9" fill="@highlight"/>'
        '<path d="M37 51 L43 51 L40 54.5 Z" fill="@mimi-nose"/>'
        '<path d="M36.5 58 C 38 59.6, 40 59.6, 40 57 C 40 59.6, 42 59.6, 43.5 58" fill="none" stroke="@mimi-outline" stroke-width="1.6" stroke-linecap="round"/>'
        '<path d="M28 55 L18 53 M28 58 L19 60 M52 55 L62 53 M52 58 L61 60" stroke="@mimi-outline" stroke-width="1.3" stroke-linecap="round" opacity="0.7"/>'
    )


# ---------------------------------------------------------------- MeeMee Rescue's numbers mode (0.6.0, round 8; NumbersMode)
# The kit puts the number itself over these drawings as text (numeral-sign on the sign, numeral-part on a tile), so one
# drawing serves every number.

NUMBERED = {"w": 140, "h": 209, "mimi": 128, "sign_y": 102.4, "sign_w": 140, "sign_h": 100}


def numbered_mimi():
    """A MeeMee holding up a peach sign (its number goes on the sign): 140 x 209 at full size, in a part circle.
    The MeeMee is 128 across; the sign 140 x 100 with a 4.5 px ink edge and a peach-dark shadow 6 px down; two lilac
    paws grip its top edge. Centred on its circle at (70, 102.5); the whole circle's is drawn at 0.86 (kit/scene.js)."""
    n = NUMBERED
    cx, sy = n["w"] / 2, n["sign_y"]
    paws = ""
    for px in (cx - 0.3 * n["sign_w"], cx + 0.3 * n["sign_w"]):
        py = sy + 4
        paws += (f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="15" ry="10" fill="@mimi" stroke="@mimi-outline" stroke-width="3.5"/>'
                 f'<path d="M{f(px - 5)} {f(py - 6)} V{f(py)} M{f(px)} {f(py - 7)} V{f(py)} M{f(px + 5)} {f(py - 6)} V{f(py)}" '
                 'stroke="@mimi-outline" stroke-width="2" stroke-linecap="round"/>')
    return (f'<svg width="{n["w"]}" height="{n["h"]}" viewBox="0 0 {n["w"]} {n["h"]}" overflow="visible" aria-hidden="true">'
            f'<svg x="{f(cx - n["mimi"] / 2)}" y="0" width="{n["mimi"]}" height="{n["mimi"]}" viewBox="0 0 80 80" overflow="visible">' + mimi_body() + '</svg>'
            + tok(f'<rect x="0" y="{f(sy + 6)}" width="{n["sign_w"]}" height="{n["sign_h"]}" rx="22" fill="@peach-dark"/>'
                  f'<rect x="2.25" y="{f(sy + 2.25)}" width="{f(n["sign_w"] - 4.5)}" height="{f(n["sign_h"] - 4.5)}" rx="19.75" '
                  'fill="@peach" stroke="@ink" stroke-width="4.5"/>' + paws)
            + '</svg>')


def number_tile():
    """A number tile (its number goes on top): a moon disc 84 across with a 6 px mint rim, a 3 px ink edge and an ink
    shadow 6 px down. 90 x 96, the disc centred on (45, 45): put it 3 px up and left of the tile's 84 px box."""
    return ('<svg width="90" height="96" viewBox="-45 -45 90 96" overflow="visible" aria-hidden="true">'
            + tok('<circle cx="0" cy="6" r="45" fill="@ink"/>'
                  '<circle cx="0" cy="0" r="43.5" fill="@moon" stroke="@ink" stroke-width="3"/>'
                  '<circle cx="0" cy="0" r="39" fill="none" stroke="@mint" stroke-width="6"/>')
            + '</svg>')


TRACK = {"x": 114, "y": 674, "w": 1052, "h": 108}


def number_track(uid="track"):
    """The number track's rail: an asteroid bar 1052 x 108 (radius 54) with a lit top edge, a shaded foot and an ink
    edge. It sits at (114, 674) under the tiles 0 to 10 (x 128 + 94 n, tops at 686)."""
    w, h, r, e = TRACK["w"], TRACK["h"], 54, 4.5
    iw, ih, ir = w - 2 * e, h - 2 * e, r - e

    def shape(dy=0):
        return (f'M{f(e + ir)} {f(e + dy)} H{f(e + iw - ir)} A{f(ir)} {f(ir)} 0 0 1 {f(e + iw - ir)} {f(e + ih + dy)} '
                f'H{f(e + ir)} A{f(ir)} {f(ir)} 0 0 1 {f(e + ir)} {f(e + dy)} Z')
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">'
            + tok(f'<clipPath id="{uid}-in"><path d="{shape()}"/></clipPath>'
                  f'<path d="{shape()}" fill="@asteroid"/>'
                  f'<g clip-path="url(#{uid}-in)">'
                  f'<path d="{shape()} {shape(-10)}" fill="@asteroid-crater" fill-rule="evenodd"/>'
                  f'<path d="{shape()} {shape(8)}" fill="@asteroid-light" fill-rule="evenodd"/></g>'
                  f'<rect x="{e / 2}" y="{e / 2}" width="{w - e}" height="{h - e}" rx="{r - e / 2}" fill="none" stroke="@ink" stroke-width="{e}"/>')
            + '</svg>')


# Counting patterns: offsets from a part circle's centre, and the MeeMee size for each count.
def pattern(n):
    if n <= 0:
        return 80, []
    if n == 1:
        return 80, [(0, 0)]
    if n == 2:
        return 80, [(-45, 0), (45, 0)]
    if n == 3:
        return 80, [(0, -46), (-45, 34), (45, 34)]
    if n == 4:
        return 80, [(-45, -45), (45, -45), (-45, 45), (45, 45)]
    if n == 5:
        return 56, [(-46, -46), (46, -46), (0, 0), (-46, 46), (46, 46)]
    if n == 6:
        return 56, [(x, y) for y in (-32, 32) for x in (-64, 0, 64)]
    four = [-81, -27, 27, 81]
    three = [-54, 0, 54]
    if n == 7:
        return 46, [(x, -27) for x in four] + [(x, 27) for x in three]
    if n == 8:
        return 46, [(x, -27) for x in four] + [(x, 27) for x in four]
    if n == 9:
        return 46, [(x, y) for y in (-54, 0, 54) for x in three]
    return 46, [(x, -54) for x in three] + [(x, 0) for x in four] + [(x, 54) for x in three]


def mimi_in_circle(n, inner=236):
    """Absolutely placed MeeMee inside a circle's padding box (inner × inner)."""
    size, pts = pattern(n)
    c = inner / 2
    out = []
    for (dx, dy) in pts:
        out.append(f'<div class="mw-placed" style="left:{c + dx - size / 2:.0f}px;top:{c + dy - size / 2:.0f}px">{mimi(size)}</div>')
    return "".join(out)


# ---------------------------------------------------------------- the sky

def stars(points, r=2):
    """Plain round stars at given points (x, y, radius)."""
    return tok("".join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="@moon"/>' for (x, y, rr) in points))


def spark(x, y, s=1.0, colour="spark", op=1.0):
    """A four-point sparkle."""
    o = "" if op == 1.0 else f' opacity="{op}"'
    return tok(f'<path transform="translate({f(x)} {f(y)}) scale({s})" fill="@{colour}"{o} '
               'd="M0 -12 Q 2 -2 12 0 Q 2 2 0 12 Q -2 2 -12 0 Q -2 -2 0 -12 Z"/>')


def cross_star(x, y, s=1.0):
    """A bright star with long thin rays."""
    return tok(f'<g transform="translate({f(x)} {f(y)}) scale({s})" opacity="0.9">'
               '<path d="M0 -16 L1 -1 L16 0 L1 1 L0 16 L-1 1 L-16 0 L-1 -1 Z" fill="@moon" opacity="0.55"/>'
               '<path d="M0 -7 L2 -2 L7 0 L2 2 L0 7 L-2 2 L-7 0 L-2 -2 Z" fill="@spark"/>'
               '<circle r="2" fill="@highlight"/></g>')


def starfield(seed, n, avoid=(), w=1280, h=800):
    """Scattered stars: mostly small and dim, some bright, a few coloured. Never inside the 'avoid' boxes."""
    rnd = random.Random(seed)
    out = []
    tries = 0
    while len(out) < n and tries < n * 30:
        tries += 1
        x, y = rnd.uniform(6, w - 6), rnd.uniform(6, h - 6)
        if any(ax <= x <= ax + aw and ay <= y <= ay + ah for (ax, ay, aw, ah) in avoid):
            continue
        k = rnd.random()
        if k < 0.6:
            out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rnd.uniform(0.7, 1.2))}" fill="@moon" opacity="{f(rnd.uniform(0.35, 0.7))}"/>')
        elif k < 0.9:
            out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rnd.uniform(1.4, 2.0))}" fill="@moon" opacity="0.9"/>')
        else:
            col = rnd.choice(["galaxy", "galaxy-mint", "galaxy-peach"])
            out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rnd.uniform(1.6, 2.3))}" fill="@{col}" opacity="0.95"/>')
    return tok("".join(out))


def nebula():
    """Layered flat, see-through shapes: depth without gradients."""
    return tok(
        '<path d="M800 -40 C 950 -70, 1190 -30, 1310 50 L 1310 400 C 1190 350, 1030 320, 925 236 C 838 168, 752 -16, 800 -40 Z" fill="@night-raised"/>'
        '<path d="M870 -30 C 990 -50, 1180 -10, 1300 70 L 1300 300 C 1200 270, 1080 240, 1000 180 C 930 128, 840 -10, 870 -30 Z" fill="@nebula" opacity="0.8"/>'
        '<path d="M960 -20 C 1060 -30, 1200 10, 1300 80 L 1300 210 C 1220 190, 1130 160, 1070 120 C 1010 80, 930 -10, 960 -20 Z" fill="@mimi" opacity="0.10"/>'
        '<path d="M1040 20 C 1110 10, 1220 50, 1300 110 L 1300 170 C 1240 160, 1170 130, 1120 100 C 1080 76, 1020 30, 1040 20 Z" fill="@mint" opacity="0.07"/>'
        '<path d="M-40 520 C 60 480, 200 500, 300 560 C 380 610, 360 700, 260 760 C 160 820, -20 840, -60 800 Z" fill="@night-raised" opacity="0.9"/>'
        '<path d="M-30 560 C 50 530, 160 545, 240 590 C 300 625, 290 690, 210 735 C 130 780, -10 790, -40 760 Z" fill="@mimi" opacity="0.07"/>'
    )


def shooting_star(x, y, length, angle):
    a = math.radians(angle)
    x2, y2 = x - length * math.cos(a), y - length * math.sin(a)
    return tok(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x2)}" y2="{f(y2)}" stroke="@moon" stroke-width="2" stroke-linecap="round" opacity="0.5"/>'
               f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x - length * 0.4 * math.cos(a))}" y2="{f(y - length * 0.4 * math.sin(a))}" '
               'stroke="@highlight" stroke-width="2.6" stroke-linecap="round" opacity="0.85"/>'
               f'<circle cx="{f(x)}" cy="{f(y)}" r="2.6" fill="@highlight"/>')


def galaxy(x, y, rot, scale, kind="lilac", seed=1):
    """A spiral galaxy: soft glow, two arms, a scatter of stars and a bright core."""
    outer, inner = {"lilac": ("mimi", "galaxy"), "peach": ("peach", "galaxy-peach"), "mint": ("mint", "galaxy-mint")}[kind]
    rnd = random.Random(seed)
    dots = []
    for side in (1, -1):
        for i in range(9):
            t = 0.15 + i * 0.1
            ang = t * 2.6
            rr = 10 + t * 40
            px, py = side * rr * math.cos(ang), side * rr * math.sin(ang) * 0.36
            dots.append(f'<circle cx="{f(px + rnd.uniform(-2, 2))}" cy="{f(py + rnd.uniform(-1, 1))}" r="{f(rnd.uniform(0.8, 1.6))}" '
                        f'fill="@moon" opacity="{f(rnd.uniform(0.5, 0.95))}"/>')
    return tok(f'<g transform="translate({x} {y}) rotate({rot}) scale({scale})">'
               f'<ellipse rx="58" ry="20" fill="@{outer}" opacity="0.13"/>'
               f'<ellipse rx="44" ry="15" fill="@{outer}" opacity="0.18"/>'
               f'<ellipse rx="30" ry="10" fill="@{inner}" opacity="0.32"/>'
               f'<path d="M0 0 C 16 -12, 38 -11, 50 3" fill="none" stroke="@{inner}" stroke-width="4" stroke-linecap="round" opacity="0.45"/>'
               f'<path d="M0 0 C -16 12, -38 11, -50 -3" fill="none" stroke="@{inner}" stroke-width="4" stroke-linecap="round" opacity="0.45"/>'
               f'<path d="M4 -2 C 22 -16, 46 -10, 56 8" fill="none" stroke="@{inner}" stroke-width="1.6" stroke-linecap="round" opacity="0.35"/>'
               f'<path d="M-4 2 C -22 16, -46 10, -56 -8" fill="none" stroke="@{inner}" stroke-width="1.6" stroke-linecap="round" opacity="0.35"/>'
               + "".join(dots) +
               '<ellipse rx="14" ry="5.5" fill="@moon" opacity="0.85"/>'
               '<ellipse rx="6" ry="2.6" fill="@highlight" opacity="0.9"/>'
               '</g>')


RAMPS = {
    "indigo": ["planet-indigo-light", "planet-indigo-2", "planet-indigo", "planet-indigo-4", "planet-indigo-dark", "planet-indigo-6"],
    "peach": ["planet-peach-light", "planet-peach-2", "planet-peach", "planet-peach-4", "planet-peach-dark", "planet-peach-6"],
    "mint": ["planet-mint-light", "planet-mint-2", "planet-mint", "planet-mint-4", "planet-mint-dark", "planet-mint-6"],
}


def planet(cx, cy, r, ramp, uid, bands=5, craters=(), ring=False, rim=True):
    """A banded planet: hard bands, light at the top left, darkest at the bottom right, no outline.
    craters: (dx, dy, size) as fractions of r. ring: a striped ring, its back half behind the planet. uid names the clip."""
    cols = RAMPS[ramp][:max(3, min(bands, 6))]
    d = 2 * r
    edges = [0.18, 0.36, 0.55, 0.72, 0.86][: len(cols) - 1] if len(cols) > 3 else [0.3, 0.674]
    out = [f'<clipPath id="{uid}"><circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"/></clipPath>',
           f'<g clip-path="url(#{uid})"><g transform="rotate(-45 {f(cx)} {f(cy)})">']
    x0, y0 = cx - r, cy - r
    out.append(f'<rect x="{f(x0)}" y="{f(y0)}" width="{f(d)}" height="{f(d)}" fill="@{cols[-1]}"/>')
    for i in range(len(cols) - 2, -1, -1):
        out.append(f'<rect x="{f(x0)}" y="{f(y0)}" width="{f(d)}" height="{f(d * edges[i])}" fill="@{cols[i]}"/>')
    out.append('</g>')
    for (dx, dy, cr) in craters:
        x, y = cx + dx * r, cy + dy * r
        out.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(cr * r)}" ry="{f(cr * r * 0.78)}" fill="@shadow" opacity="0.16"/>')
        out.append(f'<ellipse cx="{f(x - cr * r * 0.18)}" cy="{f(y - cr * r * 0.18)}" rx="{f(cr * r * 0.72)}" ry="{f(cr * r * 0.5)}" fill="@highlight" opacity="0.07"/>')
    out.append('</g>')
    if rim:
        out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r + 2.5)}" fill="none" stroke="@{cols[0]}" stroke-width="3" opacity="0.28"/>')
    body = "".join(out)
    if not ring:
        return tok(body)
    rx, ry, tilt = r * 1.75, r * 0.38, -14

    def arc(sweep, width, colour, op=1.0, scale=1.0):
        a, b = rx * scale, ry * scale
        o = "" if op == 1.0 else f' opacity="{op}"'
        return (f'<path d="M{f(cx - a)} {f(cy)} A{f(a)} {f(b)} 0 0 {sweep} {f(cx + a)} {f(cy)}" fill="none" stroke="@{colour}" '
                f'stroke-width="{f(width)}" stroke-linecap="round"{o}/>')
    g0 = f'<g transform="rotate({tilt} {f(cx)} {f(cy)})">'
    back = g0 + arc(1, r * 0.16, "mint-deep") + arc(1, r * 0.05, "mint-deeper", 1, 0.86) + '</g>'
    front = g0 + arc(0, r * 0.16, "mint") + arc(0, r * 0.06, "mint-light", 1, 1.08) + arc(0, r * 0.045, "mint-deep", 0.9, 0.86) + '</g>'
    shadow = (f'<g clip-path="url(#{uid})"><g transform="rotate({tilt} {f(cx)} {f(cy)})">'
              f'<path d="M{f(cx - rx * 0.95)} {f(cy + r * 0.05)} A{f(rx * 0.95)} {f(ry * 0.9)} 0 0 0 {f(cx + rx * 0.95)} {f(cy + r * 0.05)}" fill="none" '
              f'stroke="@shadow" stroke-width="{f(r * 0.12)}" opacity="0.18"/></g></g>')
    return tok(back + body + shadow + front)


SKY_CLEAR = [(255, 80, 250, 250), (75, 335, 270, 270), (415, 335, 270, 270), (150, 600, 450, 100), (735, 505, 545, 285)]


def sky_art(uid="sky"):
    """The night sky behind every screen, as SVG content for a 1280 × 800 view. Planets, galaxies and bright stars keep
    to the corners and edges, clear of what the start, game and end screens put on top; the starfield stays out of the
    diagram, the equation and the tray."""
    return (
        nebula()
        + starfield(7, 120, SKY_CLEAR)
        + galaxy(640, 160, -18, 0.85, "lilac", 3) + galaxy(915, 48, 26, 0.6, "peach", 5) + galaxy(64, 300, -40, 0.62, "mint", 9)
        + cross_star(216, 330, 0.9) + cross_star(742, 196, 0.7) + cross_star(1238, 470, 0.8)
        + spark(560, 92, 0.6) + spark(30, 640, 0.7) + spark(705, 760, 0.6)
        + shooting_star(250, 104, 80, 30)
        + planet(60, 830, 175, "indigo", f"{uid}-a", bands=6, craters=[(0.25, -0.62, 0.11), (0.55, -0.35, 0.07), (0.05, -0.85, 0.06), (0.62, -0.68, 0.05)])
        + planet(44, 548, 13, "mint", f"{uid}-m", bands=4, craters=[(0.2, -0.1, 0.25)], rim=False)
        + planet(150, 215, 32, "peach", f"{uid}-b", bands=5, ring=True)
        + planet(790, 250, 18, "mint", f"{uid}-c", bands=4, craters=[(-0.2, 0.25, 0.22)])
        + planet(822, 232, 4.5, "indigo", f"{uid}-d", bands=3, rim=False)
    )


# ---------------------------------------------------------------- the asteroid tray (520 × 260, a ten-frame of slots)

ASTEROID = "M30 120 C 20 60, 90 20, 170 28 C 250 14, 350 30, 375 90 C 398 150, 362 210, 280 214 C 200 226, 110 222, 60 200 C 30 186, 34 160, 30 120 Z"
TRAY_SLOTS = [(82 + i * 94, ry) for ry in (85, 180) for i in range(5)]


def asteroid(w=520, h=260, uid="rock"):
    """The rock itself: lit top, shaded underside, cracks and craters, ink outline."""
    sx, sy = w / 400, h / 232
    craters = "".join(
        f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="@asteroid-deep"/>'
        f'<path d="M{x - rx} {y} A{rx} {ry} 0 0 0 {x + rx} {y}" fill="none" stroke="@asteroid-light" stroke-width="2" opacity="0.8"/>'
        for (x, y, rx, ry) in [(36, 160, 12, 5), (500, 70, 10, 4), (470, 228, 14, 5), (20, 220, 7, 3)])
    return tok(
        f'<clipPath id="{uid}"><path transform="scale({sx:.3f} {sy:.3f})" d="{ASTEROID}"/></clipPath>'
        f'<path transform="scale({sx:.3f} {sy:.3f})" d="{ASTEROID}" fill="@asteroid"/>'
        f'<g clip-path="url(#{uid})">'
        '<path d="M0 40 C 120 0, 380 -10, 540 60 L 540 0 L 0 0 Z" fill="@asteroid-light"/>'
        '<path d="M0 230 C 140 270, 380 260, 540 190 L 540 300 L 0 300 Z" fill="@asteroid-crater"/>'
        '<path d="M60 120 L 110 112 M 230 132 L 300 140 M 380 120 L 440 108" stroke="@asteroid-crater" stroke-width="3" stroke-linecap="round" opacity="0.7"/>'
        + craters + '</g>'
        f'<path transform="scale({sx:.3f} {sy:.3f})" d="{ASTEROID}" fill="none" stroke="@ink" stroke-width="4.5"/>'
    )


def tray(uid="tray"):
    """The asteroid tray as a whole drawing: the rock, its ten slots and a few pebbles drifting beside it.
    The pebbles sit just outside the 520 × 260 box, so the SVG lets them show (overflow visible)."""
    slots = "".join(
        f'<circle cx="{x}" cy="{y}" r="34" fill="@asteroid-crater" opacity="0.75"/>'
        f'<path d="M{x - 34} {y} A34 34 0 0 1 {x + 34} {y}" fill="none" stroke="@asteroid-deep" stroke-width="3" opacity="0.9"/>'
        f'<path d="M{x - 30} {y + 14} A34 34 0 0 0 {x + 30} {y + 14}" fill="none" stroke="@asteroid-light" stroke-width="2" opacity="0.7"/>'
        for (x, y) in TRAY_SLOTS)
    pebbles = "".join(
        f'<path transform="translate({x} {y}) scale({s})" d="M-8 -2 C -7 -8, 4 -9, 8 -3 C 11 3, 4 8, -2 7 C -8 6, -9 2, -8 -2 Z" fill="@asteroid" stroke="@ink" stroke-width="2"/>'
        f'<path transform="translate({x} {y}) scale({s})" d="M-5 -3 C -3 -6, 3 -6, 5 -3" fill="none" stroke="@asteroid-light" stroke-width="2"/>'
        for (x, y, s) in [(-14, 60, 1.0), (526, 40, 0.8), (540, 150, 1.3), (-4, 238, 0.7)])
    return ('<svg width="520" height="260" viewBox="0 0 520 260" overflow="visible" aria-hidden="true">'
            + asteroid(520, 260, uid) + tok(slots + pebbles) + '</svg>')


# ---------------------------------------------------------------- Scruffles (head in the 400 × 430 ship's coordinates)

HEAD = ("M200 154 C 240 154, 270 180, 270 208 L 282 220 L 268 228 L 278 242 L 258 248 C 246 264, 224 272, 200 272 "
        "C 176 272, 154 264, 142 248 L 122 242 L 132 228 L 118 220 L 130 208 C 130 180, 160 154, 200 154 Z")
BLAZE = ("M200 166 C 204 186, 208 202, 212 212 C 220 224, 240 228, 248 244 C 252 260, 230 270, 200 270 "
         "C 170 270, 148 260, 152 244 C 160 228, 180 224, 188 212 C 192 202, 196 186, 200 166 Z")


def scruffles_head(uid="s"):
    """Ears, grey head with a darker crown and cheek fur, the white blaze, and the outline. The face goes on top."""
    g = []
    for side in (-1, 1):
        def X(x):
            return 200 + side * (x - 200)
        g.append(f'<path d="M{X(140)} 198 L{X(142)} 144 L{X(174)} 164 Z" fill="@scruffles-grey" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>')
        g.append(f'<path d="M{X(147)} 188 L{X(148)} 158 L{X(167)} 171 Z" fill="@ear-pink"/>')
        g.append(f'<path d="M{X(149)} 186 L{X(155)} 174 M{X(152)} 188 L{X(160)} 178 M{X(156)} 189 L{X(163)} 182" stroke="@cat-white" stroke-width="2" stroke-linecap="round"/>')
    g.append(f'<clipPath id="{uid}-head"><path d="{HEAD}"/></clipPath>')
    g.append(f'<path d="{HEAD}" fill="@scruffles-grey"/>')
    g.append(f'<g clip-path="url(#{uid}-head)">'
             '<ellipse cx="200" cy="150" rx="78" ry="30" fill="@scruffles-grey-dark" opacity="0.55"/>'
             '<path d="M126 214 C 136 206, 146 204, 154 206 M124 226 C 134 220, 144 220, 152 222 M276 214 C 266 206, 256 204, 248 206 M278 226 C 268 220, 258 220, 250 222" '
             'stroke="@scruffles-grey-dark" stroke-width="2.4" stroke-linecap="round" fill="none"/>'
             '<path d="M168 168 C 174 172, 176 178, 176 184 M232 168 C 226 172, 224 178, 224 184" stroke="@scruffles-grey-light" stroke-width="2.4" stroke-linecap="round" fill="none"/>'
             '</g>')
    g.append(f'<clipPath id="{uid}-blaze"><path d="{BLAZE}"/></clipPath>')
    g.append(f'<path d="{BLAZE}" fill="@cat-white"/>')
    g.append(f'<g clip-path="url(#{uid}-blaze)"><ellipse cx="200" cy="274" rx="46" ry="14" fill="@white-shade"/></g>')
    g.append(f'<path d="{HEAD}" fill="none" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>')
    return tok("".join(g))


def _scruffles_eye(ex, cy, look=-2):
    return (f'<ellipse cx="{ex}" cy="{cy}" rx="12.5" ry="13.5" fill="@scruffles-eye" stroke="@ink" stroke-width="2.5"/>'
            f'<ellipse cx="{ex}" cy="{cy + 2}" rx="9" ry="10" fill="none" stroke="@scruffles-eye-dark" stroke-width="2" opacity="0.7"/>'
            f'<ellipse cx="{ex + look}" cy="{cy + 1}" rx="4.6" ry="9.5" fill="@ink"/>'
            f'<circle cx="{ex + look - 4}" cy="{cy - 6}" r="3.4" fill="@highlight"/><circle cx="{ex + look + 5}" cy="{cy + 7}" r="1.5" fill="@highlight"/>')


def _faces():
    thinking = "".join(
        _scruffles_eye(ex, 212)
        + f'<path d="M{ex - 13} 205 C {ex - 8} 197, {ex + 8} 197, {ex + 13} 205" fill="none" stroke="@ink" stroke-width="3" stroke-linecap="round"/>'
        for ex in (172, 228))
    thinking += '<path d="M190 250 C 194 256, 200 254, 200 246 C 200 254, 206 256, 210 250" fill="none" stroke="@ink" stroke-width="3" stroke-linecap="round"/>'

    got_it = ""
    for ex in (172, 228):
        out = -1 if ex < 200 else 1
        got_it += (f'<path d="M{ex - 13} 216 C {ex - 9} 202, {ex + 9} 202, {ex + 13} 216" fill="none" stroke="@ink" stroke-width="5" stroke-linecap="round"/>'
                   f'<path d="M{ex + 14 * out} 210 l{5 * out} -4" stroke="@ink" stroke-width="2.6" stroke-linecap="round"/>'
                   f'<ellipse cx="{ex + 8 * out}" cy="238" rx="11" ry="6" fill="@nose-pink" opacity="0.55"/>')
    got_it += ('<path d="M186 246 C 188 268, 212 268, 214 246 Z" fill="@mouth" stroke="@ink" stroke-width="3" stroke-linejoin="round"/>'
               '<path d="M193 258 C 196 252, 204 252, 207 258 C 204 263, 196 263, 193 258 Z" fill="@tongue"/>')

    # try again: kind, raised brows and a small smile; looking at the player, never cross
    try_again = "".join(_scruffles_eye(ex, 213, 0) for ex in (172, 228))
    try_again += ('<path d="M157 195 C 163 188, 176 187, 185 192" fill="none" stroke="@ink" stroke-width="3.5" stroke-linecap="round"/>'
                  '<path d="M215 192 C 224 187, 237 188, 243 195" fill="none" stroke="@ink" stroke-width="3.5" stroke-linecap="round"/>'
                  '<path d="M189 250 C 194 257, 206 257, 211 250" fill="none" stroke="@ink" stroke-width="3" stroke-linecap="round"/>')
    return {"thinking": tok(thinking), "got-it": tok(got_it), "try-again": tok(try_again)}


FACES = _faces()


def scruffles_muzzle():
    """Nose, whiskers and the headset (band, two ear cups, mic): drawn over the face."""
    g = ['<path d="M191 231 L209 231 L200 241 Z" fill="@nose-pink" stroke="@ink" stroke-width="2.5" stroke-linejoin="round"/>',
         '<path d="M196 234 C 198 235, 202 235, 204 234" stroke="@nose-pink-dark" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
         '<path d="M216 243 C 236 238, 254 236, 270 236 M216 249 C 236 249, 254 252, 270 256 M216 255 C 234 258, 250 264, 262 270" '
         'fill="none" stroke="@ink" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>',
         '<path d="M184 243 C 170 240, 160 239, 148 240 M184 249 C 172 250, 162 252, 150 255" fill="none" stroke="@ink" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>',
         '<path d="M126 220 C 116 240, 128 258, 156 260" fill="none" stroke="@teal-band" stroke-width="5" stroke-linecap="round"/>']
    for cx in (124, 276):
        g.append(f'<circle cx="{cx}" cy="212" r="14" fill="@mint" stroke="@ink" stroke-width="4"/>'
                 f'<circle cx="{cx}" cy="212" r="7.5" fill="@mint-dark" stroke="@mint-deep" stroke-width="2"/>'
                 f'<circle cx="{cx + (-4 if cx < 200 else 4)}" cy="207" r="2.4" fill="@peach"/>')
    g.append('<rect x="153" y="253" width="14" height="12" rx="6" fill="@peach" stroke="@ink" stroke-width="3"/>'
             '<path d="M156 257 h8 M156 261 h8" stroke="@peach-dark" stroke-width="1.5"/>')
    return tok("".join(g))


def _face_slot(face):
    """One face, or all three in data-face groups (the kit shows one at a time)."""
    if face == "all":
        return "".join(f'<g data-face="{name}">{svg}</g>' for name, svg in FACES.items())
    return FACES[face]


def scruffles_whole_head(face="thinking", uid="s"):
    return scruffles_head(uid) + _face_slot(face) + scruffles_muzzle()


def scruffles_shoulders():
    """Grey shoulders and the fluffy white chest, seen in the cockpit."""
    return tok(
        '<path d="M118 304 C 118 280, 128 262, 146 254 L 254 254 C 272 262, 282 280, 282 304 Z" fill="@scruffles-grey" stroke="@ink" stroke-width="4.5" stroke-linejoin="round"/>'
        '<path d="M136 252 L148 266 L160 254 L172 270 L186 256 L200 272 L214 256 L228 270 L240 254 L252 266 L264 252 L276 304 L124 304 Z" fill="@cat-white" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M152 286 C 156 280, 162 278, 166 282 M180 290 C 184 284, 190 282, 194 286 M206 286 C 210 280, 216 278, 220 282 M234 290 C 238 284, 244 282, 248 286" '
        'fill="none" stroke="@white-shade" stroke-width="3" stroke-linecap="round"/>'
    )


# ---------------------------------------------------------------- the rescue ship (viewBox 0 0 400 430)

RIM_LIGHTS = [(200 + 172 * math.cos(t), 304 + 22 * math.sin(t)) for t in [math.pi * (0.1 + 0.8 * i / 8) for i in range(9)]]


def scruffles_pod(face="thinking", w=400, uid="ship"):
    """Scruffles in the rescue ship. face: thinking, got-it, try-again, or all (the kit switches them).

    The lights (nine round the rim and the beacon on the antenna) carry classes the kit animates after a right
    answer: mw-ship-light and mw-ship-glow in three groups (mw-ship-p0/1/2) chasing round, mw-ship-beacon and
    mw-ship-beacon-glow. Unlit, they're hidden (opacity 0) and the peach lights underneath show."""
    h = w * 430 / 400
    s = [f'<svg width="{f(w)}" height="{f(h)}" viewBox="0 0 400 430" aria-hidden="true">']
    b = []   # behind Scruffles
    b.append('<ellipse cx="200" cy="420" rx="150" ry="10" fill="@mint" opacity="0.14"/>')
    # thruster flames
    for tx in (160, 240):
        b.append(f'<path d="M{tx - 13} 384 C {tx - 12} 402, {tx - 4} 414, {tx} 422 C {tx + 4} 414, {tx + 12} 402, {tx + 13} 384 Z" fill="@peach" opacity="0.9"/>')
        b.append(f'<path d="M{tx - 6} 384 C {tx - 6} 396, {tx - 2} 404, {tx} 410 C {tx + 2} 404, {tx + 6} 396, {tx + 6} 384 Z" fill="@spark"/>')
    # landing legs
    for side in (-1, 1):
        x1, x2 = 200 + side * 92, 200 + side * 118
        b.append(f'<path d="M{x1} 356 L{x2} 400" stroke="@ink" stroke-width="13" stroke-linecap="round"/>')
        b.append(f'<path d="M{x1} 356 L{x2} 400" stroke="@peach" stroke-width="7" stroke-linecap="round"/>')
        b.append(f'<circle cx="{200 + side * 104}" cy="378" r="3" fill="@peach-dark"/>')
        b.append(f'<ellipse cx="{x2 + side * 2}" cy="404" rx="20" ry="7" fill="@mint-dark" stroke="@ink" stroke-width="4"/>')
    # side fins with a peach stripe
    for side in (-1, 1):
        def X(v):
            return 200 + side * (v - 200)
        fin = f"M{X(46)} 322 C {X(18)} 332, {X(2)} 358, {X(8)} 386 C {X(34)} 374, {X(58)} 358, {X(78)} 344 Z"
        b.append(f'<path d="{fin}" fill="@mint" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>')
        b.append(f'<path d="M{X(30)} 346 C {X(22)} 356, {X(16)} 366, {X(14)} 376" stroke="@peach" stroke-width="6" stroke-linecap="round" fill="none"/>')
    # cockpit: seat, Scruffles, console, glass, frame
    b.append(f'<clipPath id="{uid}-dome"><path d="M30 304 A170 170 0 0 1 370 304 Z"/></clipPath>')
    b.append(f'<g clip-path="url(#{uid}-dome)">'
             '<path d="M30 304 A170 170 0 0 1 370 304 Z" fill="@night" opacity="0.35"/>'
             '<rect x="104" y="236" width="192" height="90" rx="30" fill="@teal-band" opacity="0.9"/>'
             '<rect x="114" y="244" width="172" height="10" rx="5" fill="@mint-deeper"/>'
             '</g>')
    s.append(tok("".join(b)))
    s.append(scruffles_shoulders())
    s.append(scruffles_whole_head(face, uid))
    t = []
    t.append(f'<g clip-path="url(#{uid}-dome)">'
             '<rect x="30" y="286" width="340" height="22" fill="@ink" opacity="0.55"/>'
             + "".join(f'<circle cx="{cx}" cy="296" r="3" fill="@{col}"/>' for cx, col in
                       [(70, "mint"), (84, "peach"), (98, "spark"), (302, "spark"), (316, "mint"), (330, "peach")]) +
             '<path d="M30 304 A170 170 0 0 1 370 304 Z" fill="@glass" opacity="0.2"/>'
             '</g>')
    t.append('<path d="M72 254 C 86 202, 124 166, 170 154" fill="none" stroke="@cat-white" stroke-width="8" stroke-linecap="round" opacity="0.45"/>')
    t.append('<path d="M84 278 C 88 266, 92 258, 98 250" fill="none" stroke="@cat-white" stroke-width="5" stroke-linecap="round" opacity="0.35"/>')
    t.append('<circle cx="300" cy="186" r="5" fill="@cat-white" opacity="0.4"/>')
    t.append('<path d="M44 304 A156 156 0 0 1 356 304" fill="none" stroke="@mint" stroke-width="2.4" opacity="0.4"/>')
    for ang in (150, 30):
        a = math.radians(ang)
        t.append(f'<line x1="{f(200 + 140 * math.cos(a))}" y1="{f(304 - 140 * math.sin(a))}" x2="{f(200 + 170 * math.cos(a))}" '
                 f'y2="{f(304 - 170 * math.sin(a))}" stroke="@ink" stroke-width="5" stroke-linecap="round"/>')
    t.append('<path d="M30 304 A170 170 0 0 1 370 304" fill="none" stroke="@ink" stroke-width="6"/>')
    # antenna and beacon
    t.append('<line x1="200" y1="134" x2="200" y2="100" stroke="@ink" stroke-width="6" stroke-linecap="round"/>')
    t.append('<ellipse cx="200" cy="118" rx="9" ry="3.5" fill="@mint-dark" stroke="@ink" stroke-width="2.5"/>')
    t.append('<circle cx="200" cy="92" r="11" fill="@peach-dark" stroke="@ink" stroke-width="4"/>')
    t.append('<circle cx="200" cy="92" r="7" fill="@peach"/>')
    t.append('<circle class="mw-ship-beacon-glow" cx="200" cy="92" r="16" fill="@spark" opacity="0"/>')
    t.append('<circle class="mw-ship-beacon" cx="200" cy="92" r="7" fill="@spark" opacity="0"/>')
    t.append('<circle cx="196" cy="88" r="2.4" fill="@highlight" opacity="0.8"/>')
    # hull: four hard bands, panel lines, rivets
    hull = "M24 304 C 34 372, 120 394, 200 394 C 280 394, 366 372, 376 304 Z"
    t.append(f'<clipPath id="{uid}-hull"><path d="{hull}"/></clipPath>')
    t.append(f'<g clip-path="url(#{uid}-hull)">'
             '<rect x="0" y="300" width="400" height="100" fill="@mint-deep"/>'
             '<path d="M0 300 H400 V372 C 300 386, 100 386, 0 372 Z" fill="@mint-dark"/>'
             '<path d="M0 300 H400 V350 C 300 362, 100 362, 0 350 Z" fill="@mint"/>'
             '<path d="M0 300 H400 V326 C 300 334, 100 334, 0 326 Z" fill="@mint-light"/>'
             '<path d="M112 316 C 108 340, 112 366, 122 392 M288 316 C 292 340, 288 366, 278 392 M60 318 C 62 336, 70 352, 82 368 M340 318 C 338 336, 330 352, 318 368" '
             'fill="none" stroke="@ink" stroke-width="2" opacity="0.3"/>'
             + "".join(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="2.2" fill="@mint-deeper"/>'
                       for cx, cy in [(70, 344), (96, 352), (124, 358), (276, 358), (304, 352), (330, 344), (150, 378), (250, 378)]) +
             '</g>')
    t.append(f'<path d="{hull}" fill="none" stroke="@ink" stroke-width="6" stroke-linejoin="round"/>')
    for hx in (62, 338):
        t.append(f'<ellipse cx="{hx}" cy="334" rx="9" ry="6" fill="@spark" stroke="@ink" stroke-width="2.5"/>')
    # paw-print badge
    t.append('<circle cx="200" cy="362" r="18" fill="@peach" stroke="@ink" stroke-width="3.5"/>')
    t.append('<ellipse cx="200" cy="367" rx="7" ry="5.5" fill="@numeral"/>')
    t.append("".join(f'<ellipse cx="{f(200 + dx)}" cy="{f(357 + dy)}" rx="2.6" ry="3.2" fill="@numeral"/>' for dx, dy in [(-8, 2), (-3, -3), (3, -3), (8, 2)]))
    # rim with its ring of lights
    t.append('<ellipse cx="200" cy="304" rx="178" ry="20" fill="@mint-dark" stroke="@ink" stroke-width="6"/>')
    t.append('<ellipse cx="200" cy="300" rx="164" ry="11" fill="none" stroke="@mint-light" stroke-width="2.4" opacity="0.8"/>')
    for i, (lx, ly) in enumerate(RIM_LIGHTS):
        p = f"mw-ship-p{i % 3}"
        t.append(f'<circle cx="{f(lx)}" cy="{f(ly)}" r="7" fill="@peach-dark" stroke="@ink" stroke-width="2.5"/>')
        t.append(f'<circle cx="{f(lx)}" cy="{f(ly)}" r="5" fill="@peach"/>')
        t.append(f'<circle class="mw-ship-glow {p}" cx="{f(lx)}" cy="{f(ly)}" r="14" fill="@spark" opacity="0"/>')
        t.append(f'<circle class="mw-ship-light {p}" cx="{f(lx)}" cy="{f(ly)}" r="5.5" fill="@{"spark" if i % 2 else "mint-light"}" opacity="0"/>')
        t.append(f'<circle cx="{f(lx - 2)}" cy="{f(ly - 2)}" r="1.5" fill="@highlight" opacity="0.8"/>')
    s.append(tok("".join(t)))
    s.append('</svg>')
    return "".join(s)


def scruffles_face(face, w=170, uid="face"):
    """Scruffles's head on its own (for the design system's face sheet)."""
    h = w * 160 / 180
    return (f'<svg width="{w}" height="{h:.0f}" viewBox="110 136 180 160" aria-hidden="true">'
            + scruffles_whole_head(face, uid) + '</svg>')


def scruffles_standing(w=320, uid="stand"):
    """Scruffles standing (viewBox 0 0 320 400): grey with a white chest and front legs, striped tail, headset."""
    h = w * 400 / 320
    tail = "M222 356 C 296 356, 306 280, 262 252"
    body = "M92 372 C 74 316, 88 230, 160 206 C 232 230, 246 316, 228 372 Z"
    chest = "M108 216 C 120 226, 132 222, 146 230 C 154 224, 166 224, 174 230 C 188 222, 200 226, 212 216 C 222 266, 204 334, 160 344 C 116 334, 98 266, 108 216 Z"
    art = (
        '<ellipse cx="160" cy="388" rx="110" ry="9" fill="@mint" opacity="0.16"/>'
        f'<path d="{tail}" fill="none" stroke="@ink" stroke-width="38" stroke-linecap="round"/>'
        f'<path d="{tail}" fill="none" stroke="@scruffles-grey" stroke-width="28" stroke-linecap="round"/>'
        '<path d="M280 300 C 290 296, 296 290, 298 282 M268 336 C 280 334, 290 326, 294 318" fill="none" stroke="@scruffles-grey-dark" stroke-width="5" stroke-linecap="round"/>'
        f'<clipPath id="{uid}-body"><path d="{body}"/></clipPath>'
        f'<path d="{body}" fill="@scruffles-grey"/>'
        f'<g clip-path="url(#{uid}-body)">'
        '<path d="M86 260 C 92 300, 96 340, 104 372 M234 260 C 228 300, 224 340, 216 372" fill="none" stroke="@scruffles-grey-dark" stroke-width="10" stroke-linecap="round" opacity="0.6"/>'
        f'<path d="{chest}" fill="@cat-white"/>'
        '<path d="M140 262 C 146 254, 154 254, 158 260 M162 260 C 166 254, 174 254, 180 262 M150 290 C 156 282, 164 282, 170 290" fill="none" stroke="@white-shade" stroke-width="3" stroke-linecap="round"/>'
        '</g>'
        f'<path d="{body}" fill="none" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>'
        '<rect x="122" y="310" width="30" height="62" rx="14" fill="@cat-white" stroke="@ink" stroke-width="5"/>'
        '<rect x="168" y="310" width="30" height="62" rx="14" fill="@cat-white" stroke="@ink" stroke-width="5"/>'
        '<ellipse cx="137" cy="372" rx="22" ry="11" fill="@cat-white" stroke="@ink" stroke-width="5"/>'
        '<ellipse cx="183" cy="372" rx="22" ry="11" fill="@cat-white" stroke="@ink" stroke-width="5"/>'
        '<path d="M130 368 v7 M137 367 v8 M144 368 v7 M176 368 v7 M183 367 v8 M190 368 v7" stroke="@white-shade" stroke-width="2.4" stroke-linecap="round"/>'
    )
    return (f'<svg width="{w}" height="{h:.0f}" viewBox="0 0 320 400" aria-hidden="true">' + tok(art)
            + f'<g transform="translate(-40 -58)">{scruffles_whole_head("thinking", uid)}</g></svg>')


# ---------------------------------------------------------------- Moggles and Snuffles, standing (viewBox 0 0 260 340)

CAT_HEAD = ("M130 64 C 170 64, 196 92, 196 120 L 207 128 L 195 134 L 203 146 L 189 150 C 179 168, 157 180, 130 180 "
            "C 103 180, 81 168, 71 150 L 57 146 L 65 134 L 53 128 L 64 120 C 64 92, 90 64, 130 64 Z")
CAT_BODY = "M74 326 C 60 280, 70 206, 130 190 C 190 206, 200 280, 186 326 Z"


def _cat_eye(cx, cy, iris, line):
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="15" ry="13.5" fill="@{iris}"/>'
            f'<ellipse cx="{cx}" cy="{cy + 1}" rx="10.5" ry="9.5" fill="none" stroke="@{iris}-dark" stroke-width="2" opacity="0.6"/>'
            f'<ellipse cx="{cx}" cy="{cy + 1}" rx="4.6" ry="10.5" fill="@ink"/>'
            f'<circle cx="{cx - 5}" cy="{cy - 6}" r="3.6" fill="@highlight"/><circle cx="{cx + 4}" cy="{cy + 6}" r="1.6" fill="@highlight"/>'
            f'<path d="M{cx - 16} {cy - 5} C {cx - 10} {cy - 15}, {cx + 10} {cy - 15}, {cx + 16} {cy - 5}" fill="none" stroke="@{line}" stroke-width="3" stroke-linecap="round"/>')


def cat(kind="moggles", w=260, uid=None):
    """kind: moggles (all black, peach scarf) or snuffles (black and white, a black patch on one leg, mint collar)."""
    uid = uid or kind
    h = w * 340 / 260
    s = ['<ellipse cx="130" cy="332" rx="92" ry="8" fill="@mint" opacity="0.16"/>']
    tail = "M186 316 C 246 316, 252 248, 214 228"
    s.append(f'<path d="{tail}" fill="none" stroke="@moggles-rim" stroke-width="30" stroke-linecap="round"/>')
    s.append(f'<path d="{tail}" fill="none" stroke="@moggles-black" stroke-width="20" stroke-linecap="round"/>')
    s.append('<path d="M226 300 C 238 286, 240 266, 232 250 M214 312 C 228 306, 236 296, 240 284" fill="none" stroke="@fur-shade" stroke-width="3" stroke-linecap="round"/>')
    s.append(f'<clipPath id="{uid}-body"><path d="{CAT_BODY}"/></clipPath>')
    s.append(f'<path d="{CAT_BODY}" fill="@moggles-black"/>')
    if kind == "snuffles":
        s.append(f'<g clip-path="url(#{uid}-body)">'
                 '<path d="M100 202 C 116 214, 144 214, 160 202 C 172 248, 160 298, 130 312 C 100 298, 88 248, 100 202 Z" fill="@cat-white"/>'
                 '<path d="M108 270 C 116 290, 144 290, 152 270 C 150 292, 142 304, 130 310 C 118 304, 110 292, 108 270 Z" fill="@white-shade"/>'
                 '<path d="M118 222 C 120 230, 124 234, 128 238 M142 222 C 140 230, 136 234, 132 238 M130 226 L130 242" fill="none" stroke="@white-shade" stroke-width="2.6" stroke-linecap="round"/>'
                 '</g>')
    else:
        s.append(f'<g clip-path="url(#{uid}-body)">'
                 '<path d="M116 228 C 118 236, 122 242, 127 246 M144 228 C 142 236, 138 242, 133 246 M130 234 L130 252 M108 244 C 110 252, 114 258, 118 262 M152 244 C 150 252, 146 258, 142 262" '
                 'fill="none" stroke="@fur-shade" stroke-width="3" stroke-linecap="round"/>'
                 '<path d="M96 260 C 98 280, 102 300, 108 316 M164 260 C 162 280, 158 300, 152 316" fill="none" stroke="@fur-shade" stroke-width="4" stroke-linecap="round"/>'
                 '</g>')
    s.append(f'<path d="{CAT_BODY}" fill="none" stroke="@moggles-rim" stroke-width="5" stroke-linejoin="round"/>')
    # front legs and paws with toes
    if kind == "snuffles":
        s.append('<rect x="104" y="262" width="26" height="60" rx="12" fill="@cat-white"/>'
                 '<rect x="104" y="284" width="26" height="22" fill="@moggles-black"/>'
                 '<rect x="104" y="262" width="26" height="60" rx="12" fill="none" stroke="@ink" stroke-width="4"/>'
                 '<rect x="132" y="262" width="26" height="60" rx="12" fill="@cat-white" stroke="@ink" stroke-width="4"/>'
                 '<ellipse cx="117" cy="324" rx="17" ry="9" fill="@cat-white" stroke="@ink" stroke-width="4"/>'
                 '<ellipse cx="145" cy="324" rx="17" ry="9" fill="@cat-white" stroke="@ink" stroke-width="4"/>'
                 '<path d="M112 320 v6 M118 320 v6 M140 320 v6 M146 320 v6" stroke="@white-shade" stroke-width="2.2" stroke-linecap="round"/>')
    else:
        s.append('<ellipse cx="110" cy="324" rx="20" ry="10" fill="@moggles-black" stroke="@moggles-rim" stroke-width="5"/>'
                 '<ellipse cx="150" cy="324" rx="20" ry="10" fill="@moggles-black" stroke="@moggles-rim" stroke-width="5"/>'
                 '<path d="M104 320 v6 M111 319 v7 M144 320 v6 M151 319 v7" stroke="@fur-shade" stroke-width="2.4" stroke-linecap="round"/>')
    # ears with tufts
    inner = "moggles-ear" if kind == "moggles" else "snuffles-ear"
    for side in (-1, 1):
        def X(v):
            return 130 + side * (v - 130)
        s.append(f'<path d="M{X(78)} 98 L{X(72)} 38 L{X(118)} 72 Z" fill="@moggles-black" stroke="@moggles-rim" stroke-width="5" stroke-linejoin="round"/>')
        s.append(f'<path d="M{X(84)} 88 L{X(80)} 54 L{X(106)} 74 Z" fill="@{inner}"/>')
        s.append(f'<path d="M{X(86)} 86 L{X(92)} 74 M{X(90)} 88 L{X(98)} 78" stroke="@ear-tuft" stroke-width="2" stroke-linecap="round"/>')
    # head with crown fur (and Snuffles's white blaze)
    s.append(f'<clipPath id="{uid}-head"><path d="{CAT_HEAD}"/></clipPath>')
    s.append(f'<path d="{CAT_HEAD}" fill="@moggles-black"/>')
    s.append(f'<g clip-path="url(#{uid}-head)">'
             '<path d="M96 84 C 110 72, 150 72, 164 84" fill="none" stroke="@fur-shade" stroke-width="5" stroke-linecap="round"/>'
             '<path d="M118 70 L120 84 M130 68 L130 84 M142 70 L140 84" stroke="@fur-shade" stroke-width="3" stroke-linecap="round"/>'
             + ('<path d="M130 76 C 134 96, 138 110, 142 118 C 154 128, 172 136, 170 154 C 166 172, 146 178, 130 178 C 114 178, 94 172, 90 154 '
                'C 88 136, 106 128, 118 118 C 122 110, 126 96, 130 76 Z" fill="@cat-white"/>'
                '<ellipse cx="130" cy="180" rx="36" ry="12" fill="@white-shade"/>' if kind == "snuffles" else "") +
             '</g>')
    s.append(f'<path d="{CAT_HEAD}" fill="none" stroke="@moggles-rim" stroke-width="5" stroke-linejoin="round"/>')
    # neckwear
    if kind == "moggles":
        s.append('<path d="M82 182 C 106 198, 154 198, 178 182 L 182 202 C 156 220, 104 220, 78 202 Z" fill="@peach" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>'
                 '<path d="M96 196 L102 206 M116 200 L120 212 M140 200 L138 212 M160 196 L154 206" stroke="@peach-shade" stroke-width="3" stroke-linecap="round"/>'
                 '<path d="M150 206 L 168 250 L 156 246 L 150 256 L 142 240 Z" fill="@peach" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>'
                 '<path d="M150 222 L158 240" stroke="@peach-shade" stroke-width="3" stroke-linecap="round"/>'
                 '<circle cx="148" cy="206" r="7" fill="@peach-shade" stroke="@ink" stroke-width="3"/>')
    else:
        s.append('<path d="M86 184 C 108 198, 152 198, 174 184 L 177 200 C 152 216, 108 216, 83 200 Z" fill="@mint" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>'
                 '<path d="M92 192 C 112 204, 148 204, 168 192" fill="none" stroke="@mint-deep" stroke-width="2.4"/>'
                 '<circle cx="130" cy="214" r="10" fill="@peach" stroke="@ink" stroke-width="3"/>'
                 '<path d="M130 208 L132 212 L136 212.5 L133 215 L134 219 L130 217 L126 219 L127 215 L124 212.5 L128 212 Z" fill="@spark"/>')
    # face
    if kind == "moggles":
        s.append(_cat_eye(104, 118, "moggles-eye", "moggles-rim") + _cat_eye(156, 118, "moggles-eye", "moggles-rim"))
        s.append('<path d="M123 141 L137 141 L130 149 Z" fill="@nose-dark" stroke="@moggles-rim" stroke-width="2" stroke-linejoin="round"/>')
        s.append('<path d="M120 156 C 124 162, 130 160, 130 151 C 130 160, 136 162, 140 156" fill="none" stroke="@moggles-rim" stroke-width="3" stroke-linecap="round"/>')
    else:
        s.append(_cat_eye(106, 114, "snuffles-eye", "moggles-rim") + _cat_eye(154, 114, "snuffles-eye", "moggles-rim"))
        s.append('<path d="M123 139 L137 139 L130 147 Z" fill="@nose-pink" stroke="@ink" stroke-width="2" stroke-linejoin="round"/>')
        s.append('<path d="M120 154 C 124 160, 130 158, 130 149 C 130 158, 136 160, 140 154" fill="none" stroke="@ink" stroke-width="3" stroke-linecap="round"/>')
    s.append('<path d="M110 146 C 90 140, 72 138, 50 140 M110 152 C 90 152, 72 156, 52 164 M110 158 C 92 162, 78 170, 62 180 '
             'M150 146 C 170 140, 188 138, 210 140 M150 152 C 170 152, 188 156, 208 164 M150 158 C 168 162, 182 170, 198 180" '
             'fill="none" stroke="@text-3" stroke-width="2.2" stroke-linecap="round"/>')
    return f'<svg width="{f(w)}" height="{f(h)}" viewBox="0 0 260 340" aria-hidden="true">' + tok("".join(s)) + '</svg>'


def moggles(w=260, uid="moggles"):
    return cat("moggles", w, uid)


def snuffles(w=260, uid="snuffles"):
    return cat("snuffles", w, uid)



# ---------------------------------------------------------------- crew jobs (phase 4, round 4 of the design canvas)
# Four pictures in a 100 x 100 box centred on (50, 50): lookout, engineer, navigator, cook. A cat wears its job as a
# badge (the picture in a moon disc with a mint rim) on its chest.

def job_telescope(tripod=True):
    """A brass-and-mint telescope on a little tripod, pointing up to the right."""
    return (
        ('<path d="M34 66 L22 90 M38 66 L40 92 M42 64 L58 88" stroke="@ink" stroke-width="4" stroke-linecap="round"/>' if tripod else '')
        + '<g transform="rotate(-32 50 52)">'
        '<rect x="14" y="44" width="22" height="16" rx="4" fill="@peach-dark" stroke="@ink" stroke-width="3.5"/>'
        '<rect x="34" y="41" width="30" height="22" rx="4" fill="@mint-dark" stroke="@ink" stroke-width="3.5"/>'
        '<rect x="62" y="37" width="26" height="30" rx="5" fill="@mint" stroke="@ink" stroke-width="3.5"/>'
        '<rect x="44" y="41" width="6" height="22" fill="@peach"/>'
        '<rect x="44" y="41" width="6" height="22" fill="none" stroke="@ink" stroke-width="2"/>'
        '<ellipse cx="88" cy="52" rx="5" ry="15" fill="@glass" stroke="@ink" stroke-width="3.5"/>'
        '<path d="M66 42 h16" stroke="@mint-light" stroke-width="3" stroke-linecap="round"/>'
        '</g>'
        + ('<circle cx="40" cy="64" r="4.5" fill="@ink"/>' if tripod else '')
    )


def job_spanner():
    """An open-ended spanner, corner to corner, with a ring at the other end."""
    return (
        '<g transform="rotate(-45 50 50)">'
        '<path d="M44 34 L56 34 L56 76 L44 76 Z" fill="@steel" stroke="@ink" stroke-width="3.5" stroke-linejoin="round"/>'
        '<path d="M43 9 L43 25 L57 25 L57 9 A20 20 0 1 1 43 9 Z" fill="@steel" stroke="@ink" stroke-width="3.5" stroke-linejoin="round"/>'
        '<circle cx="50" cy="84" r="10" fill="@steel" stroke="@ink" stroke-width="3.5"/>'
        '<circle cx="50" cy="84" r="4" fill="@steel-dark" stroke="@ink" stroke-width="2"/>'
        '<path d="M50 40 L50 70" stroke="@cat-white" stroke-width="2.5" stroke-linecap="round" opacity="0.8"/>'
        '</g>'
    )


def job_star_map():
    """A rolled star map: three stars joined by a dotted route."""
    star5 = "M0 -9 L2.6 -2.8 L9 -2.8 L3.8 1.4 L5.8 8 L0 4 L-5.8 8 L-3.8 1.4 L-9 -2.8 L-2.6 -2.8 Z"
    return (
        '<path d="M18 26 L82 26 L82 78 L18 78 Z" fill="@moon" stroke="@ink" stroke-width="3.5" stroke-linejoin="round"/>'
        '<path d="M12 22 C 12 16, 24 16, 24 22 L24 82 C 24 88, 12 88, 12 82 Z" fill="@moon-dim" stroke="@ink" stroke-width="3.5"/>'
        '<path d="M76 18 C 76 12, 88 12, 88 18 L88 78 C 88 84, 76 84, 76 78 Z" fill="@moon-dim" stroke="@ink" stroke-width="3.5"/>'
        '<path d="M34 64 C 42 52, 46 46, 52 44 C 58 42, 62 40, 66 36" fill="none" stroke="@mint-deep" stroke-width="3" stroke-dasharray="1 6" stroke-linecap="round"/>'
        + "".join(f'<path transform="translate({x} {y}) scale({k})" d="{star5}" fill="@{c}" stroke="@ink" stroke-width="2"/>'
                  for (x, y, k, c) in [(34, 64, 1.0, "peach"), (52, 44, 0.8, "spark"), (68, 34, 1.1, "peach")])
    )


def job_frying_pan():
    """A frying pan with a fish in it (the crew are cats)."""
    return (
        '<path d="M62 62 L92 86" stroke="@ink" stroke-width="12" stroke-linecap="round"/>'
        '<path d="M62 62 L92 86" stroke="@peach-dark" stroke-width="6" stroke-linecap="round"/>'
        '<ellipse cx="42" cy="46" rx="34" ry="32" fill="@night-button" stroke="@ink" stroke-width="4"/>'
        '<ellipse cx="42" cy="46" rx="26" ry="24" fill="@asteroid-crater"/>'
        '<path d="M22 46 C 30 34, 46 34, 54 46 C 46 58, 30 58, 22 46 Z" fill="@peach" stroke="@ink" stroke-width="3" stroke-linejoin="round"/>'
        '<path d="M54 46 L64 38 L64 54 Z" fill="@peach" stroke="@ink" stroke-width="3" stroke-linejoin="round"/>'
        '<circle cx="30" cy="44" r="2.4" fill="@ink"/>'
        '<path d="M38 40 C 40 44, 40 48, 38 52 M44 40 C 46 44, 46 48, 44 52" fill="none" stroke="@peach-dark" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M26 22 C 30 18, 36 16, 42 16" fill="none" stroke="@mint-light" stroke-width="3" stroke-linecap="round" opacity="0.5"/>'
    )


JOB_ART = {"lookout": job_telescope, "engineer": job_spanner, "navigator": job_star_map, "cook": job_frying_pan}
JOBS = list(JOB_ART)


def job_picture(job, size=100):
    """A job's picture alone."""
    return f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">' + tok(JOB_ART[job]()) + '</svg>'


def job_badge(job, size=56):
    """The badge a cat wears: the picture in a moon disc with a mint rim."""
    return (f'<svg width="{size}" height="{size}" viewBox="-8 -8 116 116" aria-hidden="true">'
            + tok('<circle cx="50" cy="50" r="54" fill="@moon" stroke="@mint" stroke-width="7"/>'
                  '<circle cx="50" cy="50" r="58" fill="none" stroke="@ink" stroke-width="2.5"/>')
            + '<g transform="translate(9 9) scale(0.82)">' + tok(JOB_ART[job]()) + '</g></svg>')


def held_telescope(size=100):
    """The telescope without its tripod, for a cat holding it to its eye."""
    return f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">' + tok(job_telescope(False)) + '</svg>'

# ---------------------------------------------------------------- icons (48 viewBox, stroke currentColor)

ICONS = {
    "home": '<path d="M7 23 L24 8 L41 23"/><path d="M12 20 V40 H36 V20"/><path d="M20 40 V30 H28 V40"/>',
    "hear": '<path d="M8 18 H16 L26 9 V39 L16 30 H8 Z"/><path d="M32 17 C 36 21, 36 27, 32 31"/><path d="M37 12 C 44 19, 44 29, 37 36"/>',
    "music": '<path d="M18 34 V10 L38 6 V30"/><ellipse cx="13" cy="34" rx="6" ry="5"/><ellipse cx="33" cy="30" rx="6" ry="5"/>',
    "music-off": '<path d="M18 34 V10 L38 6 V30"/><ellipse cx="13" cy="34" rx="6" ry="5"/><ellipse cx="33" cy="30" rx="6" ry="5"/><path d="M6 6 L42 42"/>',
    "lock": '<rect x="12" y="21" width="24" height="18" rx="3"/><path d="M17 21 V15 C 17 7, 31 7, 31 15 V21"/>',
    "play": '<path d="M17 10 L38 24 L17 38 Z"/>',
    "full": '<path d="M8 18 V8 H18 M30 8 H40 V18 M8 30 V40 H18 M30 40 H40 V30"/>',
    "tick": '<path d="M10 25 L20 35 L38 14"/>',
}


def icon(name, size=48, stroke=4.5, fill_play=False):
    fill = 'currentColor' if (name == "play" and fill_play) else 'none'
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" fill="{fill}" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


STAR = "24,5 29.3,17.7 43,18.8 32.6,27.8 35.8,41.2 24,34 12.2,41.2 15.4,27.8 5,18.8 18.7,17.7"


def star(state, size=38):
    cls = {"done": 'class="f-peach s-peach" stroke-width="3"',
           "current": 'class="f-night s-mint" stroke-width="4"',
           "todo": 'class="s-star-empty" fill="none" stroke-width="3"'}[state]
    return f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" aria-hidden="true"><polygon {cls} stroke-linejoin="round" points="{STAR}"/></svg>'
