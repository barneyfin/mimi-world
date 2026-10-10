"""MeeMee Rockets' own drawings, adapted from the round 6 boards' drawing code (the boards' art6.py), in the older
look: hard colour bands, ink outlines, panel lines, rivets, lights and glints.

The build calls templates() and puts each drawing on the page for MW.art(name). Names start with the game's id.
Colours are tokens written as fill="@token" or stroke="@token"; tok() turns them into classes and stops the build on a
raw colour. Parts that only show at certain moments are groups with a class the game's CSS switches on:
  words-fire   a standing rocket's engines (flame, lit lights, smoke): shown when the right word is tapped
  words-glow   a tile's spark halo: shown on the hint tile
  words-loose / words-set   a tile in the tray (its own frame) / a tile set in a porthole (only its glass shows)

The rocket on its side (Build) is made of pieces the game puts together for each word, because its length depends on
the word: the back (fins, nozzle, flame), the hull (drawn long; the game shows as much of it as the word needs), the
nose, and a porthole socket for each tile. All in the same units: portholes are D across, the hull H high.
"""
import math

import gen_art as GA
from gen_art import tok

f = GA.f

D = 104                   # a porthole for one letter; the tile in it is the same size
GAP = 16                  # between portholes
H = D + 84                # the hull's height (188)
NOSE = H * 0.82           # the nose's length
HULL_MAX = 1400           # the hull is drawn this long; the game crops it to the word
BACK = (200, 70)          # where the hull's back top corner sits in the back piece
NOSE_X = 12               # where the nose starts in the nose piece
ROCKET_W = 250            # a standing rocket's body width (Find)
ROCKET_BOX = (320, 600)   # its drawing's box
ROCKET_AT = (160, 560)    # the rocket's centre line and the pad's top, in that box


def mimi_at(x, y, size):
    """A MeeMee's head, nested at (x, y)."""
    return GA.mimi(size).replace("<svg ", f'<svg x="{f(x)}" y="{f(y)}" ', 1)


def rivets(points, r=2.4, colour="mint-deeper", op=1.0):
    o = "" if op == 1.0 else f' opacity="{op}"'
    return "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" fill="@{colour}"{o}/>' for x, y in points)


def bands_v(x0, y0, w, h, cols, edges):
    """Hard vertical bands, lit from the left: cols[i] from edges[i-1] to edges[i] (fractions of w)."""
    out, prev = [], 0.0
    for c, e in zip(cols, list(edges) + [1.0]):
        out.append(f'<rect x="{f(x0 + prev * w - 0.5)}" y="{f(y0)}" width="{f((e - prev) * w + 1)}" height="{f(h)}" fill="@{c}"/>')
        prev = e
    return "".join(out)


def bands_h(x0, y0, w, h, cols, edges):
    """Hard horizontal bands, lit from the top."""
    out, prev = [], 0.0
    for c, e in zip(cols, list(edges) + [1.0]):
        out.append(f'<rect x="{f(x0)}" y="{f(y0 + prev * h - 0.5)}" width="{f(w)}" height="{f((e - prev) * h + 1)}" fill="@{c}"/>')
        prev = e
    return "".join(out)


MINT_V = (["mint-light", "mint", "mint-dark", "mint-deep"], [0.13, 0.6, 0.85])
PEACH_V = (["planet-peach-light", "planet-peach-2", "planet-peach", "planet-peach-4"], [0.16, 0.55, 0.8])
MINT_H = (["mint-light", "mint", "mint-dark", "mint-deep"], [0.15, 0.6, 0.84])
PEACH_H = (["planet-peach-light", "planet-peach-2", "planet-peach", "planet-peach-4"], [0.2, 0.55, 0.8])


def flame_down(cx, top, w, length):
    """An exhaust flame pointing down: peach outside, spark inside, a white-hot core."""
    h = w / 2

    def plume(hw, ln, col):
        return (f'<path d="M{f(cx - hw)} {f(top)} C {f(cx - hw * 1.1)} {f(top + ln * 0.45)}, {f(cx - hw * 0.35)} {f(top + ln * 0.8)}, {f(cx)} {f(top + ln)} '
                f'C {f(cx + hw * 0.35)} {f(top + ln * 0.8)}, {f(cx + hw * 1.1)} {f(top + ln * 0.45)}, {f(cx + hw)} {f(top)} Z" fill="@{col}"/>')
    return plume(h, length, "peach") + plume(h * 0.66, length * 0.72, "spark") + plume(h * 0.3, length * 0.42, "highlight")


def flame_left(tx, cy, h, length):
    """An exhaust flame pointing left from a nozzle at (tx, cy)."""
    def plume(hh, ln, col):
        return (f'<path d="M{f(tx)} {f(cy - hh)} C {f(tx - ln * 0.45)} {f(cy - hh * 1.15)}, {f(tx - ln * 0.8)} {f(cy - hh * 0.35)}, {f(tx - ln)} {f(cy)} '
                f'C {f(tx - ln * 0.8)} {f(cy + hh * 0.35)}, {f(tx - ln * 0.45)} {f(cy + hh * 1.15)}, {f(tx)} {f(cy + hh)} Z" fill="@{col}"/>')
    return plume(h / 2, length, "peach") + plume(h * 0.33, length * 0.74, "spark") + plume(h * 0.15, length * 0.45, "highlight")


