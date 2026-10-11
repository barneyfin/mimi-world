"""Headless checks for MeeMee World: the map, the crew, MeeMee Rescue (a round, the bonds), MeeMee Rockets (the tricky-words
game), the kit (0.6.0: the title banners, the store, stars, pick-up boxes, numbers mode's pieces) and MeeMee Rescue's
numbers mode (0.6.0), on Fire and Doogee screen sizes.

    python tools/tests/test_game.py            run everything, screenshots into tools/tests/shots/

Uses Playwright's Chromium with touch input sent through the DevTools protocol, the way a finger would.
"""
import asyncio
import functools
import re
import http.server
import json
import pathlib
import sys
import threading

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SHOTS = pathlib.Path(__file__).resolve().parent / "shots"
SHOTS.mkdir(exist_ok=True)
PORT = 8791
ORIGIN = f"http://127.0.0.1:{PORT}"
RESULTS = []
ROUND = [
    {"whole": 7, "left": 3, "right": 4, "missing": "right"},
    {"whole": 5, "left": 2, "right": 3, "missing": "whole"},
    {"whole": 6, "left": 1, "right": 5, "missing": "left"},
    {"whole": 9, "left": 4, "right": 5, "missing": "right"},
    {"whole": 4, "left": 3, "right": 1, "missing": "whole"},
]
CENTRES = {"whole": (380, 205), "left": (210, 470), "right": (550, 470)}
PLAY = (900, 380)                     # the Play button on the start screen
RESCUE = (330, 300)                   # the MeeMee Rescue planet on the map
EMPTY_PLANETS = "MW.LAYOUT.map.planets.filter((p, i) => !MW.world.games.some(g => g.planet === i))"   # planets with no game yet


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(DOCS)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


class Tablet:
    def __init__(self, page, cdp):
        self.page, self.cdp = page, cdp

    async def geom(self):
        return await self.page.evaluate("({s: MW.stage.scale, x: MW.stage.offX, y: MW.stage.offY})")

    async def screen(self, sx, sy):
        g = await self.geom()
        return g["x"] + sx * g["s"], g["y"] + sy * g["s"]

    async def drag(self, sx0, sy0, sx1, sy1, steps=14):
        x0, y0 = await self.screen(sx0, sy0)
        x1, y1 = await self.screen(sx1, sy1)
        pt = lambda x, y: [{"x": x, "y": y, "id": 1, "radiusX": 8, "radiusY": 8, "force": 1}]
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt(x0, y0)})
        for i in range(1, steps + 1):
            await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pt(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)})
            await asyncio.sleep(0.016)
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await asyncio.sleep(0.32)

    async def tap(self, sx, sy, hold=0.05):
        x, y = await self.screen(sx, sy)
        pt = [{"x": x, "y": y, "id": 2, "radiusX": 8, "radiusY": 8, "force": 1}]
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt})
        await asyncio.sleep(hold)
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await asyncio.sleep(0.15)

    async def state(self):
        return await self.page.evaluate("({phase: MW.rescue.st.phase, qi: MW.rescue.st.qi, target: MW.rescue.st.target, answer: MW.rescue.st.answer,"
                                        " placed: MW.rescue.st.counters.filter(c => c.where === MW.rescue.st.target).length, screen: MW.shell.screen})")

    async def wait_phase(self, phases, timeout=25):
        for _ in range(int(timeout / 0.1)):
            s = await self.state()
            if s["phase"] in phases:
                return s
            await asyncio.sleep(0.1)
        return await self.state()

    async def tray_free(self):
        return await self.page.evaluate("MW.rescue.st.counters.filter(c => c.where === 'tray').map(c => [c.x, c.y])")

    async def fill(self, n, target):
        cx, cy = CENTRES[target]
        for _ in range(n):
            free = await self.tray_free()
            x, y = free[-1]
            await self.drag(x, y, cx + 10, cy + 8)

    async def said(self):
        return await self.page.evaluate("MW.events.filter(e => e.type === 'say').map(e => e.detail)")

    async def wait_screen(self, screen, timeout=10):
        for _ in range(int(timeout / 0.1)):
            if await self.page.evaluate("MW.shell.screen") == screen:
                if screen == "screen-map":                   # 0.6.0: a planet can be tapped once the title banner has gone
                    return await self.wait_banner(timeout)
                return True
            await asyncio.sleep(0.1)
        return False

    async def wait_banner(self, timeout=10):
        """Until no title banner is showing (MeeMee World's after Play, or a game's after its planet is tapped)."""
        for _ in range(int(timeout / 0.1)):
            if not await self.page.evaluate("MW.world.banner.up() || MW.world.st.phase === 'welcome'"):
                return True
            await asyncio.sleep(0.1)
        return False

    async def start_round(self):
        """Play on the start screen, then the MeeMee Rescue planet on the map."""
        if await self.page.evaluate("MW.shell.screen") == "screen-start":
            await self.tap(*PLAY)
            await self.wait_screen("screen-map")
        await self.tap(*RESCUE)
        return await self.wait_phase(["asking", "open"])


async def open_tablet(p, name, vw, vh, dpr, extra_args=(), mode="auto"):
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", *extra_args])
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    problems, requests = [], []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    page.on("request", lambda r: requests.append(r.url))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    if mode:
        await page.evaluate("MW.store.setting('check', %s); MW.store.setting('checkPicked', true)" % json.dumps(mode))
    cdp = await ctx.new_cdp_session(page)
    return browser, ctx, page, Tablet(page, cdp), problems, requests


async def play_round(t, name, shots=True):
    page = t.page
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    check(f"{name}: Play opens the map", await t.wait_screen("screen-map"))
    check(f"{name}: sound running after the tap", await page.evaluate("MW.audio.running()"))
    await asyncio.sleep(0.4)
    check(f"{name}: the map says 'Welcome to MeeMee World!'", "map-welcome" in await t.said())
    if shots:
        await asyncio.sleep(0.6)
        await page.screenshot(path=str(SHOTS / f"{name}-0b-map.png"))
    await t.tap(*RESCUE)
    s = await t.wait_phase(["asking", "open"])
    check(f"{name}: the MeeMee Rescue planet says its name and starts the round",
          s["screen"] == "screen-game" and s["qi"] == 0 and "map-mimi-rescue" in await t.said(), json.dumps(s))

    # Q1 missing right part 4 (whole 7, given 3)
    await t.fill(2, "right")
    s = await t.state()
    check(f"{name}: two MeeMee dropped show 2 in the pill", s["placed"] == 2 and (await page.inner_text("#screen-game .mw-pill.is-waiting")) == "2")
    if shots:
        free = await t.tray_free()
        x0, y0 = await t.screen(*free[-1])
        x1, y1 = await t.screen(700, 330)
        pt = lambda x, y: [{"x": x, "y": y, "id": 1, "radiusX": 8, "radiusY": 8, "force": 1}]
        await t.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt(x0, y0)})
        for i in range(1, 11):
            await t.cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pt(x0 + (x1 - x0) * i / 10, y0 + (y1 - y0) * i / 10)})
            await asyncio.sleep(0.016)
        await asyncio.sleep(0.2)
        await page.screenshot(path=str(SHOTS / f"{name}-1-dragging.png"))
        await t.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await asyncio.sleep(0.4)
        s = await t.state()
        check(f"{name}: a drop between circles floats back", s["placed"] == 2, json.dumps(s))
    await t.fill(2, "right")
    s = await t.wait_phase(["celebrate"], 3)
    check(f"{name}: the fourth MeeMee completes 3 + ? = 7", s["phase"] == "celebrate", json.dumps(s))
    lights = await page.evaluate("""(() => { const pod = document.querySelector('#screen-game .mw-pod');
        const l = getComputedStyle(pod.querySelector('.mw-ship-light')), b = getComputedStyle(pod.querySelector('.mw-ship-beacon'));
        return [pod.classList.contains('is-celebrating'), l.animationName, l.animationDuration, l.animationIterationCount,
                b.animationDuration, b.animationIterationCount]; })()""")
    check(f"{name}: the ship's lights flash after a right answer (0.66 s × 6, beacon 1 s × 4)",
          lights == [True, "mw-ship-flash", "0.66s", "6", "1s", "4"], str(lights))
    if shots:
        await asyncio.sleep(0.25)
        await page.screenshot(path=str(SHOTS / f"{name}-2a-lights.png"))
    await asyncio.sleep(2.6)
    on = await page.evaluate("document.querySelector('#screen-game .mw-pod').classList.contains('is-celebrating')")
    check(f"{name}: the lights are still going at about 3 seconds", on)
    if shots:
        await page.screenshot(path=str(SHOTS / f"{name}-2-celebrate.png"))
    eq = await page.inner_text("#screen-game .mw-equation")
    check(f"{name}: equation reads 3 + 4 = 7", eq.replace("\n", " ").split() == ["3", "+", "4", "=", "7"], eq)
    await asyncio.sleep(1.4)
    off = await page.evaluate("!document.querySelector('#screen-game .mw-pod').classList.contains('is-celebrating')")
    check(f"{name}: the lights stop after about 4 seconds", off)
    s = await t.wait_phase(["asking", "open"], 15)
    lit = await page.evaluate("document.querySelector('#screen-game .mw-pod').classList.contains('is-celebrating')")
    check(f"{name}: the next question starts with the lights off", not lit)
    said = await t.said()
    check(f"{name}: question 1 spoken as pieces", "q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more" in said)
    check(f"{name}: equation spoken", "num-mid-3 and num-mid-4 make num-end-7" in said)
    stars = await page.evaluate("Array.from(document.querySelectorAll('#screen-game .mw-stars svg')).map(s => s.dataset.state).join(',')")
    check(f"{name}: one star done, the next is current", stars == "done,current,todo,todo,todo", stars)

    # Q2 missing whole (2 and 5): two misses bring the counting hint
    check(f"{name}: question 2 asks for the whole", s["target"] == "whole" and s["qi"] == 1, json.dumps(s))
    free = await t.tray_free()
    await t.drag(free[-1][0], free[-1][1], 660, 120)        # empty sky: a miss
    await asyncio.sleep(0.3)
    free = await t.tray_free()
    await t.drag(free[-1][0], free[-1][1], 210, 470)        # onto a given part: a miss
    await asyncio.sleep(1.2)
    said = await t.said()
    check(f"{name}: first miss says 'Let's try again'", "again-try-again" in said)
    check(f"{name}: second miss plays the count-with-me hint", any(x.startswith("again-count-with-me") for x in said))
    ghosts = await page.evaluate("document.querySelectorAll('.mw-ghost').length")
    check(f"{name}: hint shows 5 ghost MeeMee in the whole", ghosts == 5, str(ghosts))
    await asyncio.sleep(2.5)
    if shots:
        await page.screenshot(path=str(SHOTS / f"{name}-3-hint.png"))
    await t.fill(5, "whole")
    s = await t.wait_phase(["celebrate"], 3)
    check(f"{name}: five MeeMee in the whole completes 2 + 3 = ?", s["phase"] == "celebrate", json.dumps(s))
    s = await t.wait_phase(["asking", "open"], 15)

    # Q3 missing left (? + 5 = 6): take one back out
    await t.fill(1, "left")
    s = await t.wait_phase(["celebrate"], 3)
    check(f"{name}: missing left part completes", s["phase"] == "celebrate" and s["target"] == "left", json.dumps(s))
    s = await t.wait_phase(["asking", "open"], 15)

    # Q4 (4 + ? = 9): put 2 in, take 1 out, then finish
    await t.fill(2, "right")
    placed = await page.evaluate("MW.rescue.st.counters.filter(c => c.where === 'right').map(c => [c.x, c.y])")
    await t.drag(placed[0][0], placed[0][1], 1000, 300)
    s = await t.state()
    check(f"{name}: dragging a MeeMee back out leaves 1", s["placed"] == 1, json.dumps(s))
    await t.fill(4, "right")
    s = await t.wait_phase(["celebrate"], 3)
    check(f"{name}: 4 + ? = 9 completes at 5", s["phase"] == "celebrate", json.dumps(s))
    s = await t.wait_phase(["asking", "open"], 15)

    # Q5 (3 + 1 = ?)
    await t.fill(4, "whole")
    await t.wait_phase(["done"], 20)
    await asyncio.sleep(3.5)
    s = await t.state()
    check(f"{name}: round ends on the celebration screen", s["screen"] == "screen-end", json.dumps(s))
    said = await t.said()
    check(f"{name}: 'You rescued all the MeeMee!' plays", "round-rescued-all" in said)
    if shots:
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(SHOTS / f"{name}-4-end.png"))
    answers = await page.evaluate("MW.store.get('answers').length")
    check(f"{name}: five answers saved on this tablet", answers == 5, str(answers))


async def test_device(p, name, vw, vh, dpr):
    print(f"\n== {name}: {vw}x{vh} at {dpr}x ==")
    browser, ctx, page, t, problems, requests = await open_tablet(p, name, vw, vh, dpr)
    await page.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.ready", timeout=8000)
    await asyncio.sleep(0.5)
    if name == "fire":
        await page.screenshot(path=str(SHOTS / f"{name}-0-start.png"))
    dup = await page.evaluate("(() => { const ids = Array.from(document.querySelectorAll('[id]')).map(e => e.id); return ids.filter((x, i) => ids.indexOf(x) !== i); })()")
    check(f"{name}: no id is used twice (each copy of a drawing has its own clip paths)", not dup, str(dup[:5]))
    lost = await page.evaluate("Array.from(document.querySelectorAll('[clip-path]')).map(e => e.getAttribute('clip-path').slice(5, -1)).filter(id => !document.getElementById(id))")
    check(f"{name}: every clip path a drawing uses is there", not lost, str(lost[:5]))
    await play_round(t, name, shots=True)

    # Music: on by default, dips under speech, off is remembered
    playing = await page.evaluate("MW.audio.music.playing()")
    check(f"{name}: music playing", playing)
    for _ in range(80):                                      # let the end-of-round lines finish
        if not await page.evaluate("MW.audio.speaking()"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(1.2)
    quiet = await page.evaluate("MW.audio.music.level()")
    await page.evaluate("MW.audio.say([['q-lets-make', 'num-end-7'], ['q-weve-got', 'num-end-3']]), 0")   # don't wait for the line
    await asyncio.sleep(0.8)
    ducked = await page.evaluate("MW.audio.music.level()")
    check(f"{name}: music dips while a line is spoken", ducked < quiet * 0.5, f"{quiet:.3f} -> {ducked:.3f}")
    for _ in range(100):                                     # until the line ends, then a moment
        if not await page.evaluate("MW.audio.speaking()"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(1.2)
    back = await page.evaluate("MW.audio.music.level()")
    check(f"{name}: music comes back after the line", back > quiet * 0.8, f"{back:.3f}")

    # Grown-ups lock: a quick tap does nothing; a 3-second hold opens it
    await t.tap(46, 754, 0.1)
    check(f"{name}: a quick tap on the lock does nothing", not await page.evaluate("MW.grownups.open"))
    await t.tap(46, 754, 3.3)
    check(f"{name}: holding the lock for 3 s opens the grown-ups area", await page.evaluate("MW.grownups.open"))
    for tab in ("progress", "settings", "sound", "checks"):
        await page.evaluate(f"MW.grownups.show('{tab}')")
        await asyncio.sleep(0.3)
        await page.screenshot(path=str(SHOTS / f"{name}-5-grownups-{tab}.png"))
    rows = await page.evaluate("MW.grownups.deviceRows().map(r => r[0] + ': ' + r[1])")
    print("   " + "\n   ".join(rows))

    # music off via the settings, remembered after reloading
    await page.evaluate("MW.audio.music.setOn(false)")
    await page.evaluate("MW.grownups.close()")
    await page.reload()
    await page.wait_for_load_state("load")
    check(f"{name}: music off is remembered", not await page.evaluate("MW.audio.music.isOn()"))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await asyncio.sleep(1)
    check(f"{name}: music stays off after Play", not await page.evaluate("MW.audio.music.playing()"))
    icon = await page.evaluate("document.querySelector('#screen-game .mw-music').getAttribute('aria-label')")
    check(f"{name}: music button shows the crossed note", icon == "Music off", icon)
    await page.evaluate("MW.audio.music.setOn(true)")

    # Offline: reload with the network off
    await page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=8000)
    await ctx.set_offline(True)
    await page.reload()
    await page.wait_for_load_state("load")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    st = await page.evaluate("MW.audio.status()")
    check(f"{name}: opens and loads all sound with the network off", st["decoded"] == st["total"] and not st["failed"], json.dumps(st))
    await ctx.set_offline(False)

    outside = [u for u in requests if not u.startswith(ORIGIN)]
    check(f"{name}: no requests outside the site", not outside, ", ".join(outside[:3]))
    check(f"{name}: no console errors or warnings", not problems, "; ".join(problems[:4]))
    await browser.close()


async def test_tap_mode(p):
    print("\n== tap-to-check mode ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "tap", 1280, 800, 1, mode=None)
    check("tap: a new tablet checks by tapping Scruffles", await page.evaluate("MW.store.setting('check')") == "tap")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 15)
    said = await t.said()
    check("tap: question 1 ends with 'Tap Scruffles when you're ready.'", "q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more tap-scruffles" in said, str(said[-2:]))
    ready = await page.evaluate("document.querySelector('#screen-game .mw-pod').classList.contains('is-ready')")
    check("tap: the ship's lights are off while the circle is empty", not ready)
    await t.fill(2, "right")
    cue = await page.evaluate("""(() => { const pod = document.querySelector('#screen-game .mw-pod');
        const l = getComputedStyle(pod.querySelector('.mw-ship-light'));
        return [pod.classList.contains('is-ready'), l.opacity, l.animationName]; })()""")
    check("tap: with MeeMee in the circle the lights glow steadily", cue == [True, "1", "none"], str(cue))
    await t.tap(1030, 300)                                   # tap Scruffles with 2 (too few)
    await asyncio.sleep(0.6)
    check("tap: too few says 'Let's look again.'", "again-look-again" in await t.said())
    await t.fill(4, "right")                                 # 6 > 4
    s = await t.state()
    check("tap: six MeeMee can go in (no auto-complete)", s["placed"] == 6 and s["phase"] == "open", json.dumps(s))
    await t.tap(1030, 300)
    await asyncio.sleep(0.6)
    check("tap: too many says 'That's too many. Take one back.'", "too-many" in await t.said())
    placed = await page.evaluate("MW.rescue.st.counters.filter(c => c.where === 'right').map(c => [c.x, c.y])")
    for x, y in placed[:3]:
        await t.drag(x, y, 1000, 640)
    await t.tap(1030, 300)
    await asyncio.sleep(0.8)
    check("tap: third wrong check plays the counting-on hint", any(x.startswith("q-count-on-from num-end-3") for x in await t.said()))
    await t.fill(1, "right")
    await t.tap(1030, 300)
    s = await t.wait_phase(["celebrate"], 3)
    check("tap: four MeeMee and a tap on Scruffles completes it", s["phase"] == "celebrate", json.dumps(s))
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check("tap: saved with 3 wrong checks and the hint", rec["tries"] == 3 and rec["hint"] is True, json.dumps(rec))
    check("tap: saved as answered with MeeMee to count (0.6.0: every answer is saved with its mode)", rec.get("mode") == "counting", json.dumps(rec))
    s = await t.wait_phase(["asking", "open"], 15)
    p2 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("tap: question 2 ends with the line too", s["qi"] == 1 and "tap-scruffles" in p2, p2)
    await t.wait_phase(["open"], 15)
    await t.fill(5, "whole")
    await t.tap(1030, 300)
    await t.wait_phase(["celebrate"], 3)
    s = await t.wait_phase(["asking", "open"], 15)
    p3 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("tap: from question 3 the line isn't said", s["qi"] == 2 and "tap-scruffles" not in p3, p3)
    check("tap: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_switch(p):
    print("\n== tap-to-check becomes the default ==")
    browser = await p.chromium.launch()
    for saved, want, label in [
            ({"v": 1, "music": True, "settings": {"check": "auto"}, "answers": [{"t": 1}]}, "tap", "a tablet on the old default moves to tap"),
            ({"v": 1, "music": True, "settings": {"check": "auto", "checkPicked": True}, "answers": []}, "auto", "a mode picked in Settings is kept")]:
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        await ctx.add_init_script("localStorage.setItem('mimi-world', %s)" % json.dumps(json.dumps(saved)))
        page = await ctx.new_page()
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        got = await page.evaluate("[MW.store.setting('check'), MW.store.get('answers').length]")
        check(f"switch: {label}", got[0] == want and got[1] == len(saved["answers"]), str(got))
        await ctx.close()
    await browser.close()


async def touch(t, kind, points):
    await t.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [
        {"x": x, "y": y, "id": i, "radiusX": 8, "radiusY": 8, "force": 1} for i, (x, y) in points]})


