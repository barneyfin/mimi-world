"""Build MeeMee World into docs/ (the folder GitHub Pages publishes).

    python tools/build.py              everything: audio, pages, offline copy, icons, checks
    python tools/build.py --no-audio   reuse docs/audio/ as it is (faster; needs a previous full build)

Needs Python 3.10+, ffmpeg on PATH, and the packages numpy, scipy, pyloudnorm and playwright (with Chromium).
The build stops with a message if a check fails: a missing recording, an outside address, a fast flashing animation.
"""
import base64
import hashlib
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
KIT = ROOT / "kit"
sys.path.insert(0, str(ROOT / "design"))
sys.path.insert(0, str(ROOT / "tools"))

from gen_tokens import COLOURS, OPACITY, RADIUS, SHADOWS, SIZES, SPACING, TYPE_STYLES  # noqa: E402
import gen_scenes  # noqa: E402

VERSION = "0.3.2"
KIT_JS = ["core.js", "audio.js", "drag.js", "scene.js", "shell.js", "grownups.js"]


# ---------------------------------------------------------------- tokens -> CSS
def tokens_css():
    hexes = {n: v for n, v, _ in COLOURS}

    def resolve(v):
        m = re.fullmatch(r"\{(.+)\}", v)
        return resolve(hexes[m.group(1)]) if m else v

    lines = [":root {", '  --font-andika: "Andika", system-ui, sans-serif;']
    lines += [f"  --{n}: {resolve(v)};" for n, v, _ in COLOURS]
    for group in (SPACING, RADIUS, SIZES, SHADOWS, OPACITY):
        lines += [f"  --{n}: {v};" for n, v, _ in group]
    lines.append("}")
    # colour helpers: f- fill, s- stroke, bg- background, c- text colour
    lines += [f".f-{n}{{fill:var(--{n})}}.s-{n}{{stroke:var(--{n})}}.bg-{n}{{background:var(--{n})}}.c-{n}{{color:var(--{n})}}" for n, _, _ in COLOURS]
    # type styles
    for styles in TYPE_STYLES.values():
        for s in styles:
            lh = s["lineHeight"] if isinstance(s["lineHeight"], str) else str(s["lineHeight"])
            lines.append(f".{s['name']}{{font-family:var(--font-andika);font-size:{s['fontSize']};line-height:{lh};font-weight:{s['fontWeight']}}}")
    return "\n".join(lines)


