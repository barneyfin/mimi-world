"""SVG builders for Mimi World. Every fill and stroke is a class bound to a token (bundle.css)."""

# ---------------------------------------------------------------- the Mimi

def mimi(size=80, extra=""):
    return (
        f'<svg class="mw-mimi-art" width="{size}" height="{size}" viewBox="0 0 80 80" aria-hidden="true"{extra}>'
        '<path class="f-mimi s-mimi-outline" stroke-width="4" stroke-linejoin="round" d="M14 32 L12 6 L33 21 Z"/>'
        '<path class="f-mimi s-mimi-outline" stroke-width="4" stroke-linejoin="round" d="M66 32 L68 6 L47 21 Z"/>'
        '<ellipse class="f-mimi s-mimi-outline" stroke-width="4" cx="40" cy="45" rx="31" ry="28"/>'
        '<ellipse class="f-mimi-muzzle" cx="40" cy="55" rx="13" ry="9"/>'
        '<circle class="f-mimi-eye" cx="29" cy="41" r="5"/><circle class="f-mimi-eye" cx="51" cy="41" r="5"/>'
        '<circle class="f-cat-white" cx="27.5" cy="39.5" r="1.6"/><circle class="f-cat-white" cx="49.5" cy="39.5" r="1.6"/>'
        '<path class="f-mimi-nose" d="M37 51 L43 51 L40 55 Z"/>'
        '</svg>'
    )


# Counting patterns: offsets from a part circle's centre, and the Mimi size for each count.
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
    """Absolutely placed Mimi inside a circle's padding box (inner × inner)."""
    size, pts = pattern(n)
    c = inner / 2
    out = []
    for (dx, dy) in pts:
        out.append(f'<div class="mw-placed" style="left:{c + dx - size / 2:.0f}px;top:{c + dy - size / 2:.0f}px">{mimi(size)}</div>')
    return "".join(out)


# ---------------------------------------------------------------- sky

def stars(points, r=2):
    return "".join(f'<circle class="f-moon" cx="{x}" cy="{y}" r="{rr}"/>' for (x, y, rr) in points)


def spark(x, y, s=1.0):
    return (f'<path class="f-spark" transform="translate({x} {y}) scale({s})" '
            'd="M0 -12 Q 2 -2 12 0 Q 2 2 0 12 Q -2 2 -12 0 Q -2 -2 0 -12 Z"/>')


def galaxy(x, y, rot, scale, kind="lilac"):
    outer, inner = {"lilac": ("f-mimi", "f-galaxy"), "peach": ("f-peach", "f-galaxy-peach"), "mint": ("f-mint", "f-galaxy-mint")}[kind]
    arm = {"lilac": "s-galaxy", "peach": "s-galaxy-peach", "mint": "s-galaxy-mint"}[kind]
    return (
        f'<g transform="translate({x} {y}) rotate({rot}) scale({scale})">'
        f'<ellipse class="{outer}" rx="48" ry="16" opacity="0.2"/>'
        f'<ellipse class="{inner}" rx="31" ry="10" opacity="0.35"/>'
        f'<ellipse class="f-moon" rx="13" ry="5" opacity="0.85"/>'
        f'<path class="{arm}" fill="none" stroke-width="3" stroke-linecap="round" opacity="0.55" d="M0 0 C 16 -10, 36 -9, 46 3"/>'
        f'<path class="{arm}" fill="none" stroke-width="3" stroke-linecap="round" opacity="0.55" d="M0 0 C -16 10, -36 9, -46 -3"/>'
        '</g>'
    )