async def test_edge_cases(p):
    print("\n== edge cases ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "edge", 1046, 653, 1.22)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 15)

    # picking a MeeMee up keeps it fully visible (no fade-in replay)
    free = await t.tray_free()
    x0, y0 = await t.screen(*free[-1])
    await touch(t, "touchStart", [(1, (x0, y0))])
    await asyncio.sleep(0.05)
    op = await page.evaluate("Math.min(...MW.rescue.st.counters.map(c => +getComputedStyle(c.el).opacity))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.4)
    check("edge: a picked-up MeeMee stays fully visible", op > 0.99, str(op))

    # two fingers on the lock, lifted quickly: nothing opens
    lx, ly = await t.screen(46, 754)
    await touch(t, "touchStart", [(3, (lx, ly))])
    await touch(t, "touchStart", [(3, (lx, ly)), (4, (lx + 6, ly + 4))])
    await asyncio.sleep(0.15)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(3.4)
    check("edge: two fingers on the lock don't open the grown-ups area", not await page.evaluate("MW.grownups.open"))
    # a thumb sliding off the lock doesn't count
    await touch(t, "touchStart", [(5, (lx, ly))])
    for k in range(1, 8):
        await touch(t, "touchMove", [(5, (lx + k * 10, ly - k * 6))])
        await asyncio.sleep(0.05)
    await asyncio.sleep(3.2)
    await touch(t, "touchEnd", [])
    check("edge: a thumb sliding off the lock doesn't open it", not await page.evaluate("MW.grownups.open"))

    # screen off mid-question: the game waits, then asks again when it comes back
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(1.0)
    check("edge: hiding the page pauses the game", await page.evaluate("MW.rescue.st.paused"))
    n_before = len(await t.said())
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.6)
    said = await t.said()
    check("edge: coming back asks the question again", not await page.evaluate("MW.rescue.st.paused") and said[n_before:][:1] == ["q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more"], str(said[n_before:]))

    # Home while a MeeMee is held, then the finger lifts: nothing is said on the start screen
    free = await t.tray_free()
    x0, y0 = await t.screen(*free[-1])
    x1, y1 = await t.screen(660, 120)
    await touch(t, "touchStart", [(6, (x0, y0))])
    for k in range(1, 6):
        await touch(t, "touchMove", [(6, (x0 + (x1 - x0) * k / 5, y0 + (y1 - y0) * k / 5))])
        await asyncio.sleep(0.02)
    await page.evaluate("MW.rescue.home()")
    n_before = len(await t.said())
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.8)
    check("edge: a MeeMee let go after Home says nothing", len(await t.said()) == n_before, str((await t.said())[n_before:]))
    check("edge: Home goes back to the map", await page.evaluate("MW.shell.screen") == "screen-map")

    # an interrupted hint comes back on the next wrong try
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.start_round()
    await t.wait_phase(["open"], 15)
    for _ in range(2):
        free = await t.tray_free()
        await t.drag(free[-1][0], free[-1][1], 660, 120)
        await asyncio.sleep(0.3)
    await asyncio.sleep(0.8)
    check("edge: two misses start the hint", await page.evaluate("MW.rescue.st.hinted"))
    await t.tap(1208, 68)                                    # Hear it again
    await asyncio.sleep(0.5)
    check("edge: Hear-again during the hint takes it away", not await page.evaluate("MW.rescue.st.hinted") and await page.evaluate("document.querySelectorAll('.mw-ghost').length") == 0)
    free = await t.tray_free()
    await t.drag(free[-1][0], free[-1][1], 660, 120)
    await asyncio.sleep(0.8)
    check("edge: the next miss gives the hint again", await page.evaluate("MW.rescue.st.hinted"))

    # rescued MeeMee that were dropped in fade out with the rest
    await t.fill(4, "right")
    await t.wait_phase(["celebrate"], 3)
    for _ in range(80):
        if await page.evaluate("document.querySelectorAll('.mw-mimi.is-rescued').length") > 0:
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)
    ops = await page.evaluate("Array.from(document.querySelectorAll('.mw-mimi.is-rescued')).map(e => Math.round(+getComputedStyle(e).opacity * 100) / 100)")
    check("edge: every rescued MeeMee is fading out (dropped ones too)", len(ops) == 7 and max(ops) < 0.5, str(ops))
    check("edge: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_portrait(p):
    print("\n== portrait ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "portrait", 653, 1046, 1.22)
    shown = await page.evaluate("getComputedStyle(document.querySelector('.mw-sideways')).display")
    check("portrait: 'turn the tablet sideways' shows", shown == "flex", shown)
    await page.screenshot(path=str(SHOTS / "portrait.png"))
    await browser.close()


async def test_reduce_motion(p):
    print("\n== reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce")
    page = await ctx.new_page()
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    anim = await page.evaluate("getComputedStyle(document.getElementById('play')).animationName")
    check("reduce motion: the Play button doesn't pulse", anim == "none", anim)
    check("reduce motion: the kit knows", await page.evaluate("MW.reduceMotion"))
    lit = await page.evaluate("""(() => { const pod = document.querySelector('#screen-start .mw-pod'); pod.classList.add('is-celebrating');
        const l = getComputedStyle(pod.querySelector('.mw-ship-light')); return [l.animationName, l.opacity]; })()""")
    check("reduce motion: the ship's lights stay lit instead of flashing", lit == ["none", "1"], str(lit))
    peek = await page.evaluate("""(() => { const d = document.createElement('div'); d.className = 'mw-peek'; d.innerHTML = '<div class="mw-peek-inner"></div>';
        document.body.appendChild(d); const t = getComputedStyle(d.firstChild).transform; d.remove(); return t; })()""")
    check("reduce motion: the lookout fades in instead of rising", peek == "none", peek)
    await browser.close()


# ---------------------------------------------------------------- phase 4: the map, zero bonds, the bonds, the grid
DAY = 86_400_000
T0 = 1_790_848_800_000                # 1 October 2026, 10:00 UTC


def ans(t, w, a, first=True, missing="right", hint=False):
    return {"t": t, "whole": w, "left": a, "right": w - a, "missing": missing, "tries": 0 if first else 1,
            "misses": 0, "hint": hint, "check": "tap"}


def secure_answers(bonds, start=T0):
    """Right first time on three different days for each (whole, smaller part)."""
    return [ans(start + d * DAY + i * 1000, w, a) for d in range(3) for i, (w, a) in enumerate(bonds)]


NONZERO = [(w, a) for w in range(2, 11) for a in range(1, w // 2 + 1)]
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


async def seeded(browser, answers, check_mode="tap", vw=1280, vh=800):
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, has_touch=True, is_mobile=True)
    saved = {"v": 1, "music": True, "settings": {"check": check_mode, "checkPicked": True}, "answers": answers}
    await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                              % json.dumps(json.dumps(saved)))
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    return ctx, page, problems


async def test_map(p):
    print("\n== the home map ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "map", 1280, 800, 1, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    start = await page.evaluate("[document.getElementById('screen-start').innerText.trim(), document.querySelectorAll('#screen-start .mw-caption').length]")
    check("map: the start screen has nothing to read (no 'MeeMee World' caption: its banner names it after Play)", start == ["", 0], str(start))
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    nav = await page.evaluate("[document.querySelectorAll('#screen-map [aria-label=Home]').length, document.querySelectorAll('#screen-map .mw-music').length]")
    check("map: a music button and no Home button", nav == [0, 1], str(nav))
    sizes = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-planet')).map(b => b.offsetWidth)")
    check("map: every planet is a big target (at least 120 stage px)", sizes and min(sizes) >= 120, str(sizes))
    await asyncio.sleep(1.5)
    empty = await page.evaluate(EMPTY_PLANETS)
    if empty:
        await t.tap(empty[0]["x"], empty[0]["y"])
        await asyncio.sleep(0.3)
        said = await t.said()
        check("map: a locked planet says 'That planet isn't ready yet.'", said[-1:] == ["map-not-ready"] and await page.evaluate("MW.shell.screen") == "screen-map", str(said[-2:]))
        await asyncio.sleep(1.5)
    else:
        check("map: a locked planet says 'That planet isn't ready yet.'", True, "skipped: every planet has a game")
    if len(empty) > 1:
        await t.tap(empty[1]["x"], empty[1]["y"])
        await asyncio.sleep(0.3)
        check("map: so does the other one", (await t.said())[-1:] == ["map-not-ready"])
        await asyncio.sleep(1.5)
    else:
        check("map: so does the other one", True, "skipped: fewer than two planets still to come")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(368 + 42, 166 + 42)                          # the MeeMee badge
    s = await t.wait_phase(["asking", "open"])
    check("map: the MeeMee badge starts a round too", s["screen"] == "screen-game", json.dumps(s))
    await t.tap(66, 62)                                      # Home
    await asyncio.sleep(0.5)
    check("map: Home in a round goes back to the map", await page.evaluate("MW.shell.screen") == "screen-map")
    check("map: the welcome is said once a visit", (await t.said()).count("map-welcome") == 1, str(await t.said()))
    # a double tap on the planet starts one round, not two
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.tap(*RESCUE)
    await t.wait_phase(["asking", "open"])
    await asyncio.sleep(0.5)
    rounds = await page.evaluate("MW.events.filter(e => e.type === 'round').length")
    check("map: a double tap on the planet starts one round", rounds == 2, str(rounds))
    # the screen going off while "MeeMee Rescue!" is said: back on the map, no round behind the pause
    await page.evaluate("MW.rescue.home()")
    await asyncio.sleep(0.3)
    await t.tap(*RESCUE)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(1.5)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.8)
    st = await page.evaluate("[MW.shell.screen, MW.rescue.st.phase, MW.events.filter(e => e.type === 'round').length]")
    check("map: a pause during 'MeeMee Rescue!' stays on the map", st == ["screen-map", "map", 2], str(st))
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    s = await t.wait_phase(["asking", "open"])
    check("map: and the planet works again after it", s["screen"] == "screen-game", json.dumps(s))
    check("map: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_zero(p):
    print("\n== zero bonds (tap Scruffles with the circle empty) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "zero", 1280, 800, 1, mode="tap")
    zround = [{"whole": 5, "left": 5, "right": 0, "missing": "right"},
              {"whole": 4, "left": 0, "right": 4, "missing": "left"},
              {"whole": 6, "left": 0, "right": 6, "missing": "whole"},
              {"whole": 3, "left": 3, "right": 0, "missing": "right"},
              {"whole": 2, "left": 1, "right": 1, "missing": "right"}]
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(zround))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 15)
    check("zero: 5 + ? = 5 asks 'Let's make five. We've got five. How many more?'",
          "q-lets-make num-end-5 q-weve-got num-end-5 q-how-many-more tap-scruffles" in await t.said())
    await t.fill(1, "right")
    await t.tap(1030, 300)
    await asyncio.sleep(0.6)
    check("zero: one MeeMee in is too many", (await t.said())[-1:] == ["too-many"])
    placed = await page.evaluate("MW.rescue.st.counters.filter(c => c.where === 'right').map(c => [c.x, c.y])")
    await t.drag(placed[0][0], placed[0][1], 1000, 640)
    ready = await page.evaluate("document.querySelector('#screen-game .mw-pod').classList.contains('is-ready')")
    check("zero: the ship's lights don't glow with the circle empty (no give-away)", not ready)
    await t.tap(1030, 300)
    s = await t.wait_phase(["celebrate"], 3)
    check("zero: tapping Scruffles with the circle empty answers 0", s["phase"] == "celebrate", json.dumps(s))
    for _ in range(80):                                      # after the praise, however long it is
        if "num-mid-5 and num-mid-0 make num-end-5" in await t.said():
            break
        await asyncio.sleep(0.1)
    eq = await page.inner_text("#screen-game .mw-equation")
    check("zero: the equation reads 5 + 0 = 5", eq.replace("\n", " ").split() == ["5", "+", "0", "=", "5"], eq)
    check("zero: '5 and 0 make 5' is spoken", "num-mid-5 and num-mid-0 make num-end-5" in await t.said())
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check("zero: saved as the 5 and 0 bond with one wrong check", rec["whole"] == 5 and rec["right"] == 0 and rec["tries"] == 1, json.dumps(rec))
    await t.wait_phase(["open"], 15)
    await page.evaluate("MW.store.setting('check', 'auto')")  # a grown-up switches mode mid-round
    await t.tap(1030, 300)                                   # ? + 4 = 4: straight away
    s = await t.wait_phase(["celebrate"], 3)
    check("zero: ? + 4 = 4 answered by a tap straight away (a mode change waits for the next round)", s["phase"] == "celebrate" and s["qi"] == 1, json.dumps(s))
    await t.wait_phase(["open"], 15)
    p3 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("zero: 'zero and six, how many altogether?' (answer 6, no tap line from question 3)",
          p3 == json.dumps([["q-weve-got", "num-mid-0", "and", "num-end-6"], ["q-how-many-altogether"]]).replace(" ", ""), p3)
    await t.fill(6, "whole")
    await t.tap(1030, 300)
    await t.wait_phase(["celebrate"], 3)
    s = await t.wait_phase(["open"], 15)
    p4 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("zero: a zero answer later in the round still ends with the tap line", s["qi"] == 3 and "tap-scruffles" in p4, p4)
    await page.evaluate("MW.rescue.home()")
    nxt = await page.evaluate("MW.rescue.st.check = 'auto', MW.rescue.makeRound()")
    check("zero: the next round uses the new mode (no zero bonds in auto)", not any(0 in (q["left"], q["right"]) for q in nxt))
    await page.evaluate("MW.rescue.st.check = null; MW.store.setting('check', 'tap')")
    check("zero: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_bonds(p):
    print("\n== the bonds: secure rule and rounds ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    E = lambda js, arg=None: page.evaluate(js, arg)
    n = await E("[2,3,4,5,6,7,8,9,10].reduce((s, w) => s + MW.bonds.pairs(w).length, 0)")
    check("bonds: wholes 2 to 10 have 34 bonds, zero bonds included", n == 34, str(n))
    status = "(a) => { const m = MW.bonds.statuses(a.answers); return MW.bonds.status(m, a.w, a.a); }"
    cases = [
        ("three days right first time is secure", [ans(T0 + d * DAY, 7, 3) for d in range(3)], 7, 3, "secure"),
        ("three times on one day is practising", [ans(T0 + i * 60000, 7, 3) for i in range(3)], 7, 3, "practising"),
        ("3 + 4 and 4 + 3 are the same bond", [ans(T0, 7, 3), ans(T0 + DAY, 7, 4), ans(T0 + 2 * DAY, 7, 3)], 7, 3, "secure"),
        ("a wrong check after secure is practising", [ans(T0 + d * DAY, 7, 3) for d in range(3)] + [ans(T0 + 3 * DAY, 7, 3, first=False)], 7, 3, "practising"),
        ("a hint counts as not first time", [ans(T0 + d * DAY, 7, 3) for d in range(2)] + [ans(T0 + 2 * DAY, 7, 3, hint=True)], 7, 3, "practising"),
        ("after a wrong answer the three days start again (2 more: practising)",
         [ans(T0 + d * DAY, 7, 3) for d in range(3)] + [ans(T0 + 3 * DAY, 7, 3, first=False)] + [ans(T0 + d * DAY, 7, 3) for d in (4, 5)], 7, 3, "practising"),
        ("after a wrong answer the three days start again (3 more: secure)",
         [ans(T0 + d * DAY, 7, 3) for d in range(3)] + [ans(T0 + 3 * DAY, 7, 3, first=False)] + [ans(T0 + d * DAY, 7, 3) for d in (4, 5, 6)], 7, 3, "secure"),
        ("never asked is not yet", [ans(T0, 7, 3)], 8, 3, "notyet"),
        ("answers out of order are sorted by time", [ans(T0 + 3 * DAY, 7, 3, first=False)] + [ans(T0 + d * DAY, 7, 3) for d in range(3)], 7, 3, "practising"),
        ("a malformed answer is ignored", [{"t": 1}, ans(T0, 7, 3)], 7, 3, "practising"),
    ]
    for label, answers, w, a, want in cases:
        got = await E(status, {"answers": answers, "w": w, "a": a})
        check(f"bonds: {label}", got == want, got)
    all_secure = secure_answers(NONZERO)
    c1 = await E("(a) => MW.bonds.candidates([2,3,4,5,6,7,8,9,10], MW.bonds.statuses(a), true).length", all_secure)
    c2 = await E("(a) => MW.bonds.candidates([2,3,4,5,6,7,8,9,10], MW.bonds.statuses(a), false).length", all_secure)
    check("bonds: all secure, tap mode: 34 candidates (zero bonds open)", c1 == 34, str(c1))
    check("bonds: all secure, auto mode: 25 candidates (no zero bonds)", c2 == 25, str(c2))
    c3 = await E("() => MW.bonds.candidates([2,3,4,5,6,7,8,9,10], MW.bonds.statuses([]), true).length")
    check("bonds: nothing secure: no zero bonds yet", c3 == 25, str(c3))

    # many rounds with wholes 2 to 6 secure (9 bonds) and 7 to 10 not yet (16 bonds)
    some = secure_answers([b for b in NONZERO if b[0] <= 6])
    rounds = await E("(a) => { const out = []; for (let i = 0; i < 2000; i++) out.push(MW.bonds.pickRound({ wholes: [2,3,4,5,6,7,8,9,10], answers: a, size: 5, zero: false })); return out; }", some)
    sec = [sum(1 for q in r if q["status"] == "secure") for r in rounds]
    check("bonds: every round has five questions", all(len(r) == 5 for r in rounds))
    check("bonds: 1 or 2 secure bonds a round, both happen", set(sec) == {1, 2}, str(sorted(set(sec))))
    check("bonds: no bond twice in a round", all(len({(q["whole"], min(q["left"], q["right"])) for q in r}) == 5 for r in rounds))
    check("bonds: never the same whole twice in a row", all(r[i]["whole"] != r[i - 1]["whole"] for r in rounds for i in range(1, 5)))
    check("bonds: at most two bonds from one whole in a round", all(max(sum(1 for q in r if q["whole"] == w) for w in range(2, 11)) <= 2 for r in rounds))
    qs = [q for r in rounds for q in r]
    share = sum(q["missing"] == "whole" for q in qs) / len(qs)
    check("bonds: about 1 in 4 asks for the whole", 0.2 < share < 0.3, f"{share:.3f}")
    check("bonds: both parts get asked, either way round", {q["missing"] for q in qs} == {"whole", "left", "right"}
          and any(q["left"] > q["right"] for q in qs) and any(q["left"] < q["right"] for q in qs))
    check("bonds: no zero bonds while none is open", not any(q["left"] == 0 or q["right"] == 0 for q in qs))
    seen_work = {(q["whole"], min(q["left"], q["right"])) for q in qs if q["status"] != "secure"}
    check("bonds: every bond that needs work comes up", len(seen_work) == 16, str(len(seen_work)))

    # whole 5's other bonds secure: its zero bond joins in tap mode only
    five = secure_answers([(5, 1), (5, 2), (3, 1)])
    tap = await E("(a) => { const out = []; for (let i = 0; i < 300; i++) out.push(...MW.bonds.pickRound({ wholes: [2,3,4,5,6,7,8,9,10], answers: a, size: 5, zero: true })); return out; }", five)
    auto = await E("(a) => { const out = []; for (let i = 0; i < 300; i++) out.push(...MW.bonds.pickRound({ wholes: [2,3,4,5,6,7,8,9,10], answers: a, size: 5, zero: false })); return out; }", five)
    zeros = {q["whole"] for q in tap if q["left"] == 0 or q["right"] == 0}
    check("bonds: 5 and 0 joins once 1 + 4 and 2 + 3 are secure (and 3 and 0 once 1 + 2 is)", zeros == {3, 5}, str(sorted(zeros)))
    check("bonds: no zero bonds when the answer is checked automatically", not any(q["left"] == 0 or q["right"] == 0 for q in auto))

    small = await E("() => MW.bonds.pickRound({ wholes: [2], answers: [], size: 5, zero: true })")
    check("bonds: only 2 in play still makes a round (1 + 1 five times)", len(small) == 5 and all(q["whole"] == 2 and q["left"] == 1 for q in small), json.dumps(small))
    two = await E("() => { const out = []; for (let i = 0; i < 200; i++) out.push(MW.bonds.pickRound({ wholes: [2, 3], answers: [], size: 5, zero: false })); return out; }")
    spread = [sum(1 for q in r if q["whole"] == 2) for r in two]
    check("bonds: with only 2 and 3 in play, rounds share the bonds out (2 or 3 of each)", set(spread) <= {2, 3}, str(sorted(set(spread))))

    # every question the game can ask: listed for grown-ups to compare with a homework sheet
    allq = await E("() => MW.bonds.allQuestions([2,3,4,5,6,7,8,9,10], true)")
    nonzero = await E("() => MW.bonds.allQuestions([2,3,4,5,6,7,8,9,10], false).length")
    check("bonds: the game can ask 189 questions (135 without zero bonds)", len(allq) == 189 and nonzero == 135, f"{len(allq)}, {nonzero}")
    keys = {(q["whole"], q["left"], q["missing"]) for q in allq}
    check("bonds: every question a round picks is on the list", all((q["whole"], q["left"], q["missing"]) in keys for q in qs + tap))
    lines = ["# Every question MeeMee Rescue can ask", "",
             "Made by tools/tests/test_game.py from the game's own list (MW.bonds.allQuestions); don't edit it by hand.",
             "Zero bonds (marked *) come up only once the other bonds of that number are secure. With MeeMee to count they",
             "come up only when the answer is checked by tapping Scruffles; in numbers mode, whichever check is set (the",
             "answer is the 0 tile, or the other number). Numbers mode asks the same questions with the same words.", "",
             "| Whole | Number sentence | Answer | What Scruffles says |", "|---|---|---|---|"]
    for q in allq:
        w, a, b, m = q["whole"], q["left"], q["right"], q["missing"]
        if m == "whole":
            sent, answer = f"{a} + {b} = ?", w
            words = f"We've got {WORDS[a]} and {WORDS[b]}. How many altogether?"
        else:
            sent = f"? + {b} = {w}" if m == "left" else f"{a} + ? = {w}"
            answer = q[m]
            words = f"Let's make {WORDS[w]}. We've got {WORDS[q['right' if m == 'left' else 'left']]}. How many more?"
        lines.append(f"| {w} | {sent}{' *' if 0 in (a, b) else ''} | {answer} | {words} |")
    (ROOT / "notes" / "all-questions.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"   wrote notes/all-questions.md ({len(allq)} questions)")
    check("bonds: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_grid(p):
    print("\n== the progress grid ==")
    browser = await p.chromium.launch()
    answers = secure_answers([(7, 3), (2, 1), (5, 2)]) + [ans(T0, 5, 1, first=False), ans(T0 + DAY, 9, 4)]
    for name, vw, vh in (("fire", 1046, 653), ("doogee", 1280, 800)):
        ctx, page, problems = await seeded(browser, answers, vw=vw, vh=vh)
        await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('progress')")
        await asyncio.sleep(0.4)
        cells = await page.evaluate("""Array.from(document.querySelectorAll('.gu-grid .mw-cell')).map(c => [c.textContent.trim(), c.className.split(' ').find(x => x.startsWith('is-'))])""")
        got = {t: s for t, s in cells}
        if name == "fire":
            check("grid: 34 bonds, rows 2 to 10", len(cells) == 34, str(len(cells)))
            check("grid: secure bonds marked secure", got.get("3 + 4") == "is-secure" and got.get("1 + 1") == "is-secure" and got.get("2 + 3") == "is-secure", str(got))
            check("grid: answered but not secure is practising", got.get("1 + 4") == "is-practising" and got.get("4 + 5") == "is-practising")
            check("grid: never asked is not yet", got.get("0 + 7") == "is-notyet" and got.get("5 + 5") == "is-notyet")
            ticks = await page.evaluate("document.querySelectorAll('.gu-grid .mw-cell.is-secure svg').length")
            check("grid: a tick on each secure bond", ticks == 3, str(ticks))
            lead = await page.inner_text(".gu-lead")
            check("grid: the summary counts them", lead.startswith("Secure: 3 of 34 bonds. Practising: 2."), lead)
            chips = await page.evaluate("document.querySelectorAll('.gu-chip').length")
            check("grid: the wholes-in-play switches are on the Progress tab", chips == 9, str(chips))
            await page.evaluate("MW.grownups.show('settings')")
            await asyncio.sleep(0.2)
            chips = await page.evaluate("document.querySelectorAll('.gu-chip').length")
            check("grid: and not on Settings", chips == 0, str(chips))
            await page.evaluate("MW.grownups.show('progress')")
            await asyncio.sleep(0.3)
        wide = await page.evaluate("(() => { const g = document.querySelector('.gu-grid'); const b = g.closest('.gu-body') || g.parentElement; return [g.scrollWidth, b.clientWidth]; })()")
        check(f"grid ({name}): the widest row (10) fits without sideways scrolling", wide[0] <= wide[1], str(wide))
        await page.screenshot(path=str(SHOTS / f"{name}-5-grownups-grid.png"))
        check(f"grid ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()



# ---------------------------------------------------------------- 0.4.1: the crew screen and the job moments
CREW_BTN = (250, 510)                 # the crew corner on the map
DECK = {"moggles": (220, 279), "snuffles": (380, 279)}                     # a waiting cat's middle
STATION = {"lookout": (175, 640), "engineer": (485, 640), "navigator": (795, 640), "cook": (1105, 640)}


async def crew_state(page):
    return await page.evaluate("""({ jobs: MW.crew.jobs(), taken: Array.from(document.querySelectorAll('#screen-crew .mw-station.is-taken')).map(e => e.dataset.job),
        badges: Array.from(document.querySelectorAll('#screen-crew .mw-crew-cat')).map(e => e.dataset.who + ':' + e.dataset.job),
        pulse: document.querySelector('#screen-crew [aria-label=Home]').classList.contains('mw-pulse') })""")


async def cat_at(page, who):
    return await page.evaluate("(w => { const c = MW.rescue.crew().cats[w]; return [c.x, c.y]; })(%s)" % json.dumps(who))


async def test_crew(p, name="crew", vw=1280, vh=800, dpr=1):
    print(f"\n== the crew screen ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, name, vw, vh, dpr, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    jobs = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-cat')).map(e => e.dataset.job || '')")
    check(f"{name}: a new tablet's crew have no jobs (no badges on the map)", jobs == ["", ""], str(jobs))
    await asyncio.sleep(1.4)
    await t.tap(*CREW_BTN)
    check(f"{name}: tapping the crew on the map opens the crew screen", await t.wait_screen("screen-crew"))
    await asyncio.sleep(0.3)
    check(f"{name}: it says 'Let's give the crew their jobs!'", (await t.said())[-1:] == ["crew-jobs"], str((await t.said())[-2:]))
    if name == "crew":
        await page.screenshot(path=str(SHOTS / "crew-1-no-jobs.png"))
    await asyncio.sleep(1.5)
    x, y = await cat_at(page, "moggles")
    await t.drag(x, y, *STATION["lookout"])
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: Moggles dragged onto the telescope is the lookout", st["jobs"] == {"moggles": "lookout", "snuffles": None} and st["taken"] == ["lookout"]
          and "moggles:lookout" in st["badges"], json.dumps(st))
    check(f"{name}: 'Moggles is the lookout.'", (await t.said())[-1:] == ["name-moggles is-the job-lookout"], str((await t.said())[-1:]))
    check(f"{name}: no 'crew are ready' with one job left", not st["pulse"])
    await asyncio.sleep(2)
    x, y = await cat_at(page, "snuffles")
    await t.drag(x, y, *STATION["cook"])
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: Snuffles onto the frying pan is the cook", st["jobs"] == {"moggles": "lookout", "snuffles": "cook"}, json.dumps(st))
    check(f"{name}: 'Snuffles is the cook. The crew are ready!'", (await t.said())[-1:] == ["name-snuffles is-the job-cook crew-ready"], str((await t.said())[-1:]))
    check(f"{name}: with both jobs given, Home pulses (back to the map)", st["pulse"])
    if name == "crew":
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SHOTS / "crew-2-jobs.png"))
    await asyncio.sleep(2.5)
    # Moggles onto Snuffles's job: they swap
    x, y = await cat_at(page, "moggles")
    await t.drag(x, y, *STATION["cook"])
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: one job per cat: onto the other cat's job, they swap", st["jobs"] == {"moggles": "cook", "snuffles": "lookout"}, json.dumps(st))
    check(f"{name}: both new jobs are said", (await t.said())[-1:] == ["name-moggles is-the job-cook name-snuffles is-the job-lookout crew-ready"], str((await t.said())[-1:]))
    await asyncio.sleep(3.5)
    # a drop between the stations' rows (off the bottom half) takes the job off
    x, y = await cat_at(page, "snuffles")
    await t.drag(x, y, 640, 300)
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: a cat put back on the deck has no job", st["jobs"] == {"moggles": "cook", "snuffles": None} and not st["pulse"], json.dumps(st))
    back = await cat_at(page, "snuffles")
    check(f"{name}: ... and goes back to its place on the deck", abs(back[0] - DECK["snuffles"][0]) < 3 and abs(back[1] - DECK["snuffles"][1]) < 6, str(back))
    x, y = await cat_at(page, "snuffles")
    await t.drag(x, y, *STATION["engineer"])
    await asyncio.sleep(2.5)
    n = len(await t.said())
    x, y = await cat_at(page, "moggles")
    await t.tap(x, y)
    await asyncio.sleep(0.5)
    check(f"{name}: tapping a cat says its job", (await t.said())[n:] == ["name-moggles is-the job-cook"], str((await t.said())[n:]))
    await asyncio.sleep(2)
    await t.tap(1208, 68)                                    # Hear it again
    await asyncio.sleep(0.4)
    check(f"{name}: Hear-again says each cat's job", (await t.said())[-1:] == ["name-moggles is-the job-cook name-snuffles is-the job-engineer"], str((await t.said())[-1:]))
    # the screen going off mid-drag: the cat goes back to its place, and the next drag still works
    x, y = await cat_at(page, "snuffles")
    sx, sy = await t.screen(x, y)
    await touch(t, "touchStart", [(7, (sx, sy))])
    for k in range(1, 6):
        await touch(t, "touchMove", [(7, (sx + k * 30, sy - k * 10))])
        await asyncio.sleep(0.03)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.5)
    held = await page.evaluate("MW.rescue.crew().dragger.dragging()")
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.6)
    st = await crew_state(page)
    check(f"{name}: a pause lets go of a held cat, and its job stays", not held and st["jobs"] == {"moggles": "cook", "snuffles": "engineer"}, json.dumps([held, st["jobs"]]))
    check(f"{name}: coming back says the crew's jobs again", (await t.said())[-1:] == ["name-moggles is-the job-cook name-snuffles is-the job-engineer"], str((await t.said())[-1:]))
    await t.tap(66, 62)                                      # Home
    check(f"{name}: Home goes back to the map", await t.wait_screen("screen-map"))
    jobs = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    check(f"{name}: the cats wear their job badges on the map", jobs == ["moggles:cook", "snuffles:engineer"]
          and await page.evaluate("document.querySelectorAll('#screen-map .mw-badge').length") == 2, str(jobs))
    if name == "crew":
        await asyncio.sleep(0.4)
        await page.screenshot(path=str(SHOTS / "crew-3-map-badges.png"))
    await page.reload()
    await page.wait_for_load_state("load")
    check(f"{name}: the jobs are remembered after closing the game", await page.evaluate("JSON.stringify(MW.crew.jobs())") == json.dumps({"moggles": "cook", "snuffles": "engineer"}, separators=(",", ":")))
    check(f"{name}: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


def overlaps_circle(box, c):
    """box: [x, y, w, h] on the stage; c: (cx, cy, r)."""
    nx = min(max(c[0], box[0]), box[0] + box[2]); ny = min(max(c[1], box[1]), box[1] + box[3])
    return (nx - c[0]) ** 2 + (ny - c[1]) ** 2 < c[2] ** 2


async def moment_box(page, sel):
    """The stage box of what is drawn in a moment (its cat and what it holds), or None."""
    return await page.evaluate("""(sel => { const el = document.querySelector(sel); if (!el) return null;
        const s = MW.stage.scale, ox = MW.stage.offX, oy = MW.stage.offY;
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        el.querySelectorAll('svg').forEach(g => { const r = g.getBoundingClientRect(); x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); });
        return [(x0 - ox) / s, (y0 - oy) / s, (x1 - x0) / s, (y1 - y0) / s]; })(%s)""" % json.dumps(sel))


async def test_moments(p):
    print("\n== the job moments ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "moments", 1046, 653, 1.22, mode="auto")
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.3)
    await t.tap(*RESCUE)
    await t.wait_screen("screen-game")
    await asyncio.sleep(1.2)
    up = await page.evaluate("!!document.querySelector('#screen-game [data-moment=lookout].is-shown')")
    check("moments: the lookout peeks over the asteroid as the round starts", up)
    order = await page.evaluate("""(() => { const lay = document.querySelector('[data-moment=lookout]').closest('.mw-moments');
        const kids = Array.from(document.querySelectorAll('#screen-game > *'));
        const tray = kids.find(e => e.style.left === '745px' && e.style.top === '515px');
        const pod = document.querySelector('#screen-game .mw-pod');
        return [kids.indexOf(pod) < kids.indexOf(lay), lay.nextElementSibling === tray]; })()""")
    lb = await moment_box(page, "#screen-game [data-moment=lookout]")
    check("moments: the lookout is behind the asteroid and in front of the ship", order == [True, True], str(order))
    check("moments: the lookout keeps clear of the diagram", lb and not any(overlaps_circle(lb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]), str(lb))
    await page.screenshot(path=str(SHOTS / "moments-1-lookout.png"))
    await t.wait_phase(["open"], 15)
    await asyncio.sleep(2.4)
    check("moments: the lookout ducks down once the MeeMee are spotted", not await page.evaluate("!!document.querySelector('[data-moment=lookout]')"))
    await t.fill(4, "right")
    await asyncio.sleep(0.5)
    eb = await moment_box(page, "#screen-game [data-moment=engineer]")
    check("moments: the engineer comes to the ship on a right answer", eb is not None)
    check("moments: the engineer keeps clear of the diagram and the asteroid",
          eb and not any(overlaps_circle(eb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]) and eb[1] + eb[3] < 530, str(eb))
    tapping = await page.evaluate("document.querySelector('[data-moment=engineer] .mw-spanner').classList.contains('is-tapping')")
    check("moments: ... and taps it with the spanner", tapping)
    await page.screenshot(path=str(SHOTS / "moments-2-engineer.png"))
    await asyncio.sleep(3.8)
    check("moments: the engineer goes as the lights stop", not await page.evaluate("!!document.querySelector('[data-moment=engineer].is-shown')"))
    # the navigator and the cook
    await page.evaluate("MW.crew.save({moggles: 'navigator', snuffles: 'cook'})")
    s = await t.wait_phase(["open"], 15)
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await t.fill(5, "whole")
    for _ in range(80):
        if await page.evaluate("MW.events.filter(e => e.type === 'moment').length") > n0:
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)
    nb = await moment_box(page, "#screen-game [data-moment=navigator]")
    route = await page.evaluate("(() => { const r = document.querySelector('#screen-game .mw-route path'); return r ? r.getAttribute('d') : null; })()")
    check("moments: the navigator holds up the star map as the star turns peach", nb is not None)
    check("moments: ... with a dotted route to the next star", route is not None and "NaN" not in route, str(route))
    check("moments: the navigator keeps clear of the diagram and the stars",
          nb and not any(overlaps_circle(nb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]) and nb[1] > 95, str(nb))
    await page.screenshot(path=str(SHOTS / "moments-3-navigator.png"))
    for q in range(2, 5):
        s = await t.wait_phase(["open"], 15)
        await t.fill(s["answer"], s["target"])
    await t.wait_phase(["done"], 20)
    for _ in range(80):
        if await page.evaluate("!!document.querySelector('#screen-end [data-moment=cook].is-shown')"):
            break
        await asyncio.sleep(0.1)
    check("moments: the cook brings fish on the end screen", await page.evaluate("!!document.querySelector('#screen-end [data-moment=cook].is-shown')"))
    badges = await page.evaluate("Array.from(document.querySelectorAll('#screen-end .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    check("moments: the end screen's cats wear their badges", badges == ["moggles:navigator", "snuffles:cook"], str(badges))
    await asyncio.sleep(1)
    await page.screenshot(path=str(SHOTS / "moments-4-cook.png"))
    for _ in range(80):                                      # the cook's moment comes before "Another rescue?"
        if "round-another" in await t.said():
            break
        await asyncio.sleep(0.1)
    said = await t.said()
    check("moments: no words in the moments (a round sounds the same)", "round-another" in said and not any("job-" in x or "name-" in x for x in said), str(said[-3:]))
    await t.tap(66, 62)
    await asyncio.sleep(0.4)
    check("moments: Home clears them", await page.evaluate("document.querySelectorAll('[data-moment]').length") == 0)
    # nobody has a job: no moments
    await page.evaluate("MW.crew.save({moggles: null, snuffles: null}); MW.rescue.nextRound = %s" % json.dumps(ROUND))
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 15)
    await t.fill(4, "right")
    await asyncio.sleep(4)
    check("moments: no jobs, no moments", await page.evaluate("MW.events.filter(e => e.type === 'moment').length") == n0)
    # a very quick first answer: the lookout makes way for the engineer
    await t.tap(66, 62)
    await asyncio.sleep(0.3)
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'}); MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["asking", "open"], 15)
    await page.evaluate("for (let i = 0; i < 4; i++) { const c = MW.rescue.st.counters.filter(c => c.where === 'tray').pop(); MW.rescue.drop(c, 550, 470, false); }")
    await asyncio.sleep(0.5)
    both = await page.evaluate("[!!document.querySelector('[data-moment=lookout].is-shown'), !!document.querySelector('[data-moment=engineer].is-shown')]")
    check("moments: a quick first answer: the lookout ducks down as the engineer comes", both == [False, True], str(both))
    check("moments: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()



# ---------------------------------------------------------------- 0.5.0: the world and its games
async def test_carryover(p):
    print("\n== a tablet's saved data from 0.4.1 carries over ==")
    browser = await p.chromium.launch()
    answers = secure_answers([(7, 3), (2, 1)]) + [ans(T0, 5, 1, first=False)]
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True)
    saved = {"v": 1, "music": False, "settings": {"check": "auto", "checkPicked": True, "wholes": [2, 3, 4, 5, 6, 7],
                                                 "crew": {"moggles": "cook", "snuffles": "engineer"}}, "answers": answers}
    await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                              % json.dumps(json.dumps(saved)))
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    got = await page.evaluate("""({ music: MW.audio.music.isOn(), check: MW.store.setting('check'), wholes: MW.store.setting('wholes'),
        jobs: MW.crew.jobs(), answers: MW.store.get('answers').length,
        secure: Object.values(MW.bonds.statuses(MW.store.get('answers'))).filter(s => s.status === 'secure').length })""")
    check("carry-over: music off, answer check and wholes in play kept", got["music"] is False and got["check"] == "auto" and got["wholes"] == [2, 3, 4, 5, 6, 7], json.dumps(got))
    check("carry-over: the crew's jobs kept", got["jobs"] == {"moggles": "cook", "snuffles": "engineer"}, json.dumps(got["jobs"]))
    check("carry-over: every answer kept, and the bonds secure before are secure now", got["answers"] == len(answers) and got["secure"] == 2, json.dumps(got))
    await page.evaluate("const g = MW.store.game('starter'); g.rounds = 3; MW.store.save()")
    after = await page.evaluate("JSON.parse(localStorage.getItem('mimi-world'))")
    check("carry-over: a newer game's saved data sits beside the old, without disturbing it",
          after["games"] == {"starter": {"rounds": 3}} and len(after["answers"]) == len(answers) and after["settings"]["crew"]["moggles"] == "cook", json.dumps(after["games"]))
    check("carry-over: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


TPL_PORT = 8793


async def test_template(p):
    print("\n== a new game joins the world (the template) ==")
    import shutil
    import subprocess
    sys.path.insert(0, str(ROOT / "tools"))
    import games as G
    taken = {g.get("planet") for g in G.load()}
    free = [i for i in range(G.PLANETS) if i not in taken]
    if not free:
        check("template: a new game joins the world", True, "skipped: every planet has a game")
        return
    here = pathlib.Path(__file__).resolve().parent
    out, src = here / "serve-template", here / "serve-template-src" / "starter"
    if src.parent.exists():
        shutil.rmtree(src.parent)
    shutil.copytree(ROOT / "games" / "_template", src, ignore=shutil.ignore_patterns("__pycache__"))
    gj = json.loads((src / "game.json").read_text(encoding="utf-8"))
    gj["planet"] = free[0]
    (src / "game.json").write_text(json.dumps(gj), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--no-audio", "--out", str(out), "--extra-game", str(src)],
                       capture_output=True, text=True)
    check("template: builds into a test copy with no problems", r.returncode == 0 and "Starter game" in r.stdout, (r.stdout + r.stderr)[-300:])
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", TPL_PORT), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": 1046, "height": 653}, device_scale_factor=1.22, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(f"http://127.0.0.1:{TPL_PORT}/")
    await page.wait_for_load_state("load")
    t = Tablet(page, await ctx.new_cdp_session(page))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    planets = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-planet')).map(b => b.getAttribute('aria-label'))")
    locks = await page.evaluate("document.querySelectorAll('#screen-map .mw-planet-lock').length")
    check("template: its planet is on the map, MeeMee Rescue's is still first, the rest still to come",
          planets[0] == "MeeMee Rescue" and planets[free[0]] == "Starter game" and locks == G.PLANETS - len(taken) - 1, json.dumps([planets, locks]))
    await asyncio.sleep(1.2)
    await page.screenshot(path=str(SHOTS / "template-1-map.png"))
    pl = await page.evaluate("MW.LAYOUT.map.planets[%d]" % free[0])
    await t.tap(pl["x"], pl["y"])
    ok = await t.wait_screen("screen-starter-play", 2)
    said = await t.said()
    check("template: tapping its planet opens its screen (its name isn't recorded yet, so no banner: straight away)",
          ok and await page.evaluate("[MW.audio.recorded('starter-name'), MW.events.some(e => e.type === 'banner' && e.detail === 'up Starter game')]") == [False, False],
          str(said[-3:]))
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / "template-2-screen.png"))
    for _ in range(3):
        await t.tap(640, 400)
        await asyncio.sleep(0.25)
    back = await t.wait_screen("screen-map", 5)
    check("template: three taps on the star finish it and go home", back and await page.evaluate("MW.store.game('starter').rounds") == 1)
    await asyncio.sleep(0.5)
    await t.tap(pl["x"], pl["y"])
    await t.wait_screen("screen-starter-play")
    await t.tap(66, 62)
    check("template: Home on its screen goes back to the map", await t.wait_screen("screen-map", 5))
    await asyncio.sleep(0.5)
    rp = await page.evaluate("MW.LAYOUT.map.planets[0]")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(rp["x"], rp["y"])
    s = await t.wait_phase(["asking", "open"])
    check("template: MeeMee Rescue still plays beside it", s["screen"] == "screen-game", json.dumps(s))
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('starter-progress')")
    await asyncio.sleep(0.3)
    text = await page.inner_text(".gu-body")
    check("template: its tab in the grown-ups area shows its saved data", "Rounds finished on this tablet: 1." in text, text[:80])
    check("template: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()
    srv.shutdown()


# ---------------------------------------------------------------- MeeMee Rockets (games/words): the tricky-words game
HEAR = (1208, 68)                     # Hear it again
HOME = (66, 62)
AGAIN = (1160, 500)                   # "Another go?" on the end screen
WORDS_PLANET = "MW.LAYOUT.map.planets[MW.world.games.find(g => g.id === 'words').planet]"
PRAISE_LINES = {"words-found-it", "words-super-reading", "words-well-done"}
W_ROUND = [{"word": "one", "step": "tiles"}, {"word": "spray", "step": "letters"}, {"word": "here", "step": "tiles"},
           {"word": "popcorn", "step": "harder"}, {"word": "my", "step": "tiles"}]
# What each sound tile says in its word (0.6.0 PRD, Lines tab; answers 13, 22 and 23): the sound ids (words-s-<id>), one
# per tile, '-' for the e of a split pair, which says nothing
W_SOUNDS = {
    "all": "or l", "of": "o v", "one": "wu n", "here": "h ear", "magnet": "m a g n e t", "cartoon": "k ar t oo-long n",
    "rabbit": "r a b b i t", "spray": "s p r ai", "popcorn": "p o p k or n", "proud": "p r ow d", "toy": "t oy", "say": "s ai",
    "go": "g oa", "my": "m igh", "into": "i n t oo-long", "out": "ow t", "feel": "f ee l", "food": "f oo-long d", "sort": "s or t",
    "down": "d ow n", "right": "r igh t", "hard": "h ar d", "took": "t oo-short k", "hear": "h ear",
    "what": "w o t", "she": "sh ee", "me": "m ee", "love": "l u v", "misses": "m i s e s", "chain": "ch ai n", "queen": "qu ee n",
    "chair": "ch air", "year": "y ear", "cobweb": "k o b w e b", "goats": "g oa t s", "farmyard": "f ar m y ar d",
    "they": "th-voiced ai", "some": "s u m -", "were": "w ur", "sure": "sh ure", "green": "g r ee n", "brown": "b r ow n",
    "train": "t r ai n", "thinks": "th i n k s", "drum": "d r u m", "splat": "s p l a t", "paint": "p ai n t", "frog": "f r o g",
    "said": "s e d", "you": "y oo-long", "like": "l igh k -", "push": "p oo-short sh", "day": "d ai", "cloud": "k l ow d",
    "boy": "b oy", "read": "r ee d", "play": "p l ai", "sound": "s ow n d", "joy": "j oy", "treat": "t r ee t",
}


async def w_state(page):
    return await page.evaluate("""(() => { const g = MW.wordsGame.st; return { phase: MW.world.st.phase, screen: MW.shell.screen, qi: g.qi,
        word: g.item && g.item.word, next: g.next, places: g.places.map(p => p.text), mode: g.plan && g.plan.mode,
        tapped: g.tapped, drops: g.drops, hinted: g.hinted }; })()""")


async def w_wait(page, phases, timeout=25):
    for _ in range(int(timeout / 0.1)):
        s = await w_state(page)
        if s["phase"] in phases:
            return s
        await asyncio.sleep(0.1)
    return await w_state(page)


async def w_wait_said(t, line, timeout=12, after=0):
    """Wait until a line has been said (after the first `after` lines)."""
    for _ in range(int(timeout / 0.1)):
        if line in (await t.said())[after:]:
            return True
        await asyncio.sleep(0.1)
    return False


async def w_rockets(page):
    return await page.evaluate("MW.wordsGame.st.rockets.map(r => ({word: r.word, x: r.cx, lit: r.el.classList.contains('is-lit'), hint: r.el.classList.contains('is-hint')}))")


async def w_tiles(page):
    """The tiles still in the tray: text, middle (stage px), spare, tricky, glowing."""
    return await page.evaluate("""MW.wordsGame.st.tiles.filter(c => !c.placed).map(c => ({text: c.text, x: c.x, y: c.y, spare: c.spare,
        tricky: c.el.classList.contains('is-tricky'), glow: c.el.classList.contains('is-glow'), hx: c.home.x, hy: c.home.y}))""")


async def w_slot(page):
    """Where the next porthole is, in stage px."""
    return await page.evaluate("""(() => { const g = MW.wordsGame.st, sl = g.ship.slots[g.next];
        return [150 + sl.x * g.ship.scale, 195 + sl.y * g.ship.scale]; })()""")


async def w_place(t, which=0):
    """Drag the next tile (the which-th tile with the right letters) into its porthole."""
    page = t.page
    need = (await w_state(page))["places"][(await w_state(page))["next"]]
    tile = [c for c in await w_tiles(page) if c["text"] == need][which]
    sx, sy = await w_slot(page)
    await t.drag(tile["x"], tile["y"], sx, sy + 10)
    return tile


async def w_drop_wrong(t, spare=None):
    """Drag a tile that isn't the next one onto the rocket (a spare, if spare is True). Returns the tile."""
    page = t.page
    s = await w_state(page)
    need = s["places"][s["next"]]
    tiles = [c for c in await w_tiles(page) if c["text"] != need and (spare is None or c["spare"] == spare)]
    sx, sy = await w_slot(page)
    await t.drag(tiles[0]["x"], tiles[0]["y"], sx, sy)
    await asyncio.sleep(0.35)
    return tiles[0]


async def w_build(t):
    """Place every remaining tile, right first time."""
    while True:
        s = await w_state(t.page)
        if s["phase"] != "words-build" or s["next"] >= len(s["places"]):
            return s
        await w_place(t)


async def w_tray(page):
    """The cargo tray's place and size (stage px), and how many rows of tiles it holds."""
    return await page.evaluate("""(() => { const e = document.querySelector('#screen-words-build .words-tray');
        return { box: [e.offsetLeft, e.offsetTop, e.offsetWidth, e.offsetHeight],
                 rows: new Set(MW.wordsGame.st.tiles.filter(c => !c.placed).map(c => Math.round(c.home.y))).size }; })()""")


async def w_open(t, page, round_):
    """Play, then the MeeMee Rockets planet, with the round fixed."""
    await page.evaluate("MW.wordsGame.nextRound = %s" % json.dumps(round_))
    if await page.evaluate("MW.shell.screen") == "screen-start":
        await t.tap(*PLAY)
        await t.wait_screen("screen-map")
        await asyncio.sleep(0.4)
    pl = await page.evaluate(WORDS_PLANET)
    await t.tap(pl["x"], pl["y"])
    return await w_wait(page, ["words-find"])


async def test_words_round(p, name, vw, vh, dpr):
    """A whole round on one tablet size: Find and Build at each step, the wrong-answer paths, Hear-again, the end."""
    print(f"\n== MeeMee Rockets: a round ({name}, {vw}x{vh}) ==")
    browser, ctx, page, t, problems, requests = await open_tablet(p, name, vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    on_page = set(await page.evaluate("Object.keys(MW.audio.manifest.voice).filter(k => k.startsWith('words-'))"))
    w_lines = json.loads((ROOT / "games" / "words" / "lines.json").read_text(encoding="utf-8"))["lines"]
    recorded = {l["id"] for l in w_lines if not l.get("pending")}
    pending = {l["id"] for l in w_lines if l.get("pending")}
    check(f"{name}: every recorded MeeMee Rockets line is on the page, and no pending one ({len(recorded)} recorded, {len(pending)} pending)",
          on_page == recorded, f"missing {sorted(recorded - on_page)[:5]}, extra {sorted(on_page - recorded)[:5]}")
    s = await w_open(t, page, W_ROUND)
    said = await t.said()
    check(f"{name}: the indigo planet says 'MeeMee Rockets!' and opens Find", s["screen"] == "screen-words-find" and "words-name" in said, json.dumps(s))
    check(f"{name}: the round starts with 'Ready to launch some rockets?'", "words-round-ready" in said)
    await w_wait_said(t, "words-find words-w-one")
    check(f"{name}: Find asks 'Find the word… one.'", "words-find words-w-one" in await t.said())
    rockets = await w_rockets(page)
    words = [r["word"] for r in rockets]
    check(f"{name}: three rockets, three different words, one of them 'one'", len(set(words)) == 3 and "one" in words, str(words))
    text = (await page.inner_text("#screen-words-find")).split()
    check(f"{name}: nothing to read on Find but the three words", sorted(text) == sorted(words), str(text))
    marked = await page.evaluate("document.querySelectorAll('#screen-words-find .is-tricky').length")
    check(f"{name}: no tricky parts marked in Find", marked == 0, str(marked))
    stars = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-find .mw-stars svg')).map(s => s.dataset.state).join(',')")
    check(f"{name}: five stars, the first current", stars == "current,todo,todo,todo,todo", stars)
    sizes = await page.evaluate("Array.from(document.querySelectorAll('.words-rocket')).map(b => Math.min(b.offsetWidth, b.offsetHeight))")
    check(f"{name}: each rocket is a big target (at least 84 stage px)", min(sizes) >= 84, str(sizes))
    await page.screenshot(path=str(SHOTS / f"{name}-words-1-find.png"))

    # Hear-again, then three wrong taps
    await asyncio.sleep(0.6)
    n = len(await t.said())
    await t.tap(*HEAR)
    await asyncio.sleep(0.3)
    got = (await t.said())[n:]
    check(f"{name}: Hear-again in Find says the question again, once", got == ["words-find words-w-one"], str(got))
    wrong = [r for r in rockets if r["word"] != "one"]
    await t.tap(wrong[0]["x"], 450)
    await asyncio.sleep(0.3)
    got = (await t.said())[-1]
    check(f"{name}: a wrong tap says the word tapped, 'Let's try again.' and the question",
          got == f"words-that-word words-w-{wrong[0]['word']} words-try-again words-find words-w-one", got)
    check(f"{name}: no glow after one wrong tap", not any(r["hint"] for r in await w_rockets(page)))
    await asyncio.sleep(0.8)
    await t.tap(wrong[1]["x"], 450)
    await asyncio.sleep(0.3)
    got = (await t.said())[-1]
    check(f"{name}: a second wrong tap says the word, then 'Let's look together.'", got == f"words-that-word words-w-{wrong[1]['word']} words-look-together", got)
    hints = [r["word"] for r in await w_rockets(page) if r["hint"]]
    check(f"{name}: ... and the right word glows", hints == ["one"], str(hints))
    await asyncio.sleep(1.2)
    await page.screenshot(path=str(SHOTS / f"{name}-words-2-find-hint.png"))
    await t.tap(wrong[0]["x"], 450)
    await asyncio.sleep(0.3)
    got = (await t.said())[-1]
    check(f"{name}: a later wrong tap only says its word", got == f"words-that-word words-w-{wrong[0]['word']}", got)
    check(f"{name}: the glow stays until he taps it", [r["word"] for r in await w_rockets(page) if r["hint"]] == ["one"])
    await asyncio.sleep(0.8)
    n = len(await t.said())
    await t.tap([r for r in rockets if r["word"] == "one"][0]["x"], 450)
    await asyncio.sleep(0.3)
    lit = [r["word"] for r in await w_rockets(page) if r["lit"]]
    sfx = await page.evaluate("MW.events.filter(e => e.type === 'sfx').map(e => e.detail).slice(-1)[0]")
    check(f"{name}: the right tap: a chime and the rocket lights its engines", lit == ["one"] and sfx == "chime" and not any(r["hint"] for r in await w_rockets(page)), str([lit, sfx]))
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"{name}-words-3-right.png"))
    await w_wait_said(t, "words-build words-w-one", after=n)
    said = (await t.said())[n:]
    check(f"{name}: a praise line, then 'Now build the word… one.'", said[:1] and said[0] in PRAISE_LINES and "words-build words-w-one" in said, str(said))

    # Build "one" in sound tiles: o · ne, both tricky (the whole word); two wrong drops and the hint
    s = await w_wait(page, ["words-build"])
    check(f"{name}: Build: 'one' from sound tiles o and ne", s["mode"] == "tiles" and s["places"] == ["o", "ne"], json.dumps(s))
    trays = [await w_tray(page)]
    socks = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-build .words-part')).filter(e => e.querySelector('[stroke-dasharray]')).map(e => Math.round(+e.getAttribute('width')))")
    check(f"{name}: a round porthole for o and an oval for ne", socks == [120, 168], str(socks))
    tiles = await w_tiles(page)
    check(f"{name}: the tray has o and ne, both marked as the tricky part", sorted(c["text"] for c in tiles) == ["ne", "o"] and all(c["tricky"] for c in tiles), str(tiles))
    text = (await page.inner_text("#screen-words-build")).split()
    check(f"{name}: nothing to read on Build but the tiles", sorted(text) == ["ne", "o"], str(text))
    await asyncio.sleep(0.8)
    n = len(await t.said())
    await t.tap(*HEAR)
    await asyncio.sleep(0.3)
    got = (await t.said())[n:]
    check(f"{name}: Hear-again in Build says 'Now build the word… one.' again, once", got == ["words-build words-w-one"], str(got))
    await page.screenshot(path=str(SHOTS / f"{name}-words-4-build.png"))
    c = await w_drop_wrong(t)
    back = [x for x in await w_tiles(page) if x["text"] == c["text"]][0]
    check(f"{name}: a wrong tile on the word floats back to its place", abs(back["x"] - back["hx"]) < 2 and abs(back["y"] - back["hy"]) < 2, str(back))
    check(f"{name}: the first wrong drop says 'Let's try again.'", (await t.said())[-1] == "words-try-again" and (await w_state(page))["drops"] == 1)
    await w_drop_wrong(t)
    glow = [x["text"] for x in await w_tiles(page) if x["glow"]]
    check(f"{name}: the second wrong drop says 'Let's look together.' and the next tile glows", (await t.said())[-1] == "words-look-together" and glow == ["o"], str(glow))
    ring = await page.evaluate("""(() => { const g = document.querySelector('.words-tile.is-glow .words-glow'); if (!g) return null; const r = g.firstElementChild;
        return [getComputedStyle(g).display, (r.getAttribute('class') || '').split(' ').includes('s-spark'), r.getAttribute('opacity'), r.getAttribute('fill'),
                +r.getAttribute('stroke-width'), getComputedStyle(g).animationName]; })()""")
    check(f"{name}: the glow is a strong, steady spark ring (solid, not faded, not flashing)", ring is not None and ring[0] != "none" and ring[1] and ring[2] is None
          and ring[3] == "none" and ring[4] >= 10 and ring[5] == "none", str(ring))
    await asyncio.sleep(0.6)
    await page.screenshot(path=str(SHOTS / f"{name}-words-5-build-hint.png"))
    await w_place(t)
    s = await w_state(page)
    check(f"{name}: o snaps into the first porthole", s["next"] == 1 and not any(x["glow"] for x in await w_tiles(page)), json.dumps(s))
    check(f"{name}: the first tricky part to land says 'That's the tricky bit.'", (await t.said())[-1] == "words-tricky-bit")
    await w_place(t)
    s = await w_wait(page, ["words-built"], 3)
    launch = await page.evaluate("document.querySelector('#screen-words-build .words-ship').classList.contains('is-launch')")
    check(f"{name}: the last tile launches the rocket", s["phase"] == "words-built" and launch, json.dumps(s))
    await asyncio.sleep(1.0)
    await page.screenshot(path=str(SHOTS / f"{name}-words-6-launch.png"))
    await w_wait_said(t, "words-you-built words-w-one")
    check(f"{name}: 'You built the word… one.'", "words-you-built words-w-one" in await t.said())
    for _ in range(60):                                      # the star comes as the line ends
        stars = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-build .mw-stars svg')).map(s => s.dataset.state).join(',')")
        if stars != "current,todo,todo,todo,todo":
            break
        await asyncio.sleep(0.1)
    check(f"{name}: ... and its star", stars == "done,current,todo,todo,todo", stars)
    rec = await page.evaluate("MW.wordsGame.answers().slice(-1)[0]")
    check(f"{name}: saved with 3 wrong taps, 2 wrong drops and the hint", rec["w"] == "one" and rec["tapped"] == 3 and rec["drops"] == 2 and rec["hint"] is True, json.dumps(rec))

    # "spray" in letters mode: one tile per letter with its spares i and e; a spare floats back
    s = await w_wait(page, ["words-find"])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "spray"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    tiles = await w_tiles(page)
    check(f"{name}: letters mode: s p r a y with the spares i and e", s["mode"] == "letters" and s["places"] == list("spray")
          and sorted(c["text"] for c in tiles) == sorted("sprayie") and sorted(c["text"] for c in tiles if c["spare"]) == ["e", "i"], str([c["text"] for c in tiles]))
    socks = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-build .words-part')).filter(e => e.querySelector('[stroke-dasharray]')).length")
    check(f"{name}: five round portholes", socks == 5, str(socks))
    trays.append(await w_tray(page))
    await w_place(t)
    sp = await w_drop_wrong(t, spare=True)
    back = [x for x in await w_tiles(page) if x["text"] == sp["text"] and x["spare"]][0]
    check(f"{name}: a spare dropped on the word floats back", abs(back["x"] - back["hx"]) < 2 and abs(back["y"] - back["hy"]) < 2 and (await w_state(page))["next"] == 1, str(back))
    check(f"{name}: ... and counts as a wrong drop ('Let's try again.')", (await t.said())[-1] == "words-try-again" and (await w_state(page))["drops"] == 1)
    await w_place(t)
    await w_place(t)
    await page.screenshot(path=str(SHOTS / f"{name}-words-7-letters.png"))
    await w_build(t)
    await w_wait(page, ["words-built"], 3)

    # "here" in sound tiles: h · ere; its tricky part lands, but the line was said this round already
    s = await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "here"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    check(f"{name}: 'here' from sound tiles h and ere", s["places"] == ["h", "ere"], json.dumps(s))
    trays.append(await w_tray(page))
    await w_build(t)
    await w_wait(page, ["words-built"], 3)
    await w_wait_said(t, "words-you-built words-w-here")
    check(f"{name}: 'That's the tricky bit.' only once a round", (await t.said()).count("words-tricky-bit") == 1, str((await t.said()).count("words-tricky-bit")))

    # "popcorn" in harder letters: 10 tiles in two rows; either p is just as good
    s = await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "popcorn"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    tiles = await w_tiles(page)
    extra = [c["text"] for c in tiles if c["text"] not in "popcornk"]
    check(f"{name}: harder letters: 10 tiles, the word's letters, its spare k and letters from the week's other words",
          s["mode"] == "harder" and len(tiles) == 10 and sorted(c["text"] for c in tiles if c["text"] in "popcornk") == sorted("popcornk")
          and len(extra) == 2 and len(set(extra)) == 2, str([c["text"] for c in tiles]))
    check(f"{name}: harder letters: the tray holds two rows", len({round(c["y"]) for c in tiles}) == 2, str(sorted({round(c["y"]) for c in tiles})))
    trays.append(await w_tray(page))
    await page.screenshot(path=str(SHOTS / f"{name}-words-8-harder.png"))
    first_p = await w_place(t, which=1)                       # the other p: just as good
    check(f"{name}: a tile with the same letters is just as good (the other p)", (await w_state(page))["next"] == 1, str(first_p))
    await w_build(t)
    await w_wait(page, ["words-built"], 3)

    # "my" right first time
    s = await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "my"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    trays.append(await w_tray(page))
    boxes = [tuple(x["box"]) for x in trays]
    check(f"{name}: the tray stays in one place for every word", len(set(boxes)) == 1, str(boxes))
    b = boxes[0]
    check(f"{name}: ... below the rocket and left of Scruffles", b[1] > 449 and b[0] + b[2] < 951 and b[1] + b[3] <= 776, str(b))
    check(f"{name}: one row when the tiles fit, two rows when they don't (7 letters) and always for harder letters",
          [x["rows"] for x in trays] == [1, 2, 1, 2, 1], str([x["rows"] for x in trays]))
    await w_build(t)
    rec = await page.evaluate("MW.wordsGame.answers().slice(-1)[0]")
    check(f"{name}: a word found and built with no wrong tap or drop is saved as right first time",
          rec["w"] == "my" and rec["tapped"] == 0 and rec["drops"] == 0 and rec["hint"] is False, json.dumps(rec))

    # the end of the round, and another go
    s = await w_wait(page, ["words-done"], 20)
    check(f"{name}: after five words, the end of the round", s["screen"] == "screen-words-end", json.dumps(s))
    await w_wait_said(t, "words-round-another", 15)
    said = await t.said()
    check(f"{name}: 'You launched all the rockets!' then 'Another go?'", said[-2:] == ["words-round-done", "words-round-another"], str(said[-3:]))
    end = await page.evaluate("[Array.from(document.querySelectorAll('#screen-words-end .mw-stars svg')).map(s => s.dataset.state).join(','), document.getElementById('words-again').classList.contains('mw-pulse'), document.querySelector('#screen-words-end').innerText.trim()]")
    check(f"{name}: five stars earned, the Play button says 'tap here', nothing to read", end == ["done,done,done,done,done", True, ""], str(end))
    tune = await page.evaluate("MW.events.filter(e => e.type === 'sfx' && e.detail === 'tune').length")
    check(f"{name}: the end-of-round tune plays", tune == 1, str(tune))
    await asyncio.sleep(0.5)
    await page.screenshot(path=str(SHOTS / f"{name}-words-9-end.png"))
    answers = await page.evaluate("MW.wordsGame.answers().length")
    check(f"{name}: five words saved on this tablet", answers == 5, str(answers))
    await page.evaluate("MW.wordsGame.nextRound = %s" % json.dumps(W_ROUND))
    n = len(await t.said())
    await t.tap(*AGAIN)
    s = await w_wait(page, ["words-starting", "words-find"], 5)
    await w_wait_said(t, "words-round-ready", after=n)
    check(f"{name}: 'Another go?' Play starts a new round", s["screen"] == "screen-words-find" and s["qi"] == 0 and "words-round-ready" in (await t.said())[n:], json.dumps(s))
    await asyncio.sleep(0.5)
    await t.tap(*HOME)
    await asyncio.sleep(0.3)
    n = len(await t.said())
    await asyncio.sleep(2.5)
    check(f"{name}: Home in a round goes back to the map, and nothing more is said", await page.evaluate("MW.shell.screen") == "screen-map" and len(await t.said()) == n,
          str((await t.said())[n:]))
    outside = [u for u in requests if not u.startswith(ORIGIN)]
    check(f"{name}: no requests outside the site", not outside, ", ".join(outside[:3]))
    check(f"{name}: no console errors or warnings", not problems, "; ".join(problems[:4]))
    await browser.close()