def puff(x, y, r, col="moon-dim", op=0.9):
    """A cloud of exhaust smoke: three overlapping circles with a shaded underside."""
    return (f'<g opacity="{op}">'
            f'<circle cx="{f(x - r * 0.7)}" cy="{f(y + r * 0.15)}" r="{f(r * 0.72)}" fill="@{col}" stroke="@ink" stroke-width="3"/>'
            f'<circle cx="{f(x + r * 0.65)}" cy="{f(y + r * 0.2)}" r="{f(r * 0.66)}" fill="@{col}" stroke="@ink" stroke-width="3"/>'
            f'<circle cx="{f(x)}" cy="{f(y - r * 0.15)}" r="{f(r)}" fill="@{col}" stroke="@ink" stroke-width="3"/>'
            f'<path d="M{f(x - r * 0.75)} {f(y + r * 0.45)} C {f(x - r * 0.3)} {f(y + r * 0.8)}, {f(x + r * 0.4)} {f(y + r * 0.8)}, {f(x + r * 0.9)} {f(y + r * 0.45)}" '
            f'fill="none" stroke="@white-shade" stroke-width="{f(r * 0.22)}" stroke-linecap="round"/>'
            f'<circle cx="{f(x - r * 0.3)}" cy="{f(y - r * 0.45)}" r="{f(r * 0.18)}" fill="@highlight" opacity="0.8"/>'
            '</g>')


def svg(w, h, body, visible=True):
    """A standalone drawing, w x h. visible: parts may stick out of its box (flames, smoke, a glow)."""
    over = ' overflow="visible"' if visible else ""
    return f'<svg width="{f(w)}" height="{f(h)}" viewBox="0 0 {f(w)} {f(h)}"{over} aria-hidden="true">{body}</svg>'


# ---------------------------------------------------------------- the rocket standing on the pad (Find)

