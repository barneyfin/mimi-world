"""Build MeeMee World into docs/ (the folder GitHub Pages publishes): one page with every game on its map.

    python tools/build.py              everything: voice script, audio, pages, offline copy, icons, checks
    python tools/build.py --no-audio   reuse docs/audio/ as it is (faster; needs a previous full build)

For the tests:
    --out FOLDER          build into another folder (copies docs/audio and the icons; implies --no-audio)
    --extra-game FOLDER   add a game folder that isn't in games/ (the template); may be given more than once

A game is a folder games/<id>/ with game.json, lines.json and its scripts (the meemee-world skill, reference.md).
Folders starting with "_" (games/_template) are skipped.

Needs Python 3.10+, ffmpeg on PATH, and the packages numpy, scipy, pyloudnorm and playwright (with Chromium).
The build stops with a message if a check fails: a missing recording, an outside address, a fast flashing animation,
a private name, a raw colour or sound code in a game, or a game.json that doesn't add up.
"""
import base64
import hashlib
import importlib.util
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
import games as G  # noqa: E402
import make_voice_script  # noqa: E402

VERSION = "0.9.0"
# the kit's scripts, in loading order: world.js last, so it starts once every game has joined
KIT_JS = ["core.js", "audio.js", "drag.js", "scene.js", "map.js", "crew.js", "shell.js", "grownups.js", "world.js"]


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


