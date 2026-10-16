"""Take MeeMee Home's own drawings: the MeeMee's home planet, its houses and the game's badge (mock-up rounds 10 and 11,
approved by Barney on 15 October 2026; copied from the round's art.py with its names changed to the game's, not redrawn).
The design system's TakeMeeMeeHome card describes them. Tokens only.

    takehome-badge      the badge: a MeeMee house on its peach planet in a round night window (56 on the map; the
                        title banner shows it at 112)
    takehome-home       the top of the home planet with three houses, 680 x 240, for the game screen's bottom right
                        (stage left 600, top 560)
    takehome-home-wide  the end screen's ground: the home planet's gentle curve across the bottom, 1280 x 240 (0, 560)
"""
import math

from gen_art import tok, planet


def house(x, base, s=1.0, sw=4):
    """A MeeMee house: a moon dome with two ear points on top and a round door. base is the ground line; sw the outline."""
    r = 15 * s
    cy = base
    def p(dx, dy):
        return f"{x + dx * s:.1f} {cy + dy * s:.1f}"
    ears = (f'<path d="M{p(-13, -7.2)} L{p(-14.5, -27)} L{p(-2.5, -14.8)} Z" fill="@moon" stroke="@ink" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<path d="M{p(13, -7.2)} L{p(14.5, -27)} L{p(2.5, -14.8)} Z" fill="@moon" stroke="@ink" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<path d="M{p(-11.5, -12)} L{p(-12.4, -22.5)} L{p(-6, -15)} Z" fill="@ear-pink"/>'
            f'<path d="M{p(11.5, -12)} L{p(12.4, -22.5)} L{p(6, -15)} Z" fill="@ear-pink"/>')
    dome = (f'<path d="M{p(-15, 0)} A{r:.1f} {r:.1f} 0 0 1 {p(15, 0)} Z" fill="@moon" stroke="@ink" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<path d="M{p(-11.5, -2)} A{r * 0.78:.1f} {r * 0.78:.1f} 0 0 1 {p(-4, -11)}" fill="none" stroke="@highlight" stroke-width="{max(1.5, sw * 0.5):.1f}" stroke-linecap="round" opacity="0.7"/>'
            f'<path d="M{p(-4.5, 0)} L{p(-4.5, -5)} A{4.5 * s:.1f} {4.5 * s:.1f} 0 0 1 {p(4.5, -5)} L{p(4.5, 0)} Z" fill="@night-raised"/>'
            f'<circle cx="{x + 8.5 * s:.1f}" cy="{cy - 6.5 * s:.1f}" r="{1.7 * s:.1f}" fill="@spark"/>')
    return tok(ears + dome)


def badge(size=56):
    """The game's badge: a little night scene in a round window: a MeeMee house on its peach home planet, two stars."""
    sky = tok('<clipPath id="takehome-badge-c"><circle cx="50" cy="50" r="47"/></clipPath>'
              '<circle cx="50" cy="50" r="47" fill="@night-raised"/>')
    ground = planet(50, 150, 82, "peach", "takehome-badge-p", bands=4, craters=[(-0.42, -0.74, 0.08), (0.46, -0.7, 0.06)], rim=False)
    stars = tok('<circle cx="22" cy="30" r="3" fill="@spark"/><circle cx="80" cy="24" r="2.4" fill="@spark"/><circle cx="74" cy="46" r="1.8" fill="@spark"/>')
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">' + sky
            + '<g clip-path="url(#takehome-badge-c)">' + stars + ground + house(50, 75, 1.7, sw=4.5) + '</g></svg>')


def home(w=680, h=240):
    """The top of the MeeMee's home planet, for the bottom-right of the game screen, with three houses on it."""
    cx, cy, r = 420, 700, 600
    body = planet(cx, cy, r, "peach", "takehome-home-p", bands=6,
                  craters=[(-0.2, -0.8, 0.045), (0.24, -0.84, 0.03), (0.05, -0.77, 0.025)])
    def ground(x):
        return cy - math.sqrt(r * r - (x - cx) ** 2)
    houses = "".join(house(x, ground(x) + 5, s) for x, s in [(300, 2.2), (430, 2.5), (560, 2.2)])
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">' + body + houses + '</svg>')


def home_wide(w=1280, h=240):
    """The end screen's ground: the home planet's gentle curve across the bottom, with houses in the foreground."""
    cx, cy, r = 640, 3443, 3413
    body = planet(cx, cy, r, "peach", "takehome-wide-p", bands=6,
                  craters=[(-0.114, -0.968, 0.007), (0.135, -0.95, 0.006), (0.0176, -0.941, 0.005), (-0.04, -0.975, 0.004)])
    houses = "".join(house(x, base, s) for x, base, s in [(470, 205, 2.4), (1150, 190, 2.2)])
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">' + body + houses + '</svg>')


def templates():
    return {"takehome-badge": badge(56), "takehome-home": home(), "takehome-home-wide": home_wide()}