def rocket_up(cx, base, w=ROCKET_W, uid="words-up"):
    """A rocket standing on the launch pad, its engines in words-fire groups (hidden until the right word is tapped).
    Returns (svg content, panel) where panel = (x, y, w, h) of the word panel, for the word written on top."""
    x0, x1 = cx - w / 2, cx + w / 2
    k = w / 240
    ys = base - 84 * k                        # bottom of the body: the rocket stands on its fins, nozzle clear of the pad
    yb = ys - 284 * k                         # top of the body
    ch = 150 * w / 240                        # nose cone height
    H_ = ys - yb
    o = []
    o.append(f'<ellipse cx="{f(cx)}" cy="{f(base + 4)}" rx="{f(w * 0.7)}" ry="9" fill="@shadow" opacity="0.18"/>')
    # fins (behind the body): peach bands, a mint stripe, ink outline
    for side in (-1, 1):
        def X(v):
            return cx + side * v
        fin = (f"M{f(X(w * 0.4))} {f(ys - H_ * 0.42)} C {f(X(w * 0.55))} {f(ys - H_ * 0.3)}, {f(X(w * 0.62))} {f(ys - H_ * 0.02)}, {f(X(w * 0.61))} {f(base)} "
               f"L{f(X(w * 0.42))} {f(base)} C {f(X(w * 0.42))} {f(ys + 30 * k)}, {f(X(w * 0.4))} {f(ys + 10 * k)}, {f(X(w * 0.36))} {f(ys)} Z")
        o.append(f'<clipPath id="{uid}-fin{side}"><path d="{fin}"/></clipPath>')
        o.append(f'<path d="{fin}" fill="@{"planet-peach-2" if side < 0 else "planet-peach-4"}"/>')
        o.append(f'<g clip-path="url(#{uid}-fin{side})"><rect x="{f(min(X(w * 0.38), X(w * 0.66)))}" y="{f(base - 22)}" width="{f(w * 0.28)}" height="22" fill="@peach-dark"/>'
                 f'<path d="M{f(X(w * 0.47))} {f(ys - H_ * 0.3)} C {f(X(w * 0.55))} {f(ys - H_ * 0.18)}, {f(X(w * 0.57))} {f(ys - H_ * 0.05)}, {f(X(w * 0.56))} {f(base - 24)}" '
                 f'fill="none" stroke="@mint-light" stroke-width="{f(w * 0.03)}" stroke-linecap="round"/></g>')
        o.append(f'<path d="{fin}" fill="none" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>')
        o.append(f'<rect x="{f(X(w * 0.52) - 13)}" y="{f(base - 12)}" width="26" height="16" rx="4" fill="@steel" stroke="@ink" stroke-width="3"/>')
    # nozzle, and the flame under it (fire)
    nw0, nw1, ny0, ny1 = w * 0.32, w * 0.46, ys - 2, ys + 38 * k
    nozzle = f"M{f(cx - nw0 / 2)} {f(ny0)} L{f(cx + nw0 / 2)} {f(ny0)} L{f(cx + nw1 / 2)} {f(ny1)} L{f(cx - nw1 / 2)} {f(ny1)} Z"
    o.append(f'<clipPath id="{uid}-noz"><path d="{nozzle}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-noz)">' + bands_v(cx - nw1 / 2, ny0, nw1, ny1 - ny0, ["steel", "scruffles-grey", "steel-dark"], [0.35, 0.75]) + '</g>')
    o.append(f'<path d="{nozzle}" fill="none" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>')
    o.append(f'<path d="M{f(cx - nw0 / 2 - 2)} {f(ny0 + 10)} L{f(cx + nw0 / 2 + 2)} {f(ny0 + 10)}" stroke="@ink" stroke-width="2" opacity="0.4"/>')
    o.append('<g class="words-fire">' + flame_down(cx, ny1 - 2, nw1 * 1.05, base - ny1 + 22) + '</g>')
    # body: a cylinder in vertical bands, a peach skirt with lights, seams with rivets
    body = (f"M{f(x0)} {f(yb)} L{f(x1)} {f(yb)} L{f(x1)} {f(ys - 14)} Q {f(x1)} {f(ys)} {f(x1 - 14)} {f(ys)} "
            f"L{f(x0 + 14)} {f(ys)} Q {f(x0)} {f(ys)} {f(x0)} {f(ys - 14)} Z")
    o.append(f'<clipPath id="{uid}-body"><path d="{body}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-body)">' + bands_v(x0, yb, w, H_, *MINT_V))
    sk = ys - 40 * w / 240
    o.append(bands_v(x0, sk, w, ys - sk, ["planet-peach-2", "planet-peach", "peach-shade", "planet-peach-6"], [0.13, 0.6, 0.85]))
    o.append(f'<path d="M{f(x0)} {f(sk)} H{f(x1)}" stroke="@ink" stroke-width="3"/>')
    seam1, seam2 = yb + 112 * w / 240, yb + 252 * w / 240
    for sy in (seam1, seam2):
        o.append(f'<path d="M{f(x0)} {f(sy)} H{f(x1)}" stroke="@ink" stroke-width="2" opacity="0.3"/>')
    o.append(rivets([(x0 + w * (0.06 + i * 0.125), yb + 20 * w / 240) for i in range(8)]))
    o.append(rivets([(x0 + w * (0.06 + i * 0.125), seam2 + 10) for i in range(8)]))
    o.append(f'<path d="M{f(x0 + w * 0.07)} {f(yb + 34)} L{f(x0 + w * 0.07)} {f(sk - 12)}" stroke="@cat-white" stroke-width="{f(w * 0.03)}" stroke-linecap="round" opacity="0.45"/>')
    o.append('</g>')
    lights = [(cx + dx * w, (sk + ys) / 2) for dx in (-0.36, -0.18, 0.18, 0.36)]
    lit = []
    for lx, ly in lights:
        o.append(f'<circle cx="{f(lx)}" cy="{f(ly)}" r="{f(w * 0.032)}" fill="@peach-dark" stroke="@ink" stroke-width="2.5"/>')
        o.append(f'<circle cx="{f(lx)}" cy="{f(ly)}" r="{f(w * 0.022)}" fill="@peach"/>')
        lit.append(f'<circle cx="{f(lx)}" cy="{f(ly)}" r="{f(w * 0.022)}" fill="@spark"/>'
                   f'<circle cx="{f(lx)}" cy="{f(ly)}" r="{f(w * 0.06)}" fill="@spark" opacity="0.35"/>')
        o.append(f'<circle cx="{f(lx - 2)}" cy="{f(ly - 2)}" r="1.5" fill="@highlight" opacity="0.8"/>')
    o.append('<g class="words-fire">' + "".join(lit) + '</g>')
    o.append(f'<path d="{body}" fill="none" stroke="@ink" stroke-width="6" stroke-linejoin="round"/>')
    # the centre fin, seen edge-on in front
    cf = (f"M{f(cx - w * 0.035)} {f(ys - 30 * k)} L{f(cx + w * 0.035)} {f(ys - 30 * k)} L{f(cx + w * 0.06)} {f(base)} L{f(cx - w * 0.06)} {f(base)} Z")
    o.append(f'<clipPath id="{uid}-cf"><path d="{cf}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-cf)">' + bands_v(cx - w * 0.06, ys - 30 * k, w * 0.12, base - ys + 30 * k, ["planet-peach-2", "planet-peach-4"], [0.5])
             + f'<rect x="{f(cx - w * 0.06)}" y="{f(base - 22)}" width="{f(w * 0.12)}" height="22" fill="@peach-dark"/></g>')
    o.append(f'<path d="{cf}" fill="none" stroke="@ink" stroke-width="4.5" stroke-linejoin="round"/>')
    o.append(f'<rect x="{f(cx - 13)}" y="{f(base - 12)}" width="26" height="16" rx="4" fill="@steel" stroke="@ink" stroke-width="3"/>')
    # nose cone: peach bands, a collar of rivets underneath, a tip light
    cone = (f"M{f(x0)} {f(yb)} C {f(x0 + w * 0.03)} {f(yb - ch * 0.55)}, {f(cx - w * 0.2)} {f(yb - ch * 0.94)}, {f(cx)} {f(yb - ch)} "
            f"C {f(cx + w * 0.2)} {f(yb - ch * 0.94)}, {f(x1 - w * 0.03)} {f(yb - ch * 0.55)}, {f(x1)} {f(yb)} Z")
    o.append(f'<clipPath id="{uid}-cone"><path d="{cone}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-cone)">' + bands_v(x0, yb - ch, w, ch, *PEACH_V)
             + f'<path d="M{f(x0)} {f(yb - ch * 0.42)} C {f(cx - w * 0.2)} {f(yb - ch * 0.5)}, {f(cx + w * 0.2)} {f(yb - ch * 0.5)}, {f(x1)} {f(yb - ch * 0.42)}" '
               f'fill="none" stroke="@ink" stroke-width="2" opacity="0.3"/>'
             + f'<path d="M{f(cx - w * 0.3)} {f(yb - ch * 0.2)} C {f(cx - w * 0.28)} {f(yb - ch * 0.5)}, {f(cx - w * 0.18)} {f(yb - ch * 0.75)}, {f(cx - w * 0.06)} {f(yb - ch * 0.9)}" '
               f'fill="none" stroke="@cat-white" stroke-width="{f(w * 0.03)}" stroke-linecap="round" opacity="0.5"/>'
             + '</g>')
    o.append(f'<path d="{cone}" fill="none" stroke="@ink" stroke-width="6" stroke-linejoin="round"/>')
    o.append(f'<rect x="{f(x0 - 4)}" y="{f(yb - 9)}" width="{f(w + 8)}" height="18" rx="6" fill="@mint-dark" stroke="@ink" stroke-width="4"/>')
    o.append(rivets([(x0 + w * (0.08 + i * 0.12), yb) for i in range(8)], r=2.2, colour="mint-deeper"))
    o.append(f'<circle cx="{f(cx)}" cy="{f(yb - ch - 2)}" r="9" fill="@peach-dark" stroke="@ink" stroke-width="3.5"/>')
    o.append(f'<circle cx="{f(cx)}" cy="{f(yb - ch - 2)}" r="5" fill="@peach"/>')
    o.append(f'<g class="words-fire"><circle cx="{f(cx)}" cy="{f(yb - ch - 2)}" r="5" fill="@spark"/></g>')
    o.append(f'<circle cx="{f(cx - 2.5)}" cy="{f(yb - ch - 4.5)}" r="1.6" fill="@highlight" opacity="0.8"/>')
    # the window, with a MeeMee looking out
    wy, wr = yb + 58 * w / 240, 34 * w / 240
    o.append(f'<circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr + 11)}" fill="@peach-dark" stroke="@ink" stroke-width="4"/>')
    o.append(f'<circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr + 5)}" fill="none" stroke="@planet-peach" stroke-width="3"/>')
    o.append(rivets([(cx + (wr + 6) * math.cos(a), wy + (wr + 6) * math.sin(a)) for a in [i * math.pi / 4 + math.pi / 8 for i in range(8)]], r=2, colour="ink"))
    o.append(f'<clipPath id="{uid}-win"><circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr)}"/></clipPath>')
    o.append(f'<circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr)}" fill="@night"/>')
    o.append(f'<g clip-path="url(#{uid}-win)">')
    o.append(mimi_at(cx - wr * 0.86, wy - wr * 0.5, wr * 1.72))
    o.append(f'<circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr)}" fill="@glass" opacity="0.22"/>'
             f'<path d="M{f(cx - wr * 0.62)} {f(wy - wr * 0.2)} C {f(cx - wr * 0.55)} {f(wy - wr * 0.6)}, {f(cx - wr * 0.3)} {f(wy - wr * 0.78)}, {f(cx)} {f(wy - wr * 0.82)}" '
             f'fill="none" stroke="@cat-white" stroke-width="5" stroke-linecap="round" opacity="0.7"/></g>')
    o.append(f'<circle cx="{f(cx)}" cy="{f(wy)}" r="{f(wr)}" fill="none" stroke="@ink" stroke-width="4"/>')
    # the word panel: a moon plate with four screws
    px, py, pw, ph = x0 + 14, yb + 120 * w / 240, w - 28, 108 * w / 240
    o.append(f'<rect x="{f(px)}" y="{f(py + 5)}" width="{f(pw)}" height="{f(ph)}" rx="16" fill="@mint-deeper" opacity="0.6"/>')
    o.append(f'<rect x="{f(px)}" y="{f(py)}" width="{f(pw)}" height="{f(ph)}" rx="16" fill="@moon" stroke="@ink" stroke-width="4"/>')
    o.append(f'<path d="M{f(px + 14)} {f(py + ph - 9)} H{f(px + pw - 14)}" stroke="@moon-dim" stroke-width="6" stroke-linecap="round"/>')
    for sx_, sy_ in [(px + 12, py + 12), (px + pw - 12, py + 12), (px + 12, py + ph - 12), (px + pw - 12, py + ph - 12)]:
        o.append(f'<circle cx="{f(sx_)}" cy="{f(sy_)}" r="4.2" fill="@steel" stroke="@ink" stroke-width="1.8"/>'
                 f'<path d="M{f(sx_ - 2.4)} {f(sy_ + 2.4)} L{f(sx_ + 2.4)} {f(sy_ - 2.4)}" stroke="@ink" stroke-width="1.4"/>')
    # smoke at the foot of the rocket (fire): it lifts off the pad a little as the engines start
    o.append('<g class="words-fire">' + puff(cx - w * 0.5, base - 12, 30) + puff(cx - w * 0.24, base + 4, 20) + puff(cx + w * 0.42, base - 8, 26) + '</g>')
    return tok("".join(o)), (px, py, pw, ph)