def planet(cx, cy, r, ramp, uid, ring=False):
    """A banded planet: three hard bands, light top-left, dark bottom-right, no outline."""
    light, mid, dark = {"indigo": ("planet-indigo-light", "planet-indigo", "planet-indigo-dark"),
                        "peach": ("planet-peach-light", "planet-peach", "planet-peach-dark"),
                        "mint": ("planet-mint-light", "planet-mint", "planet-mint-dark")}[ramp]
    x0, y0, d = cx - r, cy - r, 2 * r
    body = (
        f'<clipPath id="{uid}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
        f'<g clip-path="url(#{uid})"><g transform="rotate(-45 {cx} {cy})">'
        f'<rect class="f-{dark}" x="{x0}" y="{y0}" width="{d}" height="{d}"/>'
        f'<rect class="f-{mid}" x="{x0}" y="{y0}" width="{d}" height="{d * 0.674:.1f}"/>'
        f'<rect class="f-{light}" x="{x0}" y="{y0}" width="{d}" height="{d * 0.3:.1f}"/>'
        '</g></g>'
    )
    if not ring:
        return body
    rx, ry = r * 1.64, r * 0.34
    back = f'<g transform="rotate(-14 {cx} {cy})"><path class="s-mint-dark" fill="none" stroke-width="{max(3, r * 0.14):.1f}" stroke-linecap="round" d="M{cx - rx} {cy} A{rx} {ry} 0 0 1 {cx + rx} {cy}"/></g>'
    front = f'<g transform="rotate(-14 {cx} {cy})"><path class="s-mint" fill="none" stroke-width="{max(3, r * 0.14):.1f}" stroke-linecap="round" d="M{cx - rx} {cy} A{rx} {ry} 0 0 0 {cx + rx} {cy}"/></g>'
    return back + body + front


def asteroid(w=520, h=250):
    sx, sy = w / 400, h / 232
    return (
        f'<g transform="scale({sx:.3f} {sy:.3f})">'
        '<path class="f-asteroid s-ink" stroke-width="5" d="M30 120 C 20 60, 90 20, 170 28 C 250 14, 350 30, 375 90 C 398 150, 362 210, 280 214 C 200 226, 110 222, 60 200 C 30 186, 34 160, 30 120 Z"/>'
        '<ellipse class="f-asteroid-crater" cx="70" cy="190" rx="16" ry="6"/>'
        '<ellipse class="f-asteroid-crater" cx="352" cy="70" rx="12" ry="5"/>'
        '</g>'
    )


# ---------------------------------------------------------------- Scruffles in the pod (viewBox 0 0 400 430)

SCRUFFLES_HEAD = (
    '<path class="f-scruffles-grey s-ink" stroke-width="5" stroke-linejoin="round" d="M140 196 L142 146 L172 164 Z"/>'
    '<path class="f-scruffles-grey s-ink" stroke-width="5" stroke-linejoin="round" d="M260 196 L258 146 L228 164 Z"/>'
    '<path class="f-ear-pink" d="M148 186 L149 160 L166 172 Z"/>'
    '<path class="f-ear-pink" d="M252 186 L251 160 L234 172 Z"/>'
    '<path class="f-scruffles-grey s-ink" stroke-width="5" stroke-linejoin="round" d="M200 154 C 240 154, 270 180, 270 208 L 282 220 L 268 228 L 278 242 L 258 248 C 246 264, 224 272, 200 272 C 176 272, 154 264, 142 248 L 122 242 L 132 228 L 118 220 L 130 208 C 130 180, 160 154, 200 154 Z"/>'
    '<path class="f-cat-white" d="M200 166 C 204 186, 208 202, 212 212 C 220 224, 240 228, 248 244 C 252 260, 230 270, 200 270 C 170 270, 148 260, 152 244 C 160 228, 180 224, 188 212 C 192 202, 196 186, 200 166 Z"/>'
    '<path class="f-nose-pink s-ink" stroke-width="2.5" stroke-linejoin="round" d="M192 232 L208 232 L200 241 Z"/>'
    '<path class="s-ink" fill="none" stroke-width="2.5" stroke-linecap="round" d="M216 244 L262 236 M216 251 L260 260 M184 244 L152 240"/>'
    '<path class="s-teal-band" fill="none" stroke-width="5" stroke-linecap="round" d="M126 214 C 116 236, 128 256, 156 258"/>'
    '<circle class="f-mint s-ink" stroke-width="4" cx="126" cy="212" r="12"/>'
    '<circle class="f-mint s-ink" stroke-width="3" cx="160" cy="258" r="6"/>'
)

