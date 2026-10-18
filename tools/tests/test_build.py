"""Checks for the build's own checks (phase 5): each rule a game must follow is broken on purpose, once, in a copy of
the template, and the build must say so. The real games must pass.

    python tools/tests/test_build.py
"""
import json
import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "design"))
import build  # noqa: E402
import games as G  # noqa: E402
import gen_scenes  # noqa: E402
import make_voice_script  # noqa: E402

RESULTS = []
TEMPLATE = ROOT / "games" / "_template"
FREE = [i for i in range(G.PLANETS) if i not in {g.get("planet") for g in G.load()}]   # planets with no game yet


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def problems_for(games):
    script = make_voice_script.build(games)
    art = {}
    for g in games:
        art.update(build.game_art(g))
    names = set(gen_scenes.art_dict(extra=art))
    return build.game_problems(games, {c["id"] for c in script["clips"]}, names) + build.art_problems(games, art)


def copy_template(tmp, folder="probe", edit=None):
    """A copy of the template as games/<folder>, with every 'starter' renamed and a free planet, then edit(folder) applied."""
    dst = pathlib.Path(tmp) / folder
    shutil.copytree(TEMPLATE, dst)
    for f in dst.iterdir():
        if f.is_file():
            f.write_text(f.read_text(encoding="utf-8").replace("starter", folder), encoding="utf-8")
    edit_json(dst / "game.json", planet=FREE[0])
    if edit:
        edit(dst)
    return dst


def edit_json(path, **changes):
    d = json.loads(path.read_text(encoding="utf-8"))
    d.update(changes)
    path.write_text(json.dumps(d), encoding="utf-8")