def rocket_template():
    cx, base = ROCKET_AT
    body, _ = rocket_up(cx, base)
    return svg(*ROCKET_BOX, body)


def rocket_panel():
    """Where the word panel is in the standing rocket's box (the game writes the word there)."""
    cx, base = ROCKET_AT
    return rocket_up(cx, base)[1]


def launch_pad(x0, x1, top, uid="words-pad"):
    """The launch pad: a banded platform with hazard stripes, lights along its edge and girders underneath.
    SVG content for a 1280 x 800 layer."""
    w, h = x1 - x0, 30
    o = []
    for gx in range(int(x0) + 70, int(x1) - 20, 120):
        o.append(f'<path d="M{gx} {top + h} L{gx + 18} 812 M{gx + 60} {top + h} L{gx + 42} 812 M{gx + 4} {top + h + 34} L{gx + 56} {top + h + 34} '
                 f'M{gx + 10} {top + h + 34} L{gx + 50} {top + h + 72}" stroke="@asteroid" stroke-width="7" stroke-linecap="round"/>')
        o.append(f'<path d="M{gx} {top + h} L{gx + 18} 812 M{gx + 60} {top + h} L{gx + 42} 812" stroke="@asteroid-light" stroke-width="2" opacity="0.6"/>')
    deck = f"M{x0 + 14} {top} H{x1 - 14} Q {x1} {top} {x1} {top + 14} V{top + h - 8} Q {x1} {top + h} {x1 - 8} {top + h} H{x0 + 8} Q {x0} {top + h} {x0} {top + h - 8} V{top + 14} Q {x0} {top} {x0 + 14} {top} Z"
    o.append(f'<clipPath id="{uid}-deck"><path d="{deck}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-deck)">' + bands_h(x0, top, w, h, ["asteroid-light", "asteroid", "asteroid-crater"], [0.22, 0.62]))
    stripes = "".join(f'<path d="M{x} {top + 18} l12 0 l-10 12 l-12 0 Z" fill="@peach"/>' for x in range(int(x0) + 8, int(x1), 30))
    o.append(f'<rect x="{x0}" y="{top + 18}" width="{w}" height="12" fill="@asteroid-deep"/>' + stripes + '</g>')
    o.append(f'<path d="{deck}" fill="none" stroke="@ink" stroke-width="4.5"/>')
    o.append(f'<path d="M{x0 + 10} {top + 3} H{x1 - 10}" stroke="@mint-light" stroke-width="2" opacity="0.35"/>')
    for lx in range(int(x0) + 34, int(x1) - 20, 112):
        o.append(f'<circle cx="{lx}" cy="{top + 9}" r="4.5" fill="@spark" stroke="@ink" stroke-width="2"/><circle cx="{lx - 1.5}" cy="{top + 7.5}" r="1.3" fill="@highlight"/>')
    return svg(1280, 800, tok("".join(o)))