FACES = {
    "thinking": (
        '<ellipse class="f-scruffles-eye s-ink" stroke-width="2.5" cx="172" cy="212" rx="12" ry="13"/>'
        '<ellipse class="f-ink" cx="169" cy="213" rx="4.5" ry="9"/><circle class="f-cat-white" cx="166" cy="207" r="3"/>'
        '<ellipse class="f-scruffles-eye s-ink" stroke-width="2.5" cx="228" cy="212" rx="12" ry="13"/>'
        '<ellipse class="f-ink" cx="225" cy="213" rx="4.5" ry="9"/><circle class="f-cat-white" cx="222" cy="207" r="3"/>'
        '<path class="s-ink" fill="none" stroke-width="3" stroke-linecap="round" d="M190 250 C 194 256, 200 254, 200 246 C 200 254, 206 256, 210 250"/>'
    ),
    "got-it": (
        '<path class="s-ink" fill="none" stroke-width="5" stroke-linecap="round" d="M160 216 C 164 202, 180 202, 184 216"/>'
        '<path class="s-ink" fill="none" stroke-width="5" stroke-linecap="round" d="M216 216 C 220 202, 236 202, 240 216"/>'
        '<path class="f-mouth s-ink" stroke-width="3" stroke-linejoin="round" d="M188 246 C 190 264, 210 264, 212 246 Z"/>'
    ),
    "try-again": (
        '<path class="s-ink" fill="none" stroke-width="3.5" stroke-linecap="round" d="M158 194 C 164 188, 176 188, 184 192"/>'
        '<path class="s-ink" fill="none" stroke-width="3.5" stroke-linecap="round" d="M216 192 C 224 188, 236 188, 242 194"/>'
        '<ellipse class="f-scruffles-eye s-ink" stroke-width="2.5" cx="172" cy="213" rx="12" ry="13"/>'
        '<ellipse class="f-ink" cx="172" cy="214" rx="4.5" ry="9"/><circle class="f-cat-white" cx="168" cy="208" r="3"/>'
        '<ellipse class="f-scruffles-eye s-ink" stroke-width="2.5" cx="228" cy="213" rx="12" ry="13"/>'
        '<ellipse class="f-ink" cx="228" cy="214" rx="4.5" ry="9"/><circle class="f-cat-white" cx="224" cy="208" r="3"/>'
        '<path class="s-ink" fill="none" stroke-width="3" stroke-linecap="round" d="M188 250 C 194 258, 206 258, 212 250"/>'
    ),
}


def scruffles_pod(face="thinking", w=400):
    h = w * 430 / 400
    return (
        f'<svg width="{w:.0f}" height="{h:.0f}" viewBox="0 0 400 430" aria-hidden="true">'
        '<ellipse class="f-mint" cx="200" cy="412" rx="130" ry="14" opacity="0.2"/>'
        '<rect class="f-peach s-ink" stroke-width="5" x="140" y="358" width="34" height="42" rx="10"/>'
        '<rect class="f-peach s-ink" stroke-width="5" x="226" y="358" width="34" height="42" rx="10"/>'
        '<line class="s-ink" stroke-width="5" stroke-linecap="round" x1="200" y1="132" x2="200" y2="102"/>'
        '<circle class="f-peach s-ink" stroke-width="4" cx="200" cy="94" r="11"/>'
        '<path class="f-cat-white s-ink" stroke-width="4" stroke-linejoin="round" d="M136 250 L150 264 L162 252 L176 268 L188 254 L200 270 L212 254 L224 268 L238 252 L250 264 L264 250 L276 304 L124 304 Z"/>'
        + SCRUFFLES_HEAD + FACES[face] +
        '<path class="f-glass" opacity="0.18" d="M30 300 A170 170 0 0 1 370 300 Z"/>'
        '<path class="s-cat-white" fill="none" stroke-width="7" stroke-linecap="round" opacity="0.45" d="M74 250 C 88 198, 126 162, 170 150"/>'
        '<path class="s-ink" fill="none" stroke-width="6" d="M30 300 A170 170 0 0 1 370 300"/>'
        '<path class="f-mint s-ink" stroke-width="6" stroke-linejoin="round" d="M24 300 C 40 392, 360 392, 376 300 Z"/>'
        '<ellipse class="f-mint-dark s-ink" stroke-width="6" cx="200" cy="300" rx="176" ry="18"/>'
        + "".join(f'<circle class="f-peach s-ink" stroke-width="3" cx="{x}" cy="{y}" r="10"/>' for x, y in [(88, 330), (144, 344), (200, 348), (256, 344), (312, 330)]) +
        '</svg>'
    )


def scruffles_face(face, w=170):
    h = w * 160 / 180
    return (f'<svg width="{w}" height="{h:.0f}" viewBox="110 136 180 160" aria-hidden="true">'
            + SCRUFFLES_HEAD + FACES[face] + '</svg>')