# ---------------------------------------------------------------- the games' own drawings
def game_art(game):
    """games/<id>/art.py, if there is one: templates() -> {name: svg}, drawn with design/gen_art.py's helpers."""
    path = game["folder"] / "art.py"
    if not path.exists():
        return {}
    spec = importlib.util.spec_from_file_location(f"art_{game['id']}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.templates()


# ---------------------------------------------------------------- the game page
def build_page(games, script, audio_manifest, out):
    page = (KIT / "page.template.html").read_text(encoding="utf-8")
    js = "\n".join((KIT / f).read_text(encoding="utf-8") for f in KIT_JS)
    css = (KIT / "kit.css").read_text(encoding="utf-8")
    art = {}
    for g in games:
        # each game in its own <script>, so a mistake in one game's code leaves the world and the other games working
        code = "\n".join((g["folder"] / f).read_text(encoding="utf-8") for f in g.get("scripts", []) if (g["folder"] / f).exists())
        js += f"\n</script>\n<script>\n/* ---- games/{g['folder'].name} ---- */\n" + code
        if (g["folder"] / "game.css").exists():
            css += "\n" + (g["folder"] / "game.css").read_text(encoding="utf-8")
        art.update(game_art(g))
    # a line waiting for its recording (pending) stays off the page, even if an older recording of it exists
    pending = {c["id"] for c in script["clips"] if c.get("pending")}
    audio = {
        "voice": {k: {"dur": v["dur"]} for k, v in audio_manifest["voice"].items() if k not in pending},
        "effects": {k: {"dur": v["dur"]} for k, v in audio_manifest["effects"].items()},
        "music": {"dur": audio_manifest["music"]["dur"], "fade": audio_manifest["music"]["fade"]},
    }
    clips = [{"id": c["id"], "group": c["group"], "words": c["words"]} for c in script["clips"] if c["id"] in audio["voice"]]
    parts = {
        "__FONT400__": base64.b64encode((KIT / "Andika-400.woff2").read_bytes()).decode("ascii"),
        "__FONT700__": base64.b64encode((KIT / "Andika-700.woff2").read_bytes()).decode("ascii"),
        "__TOKENS_CSS__": tokens_css(),
        "__KIT_CSS__": css,
        "__SKY__": gen_scenes.sky(),
        "__ART__": gen_scenes.templates(taken=tuple(g["planet"] for g in games if isinstance(g.get("planet"), int)), extra=art),
        "__VERSION__": VERSION,
        "__AUDIO__": json.dumps(audio, separators=(",", ":")),
        "__GAMES__": json.dumps(G.page_info(games), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
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
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    return page, art


# ---------------------------------------------------------------- the recording page (Barney's PC)
def build_record_page(script, out):
    page = (ROOT / "tools" / "record" / "record.template.html").read_text(encoding="utf-8")
    page = page.replace("__SCRIPT_JSON__", json.dumps(script, ensure_ascii=False).replace("</", "<\\/"))
    page = page.replace("__FONT400__", base64.b64encode((KIT / "Andika-400.woff2").read_bytes()).decode("ascii"))
    page = page.replace("__FONT700__", base64.b64encode((KIT / "Andika-700.woff2").read_bytes()).decode("ascii"))
    if "__" in page.replace("window.__rec", ""):
        raise SystemExit("placeholder left in the record page")
    (out / "record").mkdir(parents=True, exist_ok=True)
    (out / "record" / "index.html").write_text(page, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- icons
def render_icons(out):
    import asyncio
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for name, scale in (("icon-512.png", 1), ("icon-192.png", 0.375)):
                page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=scale)
                await page.goto((ROOT / "design" / "icon.html").as_uri())
                await page.locator("#icon").screenshot(path=str(out / name))
            await browser.close()
    asyncio.run(go())


# ---------------------------------------------------------------- offline copy
def build_sw(out):
    files = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"]
    files += ["./" + p.relative_to(out).as_posix() for p in sorted((out / "audio").rglob("*.mp3"))]
    digest = hashlib.sha1()
    for f in files[1:]:
        digest.update((out / f[2:]).read_bytes())
    cache = f"mimi-world-v{VERSION}-{digest.hexdigest()[:8]}"
    sw = (KIT / "sw.template.js").read_text(encoding="utf-8")
    sw = sw.replace("__CACHE__", cache).replace("__FILES__", json.dumps(files, indent=2).replace("\n", "\n"))
    (out / "sw.js").write_text(sw, encoding="utf-8", newline="\n")
    return cache, files


# ---------------------------------------------------------------- checks
# Colours: a game may only use the design system's tokens. A raw colour is a hex value (#f80, #ff8800), a colour
# function (rgb(), hsl(), oklch()…) or a colour name (white, red…) where a colour is being set. Only where a colour is
# being set, so selectors like '#screen-words-play' and words like 'bead' are fine.
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])"
FUNC = r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color-mix|color)\s*\("
NAMED = set("""aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood
cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen
darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue
darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory
khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen
lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime
limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive
olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue
slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke
yellow yellowgreen""".split())
COLOUR_VALUE = re.compile(HEX + "|" + FUNC, re.I)
COLOUR_PROP = (r"(?:fill|stroke|stop-color|flood-color|lighting-color|color|background(?:-color)?|border(?:-[a-z]+)?-color|border"
               r"|outline(?:-color)?|box-shadow|text-shadow|caret-color|accent-color|text-decoration-color"
               r"|backgroundColor|borderColor|outlineColor|boxShadow|textShadow|stopColor)")
# a colour being set inside a string: fill="#f80", style="color: white", 'stroke:rgb(…)'
IN_STRING = re.compile(COLOUR_PROP + r"\s*[:=]\s*[\"']?\s*([^\"';,}]*)", re.I)
# code just before a string that will be a colour: el.style.color = '…', setAttribute('fill', '…'), { fill: '…' }
BEFORE_STRING = re.compile(r"(?:\b" + COLOUR_PROP + r"\s*[:=]|setAttribute\(\s*[\"'](?:fill|stroke|color|stop-color)[\"']\s*,)\s*$", re.I)
SELECTOR_CALL = re.compile(r"(?:querySelector(?:All)?|getElementById|closest|matches|\$)\(\s*$")
OWN_SOUND = re.compile(r"AudioContext|new\s+Audio\s*\(|<audio|speechSynthesis|createBufferSource")
SCREEN_ID = re.compile(r"[\"'](screen-[a-z0-9-]+)[\"']")
WORLD_SCREENS = {"screen-start", "screen-map", "screen-crew"}


def is_colour(value):
    """Is this text (a CSS value, or what a string sets a colour to) a raw colour? Tokens (var(--…)) are fine."""
    v = re.sub(r"var\([^)]*\)|url\([^)]*\)", " ", value)
    m = COLOUR_VALUE.search(v)
    if m:
        return m.group(0)
    for w in re.findall(r"[a-zA-Z]+", v):
        if w.lower() in NAMED:
            return w
    return None


def js_parts(text):
    """JS split into code (comments removed) and its string literals, each with the code just before it."""
    code, strings, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            strings.append((text[max(0, i - 80):i], text[i + 1:j]))
            code.append(c + "~" + c)
            i = j + 1
        else:
            code.append(c)
            i += 1
    return "".join(code), strings


def py_strings(text):
    """A Python file's string literals, each with the code just before it (comments left out)."""
    import io
    import tokenize
    out, before = [], ""
    quote = re.compile(r"^[a-zA-Z]*('''|\"\"\"|'|\")(.*)\1$", re.S)
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.STRING:
            m = quote.match(tok.string)
            out.append((before[-80:], m.group(2) if m else tok.string))
        elif tok.type != tokenize.COMMENT:
            before += tok.string + " "
    return out


def colour_problems(where, text, kind):
    found = []
    if kind == ".css":
        css = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for block in re.findall(r"\{([^{}]*)\}", css):
            for decl in block.split(";"):
                if ":" in decl:
                    prop, value = decl.split(":", 1)
                    if prop.strip().startswith("--"):
                        continue
                    c = is_colour(value)
                    if c:
                        found.append(c)
    else:
        strings = js_parts(text)[1] if kind == ".js" else py_strings(text)
        for before, sval in strings:
            if SELECTOR_CALL.search(before):
                continue                                  # querySelector('#bead'): a selector, not a colour
            if re.fullmatch(r"\s*(?:" + HEX + r")\s*", sval) or re.match(r"\s*" + FUNC, sval, re.I):
                found.append(sval.strip()[:24])
            elif BEFORE_STRING.search(before):
                c = is_colour(sval)
                if c:
                    found.append(c)
            else:
                for m in IN_STRING.finditer(sval):
                    if m.group(1).strip().startswith("@"):
                        continue
                    c = is_colour(m.group(1))
                    if c:
                        found.append(c)
    return [f"{where}: a raw colour ({c}); use a colour token (f-…, s-…, var(--…) or @token)" for c in found]


def game_problems(games, script_ids, art_names):
    """What's wrong with the games themselves: their game.json, their names, colours and sound."""
    problems = []
    seen_planets = {}
    for g in games:
        gid, folder = g.get("id"), g["folder"]
        where = f"games/{folder.name}"
        if gid != folder.name and not folder.name.startswith("_"):
            problems.append(f"{where}/game.json: id is {gid!r}, but the folder is {folder.name!r}")
        if not re.fullmatch(r"[a-z][a-z0-9]*", str(gid)):
            problems.append(f"{where}/game.json: id {gid!r} should be short lower-case letters (and digits), like 'words'")
        for key in ("name", "planet", "badge", "say", "scripts"):
            if key not in g:
                problems.append(f"{where}/game.json has no {key!r}")
        p = g.get("planet")
        if not isinstance(p, int) or not 0 <= p < G.PLANETS:
            problems.append(f"{where}/game.json: planet must be 0 to {G.PLANETS - 1}")
        elif p in seen_planets:
            problems.append(f"{where}/game.json: planet {p} is already {seen_planets[p]}'s")
        else:
            seen_planets[p] = gid
        if g.get("badge") not in art_names:
            problems.append(f"{where}/game.json: badge {g.get('badge')!r} is not a drawing in the kit or the game's art.py")
        if g.get("say") not in script_ids:
            problems.append(f"{where}/game.json: say {g.get('say')!r} is not a voice line in kit/lines.json or the game's lines.json")
        scripts = g.get("scripts", [])
        code = ""
        for f in scripts:
            if not (folder / f).exists():
                problems.append(f"{where}/game.json lists {f}, which isn't in the folder")
            else:
                code += (folder / f).read_text(encoding="utf-8")
        if scripts and not (re.search(r"\bgame\(\s*\{", code) and re.search(r"['\"]" + re.escape(str(gid)) + r"['\"]", code)):
            problems.append(f"{where}: no script joins the world with MW.world.game({{ id: '{gid}', ... }})")
        if gid not in G.LEGACY:
            for c in g.get("lines", []):
                if not c["id"].startswith(f"{gid}-"):
                    problems.append(f"{where}/lines.json: line {c['id']!r} should start with '{gid}-'")
            for sid in sorted(set(SCREEN_ID.findall(code)) - WORLD_SCREENS):
                if not sid.startswith(f"screen-{gid}-"):
                    problems.append(f"{where}: screen {sid!r} should start with 'screen-{gid}-'")
        # colours come only from the tokens; sound only through MW.audio; nothing that would end the page's <script>
        for f in sorted(folder.rglob("*")):
            if f.suffix not in (".js", ".css", ".py") or "__pycache__" in f.parts:
                continue
            text = f.read_text(encoding="utf-8")
            rel = f"{where}/{f.relative_to(folder).as_posix()}"
            problems += colour_problems(rel, text, f.suffix)
            if f.suffix == ".js":
                code, strings = js_parts(text)
                if OWN_SOUND.search(code + " " + " ".join(sv for _, sv in strings)):
                    problems.append(f"{rel}: plays sound itself; use MW.audio.say and MW.audio.sfx")
                if re.search(r"</script", text, re.I):
                    problems.append(f"{rel}: contains </script>, which would end the page's script early")
    return problems


def art_problems(games, art):
    problems = []
    for name in art:
        if not any(g["id"] not in G.LEGACY and name.startswith(g["id"] + "-") for g in games):
            problems.append(f"a game's drawing {name!r} should start with its game's id and '-'")
    return problems


def checks(page, out, games, script, art):
    problems = []
    # nothing leaves the tablet: no outside addresses (the SVG namespace is a name, not a request)
    for url in re.findall(r"https?://[^\s\"'<>)]+", page):
        if not url.startswith("http://www.w3.org/"):
            problems.append(f"outside address in the page: {url}")
    # flashing: any animation that repeats must be slower than 1 second per cycle (the longhand form too)
    for block in re.findall(r"\{([^{}]*)\}", page):
        if re.search(r"animation-iteration-count:\s*infinite", block):
            d = re.search(r"animation-duration:\s*(\d+(?:\.\d+)?)(ms|s)\b", block)
            if not d or float(d.group(1)) / (1000 if d.group(2) == "ms" else 1) < 1:
                problems.append(f"repeating animation faster than once a second: {block.strip()[:80]}")
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
    for f in [out / "index.html", out / "record" / "index.html"]:
        text = f.read_text(encoding="utf-8")
        for n in names:
            if re.search(r"\b" + re.escape(n) + r"\b", text):
                problems.append(f"{f.relative_to(out.parent)} contains a private name")
    # every voice line has its web file, unless it is waiting for its recording
    for c in script["clips"]:
        if not (out / "audio" / "voice" / f"{c['id']}.mp3").exists():
            if c.get("pending"):
                print(f"note: {c['id']} is waiting for its recording; the game doesn't use it yet")
            else:
                problems.append(f"no web audio for {c['id']}")
    art_names = set(gen_scenes.art_dict(extra=art))
    problems += game_problems(games, {c["id"] for c in script["clips"]}, art_names)
    problems += art_problems(games, art)
    if problems:
        raise SystemExit("Build checks failed:\n  " + "\n  ".join(problems))


def arg(name):
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == name]


