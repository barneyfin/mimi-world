"""The starter game's own drawings. The build calls templates() and puts each one on the page, for MW.art(name).

Names start with the game's id. Colours are tokens written as fill="@token" or stroke="@token"; tok() turns them
into classes and stops the build if a colour isn't a token. Draw with design/gen_art.py's helpers where they fit.
"""
from gen_art import tok

STAR = "50,8 61,38 93,38 67,57 77,89 50,70 23,89 33,57 7,38 39,38"


def star(size, fill="peach"):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">'
            + tok(f'<polygon points="{STAR}" fill="@{fill}" stroke="@ink" stroke-width="5" stroke-linejoin="round"/>'
                  '<path d="M38 34 L46 30" stroke="@spark" stroke-width="4" stroke-linecap="round"/>')
            + '</svg>')


def templates():
    return {"starter-badge": star(56), "starter-star": star(240)}