def scruffles_standing(w=320):
    h = w * 400 / 320
    head = SCRUFFLES_HEAD + FACES["thinking"].replace('cx="169"', 'cx="172"').replace('cx="225"', 'cx="228"').replace('cx="166"', 'cx="168"').replace('cx="222"', 'cx="224"')
    return (
        f'<svg width="{w}" height="{h:.0f}" viewBox="0 0 320 400" aria-hidden="true">'
        '<ellipse class="f-mint" cx="160" cy="388" rx="110" ry="9" opacity="0.18"/>'
        '<path class="s-ink" fill="none" stroke-width="38" stroke-linecap="round" d="M222 356 C 296 356, 306 280, 262 252"/>'
        '<path class="s-scruffles-grey" fill="none" stroke-width="28" stroke-linecap="round" d="M222 356 C 296 356, 306 280, 262 252"/>'
        '<path class="f-scruffles-grey s-ink" stroke-width="5" stroke-linejoin="round" d="M92 372 C 74 316, 88 230, 160 206 C 232 230, 246 316, 228 372 Z"/>'
        '<path class="f-cat-white" d="M108 216 L120 230 L132 218 L146 234 L160 220 L174 234 L188 218 L200 230 L212 216 C 222 266, 204 334, 160 344 C 116 334, 98 266, 108 216 Z"/>'
        '<rect class="f-cat-white s-ink" stroke-width="5" x="122" y="310" width="30" height="62" rx="14"/>'
        '<rect class="f-cat-white s-ink" stroke-width="5" x="168" y="310" width="30" height="62" rx="14"/>'
        '<ellipse class="f-cat-white s-ink" stroke-width="5" cx="137" cy="372" rx="22" ry="11"/>'
        '<ellipse class="f-cat-white s-ink" stroke-width="5" cx="183" cy="372" rx="22" ry="11"/>'
        f'<g transform="translate(-40 -58)">{head}</g>'
        '</svg>'
    )


# ---------------------------------------------------------------- Moggles and Snuffles (viewBox 0 0 260 340)

def moggles(w=260):
    h = w * 340 / 260
    return (
        f'<svg width="{w}" height="{h:.0f}" viewBox="0 0 260 340" aria-hidden="true">'
        '<ellipse class="f-mint" cx="130" cy="332" rx="90" ry="8" opacity="0.18"/>'
        '<path class="s-moggles-rim" fill="none" stroke-width="30" stroke-linecap="round" d="M186 316 C 246 316, 252 248, 214 228"/>'
        '<path class="s-moggles-black" fill="none" stroke-width="20" stroke-linecap="round" d="M186 316 C 246 316, 252 248, 214 228"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M74 326 C 60 280, 70 206, 130 190 C 190 206, 200 280, 186 326 Z"/>'
        '<path class="s-fur-shade" fill="none" stroke-width="5" stroke-linecap="round" d="M112 258 L112 314 M148 258 L148 314"/>'
        '<ellipse class="f-moggles-black s-moggles-rim" stroke-width="5" cx="110" cy="324" rx="20" ry="10"/>'
        '<ellipse class="f-moggles-black s-moggles-rim" stroke-width="5" cx="150" cy="324" rx="20" ry="10"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M78 96 L72 38 L118 72 Z"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M182 96 L188 38 L142 72 Z"/>'
        '<path class="f-moggles-ear" d="M84 86 L80 54 L106 74 Z"/><path class="f-moggles-ear" d="M176 86 L180 54 L154 74 Z"/>'
        '<ellipse class="f-moggles-black s-moggles-rim" stroke-width="5" cx="130" cy="122" rx="66" ry="58"/>'
        '<path class="s-fur-shade" fill="none" stroke-width="6" stroke-linecap="round" d="M94 88 C 110 72, 130 68, 150 70"/>'
        '<path class="f-peach s-ink" stroke-width="4" stroke-linejoin="round" d="M84 186 C 108 202, 152 202, 176 186 L 180 204 C 154 222, 106 222, 80 204 Z"/>'
        '<path class="f-peach s-ink" stroke-width="4" stroke-linejoin="round" d="M150 210 L 166 248 L 144 242 Z"/>'
        '<ellipse class="f-moggles-eye" cx="104" cy="118" rx="15" ry="13"/><ellipse class="f-ink" cx="104" cy="119" rx="4.5" ry="10"/><circle class="f-cat-white" cx="99" cy="112" r="3.5"/>'
        '<ellipse class="f-moggles-eye" cx="156" cy="118" rx="15" ry="13"/><ellipse class="f-ink" cx="156" cy="119" rx="4.5" ry="10"/><circle class="f-cat-white" cx="151" cy="112" r="3.5"/>'
        '<path class="f-nose-dark" d="M124 142 L136 142 L130 149 Z"/>'
        '<path class="s-moggles-rim" fill="none" stroke-width="3" stroke-linecap="round" d="M120 156 C 124 162, 130 160, 130 152 C 130 160, 136 162, 140 156"/>'
        '<path class="s-text-3" fill="none" stroke-width="2.5" stroke-linecap="round" d="M100 148 L56 140 M100 156 L58 164 M160 148 L204 140 M160 156 L202 164"/>'
        '</svg>'
    )