async def test_words_pause(p):
    """Pausing and Home mid-round, on the Fire's size."""
    print("\n== MeeMee Rockets: pausing and Home ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "words-pause", 1046, 653, 1.22, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    hide = "Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    show = "Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    await w_open(t, page, [{"word": "cartoon", "step": "tiles"}, {"word": "of", "step": "tiles"}])
    await w_wait_said(t, "words-find words-w-cartoon")
    await page.evaluate(hide)
    await asyncio.sleep(0.8)
    n = len(await t.said())
    wrong = [r for r in await w_rockets(page) if r["word"] != "cartoon"][0]
    await t.tap(wrong["x"], 450)
    await asyncio.sleep(0.4)
    check("words-pause: paused in Find, a tap does nothing", await page.evaluate("MW.world.st.paused") and len(await t.said()) == n and (await w_state(page))["tapped"] == 0)
    await page.evaluate(show)
    await asyncio.sleep(0.6)
    check("words-pause: coming back asks the question again", (await t.said())[n:][:1] == ["words-find words-w-cartoon"], str((await t.said())[n:]))
    await t.tap([r for r in await w_rockets(page) if r["word"] == "cartoon"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_wait_said(t, "words-build words-w-cartoon")
    await w_place(t)
    # pick a tile up, then the screen goes off: it goes back to the tray; coming back asks again
    tile = [c for c in await w_tiles(page) if c["text"] == "ar"][0]
    x0, y0 = await t.screen(tile["x"], tile["y"])
    await touch(t, "touchStart", [(8, (x0, y0))])
    for k in range(1, 6):
        await touch(t, "touchMove", [(8, (x0 + k * 20, y0 - k * 30))])
        await asyncio.sleep(0.03)
    held = await page.evaluate("MW.wordsGame.st.tiles.some(c => c.lifted)")
    await page.evaluate(hide)
    await asyncio.sleep(0.6)
    back = [c for c in await w_tiles(page) if c["text"] == "ar"][0]
    check("words-pause: a tile held when the screen goes off goes back to the tray", held and abs(back["x"] - back["hx"]) < 2 and abs(back["y"] - back["hy"]) < 2, str(back))
    n = len(await t.said())
    await page.evaluate(show)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.6)
    check("words-pause: coming back to Build says 'Now build the word… cartoon.' again", (await t.said())[n:][:1] == ["words-build words-w-cartoon"], str((await t.said())[n:]))
    s = await w_state(page)
    check("words-pause: the word carries on where it was", s["next"] == 1 and s["drops"] == 0, json.dumps(s))
    # Home mid-word: back to the map, the tiles put away
    await t.tap(*HOME)
    await asyncio.sleep(0.4)
    left = await page.evaluate("[MW.shell.screen, MW.world.st.phase, document.querySelectorAll('.words-tile').length, document.querySelectorAll('.words-ship').length]")
    check("words-pause: Home from Build goes to the map and puts the tiles away", left == ["screen-map", "map", 0, 0], str(left))
    # Home just as the rocket launches: nothing more is said on the map
    await asyncio.sleep(1.5)
    await w_open(t, page, [{"word": "of", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "of"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    await t.tap(*HOME)
    n = len(await t.said())
    await asyncio.sleep(3)
    check("words-pause: Home during the launch: back on the map, nothing more said", await page.evaluate("MW.shell.screen") == "screen-map" and len(await t.said()) == n,
          str((await t.said())[n:]))
    # Home from the end screen
    await w_open(t, page, [{"word": "toy", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "toy"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    check("words-pause: a round of one word ends with one star", await page.evaluate("document.querySelectorAll('#screen-words-end .mw-stars svg').length") == 1)
    await t.tap(*HOME)
    check("words-pause: Home from the end screen goes back to the map", await t.wait_screen("screen-map", 3))
    check("words-pause: MeeMee Rescue's answers are untouched", await page.evaluate("MW.store.get('answers').length") == 0)
    check("words-pause: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


def w_ans(t, w, step="tiles", first=True, hint=False):
    return {"t": t, "w": w, "step": step, "mode": step, "tapped": 0 if first else 1, "drops": 0, "hint": hint}


async def test_words_steps(p):
    """Each word's step, how rounds are chosen, and every question the game can ask."""
    print("\n== MeeMee Rockets: the words, the steps and the rounds ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    E = lambda js, arg=None: page.evaluate(js, arg)
    book = await E("(() => { const b = MW.wordSteps.read(MW.wordsData); return { problems: b.problems, order: b.order, weeks: b.weeks, tray: b.harderTray, start: b.startWeek }; })()")
    check("words: the words file reads with no problems", not book["problems"], "; ".join(book["problems"][:3]))
    check("words: 60 words over weeks 1 to 5 (each week's 4 tricky words and 8 others), week 5 to start, the harder tray holds 10",
          len(book["order"]) == 60 and [w["week"] for w in book["weeks"]] == [1, 2, 3, 4, 5] and all(len(w["tricky"]) == 4 and len(w["other"]) == 8 for w in book["weeks"])
          and book["start"] == 5 and book["tray"] == 10, json.dumps(book)[:200])
    lines = {c["id"] for c in json.loads((ROOT / "games" / "words" / "lines.json").read_text(encoding="utf-8"))["lines"]}
    on_page = set(await E("Object.keys(MW.audio.manifest.voice)"))
    missing = [w for w in book["order"] if f"words-w-{w}" not in lines or f"words-w-{w}" not in on_page]
    check("words: every word has its line in lines.json and its recording on the page", not missing, str(missing))
    in_play = {wk: await E("(w) => MW.wordSteps.inPlay(MW.wordSteps.read(MW.wordsData), w)", wk) for wk in (1, 2, 3, 4, 5, "all")}
    check("words: in play: week 1 has its 12 words, week 3 its 12 and 8 earlier tricky words, week 5 its 12 and 16 earlier tricky words, all weeks 60",
          len(in_play[1]) == 12 and len(in_play[3]) == 20 and len(in_play[5]) == 28 and len(in_play["all"]) == 60 and set(in_play["all"]) == set(book["order"]),
          str({k: len(v) for k, v in in_play.items()}))
    check("words: week 5 in play: its tricky words, its other words, then earlier weeks' tricky words",
          in_play[5][:12] == ["all", "of", "one", "here", "magnet", "cartoon", "rabbit", "spray", "popcorn", "proud", "toy", "say"])

    # every word of weeks 1 to 5, as a Find question and as a Build question at each step, through the game's own screens
    # (with every week in play, so Find's other two words come from all of them)
    await E("(() => { const g = MW.store.game('words'); g.week = 'all'; MW.store.save(); })()")
    rows = await E("""() => {
        const G = MW.wordsGame, S = MW.wordSteps, out = [];
        MW.world.st.phase = 'map';
        S.inPlay(G.book, 'all').forEach(w => {
          const r = { word: w, find: null, build: {} };
          G.setFind({ word: w }); G.showFind({ word: w, step: 'tiles' });
          r.find = { phase: MW.world.st.phase, screen: MW.shell.screen, words: G.st.rockets.map(x => x.word), prompt: JSON.stringify(G.st.prompt) };
          [['tiles', 'tiles'], ['letters', 'letters'], ['harder', 'harder'], ['secure', 'harder']].forEach(([step, mode]) => {
            G.showBuild({ word: w, step: step });
            const st = G.st, b = { mode: st.plan.mode, places: st.places.map(x => (x.tricky ? '[' + x.text + ']' : x.text)), sounds: st.places.map(x => x.sound),
              tray: st.tiles.map(c => c.text + (c.spare ? '*' : '')), sockets: st.ship.el.querySelectorAll('[stroke-dasharray]').length,
              marked: st.tiles.filter(c => c.el.classList.contains('is-tricky')).map(c => c.text), prompt: JSON.stringify(st.prompt), want: mode };
            st.places.forEach((pl, i) => { const sl = st.ship.slots[i]; const c = st.tiles.find(t => !t.placed && t.text === pl.text);
              G.drop(c, 150 + sl.x * st.ship.scale, 195 + sl.y * st.ship.scale, false); });
            b.done = MW.world.st.phase === 'words-built';
            b.built = Array.from(st.ship.inner.querySelectorAll('.words-tile')).map(e => e.textContent).join('');
            r.build[step] = b;
            MW.world.home();
          });
          out.push(r);
        });
        return out; }""")
    data = await E("MW.wordsData.words")
    ok_find = [r["word"] for r in rows if r["find"]["phase"] == "words-find" and r["find"]["screen"] == "screen-words-find"
               and r["word"] in r["find"]["words"] and len(set(r["find"]["words"])) == 3 and set(r["find"]["words"]) <= set(in_play["all"])
               and r["find"]["prompt"] == json.dumps([["words-find", f"words-w-{r['word']}"]]).replace(" ", "")]
    check("words: every word of weeks 1 to 5 can be asked in Find (60), among two other words in play", len(ok_find) == 60 and len(rows) == 60,
          str(sorted(set(book["order"]) - set(ok_find))))
    bad = []
    for r in rows:
        w = r["word"]
        tiles = data[w]["tiles"].split()
        letters = [("[" + ch + "]" if t.startswith("[") else ch) for t in tiles for ch in t.strip("[]")]
        spares = data[w].get("spares", "").split()
        for step, b in r["build"].items():
            want = tiles if b["want"] == "tiles" else letters
            plain = [x.strip("[]") for x in want]
            tray_plain = sorted(x.rstrip("*") for x in b["tray"])
            if b["mode"] != b["want"] or b["places"] != want or b["sockets"] != len(want) or not b["done"] or b["built"] != w:
                bad.append(f"{w} {step}: {b}")
            elif b["prompt"] != json.dumps([["words-build", f"words-w-{w}"]]).replace(" ", ""):
                bad.append(f"{w} {step}: prompt {b['prompt']}")
            elif sorted(b["marked"]) != sorted(x.strip("[]") for x in want if x.startswith("[")):
                bad.append(f"{w} {step}: marked {b['marked']}")
            elif b["want"] == "tiles" and tray_plain != sorted(plain):
                bad.append(f"{w} {step}: sound tiles tray {b['tray']}")
            elif b["want"] == "letters" and tray_plain != sorted(plain + spares):
                bad.append(f"{w} {step}: letters tray {b['tray']}")
            elif b["want"] == "harder":
                extra = [x.rstrip("*") for x in b["tray"]]
                for ch in plain + spares:
                    extra.remove(ch)
                if len(b["tray"]) != max(10, len(plain) + len(spares)) or len(set(extra)) != len(extra) or set(extra) & set(plain + spares):
                    bad.append(f"{w} {step}: harder tray {b['tray']}")
    check("words: every word of weeks 1 to 5 can be built (240 questions: sound tiles, letters, harder letters, and secure in harder letters)",
          not bad and len(rows) * 4 == 240, "; ".join(bad[:3]))
    sounds = {r["word"]: " ".join(x if x else "?" for x in r["build"]["tiles"]["sounds"]) for r in rows}
    wrong = {w: [sounds.get(w), want] for w, want in W_SOUNDS.items() if sounds.get(w) != want}
    check("words: in sound tiles every tile says its sound in its word, as on the Lines tab (60 words; tricky tiles say what they say in the word)",
          not wrong and len(sounds) == 60, json.dumps(wrong)[:300])
    # the list for grown-ups to compare with the homework (like MeeMee Rescue's all-questions.md)
    out = ["# Every question MeeMee Rockets can ask (weeks 1 to 5)", "",
           "Made by tools/tests/test_game.py from the game's own words file (games/words/words.js); don't edit it by hand.",
           "Each word is asked twice in a round: Find (tap it among three rockets) and Build (drag its tiles into the rocket).",
           "Tricky parts are in [square brackets]: on the tiles they are the darker peach letters. Spares are marked *.",
           "In sound tiles each tile says its sound as it is picked up (the recording words-s- and the sound; - says nothing).",
           "Harder letters adds letters from other words until the tray holds 10 tiles (a different few each time).", "",
           "| Word | Week | Find | Sound tiles | Tiles say | Letters | Harder letters |", "|---|---|---|---|---|---|---|"]
    week_of = {w: wk["week"] for wk in book["weeks"] for w in wk["tricky"] + wk["other"]}
    for r in rows:
        w = r["word"]
        b = r["build"]
        let = " ".join(b["letters"]["places"]) + " + " + " ".join(x + "*" for x in data[w].get("spares", "").split())
        out.append(f"| {w} | {week_of[w]} | Find the word… {w}. | {' · '.join(b['tiles']['places'])} | {' · '.join(x or '?' for x in b['tiles']['sounds'])} | {let} | {let} + {10 - len(b['letters']['tray'])} more |")
    (ROOT / "notes" / "all-questions-words.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("   wrote notes/all-questions-words.md (60 words, 240 questions)")
    await E("(() => { const g = MW.store.game('words'); g.week = 5; MW.store.save(); })()")

    # the steps: three days right first time at each step; a wrong try restarts that step's days; back a step only from
    # secure, after two slips in a row (answer 12 of the 0.6.0 PRD)
    status = "(a) => { const m = MW.wordSteps.statuses(a.answers); return [MW.wordSteps.step(m, a.w), (m[a.w] || {days: []}).days.length]; }"
    days = lambda n, step="tiles", w="of", start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    cases = [
        ("never asked is not yet", [], "of", ["notyet", 0]),
        ("asked once is practising sound tiles", days(1), "of", ["tiles", 1]),
        ("three times on one day is still sound tiles", [w_ans(T0 + i * 60000, "of") for i in range(3)], "of", ["tiles", 1]),
        ("three days right first time with sound tiles moves to letters", days(3), "of", ["letters", 0]),
        ("three more days in letters moves to harder letters", days(3) + days(3, "letters", start=3), "of", ["harder", 0]),
        ("three more days in harder letters: secure", days(3) + days(3, "letters", start=3) + days(3, "harder", start=6), "of", ["secure", 0]),
        ("a wrong try restarts the step's three days", days(2) + [w_ans(T0 + 2 * DAY, "of", first=False)] + days(2, start=3), "of", ["tiles", 2]),
        ("... and three more days after it moves on", days(2) + [w_ans(T0 + 2 * DAY, "of", first=False)] + days(3, start=3), "of", ["letters", 0]),
        ("a wrong try in letters stays in letters (only a secure word goes back)", days(3) + days(2, "letters", start=3) + [w_ans(T0 + 5 * DAY, "of", "letters", first=False)], "of", ["letters", 0]),
        ("a hint is not right first time", days(2) + [w_ans(T0 + 2 * DAY, "of", hint=True)], "of", ["tiles", 0]),
        ("one slip after secure stays secure", days(3) + days(3, "letters", start=3) + days(3, "harder", start=6) + [w_ans(T0 + 9 * DAY, "of", "secure", first=False)], "of", ["secure", 0]),
        ("words are counted separately", days(3) + days(1, w="one"), "one", ["tiles", 1]),
        ("answers out of order are sorted by time", list(reversed(days(3))), "of", ["letters", 0]),
        ("an answer saved at a later step carries on from there (older answers trimmed)", days(1, "harder"), "of", ["harder", 1]),
        ("a malformed answer is ignored", [{"t": 1}, {"w": "of"}] + days(1), "of", ["tiles", 1]),
    ]
    for label, answers, w, want in cases:
        got = await E(status, {"answers": answers, "w": w})
        check(f"words: {label}", got == want, str(got))
    mode = await E("['notyet', 'tiles', 'letters', 'harder', 'secure'].map(MW.wordSteps.mode)")
    check("words: built with sound tiles, then letters, then harder letters (secure words too)", mode == ["tiles", "tiles", "letters", "harder", "harder"], str(mode))

    # rounds: five different words, one or two secure ones for review, the rest needing work
    secure = [x for w in in_play[5][:9] for x in days(3, w=w) + days(3, "letters", w, 3) + days(3, "harder", w, 6)]
    rounds = await E("(a) => { const out = []; for (let i = 0; i < 1500; i++) out.push(MW.wordSteps.pickRound({ words: a.words, answers: a.answers, size: 5 })); return out; }",
                     {"words": in_play[5], "answers": secure})
    nsec = [sum(1 for q in r if q["step"] == "secure") for r in rounds]
    check("words: every round has five different words", all(len(r) == 5 and len({q["word"] for q in r}) == 5 for r in rounds))
    check("words: 1 or 2 secure words a round, both happen", set(nsec) == {1, 2}, str(sorted(set(nsec))))
    work = {q["word"] for r in rounds for q in r if q["step"] != "secure"}
    check("words: every word that needs work comes up (19)", len(work) == 19, str(len(work)))
    check("words: a word never asked starts with sound tiles", all(q["step"] == "tiles" for r in rounds for q in r if q["word"] not in in_play[5][:9]))
    small = await E("(w) => MW.wordSteps.pickRound({ words: w, answers: [], size: 5 })", in_play[1][:4])
    check("words: only four words in play: a round of four", len(small) == 4 and {q["word"] for q in small} == set(in_play[1][:4]), json.dumps(small))
    allq = await E("[MW.wordSteps.allQuestions(MW.wordSteps.read(MW.wordsData), 5).length, MW.wordSteps.allQuestions(MW.wordSteps.read(MW.wordsData), 'all').length]")
    check("words: the game can ask 112 questions in week 5 (28 words) and 240 with weeks 1 to 5 (60 words): Find, and Build at three steps", allq == [112, 240], str(allq))
    gone = await E("delete MW.audio.manifest.voice['words-w-magnet'], [MW.wordsGame.inPlay().includes('magnet'), MW.wordsGame.inPlay().length]")
    check("words: a word whose recording isn't on the page stays out of play", gone == [False, 27], str(gone))
    check("words: no console errors", not problems, "; ".join(problems[:3]))
    await ctx.close()

    # a word moving on in the game itself: two days right first time already, a third today moves it to letters
    ctx, page, problems = await seeded(browser, [])
    t = Tablet(page, await ctx.new_cdp_session(page))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    now = await page.evaluate("Date.now()")
    seed = {"week": 5, "answers": [w_ans(now - 2 * DAY, "of"), w_ans(now - DAY, "of")]}
    await page.evaluate("(g) => { MW.store.game('words').week = g.week; MW.store.game('words').answers = g.answers; MW.store.save(); }", seed)
    await w_open(t, page, ["of"])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "of"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    check("words-steps: with two days behind it, 'of' is still built from sound tiles", s["mode"] == "tiles", json.dumps(s))
    await w_build(t)
    step = await page.evaluate("MW.wordSteps.step(MW.wordSteps.statuses(MW.wordsGame.answers()), 'of')")
    check("words-steps: right first time on a third day: 'of' moves to letters", step == "letters", step)
    await w_wait(page, ["words-done"], 20)
    await t.tap(*HOME)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.6)
    await w_open(t, page, ["of"])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "of"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    tiles = sorted(c["text"] for c in await w_tiles(page))
    check("words-steps: the next round builds 'of' from letters, with its spare v", s["mode"] == "letters" and tiles == ["f", "o", "v"], str([s["mode"], tiles]))
    await w_drop_wrong(t, spare=True)
    await w_build(t)
    step = await page.evaluate("(() => { const m = MW.wordSteps.statuses(MW.wordsGame.answers()); return [m.of.step, m.of.days.length]; })()")
    check("words-steps: a wrong try in letters keeps it in letters and restarts its days", step == ["letters", 0], str(step))
    check("words-steps: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_grownups(p):
    """The Words tab: the week picker, the grid of steps, and clearing this game's progress only."""
    print("\n== MeeMee Rockets: the grown-ups' Words tab ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    words = (days(3, "tiles", "all") + days(3, "letters", "all", 3) + days(3, "harder", "all", 6)       # secure
             + days(1, "tiles", "of") + days(3, "tiles", "one") + days(3, "tiles", "go") + days(3, "letters", "go", 3) + days(1, "tiles", "toy"))
    rescue = secure_answers([(7, 3)])
    for name, vw, vh in (("fire", 1046, 653), ("doogee", 1280, 800)):
        ctx = await browser.new_context(viewport={"width": vw, "height": vh}, has_touch=True, is_mobile=True)
        saved = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True, "crew": {"moggles": "cook", "snuffles": "lookout"}},
                 "answers": rescue, "games": {"words": {"answers": words}}}
        await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                                  % json.dumps(json.dumps(saved)))
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        t = Tablet(page, await ctx.new_cdp_session(page))
        await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('words-progress')")
        await asyncio.sleep(0.4)
        tabs = await page.evaluate("Array.from(document.querySelectorAll('.gu-tab')).map(b => b.textContent)")
        check(f"words-grownups ({name}): a Words tab in the grown-ups area", "Words" in tabs, str(tabs))
        cells = await page.evaluate("Object.fromEntries(Array.from(document.querySelectorAll('.words-grid .words-cell')).map(c => [c.lastChild.textContent, c.className.split(' ').find(x => x.startsWith('is-'))]))")
        check(f"words-grownups ({name}): the grid shows all 28 words", len(cells) == 28, str(len(cells)))
        want = {"all": "is-secure", "of": "is-tiles", "one": "is-letters", "go": "is-harder", "toy": "is-tiles", "here": "is-notyet", "push": "is-notyet"}
        check(f"words-grownups ({name}): each word shows its step (secure, sound tiles, letters, harder letters, not yet)",
              all(cells.get(w) == s for w, s in want.items()), str({w: cells.get(w) for w in want}))
        labels = await page.evaluate("Array.from(document.querySelectorAll('.words-grid-label')).map(e => e.textContent)")
        check(f"words-grownups ({name}): rows for week 5's tricky words, its other words and earlier weeks", labels == ["Tricky words", "Week 5 words", "Earlier weeks"], str(labels))
        on = await page.evaluate("Array.from(document.querySelectorAll('.words-week')).map(b => b.textContent + (b.classList.contains('is-on') ? '*' : ''))")
        check(f"words-grownups ({name}): weeks 1 to 5 to pick from, then Weeks 1–5, week 5 in play to start", on == ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5*", "Weeks 1\u20135"], str(on))
        wide = await page.evaluate("(() => { const g = document.querySelector('.words-grid'); const b = g.closest('.gu-body'); return [g.scrollWidth, b.clientWidth]; })()")
        check(f"words-grownups ({name}): the grid fits without sideways scrolling", wide[0] <= wide[1], str(wide))
        await page.screenshot(path=str(SHOTS / f"{name}-words-grownups.png"))
        # pick week 2 with a tap on its button
        box = await page.evaluate("""(() => { const b = Array.from(document.querySelectorAll('.words-week')).find(b => b.textContent === 'Week 2');
            const r = b.getBoundingClientRect(); return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale]; })()""")
        await t.tap(*box)
        await asyncio.sleep(0.4)
        got = await page.evaluate("""[MW.wordsGame.week(), MW.wordsGame.inPlay(), Array.from(document.querySelectorAll('.words-grid-label')).map(e => e.textContent),
            Array.from(document.querySelectorAll('.words-week.is-on')).map(b => b.textContent)]""")
        week2 = ["what", "she", "me", "love", "misses", "chain", "queen", "chair", "year", "cobweb", "goats", "farmyard", "go", "my", "into", "out"]
        check(f"words-grownups ({name}): tapping Week 2 puts week 2 in play: its words and week 1's tricky words",
              got[0] == 2 and sorted(got[1]) == sorted(week2) and got[3] == ["Week 2"], json.dumps(got[:2]))
        check(f"words-grownups ({name}): the grid shows week 2's tricky words, its other words, earlier weeks and later weeks",
              got[2] == ["Tricky words", "Week 2 words", "Earlier weeks", "Later weeks"], str(got[2]))
        rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 200; i++) MW.wordsGame.makeRound().forEach(q => out.add(q.word)); return Array.from(out); })()")
        check(f"words-grownups ({name}): rounds then use only week 2's words and earlier tricky words", set(rounds) == set(got[1]), str(sorted(rounds)))
        cells2 = await page.evaluate("document.querySelectorAll('.words-grid .words-cell').length")
        if name == "fire":
            await page.screenshot(path=str(SHOTS / f"{name}-words-grownups-week2.png"))
        # clear: two taps; only this game's answers go
        clear = await page.evaluate("""(() => { const b = Array.from(document.querySelectorAll('.gu-body .gu-btn')).find(b => b.textContent.startsWith('Clear'));
            b.scrollIntoView(); const r = b.getBoundingClientRect(); return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale]; })()""")
        await t.tap(*clear)
        await asyncio.sleep(0.3)
        first = await page.evaluate("MW.wordsGame.answers().length")
        await t.tap(*clear)
        await asyncio.sleep(0.4)
        after = await page.evaluate("""[MW.wordsGame.answers().length, MW.store.get('answers').length, JSON.stringify(MW.crew.jobs()), MW.wordsGame.week(),
            document.querySelectorAll('.words-grid .words-cell.is-notyet').length]""")
        check(f"words-grownups ({name}): one tap on Clear does nothing yet", first == len(words), str(first))
        check(f"words-grownups ({name}): the second tap clears this game's progress (every word not yet)", after[0] == 0 and after[4] == cells2 == 52, str([after, cells2]))
        check(f"words-grownups ({name}): ... and nothing else: MeeMee Rescue's answers, the crew and the week in play stay",
              after[1] == len(rescue) and after[2] == json.dumps({"moggles": "cook", "snuffles": "lookout"}, separators=(",", ":")) and after[3] == 2, str(after))
        await page.evaluate("MW.grownups.close()")
        await page.reload()
        await page.wait_for_load_state("load")
        kept = await page.evaluate("[MW.wordsGame.week(), MW.wordsGame.answers().length]")
        check(f"words-grownups ({name}): the week in play is remembered on the tablet", kept == [2, 0], str(kept))
        check(f"words-grownups ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_words_first_find(p):
    """Every word fits its plate on the very first Find after a fresh load (the bold type may not have loaded yet)."""
    print("\n== MeeMee Rockets: words fit their plates on the first Find ==")
    browser = await p.chromium.launch()
    for name, vw, vh, dpr in (("fire", 1046, 653, 1.22), ("doogee", 1280, 800, 2)):
        ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
        problems, worst, bad = [], {}, []
        page = await ctx.new_page()
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        words = await page.evaluate("MW.wordSteps.inPlay(MW.wordsGame.book, 'all')")
        await page.close()
        for w in words:
            page = await ctx.new_page()                    # a fresh page: a new visit, nothing in bold drawn yet
            page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
            await page.goto(ORIGIN + "/")
            await page.wait_for_load_state("load")
            await page.evaluate("MW.wordsGame.nextRound = [%s]; MW.wordsGame.start()" % json.dumps(w))
            await page.wait_for_function("MW.wordsGame.st.rockets.some(r => r.word === %s)" % json.dumps(w), timeout=5000)
            await page.evaluate("document.fonts.ready.then(() => true)")
            await asyncio.sleep(0.15)
            got = await page.evaluate("""MW.wordsGame.st.rockets.filter(r => r.word).map(r => [r.word,
                r.wordEl.getBoundingClientRect().width / MW.stage.scale, r.wordEl.parentNode.getBoundingClientRect().width / MW.stage.scale, parseFloat(r.wordEl.style.fontSize)])""")
            for word, width, plate, size in got:
                worst[word] = max(worst.get(word, 0), width)
                if width > plate - 28 + 0.5:                 # 14 px clear of each end of the plate, inside its screws
                    bad.append(f"{word}: {width:.0f} px at {size:.0f} px in a {plate:.0f} px plate")
            await page.close()
        check(f"words-first-find ({name}): every word fits its plate on the first Find of a fresh visit ({len(words)} visits)",
              not bad and len(words) == 60 and all(w in worst for w in words), "; ".join(bad[:4]))
        check(f"words-first-find ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def w_double_tap(t, sx, sy, gap=0.12):
    """Two quick taps on the same place, gap seconds apart (a five-year-old's double tap)."""
    x, y = await t.screen(sx, sy)
    for k in range(2):
        await touch(t, "touchStart", [(30 + k, (x, y))])
        await asyncio.sleep(0.03)
        await touch(t, "touchEnd", [])
        if k == 0:
            await asyncio.sleep(gap - 0.03)


async def test_words_fixes(p):
    """A double tap on one wrong rocket, a pause during "You built the word…", and the week changed mid-round."""
    print("\n== MeeMee Rockets: double taps, pauses and the week mid-round ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "words-fixes", 1280, 800, 1, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    hide = "Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    show = "Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"

    # a quick double tap on one wrong rocket is one try; a tap on a different rocket still counts
    await w_open(t, page, [{"word": "cartoon", "step": "tiles"}])
    await w_wait_said(t, "words-find words-w-cartoon")
    await asyncio.sleep(0.4)
    wrong = [r for r in await w_rockets(page) if r["word"] != "cartoon"]
    n = len(await t.said())
    await w_double_tap(t, wrong[0]["x"], 450)
    await asyncio.sleep(0.25)
    s = await w_state(page)
    hint = [r["word"] for r in await w_rockets(page) if r["hint"]]
    check("words-fixes: a double tap on a wrong rocket is one wrong try (no hint)", s["tapped"] == 1 and not hint, json.dumps([s["tapped"], hint]))
    check("words-fixes: ... and its line isn't cut off by a second one", (await t.said())[n:] == [f"words-that-word words-w-{wrong[0]['word']} words-try-again words-find words-w-cartoon"],
          str((await t.said())[n:]))
    await t.tap(wrong[1]["x"], 450)                        # while "That word is…" is still playing
    await asyncio.sleep(0.3)
    s = await w_state(page)
    check("words-fixes: a tap on a different rocket while that line plays still counts", s["tapped"] == 2 and (await t.said())[-1] == f"words-that-word words-w-{wrong[1]['word']} words-look-together"
          and [r["word"] for r in await w_rockets(page) if r["hint"]] == ["cartoon"], json.dumps(s))
    for _ in range(80):
        if not await page.evaluate("MW.audio.speaking()"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.3)
    await t.tap(wrong[1]["x"], 450)                        # the same rocket again once its line has finished: a try
    await asyncio.sleep(0.3)
    check("words-fixes: the same rocket tapped again after its line has finished counts", (await w_state(page))["tapped"] == 3)
    await t.tap(*HOME)
    await asyncio.sleep(1.2)

    # a pause during "You built the word… toy.": it is said again before the next word
    await w_open(t, page, [{"word": "toy", "step": "tiles"}, {"word": "say", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "toy"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    n = len(await t.said())
    await w_build(t)
    await w_wait_said(t, "words-you-built words-w-toy", after=n)
    await asyncio.sleep(0.3)                               # partway through the line
    await page.evaluate(hide)
    await asyncio.sleep(1.2)
    await page.evaluate(show)
    await w_wait(page, ["words-find"], 15)
    await w_wait_said(t, "words-find words-w-say", after=n)
    said = (await t.said())[n:]
    built = [i for i, x in enumerate(said) if x == "words-you-built words-w-toy"]
    nxt = said.index("words-find words-w-say") if "words-find words-w-say" in said else -1
    check("words-fixes: a pause during 'You built the word… toy.' says it again before the next word", len(built) == 2 and built[1] < nxt, str(said))
    stars = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-find .mw-stars svg')).map(s => s.dataset.state).join(',')")
    check("words-fixes: ... and its star is earned", stars == "done,current", stars)
    await t.tap(*HOME)
    await asyncio.sleep(1.2)

    # the week changed in the grown-ups area mid-round: this round keeps its words; the change starts with the next round
    await page.evaluate("const g = MW.store.game('words'); g.week = 2; MW.store.save()")
    week2 = set(await page.evaluate("MW.wordsGame.inPlay()"))
    await w_open(t, page, [{"word": "what", "step": "tiles"}, {"word": "love", "step": "harder"}, {"word": "she", "step": "tiles"}])
    await w_wait_said(t, "words-find words-w-what")
    await t.tap(46, 754, 3.3)                              # the grown-ups lock
    await page.evaluate("MW.grownups.show('words-progress')")
    await asyncio.sleep(0.3)
    box = await page.evaluate("""(() => { const b = Array.from(document.querySelectorAll('.words-week')).find(b => b.textContent === 'Week 5');
        const r = b.getBoundingClientRect(); return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale]; })()""")
    await t.tap(*box)
    await asyncio.sleep(0.3)
    await page.evaluate("MW.grownups.close()")
    check("words-fixes: week 5 picked mid-round in the grown-ups area", await page.evaluate("MW.wordsGame.week()") == 5)
    await asyncio.sleep(0.6)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "what"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    others = []
    for word in ("love", "she"):
        await w_wait(page, ["words-find"], 20)
        others += [r["word"] for r in await w_rockets(page) if r["word"] != word]
        if word == "love":
            await asyncio.sleep(0.3)
            await t.tap([r for r in await w_rockets(page) if r["word"] == word][0]["x"], 450)
            s = await w_wait(page, ["words-build"])
            fill = [c["text"] for c in await w_tiles(page) if c["text"] not in "loveu"]
            src = await page.evaluate("""(() => { const G = MW.wordsGame, f = MW.wordSteps.fillFrom(G.book, G.st.week, 'love', G.st.pool);
                return { week: G.st.week, own: f[0], pool: f[1] }; })()""")
            own2 = ["what", "she", "me", "love", "misses", "chain", "queen", "chair", "year", "cobweb", "goats", "farmyard"]
            own_letters = set("".join(w for w in own2 if w != "love")) - set("loveu")
            check("words-fixes: harder letters mid-round fill first from week 2's own words (the round's week, not week 5), which have enough letters",
                  s["mode"] == "harder" and src["week"] == 2 and src["own"] == own2 and sorted(src["pool"]) == sorted(week2) and len(own_letters) >= 5
                  and len(fill) == 5 and set(fill) <= own_letters, str([fill, src["week"], src["own"]]))
            await w_build(t)
    check("words-fixes: the rest of the round's Finds still use week 2's words", others and set(others) <= week2, str(others))
    await t.tap(*HOME)
    await asyncio.sleep(1.0)
    pl = await page.evaluate(WORDS_PLANET)
    await t.tap(pl["x"], pl["y"])
    await w_wait(page, ["words-find"])
    pool = await page.evaluate("(MW.wordsGame.st.pool || []).length")
    check("words-fixes: the next round uses week 5's words", pool == 28, str(pool))
    check("words-fixes: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_motion(p):
    """A real Find and Build with reduce motion on: nothing moves; things fade or change at once."""
    print("\n== MeeMee Rockets: reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": 1046, "height": 653}, device_scale_factor=1.22, has_touch=True, is_mobile=True, reduced_motion="reduce")
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    t = Tablet(page, await ctx.new_cdp_session(page))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    check("words reduce motion: the kit knows", await page.evaluate("MW.reduceMotion"))
    await w_open(t, page, [{"word": "say", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "say"][0]["x"], 450)
    await asyncio.sleep(0.2)
    got = await page.evaluate("(() => { const r = document.querySelector('.words-rocket.is-lit'); return r ? [getComputedStyle(r).transform, getComputedStyle(r).animationName] : null; })()")
    check("words reduce motion: the right rocket lights its engines without moving", got == ["none", "none"], str(got))
    await w_wait(page, ["words-build"])

    async def drop_now(tile, x1, y1):
        """Drag and let go, then read where the tile is drawn straight away (no waiting for a slide)."""
        x0, y0 = await t.screen(tile["x"], tile["y"])
        sx, sy = await t.screen(x1, y1)
        await touch(t, "touchStart", [(40, (x0, y0))])
        for k in range(1, 9):
            await touch(t, "touchMove", [(40, (x0 + (sx - x0) * k / 8, y0 + (sy - y0) * k / 8))])
            await asyncio.sleep(0.016)
        await touch(t, "touchEnd", [])
        await asyncio.sleep(0.03)
        return await page.evaluate("""(t => { const c = MW.wordsGame.st.tiles.find(c => c.text === t); const r = c.el.getBoundingClientRect();
            return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale,
                    getComputedStyle(c.el).transitionDuration, c.home.x, c.home.y]; })(%s)""" % json.dumps(tile["text"]))

    sx, sy = await w_slot(page)
    ay = [c for c in await w_tiles(page) if c["text"] == "ay"][0]
    got = await drop_now(ay, sx, sy)
    check("words reduce motion: a wrong tile is back in its place at once (no float)", abs(got[0] - got[3]) < 2 and abs(got[1] - got[4]) < 2 and got[2] == "0s", str(got))
    await asyncio.sleep(1.5)
    s_tile = [c for c in await w_tiles(page) if c["text"] == "s"][0]
    got = await drop_now(s_tile, sx, sy)
    check("words reduce motion: the right tile is in its porthole at once (no slide)", abs(got[0] - sx) < 2 and abs(got[1] - sy) < 2, str(got))
    await asyncio.sleep(0.3)
    await w_place(t)
    await w_wait(page, ["words-built"], 3)
    await asyncio.sleep(0.8)
    got = await page.evaluate("(() => { const s = document.querySelector('#screen-words-build .words-ship'); return [s.classList.contains('is-launch'), getComputedStyle(s).transform, getComputedStyle(s.querySelector('.words-fire')).display]; })()")
    check("words reduce motion: the rocket's engines light but it doesn't tilt or move", got[0] and got[1] == "none" and got[2] != "none", str(got))
    for _ in range(80):
        if await page.evaluate("document.querySelector('#screen-words-build .words-ship').classList.contains('is-away')"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.7)
    got = await page.evaluate("(() => { const s = document.querySelector('#screen-words-build .words-ship'); return [getComputedStyle(s).transform, +getComputedStyle(s).opacity]; })()")
    check("words reduce motion: then it fades away instead of flying off", got[0] == "none" and got[1] < 0.05, str(got))
    await w_wait(page, ["words-done"], 15)
    await asyncio.sleep(0.2)
    got = await page.evaluate("Array.from(document.querySelectorAll('.words-end-rocket')).map(e => getComputedStyle(e).animationName)")
    check("words reduce motion: the end of the round's rockets fade in instead of rising", got == ["words-fade"], str(got))
    check("words reduce motion: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()



# ---------------------------------------------------------------- 0.6.0: MeeMee Rockets, the final build
async def screenshot(page, name):
    await page.screenshot(path=str(SHOTS / name))


async def w_sounds_said(t, n=0):
    return [x for x in (await t.said())[n:] if x.startswith("words-s-")]


async def w_pick(t, tile, dx=60, dy=-150):
    """Pick a tile up and let it go away from the rocket (it floats back to the tray): one pick-up."""
    await t.drag(tile["x"], tile["y"], tile["x"] + dx, tile["y"] + dy)


async def test_words_sounds(p):
    """Tile sounds: in sound tiles only, once per pick-up; the split pairs and misses; a sound not yet recorded."""
    print("\n== MeeMee Rockets: the tile sounds ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "words-sounds", 1280, 800, 1, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    lines = {c["id"]: c for c in json.loads((ROOT / "games" / "words" / "lines.json").read_text(encoding="utf-8"))["lines"]}
    used = sorted(await page.evaluate("MW.wordSteps.soundLines(MW.wordsGame.book)"))
    want = sorted({f"words-s-{x}" for v in W_SOUNDS.values() for x in v.split() if x != "-"})
    check("words-sounds: the words use the 42 tile sounds on the Lines tab, each a line in lines.json and recorded on the page",
          used == want and len(used) == 42 and all(x in lines and not lines[x].get("pending") for x in used)
          and await page.evaluate("(ids) => ids.every(id => MW.audio.recorded(id))", used), str(sorted(set(used) ^ set(want))))
    problems_file = await page.evaluate("MW.wordsGame.book.problems")
    check("words-sounds: every tricky tile says what it says in its word (the words file has no problems)", not problems_file, "; ".join(problems_file[:3]))
    # the words file is checked too: a tricky tile with no sound of its own, a tile with no sound, a sound for no tile
    bad = await page.evaluate("""(() => { const d = JSON.parse(JSON.stringify(MW.wordsData));
        delete d.words.said.sounds; delete d.words.took.sounds; d.words.toy.sounds = { x: 'oy' };
        return MW.wordSteps.read(d).problems; })()""")
    check("words-sounds: the words file's check lists a tricky tile with no sound of its own, an oo with no sound, a sound for no tile",
          len(bad) == 3 and "said" in bad[0] + bad[1] + bad[2] and any("took" in b for b in bad) and any("toy" in b for b in bad), str(bad))

    # misses in sound tiles: m i ss e s, the last s a plain s; once per pick-up, nothing as a tile snaps in
    await w_open(t, page, [{"word": "misses", "step": "tiles"}, {"word": "some", "step": "tiles"}, {"word": "like", "step": "tiles"},
                           {"word": "like", "step": "letters"}, {"word": "they", "step": "harder"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "misses"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_wait_said(t, "words-build words-w-misses")
    n = len(await t.said())
    s_tiles = [c for c in await w_tiles(page) if c["text"] == "s"]
    await w_pick(t, s_tiles[0])
    await asyncio.sleep(0.2)
    got = await w_sounds_said(t, n)
    check("words-sounds: picking up a tile in sound tiles says its sound (the last s of misses: a plain s)", got == ["words-s-s"], str(got))
    await w_pick(t, [c for c in await w_tiles(page) if c["text"] == "s"][0])
    await asyncio.sleep(0.2)
    check("words-sounds: ... once each time it is picked up", await w_sounds_said(t, n) == ["words-s-s", "words-s-s"], str(await w_sounds_said(t, n)))
    n = len(await t.said())
    await w_build(t)
    s = await w_wait(page, ["words-built"], 3)
    got = await w_sounds_said(t, n)
    check("words-sounds: building misses says m, i, s (ss), e, s: one sound a tile, none as it snaps in", got == ["words-s-" + x for x in "m i s e s".split()], str(got))

    # some: s [o] m [e]: o says the pair's sound, u; the e says nothing and stops nothing
    await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "some"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_wait_said(t, "words-build words-w-some")
    await asyncio.sleep(0.3)
    await page.evaluate("(() => { MW.audio.say([['words-build', 'words-w-some'], ['words-build', 'words-w-some']]).then(v => (window.__done = v)); return true; })()")
    await asyncio.sleep(0.3)
    n = len(await t.said())
    await w_pick(t, [c for c in await w_tiles(page) if c["text"] == "e"][0])
    await asyncio.sleep(0.2)
    still = await page.evaluate("[MW.audio.speaking(), window.__done === undefined, MW.events.filter(e => e.type === 'words').slice(-1)[0].detail]")
    check("words-sounds: in 'some' the e of the split pair says nothing, and stops nothing (the line carries on)",
          (await t.said())[n:] == [] and still[0] and still[1] and "none" in still[2], str([(await t.said())[n:], still]))
    await w_pick(t, [c for c in await w_tiles(page) if c["text"] == "o"][0])
    await asyncio.sleep(0.3)
    cut = await page.evaluate("window.__done")
    check("words-sounds: ... and the o says u, stopping the line being said", (await t.said())[n:] == ["words-s-u"] and cut is False, str([(await t.said())[n:], cut]))
    # a sound that isn't recorded yet does nothing and stops nothing
    await page.evaluate("(() => { window.__m = MW.audio.manifest.voice['words-s-m']; delete MW.audio.manifest.voice['words-s-m']; window.__done = undefined;"
                        "MW.audio.say([['words-build', 'words-w-some'], ['words-build', 'words-w-some']]).then(v => (window.__done = v)); return true; })()")
    await asyncio.sleep(0.3)
    n = len(await t.said())
    await w_pick(t, [c for c in await w_tiles(page) if c["text"] == "m"][0])
    await asyncio.sleep(0.2)
    still = await page.evaluate("[MW.audio.speaking(), window.__done === undefined, MW.events.filter(e => e.type === 'words').slice(-1)[0].detail]")
    check("words-sounds: a tile whose sound isn't recorded yet says nothing and stops nothing", (await t.said())[n:] == [] and still[0] and still[1]
          and "not recorded yet" in still[2], str([(await t.said())[n:], still]))
    await page.evaluate("MW.audio.hush(); MW.audio.manifest.voice['words-s-m'] = window.__m")
    await w_build(t)
    await w_wait(page, ["words-built"], 3)

    # like in sound tiles: l [i] k [e]: i says igh, the e nothing
    await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "like"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_wait_said(t, "words-build words-w-like")
    n = len(await t.said())
    await w_build(t)
    await w_wait(page, ["words-built"], 3)
    got = await w_sounds_said(t, n)
    check("words-sounds: building 'like' says l, igh, k and nothing for the e", got == ["words-s-l", "words-s-igh", "words-s-k"], str(got))
    await screenshot(page, "words-sounds-like-built.png")

    # letters and harder letters: no sounds
    for word, step in (("like", "letters"), ("they", "harder")):
        await w_wait(page, ["words-find"], 20)
        await asyncio.sleep(0.3)
        await t.tap([r for r in await w_rockets(page) if r["word"] == word][0]["x"], 450)
        s = await w_wait(page, ["words-build"])
        await w_wait_said(t, f"words-build words-w-{word}")
        n = len(await t.said())
        await w_pick(t, (await w_tiles(page))[0])
        await w_build(t)
        await w_wait(page, ["words-built", "words-done"], 3)
        check(f"words-sounds: no sounds in {s['mode']} ('{word}')", s["mode"] == step and await w_sounds_said(t, n) == [], str([s["mode"], await w_sounds_said(t, n)]))
    # what they would say in sound tiles: th (voiced) and ey says ai
    plan = await page.evaluate("MW.wordSteps.plan(MW.wordsGame.book, 'they', 'tiles').places.map(p => p.sound)")
    check("words-sounds: 'they' in sound tiles: th as in they, and ey says ai", plan == ["th-voiced", "ai"], str(plan))
    check("words-sounds: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_weeks(p):
    """Weeks 1–5, the week in play's share of a round, harder letters' fill, two slips, the new spares, old saved progress."""
    print("\n== MeeMee Rockets: weeks 1 to 5, rounds, slips and spares ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    E = lambda js, arg=None: page.evaluate(js, arg)
    book = await E("(() => { const b = MW.wordsGame.book; return { order: b.order, weeks: b.weeks, label: MW.wordSteps.allLabel(b) }; })()")
    allw = await E("MW.wordSteps.inPlay(MW.wordsGame.book, 'all')")
    week_of = {w: wk["week"] for wk in book["weeks"] for w in wk["tricky"] + wk["other"]}
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    secure = lambda w: days(3, "tiles", w) + days(3, "letters", w, 3) + days(3, "harder", w, 6)
    check("words-weeks: the all-weeks choice is named from the words file: 'Weeks 1–5'", book["label"] == "Weeks 1–5", str(book["label"]))
    code = "".join((ROOT / "games" / "words" / f).read_text(encoding="utf-8") for f in ("game.js", "steps.js", "moments.js"))
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)                  # the code without its comments
    found = re.findall(r".{0,20}(?:[Ww]eeks?\s*['\"]?\s*\d|\d\s*–\s*\d).{0,10}", code)
    check("words-weeks: no week number is written into the code (a new half-term needs no code change)", not found, str(found[:3]))
    await E("(() => { const g = MW.store.game('words'); g.week = 'all'; MW.store.save(); })()")
    got = await E("[MW.wordsGame.week(), MW.wordsGame.inPlay().length]")
    check("words-weeks: with Weeks 1–5 every word of weeks 1 to 5 is in play (60, once recorded)", got == ["all", 60] and len(allw) == 60, str(got))
    gone = await E("(() => { const v = MW.audio.manifest.voice['words-w-cobweb']; delete MW.audio.manifest.voice['words-w-cobweb']; const n = MW.wordsGame.inPlay(); "
                   "MW.audio.manifest.voice['words-w-cobweb'] = v; return [n.length, n.includes('cobweb')]; })()")
    check("words-weeks: ... a word not yet recorded stays out", gone == [59, False], str(gone))

    # Weeks 1–5 rounds: one or two secure words, then the lowest step first, at random within a step
    steps = {}
    answers = []
    for i, w in enumerate(allw):
        k = i % 6
        if k == 0:
            answers += secure(w); steps[w] = "secure"
        elif k == 1:
            answers += days(3, "tiles", w) + days(3, "letters", w, 3) + days(1, "harder", w, 6); steps[w] = "harder"
        elif k == 2:
            answers += days(3, "tiles", w) + days(1, "letters", w, 3); steps[w] = "letters"
        elif k in (3, 4):
            answers += days(1, "tiles", w); steps[w] = "tiles"
        else:
            steps[w] = "notyet"
    order = ["notyet", "tiles", "letters", "harder", "secure"]
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", answers)
    rounds = await E("(() => { const out = []; for (let i = 0; i < 600; i++) out.push(MW.wordsGame.makeRound()); return out; })()")
    nsec = {sum(1 for q in r if q["step"] == "secure") for r in rounds}
    work_steps = [[steps[q["word"]] for q in r if q["step"] != "secure"] for r in rounds]
    check("words-weeks: Weeks 1–5 rounds: five different words, one or two secure ones for review", all(len(r) == 5 and len({q["word"] for q in r}) == 5 for r in rounds)
          and nsec == {1, 2}, str(sorted(nsec)))
    check("words-weeks: ... then the words not yet asked first (10 not yet: every word that needs work is not yet)",
          all(set(ws) == {"notyet"} for ws in work_steps), str([ws for ws in work_steps if set(ws) != {"notyet"}][:3]))
    seen = {q["word"] for r in rounds for q in r if q["step"] != "secure"}
    check("words-weeks: ... at random among them (all 10 come up)", seen == {w for w in allw if steps[w] == "notyet"}, str(len(seen)))
    # with every word asked: sound tiles first, then letters, then harder letters
    asked = answers + [a for w in allw if steps[w] == "notyet" for a in days(1, "tiles", w)]
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", asked)
    rounds = await E("(() => { const out = []; for (let i = 0; i < 600; i++) out.push(MW.wordsGame.makeRound()); return out; })()")
    lowest_first = all(max(order.index(q["step"]) for q in r if q["step"] != "secure") <= order.index("tiles") for r in rounds)
    check("words-weeks: ... and once every word has been asked, the sound tiles words before letters and harder letters", lowest_first,
          str([[q["step"] for q in r] for r in rounds[:3]]))
    # only three words on sound tiles left (the rest on letters and harder letters): those three, then letters
    mix = await E("""(words) => { const S = MW.wordSteps, D = 86400000, T = %d, a = [];
        const day = (w, step, d) => a.push({ t: T + d * D, w: w, step: step, mode: step, tapped: 0, drops: 0, hint: false });
        words.forEach((w, i) => { if (i < 3) day(w, 'tiles', 0); else if (i < 6) { [0, 1, 2].forEach(d => day(w, 'tiles', d)); day(w, 'letters', 3); }
          else { [0, 1, 2].forEach(d => day(w, 'tiles', d)); [3, 4, 5].forEach(d => day(w, 'letters', d)); day(w, 'harder', 6); } });
        const out = []; for (let i = 0; i < 300; i++) out.push(S.pickRound({ words: words, answers: a, size: 5, lowest: true })); return out; }""" % T0,
        allw[:12])
    ok = all(sorted(q["step"] for q in r) == ["letters", "letters", "tiles", "tiles", "tiles"] for r in mix)
    check("words-weeks: ... three words on sound tiles and the rest further on: all three, then two on letters (none on harder letters)", ok,
          str([sorted(q["step"] for q in r) for r in mix[:3]]))

    # harder letters' fill with Weeks 1–5: the word's own week first, then any word in play
    fill = await E("""(() => { const G = MW.wordsGame, S = MW.wordSteps, b = G.book, out = [];
        S.inPlay(b, 'all').forEach(w => { for (let i = 0; i < 4; i++) {
          const p = S.plan(b, w, 'harder', S.fillFrom(b, 'all', w, G.inPlay()));
          const own = new Set(S.ownWords(b, b.words[w].week).filter(x => x !== w).join('').split(''));
          const base = new Set(b.words[w].letters.map(l => l.text).concat(b.words[w].spares));
          const avail = Array.from(own).filter(c => !base.has(c)).length;
          const extra = p.tray.slice().filter(t => t.spare && b.words[w].spares.indexOf(t.text) < 0).map(t => t.text);
          out.push({ w: w, n: p.tray.length, extra: extra, outside: extra.filter(c => !own.has(c)).length, avail: avail }); } });
        return out; })()""")
    bad = [f for f in fill if f["n"] != 10 or f["outside"] > max(0, len(f["extra"]) - f["avail"])]
    check("words-weeks: harder letters with Weeks 1–5 fill the tray to 10 from the word's own week first (every word, 4 times)",
          not bad and len(fill) == 240, json.dumps(bad[:3]))
    thin = await E("""(() => { const S = MW.wordSteps, b = S.read({ harderTray: 10, weeks: [{ week: 1, tricky: ['a'], other: [] }, { week: 2, tricky: ['bc'], other: [] }],
        words: { a: { tiles: 'a', sounds: {}, spares: 'z' }, bc: { tiles: 'b c', spares: 'y' } }, sounds: { a: 'a', b: 'b', c: 'k' } });
        const p = S.plan(b, 'a', 'harder', S.fillFrom(b, 'all', 'a', ['a', 'bc'])); return p.tray.map(t => t.text).sort(); })()""")
    check("words-weeks: ... then from any word in play when its week runs out of letters", thin == ["a", "b", "c", "z"], str(thin))
    first = await E("""(() => { const S = MW.wordSteps, out = { one: new Set(), all: new Set() };
        const b = S.read({ harderTray: 4, weeks: [{ week: 1, tricky: ['xy'], other: [] }, { week: 2, tricky: ['ab'], other: ['ac'] }],
          words: { xy: { tiles: 'x y', spares: 'q' }, ab: { tiles: 'a b', spares: 'z' }, ac: { tiles: 'a c', spares: 'q' } }, sounds: { a: 'a', b: 'b', c: 'k', x: 'k', y: 'y' } });
        for (let i = 0; i < 60; i++) {
          out.one.add(S.plan(b, 'ab', 'harder', S.fillFrom(b, 2, 'ab', ['ab', 'ac', 'xy'])).tray.map(t => t.text).sort().join(''));
          out.all.add(S.plan(b, 'ab', 'harder', S.fillFrom(b, 'all', 'ab', ['ab', 'ac', 'xy'])).tray.map(t => t.text).sort().join(''));
        }
        return [Array.from(out.one), Array.from(out.all)]; })()""")
    check("words-weeks: the one extra letter always comes from the word's own week (c, from 'ac'), never another week in play (x, y), with one week or all",
          first == [["abcz"], ["abcz"]], str(first))

    # one week in play: at least 3 of 5 from that week's own words
    await E("(() => { const g = MW.store.game('words'); g.week = 5; MW.store.save(); })()")
    own5 = set(await E("MW.wordSteps.ownWords(MW.wordsGame.book, 5)"))
    for label, ans in (("no answers", []), ("its words mostly secure", [a for w in list(own5)[:10] for a in secure(w)]),
                       ("every one of its words secure", [a for w in own5 for a in secure(w)])):
        await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", ans)
        rounds = await E("(() => { const out = []; for (let i = 0; i < 800; i++) out.push(MW.wordsGame.makeRound()); return out; })()")
        counts = [sum(1 for q in r if q["word"] in own5) for r in rounds]
        check(f"words-weeks: week 5 in play ({label}): at least 3 of every round's 5 words are week 5's own",
              min(counts) >= 3 and all(len(r) == 5 for r in rounds), str(sorted(set(counts))))
    others = {q["word"] for r in rounds for q in r} - own5
    check("words-weeks: ... and earlier weeks' tricky words still come up", len(others) >= 10, str(len(others)))
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", [])
    two = await E("""(() => { const keep = {}; const ids = ['all', 'of', 'one', 'here', 'magnet', 'cartoon', 'rabbit', 'spray', 'popcorn', 'proud'];
        ids.forEach(w => { keep[w] = MW.audio.manifest.voice['words-w-' + w]; delete MW.audio.manifest.voice['words-w-' + w]; });
        const out = []; for (let i = 0; i < 200; i++) out.push(MW.wordsGame.makeRound().map(q => q.word));
        ids.forEach(w => { MW.audio.manifest.voice['words-w-' + w] = keep[w]; }); return out; })()""")
    check("words-weeks: a week with only two of its words in play (the rest not recorded yet) puts both in every round",
          all("toy" in r and "say" in r and len(r) == 5 for r in two), str(two[:2]))

    # two slips in a row take a secure word back to harder letters; a right answer in between clears the first
    status = "(a) => { const m = MW.wordSteps.statuses(a.answers); return [MW.wordSteps.step(m, a.w), (m[a.w] || {days: []}).days.length]; }"
    sec = secure("of")
    slip = lambda d, step="secure": w_ans(T0 + d * DAY, "of", step, first=False)
    right = lambda d, step="secure": w_ans(T0 + d * DAY, "of", step)
    cases = [
        ("one slip: still secure", sec + [slip(10)], ["secure", 0]),
        ("two slips in a row: back to harder letters", sec + [slip(10), slip(11)], ["harder", 0]),
        ("two slips on the same day count too", sec + [slip(10), w_ans(T0 + 10 * DAY + 60000, "of", "secure", first=False)], ["harder", 0]),
        ("a slip, a right answer, a slip: still secure (the right answer cleared the first)", sec + [slip(10), right(11), slip(12)], ["secure", 0]),
        ("a hint is a slip", sec + [slip(10), w_ans(T0 + 11 * DAY, "of", "secure", hint=True)], ["harder", 0]),
        ("back in harder letters: two days right first time is not yet secure again", sec + [slip(10), slip(11), right(12, "harder"), right(13, "harder")], ["harder", 2]),
        ("... three more days right first time: secure again", sec + [slip(10), slip(11)] + [right(d, "harder") for d in (12, 13, 14)], ["secure", 0]),
        ("... and a wrong try there restarts its days", sec + [slip(10), slip(11), right(12, "harder"), slip(13, "harder")], ["harder", 0]),
    ]
    for label, ans, want in cases:
        got = await E(status, {"answers": ans, "w": "of"})
        check(f"words-weeks: {label}", got == want, str(got))
    # the tablet keeps the last 3,000 answers: a trim that falls between a secure word's two slips loses the first slip, but
    # the answers saved after it (at harder letters) still say where the word is
    filler = [w_ans(T0 + 10 * DAY + 3600000 + i * 1000, "my") for i in range(2997)]
    full = sec + [slip(10)] + filler + [slip(11), right(12, "harder"), right(13, "harder")]
    kept = full[-3000:]
    between = slip(10) not in kept and slip(11) in kept
    got = [await E(status, {"answers": full, "w": "of"}), await E(status, {"answers": kept, "w": "of"}),
           await E(status, {"answers": kept + [right(14, "harder")], "w": "of"})]
    check("words-weeks: trimmed to 3,000 between its two slips, a word back in harder letters stays there (two days), then secure on a third",
          between and got == [["harder", 2], ["harder", 2], ["secure", 0]], str([between, got]))
    # in the game: a secure word slipped twice comes back in harder letters
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", sec + [slip(10), slip(11)])
    r = await E("MW.wordsGame.nextRound = ['of'], MW.wordsGame.makeRound()")
    check("words-weeks: ... and the next round builds it in harder letters as a word that needs work", r == [{"word": "of", "step": "harder"}], str(r))
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", [])

    # the new spares (answer 11): c for she, n for me; you keeps o, which is just as good as its own o
    spares = await E("['she', 'me', 'you'].map(w => MW.wordsGame.book.words[w].spares.join(' '))")
    check("words-weeks: the spares: c for 'she', n for 'me', o for 'you'", spares == ["c", "n", "o"], str(spares))
    tray = await E("""(() => { const G = MW.wordsGame; MW.world.st.phase = 'map'; const out = {};
        ['she', 'me'].forEach(w => { G.showBuild({ word: w, step: 'letters' }); out[w] = G.st.tiles.map(c => c.text + (c.spare ? '*' : '')).sort(); MW.world.home(); });
        G.showBuild({ word: 'you', step: 'letters' });
        const st = G.st, sl = i => [150 + st.ship.slots[i].x * st.ship.scale, 195 + st.ship.slots[i].y * st.ship.scale];
        G.drop(st.tiles.find(c => c.text === 'y'), ...sl(0), false);
        G.drop(st.tiles.find(c => c.spare), ...sl(1), false);
        out.you = [st.next, st.drops]; MW.world.home(); return out; })()""")
    check("words-weeks: letters trays: s h e with c; m e with n", tray.get("she") == ["c*", "e", "h", "s"] and tray.get("me") == ["e", "m", "n*"], json.dumps(tray))
    check("words-weeks: in 'you' the spare o goes in the o's place, just as good (not a wrong drop)", tray.get("you") == [2, 0], json.dumps(tray))

    # progress saved by the test build (week 5, its answers) carries on
    await ctx.close()
    now = T0 + 40 * DAY
    old = {"week": 5, "answers": [w_ans(T0 + d * DAY, "of") for d in range(3)] + [w_ans(T0, "magnet", first=False)]}
    ctx, page, problems2 = await seeded(browser, [])
    await page.evaluate("(g) => { const s = JSON.parse(localStorage.getItem('mimi-world')); s.games = { words: g }; localStorage.setItem('mimi-world', JSON.stringify(s)); }", old)
    await page.reload()
    await page.wait_for_load_state("load")
    kept = await page.evaluate("""(() => { const m = MW.wordSteps.statuses(MW.wordsGame.answers());
        return [MW.wordsGame.week(), MW.wordsGame.inPlay().length, m.of.step, m.magnet.step, MW.wordsGame.makeRound().length]; })()""")
    check("words-weeks: progress saved by the test build (week 5) carries on: week 5 in play, each word's step kept", kept == [5, 28, "letters", "tiles", 5], str(kept))
    check("words-weeks: no console errors", not problems and not problems2, "; ".join((problems + problems2)[:3]))
    await browser.close()


LAMP_INFO = """(() => { const st = MW.wordsGame.st, L = MW.wordsGame.LAMPS;
    return { L: st.ship.L, launch: st.ship.el.classList.contains('is-launch'),
      lamps: st.lamps.map(l => { const on = l.el.querySelector('.words-lamp-on'), cs = getComputedStyle(on), disc = l.el.querySelector('.words-lamp-off circle');
        return { x: l.x, y: l.y, g: l.group, inShip: !!l.el.closest('.words-ship'), opacity: +cs.opacity, name: cs.animationName, dur: cs.animationDuration,
                 count: cs.animationIterationCount, delay: cs.animationDelay, r: +disc.getAttribute('r'), sw: +disc.getAttribute('stroke-width'),
                 size: +l.el.getAttribute('width') }; }) }; })()"""


async def test_words_lights(p, name, vw, vh, dpr):
    """The launch lights: where they are, off until the last tile lands, then the chase; they go with the rocket."""
    print(f"\n== MeeMee Rockets: the launch lights ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"words-lights-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await w_open(t, page, [{"word": "farmyard", "step": "tiles"}, {"word": "cartoon", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "farmyard"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    info = await page.evaluate(LAMP_INFO)
    L = info["L"]
    want = []
    for x0, y in ((44, 168), (90, 15)):
        x = x0
        while x < L - 25:
            want.append((x, y))
            x += 92
    want.sort()
    got = [(l["x"], l["y"]) for l in info["lamps"]]
    check(f"words-lights ({name}): lights along the stripe (y 168) and the top edge (y 15), 92 apart, the rows half a step apart ({len(got)} on 'farmyard')",
          got == want and len(got) >= 12, str(got))
    check(f"words-lights ({name}): numbered from the back to the nose in three groups in turn", [l["g"] for l in info["lamps"]] == [i % 3 for i in range(len(got))])
    check(f"words-lights ({name}): small: 22 px lights with a 3 px ink edge (glow included, 46 px)", all(l["r"] * 2 + l["sw"] == 22 and l["size"] == 46 for l in info["lamps"]))
    check(f"words-lights ({name}): off while the word is built", not info["launch"] and all(l["opacity"] == 0 and l["name"] == "none" for l in info["lamps"]),
          str([(l["opacity"], l["name"]) for l in info["lamps"][:3]]))
    await w_build(t)
    await w_wait(page, ["words-built"], 3)
    for _ in range(30):
        info = await page.evaluate(LAMP_INFO)
        if info["launch"]:
            break
        await asyncio.sleep(0.05)
    lamps = info["lamps"]
    check(f"words-lights ({name}): they light with the engines when the last tile lands", info["launch"] and all(l["name"] == "words-lamp" for l in lamps), str(lamps[:1]))
    check(f"words-lights ({name}): each blinks once a second, over and over, its group starting 0, 1/3 or 2/3 of a second in",
          all(l["dur"] == "1s" and l["count"] == "infinite" and l["delay"] == ["0s", "0.333s", "0.667s"][l["g"]] for l in lamps),
          str(sorted({(l["g"], l["dur"], l["count"], l["delay"]) for l in lamps})))
    # the timing itself: hold each group's animation at moments through its cycle
    samples = await page.evaluate("""(() => { const st = MW.wordsGame.st, out = {};
        [0, 1, 2].forEach(g => { const l = st.lamps.find(x => x.group === g), on = l.el.querySelector('.words-lamp-on');
          const a = on.getAnimations()[0]; a.pause(); const d = [0, 333, 667][g];
          out[g] = [-150, 30, 300, 360, 660, 980, 1030, 1300, 1400].map(ms => { a.currentTime = d + ms; return +getComputedStyle(on).opacity; }); a.play(); });
        return out; })()""")
    ok = all(samples[str(g)][1:] == [1, 1, 0, 0, 0, 1, 1, 0] for g in range(3)) and samples["1"][0] == 0 and samples["2"][0] == 0
    check(f"words-lights ({name}): each light is on for the first third of its second and off for the other two thirds; a group is off until its start",
          ok, json.dumps(samples))
    await asyncio.sleep(0.5)
    await screenshot(page, f"{name}-words-lights-chase.png")
    check(f"words-lights ({name}): the lights are on the rocket, so they go with it", all(l["inShip"] for l in lamps))
    where = """(() => { const s = document.querySelector('#screen-words-build .words-ship'), k = MW.stage.scale, sb = s.getBoundingClientRect();
        return { away: s.classList.contains('is-away'), ship: [sb.left / k, sb.top / k],
                 lamps: MW.wordsGame.st.lamps.map(l => { const b = l.el.getBoundingClientRect(); return [(b.left - sb.left) / k, (b.top - sb.top) / k]; }) }; })()"""
    for _ in range(80):
        if (await page.evaluate(where))["away"]:
            break
        await asyncio.sleep(0.05)
    before = await page.evaluate(where)
    await asyncio.sleep(0.9)
    after = await page.evaluate(where)
    moved = after["ship"][0] - before["ship"][0], before["ship"][1] - after["ship"][1]
    same = all(abs(a[0] - b[0]) < 1 and abs(a[1] - b[1]) < 1 for a, b in zip(before["lamps"], after["lamps"]))
    check(f"words-lights ({name}): ... flying away with it to the top right", same and moved[0] > 300 and moved[1] > 150, str([moved, same]))
    await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "cartoon"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    left = await page.evaluate("[document.querySelectorAll('.words-ship').length, MW.wordsGame.st.lamps.every(l => getComputedStyle(l.el.querySelector('.words-lamp-on')).opacity === '0')]")
    check(f"words-lights ({name}): the next word's rocket has its own lights, off until it launches (the last rocket's have gone with it)", left == [1, True], str(left))
    check(f"words-lights ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def stage_rect(page, sel):
    """Stage boxes [x, y, w, h] of every svg or element matched (what is drawn)."""
    return await page.evaluate("""(sel => Array.from(document.querySelectorAll(sel)).map(e => { const r = e.getBoundingClientRect(), s = MW.stage.scale;
        return [(r.left - MW.stage.offX) / s, (r.top - MW.stage.offY) / s, r.width / s, r.height / s]; }))(%s)""" % json.dumps(sel))


def overlap(a, b, pad=0):
    return a[0] < b[0] + b[2] - pad and b[0] < a[0] + a[2] - pad and a[1] < b[1] + b[3] - pad and b[1] < a[1] + a[3] - pad


async def test_words_moments(p, name, vw, vh, dpr):
    """The crew's moments in MeeMee Rockets (round 7, as drawn): only for a job a cat has, never over the word."""
    print(f"\n== MeeMee Rockets: the crew's moments ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"words-moments-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    round_ = [{"word": "feel", "step": "tiles"}, {"word": "chain", "step": "harder"}]
    await w_open(t, page, round_)
    look = await page.evaluate("(() => { const b = document.querySelector('#screen-words-find [data-moment=lookout]'); return b ? [b.classList.contains('is-shown'), b.querySelector('.mw-cat').dataset.who, b.querySelector('.mw-cat').dataset.job] : null; })()")
    check(f"words-moments ({name}): the lookout peeks up in Find as the round starts (Moggles, wearing the lookout badge)", look == [True, "moggles", "lookout"], str(look))
    await asyncio.sleep(0.6)
    lb = await moment_box(page, "#screen-words-find [data-moment=lookout]")
    panels = await stage_rect(page, "#screen-words-find .words-panel")
    pod = (await stage_rect(page, "#screen-words-find .mw-pod"))[0]
    check(f"words-moments ({name}): ... from the bottom right (cat at x 1000, 210 wide, its top at 640, with the telescope)", lb and lb[0] > 960 and lb[1] >= 639 and lb[0] + lb[2] < 1260
          and await page.evaluate("!!document.querySelector('[data-moment=lookout] .words-moment-held svg')"), str(lb))
    check(f"words-moments ({name}): ... never over a word, nor Scruffles's ship", lb and not any(overlap(lb, pnl) for pnl in panels) and not overlap(lb, pod), str([lb, pod]))
    await screenshot(page, f"{name}-words-moment-lookout.png")
    await w_wait_said(t, "words-find words-w-feel")
    await asyncio.sleep(2.4)
    check(f"words-moments ({name}): the lookout ducks down once the first word is asked", not await page.evaluate("!!document.querySelector('[data-moment=lookout]')"))
    rk = [r for r in await w_rockets(page) if r["word"] == "feel"][0]
    await t.tap(rk["x"], 450)
    await asyncio.sleep(0.9)
    eb = await moment_box(page, "#screen-words-find [data-moment=engineer]")
    sp = await moment_box(page, "#screen-words-find [data-moment=engineer-spanner]")
    tapping = await page.evaluate("(() => { const s = document.querySelector('[data-moment=engineer-spanner] .words-spanner-swing'); return s ? [s.classList.contains('is-tapping'), getComputedStyle(s).animationName] : null; })()")
    check(f"words-moments ({name}): a right tap: the engineer pops up under the launch pad below that rocket", eb and abs(eb[0] + eb[2] / 2 - rk["x"]) < 12 and eb[1] >= 675, str([eb, rk["x"]]))
    check(f"words-moments ({name}): ... and taps its clamp with the spanner (beside the rocket's foot)", sp and tapping and tapping[0] and tapping[1] == "words-spanner-tap"
          and sp[1] < 693 < sp[1] + sp[3] + 20 and rk["x"] < sp[0] + sp[2] / 2 < rk["x"] + 140, str([sp, tapping]))
    check(f"words-moments ({name}): ... never over a word", not any(overlap(b, pnl) for b in (eb, sp) for pnl in panels), str([eb, sp]))
    await screenshot(page, f"{name}-words-moment-engineer.png")
    # the navigator and the cook
    await page.evaluate("MW.crew.save({moggles: 'navigator', snuffles: 'cook'})")
    await w_wait(page, ["words-build"])
    await w_build(t)
    for _ in range(80):
        if await page.evaluate("!!document.querySelector('#screen-words-build [data-moment=navigator].is-shown')"):
            break
        await asyncio.sleep(0.05)
    stars = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-build .mw-stars svg')).map(s => s.dataset.state).join(',')")
    await asyncio.sleep(0.45)
    nb = await moment_box(page, "#screen-words-build [data-moment=navigator]")
    mb = await moment_box(page, "#screen-words-build [data-moment=navigator-map]")
    route = await page.evaluate("(() => { const r = document.querySelector('#screen-words-build [data-moment=navigator-route] path'); return r ? r.getAttribute('d') : null; })()")
    star = (await stage_rect(page, "#screen-words-build .mw-stars svg"))[1]
    word = await stage_rect(page, "#screen-words-build .words-ship .words-tile")
    behind = await page.evaluate("""(() => { const r = document.querySelector('[data-moment=navigator-route]').closest('.mw-moments'), ship = document.querySelector('#screen-words-build .words-ship').parentNode;
        const kids = Array.from(r.parentNode.children); return kids.indexOf(r) < kids.indexOf(ship); })()""")
    check(f"words-moments ({name}): the navigator holds up the star map on the cargo tray as the star lights", stars == "done,current" and nb and mb and nb[1] >= 469 and mb[1] < nb[1], str([stars, nb, mb]))
    end = [float(x) for x in route.split()[-2:]] if route else None
    check(f"words-moments ({name}): ... with a dotted route to the next star", route and "NaN" not in route and abs(end[0] - (star[0] + star[2] / 2)) < 2 and 0 < end[1] - (star[1] + star[3]) < 40,
          str([route, star]))
    check(f"words-moments ({name}): ... never over the word: the cat and map clear of the rocket's portholes, the route behind the rocket",
          word and not any(overlap(b, w) for b in (nb, mb) for w in word) and behind, str([nb, mb, word[:2], behind]))
    await screenshot(page, f"{name}-words-moment-navigator.png")
    await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    check(f"words-moments ({name}): the navigator has gone when the next word is asked", not await page.evaluate("!!document.querySelector('#screen-words-build [data-moment=navigator].is-shown')"))
    await t.tap([r for r in await w_rockets(page) if r["word"] == "chain"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    for _ in range(80):
        if await page.evaluate("!!document.querySelector('#screen-words-end [data-moment=cook-pan].is-shown')"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.6)
    cb = await moment_box(page, "#screen-words-end [data-moment=cook]")
    pb = await moment_box(page, "#screen-words-end [data-moment=cook-pan]")
    again = (await stage_rect(page, "#words-again"))[0]
    who = await page.evaluate("document.querySelector('#screen-words-end [data-moment=cook] .mw-cat').dataset.job")
    check(f"words-moments ({name}): on the end screen the cook brings a pan of fish for the MeeMee in the little rockets",
          cb and pb and who == "cook" and pb[0] < cb[0] and 600 < pb[1] < 700, str([cb, pb, who]))
    check(f"words-moments ({name}): ... clear of the Play button", not overlap(cb, again) and not overlap(pb, again), str([cb, again]))
    await screenshot(page, f"{name}-words-moment-cook.png")
    await w_wait_said(t, "words-round-another", 15)
    said = await t.said()
    check(f"words-moments ({name}): the moments have no words", not any("job-" in x or "name-" in x for x in said), str(said[-4:]))
    await t.tap(*HOME)
    await asyncio.sleep(0.4)
    check(f"words-moments ({name}): Home clears them", await page.evaluate("document.querySelectorAll('[data-moment]').length") == 0)
    # nobody has a job: no moments
    await page.evaluate("MW.crew.save({moggles: null, snuffles: null})")
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await w_open(t, page, [{"word": "toy", "step": "tiles"}])
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "toy"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    await asyncio.sleep(2.5)
    check(f"words-moments ({name}): no jobs, no moments", await page.evaluate("MW.events.filter(e => e.type === 'moment').length") == n0
          and await page.evaluate("document.querySelectorAll('[data-moment]').length") == 0)
    await t.tap(*HOME)
    await asyncio.sleep(0.4)
    # only the jobs a cat has: the engineer alone, and a quick first tap (the lookout has no cat)
    await page.evaluate("MW.crew.save({moggles: 'engineer', snuffles: null})")
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await w_open(t, page, [{"word": "say", "step": "tiles"}])
    await t.tap([r for r in await w_rockets(page) if r["word"] == "say"][0]["x"], 450)
    await asyncio.sleep(0.6)
    kinds = await page.evaluate("MW.events.filter(e => e.type === 'moment').slice(%d).map(e => e.detail.split(' ')[0])" % n0)
    check(f"words-moments ({name}): only the jobs a cat has (the engineer alone: no lookout)", kinds == ["engineer"], str(kinds))
    # a pause before the lookout has ducked: it ducks as it would have once the question is asked again
    await t.tap(*HOME)
    await asyncio.sleep(0.6)
    hide = "Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    show = "Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    up = "!!document.querySelector('#screen-words-find [data-moment=lookout].is-shown')"
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: null})")
    n = len(await t.said())
    await w_open(t, page, [{"word": "feel", "step": "tiles"}])
    await w_wait_said(t, "words-find words-w-feel", after=n)
    await page.evaluate(hide)
    await asyncio.sleep(2.5)
    paused = await page.evaluate(up)
    n = len(await t.said())
    await page.evaluate(show)
    await asyncio.sleep(0.6)
    back = [await page.evaluate(up), (await t.said())[n:][:1]]
    await asyncio.sleep(2.2)
    gone = not await page.evaluate("!!document.querySelector('[data-moment=lookout]')")
    check(f"words-moments ({name}): paused before the lookout ducks: it waits, then ducks once the question is asked again",
          paused and back == [True, ["words-find words-w-feel"]] and gone, str([paused, back, gone]))
    check(f"words-moments ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_moments_motion(p):
    """With reduce motion the cats fade in and out, the spanner doesn't swing, and the launch lights are lit and steady."""
    print("\n== MeeMee Rockets: moments and lights with reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": 1046, "height": 653}, device_scale_factor=1.22, has_touch=True, is_mobile=True, reduced_motion="reduce")
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    t = Tablet(page, await ctx.new_cdp_session(page))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    await w_open(t, page, [{"word": "cartoon", "step": "tiles"}])
    await asyncio.sleep(0.5)
    got = await page.evaluate("(() => { const i = document.querySelector('[data-moment=lookout] .mw-peek-inner'); const cs = getComputedStyle(i); return [cs.transform, cs.transitionProperty, +cs.opacity]; })()")
    check("words-moments reduce motion: the lookout fades in without rising", got[0] == "none" and "opacity" in got[1] and got[2] > 0.9, str(got))
    await t.tap([r for r in await w_rockets(page) if r["word"] == "cartoon"][0]["x"], 450)
    await asyncio.sleep(0.9)
    got = await page.evaluate("""(() => { const e = document.querySelector('[data-moment=engineer] .mw-peek-inner'), s = document.querySelector('[data-moment=engineer-spanner] .words-spanner-swing');
        return [getComputedStyle(e).transform, getComputedStyle(s).animationName, getComputedStyle(document.querySelector('[data-moment=engineer-spanner]')).transform]; })()""")
    check("words-moments reduce motion: the engineer fades in, and the spanner doesn't swing", got == ["none", "none", "none"], str(got))
    await w_wait(page, ["words-build"])
    await w_build(t)
    await w_wait(page, ["words-built"], 3)
    await asyncio.sleep(0.6)
    info = await page.evaluate(LAMP_INFO)
    check("words-moments reduce motion: every launch light is lit and steady", info["launch"] and all(l["opacity"] == 1 and l["name"] == "none" for l in info["lamps"]),
          str([(l["opacity"], l["name"]) for l in info["lamps"][:3]]))
    await screenshot(page, "fire-words-lights-reduce-motion.png")
    check("words-moments reduce motion: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_allweeks_tab(p):
    """The Words tab with Weeks 1–5 on (board Grownups8Words), at both sizes."""
    print("\n== MeeMee Rockets: the Words tab with Weeks 1–5 ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    words = (days(3, "tiles", "go") + days(3, "letters", "go", 3) + days(3, "harder", "go", 6) + days(3, "tiles", "my") + days(3, "letters", "my", 3) + days(3, "harder", "my", 6)
             + days(1, "tiles", "into") + days(3, "tiles", "out") + days(1, "letters", "out", 3) + days(1, "tiles", "feel") + days(1, "tiles", "food"))
    for name, vw, vh in (("fire", 1046, 653), ("doogee", 1280, 800)):
        ctx = await browser.new_context(viewport={"width": vw, "height": vh}, has_touch=True, is_mobile=True)
        saved = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True}, "answers": [], "games": {"words": {"week": 5, "answers": words}}}
        await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                                  % json.dumps(json.dumps(saved)))
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        t = Tablet(page, await ctx.new_cdp_session(page))
        await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('words-progress')")
        await asyncio.sleep(0.3)
        box = await page.evaluate("""(() => { const b = document.querySelector('.words-week-all');
            const r = b.getBoundingClientRect(); return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale]; })()""")
        await t.tap(*box)
        await asyncio.sleep(0.4)
        got = await page.evaluate("""[MW.wordsGame.week(), MW.wordsGame.inPlay().length, Array.from(document.querySelectorAll('.words-week')).map(b => b.textContent + (b.classList.contains('is-on') ? '*' : '')),
            Array.from(document.querySelectorAll('.words-grid-label')).map(e => e.textContent),
            Array.from(document.querySelectorAll('.words-grid .words-cell')).map(c => c.lastChild.textContent),
            Object.fromEntries(Array.from(document.querySelectorAll('.words-grid .words-cell')).map(c => [c.lastChild.textContent, c.className.split(' ').find(x => x.startsWith('is-'))])),
            Array.from(document.querySelectorAll('.gu-body .gu-note')).map(p => p.textContent)]""")
        tricky = [w for wk in range(1, 6) for w in await page.evaluate("(n) => MW.wordsGame.book.weeks[n - 1].tricky", wk)]
        other = [w for wk in range(1, 6) for w in await page.evaluate("(n) => MW.wordsGame.book.weeks[n - 1].other", wk)]
        check(f"words-alltab ({name}): tapping Weeks 1–5 puts every week in play (saved on the tablet)", got[0] == "all" and got[1] == 60
              and got[2] == ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Weeks 1–5*"], json.dumps(got[:3]))
        check(f"words-alltab ({name}): the grid shows every tricky word, then every other word (60)", got[3] == ["Tricky words", "Other words"] and got[4] == tricky + other, str(got[3]))
        want = {"go": "is-secure", "my": "is-secure", "into": "is-tiles", "out": "is-letters", "feel": "is-tiles", "here": "is-notyet", "treat": "is-notyet"}
        check(f"words-alltab ({name}): each word shows its step", all(got[5].get(w) == s for w, s in want.items()), str({w: got[5].get(w) for w in want}))
        notes = " ".join(got[6])
        check(f"words-alltab ({name}): the note says Weeks 1–5 plays every word from all five weeks, leaning on the ones that need the most work, from the next round",
              "Weeks 1–5 plays every word from all five weeks, leaning on the ones that need the most work. A change starts with the next round." in notes, notes[:200])
        check(f"words-alltab ({name}): the grown-ups note says how a secure word goes back", "two slips in a row" in notes and "clears the first slip" in notes, notes[-400:])
        wide = await page.evaluate("(() => { const g = document.querySelector('.words-grid'); const b = g.closest('.gu-body'); return [g.scrollWidth, b.clientWidth]; })()")
        check(f"words-alltab ({name}): the grid fits without sideways scrolling", wide[0] <= wide[1], str(wide))
        await screenshot(page, f"{name}-words-grownups-weeks-1-5.png")
        rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 200; i++) MW.wordsGame.makeRound().forEach(q => out.add(q.word)); return Array.from(out); })()")
        check(f"words-alltab ({name}): rounds then come from every week", {week for week in [1, 2, 3, 4, 5] if any(w in rounds for w in await page.evaluate("(n) => MW.wordSteps.ownWords(MW.wordsGame.book, n)", week))} == {1, 2, 3, 4, 5},
              str(len(rounds)))
        await page.evaluate("MW.grownups.close()")
        await page.reload()
        await page.wait_for_load_state("load")
        check(f"words-alltab ({name}): Weeks 1–5 is remembered on the tablet", await page.evaluate("MW.wordsGame.week()") == "all")
        check(f"words-alltab ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_words_newwords(p, name, vw, vh, dpr):
    """A weeks 1–4 word played in Find and Build at both sizes (sound tiles, then harder letters), as the child would."""
    print(f"\n== MeeMee Rockets: weeks 1 to 4's words ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"words-new-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate("(() => { const g = MW.store.game('words'); g.week = 'all'; MW.store.save(); })()")
    await w_open(t, page, [{"word": "farmyard", "step": "tiles"}, {"word": "cobweb", "step": "harder"}])
    await w_wait_said(t, "words-find words-w-farmyard")
    rockets = await w_rockets(page)
    text = (await page.inner_text("#screen-words-find")).split()
    check(f"words-new ({name}): Find asks 'Find the word… farmyard.' among three rockets, nothing else to read", "farmyard" in [r["word"] for r in rockets]
          and sorted(text) == sorted(r["word"] for r in rockets), str(text))
    fit = await page.evaluate("MW.wordsGame.st.rockets.map(r => r.wordEl.getBoundingClientRect().width / MW.stage.scale <= r.wordEl.parentNode.getBoundingClientRect().width / MW.stage.scale - 27.5)")
    check(f"words-new ({name}): every word fits its plate", all(fit), str(fit))
    await screenshot(page, f"{name}-words-new-find.png")
    await t.tap([r for r in rockets if r["word"] == "farmyard"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    await asyncio.sleep(0.4)
    tiles = await w_tiles(page)
    check(f"words-new ({name}): Build 'farmyard' from sound tiles f ar m y ar d (six tiles: two rows of three)", s["mode"] == "tiles"
          and s["places"] == ["f", "ar", "m", "y", "ar", "d"] and len({round(c["y"]) for c in tiles}) == 2, json.dumps(s))
    ship = (await stage_rect(page, "#screen-words-build .words-ship"))[0]
    check(f"words-new ({name}): its rocket fits on the stage, clear of Hear-again", ship[0] + ship[2] <= 1252, str(ship))
    await screenshot(page, f"{name}-words-new-build-tiles.png")
    await w_build(t)
    await w_wait(page, ["words-built"], 3)
    await w_wait(page, ["words-find"], 20)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "cobweb"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    await asyncio.sleep(0.4)
    tiles = await w_tiles(page)
    own2 = set("".join(await page.evaluate("MW.wordSteps.ownWords(MW.wordsGame.book, 2)")))
    extra = [c["text"] for c in tiles if c["spare"] and c["text"] != "d"]
    check(f"words-new ({name}): Build 'cobweb' in harder letters: 10 tiles in two rows, its spare d and letters from week 2's words",
          s["mode"] == "harder" and len(tiles) == 10 and len({round(c["y"]) for c in tiles}) == 2 and set(extra) <= own2, str([c["text"] for c in tiles]))
    await screenshot(page, f"{name}-words-new-build-harder.png")
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    check(f"words-new ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# ---------------------------------------------------------------- 0.6.0: the kit (title banners, the five test-build gaps, numbers mode's pieces)
HOME_BTN = (66, 62)
BANNER_INFO = """(() => { const b = document.getElementById('banner'), p = b.querySelector('.mw-banner-plaque'), n = p.querySelector('.mw-banner-name');
    return { up: MW.world.banner.up(), name: n ? n.textContent : null, art: Array.from(p.querySelectorAll('[data-art]')).map(e => e.dataset.art),
             phase: MW.world.st.phase, screen: MW.shell.screen }; })()"""


async def banner_times(page, name):
    """When a banner went up, started to go and had gone (MW.events ms), the line said with it and how long that is."""
    return await page.evaluate("""(n => { const ev = MW.events, at = (type, d) => { const e = ev.filter(e => e.type === type && e.detail === d).slice(-1)[0]; return e ? e.t : null; };
        return { up: at('banner', 'up ' + n), going: at('banner', 'going ' + n), gone: at('banner', 'gone ' + n) }; })(%s)""" % json.dumps(name))


async def said_at(page, line):
    return await page.evaluate("(l => { const e = MW.events.filter(e => e.type === 'say' && e.detail === l).slice(-1)[0]; return e ? [e.t, MW.audio.lengthOf([[l]])] : null; })(%s)" % json.dumps(line))


async def wait_gone(page, name, timeout=10):
    for _ in range(int(timeout / 0.1)):
        times = await banner_times(page, name)
        if times["gone"] is not None:
            return times
        await asyncio.sleep(0.1)
    return await banner_times(page, name)


async def screen_after(page, screen, t0):
    """The first time (MW.events ms) that a screen was shown at or after t0."""
    return await page.evaluate("(a => { const e = MW.events.find(e => e.type === 'screen' && e.detail === a[0] && e.t >= a[1]); return e ? e.t : null; })(%s)"
                               % json.dumps([screen, t0]))


async def test_banners(p, name, vw, vh, dpr):
    """MeeMee World's banner after Play, each game's banner as its planet is tapped, taps under them, and pausing."""
    print(f"\n== title banners ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"banner-{name}", vw, vh, dpr, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    start = await page.evaluate("[document.getElementById('screen-start').innerText.trim(), MW.world.banner.up()]")
    check(f"banner ({name}): the start screen has nothing to read, and no banner (sound can't start before Play)", start == ["", False], str(start))
    await page.screenshot(path=str(SHOTS / f"banner-{name}-0-start.png"))

    # MeeMee World's banner: once a visit, after Play, while "Welcome to MeeMee World!" plays
    await t.tap(*PLAY)
    await asyncio.sleep(0.3)
    info = await page.evaluate(BANNER_INFO)
    check(f"banner ({name}): after Play the map opens with MeeMee World's banner, a MeeMee at each end",
          info == {"up": True, "name": "MeeMee World", "art": ["mimi", "mimi"], "phase": "welcome", "screen": "screen-map"}, json.dumps(info))
    check(f"banner ({name}): ... while 'Welcome to MeeMee World!' plays", "map-welcome" in await t.said())
    lock = await page.evaluate("(() => { const s = MW.stage.scale; const e = document.elementFromPoint(MW.stage.offX + 46 * s, MW.stage.offY + 754 * s); return !!(e && e.closest('.mw-gate')); })()")
    check(f"banner ({name}): the grown-ups lock stays above the banner", lock)
    await asyncio.sleep(0.25)
    await page.screenshot(path=str(SHOTS / f"banner-{name}-1-world.png"))
    n_map = await page.evaluate("MW.events.filter(e => e.type === 'map').length")
    await t.tap(*RESCUE)
    await t.tap(*CREW_BTN)
    await t.tap(1172 + 42, 26 + 42)                          # Music
    after = await page.evaluate("[MW.events.filter(e => e.type === 'map').length, MW.world.st.phase, MW.shell.screen, MW.audio.music.isOn()]")
    check(f"banner ({name}): taps under it do nothing (a planet, the crew, Music)", after == [n_map, "welcome", "screen-map", True], str(after))
    times = await wait_gone(page, "MeeMee World")
    said = await said_at(page, "map-welcome")
    shown = (times["going"] or 0) - (times["up"] or 0)
    check(f"banner ({name}): it stays at least 2 seconds and for all of its line, then goes by itself",
          times["gone"] is not None and shown >= 1990 and said and times["going"] >= said[0] + said[1] * 1000 - 60, json.dumps([times, said]))
    await asyncio.sleep(0.1)
    check(f"banner ({name}): ... and then the map is ready", await page.evaluate("[MW.world.st.phase, MW.world.banner.up()]") == ["map", False])

    # MeeMee Rescue's banner: its name and badge from game.json, while its name is said; the game starts once it has gone
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await asyncio.sleep(0.3)
    info = await page.evaluate(BANNER_INFO)
    check(f"banner ({name}): tapping MeeMee Rescue's planet shows its banner: its name and its badge (the MeeMee)",
          info == {"up": True, "name": "MeeMee Rescue", "art": ["mimi"], "phase": "opening", "screen": "screen-map"}, json.dumps(info))
    await asyncio.sleep(0.25)
    await page.screenshot(path=str(SHOTS / f"banner-{name}-2-rescue.png"))
    pl = await page.evaluate(WORDS_PLANET)
    n_map = await page.evaluate("MW.events.filter(e => e.type === 'map').length")
    await t.tap(*RESCUE)
    await t.tap(pl["x"], pl["y"])
    await t.tap(*CREW_BTN)
    await t.tap(1172 + 42, 26 + 42)                          # Music
    after = await page.evaluate("[MW.events.filter(e => e.type === 'map').length, MW.world.st.phase, MW.shell.screen, MW.events.filter(e => e.type === 'round').length, MW.audio.music.isOn()]")
    check(f"banner ({name}): taps under a game's banner do nothing (its planet again, the other planet, the crew, Music)", after == [n_map, "opening", "screen-map", 0, True], str(after))
    s = await t.wait_phase(["asking", "open"])
    times = await banner_times(page, "MeeMee Rescue")
    said = await said_at(page, "map-mimi-rescue")
    started = await screen_after(page, "screen-game", times["up"] or 0)
    shown = (times["going"] or 0) - (times["up"] or 0)
    check(f"banner ({name}): MeeMee Rescue's banner stays at least 2 seconds, for all of 'MeeMee Rescue!'",
          shown >= 1990 and said and said[0] >= times["up"] - 5 and times["going"] >= said[0] + said[1] * 1000 - 60, json.dumps([times, said]))
    check(f"banner ({name}): ... and the round starts only once it has gone", s["screen"] == "screen-game" and started is not None and times["gone"] is not None
          and started >= times["gone"], json.dumps([times, started]))

    # Home: MeeMee World's banner doesn't show again this visit
    await t.tap(*HOME_BTN)
    await asyncio.sleep(0.6)
    ups = await page.evaluate("MW.events.filter(e => e.type === 'banner' && e.detail === 'up MeeMee World').length")
    check(f"banner ({name}): Home goes back to the map with no banner (MeeMee World's is once a visit)",
          ups == 1 and await page.evaluate("[MW.shell.screen, MW.world.st.phase, MW.world.banner.up()]") == ["screen-map", "map", False], str(ups))

    # MeeMee Rockets' banner
    await page.evaluate("MW.wordsGame.nextRound = %s" % json.dumps([{"word": "one", "step": "tiles"}]))
    await t.tap(pl["x"], pl["y"])
    await asyncio.sleep(0.3)
    info = await page.evaluate(BANNER_INFO)
    check(f"banner ({name}): tapping MeeMee Rockets' planet shows its banner: its name and its badge (the rocket)",
          info == {"up": True, "name": "MeeMee Rockets", "art": ["words-badge"], "phase": "opening", "screen": "screen-map"}, json.dumps(info))
    await asyncio.sleep(0.25)
    await page.screenshot(path=str(SHOTS / f"banner-{name}-3-rockets.png"))
    s = await w_wait(page, ["words-find"])
    times = await banner_times(page, "MeeMee Rockets")
    said = await said_at(page, "words-name")
    started = await screen_after(page, "screen-words-find", times["up"] or 0)
    check(f"banner ({name}): MeeMee Rockets' banner stays at least 2 seconds, for all of 'MeeMee Rockets!', then the game starts",
          (times["going"] or 0) - (times["up"] or 0) >= 1990 and said and times["going"] >= said[0] + said[1] * 1000 - 60
          and started is not None and started >= times["gone"], json.dumps([times, said, started]))
    await t.tap(*HOME_BTN)
    await asyncio.sleep(0.6)

    # a pause mid-banner: the banner goes and the player is back on the map (the screen going off, then the grown-ups area)
    hide = "Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    show = "Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))"
    rounds = await page.evaluate("MW.events.filter(e => e.type === 'round').length")
    await t.tap(*RESCUE)
    await asyncio.sleep(0.5)
    await page.evaluate(hide)
    await asyncio.sleep(0.5)
    mid = await page.evaluate("[MW.world.banner.up(), MW.world.st.phase, MW.shell.screen]")
    await page.evaluate(show)
    await asyncio.sleep(2.5)
    end = await page.evaluate("[MW.world.banner.up(), MW.world.st.phase, MW.shell.screen, MW.events.filter(e => e.type === 'round').length]")
    check(f"banner ({name}): the screen going off mid-banner: the banner goes, back on the map, no round behind it",
          mid == [False, "map", "screen-map"] and end == [False, "map", "screen-map", rounds], json.dumps([mid, end]))
    await t.tap(*RESCUE)
    await asyncio.sleep(0.5)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")   # what holding the lock does
    await asyncio.sleep(0.5)
    mid = await page.evaluate("[MW.world.banner.up(), MW.world.st.phase, MW.grownups.open]")
    await page.evaluate("MW.grownups.close()")
    await asyncio.sleep(2.5)
    end = await page.evaluate("[MW.world.banner.up(), MW.world.st.phase, MW.shell.screen, MW.events.filter(e => e.type === 'round').length]")
    check(f"banner ({name}): the grown-ups area opened mid-banner: the banner goes; closing it leaves the player on the map",
          mid == [False, "map", True] and end == [False, "map", "screen-map", rounds], json.dumps([mid, end]))
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    s = await t.wait_phase(["asking", "open"])
    check(f"banner ({name}): and the planet works again after it", s["screen"] == "screen-game", json.dumps(s))
    check(f"banner ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_banner_motion(p):
    """The banner fades and grows in; with reduce motion it only fades. The number track slides away; with reduce motion it fades.
    What moves is read from the transitions the browser runs (property and length), so a busy machine can't fool the check."""
    print("\n== title banners and the number track: motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    runs = "(e => e.getAnimations().map(a => [a.transitionProperty, a.effect.getTiming().duration]).sort())"
    for reduce in (False, True):
        label = "reduce motion" if reduce else "motion"
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce" if reduce else "no-preference")
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        style = "(() => { const c = getComputedStyle(document.querySelector('.mw-banner-card')); return [c.transform, +c.opacity]; })()"
        card = "document.querySelector('.mw-banner-card')"
        first = await page.evaluate(f"(() => {{ MW.world.home(); return [{style}, {runs}({card})]; }})()")
        await asyncio.sleep(0.45)
        shown = await page.evaluate(style)
        if reduce:
            check(f"banner ({label}): it fades in (260 ms) without moving or growing", first == [["none", 0], [["opacity", 260]]] and shown == ["none", 1], json.dumps([first, shown]))
        else:
            k = float(first[0][0].split("(")[1].split(",")[0]) if first[0][0].startswith("matrix(") else None
            check(f"banner ({label}): it fades and grows in (260 ms)", k is not None and k < 0.95 and first[0][1] < 0.05
                  and first[1] == [["opacity", 260], ["transform", 260]] and shown == ["none", 1], json.dumps([first, shown]))
        going = await page.evaluate(f"(() => {{ MW.world.banner.cancel(); return [{style}, {runs}({card})]; }})()")
        await asyncio.sleep(0.45)
        gone = await page.evaluate("[MW.world.banner.up(), getComputedStyle(document.getElementById('banner')).display]")
        check(f"banner ({label}): it fades out (260 ms) without moving, then it has gone", going[0][0] == "none" and going[1] == [["opacity", 260]]
              and gone == [False, "none"], json.dumps([going, gone]))
        # the number track: slides down out of sight (a fade with reduce motion), and back
        await page.evaluate("""(() => { const s = MW.make('section', 'mw-screen', {id: 'screen-kittest'}); MW.$('stage').appendChild(s);
            window.__tr = MW.numberTrack(s); MW.shell.show('screen-kittest'); })()""")
        track = "(() => { const e = window.__tr.el, r = e.querySelector('svg').getBoundingClientRect(); return [getComputedStyle(e).transform, +getComputedStyle(e).opacity, Math.round((r.top - MW.stage.offY) / MW.stage.scale)]; })()"
        moving = await page.evaluate(f"(() => {{ window.__tr.hide(); return {runs}(window.__tr.el); }})()")
        await asyncio.sleep(0.45)
        away = await page.evaluate(track)
        returning = await page.evaluate(f"(() => {{ window.__tr.show(); return {runs}(window.__tr.el); }})()")
        await asyncio.sleep(0.45)
        back = await page.evaluate(track)
        if reduce:
            check(f"track ({label}): it fades away (260 ms) without moving, and back", moving == [["opacity", 260]] and returning == [["opacity", 260]]
                  and away == ["none", 0, 674] and back == ["none", 1, 674], json.dumps([moving, away, returning, back]))
        else:
            check(f"track ({label}): it slides down out of sight (260 ms), and back", moving == [["transform", 260]] and returning == [["transform", 260]]
                  and away[1] == 1 and away[2] >= 800 and back == ["none", 1, 674], json.dumps([moving, away, returning, back]))
        check(f"banner and track ({label}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_banner_unrecorded(p):
    """A banner is always spoken with its name: while a name line isn't recorded, no banner, and the game starts at once."""
    print("\n== title banners: a line not recorded yet ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "banner-unrecorded", 1280, 800, 1, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rec = await page.evaluate("[MW.audio.recorded('map-welcome'), MW.audio.recorded('map-mimi-rescue'), MW.audio.recorded('words-name'), MW.audio.recorded('no-such-line')]")
    check("banner (unrecorded): MW.audio.recorded says which lines are on the page", rec == [True, True, True, False], str(rec))
    await page.evaluate("delete MW.audio.manifest.voice['map-welcome']; delete MW.audio.manifest.voice['map-mimi-rescue']; MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*PLAY)
    await asyncio.sleep(0.3)
    got = await page.evaluate("[MW.shell.screen, MW.world.st.phase, MW.world.banner.up(), MW.events.filter(e => e.type === 'banner' && e.detail.startsWith('up')).length]")
    check("banner (unrecorded): with 'Welcome to MeeMee World!' not recorded, the map opens with no banner", got == ["screen-map", "map", False, 0], str(got))
    t0 = await page.evaluate("performance.now()")
    await t.tap(*RESCUE)
    s = await t.wait_phase(["starting", "asking", "open"], 3)
    started = await screen_after(page, "screen-game", t0)
    got = await page.evaluate("[MW.world.banner.up(), MW.events.filter(e => e.type === 'banner').map(e => e.detail)]")
    check("banner (unrecorded): with 'MeeMee Rescue!' not recorded, no banner: the round starts straight away",
          s["screen"] == "screen-game" and started is not None and started - t0 < 600 and got[0] is False and got[1] == ["none for MeeMee Rescue (map-mimi-rescue not recorded yet)"],
          json.dumps([s, started and started - t0, got]))
    check("banner (unrecorded): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


KIT_SCREEN = """(() => { let s = document.getElementById('screen-kittest');
    if (!s) { s = MW.make('section', 'mw-screen', {id: 'screen-kittest'}); MW.$('stage').appendChild(s); }
    MW.shell.show('screen-kittest'); return true; })()"""


async def stage_box(page, js):
    """The stage box [x, y, w, h] of the element js finds."""
    return await page.evaluate("(() => { const e = %s; const r = e.getBoundingClientRect(), s = MW.stage.scale;"
                               " return [(r.left - MW.stage.offX) / s, (r.top - MW.stage.offY) / s, r.width / s, r.height / s]; })()" % js)


async def last_pick(page):
    return await page.evaluate("(() => { const e = MW.events.filter(e => e.type === 'pick').slice(-1)[0]; return e ? String(e.detail) : null; })()")


async def press(t, sx, sy):
    """A finger down and up again on one spot (picks up whatever is there, and lets it go)."""
    x, y = await t.screen(sx, sy)
    await touch(t, "touchStart", [(50, (x, y))])
    await asyncio.sleep(0.05)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.35)


async def test_kit_pieces(p, name, vw, vh, dpr):
    """The five gaps from the Rockets test build, and numbers mode's pieces (for MeeMee Rescue's numbers mode)."""
    print(f"\n== the kit's new pieces ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"kit-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)

    # reading a game's saved data creates nothing
    fresh = await page.evaluate("""(() => { const g = MW.wordsGame; g.answers(); g.week(); g.inPlay(); g.makeRound();
        MW.grownups.openPanel(); MW.grownups.show('words-progress'); MW.grownups.close();
        return [JSON.stringify(MW.store.peek('words')), Object.keys(MW.store.get('games')), (localStorage.getItem('mimi-world') || '').indexOf('"words"') < 0]; })()""")
    check(f"kit ({name}): MW.store.peek reads a game's saved data without creating it (MeeMee Rockets reads this way)", fresh == ["{}", [], True], str(fresh))
    made = await page.evaluate("""(() => { const g = MW.store.game('words'); g.week = 3; MW.store.save();
        return [MW.store.peek('words').week, MW.wordsGame.week(), Object.keys(MW.store.get('games'))]; })()""")
    check(f"kit ({name}): MW.store.game creates it (to change it); peek then reads what was saved", made == [3, 3, ["words"]], str(made))
    await page.evaluate("MW.store.clearGame('words')")

    # stars centred on a point for any total; a call placed by its left edge is as before
    await page.evaluate(KIT_SCREEN)
    rows = await page.evaluate("""(() => { const s = document.getElementById('screen-kittest'), out = [];
        const c = MW.stars(s, MW.LAYOUT.stars.cx, 34, null, { centre: true }), big = MW.stars(s, 640, 140, 60, { centre: true }), old = MW.stars(s, 517, 240);
        [3, 5, 7].forEach(n => { c.set(1, n); big.set(n, n); old.set(0, 5);
          const box = e => { const r = e.getBoundingClientRect(), k = MW.stage.scale; return [(r.left - MW.stage.offX) / k, r.width / k, e.children.length, e.offsetLeft]; };
          out.push([n, box(c.el), box(big.el), box(old.el)]); });
        [c, big, old].forEach(x => x.el.remove()); return out; })()""")
    ok = all(abs(a[0] + a[1] / 2 - 640) < 0.6 and abs(b[0] + b[1] / 2 - 640) < 0.6 and a[2] == n == b[2] and abs(o[0] - 517) < 0.6 for n, a, b, o in rows)
    check(f"kit ({name}): stars centre on a point for 3, 5 and 7 (38 and 60 px); a row placed by its left edge stays at 517", ok, json.dumps(rows))
    check(f"kit ({name}): ... and each row's offsetLeft is where it is drawn (what the navigator moment reads)",
          all(abs(x[0] - x[3]) < 0.6 for _, a, b, o in rows for x in (a, b, o)), json.dumps([[r[0], r[1][3], r[2][3]] for r in rows]))
    await page.evaluate("MW.wordsGame.nextRound = %s; MW.wordsGame.start()" % json.dumps([{"word": w, "step": "tiles"} for w in ("one", "of", "all")]))
    await w_wait(page, ["words-find"], 10)
    box = await stage_box(page, "document.querySelector('#screen-words-find .mw-stars')")
    n = await page.evaluate("[document.querySelectorAll('#screen-words-find .mw-stars svg').length, document.querySelector('#screen-words-find .mw-stars').offsetLeft]")
    check(f"kit ({name}): MeeMee Rockets' stars use the kit's centring (a round of 3: three stars, centred)", n[0] == 3 and abs(box[0] + box[2] / 2 - 640) < 0.6
          and abs(n[1] - box[0]) < 0.6, json.dumps([n, box]))

    # long tiles: picked up from either end, never the neighbour ('here' in sound tiles: h, then the long ere)
    await page.evaluate("MW.wordsGame.showBuild({ word: 'here', step: 'tiles' })")
    await asyncio.sleep(0.3)
    tiles = await page.evaluate("MW.wordsGame.st.tiles.map(c => ({ text: c.text, x: c.x, y: c.y, w: c.w, grab: c.grab }))")
    h = [c for c in tiles if c["text"] == "h"][0]
    ere = [c for c in tiles if c["text"] == "ere"][0]
    got = []
    for label, x in (("left end", ere["x"] - ere["w"] / 2 + 6), ("right end", ere["x"] + ere["w"] / 2 - 6), ("middle", ere["x"])):
        await press(t, x, ere["y"])
        got.append([label, await last_pick(page)])
    await press(t, h["x"] + h["w"] / 2 - 6, h["y"])
    got.append(["h's right end", await last_pick(page)])
    nearer_h = abs((ere["x"] - ere["w"] / 2 + 6) - h["x"]) < abs((ere["x"] - ere["w"] / 2 + 6) - ere["x"])
    check(f"kit ({name}): a long tile ('ere', {ere['w']:.0f} px) is picked up from either end, never its neighbour 'h'",
          [g[1] for g in got] == ["ere", "ere", "ere", "h"] and ere["grab"]["w"] > ere["w"], json.dumps(got) + (" (its left end is nearer h's middle: one radius for all picked h)" if nearer_h else ""))
    st = await w_state(page)
    check(f"kit ({name}): ... and picking a tile up and letting it go where it was isn't a try", st["drops"] == 0 and st["next"] == 0, json.dumps(st))
    await page.evaluate("MW.world.home(); MW.world.banner.cancel()")

    # numbers mode's diagram: no pills, no "?", a numbered MeeMee in each given circle (the whole's at 0.86)
    await page.evaluate(KIT_SCREEN)
    await page.evaluate("""(() => { const s = document.getElementById('screen-kittest');
        const d = window.__d = MW.diagram(s); d.look('numbers'); d.set({ whole: 7, left: 3, right: 4, missing: 'right' });
        MW.pod(s, MW.LAYOUT.pod.x, MW.LAYOUT.pod.y, MW.LAYOUT.pod.w); MW.stars(s, 517, 34).set(0);
        const tr = window.__tr = MW.numberTrack(s);
        const lay = MW.make('div', 'mw-layer mw-fill'); s.appendChild(lay);
        window.__drag = MW.dragger(s, { counters: () => tr.tiles, onPick: c => MW.log('pick', c.n),
          onDrop: (c, x, y, cancelled) => { if (!cancelled && d.hit(x, y) === 'right') c.moveTo(MW.LAYOUT.right.x, MW.LAYOUT.right.y, 0, true); else c.goHome(true); } }); })()""")
    await asyncio.sleep(0.3)
    look = await page.evaluate("""(() => { const s = document.getElementById('screen-kittest'), d = window.__d;
        const vis = e => !!(e.offsetWidth || e.offsetHeight) && getComputedStyle(e).visibility !== 'hidden';
        const carriers = Array.from(s.querySelectorAll('.mw-numbered')).filter(vis);
        return { pills: Array.from(s.querySelectorAll('.mw-pill')).filter(vis).length, q: s.innerText.indexOf('?') >= 0,
                 carried: ['whole', 'left', 'right'].map(k => d.carried(k)), waiting: d.circles.right.classList.contains('is-waiting'),
                 scales: carriers.map(e => e.style.transform), signs: carriers.map(e => e.textContent) }; })()""")
    check(f"kit ({name}): the numbers look: no pills and no '?'", look["pills"] == 0 and not look["q"], json.dumps(look))
    check(f"kit ({name}): ... the whole and the given part each hold a numbered MeeMee (7 at 0.86, 3), the missing part waits empty",
          look["carried"] == [7, 3, None] and look["waiting"] and sorted(look["scales"]) == ["scale(0.86)", "scale(1)"] and sorted(look["signs"]) == ["3", "7"], json.dumps(look))
    wb = await stage_box(page, "document.querySelectorAll('#screen-kittest .mw-numbered-sign')[0]")
    check(f"kit ({name}): the whole's sign sits in the whole circle", 380 - 115 < wb[0] and wb[0] + wb[2] < 380 + 115 and 205 - 115 < wb[1] < wb[1] + wb[3] < 205 + 115, json.dumps(wb))

    # the number track: 11 tiles, 0 to 10 in order, 84 across in 120 boxes, clear of the grown-ups lock
    tr = await page.evaluate("window.__tr.tiles.map(c => ({ n: c.n, x: c.x, y: c.y, grab: c.grab, text: c.el.textContent }))")
    boxes = [await stage_box(page, f"window.__tr.tiles[{i}].el.querySelector('.mw-number-tile-body')") for i in range(11)]
    rail = await stage_box(page, "window.__tr.el.querySelector('svg')")
    check(f"kit ({name}): the track has 11 tiles, 0 to 10 in order (x 128 + 94 n, tops at 686)",
          [c["text"] for c in tr] == [str(i) for i in range(11)] and all(abs(b[0] - (128 + 94 * i)) < 0.6 and abs(b[1] - 686) < 0.6 for i, b in enumerate(boxes)), json.dumps(boxes[:3]))
    check(f"kit ({name}): each tile is drawn 84 across with a 120 pick-up box", all(abs(b[2] - 84) < 0.6 and abs(b[3] - 84) < 0.6 for b in boxes)
          and all(c["grab"] == {"w": 120, "h": 120} for c in tr), json.dumps([boxes[0], tr[0]["grab"]]))
    lock = [24, 732, 44, 44]
    clear = rail[0] > lock[0] + lock[2] and all(c["x"] - 60 > lock[0] + lock[2] for c in tr) and all(b[1] + b[3] <= 800 - 24 for b in boxes)
    check(f"kit ({name}): the track is clear of the grown-ups lock (and its tiles 24 px from the edge)", clear, json.dumps([rail, lock]))
    await page.screenshot(path=str(SHOTS / f"kit-{name}-numbers-ask.png"))

    # dragging tiles: into the waiting circle, or back to the track; the tile's place shows a dashed ring while it's out
    four = tr[4]
    await t.drag(four["x"], four["y"], 560, 480)
    at = await page.evaluate("[window.__tr.tile(4).x, window.__tr.tile(4).y, window.__tr.tile(4).out(), window.__tr.tiles.filter(c => c.out()).length]")
    ring = await page.evaluate("getComputedStyle(document.querySelectorAll('#screen-kittest .mw-track-place')[4]).display")
    check(f"kit ({name}): a tile dragged into the waiting circle stays there, and its place shows a dashed ring", at == [550, 470, True, 1] and ring == "block", json.dumps([at, ring]))
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"kit-{name}-numbers-dropped.png"))
    seven = tr[7]
    await t.drag(seven["x"], seven["y"], 900, 330)
    await asyncio.sleep(0.3)
    back = await page.evaluate("[window.__tr.tile(7).x, window.__tr.tile(7).y, window.__tr.tile(7).out()]")
    check(f"kit ({name}): a tile dropped anywhere else goes back to its place", back == [seven["x"], seven["y"], False], json.dumps(back))
    got = []
    for i, dx in ((5, -38), (5, 38), (6, -38), (0, -38), (10, 38)):
        await press(t, tr[i]["x"] + dx, tr[i]["y"] + 36)
        got.append([i, await last_pick(page)])
    check(f"kit ({name}): a tile is picked up anywhere on it, never its neighbour", all(str(i) == g for i, g in got), json.dumps(got))

    # the track goes while a finger holds a tile: the tile is let go and goes home with the rest
    six = tr[6]
    x0, y0 = await t.screen(six["x"], six["y"])
    x1, y1 = await t.screen(600, 520)
    await touch(t, "touchStart", [(60, (x0, y0))])
    for k in range(1, 7):
        await touch(t, "touchMove", [(60, (x0 + (x1 - x0) * k / 6, y0 + (y1 - y0) * k / 6))])
        await asyncio.sleep(0.03)
    held = await page.evaluate("[window.__drag.dragging(), window.__tr.tile(6).out()]")
    await page.evaluate("window.__tr.hide()")
    let_go = await page.evaluate("[window.__drag.dragging(), window.__tr.tile(6).x, window.__tr.tile(6).y, window.__tr.tile(6).lifted, window.__tr.tile(6).out(), window.__tr.away()]")
    n_pick = await page.evaluate("MW.events.filter(e => e.type === 'pick').length")
    for k in range(1, 4):                                    # the finger carries on moving, then lifts
        await touch(t, "touchMove", [(60, (x1 + k * 20, y1))])
        await asyncio.sleep(0.03)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.4)
    after = await page.evaluate("[window.__tr.tile(6).x, window.__tr.tile(6).y, window.__tr.tile(6).out(), MW.events.filter(e => e.type === 'pick').length]")
    check(f"kit ({name}): hiding the track while a tile is held lets go of it: it goes home with the rest, and the finger moving on does nothing",
          held == [True, True] and let_go == [False, six["x"], six["y"], False, False, True] and after == [six["x"], six["y"], False, n_pick],
          json.dumps([held, let_go, after]))
    await page.evaluate("window.__tr.show()")
    await asyncio.sleep(0.4)

    # a right answer: a numbered MeeMee pops up to carry the number, and the track slides away and back
    await page.evaluate("window.__d.success('right', 4); window.__tr.hide()")
    await asyncio.sleep(0.5)
    right = await page.evaluate("""[window.__d.carried('right'), window.__d.circles.right.classList.contains('is-success'),
        Array.from(document.querySelectorAll('#screen-kittest .mw-numbered')).some(e => e.classList.contains('is-popping')),
        window.__tr.tile(4).out(), window.__tr.away()]""")
    rail = await stage_box(page, "window.__tr.el.querySelector('svg')")
    check(f"kit ({name}): success in the numbers look: a numbered MeeMee pops up carrying 4; the track slides out of sight, tile 4 back in it",
          right == [4, True, True, False, True] and rail[1] >= 800, json.dumps([right, rail]))
    await page.screenshot(path=str(SHOTS / f"kit-{name}-numbers-right.png"))
    n_pick = await page.evaluate("MW.events.filter(e => e.type === 'pick').length")
    await press(t, tr[3]["x"], tr[3]["y"])
    check(f"kit ({name}): while the track is away its tiles can't be picked up", await page.evaluate("MW.events.filter(e => e.type === 'pick').length") == n_pick)
    await page.evaluate("window.__tr.show(); window.__d.set({ whole: 5, left: 2, right: 3, missing: 'whole' })")
    await asyncio.sleep(0.4)
    whole = await page.evaluate("[['whole', 'left', 'right'].map(k => window.__d.carried(k)), window.__d.circles.whole.classList.contains('is-waiting'), window.__tr.away()]")
    rail = await stage_box(page, "window.__tr.el.querySelector('svg')")
    check(f"kit ({name}): a missing whole: numbered MeeMee in both parts, the whole waits; the track is back", whole == [[None, 2, 3], True, False] and abs(rail[1] - 674) < 0.6,
          json.dumps([whole, rail]))
    await page.screenshot(path=str(SHOTS / f"kit-{name}-numbers-whole.png"))
    # and the counting look is as before: the pills and "?", no numbered MeeMee
    back = await page.evaluate("""(() => { const d = window.__d, s = document.getElementById('screen-kittest'); d.look('counting'); d.set({ whole: 7, left: 3, right: 4, missing: 'right' });
        const vis = e => !!(e.offsetWidth || e.offsetHeight);
        return [Array.from(s.querySelectorAll('.mw-pill')).filter(vis).map(e => e.textContent), s.querySelector('.numeral-whole').textContent,
                Array.from(s.querySelectorAll('.mw-numbered')).filter(vis).length]; })()""")
    check(f"kit ({name}): the counting look is unchanged: pills 3 and ?, 7 in the whole, no numbered MeeMee", back == [["3", "?"], "7", 0], json.dumps(back))
    check(f"kit ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# ---------------------------------------------------------------- 0.6.0: MeeMee Rescue's numbers mode
POD = (1030, 300)                     # Scruffles: tapped to check


def tile_xy(n):
    """The middle of number tile n in its place on the track (x 128 + 94 n, tops at 686, 84 across)."""
    return (128 + 94 * n + 42, 686 + 42)


async def n_state(page):
    return await page.evaluate("""(() => { const R = MW.rescue, s = R.st, d = R.diagram(), tr = R.track();
        return { phase: s.phase, qi: s.qi, target: s.target, answer: s.answer, placed: s.placed ? s.placed.n : null,
                 tries: s.tries, misses: s.misses, hinted: s.hinted, mode: R.mode(), screen: MW.shell.screen,
                 carried: ['whole', 'left', 'right'].map(k => d.carried(k)), away: tr.away(),
                 out: tr.tiles.filter(t => t.out()).map(t => t.n), fixed: s.fixed.length,
                 ghosts: document.querySelectorAll('#screen-game .mw-ghost').length,
                 lit: document.querySelectorAll('#screen-game .mw-ghost.is-lit').length,
                 face: document.querySelector('#screen-game .mw-pod').dataset.face,
                 ready: document.querySelector('#screen-game .mw-pod').classList.contains('is-ready') }; })()""")


async def n_look(page):
    """What the game screen shows: visible pills, any '?', the asteroid, the track, MeeMee counters."""
    return await page.evaluate("""(() => { const g = document.getElementById('screen-game');
        const shown = e => !!e && getComputedStyle(e).display !== 'none' && !e.closest('.mw-off');
        const tray = Array.from(g.children).find(e => e.style.left === '745px' && e.style.top === '515px');
        const tr = MW.rescue.track();
        return { pills: Array.from(g.querySelectorAll('.mw-pill')).filter(shown).length,
                 q: Array.from(g.querySelectorAll('.numeral-whole, .numeral-part')).filter(e => shown(e) && e.textContent === '?').length,
                 tray: shown(tray), track: shown(tr.el), tiles: tr.tiles.map(t => t.el.textContent),
                 counters: g.querySelectorAll('.mw-counters .mw-mimi').length,
                 look: MW.rescue.diagram().look() }; })()""")


async def n_wait(t, pred_js, timeout=10):
    for _ in range(int(timeout / 0.1)):
        if await t.page.evaluate(pred_js):
            return True
        await asyncio.sleep(0.1)
    return False


async def n_quiet(t, timeout=15):
    """Until nothing is being said."""
    for _ in range(int(timeout / 0.1)):
        if not await t.page.evaluate("MW.audio.speaking()"):
            return True
        await asyncio.sleep(0.1)
    return False


async def n_hold(t, sx0, sy0, sx1, sy1, touch_id=40, steps=8):
    """A finger down at one point, moved to another, still held."""
    x0, y0 = await t.screen(sx0, sy0)
    x1, y1 = await t.screen(sx1, sy1)
    await touch(t, "touchStart", [(touch_id, (x0, y0))])
    for k in range(1, steps + 1):
        await touch(t, "touchMove", [(touch_id, (x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps))])
        await asyncio.sleep(0.02)
    await asyncio.sleep(0.15)


async def n_check(t):
    """Tap Scruffles, then a moment."""
    await t.tap(*POD)
    await asyncio.sleep(0.5)


async def test_numbers_round(p, name, vw, vh, dpr):
    """A whole numbers-mode round with tap Scruffles (the usual check), played by touch, with the boards' screenshots."""
    print(f"\n== numbers mode: a round with tap Scruffles ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"numbers-{name}", vw, vh, dpr, mode="tap")
    await page.evaluate("MW.store.setting('answerMode', 'numbers'); MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 20)
    st = await n_state(page)
    look = await n_look(page)
    check(f"numbers ({name}): a numbered MeeMee in each given circle (7 in the whole, 3 in a part); the missing part waits empty and dashed",
          st["carried"] == [7, 3, None] and st["mode"] == "numbers"
          and await page.evaluate("MW.rescue.diagram().circles.right.classList.contains('is-waiting')"), json.dumps(st))
    check(f"numbers ({name}): no pills, no '?', no asteroid and no MeeMee to drag; the number track holds 0 to 10",
          look["pills"] == 0 and look["q"] == 0 and not look["tray"] and look["track"] and look["counters"] == 0
          and look["tiles"] == [str(i) for i in range(11)] and look["look"] == "numbers", json.dumps(look))
    said = await t.said()
    check(f"numbers ({name}): question 1 as in counting mode, then 'Find the number.', then 'Tap Scruffles when you're ready.'",
          "q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more rescue-find-number tap-scruffles" in said, str(said[-2:]))
    # the ask (Numbers8Ask): a tile on its way to the circle
    await n_hold(t, *tile_xy(4), 652, 632)
    ring = await page.evaluate("getComputedStyle(document.querySelectorAll('#screen-game .mw-track-place')[4]).display")
    check(f"numbers ({name}): a tile picked up leaves a dashed ring in its place", ring == "block", ring)
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-1-ask.png"))
    hx, hy = await t.screen(*tile_xy(4))
    await touch(t, "touchMove", [(40, (hx, hy))])
    await asyncio.sleep(0.05)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.4)
    st = await n_state(page)
    check(f"numbers ({name}): ... and put back in its place it's simply back (not a try)", st["out"] == [] and st["tries"] == 0 and st["misses"] == 0, json.dumps(st))

    # tapping Scruffles with no tile in the circle asks the question again and isn't a try
    await n_quiet(t)
    n0 = len(await t.said())
    await n_check(t)
    said = await t.said()
    st = await n_state(page)
    check(f"numbers ({name}): Scruffles tapped with no tile in the circle asks the question again (not a try)",
          said[n0:][:1] == ["q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more rescue-find-number tap-scruffles"] and st["tries"] == 0,
          json.dumps([said[n0:], st["tries"]]))
    # a tile dropped in the circle stays there; a second one sends the first back
    await t.drag(*tile_xy(2), 560, 480)
    st = await n_state(page)
    check(f"numbers ({name}): tile 2 dropped in the waiting circle stays there, its place ringed, the ship's lights glow (tap mode)",
          st["placed"] == 2 and st["out"] == [2] and st["ready"] and st["phase"] == "open", json.dumps(st))
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-2-dropped.png"))
    await t.drag(*tile_xy(5), 600, 520)
    st = await n_state(page)
    check(f"numbers ({name}): a second tile (5) in the circle sends the first (2) back to the track", st["placed"] == 5 and st["out"] == [5], json.dumps(st))
    # a wrong number: try-again face, "Let's try again.", and the tile floats back
    await n_check(t)
    st = await n_state(page)
    check(f"numbers ({name}): a wrong number (5 for 4): 'Let's try again.', the try-again face, and the tile floats back",
          (await t.said())[-1:] == ["again-try-again"] and st["face"] == "try-again" and st["placed"] is None and st["out"] == []
          and st["tries"] == 1 and not st["hinted"] and not st["ready"], json.dumps(st))
    # with tap Scruffles a tile dropped away from the circle isn't a try
    await asyncio.sleep(1.2)
    n0 = len(await t.said())
    await t.drag(*tile_xy(8), 900, 330)
    await asyncio.sleep(0.4)
    st = await n_state(page)
    check(f"numbers ({name}): a tile dropped anywhere else floats back to its place, and with tap Scruffles isn't a try",
          st["out"] == [] and st["misses"] == 0 and st["tries"] == 1 and (await t.said())[n0:] == [], json.dumps(st))
    # the second wrong number brings the hint: the given part as MeeMee, the whole keeps its number, ghosts count on
    await t.drag(*tile_xy(6), 550, 470)
    await n_check(t)
    st = await n_state(page)
    said = await t.said()
    check(f"numbers ({name}): the second wrong number brings the counting-on hint ('Let's count on from three. Four, five, six, seven.')",
          "q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7" in said and st["hinted"] and st["tries"] == 2, str(said[-2:]))
    check(f"numbers ({name}): ... the given part comes back as 3 MeeMee, the whole keeps its numbered MeeMee, 4 ghosts wait",
          st["carried"] == [7, None, None] and st["fixed"] == 3 and st["ghosts"] == 4, json.dumps(st))
    await n_quiet(t)
    await asyncio.sleep(0.3)
    st = await n_state(page)
    check(f"numbers ({name}): ... the ghosts light as they're counted, and stay (with the MeeMee) until the question is answered",
          st["lit"] == 4 and st["fixed"] == 3 and st["hinted"], json.dumps(st))
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-3-hint-part.png"))
    # right: a MeeMee pops up to carry the number; the track slides away; the number sentence
    await t.drag(*tile_xy(4), 545, 465)
    await n_check(t)
    st = await n_state(page)
    rail = await stage_box(page, "MW.rescue.track().el.querySelector('svg')")
    right = await page.evaluate("""[MW.rescue.diagram().circles.right.classList.contains('is-success'),
        Array.from(document.querySelectorAll('#screen-game .mw-numbered')).some(e => e.classList.contains('is-popping') && e.textContent === '4'),
        document.querySelector('#screen-game .mw-pod').classList.contains('is-celebrating')]""")
    check(f"numbers ({name}): tile 4 and a tap: a numbered MeeMee pops up carrying 4, the success ring, the got-it face and the ship's lights",
          st["phase"] == "celebrate" and st["carried"] == [7, 3, 4] and right == [True, True, True] and st["face"] == "got-it", json.dumps([st, right]))
    check(f"numbers ({name}): ... the track slides down out of sight, every tile back in it", st["away"] and st["out"] == [] and rail[1] >= 800, json.dumps([st["away"], rail]))
    check(f"numbers ({name}): ... the hint's MeeMee fly up to the ship and the part carries its number again", st["carried"][1] == 3
          and await page.evaluate("document.querySelectorAll('#screen-game .mw-counters .mw-mimi.is-rescued').length") == 3)
    await n_wait(t, "MW.events.some(e => e.type === 'say' && e.detail === 'num-mid-3 and num-mid-4 make num-end-7')", 10)
    await asyncio.sleep(0.4)
    eq = await page.inner_text("#screen-game .mw-equation")
    check(f"numbers ({name}): the number sentence shows and is said: 3 + 4 = 7", eq.replace("\n", " ").split() == ["3", "+", "4", "=", "7"], eq)
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-5-right.png"))
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check(f"numbers ({name}): saved with its mode: numbers, 2 wrong numbers, the hint, tap Scruffles",
          rec.get("mode") == "numbers" and rec["tries"] == 2 and rec["hint"] is True and rec["check"] == "tap" and rec["misses"] == 0, json.dumps(rec))

    # Q2: a missing whole: numbered MeeMee in both parts, the whole waiting; two wrong numbers, then count with me
    s = await t.wait_phase(["open"], 20)
    st = await n_state(page)
    rail = await stage_box(page, "MW.rescue.track().el.querySelector('svg')")
    said = await t.said()
    check(f"numbers ({name}): the track comes back for the next question", not st["away"] and abs(rail[1] - 674) < 0.6, json.dumps(rail))
    check(f"numbers ({name}): question 2 (missing whole): numbered MeeMee in both parts, the whole waits; asked as in counting mode, then the two lines",
          st["carried"] == [None, 2, 3] and st["target"] == "whole"
          and "q-weve-got num-mid-2 and num-end-3 q-how-many-altogether rescue-find-number tap-scruffles" in said, json.dumps([st, said[-1:]]))
    await t.drag(*tile_xy(4), 380, 205)
    await n_check(t)
    await asyncio.sleep(1.2)
    await t.drag(*tile_xy(6), 400, 220)
    await n_check(t)
    st = await n_state(page)
    check(f"numbers ({name}): two wrong numbers for a missing whole bring 'Count them with me.': both parts as MeeMee, 5 ghosts in the whole",
          any(x.startswith("again-count-with-me") for x in await t.said()) and st["carried"] == [None, None, None] and st["fixed"] == 5 and st["ghosts"] == 5,
          json.dumps(st))
    await n_quiet(t)
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-4-hint-whole.png"))
    await t.drag(*tile_xy(5), 380, 205)
    await n_check(t)
    st = await n_state(page)
    check(f"numbers ({name}): tile 5 completes 2 + 3 = ?", st["phase"] == "celebrate" and st["carried"] == [5, 2, 3], json.dumps(st))

    # Q3: from the third question neither line is said; right first time
    s = await t.wait_phase(["open"], 20)
    p3 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check(f"numbers ({name}): from question 3, no 'Find the number.' and no tap line", s["qi"] == 2 and "rescue-find-number" not in p3 and "tap-scruffles" not in p3, p3)
    await t.drag(*tile_xy(1), 210, 470)
    await n_check(t)
    st = await n_state(page)
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check(f"numbers ({name}): ? + 5 = 6 answered with tile 1, right first time", st["phase"] == "celebrate" and rec["tries"] == 0 and not rec["hint"] and rec["mode"] == "numbers", json.dumps(rec))
    s = await t.wait_phase(["open"], 20)
    await t.drag(*tile_xy(5), 550, 470)
    await n_check(t)
    s = await t.wait_phase(["open"], 20)
    await t.drag(*tile_xy(4), 380, 205)
    await n_check(t)
    await t.wait_phase(["done"], 20)
    await asyncio.sleep(1)
    s = await t.state()
    modes = await page.evaluate("MW.store.get('answers').map(a => a.mode)")
    check(f"numbers ({name}): the round ends on the celebration screen with five answers saved as numbers", s["screen"] == "screen-end" and modes == ["numbers"] * 5, json.dumps([s, modes]))

    # the grown-ups tabs (Grownups8Settings, Grownups8Progress)
    await n_quiet(t)
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('settings')")
    await asyncio.sleep(0.4)
    settings = await page.evaluate("""(() => { const b = document.querySelector('.gu-body');
        return { h3: Array.from(b.querySelectorAll('.gu-h3')).map(h => h.textContent),
                 ways: Array.from(b.querySelectorAll('[data-way]')).map(x => [x.textContent, x.classList.contains('is-on')]) }; })()""")
    check(f"numbers ({name}): Settings: 'How your child answers' above 'Answer check', 'MeeMee to count' or 'Numbers' (on)",
          settings["h3"] == ["How your child answers", "Answer check"] and settings["ways"] == [["MeeMee to count", False], ["Numbers", True]], json.dumps(settings))
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-6-settings.png"))
    await page.evaluate("MW.grownups.show('progress')")
    await asyncio.sleep(0.4)
    prog = await page.evaluate("""(() => { const b = document.querySelector('.gu-body');
        return { h3: b.querySelector('.gu-h3').textContent, ways: Array.from(b.querySelectorAll('[data-way]')).map(x => [x.textContent, x.classList.contains('is-on')]),
                 lead: b.querySelector('.gu-lead').textContent }; })()""")
    check(f"numbers ({name}): Progress: 'Showing progress for' with the switch on Numbers, and the numbers-mode summary",
          prog["h3"] == "Showing progress for" and prog["ways"] == [["MeeMee to count", False], ["Numbers", True]]
          and prog["lead"] == "Secure: 0 of 34 bonds. Practising: 5. Questions answered this way on this tablet: 5.", json.dumps(prog))
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-7-progress.png"))
    rows = await page.evaluate("Array.from(document.querySelectorAll('.gu-body .gu-table tr')).slice(1).map(tr => tr.children[2].textContent)")
    check(f"numbers ({name}): Progress's recent answers are this way's (five, the first with 2 wrong numbers and the hint)",
          len(rows) == 5 and rows[-1] == "2 wrong numbers, with the hint (tap Scruffles)", json.dumps(rows))
    await page.evaluate("(() => { const b = document.querySelector('.gu-body'); b.scrollTop = b.scrollHeight; })()")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"{name}-numbers-8-recent.png"))
    await page.evaluate("MW.grownups.close()")
    check(f"numbers ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_numbers_auto(p):
    """Numbers mode with 'as soon as it's right': checked as a tile lands; a tile dropped away is a try. The lookout's place."""
    print("\n== numbers mode: as soon as it's right ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "numbers-auto", 1280, 800, 1, mode="auto")
    await page.evaluate("MW.store.setting('answerMode', 'numbers'); MW.crew.save({moggles: 'lookout', snuffles: 'engineer'}); MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await t.tap(*RESCUE)
    await t.wait_screen("screen-game", 6)
    await asyncio.sleep(1.2)
    shown = await page.evaluate("!!document.querySelector('#screen-game [data-moment=lookout].is-shown')")
    lb = await stage_box(page, "document.querySelector('#screen-game [data-moment=lookout]')")    # the window it peeks through
    order = await page.evaluate("""(() => { const lay = document.querySelector('[data-moment=lookout]').closest('.mw-moments'), tr = MW.rescue.track().el;
        return !!(lay.compareDocumentPosition(tr) & Node.DOCUMENT_POSITION_FOLLOWING); })()""")
    check("numbers: the lookout peeks up from behind the right-hand end of the number track (its rail ends at 1166, top 674), below the ship (answer 24)",
          shown and order and lb[0] > 880 and lb[0] + lb[2] <= 1166 and lb[1] >= 500 and 674 < lb[1] + lb[3] <= 700, json.dumps([lb, order]))
    check("numbers: ... and keeps clear of the diagram", lb and not any(overlaps_circle(lb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]), str(lb))
    await page.screenshot(path=str(SHOTS / "numbers-lookout.png"))
    await t.wait_phase(["open"], 20)
    said = await t.said()
    check("numbers: with 'as soon as it's right' the first question ends with 'Find the number.' (no tap line)",
          said[-1:] == ["q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more rescue-find-number"], str(said[-1:]))
    n0 = len(said)
    await n_check(t)
    check("numbers: tapping Scruffles asks the question again", (await t.said())[n0:][:1] == said[-1:] and (await n_state(page))["tries"] == 0)
    await n_quiet(t)
    await t.drag(*tile_xy(2), 550, 470)
    await asyncio.sleep(0.3)
    st = await n_state(page)
    check("numbers: a wrong tile is checked as it lands: 'Let's try again.' and it floats back",
          (await t.said())[-1:] == ["again-try-again"] and st["tries"] == 1 and st["placed"] is None and st["out"] == [] and st["phase"] == "open", json.dumps(st))
    await asyncio.sleep(1.2)
    await t.drag(*tile_xy(9), 760, 300)
    await asyncio.sleep(0.4)
    st = await n_state(page)
    check("numbers: a tile dropped away from the circle floats back and counts as a try (a miss)", st["misses"] == 1 and st["out"] == []
          and (await t.said())[-1:] == ["again-try-again"], json.dumps(st))
    await asyncio.sleep(1.2)
    await t.drag(*tile_xy(9), *tile_xy(9))                  # picked up and put down in its place: nothing
    await t.drag(*tile_xy(6), 520, 450)
    await asyncio.sleep(0.4)
    st = await n_state(page)
    check("numbers: the second wrong number brings the hint", st["hinted"] and st["tries"] == 2 and st["misses"] == 1, json.dumps(st))
    await t.drag(*tile_xy(4), 560, 480)
    st = await n_state(page)
    check("numbers: the right tile completes it as it lands (no tap)", st["phase"] == "celebrate" and st["carried"][2] == 4, json.dumps(st))
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check("numbers: saved with its mode and the check", rec["mode"] == "numbers" and rec["check"] == "auto" and rec["tries"] == 2 and rec["misses"] == 1 and rec["hint"], json.dumps(rec))
    # Q2: two misses bring the count-with-me hint; then the right tile
    await t.wait_phase(["open"], 20)
    said = await t.said()
    check("numbers: question 2 ends with 'Find the number.' too", said[-1:] == ["q-weve-got num-mid-2 and num-end-3 q-how-many-altogether rescue-find-number"], str(said[-1:]))
    await t.drag(*tile_xy(3), 660, 120)
    await asyncio.sleep(1.2)
    await t.drag(*tile_xy(3), 210, 470)                     # onto a given part: a miss
    await asyncio.sleep(0.5)
    st = await n_state(page)
    check("numbers: two tiles dropped away bring 'Count them with me.'", st["hinted"] and st["misses"] == 2
          and any(x.startswith("again-count-with-me") for x in await t.said()), json.dumps(st))
    await t.drag(*tile_xy(5), 380, 205)
    st = await n_state(page)
    check("numbers: tile 5 in the whole completes 2 + 3 = ?", st["phase"] == "celebrate" and st["carried"] == [5, 2, 3], json.dumps(st))
    await t.wait_phase(["open"], 20)
    p3 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("numbers: from question 3, no 'Find the number.'", "rescue-find-number" not in p3, p3)
    await t.tap(*HOME)
    check("numbers: Home goes back to the map", await t.wait_screen("screen-map", 5))
    check("numbers (auto): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_numbers_bonds(p):
    """Every bond, zero bonds included, as a numbers question; zero bonds and progress kept apart by mode."""
    print("\n== numbers mode: every bond, and progress by mode ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [], check_mode="auto")
    qs = await page.evaluate("MW.bonds.allQuestions([2,3,4,5,6,7,8,9,10], true)")
    out = await page.evaluate("""(qs) => { MW.store.setting('answerMode', 'numbers'); const R = MW.rescue, out = [];
        qs.forEach(q => { R.ask(q); const d = R.diagram(), tr = R.track(), s = R.st, c = MW.LAYOUT[q.missing];
          const ans = q.missing === 'whole' ? q.whole : q[q.missing], wrong = (ans + 1) % 11;
          const o = { q: q, ans: ans, mode: R.mode(), shown: ['whole', 'left', 'right'].map(k => d.carried(k)),
                      waiting: d.circles[q.missing].classList.contains('is-waiting'), prompt: s.prompt };
          R.drop(tr.tile(wrong), c.x + 30, c.y - 20, false);
          o.wrong = [s.phase, s.tries, s.placed ? s.placed.n : null, tr.tile(wrong).out()];
          R.drop(tr.tile(ans), c.x - 40, c.y + 30, false);
          const rec = MW.store.get('answers').slice(-1)[0];
          o.right = [s.phase, d.carried(q.missing), d.circles[q.missing].classList.contains('is-success'), tr.away()];
          o.rec = [rec.mode, rec.whole, rec.left, rec.right, rec.missing, rec.tries];
          out.push(o); });
        MW.world.home(); return out; }""", qs)
    bad = []
    for o in out:
        q, ans = o["q"], o["ans"]
        want_shown = [None if k == q["missing"] else q[k] for k in ("whole", "left", "right")]
        if q["missing"] == "whole":
            want_prompt = [["q-weve-got", f"num-mid-{q['left']}", "and", f"num-end-{q['right']}"], ["q-how-many-altogether"]]
        else:
            given = q["right" if q["missing"] == "left" else "left"]
            want_prompt = [["q-lets-make", f"num-end-{q['whole']}"], ["q-weve-got", f"num-end-{given}"], ["q-how-many-more"]]
        ok = (o["mode"] == "numbers" and o["shown"] == want_shown and o["waiting"] and o["prompt"] == want_prompt
              and o["wrong"] == ["open", 1, None, False] and o["right"] == ["celebrate", ans, True, True]
              and o["rec"] == ["numbers", q["whole"], q["left"], q["right"], q["missing"], 1])
        if not ok:
            bad.append(o)
    zeros = [o for o in out if 0 in (o["q"]["left"], o["q"]["right"])]
    check("numbers: every bond as a numbers question (189, zero bonds included): the numbered MeeMee, the same words, a wrong tile refused, the right tile completes it",
          len(out) == 189 and not bad, json.dumps(bad[:2]))
    check("numbers: a zero bond's answer is what the question asks for: 0, or the other number",
          len(zeros) == 54 and {o["ans"] for o in zeros if o["q"]["missing"] != "whole" and o["q"][o["q"]["missing"]] == 0} == {0}
          and all(o["ans"] > 0 for o in zeros if o["q"]["missing"] == "whole"), str(len(zeros)))
    await ctx.close()

    # zero bonds in numbers mode, whichever check, once that number's other bonds are secure in numbers mode
    rounds = """() => { const out = {}; [['numbers', 'auto'], ['numbers', 'tap'], ['counting', 'auto'], ['counting', 'tap']].forEach(mc => {
        MW.store.setting('answerMode', mc[0]); MW.store.setting('check', mc[1]); MW.rescue.st.mode = null; MW.rescue.st.check = null;
        const z = new Set(); for (let i = 0; i < 300; i++) MW.rescue.makeRound().forEach(q => { if (q.left === 0 || q.right === 0) z.add(q.whole); });
        out[mc.join('-')] = Array.from(z).sort((a, b) => a - b); }); return out; }"""
    num_secure = [dict(a, mode="numbers") for a in secure_answers([(5, 1), (5, 2), (3, 1)])]
    ctx, page, problems2 = await seeded(browser, num_secure)
    got = await page.evaluate(rounds)
    check("numbers: zero bonds come up in numbers mode whichever check is set, once that number's other bonds are secure in numbers mode",
          got == {"numbers-auto": [3, 5], "numbers-tap": [3, 5], "counting-auto": [], "counting-tap": []}, json.dumps(got))
    await ctx.close()
    old_secure = secure_answers([(5, 1), (5, 2), (3, 1)])               # saved before 0.6.0: no mode, so counting mode's
    ctx, page, problems3 = await seeded(browser, old_secure)
    got = await page.evaluate(rounds)
    check("numbers: answers with no mode (saved before 0.6.0) count as counting mode's: they open zero bonds there, not in numbers mode",
          got == {"numbers-auto": [], "numbers-tap": [], "counting-auto": [], "counting-tap": [3, 5]}, json.dumps(got))
    # a numbers-mode round picks from numbers-mode progress
    secure = await page.evaluate("""() => { MW.store.setting('answerMode', 'numbers'); MW.rescue.st.mode = null; const out = new Set();
        for (let i = 0; i < 200; i++) MW.rescue.makeRound().forEach(q => out.add(q.status)); return Array.from(out).sort(); }""")
    check("numbers: a numbers-mode round picks from numbers-mode progress (nothing secure there yet)", secure == ["notyet"], json.dumps(secure))
    await ctx.close()
    check("numbers (bonds): no console errors", not (problems or problems2 or problems3), "; ".join((problems + problems2 + problems3)[:3]))
    await browser.close()


async def test_numbers_grownups(p):
    """Settings' 'How your child answers' (a change starts with the next round), and the Progress tab's switch."""
    print("\n== numbers mode: the grown-ups area ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "numbers-gu", 1046, 653, 1.22, mode="auto")
    old = secure_answers([(7, 3)]) + [ans(T0 + 5 * DAY, 5, 1, first=False)]              # counting mode's (no mode: before 0.6.0)
    new = [dict(a, mode="numbers") for a in secure_answers([(2, 1)])] + [dict(ans(T0 + 6 * DAY, 9, 4), mode="numbers")]
    push = "(a) => { const s = MW.store.get('answers'); a.forEach(x => s.push(x)); MW.store.save(); }"
    await page.evaluate(push, old)
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('progress')")
    await asyncio.sleep(0.4)
    grid = """(() => { const b = document.querySelector('.gu-body'), g = {};
        b.querySelectorAll('.gu-grid .mw-cell').forEach(c => { g[c.textContent.trim()] = c.className.split(' ').find(x => x.startsWith('is-')); });
        return { ways: Array.from(b.querySelectorAll('[data-way]')).map(x => [x.textContent, x.classList.contains('is-on')]),
                 lead: b.querySelector('.gu-lead').textContent, g: [g['3 + 4'], g['1 + 4'], g['1 + 1'], g['4 + 5']],
                 order: Array.from(b.children).map(e => e.className.split(' ')[0]).slice(0, 5),
                 table: !!b.querySelector('.gu-table'),
                 recent: Array.from(b.querySelectorAll('.gu-table tr')).slice(1).map(tr => [tr.children[1].textContent.split('   (')[0], tr.children[2].textContent]) }; })()"""
    a = await page.evaluate(grid)
    check("numbers: the Progress tab opens on the way set in Settings (MeeMee to count): its own secure and practising, and its recent answers",
          a["ways"] == [["MeeMee to count", True], ["Numbers", False]] and a["g"] == ["is-secure", "is-practising", "is-notyet", "is-notyet"]
          and a["lead"].startswith("Secure: 1 of 34 bonds. Practising: 1. Questions answered this way on this tablet: 4.")
          and sorted(r[0] for r in a["recent"]) == ["1 + ? = 5", "3 + ? = 7", "3 + ? = 7", "3 + ? = 7"], json.dumps(a))
    check("numbers: ... the switch sits above the grid (heading, switch, note, summary, grid)", a["order"] == ["gu-h3", "gu-row", "gu-p", "gu-p", "gu-grid"], json.dumps(a["order"]))
    await page.click(".gu-body [data-way=numbers]")
    await asyncio.sleep(0.3)
    b = await page.evaluate(grid)
    check("numbers: the switch on 'Numbers' with no numbers answers yet: 'No questions answered this way', and no table of the other way's answers",
          b["ways"] == [["MeeMee to count", False], ["Numbers", True]] and b["lead"] == "No questions answered this way on this tablet yet."
          and not b["table"] and b["g"] == ["is-notyet"] * 4, json.dumps(b))
    await page.evaluate(push, new)
    await page.evaluate("MW.grownups.show('progress')")       # the switch stays on Numbers
    await asyncio.sleep(0.3)
    b = await page.evaluate(grid)
    check("numbers: the switch on 'Numbers' shows numbers mode's grid: 1 + 1 secure, 4 + 5 practising, 3 + 4 not yet",
          b["ways"] == [["MeeMee to count", False], ["Numbers", True]] and b["g"] == ["is-notyet", "is-notyet", "is-secure", "is-practising"]
          and b["lead"].startswith("Secure: 1 of 34 bonds. Practising: 1. Questions answered this way on this tablet: 4."), json.dumps(b))
    check("numbers: ... and only the answers given with numbers in the recent answers",
          sorted(r[0] for r in b["recent"]) == ["1 + ? = 2", "1 + ? = 2", "1 + ? = 2", "4 + ? = 9"] and all(r[1] == "First time (tap Scruffles)" for r in b["recent"]),
          json.dumps(b["recent"]))
    await page.screenshot(path=str(SHOTS / "numbers-gu-progress-switch.png"))
    await page.click(".gu-body [data-way=counting]")
    await asyncio.sleep(0.3)
    a = await page.evaluate(grid)
    check("numbers: back on 'MeeMee to count': counting's grid and only counting's recent answers", a["g"] == ["is-secure", "is-practising", "is-notyet", "is-notyet"]
          and sorted(r[0] for r in a["recent"]) == ["1 + ? = 5", "3 + ? = 7", "3 + ? = 7", "3 + ? = 7"], json.dumps(a))
    await page.evaluate("MW.grownups.close()")

    # a change of mode starts with the next round
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 20)
    look = await n_look(page)
    check("numbers: a counting round looks as before (pills, the asteroid, no track)", look["look"] == "counting" and look["pills"] == 2 and look["tray"]
          and not look["track"] and look["counters"] == 13, json.dumps(look))
    await t.tap(46, 754, 3.3)                                # the grown-ups lock
    await page.evaluate("MW.grownups.show('settings')")
    await asyncio.sleep(0.3)
    await page.click(".gu-body [data-way=numbers]")
    await asyncio.sleep(0.2)
    on = await page.evaluate("[MW.store.setting('answerMode'), Array.from(document.querySelectorAll('.gu-body [data-way]')).map(x => x.classList.contains('is-on'))]")
    check("numbers: 'Numbers' in Settings is saved with Rescue's settings", on == ["numbers", [False, True]], json.dumps(on))
    await page.click(".gu-close")
    await asyncio.sleep(0.6)
    look = await n_look(page)
    check("numbers: ... but this round carries on counting", look["look"] == "counting" and look["tray"] and not look["track"]
          and await page.evaluate("MW.rescue.mode()") == "counting", json.dumps(look))
    await t.fill(4, "right")
    s = await t.wait_phase(["celebrate"], 3)
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check("numbers: ... and its answers are saved as counting", s["phase"] == "celebrate" and rec["mode"] == "counting", json.dumps(rec))
    await t.wait_phase(["open"], 20)
    look = await n_look(page)
    check("numbers: ... to the end of the round (question 2 still counting)", look["look"] == "counting" and look["tray"], json.dumps(look))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 20)
    look = await n_look(page)
    st = await n_state(page)
    check("numbers: the next round is in numbers mode", look["look"] == "numbers" and not look["tray"] and look["track"] and st["carried"] == [7, 3, None], json.dumps([look, st]))
    # and back to counting: exactly as before
    await page.evaluate("MW.store.setting('answerMode', 'counting')")
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 20)
    look = await n_look(page)
    vis = await page.evaluate("Array.from(document.querySelectorAll('#screen-game .mw-numbered')).filter(e => getComputedStyle(e).display !== 'none').length")
    check("numbers: switched back, the counting look returns (pills, asteroid, no numbered MeeMee, no track)",
          look["look"] == "counting" and look["pills"] == 2 and look["tray"] and not look["track"] and vis == 0, json.dumps([look, vis]))
    check("numbers (grown-ups): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_numbers_pause(p):
    """Home and pausing mid-drag; a hint cut short; a zero bond; reduce motion."""
    print("\n== numbers mode: pausing, Home, zero bonds ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "numbers-pause", 1046, 653, 1.22, mode="tap")
    zround = [{"whole": 5, "left": 5, "right": 0, "missing": "right"},
              {"whole": 6, "left": 0, "right": 6, "missing": "whole"},
              {"whole": 4, "left": 1, "right": 3, "missing": "left"},
              {"whole": 3, "left": 3, "right": 0, "missing": "right"},
              {"whole": 2, "left": 1, "right": 1, "missing": "right"}]
    await page.evaluate("MW.store.setting('answerMode', 'numbers'); MW.rescue.nextRound = %s" % json.dumps(zround))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.start_round()
    await t.wait_phase(["open"], 20)
    await n_quiet(t)
    # a placed tile picked up again, then the screen goes off: it goes back into the circle
    await t.drag(*tile_xy(3), 550, 470)
    await n_hold(t, 550, 470, 800, 300, touch_id=41)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.5)
    held = await page.evaluate("[MW.rescue.st.paused, MW.rescue.track().tile(3).x, MW.rescue.track().tile(3).y, MW.rescue.st.placed && MW.rescue.st.placed.n]")
    n0 = len(await t.said())
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.6)
    said = await t.said()
    check("numbers: the screen going off mid-drag puts the tile back where it was (in the circle)", held == [True, 550, 470, 3], json.dumps(held))
    check("numbers: coming back asks the question again", said[n0:][:1] == ["q-lets-make num-end-5 q-weve-got num-end-5 q-how-many-more rescue-find-number tap-scruffles"], str(said[n0:]))
    # a tile from the track held as the screen goes off: back to its place
    await n_quiet(t)
    await n_hold(t, *tile_xy(7), 700, 300, touch_id=42)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.4)
    st = await n_state(page)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.5)
    check("numbers: a tile held from the track as the screen goes off goes back to its place (not a try)", st["out"] == [3] and st["tries"] == 0 and st["misses"] == 0, json.dumps(st))
    # a zero bond: 5 + ? = 5 is answered with the 0 tile
    await n_quiet(t)
    await t.drag(*tile_xy(0), 550, 470)
    st = await n_state(page)
    check("numbers: the 0 tile replaces the 3", st["placed"] == 0 and st["out"] == [0], json.dumps(st))
    await n_check(t)
    st = await n_state(page)
    check("numbers: 5 + ? = 5 answered with the 0 tile and a tap", st["phase"] == "celebrate" and st["carried"] == [5, 5, 0], json.dumps(st))
    await n_wait(t, "MW.events.some(e => e.type === 'say' && e.detail === 'num-mid-5 and num-mid-0 make num-end-5')", 10)
    eq = await page.inner_text("#screen-game .mw-equation")
    check("numbers: ... the number sentence 5 + 0 = 5", eq.replace("\n", " ").split() == ["5", "+", "0", "=", "5"], eq)
    # 0 + 6 = ?: the answer is 6
    await t.wait_phase(["open"], 20)
    st = await n_state(page)
    check("numbers: 0 + 6 = ?: a numbered MeeMee carrying 0, one carrying 6, the whole waits", st["carried"] == [None, 0, 6], json.dumps(st))
    # two wrong numbers, then Hear-again cuts the hint short: it is taken away (back to numbered MeeMee) and comes back next time
    await n_quiet(t)
    await t.drag(*tile_xy(5), 380, 205); await n_check(t); await asyncio.sleep(1.2)
    await t.drag(*tile_xy(7), 380, 205); await n_check(t)
    st = await n_state(page)
    check("numbers: two wrong numbers for 0 + 6 bring 'Count them with me.' (6 MeeMee, 6 ghosts)", st["hinted"] and st["fixed"] == 6 and st["ghosts"] == 6 and st["carried"] == [None, None, None], json.dumps(st))
    await asyncio.sleep(0.6)
    await t.tap(*HEAR)
    await asyncio.sleep(0.5)
    st = await n_state(page)
    check("numbers: Hear-again during the hint takes it away: the numbered MeeMee come back", not st["hinted"] and st["fixed"] == 0 and st["ghosts"] == 0 and st["carried"] == [None, 0, 6], json.dumps(st))
    await n_quiet(t)
    await t.drag(*tile_xy(4), 380, 205); await n_check(t)
    st = await n_state(page)
    check("numbers: the next wrong number gives the hint again", st["hinted"] and st["fixed"] == 6, json.dumps(st))
    await t.drag(*tile_xy(6), 380, 205); await n_check(t)
    st = await n_state(page)
    check("numbers: 0 + 6 = ? answered with 6", st["phase"] == "celebrate" and st["carried"] == [6, 0, 6], json.dumps(st))
    await t.wait_phase(["open"], 20)
    await t.drag(*tile_xy(1), 210, 470); await n_check(t)    # ? + 3 = 4
    check("numbers: ? + 3 = 4 answered with tile 1", (await n_state(page))["phase"] == "celebrate")
    s4 = await t.wait_phase(["open"], 20)
    p4 = await page.evaluate("JSON.stringify(MW.rescue.st.prompt)")
    check("numbers: with tap Scruffles a zero answer later in the round still ends with 'Tap Scruffles when you're ready.' (as Settings says; no 'Find the number.')",
          s4["qi"] == 3 and p4 == json.dumps([["q-lets-make", "num-end-3"], ["q-weve-got", "num-end-3"], ["q-how-many-more"], ["tap-scruffles"]]).replace(" ", ""), p4)
    # Home mid-drag: nothing is said after, every tile is back in its place
    await n_hold(t, *tile_xy(2), 600, 500, touch_id=43)
    await page.evaluate("MW.rescue.home()")
    n0 = len(await t.said())
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.6)
    st = await n_state(page)
    check("numbers: Home while a tile is held: nothing is said, the map shows, the tiles are all back", len(await t.said()) == n0 and st["screen"] == "screen-map"
          and st["out"] == [] and st["placed"] is None, json.dumps(st))
    check("numbers (pausing): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_numbers_motion(p):
    """Reduce motion in numbers mode: tiles jump rather than glide, the numbered MeeMee fades in, the track fades away."""
    print("\n== numbers mode: reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce")
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)   # all loaded before closing
    got = await page.evaluate("""(() => { MW.store.setting('answerMode', 'numbers'); MW.store.setting('check', 'auto'); MW.store.setting('checkPicked', true);
        const R = MW.rescue; R.ask({ whole: 7, left: 3, right: 4, missing: 'right' }); const tr = R.track(), c = MW.LAYOUT.right;
        R.drop(tr.tile(2), c.x, c.y, false);
        const wrong = [tr.tile(2).el.classList.contains('is-moving'), tr.tile(2).out()];
        R.drop(tr.tile(4), c.x, c.y, false);
        const pop = Array.from(document.querySelectorAll('#screen-game .mw-numbered.is-popping')).map(e => getComputedStyle(e).animationName);
        const t = getComputedStyle(tr.el);
        return { wrong: wrong, pop: pop, away: tr.away(), transform: t.transform, transition: t.transitionProperty }; })()""")
    await asyncio.sleep(0.5)
    op = await page.evaluate("getComputedStyle(MW.rescue.track().el).opacity")
    check("numbers (reduce motion): a wrong tile goes straight back (no glide)", got["wrong"] == [False, False], json.dumps(got))
    check("numbers (reduce motion): the numbered MeeMee fades in rather than popping up", got["pop"] == ["mw-arrive"], json.dumps(got))
    check("numbers (reduce motion): the track fades away rather than sliding", got["away"] and got["transform"] == "none" and op == "0", json.dumps([got, op]))
    await page.evaluate("MW.world.home()")
    peek = await page.evaluate("""(() => { const d = document.createElement('div'); d.className = 'mw-peek rescue-peek-flip'; d.innerHTML = '<div class="mw-peek-inner"></div>';
        document.body.appendChild(d); const c = getComputedStyle(d.firstChild), out = [c.transform, c.scale, c.transitionProperty]; d.remove(); return out; })()""")
    check("numbers (reduce motion): the mirrored lookout fades in rather than rising, and stays mirrored", peek == ["none", "-1 1", "opacity"], json.dumps(peek))
    check("numbers (reduce motion): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def n_says_after(t, n0):
    return (await t.said())[n0:]


async def test_numbers_taps(p):
    """Taps on Scruffles while he talks after a check (numbers mode, and counting mode as before), 'Find the number.'
    not recorded, and Home or the grown-ups area mid-celebration and mid-hint, in numbers mode."""
    print("\n== numbers mode: taps while Scruffles talks; Home and pauses mid-celebration and mid-hint ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "numbers-taps", 1280, 800, 1, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    # "Find the number." not recorded yet (pending): it is left out, and the question and the tap line are still said
    await page.evaluate("delete MW.audio.manifest.voice['rescue-find-number']; MW.store.setting('answerMode', 'numbers'); MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.start_round()
    await t.wait_phase(["open"], 20)
    said = await t.said()
    fails = await page.evaluate("MW.events.filter(e => e.type === 'audio-fail').map(e => e.detail)")
    check("numbers: with 'Find the number.' not recorded, the question and the tap line are still said",
          said[-1:] == ["q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more tap-scruffles"] and not fails, json.dumps([said[-2:], fails]))
    await n_quiet(t)

    # a double tap: the first checks a wrong number, the second (no tile now) waits for "Let's try again."
    await t.drag(*tile_xy(5), 550, 470)
    n0 = len(await t.said())
    await w_double_tap(t, *POD)
    await asyncio.sleep(0.3)
    talking = await page.evaluate("MW.audio.speaking()")
    await n_quiet(t)
    st = await n_state(page)
    check("numbers: a double tap on Scruffles (a wrong number, then no tile): 'Let's try again.' plays to the end, the question isn't asked again, one try",
          talking and await n_says_after(t, n0) == ["again-try-again"] and st["tries"] == 1 and not st["hinted"], json.dumps([await n_says_after(t, n0), st]))
    # once he's quiet, a tap with no tile asks the question again (not a try)
    n0 = len(await t.said())
    await n_check(t)
    check("numbers: once he's quiet, a tap with no tile asks the question again", (await n_says_after(t, n0))[:1] == said[-1:]
          and (await n_state(page))["tries"] == 1, json.dumps(await n_says_after(t, n0)))
    await n_quiet(t)
    # the second wrong number brings the hint; a double tap and a single tap during it leave it in place
    await t.drag(*tile_xy(6), 550, 470)
    n0 = len(await t.said())
    await w_double_tap(t, *POD)
    await asyncio.sleep(0.6)
    await t.tap(*POD)
    await asyncio.sleep(0.4)
    mid = await n_state(page)
    await n_quiet(t)
    st = await n_state(page)
    says = await n_says_after(t, n0)
    check("numbers: a double tap that brings the hint, then another tap during it: the hint plays to the end and stays",
          says == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"] and mid["hinted"] and st["hinted"] and st["fixed"] == 3
          and st["ghosts"] == 4 and st["lit"] == 4 and st["carried"] == [7, None, None] and st["tries"] == 2, json.dumps([says, st]))
    # right, then Home in the middle of the celebration: nothing more is said, the map shows, the next round is as new
    await t.drag(*tile_xy(4), 550, 470)
    await n_check(t)
    check("numbers: tile 4 completes it", (await n_state(page))["phase"] == "celebrate")
    await t.tap(*HOME)
    n0 = len(await t.said())
    await asyncio.sleep(3)
    st = await n_state(page)
    check("numbers: Home mid-celebration: back on the map, nothing more said (no number sentence), the tiles all back",
          st["screen"] == "screen-map" and await n_says_after(t, n0) == [] and st["out"] == [] and st["placed"] is None, json.dumps([await n_says_after(t, n0), st]))
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 20)
    st = await n_state(page)
    check("numbers: ... and the next round starts as new, the track back", st["qi"] == 0 and st["carried"] == [7, 3, None] and not st["away"] and st["tries"] == 0, json.dumps(st))
    await n_quiet(t)
    # a single impatient tap during "Let's try again."
    await t.drag(*tile_xy(2), 550, 470)
    await n_check(t)
    n0 = len(await t.said())
    await asyncio.sleep(0.2)
    await t.tap(*POD)
    await n_quiet(t)
    st = await n_state(page)
    check("numbers: a single tap during 'Let's try again.' does nothing (the line isn't cut off, the question isn't asked again)",
          await n_says_after(t, n0) == [] and st["tries"] == 1, json.dumps([await n_says_after(t, n0), st]))
    # the grown-ups area opened mid-hint: the hint is taken away (as in counting mode) and comes back in full next time
    await t.drag(*tile_xy(6), 550, 470)
    await n_check(t)
    await asyncio.sleep(0.6)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    await asyncio.sleep(0.6)
    st = await n_state(page)
    check("numbers: the grown-ups area opened mid-hint: the hint stops and is taken away (numbered MeeMee back)", not st["hinted"] and st["fixed"] == 0
          and st["ghosts"] == 0 and st["carried"] == [7, 3, None] and not await page.evaluate("MW.audio.speaking()"), json.dumps(st))
    n0 = len(await t.said())
    await page.click(".gu-close")
    await asyncio.sleep(0.6)
    check("numbers: ... closed, the question is asked again", (await n_says_after(t, n0))[:1] == ["q-lets-make num-end-7 q-weve-got num-end-3 q-how-many-more tap-scruffles"],
          json.dumps(await n_says_after(t, n0)))
    await n_quiet(t)
    await t.drag(*tile_xy(7), 550, 470)
    await n_check(t)
    st = await n_state(page)
    check("numbers: ... and the next wrong number gives the hint again", st["hinted"] and st["fixed"] == 3, json.dumps(st))
    await n_quiet(t)
    # the grown-ups area opened mid-celebration: everything waits, then carries on
    await t.drag(*tile_xy(4), 550, 470)
    await n_check(t)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    n0 = len(await t.said())
    await asyncio.sleep(2.5)
    st = await n_state(page)
    check("numbers: the grown-ups area opened mid-celebration: nothing is said while it's open, the answer stays",
          st["phase"] == "celebrate" and st["carried"] == [7, 3, 4] and await n_says_after(t, n0) == [], json.dumps([await n_says_after(t, n0), st]))
    await page.click(".gu-close")
    ok = await n_wait(t, "MW.events.some(e => e.type === 'say' && e.detail === 'num-mid-3 and num-mid-4 make num-end-7')", 10)
    s = await t.wait_phase(["open"], 20)
    st = await n_state(page)
    check("numbers: ... closed, the celebration carries on (the number sentence), then question 2 with the track back",
          ok and s["qi"] == 1 and st["carried"] == [None, 2, 3] and not st["away"], json.dumps(st))

    # counting mode, as before: a tap during the hint leaves it in place
    await page.evaluate("MW.store.setting('answerMode', 'counting')")
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 20)
    await n_quiet(t)
    await t.fill(2, "right")
    n0 = len(await t.said())
    await w_double_tap(t, *POD)                              # two wrong checks (too few): the second brings the hint
    await asyncio.sleep(0.6)
    await w_double_tap(t, *POD)                              # and more taps during the hint
    await asyncio.sleep(0.4)
    await t.tap(*POD)
    await n_quiet(t)
    says = await n_says_after(t, n0)
    st = await t.state()
    hint = await page.evaluate("[MW.rescue.st.hinted, document.querySelectorAll('#screen-game .mw-ghost').length, document.querySelectorAll('#screen-game .mw-ghost.is-lit').length]")
    check("counting: a double tap with too few is two wrong checks (the hint), and taps during the hint leave it in place, as before",
          says[-1:] == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"] and len(says) <= 2 and hint == [True, 2, 2]
          and st["placed"] == 2 and await page.evaluate("MW.rescue.st.tries") >= 2, json.dumps([says, hint, st]))
    check("numbers (taps): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


LOOKOUT_LOOK = """(() => { const b = document.querySelector('#screen-game [data-moment=lookout].is-shown'); if (!b) return null;
    const i = b.querySelector('.mw-peek-inner'), mid = e => { const r = e.getBoundingClientRect(); return (r.left + r.right) / 2; };
    return { scale: getComputedStyle(i).scale, flip: b.classList.contains('rescue-peek-flip'),
             scopeLeft: mid(i.querySelector('.mw-held-scope')) < mid(i.firstElementChild),
             window: [b.offsetLeft, b.offsetTop, b.offsetWidth, b.offsetHeight] }; })()"""


async def test_numbers_decided(p, name, vw, vh, dpr):
    """Barney's two decisions (11 October): no hint for a zero answer in numbers mode, and the lookout mirrored in numbers
    mode (looking towards the diagram)."""
    print(f"\n== numbers mode: no hint for a zero answer; the lookout mirrored ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"numbers-decided-{name}", vw, vh, dpr, mode="tap")
    zround = [{"whole": 5, "left": 5, "right": 0, "missing": "right"},
              {"whole": 6, "left": 0, "right": 6, "missing": "whole"},
              {"whole": 4, "left": 1, "right": 3, "missing": "left"},
              {"whole": 3, "left": 3, "right": 0, "missing": "right"},
              {"whole": 2, "left": 1, "right": 1, "missing": "right"}]
    await page.evaluate("MW.store.setting('answerMode', 'numbers'); MW.crew.save({moggles: 'lookout', snuffles: null}); MW.rescue.nextRound = %s" % json.dumps(zround))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await t.tap(*RESCUE)
    await t.wait_screen("screen-game", 6)
    await asyncio.sleep(1.2)
    look = await page.evaluate(LOOKOUT_LOOK)
    check(f"numbers ({name}): the lookout is mirrored in numbers mode, its telescope towards the diagram, in the same window (906, 519, 250 x 175)",
          look is not None and look["scale"] == "-1 1" and look["flip"] and look["scopeLeft"] and look["window"] == [906, 519, 250, 175], json.dumps(look))
    await page.screenshot(path=str(SHOTS / f"{name}-lookout-numbers.png"))

    # 5 + ? = 5: two and three wrong numbers, and never the hint
    await t.wait_phase(["open"], 20)
    await n_quiet(t)
    n0 = len(await t.said())
    sts = []
    for tile in (3, 2, 4):
        await t.drag(*tile_xy(tile), 550, 470)
        await n_check(t)
        await n_quiet(t)
        sts.append(await n_state(page))
    says = (await t.said())[n0:]
    two, three = sts[1], sts[2]
    check(f"numbers ({name}): 5 + ? = 5, two wrong numbers: 'Let's try again.' each time, the tile back, and no hint (no MeeMee or ghosts, no counting on)",
          two["tries"] == 2 and not two["hinted"] and two["fixed"] == 0 and two["ghosts"] == 0 and two["carried"] == [5, 5, None] and two["out"] == []
          and says[:2] == ["again-try-again", "again-try-again"], json.dumps([says, two]))
    check(f"numbers ({name}): ... and a third: the same, still no hint", three["tries"] == 3 and not three["hinted"] and three["fixed"] == 0 and three["ghosts"] == 0
          and three["carried"] == [5, 5, None] and says == ["again-try-again"] * 3 and not any("count" in x for x in says), json.dumps([says, three]))
    await t.drag(*tile_xy(0), 550, 470)
    await n_check(t)
    st = await n_state(page)
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check(f"numbers ({name}): ... then the 0 tile completes it (saved with 3 wrong numbers and no hint)", st["phase"] == "celebrate" and rec["tries"] == 3 and rec["hint"] is False, json.dumps(rec))
    # 0 + 6 = ?: a non-zero answer still gets the hint on the second wrong number
    await t.wait_phase(["open"], 20)
    await n_quiet(t)
    await t.drag(*tile_xy(5), 380, 205)
    await n_check(t)
    await n_quiet(t)
    await t.drag(*tile_xy(7), 380, 205)
    await n_check(t)
    st = await n_state(page)
    check(f"numbers ({name}): 0 + 6 = ? (answer 6): the second wrong number still brings the hint", st["hinted"] and st["tries"] == 2 and st["fixed"] == 6
          and any(x.startswith("again-count-with-me") for x in await t.said()), json.dumps(st))
    # with 'as soon as it's right', tiles dropped away from a zero answer's circle don't bring the hint either
    got = await page.evaluate("""(() => { MW.store.setting('check', 'auto'); const R = MW.rescue; R.ask({ whole: 5, left: 5, right: 0, missing: 'right' });
        const tr = R.track(); R.drop(tr.tile(7), 900, 330, false); R.drop(tr.tile(8), 900, 330, false); R.drop(tr.tile(2), 550, 470, false);
        const s = R.st; return [s.misses, s.tries, s.hinted, s.fixed.length, document.querySelectorAll('#screen-game .mw-ghost').length]; })()""")
    check(f"numbers ({name}): with 'as soon as it's right', two misses and a wrong number on a zero answer: no hint", got == [2, 1, False, 0, 0], json.dumps(got))
    await page.evaluate("MW.store.setting('check', 'tap')")

    # counting mode: the lookout as before, not mirrored, looking left from behind the asteroid
    await page.evaluate("MW.store.setting('answerMode', 'counting')")
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_screen("screen-game", 6)
    await asyncio.sleep(1.2)
    look = await page.evaluate(LOOKOUT_LOOK)
    check(f"counting ({name}): the lookout isn't mirrored, as before (telescope to the right, over the asteroid)",
          look is not None and look["scale"] == "none" and not look["flip"] and not look["scopeLeft"] and look["window"] == [690, 390, 250, 175], json.dumps(look))
    await page.screenshot(path=str(SHOTS / f"{name}-lookout-counting.png"))
    check(f"numbers ({name}, decided): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def main():
    srv = serve()
    async with async_playwright() as p:
        await test_device(p, "fire", 1046, 653, 1.22)
        await test_device(p, "doogee", 1280, 800, 2)
        await test_tap_mode(p)
        await test_switch(p)
        await test_map(p)
        await test_zero(p)
        await test_bonds(p)
        await test_grid(p)
        await test_crew(p)
        await test_crew(p, "crew-fire", 1046, 653, 1.22)
        await test_moments(p)
        await test_carryover(p)
        await test_template(p)
        await test_edge_cases(p)
        await test_portrait(p)
        await test_reduce_motion(p)
        await test_words_round(p, "fire", 1046, 653, 1.22)
        await test_words_round(p, "doogee", 1280, 800, 2)
        await test_words_pause(p)
        await test_words_steps(p)
        await test_words_grownups(p)
        await test_words_first_find(p)
        await test_words_fixes(p)
        await test_words_motion(p)
        await test_words_sounds(p)
        await test_words_weeks(p)
        await test_words_lights(p, "fire", 1046, 653, 1.22)
        await test_words_lights(p, "doogee", 1280, 800, 2)
        await test_words_moments(p, "fire", 1046, 653, 1.22)
        await test_words_moments(p, "doogee", 1280, 800, 2)
        await test_words_moments_motion(p)
        await test_words_allweeks_tab(p)
        await test_words_newwords(p, "fire", 1046, 653, 1.22)
        await test_words_newwords(p, "doogee", 1280, 800, 2)
        await test_banners(p, "fire", 1046, 653, 1.22)
        await test_banners(p, "doogee", 1280, 800, 2)
        await test_banner_motion(p)
        await test_banner_unrecorded(p)
        await test_kit_pieces(p, "fire", 1046, 653, 1.22)
        await test_kit_pieces(p, "doogee", 1280, 800, 2)
        await test_numbers_round(p, "fire", 1046, 653, 1.22)
        await test_numbers_round(p, "doogee", 1280, 800, 2)
        await test_numbers_auto(p)
        await test_numbers_bonds(p)
        await test_numbers_grownups(p)
        await test_numbers_pause(p)
        await test_numbers_motion(p)
        await test_numbers_taps(p)
        await test_numbers_decided(p, "fire", 1046, 653, 1.22)
        await test_numbers_decided(p, "doogee", 1280, 800, 2)
    srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
