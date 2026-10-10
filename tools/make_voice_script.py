"""Write voice/script.json: every line MeeMee World says, for the game page and the recording page.

The lines come from kit/lines.json (the world's own: the map and the crew) and each game's games/<id>/lines.json,
in planet order. Each clip gets the name of its game, so the recording page groups them by game. The build runs this
itself; you can also run it alone:

    python tools/make_voice_script.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import games as G  # noqa: E402

OUT = G.ROOT / "voice" / "script.json"


def build(games):
    clips = []
    for owner, lines in [("MeeMee World", G.world_lines())] + [(g.get("name") or g["folder"].name, g["lines"]) for g in games]:
        for c in lines:
            clip = {"id": c["id"], "game": owner, "group": c["group"], "words": c["words"], "how": c["how"]}
            if c.get("pending"):
                clip["pending"] = True
            clips.append(clip)
    ids = [c["id"] for c in clips]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise SystemExit("voice lines with the same id in more than one place: " + ", ".join(twice))
    return {
        "set": "MeeMee World",
        "version": 2,
        "format": "WAV, mono, 44.1 kHz, 16-bit; silence trimmed; loudness normalised; peaks at most -1 dB",
        "clips": clips,
    }


def main(extra=(), out=OUT):
    script = build(G.load(extra))
    text = json.dumps(script, indent=2, ensure_ascii=False) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8", newline="\n")
    return script


if __name__ == "__main__":
    s = main()
    print(len(s["clips"]), "clips ->", OUT)
