"""The games in MeeMee World: each folder in games/ with a game.json, in planet order.

A folder whose name starts with "_" (the template) isn't a game; the tests can add one with extra=[path].
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAMES = ROOT / "games"
PLANETS = 3                     # the map's planets: 0 ringed mint, 1 indigo, 2 small peach (kit/map.js)
LEGACY = {"rescue"}             # older than the naming rules (prefixed line ids and screen ids)


def load(extra=()):
    folders = [p for p in sorted(GAMES.iterdir()) if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "game.json").exists()]
    folders += [pathlib.Path(e).resolve() for e in extra]
    return sorted([load_folder(f) for f in folders], key=lambda g: g.get("planet") if isinstance(g.get("planet"), int) else 99)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path.relative_to(ROOT) if ROOT in path.parents else path} isn't valid JSON: {e}")


def load_folder(f):
    f = pathlib.Path(f)
    g = read_json(f / "game.json")
    if not isinstance(g, dict):
        raise SystemExit(f"games/{f.name}/game.json should be an object with id, name, planet, badge, say and scripts")
    g["folder"] = f
    lines = f / "lines.json"
    g["lines"] = read_json(lines).get("lines", []) if lines.exists() else []
    for i, c in enumerate(g["lines"]):
        missing = [k for k in ("id", "group", "words", "how") if not isinstance(c, dict) or k not in c]
        if missing:
            raise SystemExit(f"games/{f.name}/lines.json: line {i + 1} has no {', '.join(missing)}")
    return g


def world_lines():
    return read_json(ROOT / "kit" / "lines.json")["lines"]


def page_info(games):
    """What the page itself needs to know about each game (window.MW_GAMES)."""
    return [{k: g.get(k) for k in ("id", "name", "planet", "badge", "say")} for g in games]
