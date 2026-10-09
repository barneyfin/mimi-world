"""Headless checks for MeeMee World (phase 4): the map, a round, the bonds and the kit, on Fire and Doogee screen sizes.

    python tools/tests/test_game.py            run everything, screenshots into tools/tests/shots/

Uses Playwright's Chromium with touch input sent through the DevTools protocol, the way a finger would.
"""
import asyncio
import functools
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
LOCKED = (1010, 560)                  # a planet still to come


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
    caption = await page.inner_text("#screen-start .mw-caption")
    check("map: the start screen says MeeMee World", caption == "MeeMee World", caption)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    nav = await page.evaluate("[document.querySelectorAll('#screen-map [aria-label=Home]').length, document.querySelectorAll('#screen-map .mw-music').length]")
    check("map: a music button and no Home button", nav == [0, 1], str(nav))
    sizes = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-planet')).map(b => b.offsetWidth)")
    check("map: every planet is a big target (at least 120 stage px)", sizes and min(sizes) >= 120, str(sizes))
    await asyncio.sleep(1.5)
    await t.tap(*LOCKED)
    await asyncio.sleep(0.3)
    said = await t.said()
    check("map: a locked planet says 'That planet isn't ready yet.'", said[-1:] == ["map-not-ready"] and await page.evaluate("MW.shell.screen") == "screen-map", str(said[-2:]))
    await asyncio.sleep(1.5)
    await t.tap(1150, 250)
    await asyncio.sleep(0.3)
    check("map: so does the other one", (await t.said())[-1:] == ["map-not-ready"])
    await asyncio.sleep(1.5)
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
    await asyncio.sleep(2.5)
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
             "Zero bonds (marked *) come up only once the other bonds of that number are secure, and only when the answer",
             "is checked by tapping Scruffles.", "",
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
        await test_edge_cases(p)
        await test_portrait(p)
        await test_reduce_motion(p)
    srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