def snuffles(w=260):
    h = w * 340 / 260
    return (
        f'<svg width="{w}" height="{h:.0f}" viewBox="0 0 260 340" aria-hidden="true">'
        '<ellipse class="f-mint" cx="130" cy="332" rx="90" ry="8" opacity="0.18"/>'
        '<path class="s-moggles-rim" fill="none" stroke-width="28" stroke-linecap="round" d="M182 316 C 240 316, 246 250, 210 230"/>'
        '<path class="s-moggles-black" fill="none" stroke-width="18" stroke-linecap="round" d="M182 316 C 240 316, 246 250, 210 230"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M80 326 C 66 280, 76 206, 130 190 C 184 206, 194 280, 180 326 Z"/>'
        '<path class="f-cat-white" d="M102 202 C 118 212, 142 212, 158 202 C 168 248, 158 296, 130 308 C 102 296, 92 248, 102 202 Z"/>'
        '<rect class="f-cat-white" x="104" y="262" width="26" height="60" rx="12"/>'
        '<rect class="f-moggles-black" x="104" y="284" width="26" height="22"/>'
        '<rect class="s-ink" fill="none" stroke-width="4" x="104" y="262" width="26" height="60" rx="12"/>'
        '<rect class="f-cat-white s-ink" stroke-width="4" x="132" y="262" width="26" height="60" rx="12"/>'
        '<ellipse class="f-cat-white s-ink" stroke-width="4" cx="117" cy="324" rx="17" ry="9"/>'
        '<ellipse class="f-cat-white s-ink" stroke-width="4" cx="145" cy="324" rx="17" ry="9"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M80 96 L74 40 L118 72 Z"/>'
        '<path class="f-moggles-black s-moggles-rim" stroke-width="5" stroke-linejoin="round" d="M180 96 L186 40 L142 72 Z"/>'
        '<path class="f-snuffles-ear" d="M86 86 L82 56 L106 74 Z"/><path class="f-snuffles-ear" d="M174 86 L178 56 L154 74 Z"/>'
        '<ellipse class="f-moggles-black s-moggles-rim" stroke-width="5" cx="130" cy="120" rx="62" ry="56"/>'
        '<path class="f-cat-white" d="M130 78 C 134 98, 138 112, 142 120 C 154 130, 170 138, 168 156 C 164 172, 146 176, 130 176 C 114 176, 96 172, 92 156 C 90 138, 106 130, 118 120 C 122 112, 126 98, 130 78 Z"/>'
        '<path class="f-mint s-ink" stroke-width="4" stroke-linejoin="round" d="M84 184 C 108 200, 152 200, 176 184 L 180 202 C 154 220, 106 220, 80 202 Z"/>'
        '<ellipse class="f-snuffles-eye" cx="106" cy="114" rx="12" ry="12"/><ellipse class="f-ink" cx="106" cy="115" rx="4" ry="9"/><circle class="f-cat-white" cx="102" cy="109" r="3"/>'
        '<ellipse class="f-snuffles-eye" cx="154" cy="114" rx="12" ry="12"/><ellipse class="f-ink" cx="154" cy="115" rx="4" ry="9"/><circle class="f-cat-white" cx="150" cy="109" r="3"/>'
        '<path class="f-nose-pink s-ink" stroke-width="2" stroke-linejoin="round" d="M124 140 L136 140 L130 147 Z"/>'
        '<path class="s-ink" fill="none" stroke-width="3" stroke-linecap="round" d="M120 154 C 124 160, 130 158, 130 150 C 130 158, 136 160, 140 154"/>'
        '<path class="s-text-3" fill="none" stroke-width="2.5" stroke-linecap="round" d="M114 148 L70 140 M114 156 L72 164 M146 148 L190 140 M146 156 L188 164"/>'
        '</svg>'
    )


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