def main():
    out = pathlib.Path(arg("--out")[0]).resolve() if arg("--out") else DOCS
    extra = arg("--extra-game")
    full = "--no-audio" not in sys.argv and out == DOCS
    games = G.load(extra)
    script = make_voice_script.build(games)
    if not extra:
        make_voice_script.main()                # voice/script.json, read by make_audio and the recording page
    out.mkdir(parents=True, exist_ok=True)
    if full:
        import make_audio
        manifest = make_audio.main()
    else:
        manifest = json.loads((ROOT / "tools" / "audio-manifest.json").read_text(encoding="utf-8"))
    if out != DOCS:                             # a test copy: the audio and icons come from docs/
        if (out / "audio").exists():
            shutil.rmtree(out / "audio")
        shutil.copytree(DOCS / "audio", out / "audio")
        for icon in ("icon-192.png", "icon-512.png"):
            shutil.copy(DOCS / icon, out / icon)
    page, art = build_page(games, script, manifest, out)
    build_record_page(script, out)
    shutil.copy(KIT / "manifest.json", out / "manifest.json")
    if out == DOCS and (full or not (DOCS / "icon-512.png").exists()):
        render_icons(out)
    cache, files = build_sw(out)
    checks(page, out, games, script, art)
    names = ", ".join(g["name"] for g in games)
    print(f"MeeMee World {VERSION} ({names}): index.html {len(page.encode('utf-8')) / 1024:.0f} KB, offline copy {cache} ({len(files)} files)")


if __name__ == "__main__":
    main()
