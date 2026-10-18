"""MeeMee Station's own drawings: the game's badge and the shutter on a closed window (mock-up rounds 12 to 15, approved
by Barney on 16 and 17 October 2026; copied from the round's art.py with its names changed to the game's, not redrawn).
The design system's MeeMeeStation card describes them. Tokens only.

    station-badge     the badge: the station in a round night window, three MeeMee aboard (56 on the map; the title
                      banner shows it at 112)
    station-shutter   a window's shutter, pulled down over a window past the whole (the hint, and every right answer)

The station itself and its hull modules are drawn by the game's own script (draw.js), since their sizes change from
screen to screen.
"""
from gen_art import tok


def badge(size=56):
    """The station in a round night window, with two stars."""
    sky = tok('<clipPath id="station-badge-c"><circle cx="50" cy="50" r="47"/></clipPath>'
              '<circle cx="50" cy="50" r="47" fill="@night-raised"/>'
              '<circle cx="20" cy="26" r="2.6" fill="@spark"/><circle cx="80" cy="78" r="2.2" fill="@spark"/><circle cx="28" cy="80" r="1.6" fill="@spark"/>')
    # the station as in the game: a mint truss with indigo solar wings at each end, and the ten modules in the
    # middle (2 rows of 5), three with a MeeMee in their window
    body = '<rect x="10" y="47" width="80" height="6" rx="2" fill="@mint-deep" stroke="@ink" stroke-width="2"/>'
    for wx in (13, 87):
        body += (f'<rect x="{wx - 7}" y="25" width="14" height="19" rx="2" fill="@planet-indigo" stroke="@ink" stroke-width="2"/>'
                 f'<rect x="{wx - 7}" y="56" width="14" height="19" rx="2" fill="@planet-indigo" stroke="@ink" stroke-width="2"/>'
                 f'<path d="M{wx} 26 V43 M{wx} 57 V74" stroke="@planet-indigo-light" stroke-width="1.4"/>')
    body += '<rect x="44" y="16" width="16" height="17" rx="4" fill="@moon" stroke="@ink" stroke-width="2"/>'
    wins = ""
    for r in range(2):
        for c in range(5):
            x, y = 25 + c * 11, 36 + r * 17
            wins += (f'<rect x="{x}" y="{y}" width="10" height="11" rx="2.5" fill="@moon" stroke="@ink" stroke-width="1.6"/>'
                     f'<circle cx="{x + 5}" cy="{y + 5.5}" r="3.3" fill="@{"mimi" if r == 0 and c < 3 else "night-raised"}"/>')
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">' + sky
            + '<g clip-path="url(#station-badge-c)">' + tok(body + wins) + '</g></svg>')


def shutter(size=100):
    """A window's shutter, pulled down over a window past the whole."""
    slats = "".join(f'<path d="M14 {y} H86" stroke="@ink" stroke-width="3" stroke-linecap="round" opacity="0.7"/>' for y in (30, 44, 58, 72))
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">'
            + tok('<circle cx="50" cy="50" r="44" fill="@night-button"/>' + slats
                  + '<circle cx="50" cy="50" r="44" fill="none" stroke="@ink" stroke-width="3"/>')
            + '</svg>')


def templates():
    return {"station-badge": badge(56), "station-shutter": shutter(100)}