# ---------------------------------------------------------------- the rocket on its side (Build), in pieces

def tile_width(k, d=D):
    """A porthole for one letter is round; for a pair or three letters (one sound) it is an oval, wider by half a
    porthole per extra letter, so every letter is the same size."""
    return d if k == 1 else d + (k - 1) * 0.46 * d


def ship_back(uid="words-back"):
    """The back of the rocket on its side: fins top and bottom, the nozzle, and its flame and smoke (words-fire).
    The hull's back top corner is at BACK in this drawing; the hull covers the fins' roots."""
    x, y = BACK
    cy = y + H / 2
    o = []
    for side in (-1, 1):
        def Y(v):
            return cy + side * v
        fin = (f"M{f(x + 120)} {f(Y(H / 2 - 4))} C {f(x + 70)} {f(Y(H / 2 + 14))}, {f(x + 18)} {f(Y(H / 2 + 50))}, {f(x - 14)} {f(Y(H / 2 + 66))} "
               f"L{f(x + 6)} {f(Y(H / 2 - 4))} Z")
        o.append(f'<clipPath id="{uid}-fin{side}"><path d="{fin}"/></clipPath>')
        o.append(f'<path d="{fin}" fill="@{"planet-peach-2" if side < 0 else "planet-peach-4"}"/>')
        o.append(f'<g clip-path="url(#{uid}-fin{side})"><path d="M{f(x + 92)} {f(Y(H / 2 + 4))} C {f(x + 56)} {f(Y(H / 2 + 20))}, {f(x + 22)} {f(Y(H / 2 + 40))}, {f(x)} {f(Y(H / 2 + 54))}" '
                 f'fill="none" stroke="@mint-light" stroke-width="8" stroke-linecap="round"/></g>')
        o.append(f'<path d="{fin}" fill="none" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>')
    fire = flame_left(x - 44, cy, H * 0.56, 150) + puff(x - 150, cy + 70, 34) + puff(x - 96, cy + 128, 26) + puff(x - 210, cy + 10, 24)
    o.append('<g class="words-fire">' + fire + '</g>')
    noz = f"M{f(x + 2)} {f(cy - H * 0.2)} L{f(x - 40)} {f(cy - H * 0.3)} L{f(x - 40)} {f(cy + H * 0.3)} L{f(x + 2)} {f(cy + H * 0.2)} Z"
    o.append(f'<clipPath id="{uid}-noz"><path d="{noz}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid}-noz)">' + bands_h(x - 40, cy - H * 0.3, 44, H * 0.6, ["steel", "scruffles-grey", "steel-dark"], [0.3, 0.72]) + '</g>')
    o.append(f'<path d="{noz}" fill="none" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>')
    o.append(f'<ellipse cx="{f(x - 40)}" cy="{f(cy)}" rx="7" ry="{f(H * 0.3)}" fill="@steel-dark" stroke="@ink" stroke-width="3.5"/>')
    return svg(x + 130, y + H + 70, tok("".join(o)))