# ---------------------------------------------------------------- the game page
def build_game(audio_manifest):
    script = json.loads((ROOT / "voice" / "script.json").read_text(encoding="utf-8"))
    page = (ROOT / "games" / "rescue" / "index.template.html").read_text(encoding="utf-8")
    js = "\n".join((KIT / f).read_text(encoding="utf-8") for f in KIT_JS)
    js += "\n" + (ROOT / "games" / "rescue" / "rescue.js").read_text(encoding="utf-8")
    audio = {
        "voice": {k: {"dur": v["dur"]} for k, v in audio_manifest["voice"].items()},
        "effects": {k: {"dur": v["dur"]} for k, v in audio_manifest["effects"].items()},
        "music": {"dur": audio_manifest["music"]["dur"], "fade": audio_manifest["music"]["fade"]},
    }
    # a clip still waiting for its recording (pending) stays off the game page
    clips = [{"id": c["id"], "group": c["group"], "words": c["words"]} for c in script["clips"] if c["id"] in audio["voice"]]
    parts = {
        "__FONT400__": base64.b64encode((KIT / "Andika-400.woff2").read_bytes()).decode("ascii"),
        "__FONT700__": base64.b64encode((KIT / "Andika-700.woff2").read_bytes()).decode("ascii"),
        "__TOKENS_CSS__": tokens_css(),
        "__KIT_CSS__": (KIT / "kit.css").read_text(encoding="utf-8"),
        "__SKY__": gen_scenes.sky(),
        "__ART__": gen_scenes.templates(),
        "__VERSION__": VERSION,
        "__AUDIO__": json.dumps(audio, separators=(",", ":")),
        "__SCRIPT__": json.dumps(clips, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        "__JS__": js,
    }
    for k, v in parts.items():
        if k not in page:
            raise SystemExit(f"template has no {k}")
        page = page.replace(k, v)
    leftover = re.findall(r"__[A-Z0-9]+__", page)
    if leftover:
        raise SystemExit(f"placeholders left in the page: {leftover}")
    (DOCS / "index.html").write_text(page, encoding="utf-8", newline="\n")
    return page


# ---------------------------------------------------------------- the recording page (Barney's PC)
def build_record_page():
    script = json.loads((ROOT / "voice" / "script.json").read_text(encoding="utf-8"))
    page = (ROOT / "tools" / "record" / "record.template.html").read_text(encoding="utf-8")
    page = page.replace("__SCRIPT_JSON__", json.dumps(script, ensure_ascii=False).replace("</", "<\\/"))
    page = page.replace("__FONT400__", base64.b64encode((KIT / "Andika-400.woff2").read_bytes()).decode("ascii"))
    page = page.replace("__FONT700__", base64.b64encode((KIT / "Andika-700.woff2").read_bytes()).decode("ascii"))
    if "__" in page.replace("window.__rec", ""):
        raise SystemExit("placeholder left in the record page")
    (DOCS / "record").mkdir(parents=True, exist_ok=True)
    (DOCS / "record" / "index.html").write_text(page, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- icons
def render_icons():
    import asyncio
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for name, scale in (("icon-512.png", 1), ("icon-192.png", 0.375)):
                page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=scale)
                await page.goto((ROOT / "design" / "icon.html").as_uri())
                await page.locator("#icon").screenshot(path=str(DOCS / name))
            await browser.close()
    asyncio.run(go())


# ---------------------------------------------------------------- offline copy
def build_sw():
    files = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"]
    files += ["./" + p.relative_to(DOCS).as_posix() for p in sorted((DOCS / "audio").rglob("*.mp3"))]
    digest = hashlib.sha1()
    for f in files[1:]:
        digest.update((DOCS / f[2:]).read_bytes())
    cache = f"mimi-world-v{VERSION}-{digest.hexdigest()[:8]}"
    sw = (KIT / "sw.template.js").read_text(encoding="utf-8")
    sw = sw.replace("__CACHE__", cache).replace("__FILES__", json.dumps(files, indent=2).replace("\n", "\n"))
    (DOCS / "sw.js").write_text(sw, encoding="utf-8", newline="\n")
    return cache, files


# ---------------------------------------------------------------- checks
def checks(page):
    problems = []
    # nothing leaves the tablet: no outside addresses (the SVG namespace is a name, not a request)
    for url in re.findall(r"https?://[^\s\"'<>)]+", page):
        if not url.startswith("http://www.w3.org/"):
            problems.append(f"outside address in the page: {url}")
    # flashing: any animation that repeats must be slower than 1 second per cycle
    for m in re.finditer(r"animation:\s*([^;}]+)", page):
        decl = m.group(1)
        if "infinite" in decl:
            d = re.search(r"(\d+(?:\.\d+)?)(ms|s)\b", decl)
            secs = float(d.group(1)) / (1000 if d.group(2) == "ms" else 1) if d else 0
            if secs < 1:
                problems.append(f"repeating animation faster than once a second: {decl.strip()}")
    # the website is public: it never says the family's private names. They are listed, one per line, in
    # tools/private-names.txt, which stays on the PC (it's in .gitignore) so the names aren't in the repository either.
    names_file = ROOT / "tools" / "private-names.txt"
    names = [n.strip() for n in names_file.read_text(encoding="utf-8").splitlines() if n.strip()] if names_file.exists() else []
    if not names:
        print("warning: tools/private-names.txt is missing, so the private-name check was skipped")
    for f in [DOCS / "index.html", DOCS / "record" / "index.html"]:
        text = f.read_text(encoding="utf-8")
        for n in names:
            if re.search(r"\b" + re.escape(n) + r"\b", text):
                problems.append(f"{f.relative_to(ROOT)} contains a private name")
    # every voice clip in the script has its web file
    script = json.loads((ROOT / "voice" / "script.json").read_text(encoding="utf-8"))
    for c in script["clips"]:
        if not (DOCS / "audio" / "voice" / f"{c['id']}.mp3").exists():
            if c.get("pending"):
                print(f"note: {c['id']} is waiting for its recording; the game doesn't use it yet")
            else:
                problems.append(f"no web audio for {c['id']}")
    if problems:
        raise SystemExit("Build checks failed:\n  " + "\n  ".join(problems))


def main():
    full = "--no-audio" not in sys.argv
    if full:
        import make_audio
        manifest = make_audio.main()
    else:
        manifest = json.loads((ROOT / "tools" / "audio-manifest.json").read_text(encoding="utf-8"))
    DOCS.mkdir(exist_ok=True)
    page = build_game(manifest)
    build_record_page()
    shutil.copy(KIT / "manifest.json", DOCS / "manifest.json")
    if full or not (DOCS / "icon-512.png").exists():
        render_icons()
    cache, files = build_sw()
    checks(page)
    print(f"MeeMee World {VERSION}: index.html {len(page.encode('utf-8')) / 1024:.0f} KB, offline copy {cache} ({len(files)} files)")


if __name__ == "__main__":
    main()