def append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def main():
    real = G.load()
    if not FREE:
        print("Every place on the map has a game, so the template can't be added to test the build's checks.")
        print("A sixth game needs a new map layout first (MEEMEE.md, Open decisions).")
        sys.exit(0)
    p = problems_for(real)
    check("the real games pass the build's checks", not p, "; ".join(p[:3]))

    # 0.8.0: the map has five places, and its drawing (design/gen_scenes.py), its buttons (kit/map.js) and the build
    # (tools/games.py) agree on them
    drawn = [(x, y) for x, y, _, _ in gen_scenes.MAP["planets"]] + [(x, y) for x, y, _ in gen_scenes.MAP["places"]]
    buttons = [(int(x), int(y)) for x, y in re.findall(r"\{ x: (\d+), y: (\d+), tap:", (ROOT / "kit" / "map.js").read_text(encoding="utf-8"))]
    check("the map has five places, at the same positions in its drawing and its buttons", G.PLANETS == 5 and drawn == buttons and len(drawn) == 5,
          json.dumps([G.PLANETS, drawn, buttons]))

    cases = [
        ("a renamed copy of the template passes", None, None),
        ("a raw colour in a game's JS", lambda d: append(d / "game.js", "\nstar.style.background = '#ff8800';\n"), "raw colour"),
        ("a colour name set in a game's JS", lambda d: append(d / "game.js", "\nstar.style.color = 'white';\n"), "raw colour (white)"),
        ("a colour set through setAttribute", lambda d: append(d / "game.js", "\nstar.setAttribute('fill', 'red');\n"), "raw colour (red)"),
        ("a colour inside an SVG string", lambda d: append(d / "game.js", "\nconst s = '<circle fill=\"#a0b0c0\" r=\"3\"/>';\n"), "raw colour"),
        ("a colour function in capitals", lambda d: append(d / "game.js", "\nconst c = 'RGB(1, 2, 3)';\n"), "raw colour"),
        ("a colour name in a game's CSS", lambda d: append(d / "game.css", "\n.x { border: 2px solid white; }\n"), "raw colour (white)"),
        ("a modern colour function in CSS", lambda d: append(d / "game.css", "\n.x { color: oklch(70% 0.1 200); }\n"), "raw colour"),
        ("a raw colour in a script in a subfolder", lambda d: ((d / "parts").mkdir(), (d / "parts" / "extra.js").write_text("x.style.fill = '#123456';", encoding="utf-8")), "parts/extra.js: a raw colour"),
        ("</script> in a game's code", lambda d: append(d / "game.js", "\nconst t = '</script>';\n"), "</script>"),
        ("a raw colour in a game's CSS", lambda d: append(d / "game.css", "\n.x { color: rgb(255, 0, 0); }\n"), "raw colour"),
        ("a raw colour in a game's drawings", lambda d: append(d / "art.py", "\nX = '#a0b0c0'\n"), "raw colour"),
        ("a game playing sound itself", lambda d: append(d / "game.js", "\nconst ctx = new AudioContext();\n"), "plays sound itself"),
        ("a game using speech synthesis", lambda d: append(d / "game.js", "\nspeechSynthesis.speak(x);\n"), "plays sound itself"),
        ("an id that isn't the folder's name", lambda d: edit_json(d / "game.json", id="other"), "but the folder is"),
        ("a planet that isn't on the map (5: a sixth place, after the rocks and the station)", lambda d: edit_json(d / "game.json", planet=5), "planet must be 0 to 4"),
        ("a planet that isn't a number", lambda d: edit_json(d / "game.json", planet="3"), "planet must be 0 to 4"),
        ("a planet another game has", lambda d: edit_json(d / "game.json", planet=0), "already rescue's"),
        ("a badge that isn't a drawing", lambda d: edit_json(d / "game.json", badge="nothing"), "badge"),
        ("a spoken name that isn't a line", lambda d: edit_json(d / "game.json", say="nothing"), "say"),
        ("a script that isn't there", lambda d: edit_json(d / "game.json", scripts=["game.js", "missing.js"]), "isn't in the folder"),
        ("a game that never joins the world", lambda d: (d / "game.js").write_text("(function () {})();\n", encoding="utf-8"), "joins the world"),
        ("a line without the game's id in front", lambda d: (d / "lines.json").write_text(
            (d / "lines.json").read_text(encoding="utf-8").replace('"probe-tap"', '"tap-now"'), encoding="utf-8"), "should start with 'probe-'"),
        ("a screen without the game's id in front", lambda d: (d / "game.js").write_text(
            (d / "game.js").read_text(encoding="utf-8").replace("'screen-probe-play'", "'screen-play'"), encoding="utf-8"), "screen 'screen-play'"),
        ("a drawing without the game's id in front", lambda d: (d / "art.py").write_text(
            (d / "art.py").read_text(encoding="utf-8").replace('"probe-star"', '"big-star"'), encoding="utf-8"), "big-star"),
    ]
    for label, edit, expect in cases:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                games = real + [G.load_folder(copy_template(tmp, edit=edit))]
                p = problems_for(games)
            except (Exception, SystemExit) as e:   # some breakages stop the build before the checks
                p = [f"{type(e).__name__}: {e}"]
            if expect is None:
                check(f"build: {label}", not p, "; ".join(p[:3]))
            else:
                check(f"build: {label} stops the build", any(expect in x for x in p), "; ".join(p[:2]) or "no problem found")

    # 0.8.0: a game can take a free place; 0.9.0: the station (4) is MeeMee Station's, so the rocks (3) are the only free
    # place, and a new game on the station stops the build; two games can't share a place
    with tempfile.TemporaryDirectory() as tmp:
        d = copy_template(tmp, edit=lambda d: edit_json(d / "game.json", planet=3))
        p = problems_for(real + [G.load_folder(d)])
        check("build: a game on place 3 (the rocks, the one free place) builds", FREE == [3] and not p, f"free: {FREE}; " + "; ".join(p[:3]))
    with tempfile.TemporaryDirectory() as tmp:
        d = copy_template(tmp, edit=lambda d: edit_json(d / "game.json", planet=4))
        p = problems_for(real + [G.load_folder(d)])
        check("build: a game on place 4 (the station, MeeMee Station's) stops the build", any("planet 4 is already station's" in x for x in p),
              "; ".join(p[:2]) or "no problem found")
    with tempfile.TemporaryDirectory() as tmp:
        place = FREE[-1]
        one = copy_template(tmp, "probe", lambda d: edit_json(d / "game.json", planet=place))
        two = copy_template(tmp, "probetwo", lambda d: edit_json(d / "game.json", planet=place))
        p = problems_for(real + [G.load_folder(one), G.load_folder(two)])
        check(f"build: two new games on one place ({place}) stops the build", any(f"planet {place} is already probe's" in x for x in p), "; ".join(p[:2]) or "no problem found")

    # things that look a bit like colours or sound, but aren't: the build must not complain
    harmless = """
// issue #123: the star used to use rgba(…) and an AudioContext; now it uses MW.audio
/* fill: '#ff8800' was the old colour */
const a = document.querySelector('#screen-probe-play .probe-card');
const b = document.querySelector('#bead');
const c = '#add-card';
const word = 'red';           // a word to read, not a colour
const kinds = ['white', 'black'];
star.style.background = 'var(--peach)';
star.setAttribute('fill', 'none');
"""
    harmless_css = """
/* rgb(1,2,3) and white in a comment */
#screen-probe-play .probe-card { background: var(--moon); color: var(--numeral); box-shadow: var(--press-ink); border: 4px solid var(--mint); }
.probe-card.is-on { border-color: var(--peach); }
"""
    with tempfile.TemporaryDirectory() as tmp:
        d = copy_template(tmp, edit=lambda d: (append(d / "game.js", harmless), append(d / "game.css", harmless_css)))
        p = problems_for(real + [G.load_folder(d)])
        check("build: selectors, words, tokens and comments that only look like colours or sound pass", not p, "; ".join(p[:3]))

    # two games with the same line id
    with tempfile.TemporaryDirectory() as tmp:
        d = copy_template(tmp)
        (d / "lines.json").write_text((d / "lines.json").read_text(encoding="utf-8").replace('"probe-tap"', '"map-welcome"'), encoding="utf-8")
        try:
            make_voice_script.build(real + [G.load_folder(d)])
            ok = False
        except SystemExit as e:
            ok = "map-welcome" in str(e)
        check("build: a line id used twice stops the build", ok)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} build checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