def ship_hull(uid="words-hull"):
    """The hull, HULL_MAX long, its back top corner at (0, 0): mint bands, a peach stripe, rows of rivets, a seam and
    a highlight. The game shows only as much as the word needs (the nose's collar covers the cut)."""
    L = HULL_MAX
    o = []
    hull = f"M10 0 H{L} V{H} H10 Q 0 {H} 0 {H - 10} V10 Q 0 0 10 0 Z"
    o.append(f'<clipPath id="{uid}"><path d="{hull}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid})">' + bands_h(0, 0, L, H, *MINT_H))
    o.append(f'<rect x="0" y="{H - 26}" width="{L}" height="12" fill="@peach-dark"/><rect x="0" y="{H - 26}" width="{L}" height="4" fill="@planet-peach"/>')
    o.append(rivets([(24 + i * 30, 14) for i in range(int((L - 30) / 30))]))
    o.append(rivets([(24 + i * 30, H - 38) for i in range(int((L - 30) / 30))], colour="mint-deeper", op=0.8))
    o.append(f'<path d="M20 28 H{L}" stroke="@cat-white" stroke-width="6" stroke-linecap="round" opacity="0.4"/>')
    o.append(f'<path d="M60 0 V{H}" stroke="@ink" stroke-width="2" opacity="0.3"/>')
    o.append('</g>')
    o.append(f'<path d="{hull}" fill="none" stroke="@ink" stroke-width="6" stroke-linejoin="round"/>')
    return svg(L, H, tok("".join(o)), visible=False)


def ship_nose(uid="words-nose"):
    """The nose: peach bands, the collar where it joins the hull (with rivets), and a window with a MeeMee.
    It starts at NOSE_X in this drawing; its top is the hull's top (y 0)."""
    xn, y, nl = NOSE_X, 0, NOSE
    cy = H / 2
    o = []
    nose = (f"M{f(xn)} {f(y)} C {f(xn + nl * 0.55)} {f(y + 2)}, {f(xn + nl * 0.95)} {f(cy - H * 0.22)}, {f(xn + nl)} {f(cy)} "
            f"C {f(xn + nl * 0.95)} {f(cy + H * 0.22)}, {f(xn + nl * 0.55)} {f(y + H - 2)}, {f(xn)} {f(y + H)} Z")
    o.append(f'<clipPath id="{uid}"><path d="{nose}"/></clipPath>')
    o.append(f'<g clip-path="url(#{uid})">' + bands_h(xn, y, nl, H, *PEACH_H)
             + f'<path d="M{f(xn + 10)} {f(y + 22)} C {f(xn + nl * 0.4)} {f(y + 24)}, {f(xn + nl * 0.7)} {f(y + H * 0.3)}, {f(xn + nl * 0.84)} {f(cy - H * 0.12)}" '
               f'fill="none" stroke="@cat-white" stroke-width="6" stroke-linecap="round" opacity="0.5"/>' + '</g>')
    o.append(f'<path d="{nose}" fill="none" stroke="@ink" stroke-width="6" stroke-linejoin="round"/>')
    o.append(f'<rect x="{f(xn - 9)}" y="{f(y - 4)}" width="18" height="{f(H + 8)}" rx="6" fill="@mint-dark" stroke="@ink" stroke-width="4"/>')
    o.append(rivets([(xn, y + 14 + i * ((H - 28) / 6)) for i in range(7)], r=2.2))
    wx, wr = xn + nl * 0.42, H * 0.17
    o.append(f'<circle cx="{f(wx)}" cy="{f(cy)}" r="{f(wr + 8)}" fill="@peach-dark" stroke="@ink" stroke-width="4"/>')
    o.append(f'<circle cx="{f(wx)}" cy="{f(cy)}" r="{f(wr)}" fill="@night"/>')
    body = tok("".join(o))
    glass = tok(f'<clipPath id="{uid}-win"><circle cx="{f(wx)}" cy="{f(cy)}" r="{f(wr)}"/></clipPath>'
                f'<g clip-path="url(#{uid}-win)">' + mimi_at(wx - wr * 0.86, cy - wr * 0.5, wr * 1.72)
                + f'<circle cx="{f(wx)}" cy="{f(cy)}" r="{f(wr)}" fill="@glass" opacity="0.22"/>'
                f'<path d="M{f(wx - wr * 0.6)} {f(cy - wr * 0.2)} C {f(wx - wr * 0.5)} {f(cy - wr * 0.6)}, {f(wx - wr * 0.25)} {f(cy - wr * 0.8)}, {f(wx + wr * 0.05)} {f(cy - wr * 0.82)}" '
                f'fill="none" stroke="@cat-white" stroke-width="4" stroke-linecap="round" opacity="0.7"/></g>'
                f'<circle cx="{f(wx)}" cy="{f(cy)}" r="{f(wr)}" fill="none" stroke="@ink" stroke-width="3.5"/>')
    return svg(xn + nl + 10, H, body + glass)


def socket(k, d=D):
    """An empty porthole frame in the hull: a peach-dark rim with rivets round a dark opening, a dashed mint ring
    inside saying 'a tile goes here'. Drawn with an 8 px margin for the rim: the opening is at (8, 8)."""
    w = tile_width(k, d)
    x = y = 8
    r = d / 2
    cx, cy = x + w / 2, y + r
    straight = w - d
    o = [f'<rect x="{f(x - 8)}" y="{f(y - 8)}" width="{f(w + 16)}" height="{f(d + 16)}" rx="{f(r + 8)}" fill="@peach-dark" stroke="@ink" stroke-width="4"/>',
         f'<rect x="{f(x - 3)}" y="{f(y - 3)}" width="{f(w + 6)}" height="{f(d + 6)}" rx="{f(r + 3)}" fill="none" stroke="@planet-peach" stroke-width="2.5"/>']
    pts = []
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        px = cx + (r + 4) * math.cos(a) + (straight / 2) * (1 if math.cos(a) > 0 else -1)
        pts.append((px, cy + (r + 4) * math.sin(a)))
    o.append(rivets(pts, r=2, colour="ink"))
    o.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(d)}" rx="{f(r)}" fill="@night-raised" stroke="@ink" stroke-width="3"/>')
    o.append(f'<rect x="{f(x + 8)}" y="{f(y + 8)}" width="{f(w - 16)}" height="{f(d - 16)}" rx="{f(r - 8)}" fill="none" stroke="@mint" stroke-width="4" '
             f'stroke-dasharray="3 10" stroke-linecap="round"/>')
    return svg(w + 16, d + 16, tok("".join(o)))


def tile(k, d=D):
    """A porthole tile, w x d: round for one letter, an oval for a pair or three. The letters go on top as HTML.
    Three groups: words-glow (the hint's spark halo), words-loose (a moon window in its own peach-dark frame, for the
    tray and dragging) and words-set (only the glass, once it sits in the rocket's own frame)."""
    w = tile_width(k, d)
    r = d / 2
    straight = w - d
    glow = f'<rect x="-14" y="-14" width="{f(w + 28)}" height="{f(d + 28)}" rx="{f(r + 14)}" fill="@spark" opacity="0.4"/>'
    t = [f'<rect x="2" y="2" width="{f(w - 4)}" height="{f(d - 4)}" rx="{f(r - 2)}" fill="@peach-dark" stroke="@ink" stroke-width="4"/>',
         f'<rect x="7" y="7" width="{f(w - 14)}" height="{f(d - 14)}" rx="{f(r - 7)}" fill="none" stroke="@planet-peach" stroke-width="2.5"/>']
    pts = []
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        px = w / 2 + (r - 6) * math.cos(a) + (straight / 2) * (1 if math.cos(a) > 0 else -1)
        pts.append((px, r + (r - 6) * math.sin(a)))
    t.append(rivets(pts, r=2.2, colour="ink"))
    t.append(f'<rect x="{f(d * 0.1)}" y="{f(d * 0.1)}" width="{f(w - d * 0.2)}" height="{f(d * 0.8)}" rx="{f(r * 0.8)}" fill="@moon" stroke="@ink" stroke-width="3"/>')
    t.append(f'<path d="M{f(d * 0.24)} {f(d * 0.4)} C {f(d * 0.28)} {f(d * 0.26)}, {f(d * 0.38)} {f(d * 0.2)}, {f(d * 0.5)} {f(d * 0.19)}" fill="none" '
             f'stroke="@cat-white" stroke-width="4" stroke-linecap="round" opacity="0.9"/>')
    t.append(f'<path d="M{f(d * 0.3)} {f(d * 0.78)} H{f(w - d * 0.3)}" stroke="@moon-dim" stroke-width="5" stroke-linecap="round"/>')
    s = [f'<rect x="1.5" y="1.5" width="{f(w - 3)}" height="{f(d - 3)}" rx="{f(r - 1.5)}" fill="@moon" stroke="@ink" stroke-width="3"/>',
         f'<path d="M{f(d * 0.2)} {f(d * 0.4)} C {f(d * 0.24)} {f(d * 0.24)}, {f(d * 0.36)} {f(d * 0.15)}, {f(d * 0.5)} {f(d * 0.13)}" fill="none" '
         f'stroke="@cat-white" stroke-width="4" stroke-linecap="round" opacity="0.9"/>',
         f'<path d="M{f(d * 0.3)} {f(d * 0.85)} H{f(w - d * 0.3)}" stroke="@moon-dim" stroke-width="5" stroke-linecap="round"/>']
    body = ('<g class="words-glow">' + tok(glow) + '</g><g class="words-loose">' + tok("".join(t)) + '</g>'
            '<g class="words-set">' + tok("".join(s)) + '</g>')
    return svg(w, d, body)


# ---------------------------------------------------------------- the planet's badge, and the little rockets at the end

def badge_rocket(uid="words-bdg"):
    """A rocket in the older look, in a 100 x 100 box (the planet's badge)."""
    o = ['<path d="M30 62 C 20 68, 16 78, 16 88 L34 80 Z" fill="@planet-peach-2" stroke="@ink" stroke-width="3.5" stroke-linejoin="round"/>',
         '<path d="M70 62 C 80 68, 84 78, 84 88 L66 80 Z" fill="@planet-peach-4" stroke="@ink" stroke-width="3.5" stroke-linejoin="round"/>',
         '<path d="M40 82 L60 82 L64 92 L36 92 Z" fill="@steel" stroke="@ink" stroke-width="3" stroke-linejoin="round"/>',
         f'<clipPath id="{uid}-b"><rect x="32" y="38" width="36" height="46" rx="5"/></clipPath>',
         f'<g clip-path="url(#{uid}-b)">' + bands_v(32, 38, 36, 46, *MINT_V) + '<rect x="32" y="72" width="36" height="12" fill="@peach-shade"/></g>',
         '<rect x="32" y="38" width="36" height="46" rx="5" fill="none" stroke="@ink" stroke-width="4"/>',
         f'<clipPath id="{uid}-c"><path d="M32 40 C 33 26, 42 14, 50 8 C 58 14, 67 26, 68 40 Z"/></clipPath>',
         f'<g clip-path="url(#{uid}-c)">' + bands_v(32, 8, 36, 34, *PEACH_V) + '</g>',
         '<path d="M32 40 C 33 26, 42 14, 50 8 C 58 14, 67 26, 68 40 Z" fill="none" stroke="@ink" stroke-width="4" stroke-linejoin="round"/>',
         '<circle cx="50" cy="54" r="9" fill="@peach-dark" stroke="@ink" stroke-width="3"/><circle cx="50" cy="54" r="5.5" fill="@glass" stroke="@ink" stroke-width="2"/>',
         '<path d="M47 52 C 48 50, 50 49, 52 49" fill="none" stroke="@cat-white" stroke-width="1.8" stroke-linecap="round"/>']
    return tok("".join(o))


def badge(size=56):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">' + badge_rocket() + '</svg>'


def mini_rocket(uid="words-mini"):
    """A little rocket flying, its engine lit: the end of the round. 100 x 140, the rocket in the top 100."""
    flame = tok(flame_down(50, 90, 26, 40))
    return ('<svg width="100" height="140" viewBox="0 0 100 140" overflow="visible" aria-hidden="true">'
            + flame + badge_rocket(uid) + '</svg>')


def templates():
    t = {
        "words-badge": badge(56),
        "words-rocket": rocket_template(),
        "words-pad": launch_pad(50, 942, 693),
        "words-ship-back": ship_back(),
        "words-ship-hull": ship_hull(),
        "words-ship-nose": ship_nose(),
        "words-rocket-mini": mini_rocket(),
    }
    for k in (1, 2, 3, 4):                # letters in one tile: a sound can be written with up to four ("eigh")
        t[f"words-socket-{k}"] = socket(k)
        t[f"words-tile-{k}"] = tile(k)
    return t
