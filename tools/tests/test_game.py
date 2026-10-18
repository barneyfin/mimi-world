"""Headless checks for MeeMee World: the map, the crew, MeeMee Rescue (a round, the bonds), MeeMee Rockets (the tricky-words
game; 0.7.0: autumn 2, the half-term switch, capitals), the kit (0.6.0: the title banners, the store, stars, pick-up boxes,
numbers mode's pieces; 0.8.0: the map's five places and the minus sentence; 0.9.0: the commander and its moment, the crew's
got-it face, the redrawn station and the grown-ups tab row), MeeMee Rescue's numbers mode (0.6.0), Take MeeMee Home
(0.8.0: subtraction, its three steps, its progress and its grown-ups tab) and MeeMee Station (0.9.0: the ten frame and the
bar model, its three steps, the commander's smile, its progress and its grown-ups tab), on Fire and Doogee screen sizes.

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
    n0 = len(await t.said())
    await t.tap(1030, 300)                                   # tap Scruffles with 2 (too few), twice in quick succession
    await asyncio.sleep(0.12)
    await t.tap(1030, 300)
    await asyncio.sleep(0.6)
    s = await t.state()
    waited = await page.evaluate("MW.events.some(e => e.type === 'check' && e.detail === 'still answering')")
    check("tap: too few says 'Let's look again.'; a double tap is one try, the second tap does nothing while he is answering (0.8.1)",
          (await t.said())[n0:] == ["again-look-again"] and waited and await page.evaluate("MW.rescue.st.tries") == 1, json.dumps(s))
    await n_quiet(t)
    await t.fill(4, "right")                                 # 6 > 4
    s = await t.state()
    check("tap: six MeeMee can go in (no auto-complete)", s["placed"] == 6 and s["phase"] == "open", json.dumps(s))
    await t.tap(1030, 300)
    await asyncio.sleep(0.6)
    check("tap: too many says 'That's too many. Take one back.'", "too-many" in await t.said())
    placed = await page.evaluate("MW.rescue.st.counters.filter(c => c.where === 'right').map(c => [c.x, c.y])")
    for x, y in placed[:3]:
        await t.drag(x, y, 1000, 640)
    await n_quiet(t)                                         # a tap while he is still answering does nothing (0.8.1)
    await t.tap(1030, 300)
    await asyncio.sleep(0.8)
    check("tap: third wrong check plays the counting-on hint", any(x.startswith("q-count-on-from num-end-3") for x in await t.said()))
    await t.fill(1, "right")
    await n_quiet(t)                                         # the hint is still being said: a tap waits for it (0.8.1)
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
    locked = await page.evaluate(MAP_LOCKED_LINE)            # "That place isn't ready yet." once recorded (0.8.1), the old line before
    if empty:
        await t.tap(empty[0]["x"], empty[0]["y"])
        await asyncio.sleep(0.3)
        said = await t.said()
        check(f"map: a locked planet says its locked line ({locked})", said[-1:] == [locked] and await page.evaluate("MW.shell.screen") == "screen-map", str(said[-2:]))
        await asyncio.sleep(1.5)
    else:
        check("map: a locked planet says its locked line", True, "skipped: every planet has a game")
    if len(empty) > 1:
        await t.tap(empty[1]["x"], empty[1]["y"])
        await asyncio.sleep(0.3)
        check("map: so does the other one", (await t.said())[-1:] == [locked])
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
    await n_quiet(t)                                         # a tap while he is still answering does nothing (0.8.1)
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
STATION = {"lookout": (175, 640), "engineer": (485, 640), "navigator": (795, 640), "commander": (1105, 640)}   # 0.9.0: the commander in the cook's place
SHOTS9 = SHOTS / "0.9.0"                    # 0.9.0's screenshots: the commander, the got-it face, the station, the tab row
SHOTS9.mkdir(exist_ok=True)
# "commander." (job-commander) is pending until Barney records it. These make the page treat it as pending (false) or
# recorded (true), whichever it really is, as the place line's stubs do (0.8.0)
COMMANDER_LINE = """(on => { if (!window.__recordedJob) window.__recordedJob = MW.audio.recorded;
    MW.audio.recorded = id => id === 'job-commander' ? on : window.__recordedJob(id); })"""
UNSTUB_COMMANDER_LINE = "(() => { if (window.__recordedJob) { MW.audio.recorded = window.__recordedJob; delete window.__recordedJob; } })()"
# each job station on the crew screen: its job, its left edge, and whether its picture is the kit's drawing for that job
STATIONS_INFO = """Array.from(document.querySelectorAll('#screen-crew .mw-station')).map(e => [e.dataset.job, e.offsetLeft,
    e.querySelector('.mw-station-disc svg').innerHTML === document.getElementById('art-job-' + e.dataset.job).content.firstElementChild.innerHTML])"""


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
    stations = await page.evaluate(STATIONS_INFO)
    check(f"{name}: four job stations: lookout, engineer, navigator and commander (0.9.0: the radio, where the cook's frying pan was), each with its job's picture",
          stations == [["lookout", 40, True], ["engineer", 350, True], ["navigator", 660, True], ["commander", 970, True]], json.dumps(stations))
    if name == "crew":
        await page.screenshot(path=str(SHOTS / "crew-1-no-jobs.png"))
    await page.evaluate(COMMANDER_LINE + "(false)")             # as while "commander." is pending
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
    n = len(await t.said())
    await t.drag(x, y, *STATION["commander"])
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: Snuffles onto the radio is the commander", st["jobs"] == {"moggles": "lookout", "snuffles": "commander"}
          and st["taken"] == ["lookout", "commander"] and "snuffles:commander" in st["badges"], json.dumps(st))
    check(f"{name}: while 'commander.' is pending, 'Snuffles is the commander.' isn't said at all (never half a sentence); 'The crew are ready!' still is",
          (await t.said())[n:] == ["crew-ready"], str((await t.said())[n:]))
    check(f"{name}: with both jobs given, Home pulses (back to the map)", st["pulse"])
    if name == "crew":
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SHOTS / "crew-2-jobs.png"))
    await asyncio.sleep(2.5)
    # Moggles onto Snuffles's job: they swap
    x, y = await cat_at(page, "moggles")
    await t.drag(x, y, *STATION["commander"])
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: one job per cat: onto the other cat's job, they swap", st["jobs"] == {"moggles": "commander", "snuffles": "lookout"}, json.dumps(st))
    check(f"{name}: both new jobs are said (the commander's sentence left out while its line is pending)",
          (await t.said())[-1:] == ["name-snuffles is-the job-lookout crew-ready"], str((await t.said())[-1:]))
    await asyncio.sleep(0.6)
    await screenshot(page, f"0.9.0/{'doogee' if name == 'crew' else 'fire'}-crew-commander.png")   # as board Crew12
    await asyncio.sleep(3.5)
    # a drop between the stations' rows (off the bottom half) takes the job off
    x, y = await cat_at(page, "snuffles")
    await t.drag(x, y, 640, 300)
    await asyncio.sleep(0.5)
    st = await crew_state(page)
    check(f"{name}: a cat put back on the deck has no job", st["jobs"] == {"moggles": "commander", "snuffles": None} and not st["pulse"], json.dumps(st))
    back = await cat_at(page, "snuffles")
    check(f"{name}: ... and goes back to its place on the deck", abs(back[0] - DECK["snuffles"][0]) < 3 and abs(back[1] - DECK["snuffles"][1]) < 6, str(back))
    x, y = await cat_at(page, "snuffles")
    await t.drag(x, y, *STATION["engineer"])
    await asyncio.sleep(2.5)
    n = len(await t.said())
    x, y = await cat_at(page, "snuffles")
    await t.tap(x, y)
    await asyncio.sleep(0.5)
    check(f"{name}: tapping a cat says its job", (await t.said())[n:] == ["name-snuffles is-the job-engineer"], str((await t.said())[n:]))
    await asyncio.sleep(0.3)
    n = len(await t.said())
    x, y = await cat_at(page, "moggles")
    await t.tap(x, y)
    await asyncio.sleep(0.5)
    check(f"{name}: tapping the commander says nothing while 'commander.' is pending, and doesn't cut off what was being said",
          (await t.said())[n:] == [] and await page.evaluate("MW.audio.speaking()"), str((await t.said())[n:]))
    await asyncio.sleep(2)
    await t.tap(1208, 68)                                    # Hear it again
    await asyncio.sleep(0.4)
    check(f"{name}: Hear-again says each cat's job (the commander's left out while its line is pending)",
          (await t.said())[-1:] == ["name-snuffles is-the job-engineer"], str((await t.said())[-1:]))
    # once "commander." is recorded (stubbed), the commander's sentence is said like every job's
    await page.evaluate(COMMANDER_LINE + "(true)")
    await asyncio.sleep(1.6)
    n = len(await t.said())
    x, y = await cat_at(page, "moggles")
    await t.tap(x, y)
    await asyncio.sleep(0.5)
    tapped = (await t.said())[n:]
    await t.tap(1208, 68)
    await asyncio.sleep(0.4)
    heard = (await t.said())[-1:]
    x, y = await cat_at(page, "moggles")
    await t.drag(x, y, 640, 300)                             # off the job, and back onto the radio
    await asyncio.sleep(0.6)
    x, y = await cat_at(page, "moggles")
    n2 = len(await t.said())
    await t.drag(x, y, *STATION["commander"])
    await asyncio.sleep(0.5)
    given = (await t.said())[n2:]
    check(f"{name}: once 'commander.' is recorded, tapping the commander, Hear-again and giving a cat the radio say 'Moggles… is the… commander.'",
          tapped == ["name-moggles is-the job-commander"] and heard == ["name-moggles is-the job-commander name-snuffles is-the job-engineer"]
          and given == ["name-moggles is-the job-commander crew-ready"], json.dumps([tapped, heard, given]))
    await asyncio.sleep(2.5)
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
    check(f"{name}: a pause lets go of a held cat, and its job stays", not held and st["jobs"] == {"moggles": "commander", "snuffles": "engineer"}, json.dumps([held, st["jobs"]]))
    check(f"{name}: coming back says the crew's jobs again", (await t.said())[-1:] == ["name-moggles is-the job-commander name-snuffles is-the job-engineer"], str((await t.said())[-1:]))
    await page.evaluate(UNSTUB_COMMANDER_LINE)
    await t.tap(66, 62)                                      # Home
    check(f"{name}: Home goes back to the map", await t.wait_screen("screen-map"))
    jobs = await page.evaluate("Array.from(document.querySelectorAll('#screen-map .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    check(f"{name}: the cats wear their job badges on the map", jobs == ["moggles:commander", "snuffles:engineer"]
          and await page.evaluate("document.querySelectorAll('#screen-map .mw-badge').length") == 2, str(jobs))
    if name == "crew":
        await asyncio.sleep(0.4)
        await page.screenshot(path=str(SHOTS / "crew-3-map-badges.png"))
    await page.reload()
    await page.wait_for_load_state("load")
    check(f"{name}: the jobs are remembered after closing the game", await page.evaluate("JSON.stringify(MW.crew.jobs())") == json.dumps({"moggles": "commander", "snuffles": "engineer"}, separators=(",", ":")))
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


# 0.9.0: the commander's moment on an end screen (the cook's before): its box in stage px, whether it is flipped, whether
# it holds the kit's commander-call drawing (the same as the page's template) at its size, its sparkles (count and
# middle), its motion (how it changes, its scale and opacity), anything repeating, and any cook moment left on the page
CALL_INFO = """(sel => { const el = document.querySelector(sel); if (!el) return null;
    const svg = el.querySelector('svg'), tpl = document.getElementById('art-commander-call').content.firstElementChild, cs = getComputedStyle(el);
    const sp = Array.from(el.parentNode.querySelectorAll('.mw-spark')).map(e => [parseFloat(e.style.left) + parseFloat(e.getAttribute('width')) / 2,
        parseFloat(e.style.top) + parseFloat(e.getAttribute('height')) / 2]);
    const mid = i => sp.length ? Math.round(sp.reduce((a, q) => a + q[i], 0) / sp.length * 10) / 10 : null;
    return { box: [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight], shown: el.classList.contains('is-shown'), flipped: el.classList.contains('is-flipped'),
             drawing: !!svg && svg.innerHTML === tpl.innerHTML, viewBox: svg && svg.getAttribute('viewBox'), size: svg ? [+svg.getAttribute('width'), +svg.getAttribute('height')] : null,
             sparks: [sp.length, mid(0), mid(1)], transition: cs.transitionProperty, scale: cs.scale, opacity: +cs.opacity,
             repeats: el.getAnimations({ subtree: true }).some(a => a.effect && a.effect.getTiming().iterations === Infinity),
             cook: document.querySelectorAll('[data-moment^="cook"], .mw-cook-pan').length }; })"""
MOMENTS_LOGGED = "MW.events.filter(e => e.type === 'moment').map(e => e.detail)"


async def wait_call(page, screen, timeout=20):
    """Wait for the commander's moment on an end screen; what it is as it shows (with its sparkles), and its scale and
    opacity half a second later, once it has grown (or faded) in."""
    sel = screen + " [data-moment=commander]"
    for _ in range(int(timeout / 0.05)):
        if await page.evaluate("!!document.querySelector(%s)" % json.dumps(sel + ".is-shown")):
            break
        await asyncio.sleep(0.05)
    info = await page.evaluate(CALL_INFO, sel)
    if info:
        await asyncio.sleep(0.5)
        later = await page.evaluate(CALL_INFO, sel)
        info["after"] = [later["scale"], later["opacity"], later["repeats"]]
    return info


def call_ok(c, box, flipped, reduce=False):
    """The commander's moment: shown, its box (the radio's box where the cook's pan was, the call rising above it: the
    drawing is as wide as the radio's box and 1.42 times as tall), flipped or not (never, as on the boards), the commander-call drawing,
    five sparkles round the radio's box, nothing repeating, no cook moment, and grown in (or, with reduce motion, faded in)."""
    if not c:
        return False
    radio = (box[0] + box[2] / 2, box[1] + box[3] - box[2] / 2)
    grown = c["after"][0] == "1" and c["after"][1] == 1 and not c["after"][2]
    motion = (c["transition"] == "opacity" and c["scale"] == "1") if reduce else ("scale" in c["transition"])
    return (c["shown"] and c["box"] == box and c["flipped"] == flipped and c["drawing"] and c["viewBox"] == "0 -42 100 142"
            and c["size"] == [box[2], box[3]] and c["sparks"][0] == 5 and abs(c["sparks"][1] - radio[0]) < 1 and abs(c["sparks"][2] - radio[1]) < 1
            and not c["repeats"] and c["cook"] == 0 and grown and motion)


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
    # the navigator and the commander
    await page.evaluate("MW.crew.save({moggles: 'navigator', snuffles: 'commander'})")
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
    call = await wait_call(page, "#screen-end")
    check("moments: the commander's radio calls on the end screen (0.9.0, the cook's moment before), at Snuffles's place, logged, and no cook",
          call_ok(call, [770, 450, 104, 148], False) and (await page.evaluate(MOMENTS_LOGGED)).count("commander") == 1, json.dumps(call))
    badges = await page.evaluate("Array.from(document.querySelectorAll('#screen-end .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    check("moments: the end screen's cats wear their badges", badges == ["moggles:navigator", "snuffles:commander"], str(badges))
    await asyncio.sleep(1)
    await page.screenshot(path=str(SHOTS / "moments-4-commander.png"))
    for _ in range(80):                                      # the commander's moment comes before "Another rescue?"
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
    check("carry-over: the crew's jobs kept (0.9.0: the cook saved then is the commander)", got["jobs"] == {"moggles": "commander", "snuffles": "engineer"}, json.dumps(got["jobs"]))
    check("carry-over: every answer kept, and the bonds secure before are secure now", got["answers"] == len(answers) and got["secure"] == 2, json.dumps(got))
    await page.evaluate("const g = MW.store.game('starter'); g.rounds = 3; MW.store.save()")
    after = await page.evaluate("JSON.parse(localStorage.getItem('mimi-world'))")
    check("carry-over: a newer game's saved data sits beside the old, without disturbing it",
          after["games"] == {"starter": {"rounds": 3}} and len(after["answers"]) == len(answers) and after["settings"]["crew"]["moggles"] == "commander", json.dumps(after["games"]))
    check("carry-over: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


TPL_PORT = 8793


# The shapes that draw place i on the map (0.8.0): a planet by its clip circle; the rocks by the rock groups (each with
# its shaded underside) and the sparkle within place 3's tap area; the station by its group, drawn 6 px below place 4's
# middle (0.9.0, the redrawn station).
SHAPES_JS = """const L = MW.LAYOUT.map.planets, svg = document.querySelector('#screen-map > svg.mw-layer'), k = MW.stage.scale;
    const mid = e => { const r = e.getBoundingClientRect(); return [(r.left + r.width / 2 - MW.stage.offX) / k, (r.top + r.height / 2 - MW.stage.offY) / k]; };
    const near = (e, p) => { const m = mid(e); return Math.hypot(m[0] - p.x, m[1] - p.y) < p.tap / 2; };
    const GEO = 'path, rect, circle, ellipse';
    const shapes = i => { const p = L[i];
        if (i === 3) return Array.from(svg.querySelectorAll('g[transform*=" rotate("]')).filter(g => g.querySelector('.f-asteroid-crater') && near(g, p))
            .reduce((a, g) => a.concat(Array.from(g.querySelectorAll(GEO))), []).concat(Array.from(svg.querySelectorAll('path.f-spark')).filter(e => near(e, p)));
        if (i === 4) { const g = svg.querySelector('g[transform^="translate(' + p.x + ' ' + (p.y + 6) + ')"]'); return g ? Array.from(g.querySelectorAll(GEO)) : []; }
        return Array.from(svg.querySelectorAll('clipPath circle')).filter(c => +c.getAttribute('cx') === p.x && +c.getAttribute('cy') === p.y); };"""
# Each place on the map as drawn and as buttons (0.8.0): whose game it has, its tap area, whether it is lit with a mint
# halo and its badge, or dimmed with its lock badge.
PLACES_INFO = """(() => { """ + SHAPES_JS + """
    const dimmed = e => !!e.closest('g[opacity="0.45"], g[opacity="0.62"]'), at = (e, p) => +e.getAttribute('cx') === p.x && +e.getAttribute('cy') === p.y;
    const box = e => [e.offsetLeft, e.offsetTop, e.offsetWidth, e.offsetHeight];
    const buttons = Array.from(document.querySelectorAll('#screen-map .mw-planet'));
    const locks = Array.from(document.querySelectorAll('#screen-map .mw-planet-lock')).map(box);
    const badges = Array.from(document.querySelectorAll('#screen-map .mw-planet-badge')).map(box);
    const same = (b, q) => b[0] === q.x && b[1] === q.y && b[2] === q.d && b[3] === q.d;
    return L.map((p, i) => { const d = shapes(i), g = MW.world.games.find(g => g.planet === i);
        return { i: i, game: g ? g.name : null, label: buttons[i].getAttribute('aria-label'), tap: box(buttons[i]),
                 lit: d.length > 0 && !d.some(dimmed), dim: d.length > 0 && d.every(dimmed),
                 halo: Array.from(svg.querySelectorAll('circle.s-mint[stroke-width="10"][opacity="0.3"]')).filter(c => at(c, p) && !dimmed(c)).length,
                 badge: badges.some(b => same(b, p.badge)), lock: locks.some(b => same(b, p.lock)) }; }); })()"""


def place_ok(info, game):
    """A place with a game: lit, a mint halo and its badge, no lock. One without: dimmed, its lock, no halo or badge."""
    if game:
        return info["game"] == game and info["label"] == game and info["lit"] and info["halo"] == 1 and info["badge"] and not info["lock"]
    return info["game"] is None and info["label"] == "A place that isn't ready yet" and info["dim"] and info["halo"] == 0 and info["lock"] and not info["badge"]


async def test_template(p):
    """The starter game on each free place in turn (0.8.0: the small peach planet, the rocks and the station, while they
    are free). The first keeps the names its checks had before."""
    print("\n== a new game joins the world (the template) ==")
    sys.path.insert(0, str(ROOT / "tools"))
    import games as G
    taken = {g.get("planet") for g in G.load()}
    free = [i for i in range(G.PLANETS) if i not in taken]
    if not free:
        check("template: a new game joins the world", True, "skipped: every place has a game")
        return
    here = pathlib.Path(__file__).resolve().parent
    out = here / "serve-template"
    out.mkdir(exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", TPL_PORT), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for k, place in enumerate(free):
            await template_on(p, G, taken, place, "template" if k == 0 else f"template (place {place})", here, out)
    finally:
        srv.shutdown()
        srv.server_close()


async def template_on(p, G, taken, place, label, here, out):
    import shutil
    import subprocess
    first = label == "template"
    src = here / "serve-template-src" / "starter"
    if src.parent.exists():
        shutil.rmtree(src.parent)
    shutil.copytree(ROOT / "games" / "_template", src, ignore=shutil.ignore_patterns("__pycache__"))
    gj = json.loads((src / "game.json").read_text(encoding="utf-8"))
    gj["planet"] = place
    (src / "game.json").write_text(json.dumps(gj), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--no-audio", "--out", str(out), "--extra-game", str(src)],
                       capture_output=True, text=True)
    check(f"{label}: builds into a test copy with no problems", r.returncode == 0 and "Starter game" in r.stdout, (r.stdout + r.stderr)[-300:])
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
    check(f"{label}: its planet is on the map, MeeMee Rescue's is still first, the rest still to come",
          planets[0] == "MeeMee Rescue" and planets[place] == "Starter game" and locks == G.PLANETS - len(taken) - 1, json.dumps([planets, locks]))
    info = await page.evaluate(PLACES_INFO)
    others = [i for i in range(G.PLANETS) if i not in taken and i != place]
    check(f"{label}: its place ({place}) shows its badge and a mint halo; the other free places ({', '.join(map(str, others))}) stay dimmed with their locks",
          place_ok(info[place], "Starter game") and all(place_ok(info[i], None) for i in others), json.dumps([info[place]] + [info[i] for i in others]))
    await asyncio.sleep(1.2)
    await page.screenshot(path=str(SHOTS / ("template-1-map.png" if first else f"template-place{place}-map.png")))
    pl = await page.evaluate("MW.LAYOUT.map.planets[%d]" % place)
    await t.tap(pl["x"], pl["y"])
    ok = await t.wait_screen("screen-starter-play", 2)
    said = await t.said()
    check(f"{label}: tapping its planet opens its screen (its name isn't recorded yet, so no banner: straight away)",
          ok and await page.evaluate("[MW.audio.recorded('starter-name'), MW.events.some(e => e.type === 'banner' && e.detail === 'up Starter game')]") == [False, False],
          str(said[-3:]))
    await asyncio.sleep(0.3)
    if first:
        await page.screenshot(path=str(SHOTS / "template-2-screen.png"))
    for _ in range(3):
        await t.tap(640, 400)
        await asyncio.sleep(0.25)
    back = await t.wait_screen("screen-map", 5)
    check(f"{label}: three taps on the star finish it and go home", back and await page.evaluate("MW.store.game('starter').rounds") == 1)
    await asyncio.sleep(0.5)
    await t.tap(pl["x"], pl["y"])
    await t.wait_screen("screen-starter-play")
    await t.tap(66, 62)
    check(f"{label}: Home on its screen goes back to the map", await t.wait_screen("screen-map", 5))
    await asyncio.sleep(0.5)
    rp = await page.evaluate("MW.LAYOUT.map.planets[0]")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(rp["x"], rp["y"])
    s = await t.wait_phase(["asking", "open"])
    check(f"{label}: MeeMee Rescue still plays beside it", s["screen"] == "screen-game", json.dumps(s))
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('starter-progress')")
    await asyncio.sleep(0.3)
    text = await page.inner_text(".gu-body")
    check(f"{label}: its tab in the grown-ups area shows its saved data", "Rounds finished on this tablet: 1." in text, text[:80])
    check(f"{label}: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# ---------------------------------------------------------------- MeeMee Rockets (games/words): the tricky-words game
HEAR = (1208, 68)                     # Hear it again
HOME = (66, 62)
AGAIN = (1160, 500)                   # "Another go?" on the end screen
WORDS_PLANET = "MW.LAYOUT.map.planets[MW.world.games.find(g => g.id === 'words').planet]"
PRAISE_LINES = {"words-found-it", "words-super-reading", "words-well-done"}
W_ROUND = [{"word": "one", "step": "tiles"}, {"word": "spray", "step": "letters"}, {"word": "here", "step": "tiles"},
           {"word": "popcorn", "step": "harder"}, {"word": "my", "step": "tiles"}]
# 0.7.0: what's in play is a grown-up's choice of half-term and week (or a whole term). The checks written for 0.6.0 play
# autumn 1's week 5 (0.6.0's week in play), saved in the new shape; a tablet with nothing saved plays the start, autumn 2's
# week 1.
A1 = {"half": "autumn-1", "week": 5}
A2 = {"half": "autumn-2", "week": 1}
TERM = {"term": "autumn"}
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
# Autumn 2 (0.7.0 PRD, Words and tiles tab, with Barney's answers): what each sound tile says, one per tile, '-' for a
# tile that says nothing. The seven words shared with autumn 1 say the same as there.
W_SOUNDS_A2 = {
    "their": "th-voiced air", "people": "p ee p l", "oh": "oa -", "your": "y or", "bird": "b ur d", "girl": "g ur l",
    "pie": "p igh", "tried": "t r igh d", "blue": "b l oo-long", "true": "t r oo-long", "human": "h yoo m a n", "unit": "yoo n i t",
    "Mr": "- -", "Mrs": "- - -", "Ms": "- -", "ask": "ar s k", "both": "b oa th", "go": "g oa", "child": "ch igh l d",
    "kind": "k igh n d", "basic": "b ai s i k", "acorn": "ai k or n", "fever": "f ee v er", "me": "m ee",
    "could": "k oo-short d", "would": "w oo-short d", "should": "sh oo-short d", "our": "ow er", "take": "t ai k -",
    "same": "s ai m -", "time": "t igh m -", "like": "l igh k -", "home": "h oa m -", "woke": "w oa k -", "rude": "r oo-long d -",
    "cute": "k yoo t -", "house": "h ow s -", "mouse": "m ow s -", "water": "w or t er", "want": "w o n t",
    "these": "th-voiced ee z -", "even": "ee v e n", "new": "n yoo", "chew": "ch oo-long", "shriek": "sh r ee k",
    "field": "f ee l d", "claw": "k l or", "draw": "d r or", "sure": "sh ure", "some": "s u m -", "little": "l i t l",
    "what": "w o t", "fried": "f r igh d", "spray": "s p r ai", "game": "g ai m -", "open": "oa p e n", "float": "f l oa t",
    "being": "b ee i ng", "eating": "ee t i ng",
}
A2_SHARED = ["go", "me", "like", "sure", "some", "what", "spray"]       # in both half-terms (D1)


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


async def w_choose(page, choice):
    """Put a choice in play, saved as the Words tab saves it: {'half': id, 'week': n or 'all'}, or {'term': id}."""
    await page.evaluate("(c) => { const g = MW.store.game('words'); delete g.term; delete g.half; delete g.week; Object.assign(g, c); MW.store.save(); }", choice)


async def w_open(t, page, round_, choice=A1):
    """Play, then the MeeMee Rockets planet, with the round fixed (and a choice in play: autumn 1's week 5, unless given;
    None leaves the saved choice as it is)."""
    if choice is not None:
        await w_choose(page, choice)
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
    book = await E("""(() => { const b = MW.wordSteps.read(MW.wordsData); return { problems: b.problems, order: b.order, tray: b.harderTray, start: b.start,
        terms: b.terms.map(t => [t.id, t.name, t.all, t.halves.map(h => h.id)]), halves: b.halves.map(h => ({ id: h.id, name: h.name, weeks: h.weeks })) }; })()""")
    check("words: the words file reads with no problems", not book["problems"], "; ".join(book["problems"][:3]))
    halves = {h["id"]: h for h in book["halves"]}
    a1, a2 = halves.get("autumn-1"), halves.get("autumn-2")
    listed = lambda h: [w for wk in h["weeks"] for w in wk["tricky"] + wk["other"]]
    check("words: one term, autumn ('All of autumn'), with two half-terms, Autumn 1 and Autumn 2, autumn 2's week 1 to start, the harder tray holds 10",
          book["terms"] == [["autumn", "Autumn", "All of autumn", ["autumn-1", "autumn-2"]]] and a1 and a2 and a1["name"] == "Autumn 1" and a2["name"] == "Autumn 2"
          and book["start"] == {"half": "autumn-2", "week": 1} and book["tray"] == 10, json.dumps([book["terms"], book["start"]]))
    check("words: autumn 1: 60 words over weeks 1 to 5 (each week's 4 tricky words and 8 others)",
          [w["week"] for w in a1["weeks"]] == [1, 2, 3, 4, 5] and all(len(w["tricky"]) == 4 and len(w["other"]) == 8 for w in a1["weeks"])
          and len(listed(a1)) == len(set(listed(a1))) == 60, str(len(listed(a1))))
    check("words: autumn 2: weeks 1 to 5, 60 entries (4 tricky words and 8 others a week), 59 different words ('time' in weeks 3 and 5), 52 new to the game",
          [w["week"] for w in a2["weeks"]] == [1, 2, 3, 4, 5] and all(len(w["tricky"]) == 4 and len(w["other"]) == 8 for w in a2["weeks"])
          and len(listed(a2)) == 60 and len(set(listed(a2))) == 59 and listed(a2).count("time") == 2 and len(set(listed(a2)) - set(listed(a1))) == 52
          and sorted(set(listed(a2)) & set(listed(a1))) == sorted(A2_SHARED), str(sorted(set(listed(a2)) & set(listed(a1)))))
    check("words: 112 words in all, each once in the words file's list", len(book["order"]) == 112 == len(set(book["order"])), str(len(book["order"])))
    w_lines = {c["id"]: c for c in json.loads((ROOT / "games" / "words" / "lines.json").read_text(encoding="utf-8"))["lines"]}
    on_page = set(await E("Object.keys(MW.audio.manifest.voice)"))
    missing = [w for w in book["order"] if f"words-w-{w.lower()}" not in w_lines or ((f"words-w-{w.lower()}" in on_page) == bool(w_lines[f"words-w-{w.lower()}"].get("pending")))]
    check("words: every word has its line in lines.json (in small letters: words-w-mr), on the page once recorded and pending until then", not missing, str(missing))
    check("words: autumn 1's 60 words are recorded", all(f"words-w-{w}" in on_page for w in listed(a1)), str([w for w in listed(a1) if f"words-w-{w}" not in on_page]))
    in_play = {wk: await E("(w) => MW.wordSteps.inPlay(MW.wordSteps.read(MW.wordsData), w)", {"half": "autumn-1", "week": wk}) for wk in (1, 2, 3, 4, 5, "all")}
    check("words: in play: week 1 has its 12 words, week 3 its 12 and 8 earlier tricky words, week 5 its 12 and 16 earlier tricky words, all weeks 60",
          len(in_play[1]) == 12 and len(in_play[3]) == 20 and len(in_play[5]) == 28 and len(in_play["all"]) == 60 and set(in_play["all"]) == set(listed(a1)),
          str({k: len(v) for k, v in in_play.items()}))
    check("words: week 5 in play: its tricky words, its other words, then earlier weeks' tricky words",
          in_play[5][:12] == ["all", "of", "one", "here", "magnet", "cartoon", "rabbit", "spray", "popcorn", "proud", "toy", "say"])

    # every word of both half-terms, as a Find question and as a Build question at each step, through the game's own
    # screens (with all of autumn in play, so Find's other two words come from every recorded word; a word whose recording
    # isn't on the page yet is asked through the game's own screens all the same)
    await w_choose(page, TERM)
    term_words = await E("MW.wordSteps.inPlay(MW.wordsGame.book, { term: 'autumn' })")
    marked = await E("(() => { const m = MW.wordSteps.marks(MW.wordsGame.book, { term: 'autumn' }); return Object.fromEntries(Object.keys(m).map(w => [w, m[w].tricky])); })()")
    check("words: with all of autumn in play, go, me and like are plain (autumn 2 lists them as other words); sure, some and what tricky",
          [marked.get(w) for w in A2_SHARED] == [False, False, False, True, True, True, False], str([marked.get(w) for w in A2_SHARED]))
    rows = await E("""() => {
        const G = MW.wordsGame, S = MW.wordSteps, out = [];
        MW.world.st.phase = 'map';
        S.inPlay(G.book, { term: 'autumn' }).forEach(w => {
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
               and r["word"] in r["find"]["words"] and len(set(r["find"]["words"])) == 3 and set(r["find"]["words"]) <= set(term_words)
               and r["find"]["prompt"] == json.dumps([["words-find", f"words-w-{r['word'].lower()}"]]).replace(" ", "")]
    check("words: every word of both half-terms can be asked in Find (112), among two other words in play", len(ok_find) == 112 and len(rows) == 112,
          str(sorted(set(book["order"]) - set(ok_find))))
    bad = []
    for r in rows:
        w = r["word"]
        # the tricky part is marked only where the half-term in play lists the word as tricky (with all of autumn: the
        # last half-term that lists it)
        tiles = [t if marked[w] else t.strip("[]") for t in data[w]["tiles"].split()]
        letters = [("[" + ch + "]" if t.startswith("[") else ch) for t in tiles for ch in t.strip("[]")]
        spares = data[w].get("spares", "").split()
        for step, b in r["build"].items():
            want = tiles if b["want"] == "tiles" else letters
            plain = [x.strip("[]") for x in want]
            tray_plain = sorted(x.rstrip("*") for x in b["tray"])
            if b["mode"] != b["want"] or b["places"] != want or b["sockets"] != len(want) or not b["done"] or b["built"] != w:
                bad.append(f"{w} {step}: {b}")
            elif b["prompt"] != json.dumps([["words-build", f"words-w-{w.lower()}"]]).replace(" ", ""):
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
                elif any(ch != ch.lower() for ch in extra):
                    bad.append(f"{w} {step}: a capital in its harder tray that isn't its own {b['tray']}")
    check("words: every word of both half-terms can be built (448 questions: sound tiles, letters, harder letters, and secure in harder letters)",
          not bad and len(rows) * 4 == 448, "; ".join(bad[:3]))
    sounds = {r["word"]: " ".join(x if x else "?" for x in r["build"]["tiles"]["sounds"]) for r in rows}
    wrong = {w: [sounds.get(w), want] for w, want in W_SOUNDS.items() if sounds.get(w) != want}
    check("words: in sound tiles every autumn 1 tile says its sound in its word, as on the 0.6.0 Lines tab (60 words; tricky tiles say what they say in the word)",
          not wrong and len(W_SOUNDS) == 60, json.dumps(wrong)[:300])
    wrong = {w: [sounds.get(w), want] for w, want in W_SOUNDS_A2.items() if sounds.get(w) != want}
    same = [w for w in A2_SHARED if W_SOUNDS[w] != W_SOUNDS_A2[w]]
    check("words: ... and every autumn 2 tile as on the 0.7.0 Words and tiles tab (59 words: ask's a says ar, our's ou ow and r er, even's e's ee then e, these's s z)",
          not wrong and not same and len(W_SOUNDS_A2) == 59 and len(sounds) == 112, json.dumps([wrong, same])[:300])
    # the list for grown-ups to compare with the homework (like MeeMee Rescue's all-questions.md)
    out = ["# Every question MeeMee Rockets can ask (autumn 1 and autumn 2)", "",
           "Made by tools/tests/test_game.py from the game's own words file (games/words/words.js); don't edit it by hand.",
           "Each word is asked twice in a round: Find (tap it among three rockets) and Build (drag its tiles into the rocket).",
           "Tricky parts are in [square brackets]: on the tiles they are the darker peach letters, shown only where the half-term in",
           "play lists the word as tricky (Tricky in). Spares are marked *.",
           "In sound tiles each tile says its sound as it is picked up (the recording words-s- and the sound; - says nothing).",
           "Harder letters adds letters from other words until the tray holds 10 tiles (a different few each time).", "",
           "| Word | Listed in | Tricky in | Find | Sound tiles | Tiles say | Letters | Harder letters |", "|---|---|---|---|---|---|---|---|"]
    where, tricky_in = {}, {}
    for h in book["halves"]:
        for wk in h["weeks"]:
            for kind in ("tricky", "other"):
                for w in wk[kind]:
                    where.setdefault(w, []).append(f"{h['name']}, week {wk['week']}")
                    if kind == "tricky" and h["name"] not in tricky_in.setdefault(w, []):
                        tricky_in[w].append(h["name"])
    for r in rows:
        w = r["word"]
        b = r["build"]
        tiles = data[w]["tiles"].split()
        letters = " ".join(("[" + ch + "]" if t.startswith("[") else ch) for t in tiles for ch in t.strip("[]"))
        let = letters + " + " + " ".join(x + "*" for x in data[w].get("spares", "").split())
        out.append(f"| {w} | {'; '.join(where[w])} | {', '.join(tricky_in.get(w, [])) or '-'} | Find the word… {w}. | {' · '.join(tiles)} | "
                   f"{' · '.join(x or '?' for x in b['tiles']['sounds'])} | {let} | {let} + {10 - len(b['letters']['tray'])} more |")
    (ROOT / "notes" / "all-questions-words.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("   wrote notes/all-questions-words.md (112 words, 448 questions)")
    await w_choose(page, A1)

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
    allq = await E("""(() => { const S = MW.wordSteps, b = S.read(MW.wordsData);
        return [{ half: 'autumn-1', week: 5 }, { half: 'autumn-1', week: 'all' }, { half: 'autumn-2', week: 'all' }, { term: 'autumn' }].map(c => S.allQuestions(b, c).length); })()""")
    check("words: the game can ask 112 questions in autumn 1's week 5 (28 words), 240 with its weeks 1 to 5 (60 words), 236 with autumn 2's (59) and 448 with all of autumn (112)",
          allq == [112, 240, 236, 448], str(allq))
    gone = await E("delete MW.audio.manifest.voice['words-w-magnet'], [MW.wordsGame.inPlay().includes('magnet'), MW.wordsGame.inPlay().length]")
    check("words: a word whose recording isn't on the page stays out of play", gone == [False, 27], str(gone))
    check("words: no console errors", not problems, "; ".join(problems[:3]))
    await ctx.close()

    # a word moving on in the game itself: two days right first time already, a third today moves it to letters
    ctx, page, problems = await seeded(browser, [])
    t = Tablet(page, await ctx.new_cdp_session(page))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    now = await page.evaluate("Date.now()")
    seed = {"half": "autumn-1", "week": 5, "answers": [w_ans(now - 2 * DAY, "of"), w_ans(now - DAY, "of")]}
    await page.evaluate("(g) => { Object.assign(MW.store.game('words'), g); MW.store.save(); }", seed)
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
        saved = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True, "crew": {"moggles": "commander", "snuffles": "lookout"}},
                 "answers": rescue, "games": {"words": {"half": "autumn-1", "week": 5, "answers": words}}}
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
        halves = await page.evaluate("Array.from(document.querySelectorAll('.words-half')).map(b => b.textContent + (b.classList.contains('is-on') ? '*' : ''))")
        check(f"words-grownups ({name}): ... under autumn 1 (a 0.7.0 save keeps its half-term)", halves == ["Autumn 1*", "Autumn 2", "All of autumn"], str(halves))
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
              after[1] == len(rescue) and after[2] == json.dumps({"moggles": "commander", "snuffles": "lookout"}, separators=(",", ":")) and after[3] == 2, str(after))
        await page.evaluate("MW.grownups.close()")
        await page.reload()
        await page.wait_for_load_state("load")
        kept = await page.evaluate("[MW.wordsGame.week(), MW.wordsGame.answers().length, MW.wordsGame.choice()]")
        check(f"words-grownups ({name}): the week in play is remembered on the tablet", kept == [2, 0, {"half": "autumn-1", "week": 2}], str(kept))
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
        await w_choose(page, TERM)                          # all of autumn: Find's other words from every recorded word
        words = await page.evaluate("MW.wordSteps.inPlay(MW.wordsGame.book, { term: 'autumn' })")
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
              not bad and len(words) == 112 and all(w in worst for w in words), "; ".join(bad[:4]))
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
    await w_choose(page, {"half": "autumn-1", "week": 2})
    week2 = set(await page.evaluate("MW.wordsGame.inPlay()"))
    await w_open(t, page, [{"word": "what", "step": "tiles"}, {"word": "love", "step": "harder"}, {"word": "she", "step": "tiles"}], choice=None)
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
            src = await page.evaluate("""(() => { const G = MW.wordsGame, f = MW.wordSteps.fillFrom(G.book, G.st.choice, 'love', G.st.pool);
                return { week: G.st.choice.week, half: G.st.choice.half, own: f[0], pool: f[1] }; })()""")
            own2 = ["what", "she", "me", "love", "misses", "chain", "queen", "chair", "year", "cobweb", "goats", "farmyard"]
            own_letters = set("".join(w for w in own2 if w != "love")) - set("loveu")
            check("words-fixes: harder letters mid-round fill first from week 2's own words (the round's week, not week 5), which have enough letters",
                  s["mode"] == "harder" and src["week"] == 2 and src["half"] == "autumn-1" and src["own"] == own2 and sorted(src["pool"]) == sorted(week2) and len(own_letters) >= 5
                  and len(fill) == 5 and set(fill) <= own_letters, str([fill, src["week"], src["own"]]))
            await w_build(t)
    check("words-fixes: the rest of the round's Finds still use week 2's words", others and set(others) <= week2, str(others))
    await t.tap(*HOME)
    await asyncio.sleep(1.0)
    pl = await page.evaluate(WORDS_PLANET)
    await t.tap(pl["x"], pl["y"])
    await w_wait(page, ["words-find"])
    pool = await page.evaluate("[(MW.wordsGame.st.pool || []).length, MW.wordsGame.st.choice]")
    check("words-fixes: the next round uses week 5's words", pool == [28, {"half": "autumn-1", "week": 5}], str(pool))
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
    old42 = sorted({f"words-s-{x}" for v in W_SOUNDS.values() for x in v.split() if x != "-"})
    want = sorted({f"words-s-{x}" for v in list(W_SOUNDS.values()) + list(W_SOUNDS_A2.values()) for x in v.split() if x != "-"})
    new4 = sorted(set(want) - set(old42))
    on_page = await page.evaluate("(ids) => ids.map(id => MW.audio.recorded(id))", used)
    check("words-sounds: the words use 46 tile sounds: the 42 on the 0.6.0 Lines tab, each a line in lines.json and recorded on the page, and autumn 2's four new ones",
          used == want and len(old42) == 42 and len(used) == 46 and new4 == ["words-s-er", "words-s-ng", "words-s-yoo", "words-s-z"]
          and all(x in lines and not lines[x].get("pending") for x in old42) and await page.evaluate("(ids) => ids.every(id => MW.audio.recorded(id))", old42),
          str(sorted(set(used) ^ set(want))))
    check("words-sounds: ... the four new ones (yoo, er, ng, z) each a line in lines.json, on the page once recorded and pending until then",
          all(x in lines for x in new4) and all(rec == (not lines[x].get("pending")) for x, rec in zip(used, on_page)), str([(x, lines.get(x, {}).get("pending")) for x in new4]))
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
    book = await E("(() => { const b = MW.wordsGame.book, h = MW.wordSteps.half(b, 'autumn-1'); return { order: b.order, weeks: h.weeks, label: MW.wordSteps.allLabel(h) }; })()")
    allw = await E("MW.wordSteps.inPlay(MW.wordsGame.book, { half: 'autumn-1', week: 'all' })")
    week_of = {w: wk["week"] for wk in book["weeks"] for w in wk["tricky"] + wk["other"]}
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    secure = lambda w: days(3, "tiles", w) + days(3, "letters", w, 3) + days(3, "harder", w, 6)
    check("words-weeks: the all-weeks choice is named from the words file: 'Weeks 1–5'", book["label"] == "Weeks 1–5", str(book["label"]))
    code = "".join((ROOT / "games" / "words" / f).read_text(encoding="utf-8") for f in ("game.js", "steps.js", "moments.js"))
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)                  # the code without its comments
    found = re.findall(r".{0,20}(?:[Ww]eeks?\s*['\"]?\s*\d|\d\s*–\s*\d).{0,10}", code)
    check("words-weeks: no week number is written into the code (a new half-term needs no code change)", not found, str(found[:3]))
    found = re.findall(r".{0,20}(?:autumn|spring|summer).{0,10}", code, flags=re.I)
    check("words-weeks: no half-term or term is named in the code either (0.7.0: every name comes from the words file)", not found, str(found[:3]))
    await w_choose(page, {"half": "autumn-1", "week": "all"})
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
        S.inPlay(b, { half: 'autumn-1', week: 'all' }).forEach(w => { for (let i = 0; i < 4; i++) {
          const c = { half: 'autumn-1', week: 'all' }, m = S.marks(b, c)[w];
          const p = S.plan(b, w, 'harder', S.fillFrom(b, c, w, G.inPlay()));
          const own = new Set(S.ownWords(b, m.half, m.week).filter(x => x !== w).join('').split(''));
          const base = new Set(b.words[w].letters.map(l => l.text).concat(b.words[w].spares));
          const avail = Array.from(own).filter(c => !base.has(c)).length;
          const extra = p.tray.slice().filter(t => t.spare && b.words[w].spares.indexOf(t.text) < 0).map(t => t.text);
          out.push({ w: w, n: p.tray.length, extra: extra, outside: extra.filter(c => !own.has(c)).length, avail: avail }); } });
        return out; })()""")
    bad = [f for f in fill if f["n"] != 10 or f["outside"] > max(0, len(f["extra"]) - f["avail"])]
    check("words-weeks: harder letters with Weeks 1–5 fill the tray to 10 from the word's own week first (every word, 4 times)",
          not bad and len(fill) == 240, json.dumps(bad[:3]))
    thin = await E("""(() => { const S = MW.wordSteps, b = S.read({ harderTray: 10, start: { half: 'h', week: 1 }, terms: [{ id: 't', name: 'T', all: 'All of t', halves: [
          { id: 'h', name: 'H', weeks: [{ week: 1, tricky: ['a'], other: [] }, { week: 2, tricky: ['bc'], other: [] }] }] }],
        words: { a: { tiles: 'a', sounds: {}, spares: 'z' }, bc: { tiles: 'b c', spares: 'y' } }, sounds: { a: 'a', b: 'b', c: 'k' } });
        const p = S.plan(b, 'a', 'harder', S.fillFrom(b, { half: 'h', week: 'all' }, 'a', ['a', 'bc'])); return p.tray.map(t => t.text).sort(); })()""")
    check("words-weeks: ... then from any word in play when its week runs out of letters", thin == ["a", "b", "c", "z"], str(thin))
    first = await E("""(() => { const S = MW.wordSteps, out = { one: new Set(), all: new Set() };
        const b = S.read({ harderTray: 4, start: { half: 'h', week: 1 }, terms: [{ id: 't', name: 'T', all: 'All of t', halves: [
            { id: 'h', name: 'H', weeks: [{ week: 1, tricky: ['xy'], other: [] }, { week: 2, tricky: ['ab'], other: ['ac'] }] }] }],
          words: { xy: { tiles: 'x y', spares: 'q' }, ab: { tiles: 'a b', spares: 'z' }, ac: { tiles: 'a c', spares: 'q' } }, sounds: { a: 'a', b: 'b', c: 'k', x: 'k', y: 'y' } });
        for (let i = 0; i < 60; i++) {
          out.one.add(S.plan(b, 'ab', 'harder', S.fillFrom(b, { half: 'h', week: 2 }, 'ab', ['ab', 'ac', 'xy'])).tray.map(t => t.text).sort().join(''));
          out.all.add(S.plan(b, 'ab', 'harder', S.fillFrom(b, { half: 'h', week: 'all' }, 'ab', ['ab', 'ac', 'xy'])).tray.map(t => t.text).sort().join(''));
        }
        return [Array.from(out.one), Array.from(out.all)]; })()""")
    check("words-weeks: the one extra letter always comes from the word's own week (c, from 'ac'), never another week in play (x, y), with one week or all",
          first == [["abcz"], ["abcz"]], str(first))

    # one week in play: at least 3 of 5 from that week's own words
    await w_choose(page, A1)
    own5 = set(await E("MW.wordSteps.ownWords(MW.wordsGame.book, 'autumn-1', 5)"))
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

    # progress saved by the test build (week 5, its answers) carries on; 0.7.0 moves it once to the file's start (autumn
    # 2's week 1: test_words_move has the rest)
    await ctx.close()
    now = T0 + 40 * DAY
    old = {"week": 5, "answers": [w_ans(T0 + d * DAY, "of") for d in range(3)] + [w_ans(T0, "magnet", first=False)]}
    ctx, page, problems2 = await seeded(browser, [])
    await page.evaluate("(g) => { const s = JSON.parse(localStorage.getItem('mimi-world')); s.games = { words: g }; localStorage.setItem('mimi-world', JSON.stringify(s)); }", old)
    await page.reload()
    await page.wait_for_load_state("load")
    kept = await page.evaluate("""(() => { const m = MW.wordSteps.statuses(MW.wordsGame.answers());
        return [MW.wordsGame.choice(), MW.wordsGame.answers().length, m.of.step, m.magnet.step]; })()""")
    check("words-weeks: progress saved by the test build (week 5) carries on: each word's step kept (and autumn 2's week 1 in play, once)",
          kept == [A2, 4, "letters", "tiles"], str(kept))
    await w_choose(page, A1)
    kept = await page.evaluate("[MW.wordsGame.inPlay().length, MW.wordsGame.makeRound().length]")
    check("words-weeks: ... and with autumn 1's week 5 picked again, its 28 words in play", kept == [28, 5], str(kept))
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
    # the navigator and the commander
    await page.evaluate("MW.crew.save({moggles: 'navigator', snuffles: 'commander'})")
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
    call = await wait_call(page, "#screen-words-end")
    await asyncio.sleep(0.6)
    cb = await moment_box(page, "#screen-words-end [data-moment=commander-cat]")
    pb = await moment_box(page, "#screen-words-end [data-moment=commander]")
    again = (await stage_rect(page, "#words-again"))[0]
    who = await page.evaluate("document.querySelector('#screen-words-end [data-moment=commander-cat] .mw-cat').dataset.job")
    check(f"words-moments ({name}): on the end screen the commander pops up beside the little rockets and holds up the radio, which calls (0.9.0, the cook's moment before)",
          call_ok(call, [800, 580, 120, 170], False) and cb and pb and who == "commander" and pb[0] < cb[0] and 570 < pb[1] < 700, json.dumps([call, cb, pb, who]))
    check(f"words-moments ({name}): ... clear of the Play button", not overlap(cb, again) and not overlap(pb, again), str([cb, pb, again]))
    await screenshot(page, f"{name}-words-moment-commander.png")
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
        saved = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True}, "answers": [], "games": {"words": {"half": "autumn-1", "week": 5, "answers": words}}}
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
        tricky = [w for wk in range(1, 6) for w in await page.evaluate("(n) => MW.wordSteps.half(MW.wordsGame.book, 'autumn-1').weeks[n - 1].tricky", wk)]
        other = [w for wk in range(1, 6) for w in await page.evaluate("(n) => MW.wordSteps.half(MW.wordsGame.book, 'autumn-1').weeks[n - 1].other", wk)]
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
        check(f"words-alltab ({name}): rounds then come from every week", {week for week in [1, 2, 3, 4, 5] if any(w in rounds for w in await page.evaluate("(n) => MW.wordSteps.ownWords(MW.wordsGame.book, 'autumn-1', n)", week))} == {1, 2, 3, 4, 5},
              str(len(rounds)))
        await page.evaluate("MW.grownups.close()")
        await page.reload()
        await page.wait_for_load_state("load")
        check(f"words-alltab ({name}): Weeks 1–5 is remembered on the tablet", await page.evaluate("MW.wordsGame.choice()") == {"half": "autumn-1", "week": "all"})
        check(f"words-alltab ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_words_newwords(p, name, vw, vh, dpr):
    """A weeks 1–4 word played in Find and Build at both sizes (sound tiles, then harder letters), as the child would."""
    print(f"\n== MeeMee Rockets: weeks 1 to 4's words ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"words-new-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await w_open(t, page, [{"word": "farmyard", "step": "tiles"}, {"word": "cobweb", "step": "harder"}], choice={"half": "autumn-1", "week": "all"})
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
    own2 = set("".join(await page.evaluate("MW.wordSteps.ownWords(MW.wordsGame.book, 'autumn-1', 2)")))
    extra = [c["text"] for c in tiles if c["spare"] and c["text"] != "d"]
    check(f"words-new ({name}): Build 'cobweb' in harder letters: 10 tiles in two rows, its spare d and letters from week 2's words",
          s["mode"] == "harder" and len(tiles) == 10 and len({round(c["y"]) for c in tiles}) == 2 and set(extra) <= own2, str([c["text"] for c in tiles]))
    await screenshot(page, f"{name}-words-new-build-harder.png")
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    check(f"words-new ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# ---------------------------------------------------------------- 0.7.0: autumn 2, the half-term switch, capitals
def a2_pending():
    """Autumn 2's words and tile sounds still waiting for Barney's recordings (pending in lines.json)."""
    lines = json.loads((ROOT / "games" / "words" / "lines.json").read_text(encoding="utf-8"))["lines"]
    return {l["id"] for l in lines if l.get("pending")}


def term_order(halves):
    """Every word of these half-terms once, in the order first listed, with whether it is tricky: the last half-term
    that lists it decides (the 0.7.0 PRD's D1), worked out here from the half-terms themselves."""
    order, tricky = [], {}
    for h in halves:
        mine = {}
        for wk in h["weeks"]:
            for kind in ("tricky", "other"):
                for w in wk[kind]:
                    if w not in order:
                        order.append(w)
                    mine[w] = mine.get(w, False) or kind == "tricky"
        tricky.update(mine)
    return order, tricky


async def test_words_halves(p):
    """0.7.0 through the game's hooks: what's in play for a week, a half-term's weeks and the whole term; a shared word's
    step and marking; "these" and "even"; capitals (Mr, Mrs, Ms) in every step; the words file's new checks."""
    print("\n== MeeMee Rockets 0.7.0: half-terms, shared words, tiles used twice, capitals ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    E = lambda js, arg=None: page.evaluate(js, arg)
    IP = "(c) => MW.wordSteps.inPlay(MW.wordsGame.book, c)"
    halves = {h["id"]: h for h in await E("MW.wordsGame.book.halves")}
    a1, a2 = halves["autumn-1"], halves["autumn-2"]
    a1_words = {w for wk in a1["weeks"] for w in wk["tricky"] + wk["other"]}
    a2_words = {w for wk in a2["weeks"] for w in wk["tricky"] + wk["other"]}
    wk2 = {wk: await E(IP, {"half": "autumn-2", "week": wk}) for wk in (1, 2, 3, 4, 5, "all")}
    own = lambda n: a2["weeks"][n - 1]["tricky"] + a2["weeks"][n - 1]["other"]
    earlier = lambda n: [w for wk in a2["weeks"][:n - 1] for w in wk["tricky"]]
    check("words-halves: autumn 2's week 1 in play: its 12 words", wk2[1] == own(1), str(wk2[1]))
    check("words-halves: autumn 2's week 3: its 12 words, then the 8 tricky words of weeks 1 and 2 (Mr, Mrs and Ms among them)",
          wk2[3] == own(3) + earlier(3) and len(wk2[3]) == 20 and {"Mr", "Mrs", "Ms"} <= set(wk2[3]), str(wk2[3]))
    check("words-halves: autumn 2's week 5: its 12 words ('time' among them) and the 16 tricky words before it, 'time' once",
          wk2[5] == own(5) + earlier(5) and len(wk2[5]) == 28 and wk2[5].count("time") == 1, str(len(wk2[5])))
    check("words-halves: autumn 1's words don't carry into autumn 2 (only the seven it lists again: go, me, like, sure, some, what, spray)",
          all(set(v) <= a2_words for v in wk2.values()) and not ({"my", "all", "they", "said", "here"} & set(wk2[5])), str(sorted(set(wk2[5]) - a2_words)))
    check("words-halves: autumn 2's Weeks 1–5: all 59 of its words, 'time' once", len(wk2["all"]) == 59 and set(wk2["all"]) == a2_words and wk2["all"].count("time") == 1,
          str(len(wk2["all"])))
    term = await E(IP, TERM)
    check("words-halves: all of autumn: 112 words, each once (the seven shared words and 'time' once each)",
          len(term) == 112 and len(set(term)) == 112 and set(term) == a1_words | a2_words, str(len(term)))
    pending = a2_pending()
    await w_choose(page, {"half": "autumn-2", "week": 2})
    got = await E("MW.wordsGame.inPlay()")
    want = [w for w in wk2[2] if f"words-w-{w.lower()}" not in pending]
    check("words-halves: in the game only recorded words are in play (autumn 2's week 2: those recorded so far)", got == want, str(got))

    # rounds, with autumn 2's words treated as recorded through the hooks (no line is said)
    fake = await E("""(() => { const v = MW.audio.manifest.voice, out = [];
        MW.wordsGame.book.order.forEach(w => { const id = MW.wordSteps.line(w); if (!v[id]) { v[id] = { dur: 0.8 }; out.push(id); } }); return out; })()""")
    await w_choose(page, {"half": "autumn-2", "week": 3})
    rounds = await E("(() => { const out = []; for (let i = 0; i < 400; i++) out.push(MW.wordsGame.makeRound().map(q => q.word)); return out; })()")
    check("words-halves: autumn 2's week 3 rounds: five words from its words in play, at least 3 of them the week's own",
          all(len(r) == 5 and set(r) <= set(wk2[3]) and sum(1 for w in r if w in own(3)) >= 3 for r in rounds), str(rounds[:2]))
    # all of autumn: one or two secure words, then the lowest step first, so autumn 2's new words (never asked) come
    # before autumn 1's words already started (question 12)
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    secure = lambda w: days(3, "tiles", w) + days(3, "letters", w, 3) + days(3, "harder", w, 6)
    started = sorted(a1_words)
    answers = [a for w in started[:6] for a in secure(w)] + [a for w in started[6:] for a in days(1, "tiles", w)]
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", answers)
    await w_choose(page, TERM)
    rounds = await E("(() => { const out = []; for (let i = 0; i < 400; i++) out.push(MW.wordsGame.makeRound()); return out; })()")
    new = a2_words - a1_words
    check("words-halves: all of autumn rounds: one or two secure words, then autumn 2's new words first (never asked), before autumn 1's words already started",
          all(len(r) == 5 and 1 <= sum(1 for q in r if q["step"] == "secure") <= 2 and all(q["word"] in new for q in r if q["step"] != "secure") for r in rounds),
          str(rounds[:1]))
    await E("(ids) => ids.forEach(id => delete MW.audio.manifest.voice[id])", fake)
    await E("(() => { MW.store.game('words').answers = []; MW.store.save(); })()")

    # a shared word: one step in both half-terms; marked in autumn 1, plain in autumn 2 and with all of autumn
    await E("(a) => { MW.store.game('words').answers = a; MW.store.save(); }", days(3, "tiles", "go") + days(1, "letters", "go", 3))
    marks = {}
    for label, c in (("autumn 1", {"half": "autumn-1", "week": 1}), ("autumn 2", {"half": "autumn-2", "week": 2}), ("all of autumn", TERM),
                     ("autumn 1's weeks", {"half": "autumn-1", "week": "all"}), ("autumn 2's weeks", {"half": "autumn-2", "week": "all"})):
        await w_choose(page, c)
        marks[label] = await E("""(() => { const G = MW.wordsGame; MW.world.st.phase = 'map'; G.nextRound = ['go']; const r = G.makeRound();
            G.showBuild({ word: 'go', step: 'tiles' }); const out = { step: r[0].step, places: G.st.places.map(p => p.tricky),
            marked: G.st.tiles.filter(t => t.el.classList.contains('is-tricky')).map(t => t.text), sounds: G.st.places.map(p => p.sound) };
            G.showBuild({ word: 'go', step: 'letters' }); out.letters = G.st.tiles.filter(t => t.el.classList.contains('is-tricky')).map(t => t.text);
            MW.world.home(); return out; })()""")
    check("words-halves: 'go' keeps one step in both half-terms (letters, wherever it is played)", {m["step"] for m in marks.values()} == {"letters"}, json.dumps(marks))
    check("words-halves: 'go' is marked tricky in autumn 1 (sound tiles and letters: its o)", marks["autumn 1"]["marked"] == ["o"] and marks["autumn 1"]["letters"] == ["o"]
          and marks["autumn 1's weeks"]["marked"] == ["o"], json.dumps(marks["autumn 1"]))
    check("words-halves: ... and plain in autumn 2 and with all of autumn (no tile marked in any step), its o still saying oa",
          all(marks[k]["marked"] == [] and marks[k]["letters"] == [] and marks[k]["places"] == [False, False] and marks[k]["sounds"] == ["g", "oa"]
              for k in ("autumn 2", "all of autumn", "autumn 2's weeks")), json.dumps(marks))
    tab = {}
    for label, c in (("autumn 1", {"half": "autumn-1", "week": 1}), ("autumn 2", {"half": "autumn-2", "week": 2}), ("all of autumn", TERM)):
        await w_choose(page, c)
        tab[label] = await E("""(() => { MW.grownups.openPanel(); MW.grownups.show('words-progress');
            const c = Array.from(document.querySelectorAll('.words-grid .words-cell')).filter(c => c.lastChild.textContent === 'go');
            const out = c.map(x => x.className); MW.grownups.close(); return out; })()""")
    check("words-halves: the Words tab shows 'go' once, at the same step, in autumn 1, autumn 2 and all of autumn",
          all(v == ["words-cell is-letters"] for v in tab.values()), json.dumps(tab))
    others = await E("""(() => { const S = MW.wordSteps, b = MW.wordsGame.book;
        return ['like', 'me', 'what', 'some', 'sure', 'spray'].map(w => [w, S.marked(b, { half: 'autumn-1', week: 5 }, w), S.marked(b, { half: 'autumn-2', week: 5 }, w), S.marked(b, { term: 'autumn' }, w)]); })()""")
    check("words-halves: like and me tricky in autumn 1 only; what, some and sure in both; spray in neither",
          others == [["like", True, False, False], ["me", True, False, False], ["what", True, True, True], ["some", True, True, True], ["sure", True, True, True], ["spray", False, False, False]],
          str(others))
    own_week = await E("(() => { const m = MW.wordSteps.marks(MW.wordsGame.book, { term: 'autumn' }); return [m.time, m.go, m.my]; })()")
    check("words-halves: a word's own week (for the harder-letters tray) is the first week that lists it in the half-term that decides it: 'time' week 3's, 'go' autumn 2 week 2's",
          own_week == [{"half": "autumn-2", "week": 3, "tricky": False}, {"half": "autumn-2", "week": 2, "tricky": False}, {"half": "autumn-1", "week": 1, "tricky": True}],
          str(own_week))
    await E("(() => { MW.store.game('words').answers = []; MW.store.save(); })()")

    # "these" and "even": a tile used twice says one sound each time, left to right
    await w_choose(page, {"half": "autumn-2", "week": 4})
    tw = await E("""(() => { const G = MW.wordsGame, out = {}; MW.world.st.phase = 'map';
        const said = () => MW.events.filter(e => e.type === 'words' && e.detail.startsWith('sound')).map(e => e.detail);
        const drop = t => { const st = G.st, sl = st.ship.slots[st.next]; G.drop(t, 150 + sl.x * st.ship.scale, 195 + sl.y * st.ship.scale, false); };
        ['these', 'even'].forEach(w => {
          G.showBuild({ word: w, step: 'tiles' });
          const st = G.st, n = said().length, picks = [];
          out[w] = { sounds: st.places.map(p => p.sound) };
          // pick up every tile in the tray, in turn, before any is placed; then build, picking up each tile before placing it
          st.tiles.forEach(t => G.sayTile(t)); picks.push(said().slice(n));
          const m = said().length;
          st.places.forEach(p => { const t = st.tiles.find(c => !c.placed && c.text === p.text); G.sayTile(t); drop(t); });
          out[w].tray = picks[0]; out[w].build = said().slice(m); out[w].done = MW.world.st.phase === 'words-built';
          MW.world.home(); });
        return out; })()""")
    zid = "words-s-z" + (" not recorded yet" if "words-s-z" in pending else "")
    check("words-halves: 'these' in sound tiles: th (as in this), e says ee, s says z, the last e nothing",
          tw["these"]["sounds"] == ["th-voiced", "ee", "z", "-"] and tw["these"]["done"], json.dumps(tw["these"]))
    check("words-halves: ... built left to right, the e's say ee, then nothing; the s says z (quiet until it is recorded)",
          tw["these"]["build"] == ["sound words-s-th-voiced", "sound words-s-ee", f"sound {zid}", "sound e: none"], json.dumps(tw["these"]["build"]))
    check("words-halves: ... and either e picked up first says ee (the e's are the same tile)",
          tw["these"]["tray"].count("sound words-s-ee") == 2 and "sound e: none" not in tw["these"]["tray"], json.dumps(tw["these"]["tray"]))
    check("words-halves: 'even': the first e says ee, the second e (question 4)",
          tw["even"]["sounds"] == ["ee", "v", "e", "n"] and tw["even"]["build"] == ["sound words-s-ee", "sound words-s-v", "sound words-s-e", "sound words-s-n"],
          json.dumps(tw["even"]))
    bad = await E("""(() => { const d = JSON.parse(JSON.stringify(MW.wordsData)); d.words.these.sounds.e = ['ee']; d.words.even.sounds.e = ['ee', 'e', 'e'];
        return MW.wordSteps.read(d).problems; })()""")
    check("words-halves: a sound list of the wrong length is reported as a problem in the words file",
          len(bad) == 2 and "these" in bad[0] + bad[1] and "even" in bad[0] + bad[1], str(bad))
    bad = await E("""(() => { const d = JSON.parse(JSON.stringify(MW.wordsData)), h = d.terms[0].halves;
        h[1].weeks[0].other.push('bird'); d.words.mr = { tiles: 'm r', spares: 'n' }; h[0].weeks[0].other.push('mr'); d.words.ms = { tiles: '[M] [s]', sounds: { M: '-', s: '-' }, spares: 'M' };
        d.words.Ms.spares = 'M'; return MW.wordSteps.read(d).problems; })()""")
    check("words-halves: the words file's other new checks: a word listed twice in a week, two words differing only in capitals, a capital spare",
          len(bad) == 3 and any("listed twice" in b for b in bad) and any("only in capitals" in b for b in bad) and any("never a spare" in b for b in bad), str(bad))
    shared_ok = await E("""(() => { const d = JSON.parse(JSON.stringify(MW.wordsData)); return MW.wordSteps.read(d).problems.length; })()""")
    check("words-halves: a word in two weeks ('time') or two half-terms (go) is no longer a problem", shared_ok == 0, str(shared_ok))

    # capitals: Mrs with a capital M in all three steps; its sound tiles silent; never a capital in another word's tray
    await w_choose(page, {"half": "autumn-2", "week": 2})
    mrs = await E("""(() => { const G = MW.wordsGame, out = {}; MW.world.st.phase = 'map';
        ['tiles', 'letters', 'harder'].forEach(step => { G.showBuild({ word: 'Mrs', step: step }); const st = G.st;
          const n = MW.events.length; st.tiles.forEach(t => G.sayTile(t));
          out[step] = { places: st.places.map(p => (p.tricky ? '[' + p.text + ']' : p.text)), tray: st.tiles.map(c => c.text + (c.spare ? '*' : '')).sort(),
            sounds: MW.events.slice(n).filter(e => e.type === 'words').map(e => e.detail), said: MW.events.slice(n).filter(e => e.type === 'say').length,
            font: st.tiles.map(c => { const s = getComputedStyle(c.el.querySelector('.words-tile-text')); return [c.text, s.fontSize, s.fontFamily.split(',')[0].replace(/["']/g, '').trim(), s.fontWeight]; }) };
          MW.world.home(); });
        G.showBuild({ word: 'Mrs', step: 'letters' });
        const st = G.st, sl = st.ship.slots[0];
        G.drop(st.tiles.find(c => c.spare && c.text === 'm'), 150 + sl.x * st.ship.scale, 195 + sl.y * st.ship.scale, false);
        out.small = [st.next, st.drops];
        G.drop(st.tiles.find(c => c.text === 'M'), 150 + sl.x * st.ship.scale, 195 + sl.y * st.ship.scale, false);
        out.capital = [st.next, st.drops]; MW.world.home(); return out; })()""")
    check("words-halves: Mrs in sound tiles: [M] [r] [s], a capital M, all marked tricky", mrs["tiles"]["places"] == ["[M]", "[r]", "[s]"] and mrs["tiles"]["tray"] == ["M", "r", "s"],
          json.dumps(mrs["tiles"]))
    check("words-halves: ... its sound tiles are silent (each says nothing, nothing is spoken)",
          sorted(mrs["tiles"]["sounds"]) == ["sound M: none", "sound r: none", "sound s: none"] and mrs["tiles"]["said"] == 0, json.dumps(mrs["tiles"]["sounds"]))
    check("words-halves: Mrs in letters: M r s with the spare, a small m", mrs["letters"]["places"] == ["[M]", "[r]", "[s]"] and mrs["letters"]["tray"] == ["M", "m*", "r", "s"],
          json.dumps(mrs["letters"]))
    upper = [x for x in mrs["harder"]["tray"] if x.rstrip("*") != x.rstrip("*").lower()]
    check("words-halves: Mrs in harder letters: 10 tiles, its capital M once, the small m, the rest small letters",
          len(mrs["harder"]["tray"]) == 10 and upper == ["M"] and "m*" in mrs["harder"]["tray"], json.dumps(mrs["harder"]))
    fonts = {tuple(f[1:]) for st in ("tiles", "letters", "harder") for f in mrs[st]["font"]}
    check("words-halves: the capital M is a tile like any other: Andika, bold, the same size as the small letters", len(fonts) == 1 and list(fonts)[0][1] == "Andika",
          str(fonts))
    check("words-halves: a small m dropped where the capital M goes is a wrong try (it floats back); the capital goes in",
          mrs["small"] == [0, 1] and mrs["capital"] == [1, 1], json.dumps(mrs))
    caps = await E("""(() => { const S = MW.wordSteps, b = MW.wordsGame.book, out = [];
        [{ half: 'autumn-2', week: 2 }, { half: 'autumn-2', week: 'all' }, { term: 'autumn' }].forEach(c => {
          S.inPlay(b, c).forEach(w => { for (let i = 0; i < 6; i++) { ['letters', 'harder'].forEach(step => {
            const p = S.plan(b, w, step, S.fillFrom(b, c, w), Math.random, S.marked(b, c, w));
            const own = new Set(w.split(''));
            p.tray.forEach(t => { if (S.isCapital(t.text) && (!own.has(t.text) || t.spare)) out.push(w + ' ' + step + ': ' + t.text); }); }); } }); });
        const spares = b.order.filter(w => b.words[w].spares.some(S.isCapital));
        return [out.slice(0, 5), out.length, spares]; })()""")
    check("words-halves: no capital in any other word's tray, never as a spare or a filler (letters and harder letters, every word in play, 6 times each)",
          caps[1] == 0 and caps[2] == [], json.dumps(caps))
    mr = await E("['Mr', 'Mrs', 'Ms'].map(w => [MW.wordsGame.book.words[w].line, MW.wordsGame.book.words[w].spares.join(' ')])")
    check("words-halves: Mr, Mrs and Ms: their lines words-w-mr, words-w-mrs, words-w-ms (small letters); each with the spare m",
          mr == [["words-w-mr", "m"], ["words-w-mrs", "m"], ["words-w-ms", "m"]], str(mr))
    check("words-halves: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_move(p):
    """The one-time move (question 1): a 0.6.0 save (week 5, 'all' or no week) and a tablet with nothing saved open on
    Autumn 2 week 1 with every answer kept; a 0.7.0 save keeps its choice; one the file doesn't have falls back to the start."""
    print("\n== MeeMee Rockets 0.7.0: the one-time move to autumn 2 ==")
    browser = await p.chromium.launch()
    answers = [w_ans(T0 + d * DAY, "of") for d in range(3)] + [w_ans(T0 + d * DAY, "go") for d in range(3)] + [w_ans(T0, "magnet", first=False)]
    cases = [
        ("a 0.6.0 save with week 5", {"week": 5, "answers": answers}, A2, "moved"),
        ("a 0.6.0 save with Weeks 1–5 ('all')", {"week": "all", "answers": answers}, A2, "moved"),
        ("a 0.6.0 save with answers but no week", {"answers": answers}, A2, "moved"),
        ("a tablet with nothing saved for the game", None, A2, "nothing"),
        ("a 0.7.0 save: autumn 1, week 3", {"half": "autumn-1", "week": 3, "answers": answers}, {"half": "autumn-1", "week": 3}, "kept"),
        ("a 0.7.0 save: autumn 2's Weeks 1–5", {"half": "autumn-2", "week": "all", "answers": answers}, {"half": "autumn-2", "week": "all"}, "kept"),
        ("a 0.7.0 save: all of autumn", {"term": "autumn", "half": "autumn-1", "week": 2, "answers": answers}, TERM, "kept"),
        ("a saved half-term the file doesn't have (spring 1)", {"half": "spring-1", "week": 1, "answers": answers}, A2, "kept"),
        ("a saved week the file doesn't have (autumn 2, week 6)", {"half": "autumn-2", "week": 6, "answers": answers}, A2, "kept"),
        ("a saved term the file doesn't have (spring)", {"term": "spring", "half": "spring-1", "week": 1, "answers": answers}, A2, "kept"),
    ]
    for label, save, want, how in cases:
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, is_mobile=True)
        stored = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True}, "answers": [], "games": {"words": save} if save is not None else {}}
        await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                                  % json.dumps(json.dumps(stored)))
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        got = await page.evaluate("""(() => { const m = MW.wordSteps.statuses(MW.wordsGame.answers()), s = JSON.parse(localStorage.getItem('mimi-world'));
            return { choice: MW.wordsGame.choice(), answers: MW.wordsGame.answers(), steps: [MW.wordSteps.step(m, 'of'), MW.wordSteps.step(m, 'go'), MW.wordSteps.step(m, 'magnet')],
              stored: (s.games || {}).words || null, moved: MW.events.filter(e => e.type === 'words' && e.detail.startsWith('moved')).length }; })()""")
        await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('words-progress')")
        await asyncio.sleep(0.2)
        chips = await page.evaluate("Array.from(document.querySelectorAll('.words-half.is-on, .words-week.is-on')).map(b => b.textContent)")
        await page.evaluate("MW.grownups.close()")
        kept = got["answers"] == (save or {}).get("answers", []) and (save is None or got["steps"] == ["letters", "letters", "tiles"])
        if how == "moved":
            stored_ok = got["moved"] == 1 and {k: v for k, v in got["stored"].items() if k != "answers"} == A2
        elif how == "nothing":
            stored_ok = got["moved"] == 0 and got["stored"] is None
        else:
            stored_ok = got["moved"] == 0 and got["stored"] == save
        chips_ok = chips == (["All of autumn"] if want == TERM else [{"autumn-1": "Autumn 1", "autumn-2": "Autumn 2"}[want["half"]],
                                                                     "Weeks 1–5" if want["week"] == "all" else f"Week {want['week']}"])
        check(f"words-move: {label}: opens on {json.dumps(want)}, every answer kept"
              + {"moved": " (the move is saved, once)", "nothing": " (and nothing is saved for the game)", "kept": " (the save is left as it was)"}[how],
              got["choice"] == want and kept and stored_ok and chips_ok, json.dumps([got["choice"], got["steps"], got["stored"] if how != "kept" else "", got["moved"], chips]))
        if how == "moved" and label.endswith("week 5"):
            # the move happens once: a grown-up's choice after it holds over a reload
            await w_choose(page, {"half": "autumn-1", "week": 4})
            await page.reload()
            await page.wait_for_load_state("load")
            again = await page.evaluate("[MW.wordsGame.choice(), MW.events.filter(e => e.type === 'words' && e.detail.startsWith('moved')).length, MW.wordsGame.answers().length]")
            check("words-move: after the move, a grown-up's choice (autumn 1, week 4) holds over a reload, and the move doesn't happen again",
                  again == [{"half": "autumn-1", "week": 4}, 0, len(answers)], str(again))
        check(f"words-move: {label}: no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


TAB_STATE = """(() => { const b = document.querySelector('.gu-body');
    const chip = sel => Array.from(b.querySelectorAll(sel)).map(x => x.textContent + (x.classList.contains('is-on') ? '*' : ''));
    const rows = Array.from(b.querySelectorAll('.words-grid-label')).map(l => [l.textContent, Array.from(l.nextElementSibling.querySelectorAll('.words-cell')).map(c => c.lastChild.textContent)]);
    const g = b.querySelector('.words-grid');
    return { headings: Array.from(b.querySelectorAll('.gu-h3')).map(h => h.textContent), halves: chip('.words-half'), weeks: chip('.words-week'),
      notes: Array.from(b.querySelectorAll('.gu-note')).map(n => n.textContent), rows: rows,
      cells: Object.fromEntries(Array.from(b.querySelectorAll('.words-grid .words-cell')).map(c => [c.lastChild.textContent, c.className.split(' ').find(x => x.startsWith('is-'))])),
      wide: g ? [g.scrollWidth, b.clientWidth] : null, choice: MW.wordsGame.choice() }; })()"""


async def tap_chip(t, page, sel, text):
    """Tap a chip in the grown-ups area (stage px from where it is drawn), as a finger would."""
    box = await page.evaluate("""([sel, text]) => { const b = Array.from(document.querySelectorAll(sel)).find(b => b.textContent === text);
        b.scrollIntoView({ block: 'nearest' }); const r = b.getBoundingClientRect();
        return [(r.left + r.width / 2 - MW.stage.offX) / MW.stage.scale, (r.top + r.height / 2 - MW.stage.offY) / MW.stage.scale]; }""", [sel, text])
    await t.tap(*box)
    await asyncio.sleep(0.4)


async def test_words_tab(p, name, vw, vh, dpr):
    """The Words tab (boards Grownups9Week and Grownups9All): the half-term row and the week row, the term chip hiding the
    week row, the notes and the grid, with real taps, at one tablet's size."""
    print(f"\n== MeeMee Rockets 0.7.0: the Words tab with half-terms ({name}) ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    days = lambda n, step, w, start=0: [w_ans(T0 + (start + d) * DAY, w, step) for d in range(n)]
    secure = lambda w: days(3, "tiles", w) + days(3, "letters", w, 3) + days(3, "harder", w, 6)
    # as on the boards: go, some and what secure; me and spray in letters; like in harder letters; sure in sound tiles
    words = (secure("go") + secure("some") + secure("what") + days(3, "tiles", "me") + days(1, "letters", "me", 3) + days(3, "tiles", "spray")
             + days(3, "tiles", "like") + days(3, "letters", "like", 3) + days(1, "harder", "like", 6) + days(1, "tiles", "sure"))
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
    saved = {"v": 1, "music": True, "settings": {"check": "tap", "checkPicked": True}, "answers": [], "games": {"words": {"answers": words}}}   # as saved by 0.6.0
    await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                              % json.dumps(json.dumps(saved)))
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    t = Tablet(page, await ctx.new_cdp_session(page))
    halves = {h["id"]: h for h in await page.evaluate("MW.wordsGame.book.halves")}
    pending = a2_pending()
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('words-progress')")
    await asyncio.sleep(0.4)
    s = await page.evaluate(TAB_STATE)
    a2 = halves["autumn-2"]
    check(f"words-tab ({name}): a 'Half-term' heading and its row (Autumn 1, Autumn 2, All of autumn) above 'Week in play'",
          s["headings"] == ["Half-term", "Week in play"] and s["halves"] == ["Autumn 1", "Autumn 2*", "All of autumn"], json.dumps(s["headings"] + s["halves"]))
    check(f"words-tab ({name}): the week row: autumn 2's weeks 1 to 5, then Weeks 1–5, week 1 on (where a 0.6.0 tablet starts)",
          s["weeks"] == ["Week 1*", "Week 2", "Week 3", "Week 4", "Week 5", "Weeks 1–5"], str(s["weeks"]))
    check(f"words-tab ({name}): the note, as on the board: 'Autumn 2, week 1: this week's words, then the tricky words of the weeks before it. A change starts with the next round.'",
          s["notes"][0] == "Autumn 2, week 1: this week's words, then the tricky words of the weeks before it. A change starts with the next round.", s["notes"][0])
    later = []
    for wk in a2["weeks"][1:]:
        for w in wk["tricky"] + wk["other"]:
            if w not in later:
                later.append(w)
    check(f"words-tab ({name}): the grid: week 1's tricky words, its other words, then later weeks' words (all autumn 2's, each once: 'time' once)",
          s["rows"] == [["Tricky words", a2["weeks"][0]["tricky"]], ["Week 1 words", a2["weeks"][0]["other"]], ["Later weeks", later]] and len(s["cells"]) == 59,
          json.dumps(s["rows"])[:300])
    want = {"go": "is-secure", "some": "is-secure", "what": "is-secure", "me": "is-letters", "spray": "is-letters", "like": "is-harder", "sure": "is-tiles", "Mrs": "is-notyet"}
    check(f"words-tab ({name}): each word shows its step, kept from autumn 1 for the shared words (as on the board)", all(s["cells"].get(w) == v for w, v in want.items()),
          str({w: s["cells"].get(w) for w in want}))
    waiting = [n for n in s["notes"] if n.startswith("Waiting for a recording")]
    want_waiting = [w for w in await page.evaluate("MW.wordsGame.book.order") if f"words-w-{w.lower()}" in pending]
    quiet = [n for n in s["notes"] if n.startswith("Tile sounds waiting")]
    want_quiet = [x[8:] for x in await page.evaluate("MW.wordSteps.soundLines(MW.wordsGame.book)") if x in pending]
    check(f"words-tab ({name}): the words and tile sounds still waiting for a recording are listed ({len(want_waiting)} words, {len(want_quiet)} sounds)",
          (waiting == [f"Waiting for a recording, so not in play yet: {', '.join(want_waiting)}."] if want_waiting else not waiting)
          and (quiet == [f"Tile sounds waiting for a recording (those tiles are quiet until then): {', '.join(want_quiet)}."] if want_quiet else not quiet), json.dumps([waiting, quiet])[:300])
    check(f"words-tab ({name}): no problems in the words file", not any(n.startswith("To fix") for n in s["notes"]), str([n for n in s["notes"] if n.startswith("To fix")]))
    check(f"words-tab ({name}): the grid fits without sideways scrolling", s["wide"][0] <= s["wide"][1], str(s["wide"]))
    await screenshot(page, f"{name}-words-tab-autumn2-week1.png")

    # the whole term: the week row and its heading go; the note and the grid as on the board
    await tap_chip(t, page, ".words-half", "All of autumn")
    s = await page.evaluate(TAB_STATE)
    order, tricky = term_order([halves["autumn-1"], a2])
    check(f"words-tab ({name}): tapping All of autumn puts the whole term in play; the week row and its heading aren't shown",
          s["choice"] == TERM and s["halves"] == ["Autumn 1", "Autumn 2", "All of autumn*"] and s["headings"] == ["Half-term"] and s["weeks"] == [],
          json.dumps([s["choice"], s["halves"], s["headings"], s["weeks"]]))
    check(f"words-tab ({name}): the note, as on the board: 'All of autumn plays every word from both half-terms, 112 in all, leaning on the ones that need the most work. A change starts with the next round.'",
          s["notes"][0] == "All of autumn plays every word from both half-terms, 112 in all, leaning on the ones that need the most work. A change starts with the next round.",
          s["notes"][0])
    check(f"words-tab ({name}): the grid: every tricky word, then every other word, each once (112), in the order first listed, go, me, like and spray with the other words",
          s["rows"] == [["Tricky words", [w for w in order if tricky[w]]], ["Other words", [w for w in order if not tricky[w]]]] and len(s["cells"]) == 112
          and all(w in s["rows"][1][1] for w in ("go", "me", "like", "spray")) and all(w in s["rows"][0][1] for w in ("sure", "some", "what")), json.dumps(s["rows"])[:300])
    check(f"words-tab ({name}): ... at the same steps", all(s["cells"].get(w) == v for w, v in want.items()), str({w: s["cells"].get(w) for w in want}))
    check(f"words-tab ({name}): ... and it fits without sideways scrolling", s["wide"][0] <= s["wide"][1], str(s["wide"]))
    await screenshot(page, f"{name}-words-tab-all-of-autumn.png")
    rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 200; i++) MW.wordsGame.makeRound().forEach(q => out.add(q.word)); return Array.from(out); })()")
    recorded = [w for w in order if f"words-w-{w.lower()}" not in pending]
    check(f"words-tab ({name}): rounds then come from every recorded word of the term", set(rounds) <= set(recorded) and len(rounds) >= 20, str(len(rounds)))

    # back to a half-term: its week row comes back, on the week picked before
    await tap_chip(t, page, ".words-half", "Autumn 1")
    s = await page.evaluate(TAB_STATE)
    check(f"words-tab ({name}): tapping Autumn 1: its weeks come back, on week 1 (the week picked before)",
          s["choice"] == {"half": "autumn-1", "week": 1} and s["halves"] == ["Autumn 1*", "Autumn 2", "All of autumn"] and s["headings"] == ["Half-term", "Week in play"]
          and s["weeks"] == ["Week 1*", "Week 2", "Week 3", "Week 4", "Week 5", "Weeks 1–5"]
          and s["notes"][0] == "Autumn 1, week 1: this week's words, then the tricky words of the weeks before it. A change starts with the next round.", json.dumps(s["notes"][:1]))
    a1 = halves["autumn-1"]
    check(f"words-tab ({name}): ... and autumn 1's grid: week 1's tricky words, its other words, later weeks (60 words; go marked tricky here)",
          [r[0] for r in s["rows"]] == ["Tricky words", "Week 1 words", "Later weeks"] and s["rows"][0][1] == a1["weeks"][0]["tricky"] and len(s["cells"]) == 60, json.dumps(s["rows"])[:200])
    await tap_chip(t, page, ".words-week", "Week 5")
    s = await page.evaluate(TAB_STATE)
    check(f"words-tab ({name}): tapping Week 5: autumn 1's week 5 in play, its note and rows",
          s["choice"] == A1 and s["notes"][0].startswith("Autumn 1, week 5: ") and [r[0] for r in s["rows"]] == ["Tricky words", "Week 5 words", "Earlier weeks"], json.dumps(s["notes"][:1]))
    await tap_chip(t, page, ".words-week", "Weeks 1–5")
    s = await page.evaluate(TAB_STATE)
    check(f"words-tab ({name}): tapping Weeks 1–5: all of autumn 1's weeks, its note as before",
          s["choice"] == {"half": "autumn-1", "week": "all"} and s["notes"][0] == "Weeks 1–5 plays every word from all five weeks, leaning on the ones that need the most work. A change starts with the next round."
          and [r[0] for r in s["rows"]] == ["Tricky words", "Other words"] and len(s["cells"]) == 60, json.dumps(s["notes"][:1]))
    await tap_chip(t, page, ".words-half", "Autumn 2")
    s = await page.evaluate(TAB_STATE)
    check(f"words-tab ({name}): tapping Autumn 2 keeps Weeks 1–5: all of autumn 2's weeks (59 words, 'time' once)",
          s["choice"] == {"half": "autumn-2", "week": "all"} and s["weeks"][-1] == "Weeks 1–5*" and len(s["cells"]) == 59
          and sum(len(r[1]) for r in s["rows"]) == 59, json.dumps([s["choice"], len(s["cells"])]))
    await screenshot(page, f"{name}-words-tab-autumn2-weeks.png")
    await tap_chip(t, page, ".words-week", "Week 3")
    await page.evaluate("MW.grownups.close()")
    await page.reload()
    await page.wait_for_load_state("load")
    check(f"words-tab ({name}): the choice holds after a reload", await page.evaluate("MW.wordsGame.choice()") == {"half": "autumn-2", "week": 3})
    check(f"words-tab ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_shared(p):
    """A shared word in real rounds: 'go' plain in autumn 2 (no tile marked, no "That's the tricky bit."), marked in autumn 1."""
    print("\n== MeeMee Rockets 0.7.0: a shared word in autumn 1 and autumn 2 ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "words-shared", 1280, 800, 1, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    got = {}
    for label, c in (("autumn 2", {"half": "autumn-2", "week": 2}), ("autumn 1", {"half": "autumn-1", "week": 1}), ("all of autumn", TERM)):
        n = len(await t.said())
        await w_open(t, page, [{"word": "go", "step": "tiles"}], choice=c)
        await asyncio.sleep(0.3)
        await t.tap([r for r in await w_rockets(page) if r["word"] == "go"][0]["x"], 450)
        await w_wait(page, ["words-build"])
        await asyncio.sleep(0.3)
        tiles = await w_tiles(page)
        if label == "autumn 2":
            await screenshot(page, "words-shared-go-autumn2.png")
        await w_build(t)
        await w_wait_said(t, "words-you-built words-w-go", after=n)
        await asyncio.sleep(0.2)
        got[label] = {"marked": sorted(c["text"] for c in tiles if c["tricky"]), "tricky_bit": (await t.said())[n:].count("words-tricky-bit"),
                      "sounds": await w_sounds_said(t, n)}
        await w_wait(page, ["words-done"], 20)
        await t.tap(*HOME)
        await t.wait_screen("screen-map")
        await asyncio.sleep(0.6)
    check("words-shared: in autumn 2 'go' is built from plain tiles (none marked) and 'That's the tricky bit.' isn't said",
          got["autumn 2"]["marked"] == [] and got["autumn 2"]["tricky_bit"] == 0, json.dumps(got["autumn 2"]))
    check("words-shared: in autumn 1 its o is marked and 'That's the tricky bit.' is said", got["autumn 1"]["marked"] == ["o"] and got["autumn 1"]["tricky_bit"] == 1,
          json.dumps(got["autumn 1"]))
    check("words-shared: with all of autumn the later half-term decides: plain", got["all of autumn"]["marked"] == [] and got["all of autumn"]["tricky_bit"] == 0,
          json.dumps(got["all of autumn"]))
    check("words-shared: what each tile says doesn't change: g, then oa, in each", all(v["sounds"] == ["words-s-g", "words-s-oa"] for v in got.values()), json.dumps(got))
    step = await page.evaluate("(() => { const m = MW.wordSteps.statuses(MW.wordsGame.answers()); return [m.go.answers, m.go.step, MW.wordsGame.answers().map(a => a.w)]; })()")
    check("words-shared: its three answers are kept as one word's (one step wherever it is played)", step[0] == 3 and step[2] == ["go", "go", "go"], str(step))
    check("words-shared: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_words_mrs(p, name, vw, vh, dpr):
    """Mrs built with a capital M in a real round (board Rockets9Mrs): letters with the small m as the spare, then its silent
    sound tiles, then Mr in harder letters, at one tablet's size."""
    print(f"\n== MeeMee Rockets 0.7.0: Mrs with a capital M ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"words-mrs-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    week2 = {"half": "autumn-2", "week": 2}
    s = await w_open(t, page, [{"word": "Mrs", "step": "letters"}], choice=week2)
    await asyncio.sleep(0.4)
    rockets = await w_rockets(page)
    said = await t.said()
    check(f"words-mrs ({name}): Find asks for Mrs (its line words-w-mrs: quiet until it is recorded)",
          s["screen"] == "screen-words-find" and "Mrs" in [r["word"] for r in rockets] and "words-find words-w-mrs" in said, json.dumps([s, [r["word"] for r in rockets]]))
    fit = await page.evaluate("MW.wordsGame.st.rockets.filter(r => r.word).map(r => [r.wordEl.textContent, r.wordEl.getBoundingClientRect().width / MW.stage.scale <= r.wordEl.parentNode.getBoundingClientRect().width / MW.stage.scale - 27.5])")
    check(f"words-mrs ({name}): 'Mrs' on its rocket with a capital M, and every word fits its plate", any(x[0] == "Mrs" for x in fit) and all(x[1] for x in fit), str(fit))
    await screenshot(page, f"{name}-words-mrs-find.png")
    await t.tap([r for r in rockets if r["word"] == "Mrs"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    await asyncio.sleep(0.4)
    tiles = await w_tiles(page)
    check(f"words-mrs ({name}): Build: Mrs in letters, M r s, every place marked as the tricky part (a whole tricky word)",
          s["mode"] == "letters" and s["places"] == ["M", "r", "s"], json.dumps(s))
    check(f"words-mrs ({name}): the tray: the capital M, r and s (marked) and the spare, a small m (not marked)",
          sorted((c["text"], c["tricky"], c["spare"]) for c in tiles) == [("M", True, False), ("m", False, True), ("r", True, False), ("s", True, False)], str(tiles))
    text = (await page.inner_text("#screen-words-build")).split()
    check(f"words-mrs ({name}): nothing to read on Build but the tiles", sorted(text) == ["M", "m", "r", "s"], str(text))
    n = len(await t.said())
    await w_place(t)
    await asyncio.sleep(0.5)
    check(f"words-mrs ({name}): the capital M snaps into the first porthole, and 'That's the tricky bit.'",
          (await w_state(page))["next"] == 1 and "words-tricky-bit" in (await t.said())[n:], str((await t.said())[n:]))
    await screenshot(page, f"{name}-words-mrs-letters.png")
    small = [c for c in await w_tiles(page) if c["text"] == "m"][0]
    await w_drop_wrong(t, spare=True)
    back = [c for c in await w_tiles(page) if c["text"] == "m"][0]
    check(f"words-mrs ({name}): the small m on the word is a wrong try: it floats back",
          (await w_state(page))["drops"] == 1 and (await w_state(page))["next"] == 1 and abs(back["x"] - small["hx"]) < 2 and abs(back["y"] - small["hy"]) < 2, str(back))
    await w_build(t)
    s = await w_wait(page, ["words-built", "words-done"], 5)
    built = await page.evaluate("Array.from(document.querySelectorAll('#screen-words-build .words-ship .words-tile')).map(e => e.textContent).join('')")
    check(f"words-mrs ({name}): Mrs built: M, r, s", built == "Mrs", built)
    await w_wait(page, ["words-done"], 20)
    rec = await page.evaluate("MW.wordsGame.answers().slice(-1)[0]")
    check(f"words-mrs ({name}): saved as the word Mrs, with one wrong drop", rec["w"] == "Mrs" and rec["drops"] == 1, json.dumps(rec))
    await t.tap(*HOME)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.6)

    # sound tiles: each pick-up is silent
    await w_open(t, page, [{"word": "Mrs", "step": "tiles"}], choice=week2)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "Mrs"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    await asyncio.sleep(0.4)
    n = len(await t.said())
    for c in await w_tiles(page):
        await w_pick(t, c)
        await asyncio.sleep(0.15)
    await w_build(t)
    await w_wait(page, ["words-built", "words-done"], 5)
    check(f"words-mrs ({name}): Mrs in sound tiles: M r s, and picking up each tile says nothing",
          s["mode"] == "tiles" and s["places"] == ["M", "r", "s"] and await w_sounds_said(t, n) == [], str(await w_sounds_said(t, n)))
    await w_wait(page, ["words-done"], 20)
    await t.tap(*HOME)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.6)

    # harder letters: Mr's tray of 10, its capital M once, everything else small
    await w_open(t, page, [{"word": "Mr", "step": "harder"}], choice=week2)
    await asyncio.sleep(0.3)
    await t.tap([r for r in await w_rockets(page) if r["word"] == "Mr"][0]["x"], 450)
    s = await w_wait(page, ["words-build"])
    await asyncio.sleep(0.4)
    tiles = await w_tiles(page)
    caps = [c["text"] for c in tiles if c["text"] != c["text"].lower()]
    check(f"words-mrs ({name}): Mr in harder letters: 10 tiles in two rows, one capital M (its own), the small m spare, the rest small letters",
          s["mode"] == "harder" and len(tiles) == 10 and caps == ["M"] and any(c["text"] == "m" and c["spare"] for c in tiles)
          and len({round(c["y"]) for c in tiles}) == 2, str([c["text"] for c in tiles]))
    await screenshot(page, f"{name}-words-mr-harder.png")
    await w_build(t)
    await w_wait(page, ["words-done"], 20)
    check(f"words-mrs ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


SPRING = """{ id: 'spring', name: 'Spring', all: 'All of spring', halves: [
        { id: 'spring-1', name: 'Spring 1', weeks: [
          { week: 1, tricky: ['said', 'you'], other: ['day', 'play', 'spring'] },
          { week: 2, tricky: ['one'], other: ['toy', 'magnet'] } ] }%s ] }"""
SPRING2 = """,
        { id: 'spring-2', name: 'Spring 2', weeks: [ { week: 1, tricky: ['here'], other: ['say', 'boy'] } ] }"""


async def test_words_spring(p):
    """A third half-term added to a copy of the words data (a spring term) shows in the Words tab and plays, with no code
    change; a second spring half-term brings its own whole-term choice, named from the file."""
    print("\n== MeeMee Rockets 0.7.0: a spring half-term from the words file alone ==")
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    end_terms, words_open = "\n    ],\n    sounds: {", "\n    words: {\n"
    check("words-spring: the page holds the words file as written (one list of terms, one list of words)", html.count(end_terms) == 1 and html.count(words_open) == 1)
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    for halves in (1, 2):
        data = SPRING % (SPRING2 if halves == 2 else "")
        page_html = html.replace(end_terms, ",\n      " + data + end_terms).replace(
            words_open, words_open + "      spring: { tiles: 's p r i ng', spares: 'a' },\n")
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, is_mobile=True)
        await ctx.route(ORIGIN + "/", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=page_html))
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        t = Tablet(page, await ctx.new_cdp_session(page))
        book = await page.evaluate("(() => { const b = MW.wordsGame.book; return [b.problems, b.terms.map(t => t.id), b.halves.map(h => h.id), b.order.length]; })()")
        check(f"words-spring ({halves} spring half-term{'s' if halves > 1 else ''}): the words file with spring added reads with no problems",
              book[0] == [] and book[1] == ["autumn", "spring"] and book[2][:3] == ["autumn-1", "autumn-2", "spring-1"] and book[3] == 113, json.dumps(book))
        await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('words-progress')")
        await asyncio.sleep(0.3)
        s = await page.evaluate(TAB_STATE)
        want = ["Autumn 1", "Autumn 2*", "All of autumn", "Spring 1"] + (["Spring 2", "All of spring"] if halves == 2 else [])
        check(f"words-spring ({halves}): the Words tab's half-term row: " + ", ".join(w.rstrip("*") for w in want)
              + ("" if halves == 2 else " (no All of spring with one half-term: its weeks are the same words)"), s["halves"] == want, str(s["halves"]))
        if halves == 1:
            await tap_chip(t, page, ".words-half", "Spring 1")
            s = await page.evaluate(TAB_STATE)
            check("words-spring (1): tapping Spring 1: its weeks (Week 1, Week 2, Weeks 1–2), week 1 on, named from the file",
                  s["choice"] == {"half": "spring-1", "week": 1} and s["weeks"] == ["Week 1*", "Week 2", "Weeks 1–2"]
                  and s["notes"][0] == "Spring 1, week 1: this week's words, then the tricky words of the weeks before it. A change starts with the next round.", json.dumps(s["notes"][:1]))
            check("words-spring (1): ... its grid: week 1's tricky words, its other words, later weeks",
                  s["rows"] == [["Tricky words", ["said", "you"]], ["Week 1 words", ["day", "play", "spring"]], ["Later weeks", ["one", "toy", "magnet"]]], json.dumps(s["rows"]))
            check("words-spring (1): ... and its new word, not yet recorded, is listed as waiting", any("spring" in n and n.startswith("Waiting") for n in s["notes"]), str(s["notes"][-4:]))
            await screenshot(page, "doogee-words-tab-spring.png")
            rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 200; i++) MW.wordsGame.makeRound().forEach(q => out.add(q.word)); return Array.from(out); })()")
            check("words-spring (1): rounds then come from spring 1's week 1 (its recorded words)", sorted(rounds) == ["day", "play", "said", "you"], str(sorted(rounds)))
            marked = await page.evaluate("['one', 'day', 'said'].map(w => MW.wordSteps.marked(MW.wordsGame.book, { half: 'spring-1', week: 2 }, w))")
            check("words-spring (1): spring 1's tricky words are marked from its own lists", marked == [True, False, True], str(marked))
        else:
            await tap_chip(t, page, ".words-half", "All of spring")
            s = await page.evaluate(TAB_STATE)
            check("words-spring (2): All of spring plays both spring half-terms, its note named and counted from the file",
                  s["choice"] == {"term": "spring"} and s["weeks"] == []
                  and s["notes"][0] == "All of spring plays every word from both half-terms, 11 in all, leaning on the ones that need the most work. A change starts with the next round.",
                  json.dumps(s["notes"][:1]))
        check(f"words-spring ({halves}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_words_unrecorded(p):
    """Nothing in the choice in play recorded yet (autumn 2's week 1 before Barney's recordings): tapping the planet goes
    back to the map and says "That planet isn't ready yet."; the Words tab says why, only while nothing in it is recorded.
    The words' recordings are taken off the page through the hooks, so this holds once autumn 2 is recorded too."""
    print("\n== MeeMee Rockets 0.7.0: nothing recorded yet in the choice in play ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "words-unrecorded", 1280, 800, 1, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    off = """(c) => { const S = MW.wordSteps, v = MW.audio.manifest.voice; window.__off = window.__off || {};
        S.inPlay(MW.wordsGame.book, c).forEach(w => { const id = S.line(w); if (v[id]) { window.__off[id] = v[id]; delete v[id]; } }); }"""
    back = "(() => { Object.assign(MW.audio.manifest.voice, window.__off || {}); window.__off = {}; })()"
    note = """(() => { MW.grownups.openPanel(); MW.grownups.show('words-progress');
        const n = Array.from(document.querySelectorAll('.gu-body .gu-note')).map(p => p.textContent).filter(t => t.startsWith('Nothing in'));
        MW.grownups.close(); return n; })()"""
    await page.evaluate(off, A2)
    check("words-unrecorded: a tablet with nothing saved plays autumn 2's week 1, and none of its words is recorded (here)",
          await page.evaluate("[MW.wordsGame.choice(), MW.wordsGame.inPlay().length]") == [A2, 0])
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.6)
    pl = await page.evaluate(WORDS_PLANET)
    for k in (1, 2):
        n = len(await t.said())
        e0 = await page.evaluate("MW.events.length")
        await t.tap(pl["x"], pl["y"])
        said = await w_wait_said(t, "map-not-ready", 12, after=n)
        await asyncio.sleep(1.5)
        got = await page.evaluate("""(e0) => [MW.shell.screen, MW.world.st.phase, MW.events.slice(e0).some(e => e.type === 'words' && e.detail === 'no words in play'),
            MW.events.slice(e0).some(e => e.type === 'screen' && e.detail === 'screen-words-find')]""", e0)
        after = (await t.said())[n:]
        check(f"words-unrecorded: tapping the planet ({'again' if k == 2 else 'first'}): its name, then back on the map with 'That planet isn't ready yet.'",
              said and got == ["screen-map", "map", True, False] and after == ["words-name", "map-not-ready"], json.dumps([got, after]))
        if k == 1:
            await screenshot(page, "words-unrecorded-map.png")
    check("words-unrecorded: ... and the round never started (no Find, no 'Ready to launch some rockets?')",
          "words-round-ready" not in await t.said() and await page.evaluate("MW.wordsGame.st.round.length") == 0)
    got = await page.evaluate(note)
    check("words-unrecorded: the Words tab says so: 'Nothing in Autumn 2, week 1 is recorded yet, so MeeMee Rockets won't start until it is.'",
          got == ["Nothing in Autumn 2, week 1 is recorded yet, so MeeMee Rockets won't start until it is."], str(got))
    for label, c in (("autumn 2's week 2 (go and me recorded)", {"half": "autumn-2", "week": 2}), ("autumn 1's week 5", A1), ("all of autumn", TERM)):
        await w_choose(page, c)
        got = await page.evaluate(note)
        check(f"words-unrecorded: no such note with {label}: something there is recorded", got == [], str(got))
    await page.evaluate(off, {"half": "autumn-2", "week": "all"})
    await w_choose(page, {"half": "autumn-2", "week": "all"})
    got = await page.evaluate(note)
    check("words-unrecorded: with autumn 2's Weeks 1–5 and none of it recorded: 'Nothing in Autumn 2, Weeks 1–5 is recorded yet, …' (named from the words file)",
          got == ["Nothing in Autumn 2, Weeks 1–5 is recorded yet, so MeeMee Rockets won't start until it is."], str(got))
    await page.evaluate(off, TERM)
    await w_choose(page, TERM)
    got = await page.evaluate(note)
    check("words-unrecorded: with all of autumn and none of it recorded: 'Nothing in Autumn is recorded yet, …'",
          got == ["Nothing in Autumn is recorded yet, so MeeMee Rockets won't start until it is."], str(got))
    await page.evaluate(back)
    await w_choose(page, A1)
    s = await w_open(t, page, [{"word": "toy", "step": "tiles"}], choice=None)
    check("words-unrecorded: with autumn 1's week 5 picked, the planet starts the game as before", s["screen"] == "screen-words-find", json.dumps(s))
    check("words-unrecorded: no console errors", not problems, "; ".join(problems[:3]))
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
    made = await page.evaluate("""(() => { const g = MW.store.game('words'); g.half = 'autumn-1'; g.week = 3; MW.store.save();
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
    await n_quiet(t)                                         # a tap during the hint does nothing (0.8.1)
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

    # counting mode (0.8.1, B2): a double tap with too few is one wrong check, not two; the second tap does nothing while
    # Scruffles is answering. A second wrong check, once he is quiet, brings the hint; taps during the hint leave it in place.
    await page.evaluate("MW.store.setting('answerMode', 'counting')")
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    await t.wait_phase(["open"], 20)
    await n_quiet(t)
    await t.fill(2, "right")
    n0 = len(await t.said())
    await w_double_tap(t, *POD)                              # too few, twice in quick succession: one wrong check
    await asyncio.sleep(0.6)
    says = await n_says_after(t, n0)
    check("counting: a double tap with too few is one wrong check ('Let's look again.' once, no hint): the second tap does nothing while he is answering (0.8.1)",
          says == ["again-look-again"] and await page.evaluate("MW.rescue.st.tries") == 1 and not await page.evaluate("MW.rescue.st.hinted"),
          json.dumps(says))
    await n_quiet(t)
    await t.tap(*POD)                                        # a second wrong check, once he is quiet: the hint
    await asyncio.sleep(0.6)
    await w_double_tap(t, *POD)                              # and more taps during the hint
    await asyncio.sleep(0.4)
    await t.tap(*POD)
    await n_quiet(t)
    says = await n_says_after(t, n0)
    st = await t.state()
    hint = await page.evaluate("[MW.rescue.st.hinted, document.querySelectorAll('#screen-game .mw-ghost').length, document.querySelectorAll('#screen-game .mw-ghost.is-lit').length]")
    check("counting: the second wrong check brings the hint, and taps during the hint leave it in place (nothing more is said, still two tries)",
          says[-1:] == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"] and len(says) == 2 and hint == [True, 2, 2]
          and st["placed"] == 2 and await page.evaluate("MW.rescue.st.tries") == 2, json.dumps([says, hint, st]))
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


# ---------------------------------------------------------------- 0.8.0: the map's five places, and the minus sentence
STUB_PLACE_LINE = """(() => { if (!window.__recorded) window.__recorded = MW.audio.recorded;
    MW.audio.recorded = id => id === 'map-place-not-ready' || window.__recorded(id); })()"""
UNSTUB_PLACE_LINE = "(() => { if (window.__recorded) { MW.audio.recorded = window.__recorded; delete window.__recorded; } })()"
# as while "That place isn't ready yet." was still pending (it was recorded on 16 October 2026, 0.8.1)
PENDING_PLACE_LINE = """(() => { if (!window.__recorded) window.__recorded = MW.audio.recorded;
    MW.audio.recorded = id => id === 'map-place-not-ready' ? false : window.__recorded(id); })()"""
MAP_LOCKED_LINE = "MW.audio.recorded('map-place-not-ready') ? 'map-place-not-ready' : 'map-not-ready'"


async def tap_said(t, sx, sy):
    """Tap a point on the map; the lines said because of it, and the screen afterwards."""
    n = len(await t.said())
    await t.tap(sx, sy)
    await asyncio.sleep(0.5)
    return (await t.said())[n:], await t.page.evaluate("MW.shell.screen")


# Taps the review found silent when the rocks' and the station's tap areas were 170 across (0.8.0): the station's wing
# ends and the outer rocks. With 240 (Barney, 15 October 2026) a tap anywhere on their drawings is heard.
FAR_TAPS = {3: [(590, 652), (605, 660), (780, 676)], 4: [(750, 182), (972, 190)]}
# Where taps on each place's drawing land: every shape's outline sampled along its length (and the outer edge of its ink
# outline), each landing on the place's button, its badge or its lock, or on something else; and the drawing's left,
# right, top and bottom ends. owner() names what a tap at a stage point lands on.
REACH_JS = """(places => { """ + SHAPES_JS + """
    const buttons = document.querySelectorAll('#screen-map .mw-planet');
    const owner = (x, y) => { const e = document.elementFromPoint(MW.stage.offX + x * k, MW.stage.offY + y * k);
        const b = e && e.closest('.mw-planet, .mw-planet-badge, .mw-planet-lock, button');
        if (!b) return 'nothing';
        const i = Array.prototype.indexOf.call(buttons, b);
        if (i >= 0) return 'place ' + i;
        for (let j = 0; j < L.length; j++) {
            if (b.classList.contains('mw-planet-badge') && b.offsetLeft === L[j].badge.x && b.offsetTop === L[j].badge.y) return 'place ' + j + ' badge';
            if (b.classList.contains('mw-planet-lock') && b.offsetLeft === L[j].lock.x && b.offsetTop === L[j].lock.y) return 'place ' + j + ' lock'; }
        return b.className || b.tagName; };
    return places.map(i => { const p = L[i], pts = [], s = shapes(i);
        s.forEach(el => { const m = el.getCTM(), n = el.getTotalLength(), sw = parseFloat(el.getAttribute('stroke-width') || 0) * Math.hypot(m.a, m.b) / 2;
            for (let j = 0; j <= 48; j++) { const q = el.getPointAtLength(n * j / 48), x = m.a * q.x + m.c * q.y + m.e, y = m.b * q.x + m.d * q.y + m.f;
                pts.push([x, y]);
                if (sw) { const d = Math.hypot(x - p.x, y - p.y) || 1; pts.push([x + (x - p.x) / d * sw, y + (y - p.y) / d * sw]); } } });
        const mine = o => o === 'place ' + i || o === 'place ' + i + ' badge' || o === 'place ' + i + ' lock';
        const missed = pts.map(q => [Math.round(q[0]), Math.round(q[1]), owner(q[0], q[1])]).filter(q => !mine(q[2]));
        const end = f => { const q = pts.reduce((a, b) => f(b, a) ? b : a); return [Math.round(q[0] * 10) / 10, Math.round(q[1] * 10) / 10, owner(q[0], q[1])]; };
        return { i: i, shapes: s.length, points: pts.length, missed: missed.length, misses: missed.slice(0, 6),
                 far: Math.round(pts.reduce((a, q) => Math.max(a, Math.hypot(q[0] - p.x, q[1] - p.y)), 0) * 10) / 10,
                 ends: { left: end((a, b) => a[0] < b[0]), right: end((a, b) => a[0] > b[0]), top: end((a, b) => a[1] < b[1]), bottom: end((a, b) => a[1] > b[1]) } }; }); })"""
# What each place's tap area (a circle, tap across) comes near: every other place's button, badge and lock, the crew,
# Music and the grown-ups lock, each with its distance from the circle's middle (to the nearest point of its box), and
# whether a tap on its own middle still lands on it.
OVERLAP_JS = """(places => { const L = MW.LAYOUT.map.planets, k = MW.stage.scale;
    const sb = e => { const r = e.getBoundingClientRect(); return [(r.left - MW.stage.offX) / k, (r.top - MW.stage.offY) / k, r.width / k, r.height / k]; };
    const things = Array.from(document.querySelectorAll('#screen-map .mw-planet')).map((b, j) => ['place ' + j, b, j]);
    document.querySelectorAll('#screen-map .mw-planet-badge, #screen-map .mw-planet-lock').forEach(e => { const kind = e.classList.contains('mw-planet-badge') ? 'badge' : 'lock';
        const j = L.findIndex(q => q[kind].x === e.offsetLeft && q[kind].y === e.offsetTop); things.push(['place ' + j + ' ' + kind, e, j]); });
    things.push(['the crew', document.querySelector('#screen-map .mw-map-crew-btn'), -1], ['Music', document.querySelector('#screen-map .mw-music'), -1],
                ['the grown-ups lock', document.querySelector('.mw-gate'), -1]);
    return places.map(i => { const p = L[i], r = p.tap / 2;
        const near = things.filter(n => n[2] !== i).map(n => { const b = sb(n[1]), cx = Math.max(b[0], Math.min(p.x, b[0] + b[2])), cy = Math.max(b[1], Math.min(p.y, b[1] + b[3]));
            const top = document.elementFromPoint(MW.stage.offX + (b[0] + b[2] / 2) * k, MW.stage.offY + (b[1] + b[3] / 2) * k);
            return [n[0], Math.round(Math.hypot(cx - p.x, cy - p.y)), !!top && n[1].contains(top)]; }).sort((a, b) => a[1] - b[1]);
        return { i: i, r: r, things: near.length, inside: near.filter(n => n[1] <= r), covered: near.filter(n => !n[2]).map(n => n[0]), nearest: near.slice(0, 3) }; }); })"""
WHAT = {3: "the rocks", 4: "the station"}


def reach_ok(r):
    mine = (f"place {r['i']}", f"place {r['i']} badge", f"place {r['i']} lock")
    return r["shapes"] > 0 and r["missed"] == 0 and all(e[2] in mine for e in r["ends"].values())


def far_points(r):
    """The review's points for a place, then its drawing's left, right, top and bottom ends."""
    return [tuple(q) for q in FAR_TAPS[r["i"]]] + [(e[0], e[1]) for e in r["ends"].values()]


async def test_places(p, name, vw, vh, dpr):
    """The map has five places: the three planets, the rocks and the station. A place with no game is dimmed with its
    lock and says "That place isn't ready yet." when tapped ("That planet isn't ready yet." while that line is pending).
    A tap anywhere on the rocks' or the station's drawing is heard (their tap areas are 240 across), locked and lit, and
    those tap areas reach nothing else. MeeMee Rescue and MeeMee Rockets open as before."""
    print(f"\n== the map's five places ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"places-{name}", vw, vh, dpr, mode="tap")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await asyncio.sleep(1.0)
    await page.screenshot(path=str(SHOTS / f"places-{name}-map.png"))
    sys.path.insert(0, str(ROOT / "tools"))
    import games as G
    games = {g["planet"]: g["name"] for g in G.load()}           # from each game.json: with 0.8.0's part B, 0, 1 and 2
    free = [i for i in range(G.PLANETS) if i not in games]
    info = await page.evaluate(PLACES_INFO)
    check(f"places ({name}): the map has five places; each with a game ({', '.join(f'{g} on {i}' for i, g in games.items())}) is lit, with its badge and a mint halo",
          len(info) == 5 and G.PLANETS == 5 and {i["i"]: i["game"] for i in info if i["game"]} == games and all(place_ok(info[i], g) for i, g in games.items()),
          json.dumps([info[i] for i in games]))
    if free:
        check(f"places ({name}): the places with no game ({', '.join(map(str, free))}) are dimmed, each with its lock badge and no halo",
              all(place_ok(info[i], None) for i in free), json.dumps([info[i] for i in free]))
    else:
        check(f"places ({name}): the places with no game are dimmed, each with its lock badge and no halo", True, "skipped: every place has a game")
    taps = await page.evaluate("MW.LAYOUT.map.planets.map(p => p.tap)")
    centred = all(abs(i["tap"][0] + i["tap"][2] / 2 - pl["x"]) < 0.6 and abs(i["tap"][1] + i["tap"][3] / 2 - pl["y"]) < 0.6
                  for i, pl in zip(info, await page.evaluate("MW.LAYOUT.map.planets")))
    check(f"places ({name}): every place is a big target, centred on it (the rocks and the station: 240 across)",
          centred and min(i["tap"][2] for i in info) >= 120 and [info[3]["tap"][2], info[4]["tap"][2]] == [240, 240] and taps[3:] == [240, 240], json.dumps(taps))

    # a tap anywhere on the rocks' or the station's drawing lands on that place, and their tap areas reach nothing else
    reach = await page.evaluate(REACH_JS, [3, 4])
    looks = " and ".join(f"{WHAT[r['i']]} {'lit' if r['i'] in games else 'locked'}" for r in reach)
    check(f"places ({name}): a tap anywhere on the drawing of {looks} lands on that place (every outline, its outer edge, and the drawing's far ends)",
          all(reach_ok(r) for r in reach), json.dumps(reach))
    over = await page.evaluate(OVERLAP_JS, [3, 4])
    check(f"places ({name}): the rocks' and the station's tap areas reach no other place's button, badge or lock, the crew, Music or the grown-ups lock",
          all(o["things"] >= 9 and not o["inside"] and not o["covered"] for o in over), json.dumps(over))

    if free:
        # while "That place isn't ready yet." is pending (stubbed: it was recorded on 16 October 2026): "That planet isn't
        # ready yet.", never silence
        await page.evaluate(PENDING_PLACE_LINE)
        rec = await page.evaluate("[MW.audio.recorded('map-place-not-ready'), MW.audio.recorded('map-not-ready')]")
        got = []
        for i in free:
            pl = await page.evaluate("MW.LAYOUT.map.planets[%d]" % i)
            got.append([i] + list(await tap_said(t, pl["x"], pl["y"])))
        tried = await page.evaluate("MW.events.filter(e => e.type === 'audio-fail' && e.detail.indexOf('map-place-not-ready') >= 0).length")
        check(f"places ({name}): while the new line is pending, each locked place says 'That planet isn't ready yet.' and stays on the map",
              rec == [False, True] and all(g[1] == ["map-not-ready"] and g[2] == "screen-map" for g in got) and tried == 0, json.dumps([rec, got, tried]))
        ends = [r for r in reach if r["i"] in free]
        got = []
        for r in ends:
            for x, y in far_points(r):
                got.append([r["i"], x, y] + list(await tap_said(t, x, y)))
        check(f"places ({name}): taps at the far ends of {' and '.join(WHAT[r['i']] for r in ends) or 'the rocks and the station'} (the review's points, and each drawing's left, right, top and bottom) are heard too",
              all(g[3] == ["map-not-ready"] and g[4] == "screen-map" for g in got), json.dumps(got) if ends else "skipped: both have a game")

        # once it is recorded (stubbed, in case it isn't on this page), "That place isn't ready yet."
        await page.evaluate(UNSTUB_PLACE_LINE)
        await page.evaluate(STUB_PLACE_LINE)
        got = []
        for i in free:
            pl = await page.evaluate("MW.LAYOUT.map.planets[%d]" % i)
            got.append([i] + list(await tap_said(t, pl["x"], pl["y"])))
        if 4 in free:
            lock = await page.evaluate("MW.LAYOUT.map.planets[4].lock")
            got.append(["station's lock badge"] + list(await tap_said(t, lock["x"] + lock["d"] / 2, lock["y"] + lock["d"] / 2)))
        check(f"places ({name}): once it is recorded, each locked place (and the station's lock badge) says 'That place isn't ready yet.'",
              all(g[1] == ["map-place-not-ready"] and g[2] == "screen-map" for g in got), json.dumps(got))
        await page.evaluate(UNSTUB_PLACE_LINE)
        await asyncio.sleep(1.0)
    else:
        for what in ("while the new line is pending, each locked place says 'That planet isn't ready yet.'",
                     "taps at the far ends of the rocks and the station are heard too",
                     "once it is recorded, each locked place says 'That place isn't ready yet.'"):
            check(f"places ({name}): {what}", True, "skipped: every place has a game")

    # MeeMee Rescue and MeeMee Rockets open as before
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(*RESCUE)
    s = await t.wait_phase(["asking", "open"])
    check(f"places ({name}): MeeMee Rescue's planet opens it as before (its banner, then the round)",
          s["screen"] == "screen-game" and "map-mimi-rescue" in await t.said() and await page.evaluate("MW.events.some(e => e.type === 'banner' && e.detail === 'gone MeeMee Rescue')"), json.dumps(s))
    await t.tap(*HOME_BTN)
    await t.wait_screen("screen-map")
    await asyncio.sleep(0.5)
    s = await w_open(t, page, [{"word": "one", "step": "tiles"}])
    check(f"places ({name}): MeeMee Rockets' planet opens it as before (its banner, then Find)",
          s["screen"] == "screen-words-find" and "words-name" in await t.said(), json.dumps(s))
    await t.tap(*HOME_BTN)
    check(f"places ({name}): Home goes back to the map", await t.wait_screen("screen-map"))
    check(f"places ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()
    await places_lit(p, name, vw, vh, dpr, [i for i in (3, 4) if i in free])


async def places_lit(p, name, vw, vh, dpr, spots):
    """The rocks and the station with a game on each (the starter game, and a second copy of it), in a test copy built
    into the template test's folders: lit with their badges and halos, a tap anywhere on their drawings opens their game,
    and their tap areas still reach nothing else."""
    import shutil
    import subprocess
    label = f"places lit ({name})"
    if not spots:
        check(f"{label}: the rocks and the station with a game on them", True, "skipped: neither is free for the starter game")
        return
    here = pathlib.Path(__file__).resolve().parent
    out, srcs = here / "serve-template", here / "serve-template-src"
    if srcs.exists():
        shutil.rmtree(srcs)
    made = {}
    for gid, place in zip(("starter", "startertwo"), spots):
        d = srcs / gid
        shutil.copytree(ROOT / "games" / "_template", d, ignore=shutil.ignore_patterns("__pycache__"))
        for f in d.iterdir():
            if f.is_file():
                f.write_text(f.read_text(encoding="utf-8").replace("starter", gid), encoding="utf-8")
        gj = json.loads((d / "game.json").read_text(encoding="utf-8"))
        gj["planet"] = place
        gj["name"] = "Starter game" if gid == "starter" else "Starter game two"
        (d / "game.json").write_text(json.dumps(gj), encoding="utf-8")
        made[place] = (gid, gj["name"])
    cmd = [sys.executable, str(ROOT / "tools" / "build.py"), "--no-audio", "--out", str(out)]
    for gid, _ in made.values():
        cmd += ["--extra-game", str(srcs / gid)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    check(f"{label}: a test copy with the starter game on {' and '.join(WHAT[i] for i in spots)} builds", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", TPL_PORT), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
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
        await asyncio.sleep(1.0)
        await page.screenshot(path=str(SHOTS / f"places-{name}-lit.png"))
        info = await page.evaluate(PLACES_INFO)
        check(f"{label}: {' and '.join(WHAT[i] for i in spots)} are lit, each with its badge and a mint halo",
              all(place_ok(info[i], made[i][1]) for i in spots), json.dumps([info[i] for i in spots]))
        if 4 in spots:                                       # 0.9.0: the redrawn station, lit, as part B will have it (board Map14)
            await page.screenshot(path=str(SHOTS9 / f"{name}-map-station-lit.png"))
            lit = await page.evaluate("""(() => { const b = document.querySelectorAll('#screen-map .mw-planet-badge'), L = MW.LAYOUT.map.planets[4].badge;
                const e = Array.from(b).find(e => e.offsetLeft === L.x && e.offsetTop === L.y); return e ? [e.offsetLeft, e.offsetTop, e.offsetWidth] : null; })()""")
            check(f"{label}: with a game on the station (0.9.0), its badge is at 944, 56 (84 across) and it has its halo, at full colour",
                  lit == [944, 56, 84] and info[4]["halo"] == 1 and info[4]["lit"], json.dumps([lit, info[4]]))
        reach = await page.evaluate(REACH_JS, spots)
        check(f"{label}: a tap anywhere on their drawings lands on that place or its badge (every outline, its outer edge, and the drawing's far ends)",
              all(reach_ok(x) for x in reach), json.dumps(reach))
        over = await page.evaluate(OVERLAP_JS, spots)
        check(f"{label}: their tap areas reach no other place's button, badge or lock, the crew, Music or the grown-ups lock",
              all(o["things"] >= 9 and not o["inside"] and not o["covered"] for o in over), json.dumps(over))
        got = []
        for x in reach:
            gid = made[x["i"]][0]
            for sx, sy in far_points(x):
                await t.tap(sx, sy)
                opened = await t.wait_screen(f"screen-{gid}-play", 3)
                await t.tap(*HOME_BTN)
                back = await t.wait_screen("screen-map", 5)
                await asyncio.sleep(0.3)
                got.append([x["i"], sx, sy, opened, back])
        check(f"{label}: taps at their far ends (the review's points, and each drawing's left, right, top and bottom) open their game",
              all(g[3] and g[4] for g in got), json.dumps(got))
        check(f"{label}: no console errors", not problems, "; ".join(problems[:3]))
        await browser.close()
    finally:
        srv.shutdown()
        srv.server_close()


# The number sentence as it is on the screen: its box, each part (text, ring or sign, colours, box in stage px) and gap()
EQ_INFO = """(() => { const e = window.__eq, el = e.el, k = MW.stage.scale;
    const sb = r => [(r.left - MW.stage.offX) / k, (r.top - MW.stage.offY) / k, r.width / k, r.height / k];
    const parts = Array.from(el.children).map(c => { const cs = getComputedStyle(c);
        return { text: c.textContent, ring: c.classList.contains('mw-equation-gap'), op: c.classList.contains('op'), color: cs.color,
                 bg: cs.backgroundColor, rim: [cs.borderTopStyle, cs.borderTopWidth, cs.borderTopColor], box: sb(c.getBoundingClientRect()) }; });
    return { shown: el.classList.contains('is-shown'), box: [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight],
             seen: sb(el.getBoundingClientRect()), parts: parts, gap: e.gap(), html: el.innerHTML,
             log: MW.events.filter(x => x.type === 'equation').map(x => x.detail) }; })()"""
COLOURS = """(names => { const d = document.createElement('div'); document.body.appendChild(d); const out = {};
    names.forEach(n => { d.style.color = 'var(--' + n + ')'; out[n] = getComputedStyle(d).color; }); d.remove(); return out; })"""
EQ_SCREEN = """(() => { const s = document.getElementById('screen-kittest');
    const d = MW.diagram(s); d.look('numbers'); d.set({ whole: 7, left: 3, right: 4, missing: 'left' });
    MW.pod(s, MW.LAYOUT.pod.x, MW.LAYOUT.pod.y, MW.LAYOUT.pod.w); MW.stars(s, 517, 34).set(0);
    window.__tr = MW.numberTrack(s); window.__eq = MW.equation(s); })()"""


def near(a, b, tol=0.6):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def gap_box(g):
    return [g["x"], g["y"], g["w"], g["h"]] if g else None


async def test_equation(p, name, vw, vh, dpr):
    """MW.equation: MeeMee Rescue's sentence as before; the minus sentence with no gap and with each of its three gaps;
    fill; gap() where the ring is on the screen; its two places, under the diagram and under Scruffles."""
    print(f"\n== the number sentence ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"equation-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate(KIT_SCREEN)
    await page.evaluate(EQ_SCREEN)
    tok = await page.evaluate(COLOURS, ["moon", "peach", "mint", "moon-dim"])
    under, ship = [180, 700, 400, 80], [790, 528, 440, 100]

    # MeeMee Rescue's sentence, exactly as before
    await page.evaluate("window.__eq.show(3, 4, 7)")
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): MeeMee Rescue's sentence is as before: 3 + 4 = 7 under the diagram (180, 700, 400 × 80)",
          eq["html"] == '<span>3</span><span class="op">+</span><span>4</span><span class="op">=</span><span>7</span>' and eq["shown"] and eq["box"] == under
          and eq["gap"] is None and eq["log"] == [], json.dumps([eq["html"], eq["box"], eq["log"]]))
    await page.evaluate("window.__eq.hide()")
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): ... and hide() takes it away", eq["html"] == "" and not eq["shown"], eq["html"])

    # the minus sentence with no gap: the minus sign (not a hyphen), in peach like = ; numbers in moon
    await page.evaluate("window.__eq.minus(7, 4, 3)")
    eq = await page.evaluate(EQ_INFO)
    texts = [x["text"] for x in eq["parts"]]
    colours = [x["color"] for x in eq["parts"]]
    check(f"equation ({name}): minus(7, 4, 3) shows 7 − 4 = 3 at once, with the minus sign (U+2212), no gap",
          texts == ["7", "−", "4", "=", "3"] and "-" not in "".join(texts) and eq["shown"] and eq["gap"] is None
          and not any(x["ring"] for x in eq["parts"]) and eq["log"][-1:] == ["minus 7-4=3"], json.dumps([texts, eq["log"]]))
    check(f"equation ({name}): ... − and = in peach, the numbers in moon",
          colours == [tok["moon"], tok["peach"], tok["moon"], tok["peach"], tok["moon"]], json.dumps([colours, tok]))
    await page.evaluate("window.__eq.minus(7, 4, 3, null)")
    check(f"equation ({name}): ... and the same with gap null", [x["text"] for x in (await page.evaluate(EQ_INFO))["parts"]] == ["7", "−", "4", "=", "3"])

    # each of the three gaps: the ring in that number's place, 84 across, moon-dim with a 5 px dashed mint rim
    for k, want in ((0, "minus ?-4=3"), (1, "minus 7-?=3"), (2, "minus 7-4=?")):
        await page.evaluate(f"window.__eq.minus(7, 4, 3, {k})")
        await asyncio.sleep(0.05)
        eq = await page.evaluate(EQ_INFO)
        ring = eq["parts"][2 * k]
        others = [x["text"] for i, x in enumerate(eq["parts"]) if i != 2 * k]
        expect = [x for i, x in enumerate(["7", "−", "4", "=", "3"]) if i != 2 * k]
        check(f"equation ({name}): gap {k}: the ring stands in for {'7 4 3'.split()[k]}, 84 across, moon-dim, 5 px dashed mint rim",
              ring["ring"] and ring["text"] == "" and others == expect and near(ring["box"][2:], [84, 84]) and ring["bg"] == tok["moon-dim"]
              and ring["rim"] == ["dashed", "5px", tok["mint"]] and sum(x["ring"] for x in eq["parts"]) == 1, json.dumps(ring))
        check(f"equation ({name}): gap {k}: gap() is the ring's box on the screen, and the log says '{want}'",
              near(gap_box(eq["gap"]), ring["box"]) and eq["log"][-1] == want, json.dumps([eq["gap"], ring["box"], eq["log"][-1:]]))

    # fill: the ring becomes the number; nothing more to fill
    await page.evaluate("window.__eq.fill(3)")
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): fill(3) turns the ring into 3: 7 − 4 = 3, and gap() is null",
          [x["text"] for x in eq["parts"]] == ["7", "−", "4", "=", "3"] and not any(x["ring"] for x in eq["parts"]) and eq["gap"] is None
          and eq["log"][-1] == "fill 3", json.dumps([eq["parts"], eq["log"][-2:]]))
    n = len(eq["log"])
    await page.evaluate("window.__eq.fill(5)")
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): ... a second fill does nothing", [x["text"] for x in eq["parts"]] == ["7", "−", "4", "=", "3"] and len(eq["log"]) == n)
    await page.evaluate("window.__eq.minus(10, 6, 4, 0); window.__eq.fill(10)")
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): filling the first gap: ? − 6 = 4 becomes 10 − 6 = 4", [x["text"] for x in eq["parts"]] == ["10", "−", "6", "=", "4"],
          json.dumps([x["text"] for x in eq["parts"]]))

    # its place under Scruffles, and back
    await page.evaluate("window.__eq.minus(7, 4, 3, 2); window.__eq.at('ship')")
    await asyncio.sleep(0.4)
    eq = await page.evaluate(EQ_INFO)
    ring = eq["parts"][4]
    check(f"equation ({name}): at('ship') puts it under Scruffles (790, 528, 440 × 100) at once, the ring inside it",
          eq["box"] == ship and near(eq["seen"], ship) and ring["box"][0] >= 790 and ring["box"][0] + ring["box"][2] <= 1230
          and ring["box"][1] >= 528 and ring["box"][1] + ring["box"][3] <= 628 and eq["log"][-1] == "at ship", json.dumps([eq["box"], eq["seen"], ring["box"], eq["log"][-1:]]))
    check(f"equation ({name}): ... gap() is the ring's box there", near(gap_box(eq["gap"]), ring["box"]), json.dumps([eq["gap"], ring["box"]]))
    track = await stage_box(page, "window.__tr.el.querySelector('svg')")
    pod = await stage_box(page, "document.querySelector('#screen-kittest .mw-pod svg')")
    check(f"equation ({name}): ... clear of the number track, below Scruffles's ship",
          eq["seen"][1] + eq["seen"][3] <= track[1] and ring["box"][1] + ring["box"][3] <= track[1], json.dumps([eq["seen"], ring["box"], track, pod]))
    await page.screenshot(path=str(SHOTS / f"equation-{name}-ship.png"))
    await page.evaluate("window.__eq.at('under', true)")
    moving = gap_box(await page.evaluate("window.__eq.gap()"))
    await asyncio.sleep(0.5)
    eq = await page.evaluate(EQ_INFO)
    check(f"equation ({name}): at('under', true) takes it back under the diagram; gap() says where the ring is going even while it moves",
          eq["box"] == under and near(eq["seen"], under) and near(moving, eq["parts"][4]["box"]) and near(gap_box(eq["gap"]), eq["parts"][4]["box"])
          and eq["log"][-1] == "at under", json.dumps([eq["box"], eq["seen"], moving, eq["gap"]]))
    await page.evaluate("window.__eq.fill(3); window.__tr.hide()")
    await asyncio.sleep(0.5)
    await page.screenshot(path=str(SHOTS / f"equation-{name}-under.png"))
    await page.evaluate("window.__eq.hide()")
    check(f"equation ({name}): hidden, gap() is null", await page.evaluate("window.__eq.gap()") is None)
    check(f"equation ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_equation_motion(p):
    """The sentence moves between its places over 260 ms on the snap's ease-out; with reduce motion it fades in at its
    new place. What moves is read from the animations the browser runs, so a busy machine can't fool the check."""
    print("\n== the number sentence: motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    runs = """(() => window.__eq.el.getAnimations().map(a => [a.transitionProperty || a.animationName, a.effect.getTiming().duration]).sort())()"""
    look = """(() => { const el = window.__eq.el, r = el.getBoundingClientRect(), k = MW.stage.scale, cs = getComputedStyle(el);
        return [Math.round((r.left - MW.stage.offX) / k + r.width / k / 2), Math.round((r.top - MW.stage.offY) / k + r.height / k / 2), +(+cs.opacity).toFixed(2)]; })()"""
    under, ship = [380, 740], [1010, 578]                     # the middles of its two places
    for reduce in (False, True):
        label = "reduce motion" if reduce else "motion"
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce" if reduce else "no-preference")
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        await page.evaluate(KIT_SCREEN)
        await page.evaluate(EQ_SCREEN)
        await page.evaluate("window.__eq.minus(7, 4, 3, 2)")
        await asyncio.sleep(0.45)
        for to, frm, there in (("ship", under, ship), ("under", ship, under)):
            first = await page.evaluate(f"(() => {{ window.__eq.at('{to}', true); return [{runs}, {look}]; }})()")
            await asyncio.sleep(0.12)
            mid = await page.evaluate(look)
            await asyncio.sleep(0.4)
            end = await page.evaluate(f"[{runs}, {look}]")
            if reduce:
                check(f"equation ({label}): at('{to}', true) fades it in at its new place (260 ms) without moving",
                      first[0] == [["mw-arrive", 260]] and first[1][:2] == there and first[1][2] < 0.1 and mid[:2] == there
                      and end == [[], there + [1]], json.dumps([first, mid, end]))
            else:
                timing = await page.evaluate("(() => { const cs = getComputedStyle(window.__eq.el); return [cs.transitionProperty, cs.transitionDuration, cs.transitionTimingFunction]; })()")
                check(f"equation ({label}): at('{to}', true) slides it from where it was to its new place over 260 ms on the snap's ease-out",
                      first[0] == [["transform", 260]] and first[1] == frm + [1] and end == [[], there + [1]]
                      and "transform" in timing[0] and "cubic-bezier(0.2, 0.8, 0.2, 1)" in timing[2], json.dumps([first, mid, end, timing]))
        got = await page.evaluate(f"(() => {{ window.__eq.at('ship'); const a = [{runs}, {look}]; window.__eq.at('under'); return [a, [{runs}, {look}]]; }})()")
        check(f"equation ({label}): at(place) without animate is there at once, with nothing moving or fading",
              got == [[[], ship + [1]], [[], under + [1]]], json.dumps(got))
        check(f"equation ({label}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


# ---------------------------------------------------------------- 0.8.0: Take MeeMee Home (games/takehome), subtraction
TH_PLACE = "MW.LAYOUT.map.planets[MW.world.games.find(g => g.id === 'takehome').planet]"
TH_STEPS = ("take", "left", "numbers")
TH_PRAISE = {"praise-found-it", "praise-thats-right", "praise-super-counting", "praise-well-done", "takehome-home-they-go"}   # MeeMee Rescue's four and its own
TH_UNDER, TH_SHIP = [180, 700], [790, 528]              # the sentence's two places (its box's top-left corner)
# What the game screen shows (stage px): the round's step and question, the diagram, the MeeMee, the tiles, the sentence
TH_STATE = """(() => { const R = MW.takehome, s = R.st, d = R.diagram(), tr = R.track(), e = R.equation(), g = document.getElementById('screen-takehome-play');
    const shown = el => getComputedStyle(el).display !== 'none' && !el.closest('.mw-off');
    return { phase: MW.world.st.phase, qi: s.qi, step: R.step(), target: s.target, answer: s.answer, tries: s.tries, misses: s.misses,
             hinted: s.hinted, placed: s.placed ? s.placed.n : null, screen: MW.shell.screen, look: d.look(),
             whole: s.counters.filter(c => c.where === 'whole').length, going: s.counters.filter(c => c.where === 'right').length,
             staying: s.counters.filter(c => c.where === 'left').length, fixed: s.fixed.length, dim: s.dimmed.length, hoppers: s.hoppers.length,
             carried: ['whole', 'left', 'right'].map(k => d.carried(k)), away: tr.away(), track: shown(tr.el) && !tr.away(),
             out: tr.tiles.filter(t => t.out()).map(t => t.n),
             ghosts: g.querySelectorAll('.mw-ghost').length, lit: g.querySelectorAll('.mw-ghost.is-lit').length,
             face: g.querySelector('.mw-pod').dataset.face, ready: g.querySelector('.mw-pod').classList.contains('is-ready'),
             lights: g.querySelector('.mw-pod').classList.contains('is-celebrating'),
             home: !R.homePlanet().classList.contains('is-hidden'),
             sentence: e.el.classList.contains('is-shown') ? Array.from(e.el.children).map(c => c.classList.contains('mw-equation-gap') ? '_' : c.textContent).join(' ') : '',
             at: [e.el.offsetLeft, e.el.offsetTop],
             wholeNum: shown(d.circles.whole.querySelector('.numeral-whole')) && getComputedStyle(d.circles.whole.querySelector('.numeral-whole')).visibility !== 'hidden'
                       ? d.circles.whole.textContent : null,
             pills: ['left', 'right'].map(k => { const p = d.pills[k]; return shown(p) ? p.textContent + (p.classList.contains('is-waiting') ? '~' : '') : null; }),
             waiting: ['whole', 'left', 'right'].filter(k => d.circles[k].classList.contains('is-waiting')),
             success: ['whole', 'left', 'right'].filter(k => d.circles[k].classList.contains('is-success')),
             stars: Array.from(g.querySelectorAll('.mw-stars svg')).map(x => x.dataset.state).join(',') }; })()"""
TH_EQ = "MW.events.filter(e => e.type === 'equation').map(e => e.detail)"
TH_N = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def th_q(step, q):
    """A question as the game has it: whole, take (going home), left (staying), missing (the empty circle)."""
    m = q.get("missing") or ("right" if step == "take" else "left")
    return {"whole": q["whole"], "take": q["take"], "left": q["whole"] - q["take"], "missing": m}


def th_answer(q):
    return q["whole"] if q["missing"] == "whole" else (q["take"] if q["missing"] == "right" else q["left"])


def th_prompt(step, q, qi, pending=False):
    """What Scruffles says for a question (lines.md, How they join up), as the say log has it. The first two questions of a
    round add "Move them into the dotted circle." (step 1) or "Find the number." (steps 2 and 3), then "Tap Scruffles when
    you're ready."; pending: as while those two lines were still pending, when they are left out (as MeeMee Rescue's
    "Find the number.")."""
    q = th_q(step, q)
    w, t, r = q["whole"], q["take"], q["left"]
    whole = f"num-mid-{w} takehome-meemee"
    going = f"num-mid-{t} takehome-{'is' if t == 1 else 'are'}-going"
    staying = f"num-mid-{r} takehome-{'is' if r == 1 else 'are'}-staying"
    if step == "take":
        p = [whole, going]
    elif q["missing"] == "left":
        p = [whole, going, "takehome-how-many-left"]
    elif q["missing"] == "right":
        p = [whole, staying, "takehome-how-many-going"]
    else:
        p = [going, staying, "takehome-how-many-altogether"]
    if qi < 2:
        p += ([] if pending else ["takehome-move-them" if step == "take" else "takehome-find-number"]) + ["tap-scruffles"]
    return " ".join(p)


TH_TAKE_WORDS = ["takehome-take-away", "takehome-subtract", "takehome-minus"]
TH_IS_WORDS = ["takehome-is", "takehome-equals"]
TH_SENTENCE_RE = "/takehome-(take-away|subtract|minus) num-mid-\\d+ takehome-(is|equals) num-end-/"


def th_said_sentence(q, take="takehome-take-away", is_="takehome-is"):
    """The number sentence as said (0.8.1: its words take turns; take, is_: this answer's turn, from the 'words' event)."""
    return f"num-mid-{q['whole']} {take} num-mid-{q['take']} {is_} num-end-{q['whole'] - q['take']}"


async def th_words(page):
    """The words the last right answer's sentence used (its 'words' event since window.__thq), as (take, is)."""
    w = await page.evaluate("(MW.events.filter(e => e.type === 'words' && e.t > (window.__thq || 0)).pop() || {}).detail || ''")
    return tuple(w.split()) if w else ("takehome-take-away", "takehome-is")


def th_text(q, gap=None):
    """The sentence as TH_STATE shows it: '7 − 4 = 3', with _ for the gap."""
    parts = [str(q["whole"]), "−", str(q["take"]), "=", str(q["whole"] - q["take"])]
    if gap is not None:
        parts[{"whole": 0, "right": 2, "left": 4}[gap]] = "_"
    return " ".join(parts)


async def th_state(page):
    return await page.evaluate(TH_STATE)


async def th_wait(page, phases, timeout=25):
    for _ in range(int(timeout / 0.1)):
        s = await th_state(page)
        if s["phase"] in phases:
            return s
        await asyncio.sleep(0.1)
    return await th_state(page)


async def th_until(page, js, timeout=15):
    for _ in range(int(timeout / 0.1)):
        if await page.evaluate(js):
            return True
        await asyncio.sleep(0.1)
    return False


async def th_set(page, step=None, round_=None, wholes=None):
    """This game's own saved choices (its step, its wholes in play) and the next round, as a grown-up and the tests set them."""
    await page.evaluate("""(a) => { const g = MW.store.game('takehome'); if (a.step) g.step = a.step; if (a.wholes) g.wholes = a.wholes; MW.store.save();
        if (a.round) MW.takehome.nextRound = a.round; }""", {"step": step, "round": round_, "wholes": wholes})


async def th_open(t, page, step, round_):
    """Play (if on the start screen), then place 2 on the map: the round, in this step."""
    await th_set(page, step, round_)
    if await page.evaluate("MW.shell.screen") == "screen-start":
        await t.tap(*PLAY)
        await t.wait_screen("screen-map")
    pl = await page.evaluate(TH_PLACE)
    await t.tap(pl["x"], pl["y"])
    return await th_wait(page, ["takehome-open"], 30)          # its title banner, "Let's take the MeeMee home!", the question


async def th_move(t, n, to=(560, 478)):
    """Step 1: n MeeMee dragged from the whole (a touch in its middle picks up the nearest) into the going-home part."""
    for _ in range(n):
        await t.drag(380, 205, *to)


async def th_back(t, page, n, to=(900, 300)):
    """Step 1: n MeeMee dragged back out of the going-home part."""
    for _ in range(n):
        xy = await page.evaluate("(() => { const c = MW.takehome.st.counters.filter(c => c.where === 'right').pop(); return [c.x, c.y]; })()")
        await t.drag(xy[0], xy[1], *to)


async def th_gap(page):
    g = await page.evaluate("MW.takehome.equation().gap()")
    return (g["x"] + g["w"] / 2, g["y"] + g["h"] / 2) if g else None


async def th_end_question(t, page, step, q, qi, name, shot=None):
    """After a right check: wait for the MeeMee going home to set off, then check the ending (the same for every step)."""
    q = th_q(step, q)
    ok = await th_until(page, "MW.events.some(e => e.type === 'home' && e.t > (window.__thq || 0))" if q["take"] else
                        "MW.events.some(e => e.type === 'say' && %s.test(e.detail) && e.t > (window.__thq || 0))" % TH_SENTENCE_RE, 20)
    await asyncio.sleep(0.45)
    s = await th_state(page)
    if shot:
        await screenshot(page, shot)
    hops = await page.evaluate("MW.events.filter(e => e.type === 'hop' && e.t > (window.__thq || 0)).map(e => e.detail)")
    ans = th_answer(q)
    carried = [None, None, None] if step == "take" else [q["whole"] if step == "numbers" or q["missing"] == "whole" else None,
                                                         q["left"] if step == "numbers" or q["missing"] == "left" else None,
                                                         q["take"] if step == "numbers" or q["missing"] == "right" else None]
    check(f"takehome-{step} ({name}): question {qi + 1} ({th_text(q)}): the answer is carried, the success ring, the track away, the sentence complete under the "
          f"diagram, the home planet, {q['take']} MeeMee hopping home",
          ok and s["sentence"] == th_text(q) and s["at"] == TH_UNDER and s["home"] and s["success"] == [q["missing"]] and not s["track"]
          and s["carried"] == carried and len(hops) == q["take"] and all(h.endswith(("1030,652", "1160,670", "900,666")) for h in hops),
          json.dumps([s, hops, ans]))
    return s


async def th_round(t, page, step, round_, name, shots, before=None):
    """Play a whole round right first time (all five), checking each question's look and words, the sentence's events, the
    ending and the stars. shots: {question number: (ask shot, right shot)}; before: {question number: async fn}, done once
    the question is up."""
    # the sentence's events since the round started (then since the last question ended)
    eq0 = await page.evaluate("(() => { const r = MW.events.filter(e => e.type === 'round').pop(); return MW.events.filter(e => e.type === 'equation' && e.t < r.t).length; })()")
    for qi, q0 in enumerate(round_):
        q = th_q(step, q0)
        s = await th_wait(page, ["takehome-open"], 25)
        if before and qi in before:
            await before[qi]()
            s = await th_state(page)
        await n_quiet(t)
        said = await t.said()
        check(f"takehome-{step} ({name}): question {qi + 1} ({th_text(q, q['missing'])}) asked: '{th_prompt(step, q, qi)}'",
              s["qi"] == qi and said[-1:] == [th_prompt(step, q, qi)] and s["stars"] == ",".join(["done"] * qi + ["current"] + ["todo"] * (4 - qi)),
              json.dumps([said[-1:], s["stars"]]))
        ask, right = shots.get(qi, (None, None))
        if step == "take":
            check(f"takehome-take ({name}): question {qi + 1}: {q['whole']} MeeMee in the whole (no numeral), the going-home part waits, its pill says {q['take']}, "
                  f"the other pill a waiting '?'; the home planet shows, no track, no sentence",
                  s["whole"] == q["whole"] and s["wholeNum"] is None and s["waiting"] == ["right"] and s["pills"] == ["?~", str(q["take"])]
                  and s["home"] and not s["track"] and s["sentence"] == "" and s["look"] == "counting", json.dumps(s))
            if ask:
                await th_move(t, 2)
                x0, y0 = await t.screen(380, 205)
                x1, y1 = await t.screen(500, 352)
                await touch(t, "touchStart", [(50, (x0, y0))])
                for k in range(1, 9):
                    await touch(t, "touchMove", [(50, (x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8))])
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.3)
                await screenshot(page, ask)
                x2, y2 = await t.screen(560, 478)
                await touch(t, "touchMove", [(50, (x2, y2))])
                await asyncio.sleep(0.05)
                await touch(t, "touchEnd", [])
                await asyncio.sleep(0.4)
                await th_move(t, q["take"] - 3)
            else:
                await th_move(t, q["take"])
            s = await th_state(page)
            check(f"takehome-take ({name}): question {qi + 1}: {q['take']} MeeMee moved into the going-home part, the ship's lights glow",
                  s["going"] == q["take"] and s["whole"] == q["left"] and s["ready"] and s["phase"] == "takehome-open", json.dumps(s))
        else:
            given = {"whole": q["whole"], "left": q["left"], "right": q["take"]}
            if step == "left":
                check(f"takehome-left ({name}): question {qi + 1}: the whole's {q['whole']} and the going-home part's {q['take']} as MeeMee, the staying part waits; "
                      f"no pills; the sentence waits under Scruffles ({th_text(q, 'left')}); the track; no home planet",
                      s["fixed"] == q["whole"] + q["take"] and s["carried"] == [None, None, None] and s["waiting"] == ["left"] and s["pills"] == [None, None]
                      and s["sentence"] == th_text(q, "left") and s["at"] == TH_SHIP and s["track"] and not s["home"], json.dumps(s))
            else:
                want = [None if k == q["missing"] else given[k] for k in ("whole", "left", "right")]
                check(f"takehome-numbers ({name}): question {qi + 1}: a numbered MeeMee in each given circle, the empty one waits; the sentence's gap in its place "
                      f"({th_text(q, q['missing'])}) under Scruffles; the track; no home planet",
                      s["carried"] == want and s["fixed"] == 0 and s["waiting"] == [q["missing"]] and s["pills"] == [None, None]
                      and s["sentence"] == th_text(q, q["missing"]) and s["at"] == TH_SHIP and s["track"] and not s["home"] and s["look"] == "numbers", json.dumps(s))
            ans = th_answer(q)
            c = CENTRES[q["missing"]]
            if ask:
                held = {"left": (282, 560), "right": (640, 585), "whole": (470, 300)}[q["missing"]]
                await n_hold(t, *tile_xy(ans), *held, touch_id=51)
                await screenshot(page, ask)
                x2, y2 = await t.screen(*c)
                await touch(t, "touchMove", [(51, (x2, y2))])
                await asyncio.sleep(0.05)
                await touch(t, "touchEnd", [])
                await asyncio.sleep(0.4)
                how = "in the empty circle"
            elif qi % 2:
                g = await th_gap(page)
                await t.drag(*tile_xy(ans), *g)
                how = "on the sentence's gap"
            else:
                await t.drag(*tile_xy(ans), c[0] + 20, c[1] - 15)
                how = "in the empty circle"
            s = await th_state(page)
            tile = await page.evaluate("(n => { const t = MW.takehome.track().tile(n); return [t.x, t.y]; })(%d)" % ans)
            check(f"takehome-{step} ({name}): question {qi + 1}: tile {ans} dropped {how} sits in the circle, the gap shows {ans}, the ship's lights glow",
                  s["placed"] == ans and tile == list(c) and s["sentence"] == th_text(q) and s["ready"], json.dumps([s, tile]))
        await page.evaluate("window.__thq = performance.now()")
        await n_check(t)
        s = await th_state(page)
        check(f"takehome-{step} ({name}): question {qi + 1}: a tap on Scruffles checks it: right, the got-it face and the ship's lights",
              s["phase"] == "takehome-celebrate" and s["face"] == "got-it" and s["lights"], json.dumps(s))
        s = await th_end_question(t, page, step, q, qi, name, right)
        if step == "take":
            check(f"takehome-take ({name}): question {qi + 1}: the MeeMee left in the whole slid into the staying part and were counted: its pill {q['left']}, "
                  f"the whole shows {q['whole']}",
                  s["staying"] == q["left"] and s["whole"] == 0 and s["pills"] == [str(q["left"]), str(q["take"])] and s["wholeNum"] == str(q["whole"]), json.dumps(s))
        said = await t.said()
        words = await th_words(page)
        sent = th_said_sentence(q, *words)
        i = len(said) - 1 - said[::-1].index(sent) if sent in said else -1
        if step == "take":
            # 0.8.1: the MeeMee staying are counted aloud as they slide over, between the praise and the sentence
            count = " ".join([f"num-mid-{k}" for k in range(1, q["left"])] + [f"num-end-{q['left']}"])
            check(f"takehome-take ({name}): question {qi + 1}: praise, the staying MeeMee counted aloud ('{count}'), then the sentence said: '{sent}'",
                  i > 1 and said[i - 1] == count and said[i - 2] in TH_PRAISE and words[0] in TH_TAKE_WORDS and words[1] in TH_IS_WORDS, json.dumps(said[-4:]))
        else:
            check(f"takehome-{step} ({name}): question {qi + 1}: praise, then the sentence said: '{sent}'",
                  i > 0 and said[i - 1] in TH_PRAISE and words[0] in TH_TAKE_WORDS and words[1] in TH_IS_WORDS, json.dumps(said[-3:]))
        eq = (await page.evaluate(TH_EQ))[eq0:]
        want = (["at under"] if step == "take" else ["at ship", f"minus {th_text(q, q['missing']).replace(' ', '').replace('_', '?').replace('−', '-')}", f"fill {ans}"])
        want_end = [f"minus {th_text(q).replace(' ', '').replace('−', '-')}"] if step == "take" else ["at under"]
        check(f"takehome-{step} ({name}): question {qi + 1}: the sentence's events: {', '.join(want + want_end)}",
              eq == want + want_end, json.dumps(eq))
        eq0 += len(eq)
    s = await th_wait(page, ["takehome-done"], 25)
    ok = await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'takehome-round-another')", 15)
    await asyncio.sleep(0.6)
    said = await t.said()
    check(f"takehome-{step} ({name}): after five, the end screen: five stars; 'All the MeeMee are home!', then 'Another trip?'",
          ok and await page.evaluate("MW.shell.screen") == "screen-takehome-end" and said[-2:] == ["takehome-round-done", "takehome-round-another"]
          and await page.evaluate("Array.from(document.querySelectorAll('#screen-takehome-end .mw-stars svg')).map(x => x.dataset.state).join(',')") == ",".join(["done"] * 5),
          json.dumps(said[-3:]))


async def test_takehome_round(p, step, name, vw, vh, dpr):
    """A whole round of one step, right first time, played by touch, with the boards' screenshots."""
    print(f"\n== Take MeeMee Home: a round of step {TH_STEPS.index(step) + 1} ({step}, {name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-{step}-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rounds = {"take": [{"whole": 7, "take": 4}, {"whole": 5, "take": 2}, {"whole": 9, "take": 3}, {"whole": 3, "take": 1}, {"whole": 10, "take": 6}],
              "left": [{"whole": 7, "take": 4}, {"whole": 8, "take": 5}, {"whole": 6, "take": 1}, {"whole": 10, "take": 3}, {"whole": 4, "take": 2}],
              "numbers": [{"whole": 7, "take": 4, "missing": "right"}, {"whole": 7, "take": 4, "missing": "whole"}, {"whole": 6, "take": 2, "missing": "left"},
                          {"whole": 9, "take": 1, "missing": "right"}, {"whole": 10, "take": 3, "missing": "whole"}]}
    s = await th_open(t, page, step, rounds[step])
    said = await t.said()
    check(f"takehome-{step} ({name}): place 2 opens Take MeeMee Home in this step: 'Let's take the MeeMee home!', then question 1",
          s["screen"] == "screen-takehome-play" and s["step"] == step and s["qi"] == 0 and "takehome-round-ready" in said
          and said.index("takehome-round-ready") < len(said) - 1, json.dumps([s, said[-3:]]))
    k = {"take": "s1", "left": "s2", "numbers": "s3"}[step]
    shots = {0: (f"takehome-{name}-{k}-ask.png", f"takehome-{name}-{k}-right.png")}
    before = {}
    if step == "numbers":
        async def whole_shot():                                # board s3-whole: ? − 4 = 3, the second question, before it is answered
            await asyncio.sleep(0.3)
            await screenshot(page, f"takehome-{name}-s3-whole.png")
        before = {1: whole_shot}
    await th_round(t, page, step, rounds[step], name, shots, before)
    await asyncio.sleep(1.2)
    await screenshot(page, f"takehome-{name}-{step}-end.png")
    saved = await page.evaluate("JSON.parse(localStorage.getItem('mimi-world'))")
    mine = saved["games"]["takehome"]["answers"]
    check(f"takehome-{step} ({name}): five answers saved in this game's own record for this step, each right first time; MeeMee Rescue's answers untouched",
          list(mine) == [step] and len(mine[step]) == 5 and all(a["tries"] == 0 and a["hint"] is False for a in mine[step])
          and [(a["whole"], a["take"], a["missing"]) for a in mine[step]] == [(q["whole"], q["take"], th_q(step, q)["missing"]) for q in rounds[step]]
          and saved["answers"] == [], json.dumps(saved["games"]["takehome"])[:300])
    check(f"takehome-{step} ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


TH_HOPPED = "document.querySelectorAll('#screen-takehome-play .mw-counters .mw-mimi.is-hop').length"


async def test_takehome_wrong_take(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """Step 1's wrong checks: a calm line each time and nothing punishes; too many has its own line; a MeeMee dropped
    outside the going-home part floats back; two wrong checks bring the hint (the places light up as the MeeMee to move
    are counted); the answer still has to be given, and a hinted fact isn't right first time."""
    print(f"\n== Take MeeMee Home: step 1's wrong checks and the hint ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-wrong-take-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    s = await th_open(t, page, "take", [{"whole": 7, "take": 4}, {"whole": 5, "take": 2}, {"whole": 6, "take": 3}, {"whole": 8, "take": 2}, {"whole": 4, "take": 1}])
    await n_quiet(t)
    n0 = len(await t.said())
    await t.tap(*POD)                                        # nothing moved yet: too few, tapped twice in quick succession
    await asyncio.sleep(0.12)
    await t.tap(*POD)
    await asyncio.sleep(0.4)
    s = await th_state(page)
    waited = await page.evaluate("MW.events.some(e => e.type === 'check' && e.detail === 'still answering')")
    check(f"takehome-wrong-take ({name}): Scruffles double-tapped with none moved: 'Let's look again.' once, the try-again face, one try (the second tap does "
          f"nothing while he is answering, 0.8.1), no hint",
          (await t.said())[n0:] == ["again-look-again"] and waited and s["face"] == "try-again" and s["tries"] == 1 and not s["hinted"] and s["phase"] == "takehome-open", json.dumps(s))
    await asyncio.sleep(1.8)
    s = await th_state(page)
    check(f"takehome-wrong-take ({name}): ... and Scruffles is soon thinking again (no red, nothing taken away)", s["face"] == "thinking" and s["whole"] == 7, json.dumps(s))
    # a MeeMee dropped outside the going-home part (in the sky, on the staying part) floats back to its place in the whole
    n0 = len(await t.said())
    for to in ((660, 120), (210, 470)):
        await t.drag(380, 205, *to)
        await asyncio.sleep(0.4)
    home = await page.evaluate("MW.takehome.st.counters.every(c => c.where === 'whole' && Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5)")
    s = await th_state(page)
    check(f"takehome-wrong-take ({name}): a MeeMee dropped in the sky or on the staying part floats back to its place in the whole (not a try, nothing said)",
          home and s["going"] == 0 and s["tries"] == 1 and (await t.said())[n0:] == [], json.dumps(s))
    # too many: its own line, and not the hint
    await th_move(t, 6)
    await n_check(t)
    s = await th_state(page)
    check(f"takehome-wrong-take ({name}): six moved for 7 − 4: 'That's too many. Take one back.' (a try, never the hint)",
          (await t.said())[-1:] == ["too-many"] and s["tries"] == 2 and not s["hinted"] and s["going"] == 6, json.dumps(s))
    await n_quiet(t)
    await th_back(t, page, 4)
    s = await th_state(page)
    check(f"takehome-wrong-take ({name}): four taken back out of the going-home part float back into the whole",
          s["going"] == 2 and s["whole"] == 5, json.dumps(s))
    # two in, a third wrong check (too few): the hint, the two places still to fill lit as the MeeMee to move are counted
    hopped0 = await page.evaluate(TH_HOPPED)
    await n_check(t)
    s = await th_state(page)
    said = await t.said()
    check(f"takehome-wrong-take ({name}): then too few: 'Count them with me. One, two, three, four.', with a ghost in each place still to fill (2)",
          said[-1:] == ["again-count-with-me num-mid-1 num-mid-2 num-mid-3 num-end-4"] and s["hinted"] and s["ghosts"] == 2 and s["tries"] == 3,
          json.dumps([said[-1:], s]))
    await n_quiet(t)
    await asyncio.sleep(0.3)
    s = await th_state(page)
    hopped = await page.evaluate(TH_HOPPED)
    check(f"takehome-wrong-take ({name}): ... the ghosts light as they are counted, the MeeMee hop as they're counted, and the answer still has to be given",
          s["lit"] == 2 and hopped >= 4 and s["phase"] == "takehome-open" and s["going"] == 2, json.dumps([s, hopped0, hopped]))
    await screenshot(page, f"takehome-{name}-s1-hint.png")
    await th_move(t, 2)
    s = await th_state(page)
    slots = await page.evaluate("(() => { const d = MW.takehome.diagram(); return d.slots('right', 4).map(p => [p.x, p.y]); })()")
    placed = await page.evaluate("MW.takehome.st.counters.filter(c => c.where === 'right').map(c => [c.x, c.y])")
    check(f"takehome-wrong-take ({name}): the two moved in take the lit places", s["going"] == 4 and sorted(placed) == sorted(slots), json.dumps([placed, slots]))
    await n_check(t)
    s = await th_state(page)
    rec = await page.evaluate("MW.takehome.answers('take').slice(-1)[0]")
    check(f"takehome-wrong-take ({name}): four and a tap: right; saved with 3 wrong checks and the hint", s["phase"] == "takehome-celebrate"
          and rec["tries"] == 3 and rec["hint"] is True and s["ghosts"] == 0, json.dumps([s, rec]))
    # 5 − 2, right first time; the statuses: 7 − 4 not right first time (no day), 5 − 2 one day
    await th_wait(page, ["takehome-open"], 25)
    await th_move(t, 2)
    await n_check(t)
    await th_wait(page, ["takehome-celebrate"], 5)
    days = await page.evaluate("(() => { const m = MW.takehomeFacts.statuses(MW.takehome.answers('take')); return [m['7:4'].days.length, m['7:4'].status, m['5:2'].days.length]; })()")
    check(f"takehome-wrong-take ({name}): a hinted fact isn't right first time (7 − 4: no day towards secure; 5 − 2: one)", days == [0, "practising", 1], json.dumps(days))
    check(f"takehome-wrong-take ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_wrong_left(p, name, vw, vh, dpr):
    """Step 2's wrong checks: a wrong number floats back and the gap comes back; a tile dropped elsewhere floats back; two
    wrong checks bring the hint (the MeeMee going home fade in the whole, the ones left are counted into the empty circle
    with ghosts); the number still has to be dragged. Board s2-hint."""
    print(f"\n== Take MeeMee Home: step 2's wrong checks and the hint ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-wrong-left-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await th_open(t, page, "left", [{"whole": 7, "take": 4}, {"whole": 6, "take": 2}, {"whole": 9, "take": 5}, {"whole": 5, "take": 1}, {"whole": 3, "take": 2}])
    await n_quiet(t)
    await t.drag(*tile_xy(5), 210, 470)
    s = await th_state(page)
    check(f"takehome-wrong-left ({name}): tile 5 in the empty circle: the gap shows 5", s["placed"] == 5 and s["sentence"] == "7 − 4 = 5", json.dumps(s))
    await n_check(t)
    s = await th_state(page)
    check(f"takehome-wrong-left ({name}): a wrong number: 'Let's try again.', the try-again face, the tile floats back and the gap comes back",
          (await t.said())[-1:] == ["again-try-again"] and s["face"] == "try-again" and s["placed"] is None and s["out"] == [] and s["sentence"] == "7 − 4 = _"
          and s["tries"] == 1 and not s["hinted"] and not s["ready"], json.dumps(s))
    await asyncio.sleep(1.2)
    n0 = len(await t.said())
    for n, to in ((8, (900, 330)), (6, (380, 205)), (2, (550, 470))):     # the sky, the whole, the going-home part
        await t.drag(*tile_xy(n), *to)
    s = await th_state(page)
    check(f"takehome-wrong-left ({name}): tiles dropped in the sky or on a given circle float back to the track (not a try, nothing said)",
          s["out"] == [] and s["placed"] is None and s["tries"] == 1 and (await t.said())[n0:] == [] and s["sentence"] == "7 − 4 = _", json.dumps(s))
    # the second wrong number: the hint
    await t.drag(*tile_xy(2), 215, 465)
    await n_check(t)
    s = await th_state(page)
    said = await t.said()
    order = await page.evaluate("(() => { const w = MW.takehome.st.fixed.filter(c => c.where === 'whole'); const xs = w.map(c => c.x).sort((a, b) => b - a);"
                                " return [w.filter(c => c.el.classList.contains('takehome-dim')).map(c => c.x).sort((a, b) => b - a), xs.slice(0, 4)]; })()")
    check(f"takehome-wrong-left ({name}): a second wrong number: 'Count them with me. One, two, three.'; the 4 going home fade in the whole (its 4 rightmost), "
          f"3 ghosts in the empty circle",
          said[-1:] == ["again-count-with-me num-mid-1 num-mid-2 num-end-3"] and s["hinted"] and s["dim"] == 4 and order[0] == order[1] and s["ghosts"] == 3
          and s["tries"] == 2 and s["sentence"] == "7 − 4 = _", json.dumps([said[-1:], s, order]))
    # board s2-hint: two of the three counted
    await th_until(page, "document.querySelectorAll('#screen-takehome-play .mw-ghost.is-lit').length >= 2", 8)
    await screenshot(page, f"takehome-{name}-s2-hint.png")
    await n_quiet(t)
    await asyncio.sleep(0.3)
    s = await th_state(page)
    check(f"takehome-wrong-left ({name}): ... the ghosts light as the ones left are counted, and stay, with the faded MeeMee, until the number is dragged",
          s["lit"] == 3 and s["dim"] == 4 and s["phase"] == "takehome-open" and s["placed"] is None, json.dumps(s))
    await t.drag(*tile_xy(3), 210, 470)
    await n_check(t)
    s = await th_state(page)
    rec = await page.evaluate("MW.takehome.answers('left').slice(-1)[0]")
    check(f"takehome-wrong-left ({name}): tile 3: right, the MeeMee back to full, the ghosts gone; saved with 2 wrong checks and the hint",
          s["phase"] == "takehome-celebrate" and s["dim"] == 0 and s["ghosts"] == 0 and s["carried"] == [None, 3, None] and rec["tries"] == 2 and rec["hint"] is True,
          json.dumps([s, rec]))
    check(f"takehome-wrong-left ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_wrong_numbers(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """Step 3's hints, by where the gap is; Hear-again cuts a hint short; an answer of 0 never gets the hint."""
    print(f"\n== Take MeeMee Home: step 3's wrong checks and the hints ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-wrong-numbers-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rnd = [{"whole": 7, "take": 4, "missing": "right"}, {"whole": 7, "take": 4, "missing": "whole"}, {"whole": 5, "take": 5, "missing": "left"},
           {"whole": 7, "take": 0, "missing": "left"}, {"whole": 6, "take": 0, "missing": "right"}]
    await th_open(t, page, "numbers", rnd)

    async def wrong(*tiles, at=None):
        for n in tiles:
            await n_quiet(t)
            s0 = await th_state(page)
            await t.drag(*tile_xy(n), *(at or CENTRES[s0["target"]]))
            await n_check(t)

    # 7 − ? = 3: the numbers come back as MeeMee; the 3 staying fade in the whole; the rest counted into the going-home circle
    await wrong(2, 5)
    s = await th_state(page)
    order = await page.evaluate("(() => { const w = MW.takehome.st.fixed.filter(c => c.where === 'whole'); const xs = w.map(c => c.x).sort((a, b) => a - b);"
                                " return [w.filter(c => c.el.classList.contains('takehome-dim')).map(c => c.x).sort((a, b) => a - b), xs.slice(0, 3)]; })()")
    check(f"takehome-wrong-numbers ({name}): 7 − ? = 3, two wrong numbers: the whole's 7 and the staying 3 come back as MeeMee, the 3 staying fade in the whole "
          f"(its leftmost), 4 ghosts in the going-home circle; 'Count them with me. One… four.'",
          s["hinted"] and s["carried"] == [None, None, None] and s["fixed"] == 10 and s["dim"] == 3 and order[0] == order[1] and s["ghosts"] == 4
          and (await t.said())[-1:] == ["again-count-with-me num-mid-1 num-mid-2 num-mid-3 num-end-4"], json.dumps([s, order]))
    await asyncio.sleep(0.5)
    await t.tap(*HEAR)
    await asyncio.sleep(0.5)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): Hear-again during the hint takes it away: the numbered MeeMee back, nothing faded, no ghosts; the question again",
          not s["hinted"] and s["carried"] == [7, 3, None] and s["fixed"] == 0 and s["dim"] == 0 and s["ghosts"] == 0
          and (await t.said())[-1:] == [th_prompt("numbers", rnd[0], 0)], json.dumps(s))
    await wrong(6)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): the next wrong number gives the hint again in full", s["hinted"] and s["fixed"] == 10 and s["tries"] == 3, json.dumps(s))
    await n_quiet(t)
    await asyncio.sleep(0.3)
    await screenshot(page, f"takehome-{name}-s3-hint-part.png")
    await t.drag(*tile_xy(4), 550, 470)
    await n_check(t)
    s = await th_state(page)
    faded = await page.evaluate("document.querySelectorAll('#screen-takehome-play .mw-counters .mw-mimi.is-rescued').length")
    check(f"takehome-wrong-numbers ({name}): tile 4: right; the hint's MeeMee fade away and the given circles carry their numbers again",
          s["phase"] == "takehome-celebrate" and s["carried"] == [7, 3, 4] and faded == 10, json.dumps([s, faded]))
    # ? − 4 = 3: both parts' MeeMee, counted into the whole
    await th_wait(page, ["takehome-open"], 25)
    await wrong(8, 6)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): ? − 4 = 3, two wrong numbers: both parts come back as MeeMee (3 and 4), counted into the whole (7 ghosts), nothing fades",
          s["hinted"] and s["carried"] == [None, None, None] and s["fixed"] == 7 and s["dim"] == 0 and s["ghosts"] == 7
          and (await t.said())[-1:] == ["again-count-with-me num-mid-1 num-mid-2 num-mid-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"], json.dumps(s))
    await n_quiet(t)
    await asyncio.sleep(0.3)
    await screenshot(page, f"takehome-{name}-s3-hint-whole.png")
    await t.drag(*tile_xy(7), 380, 205)
    await n_check(t)
    check(f"takehome-wrong-numbers ({name}): tile 7 completes ? − 4 = 3", (await th_state(page))["phase"] == "takehome-celebrate")
    # 5 − 5 = ?: an answer of 0 never gets the hint
    await th_wait(page, ["takehome-open"], 25)
    n0 = len(await t.said())
    await wrong(1, 2, 3)
    await n_quiet(t)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): 5 − 5 = ? (a zero fact), three wrong numbers: 'Let's try again.' each time, never the hint (no MeeMee, no ghosts)",
          (await t.said())[n0:] == ["again-try-again"] * 3 and not s["hinted"] and s["fixed"] == 0 and s["ghosts"] == 0 and s["tries"] == 3, json.dumps(s))
    await t.drag(*tile_xy(0), 210, 470)
    await n_check(t)
    rec = await page.evaluate("MW.takehome.answers('numbers').slice(-1)[0]")
    check(f"takehome-wrong-numbers ({name}): ... the 0 tile answers it (saved with 3 wrong checks, no hint)", rec["whole"] == 5 and rec["take"] == 5 and rec["tries"] == 3
          and rec["hint"] is False, json.dumps(rec))
    # 7 − 0 = ?: a zero fact whose answer isn't 0 gets the hint: nothing fades, 7 counted into the staying circle
    s = await th_wait(page, ["takehome-open"], 25)
    check(f"takehome-wrong-numbers ({name}): 7 − 0 = ? asked 'Seven… MeeMee. Zero… are going home. How many are left?'",
          (await t.said())[-1:] == ["num-mid-7 takehome-meemee num-mid-0 takehome-are-going takehome-how-many-left"], json.dumps((await t.said())[-1:]))
    await wrong(5, 6)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): 7 − 0 = ?, two wrong numbers: the hint (7 MeeMee in the whole, the going-home part's 0 as no MeeMee, nothing fades, 7 ghosts)",
          s["hinted"] and s["fixed"] == 7 and s["dim"] == 0 and s["ghosts"] == 7, json.dumps(s))
    await n_quiet(t)                                         # a tap during the hint does nothing (0.8.1)
    await t.drag(*tile_xy(7), 210, 470)
    await n_check(t)
    await th_wait(page, ["takehome-celebrate"], 5)
    # 6 − ? = 6: answer 0, no hint; nobody hops home
    await th_wait(page, ["takehome-open"], 25)
    n0 = len(await t.said())
    await wrong(2, 1)
    await n_quiet(t)
    s = await th_state(page)
    check(f"takehome-wrong-numbers ({name}): 6 − ? = 6 (answer 0), two wrong numbers: no hint", not s["hinted"] and s["ghosts"] == 0
          and (await t.said())[n0:] == ["again-try-again"] * 2, json.dumps(s))
    await page.evaluate("window.__thq = performance.now()")
    await t.drag(*tile_xy(0), 550, 470)
    await n_check(t)
    ok = await th_until(page, "MW.events.some(e => e.type === 'say' && /^num-mid-6 takehome-(take-away|subtract|minus) num-mid-0 takehome-(is|equals) num-end-6$/.test(e.detail))", 15)
    await asyncio.sleep(1.5)
    hops = await page.evaluate("MW.events.filter(e => (e.type === 'hop' || e.type === 'home') && e.t > window.__thq).length")
    check(f"takehome-wrong-numbers ({name}): 6 − 0 = 6: 'Six take away zero is six.', and nobody hops home", ok and hops == 0, str(hops))
    check(f"takehome-wrong-numbers ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_drag(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """Step 1: a touch anywhere in the whole picks up a MeeMee; one dropped outside the going-home part floats back; one can
    be taken back out. Steps 2 and 3: a tile dropped on the gap lands in the circle and fills the gap; taken out, the gap
    comes back; another tile replaces it."""
    print(f"\n== Take MeeMee Home: dragging and dropping ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-drag-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate("MW.takehome.ask({ whole: 7, take: 4 }, 'take')")
    holding = "(() => { const c = MW.takehome.st.counters.find(c => c.lifted); return c ? c.where : null; })()"
    got = []
    # the whole's rim and the spaces between its MeeMee (7 of them, about 41 px), and its middle
    for x, y in ((380, 98), (488, 205), (380, 312), (272, 205), (300, 130), (460, 280), (380, 205), (330, 205)):
        await n_hold(t, x, y, 660, 120, touch_id=60)
        got.append([x, y, await page.evaluate(holding)])
        await touch(t, "touchEnd", [])
        await asyncio.sleep(0.4)
    back = await page.evaluate("MW.takehome.st.counters.every(c => c.where === 'whole' && Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5)")
    check(f"takehome-drag ({name}): a touch anywhere in the whole (its rim, between its MeeMee, its middle) picks up a MeeMee; dropped in the sky, each floats back to its place",
          all(g[2] == "whole" for g in got) and back, json.dumps(got))
    await n_hold(t, 380, 50, 660, 120, touch_id=61)
    outside = await page.evaluate(holding)
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.3)
    check(f"takehome-drag ({name}): a touch above the whole (outside its rim) picks nothing up", outside is None, str(outside))
    misses = "MW.events.filter(e => (e.type === 'drop' && e.detail === 'miss') || (e.type === 'sfx' && e.detail === 'whoosh')).length"
    check(f"takehome-drag ({name}): ... while a MeeMee dropped in the sky is a miss, with the whoosh (one of each per drop)",
          await page.evaluate(misses) == 2 * len(got), str(await page.evaluate(misses)))
    # a child touching the MeeMee to count them: taps (and a short drag) that end inside the whole, near its foot, its top
    # and its sides, far from the MeeMee's own place, put it back quietly: no whoosh, no miss, nothing said
    n0, said0 = await page.evaluate(misses), len(await t.said())
    for x, y in ((380, 330), (330, 312), (440, 312), (380, 92), (262, 205)):
        await t.tap(x, y)
        await asyncio.sleep(0.35)
    await t.drag(380, 318, 470, 290)
    await asyncio.sleep(0.4)
    quiet = await page.evaluate("MW.takehome.st.counters.every(c => c.where === 'whole' && Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5)")
    check(f"takehome-drag ({name}): taps at the foot of the whole (380, 330), near its foot, at its top and side, and a short drag inside it, say nothing, "
          f"log no miss and no whoosh, and every MeeMee is back in its place",
          await page.evaluate(misses) == n0 and len(await t.said()) == said0 and quiet and (await th_state(page))["tries"] == 0,
          json.dumps([await page.evaluate(misses) - n0, (await t.said())[said0:]]))
    await th_move(t, 2)
    xy = await page.evaluate("(() => { const c = MW.takehome.st.counters.filter(c => c.where === 'right')[0]; return [c.x, c.y]; })()")
    await t.drag(*xy, 380, 205)
    s = await th_state(page)
    moved = await page.evaluate("MW.takehome.st.counters.filter(c => c.where === 'whole').every(c => Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5)")
    check(f"takehome-drag ({name}): one taken back out of the going-home part goes back to its own place in the whole", s["going"] == 1 and s["whole"] == 6 and moved, json.dumps(s))
    big = await page.evaluate("MW.takehome.st.counters.filter(c => c.where === 'right').map(c => c.size)")
    check(f"takehome-drag ({name}): a MeeMee in the going-home part takes that part's counting pattern at the part's size", big == [80], str(big))

    # steps 2 and 3: the gap
    for step, q, target in (("left", {"whole": 7, "take": 4}, "left"), ("numbers", {"whole": 7, "take": 4, "missing": "right"}, "right"),
                            ("numbers", {"whole": 7, "take": 4, "missing": "whole"}, "whole"), ("numbers", {"whole": 9, "take": 6, "missing": "left"}, "left")):
        await page.evaluate("(a) => MW.takehome.ask(a[0], a[1])", [q, step])
        await asyncio.sleep(0.4)
        qq = th_q(step, q)
        ans = th_answer(qq)
        g = await th_gap(page)
        await t.drag(*tile_xy(ans), *g)
        s = await th_state(page)
        tile = await page.evaluate("(n => { const t = MW.takehome.track().tile(n); return [t.x, t.y]; })(%d)" % ans)
        label = f"{step}, {th_text(qq, target)}"
        check(f"takehome-drag ({name}): {label}: a tile dropped on the gap lands in the empty circle and fills the gap",
              s["placed"] == ans and tile == list(CENTRES[target]) and s["sentence"] == th_text(qq), json.dumps([s, tile, g]))
        await t.drag(*CENTRES[target], 900, 330)
        s = await th_state(page)
        check(f"takehome-drag ({name}): {label}: taken out, it floats back to the track and the sentence has its gap again",
              s["placed"] is None and s["out"] == [] and s["sentence"] == th_text(qq, target), json.dumps(s))
    # a second tile replaces the first; a placed tile picked up and put down on the number it filled stays
    wrong = 2
    await t.drag(*tile_xy(wrong), *(await th_gap(page)))
    await t.drag(*tile_xy(3), 210, 470)
    s = await th_state(page)
    check(f"takehome-drag ({name}): another tile replaces the first, which floats back; the sentence shows the new one", s["placed"] == 3 and s["out"] == [3]
          and s["sentence"] == "9 − 6 = 3", json.dumps(s))
    num = await page.evaluate("(() => { const e = MW.takehome.equation().el, r = e.children[4].getBoundingClientRect(); const c = MW.stage.toStage(r.left + r.width / 2, r.top + r.height / 2); return [c.x, c.y]; })()")
    await t.drag(210, 470, *num)
    s = await th_state(page)
    check(f"takehome-drag ({name}): the tile picked back up and put down on the number it filled stays in the circle", s["placed"] == 3 and s["sentence"] == "9 − 6 = 3", json.dumps([s, num]))
    eq = (await page.evaluate(TH_EQ))[-4:]
    check(f"takehome-drag ({name}): the sentence's events: the gap back (minus 9-6=?), filled again (fill 3)", eq[-2:] == ["minus 9-6=?", "fill 3"], json.dumps(eq))
    # "Move them into the dotted circle.", "Find the number." and "Home they go!" join the first two questions and the
    # praise now they are recorded; while they were pending they were left out, so nothing fell silent. Both ways: as the
    # page has them (recorded), and with MW.audio.recorded stubbed to say they aren't recorded yet.
    lines = await page.evaluate("""(() => { const R = MW.takehome, out = {}, three = ['takehome-move-them', 'takehome-find-number', 'takehome-home-they-go'];
        const was = MW.audio.recorded;
        const look = () => [R.ask({ whole: 7, take: 4 }, 'take') && R.st.prompt.slice(-2), R.ask({ whole: 7, take: 4 }, 'left') && R.st.prompt.slice(-2), R.praiseLines()];
        out.onPage = three.map(id => was(id));
        out.recorded = look();
        MW.audio.recorded = id => three.indexOf(id) < 0 && was(id);
        try { out.pending = look(); } finally { MW.audio.recorded = was; }
        MW.world.home(); return out; })()""")
    praise = ["praise-found-it", "praise-thats-right", "praise-super-counting", "praise-well-done"]
    check(f"takehome-drag ({name}): recorded, they join: step 1's first questions end 'Move them into the dotted circle. Tap Scruffles…', steps 2 and 3's "
          f"'Find the number. Tap Scruffles…', and 'Home they go!' is one of the praise",
          lines["onPage"] == [True] * 3 and lines["recorded"] == [[["takehome-move-them"], ["tap-scruffles"]], [["takehome-find-number"], ["tap-scruffles"]], praise + ["takehome-home-they-go"]],
          json.dumps([lines["onPage"], lines["recorded"]]))
    check(f"takehome-drag ({name}): while pending (stubbed), 'Move them into the dotted circle.', 'Find the number.' and 'Home they go!' are left out (so nothing falls silent)",
          lines["pending"] == [[["num-mid-4", "takehome-are-going"], ["tap-scruffles"]], [["takehome-how-many-left"], ["tap-scruffles"]], praise], json.dumps(lines["pending"]))
    check(f"takehome-drag ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_questions(p):
    """Every question each step can ask is put on the screen and answered (a wrong tile refused first in steps 2 and 3);
    rounds bring up every fact, and in step 3 every gap place; the zero facts only in step 3, once that whole's other
    facts are secure there. Writes notes/all-questions-takehome.md."""
    print("\n== Take MeeMee Home: every question ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    E = lambda js, arg=None: page.evaluate(js, arg)
    counts = {}
    for step in TH_STEPS:
        qs = await E("(a) => MW.takehomeFacts.allQuestions(a[0], [2,3,4,5,6,7,8,9,10], a[1])", [step, step == "numbers"])
        counts[step] = len(qs)
        out = await E("""(a) => { const R = MW.takehome, out = [], step = a[0];
            a[1].forEach(q => { R.ask(q, step); const s = R.st, d = R.diagram(), tr = R.track(), e = R.equation();
              const o = { q: q, prompt: s.prompt, carried: ['whole', 'left', 'right'].map(k => d.carried(k)), waiting: d.circles[q.missing].classList.contains('is-waiting'),
                          sentence: Array.from(e.el.children).map(c => c.classList.contains('mw-equation-gap') ? '_' : c.textContent).join(' '), counters: s.counters.length + s.fixed.length };
              const c = MW.LAYOUT[q.missing], ans = s.answer;
              if (step === 'take') {
                s.counters.filter(m => m.where === 'whole').slice(0, q.take).forEach(m => R.drop(m, 550, 470, false));
              } else {
                R.drop(tr.tile((ans + 1) % 11), c.x + 20, c.y - 20, false); R.podTap();
                o.wrong = [s.tries, s.placed, tr.tile((ans + 1) % 11).out()];
                s.talking = false;                           // as once Scruffles is quiet: a tap while he answers does nothing (0.8.1)
                R.drop(tr.tile(ans), c.x - 30, c.y + 20, false);
              }
              R.podTap();
              const rec = R.answers(step).slice(-1)[0];
              o.right = [MW.world.st.phase, d.circles[q.missing].classList.contains('is-success'), step === 'take' ? null : d.carried(q.missing), ans];
              o.rec = [rec.whole, rec.take, rec.missing];
              out.push(o); });
            MW.world.home(); return out; }""", [step, qs])
        bad = []
        for o in out:
            q = o["q"]
            w, t_, r = q["whole"], q["take"], q["left"]
            ans = th_answer(q)
            want = dict(right=["takehome-celebrate", True, None if step == "take" else ans, ans], rec=[w, t_, q["missing"]],
                        prompt=None)
            sentence_ok = (o["sentence"] == "" if step == "take" else o["sentence"] == th_text(q, q["missing"]))
            shown = (o["counters"] == w if step == "take" else (o["counters"] == w + t_ if step == "left" else o["counters"] == 0))
            wrong_ok = step == "take" or o["wrong"] == [1, None, False]
            p_ok = " ".join(" ".join(x) for x in o["prompt"]) == th_prompt(step, q, 0)
            if not (o["right"] == want["right"] and o["rec"] == want["rec"] and sentence_ok and shown and wrong_ok and p_ok and o["waiting"]):
                bad.append(o)
        label = {"take": "step 1 (take away): 45", "left": "step 2 (how many are left): 45", "numbers": "step 3 (numbers): 45 in each of the 3 gap places, and the 18 zero facts' 54"}[step]
        check(f"takehome-questions: every question of {label} on the screen as its step shows it, asked in its words, answered (a wrong tile refused first)",
              len(out) == {"take": 45, "left": 45, "numbers": 189}[step] and not bad, json.dumps(bad[:2]))

    # rounds: every fact comes up (and every gap place in step 3); zero facts only in step 3, once that whole's others are secure there
    rounds = """(a) => { const out = []; for (let i = 0; i < a.n; i++) out.push(MW.takehomeFacts.pickRound({ step: a.step, wholes: a.wholes || [2,3,4,5,6,7,8,9,10],
        answers: a.answers || [], size: 5, turn: i * 5 })); return out; }"""
    seen = {}
    for step in TH_STEPS:
        rs = await E(rounds, {"step": step, "n": 3000})
        qs = [q for r in rs for q in r]
        seen[step] = qs
        keys = {(q["whole"], q["take"], q["missing"]) for q in qs}
        want = 135 if step == "numbers" else 45
        check(f"takehome-questions: {step} rounds bring up every question ({want}), none a zero fact while nothing is secure",
              len(keys) == want and not any(q["take"] in (0, q["whole"]) for q in qs), str(len(keys)))
        check(f"takehome-questions: {step}: every round has five, at most two from one whole, never the same whole twice in a row",
              all(len(r) == 5 and max(sum(1 for q in r if q["whole"] == w) for w in range(2, 11)) <= 2 and all(r[i]["whole"] != r[i - 1]["whole"] for i in range(1, 5)) for r in rs))
    spread = [sorted(sum(1 for q in r if q["missing"] == m) for m in ("whole", "right", "left")) for r in [seen["numbers"][i:i + 5] for i in range(0, len(seen["numbers"]), 5)]]
    share = {m: sum(1 for q in seen["numbers"] if q["missing"] == m) / len(seen["numbers"]) for m in ("whole", "right", "left")}
    check("takehome-questions: step 3 spreads the gap's place: 2, 2 and 1 in every round, and about a third each across rounds",
          all(x == [1, 2, 2] for x in spread) and all(abs(v - 1 / 3) < 0.01 for v in share.values()), json.dumps(share))
    five = [{"t": T0 + d * DAY + i * 1000, "whole": 5, "take": tk, "missing": "left", "tries": 0, "misses": 0, "hint": False} for d in range(3) for i, tk in enumerate((1, 2, 3, 4))]
    z = {}
    for step in TH_STEPS:
        rs = await E(rounds, {"step": step, "n": 600, "answers": five})
        z[step] = sorted({(q["whole"], q["take"], q["missing"]) for r in rs for q in r if q["take"] in (0, q["whole"])})
    check("takehome-questions: whole 5's facts secure in a step: in step 3 its zero facts (5 − 0, 5 − 5) join, with the gap in every place; never in steps 1 and 2",
          z["take"] == [] and z["left"] == [] and {(w, t_) for w, t_, m in z["numbers"]} == {(5, 0), (5, 5)} and len(z["numbers"]) == 6, json.dumps(z))
    four = [a for a in five if a["take"] != 4]
    rs = await E(rounds, {"step": "numbers", "n": 600, "answers": four})
    check("takehome-questions: ... not while one of its other facts (5 − 4) isn't secure", not any(q["take"] in (0, q["whole"]) for r in rs for q in r))
    small = await E("() => MW.takehomeFacts.pickRound({ step: 'take', wholes: [2], answers: [], size: 5 })")
    check("takehome-questions: only 2 in play still makes a round (2 − 1 five times)", len(small) == 5 and all(q["whole"] == 2 and q["take"] == 1 for q in small), json.dumps(small))

    # notes/all-questions-takehome.md
    allq = {step: await E("(a) => MW.takehomeFacts.allQuestions(a[0], [2,3,4,5,6,7,8,9,10], a[1])", [step, step == "numbers"]) for step in TH_STEPS}
    def words(step, q):
        w, t_, r = q["whole"], q["take"], q["left"]
        whole = f"{TH_N[w].capitalize()}… MeeMee."
        going = f"{TH_N[t_].capitalize()}… {'is' if t_ == 1 else 'are'} going home."
        staying = f"{TH_N[r].capitalize()}… {'is' if r == 1 else 'are'} staying."
        if step == "take":
            return f"{whole} {going}"
        if q["missing"] == "left":
            return f"{whole} {going} How many are left?"
        if q["missing"] == "right":
            return f"{whole} {staying} How many are going home?"
        return f"{going} {staying} How many MeeMee altogether?"
    lines = ["# Every question Take MeeMee Home can ask", "",
             "Made by tools/tests/test_game.py from the game's own list (MW.takehomeFacts.allQuestions); don't edit it by hand.",
             "Step 1 (take away): the child moves the MeeMee going home into their part; the sentence shows after a right answer.",
             "Step 2 (how many are left) and step 3 (numbers): the child drags a number tile into the empty circle or the sentence's gap.",
             "Zero facts (marked *) come up in step 3 only, once the other facts of that number are secure in step 3. The first two",
             "questions of a round also say \"Move them into the dotted circle.\" (step 1) or \"Find the number.\" (steps 2 and 3), and",
             "\"Tap Scruffles when you're ready.\" Every right answer is said as a sentence: \"Seven take away four is three.\"", ""]
    for step, title in (("take", "Step 1: Take away"), ("left", "Step 2: How many are left"), ("numbers", "Step 3: Numbers")):
        lines += [f"## {title} ({len(allq[step])} questions)", ""]
        if step == "take":
            # step 1 asks for no number: the child moves the MeeMee going home, and the sentence shows once that is right
            lines += ["| Whole | MeeMee to move | Number sentence, once right | What Scruffles says |", "|---|---|---|---|"]
            lines += [f"| {q['whole']} | {q['take']} | {th_text(q)} | {words(step, q)} |" for q in allq[step]]
        else:
            lines += ["| Whole | Number sentence | Answer | What Scruffles says |", "|---|---|---|---|"]
            for q in allq[step]:
                zero = q["take"] in (0, q["whole"])
                lines.append(f"| {q['whole']} | {th_text(q, q['missing']).replace('_', '?')}{' *' if zero else ''} | {th_answer(q)} | {words(step, q)} |")
        lines.append("")
    (ROOT / "notes" / "all-questions-takehome.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"   wrote notes/all-questions-takehome.md ({', '.join(f'{s}: {len(allq[s])}' for s in TH_STEPS)})")
    check("takehome-questions: the list has 45, 45 and 189 questions (step 3: 135 and the zero facts' 54)", [len(allq[s]) for s in TH_STEPS] == [45, 45, 189])
    check("takehome-questions: no console errors", not problems, "; ".join(problems[:3]))
    await ctx.close()
    await browser.close()


TH_ANSWER = """(a) => { const R = MW.takehome; R.ask(a.q, a.step); const s = R.st, tr = R.track(), c = MW.LAYOUT[s.target];
    if (a.step === 'take') {
      if (a.wrong) R.podTap();                                // nothing moved: a wrong check
      s.counters.filter(m => m.where === 'whole').slice(0, a.q.take).forEach(m => R.drop(m, 550, 470, false));
    } else {
      if (a.wrong) { R.drop(tr.tile((s.answer + 1) % 11), c.x, c.y, false); R.podTap(); }
      R.drop(tr.tile(s.answer), c.x, c.y, false);
    }
    s.talking = false;                                       // as once Scruffles is quiet: a tap while he answers does nothing (0.8.1)
    R.podTap(); const out = MW.world.st.phase; MW.world.home(); return out; }"""
TH_STATUS = "(a) => { const m = MW.takehomeFacts.statuses(MW.takehome.answers(a[0])); const s = m[a[1]]; return s ? s.status : 'notyet'; }"


async def test_takehome_progress(p):
    """Secure: right first time on three different days (the date faked in the page); a wrong answer moves a fact back to
    practising. Each step keeps its own records; in step 3 a fact counts whichever place its gap was in. MeeMee Rescue's
    progress is untouched by this game, and this game's by MeeMee Rescue."""
    print("\n== Take MeeMee Home: progress ==")
    browser = await p.chromium.launch()
    rescue = secure_answers([(7, 3)]) + [ans(T0 + DAY, 5, 1, first=False)]
    ctx, page, problems = await seeded(browser, rescue)
    E = lambda js, arg=None: page.evaluate(js, arg)
    await E("window.__now = %d; Date.now = () => window.__now" % T0)
    got = []
    for d in range(3):
        await E("window.__now = %d" % (T0 + d * DAY + 3600_000))
        got.append(await E(TH_ANSWER, {"q": {"whole": 7, "take": 4}, "step": "take"}))
        got.append(await E(TH_STATUS, ["take", "7:4"]))
    check("takehome-progress: 7 − 4 right first time on three different days (step 1): practising, practising, then secure",
          got == ["takehome-celebrate", "practising", "takehome-celebrate", "practising", "takehome-celebrate", "secure"], json.dumps(got))
    same = []
    for i in range(3):
        await E("window.__now = %d" % (T0 + i * 60_000))
        same.append(await E(TH_ANSWER, {"q": {"whole": 8, "take": 2}, "step": "take"}))
    check("takehome-progress: three times right on one day is still practising", await E(TH_STATUS, ["take", "8:2"]) == "practising")
    await E("window.__now = %d" % (T0 + 3 * DAY))
    await E(TH_ANSWER, {"q": {"whole": 7, "take": 4}, "step": "take", "wrong": True})
    check("takehome-progress: a wrong answer moves 7 − 4 back to practising", await E(TH_STATUS, ["take", "7:4"]) == "practising")
    check("takehome-progress: 7 − 3 is a fact of its own (not yet), not 7 − 4", await E(TH_STATUS, ["take", "7:3"]) == "notyet")
    sep = await E("[MW.takehome.answers('left').length, MW.takehome.answers('numbers').length, MW.takehome.answers('take').length]")
    check("takehome-progress: each step keeps its own records: step 1's answers are in step 1's only", sep == [0, 0, 7], str(sep))
    for d, gap in enumerate(("right", "whole", "left")):
        await E("window.__now = %d" % (T0 + (5 + d) * DAY))
        await E(TH_ANSWER, {"q": {"whole": 7, "take": 4, "missing": gap}, "step": "numbers"})
    check("takehome-progress: in step 3, 7 − 4 right first time on three days with its gap in a different place each day is secure",
          await E(TH_STATUS, ["numbers", "7:4"]) == "secure" and await E(TH_STATUS, ["take", "7:4"]) == "practising" and await E(TH_STATUS, ["left", "7:4"]) == "notyet")
    saved = await E("JSON.parse(localStorage.getItem('mimi-world'))")
    th = saved["games"]["takehome"]
    check("takehome-progress: saved on the tablet in this game's own record, one list per step; MeeMee Rescue's answers untouched",
          sorted(th["answers"]) == ["numbers", "take"] and saved["answers"] == rescue, json.dumps(sorted(th)))
    # MeeMee Rescue's play leaves this game's progress as it is
    before = json.dumps(th, sort_keys=True)
    await E("""(() => { MW.store.setting('answerMode', 'numbers'); MW.store.setting('check', 'auto'); MW.rescue.ask({ whole: 5, left: 2, right: 3, missing: 'right' });
        MW.rescue.drop(MW.rescue.track().tile(3), 550, 470, false); MW.world.home(); })()""")
    saved = await E("JSON.parse(localStorage.getItem('mimi-world'))")
    check("takehome-progress: a MeeMee Rescue answer is saved with MeeMee Rescue's, and this game's progress is as it was",
          len(saved["answers"]) == len(rescue) + 1 and json.dumps(saved["games"]["takehome"], sort_keys=True) == before, str(len(saved["answers"])))
    # a tablet that has never played this game keeps nothing for it (reading its tab doesn't create it)
    ctx2, page2, problems2 = await seeded(browser, rescue)
    await page2.evaluate("MW.grownups.openPanel(); MW.grownups.show('takehome-subtraction')")
    await asyncio.sleep(0.3)
    kept = await page2.evaluate("(() => { MW.store.save(); return JSON.parse(localStorage.getItem('mimi-world')).games; })()")
    check("takehome-progress: opening the Subtraction tab on a tablet that has never played keeps nothing for the game", "takehome" not in kept, json.dumps(kept))
    check("takehome-progress: no console errors", not (problems or problems2), "; ".join((problems + problems2)[:3]))
    await ctx2.close()
    await ctx.close()
    await browser.close()


TH_TAB = """(() => { const b = document.querySelector('.gu-body'), g = {};
    b.querySelectorAll('.gu-grid .mw-cell').forEach(c => { g[c.textContent.trim()] = c.className.split(' ').find(x => x.startsWith('is-')); });
    return { tabs: Array.from(document.querySelectorAll('.gu-tab')).map(x => x.textContent), on: (document.querySelector('.gu-tab.is-on') || {}).textContent,
             h3: Array.from(b.querySelectorAll('.gu-h3')).map(h => h.textContent),
             steps: Array.from(b.querySelectorAll('[data-step]')).map(x => [x.textContent, x.classList.contains('is-on')]),
             views: Array.from(b.querySelectorAll('[data-view]')).map(x => [x.textContent, x.classList.contains('is-on')]),
             wholes: Array.from(b.querySelectorAll('.takehome-whole')).map(x => [x.textContent, x.classList.contains('is-on')]),
             paras: Array.from(b.querySelectorAll('.gu-p')).map(x => x.textContent), lead: (b.querySelector('.gu-lead') || {}).textContent,
             cells: Object.keys(g).length, rows: Array.from(b.querySelectorAll('.gu-grid-row')).map(r => r.querySelectorAll('.mw-cell').length), g: g,
             legend: Array.from(b.querySelectorAll('.gu-legend .mw-cell')).map(c => c.textContent.trim()),
             clear: Array.from(b.querySelectorAll('.gu-btn')).filter(x => /clear/i.test(x.textContent)).map(x => x.textContent) }; })()"""
TH_EXAMPLE = [(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 4)]                    # board grid-final's secure facts
TH_PRACTISING = [(5, 3), (6, 1), (6, 2), (6, 3), (7, 1), (7, 4)]


async def test_takehome_grownups(p, name, vw, vh, dpr):
    """The game's grown-ups tab, Subtraction (boards grownups and grid-final): which step (a change starts with the next
    round), wholes in play (they limit the questions), the grid for the step picked, and clearing this game's progress only."""
    print(f"\n== Take MeeMee Home: the Subtraction tab ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-gu-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    take = [{"t": T0 + d * DAY + i * 1000, "whole": w, "take": a, "missing": "right", "tries": 0, "misses": 0, "hint": False}
            for d in range(3) for i, (w, a) in enumerate(TH_EXAMPLE)]
    take += [{"t": T0 + 4 * DAY + i * 1000, "whole": w, "take": a, "missing": "right", "tries": 1, "misses": 0, "hint": False} for i, (w, a) in enumerate(TH_PRACTISING)]
    await page.evaluate("""(a) => { const g = MW.store.game('takehome'); g.answers = { take: a }; MW.store.save();
        MW.store.get('answers').push({ t: 1, whole: 7, left: 3, right: 4, missing: 'right', tries: 0, misses: 0, hint: false, check: 'tap' });
        MW.store.game('words').answers = [{ t: 1, w: 'one', step: 'tiles', mode: 'find', tapped: 0, drops: 0, hint: false }]; MW.store.save(); }""", take)
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('takehome-subtraction')")
    await asyncio.sleep(0.4)
    tab = await page.evaluate(TH_TAB)
    check(f"takehome-gu ({name}): the tab 'Subtraction' sits after MeeMee Rockets' Words, before MeeMee Station's Station, Checks and Sound",
          tab["tabs"] == ALL_TABS and tab["on"] == "Subtraction", json.dumps(tab["tabs"]))
    check(f"takehome-gu ({name}): in order: Which step (Take away on), Wholes in play (2 to 10, all on), Showing progress for (Take away)",
          tab["h3"] == ["Which step", "Wholes in play", "Showing progress for"] and tab["steps"] == [["Take away", True], ["How many are left", False], ["Numbers", False]]
          and tab["wholes"] == [[str(w), True] for w in range(2, 11)] and tab["views"] == [["Take away", True], ["How many are left", False], ["Numbers", False]],
          json.dumps([tab["h3"], tab["steps"], tab["views"]]))
    want = ["Take away (the first step): the MeeMee sit in the whole. Your child drags the ones going home into their part, then taps Scruffles. The rest slide into the other part, and the number sentence shows.",
            "How many are left: the whole and the part going home show their MeeMee, and the number sentence waits for its answer. Your child drags a number tile into the empty circle, and it fills the gap in the sentence. Two wrong tries: the MeeMee going home fade, and the ones left are counted together.",
            "Numbers: each circle shows a MeeMee holding its number, and the gap can be anywhere in the sentence: 7 − 4 = ?, 7 − ? = 3 or ? − 4 = 3.",
            "A change starts with the next round. Each step keeps its own progress, separate from MeeMee Rescue's."]
    check(f"takehome-gu ({name}): the three explanations and the note, as round 11's board words them (British English, no exclamation marks)",
          tab["paras"][:4] == want and not any("!" in x for x in tab["paras"]), json.dumps(tab["paras"][:4]))
    check(f"takehome-gu ({name}): under Wholes in play, MeeMee Rescue's note (0.8.1)",
          "Questions use only the wholes switched on. Changes start with the next round." in tab["paras"], json.dumps(tab["paras"]))
    check(f"takehome-gu ({name}): the summary: 'Secure: 9 of 45 facts. Practising: 6. Questions answered this step on this tablet: 33.'",
          tab["lead"] == "Secure: 9 of 45 facts. Practising: 6. Questions answered this step on this tablet: 33.", tab["lead"])
    check(f"takehome-gu ({name}): the grid: a row per whole (2 to 10), a cell per fact written with the minus sign, 45 in all; 7 − 4 practising, 5 − 4 secure, 8 − 1 not yet",
          tab["rows"] == list(range(1, 10)) and tab["cells"] == 45 and tab["g"].get("7 − 4") == "is-practising" and tab["g"].get("5 − 4") == "is-secure"
          and tab["g"].get("8 − 1") == "is-notyet" and tab["legend"] == ["Secure", "Practising", "Not yet"]
          and tab["paras"][-2].startswith("Secure means right first time") and tab["paras"][-1].startswith("Zero facts (such as 7 − 0 and 7 − 7)"), json.dumps(tab["rows"]))
    await page.screenshot(path=str(SHOTS / f"takehome-{name}-grownups.png"))
    await page.evaluate("(() => { const h = Array.from(document.querySelectorAll('.gu-body .gu-h3')).find(x => x.textContent === 'Showing progress for'); const b = document.querySelector('.gu-body');"
                        " b.scrollTop += (h.getBoundingClientRect().top - b.getBoundingClientRect().top) / MW.stage.scale - 18; })()")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"takehome-{name}-grid-final.png"))
    await page.click(".gu-body [data-view=numbers]")
    await asyncio.sleep(0.3)
    tab = await page.evaluate(TH_TAB)
    wide = await page.evaluate("(() => { const g = document.querySelector('.gu-grid'); const b = g.closest('.gu-body'); return [g.scrollWidth, b.clientWidth]; })()")
    check(f"takehome-gu ({name}): 'Numbers' shows step 3's grid, with each whole's zero facts (7 − 0 to 7 − 7): 63 cells, nothing answered yet",
          tab["views"] == [["Take away", False], ["How many are left", False], ["Numbers", True]] and tab["cells"] == 63 and tab["rows"] == list(range(3, 12))
          and "7 − 0" in tab["g"] and "7 − 7" in tab["g"] and tab["lead"] == "No questions answered this step on this tablet yet." and tab["steps"][0][1], json.dumps(tab["rows"]))
    check(f"takehome-gu ({name}): the widest row (10 − 0 to 10 − 10) fits without sideways scrolling", wide[0] <= wide[1], str(wide))
    # 0.8.1: the summary counts the 45 facts in Numbers too, and the zero facts have a line of their own
    nums = [{"t": T0 + d * DAY + i * 1000, "whole": w, "take": a, "missing": "left", "tries": 0, "misses": 0, "hint": False}
            for d in range(3) for i, (w, a) in enumerate([(5, 4), (5, 5)])]
    nums.append({"t": T0 + 5 * DAY, "whole": 6, "take": 0, "missing": "left", "tries": 1, "misses": 0, "hint": False})
    await page.evaluate("(a) => { const g = MW.store.game('takehome'); g.answers.numbers = a; MW.store.save(); }", nums)
    await page.click(".gu-body [data-view=numbers]")
    await asyncio.sleep(0.3)
    zl = await page.evaluate("Array.from(document.querySelectorAll('.gu-body .gu-lead')).map(x => x.textContent)")
    check(f"takehome-gu ({name}): Numbers' summary counts the 45 facts, and the zero facts have their own line (0.8.1)",
          zl == ["Secure: 1 of 45 facts. Practising: 0. Questions answered this step on this tablet: 7.", "Zero facts: 1 of 18 secure. Practising: 1."], json.dumps(zl))
    await page.evaluate("(() => { const g = MW.store.game('takehome'); delete g.answers.numbers; MW.store.save(); })()")
    await page.click(".gu-body [data-view=numbers]")
    await asyncio.sleep(0.3)
    await page.screenshot(path=str(SHOTS / f"takehome-{name}-grid-numbers.png"))
    await page.evaluate("MW.grownups.close()")

    # a change of step starts with the next round
    s = await th_open(t, page, "take", [{"whole": 7, "take": 4}] * 5)
    await t.tap(46, 754, 3.3)                                # the grown-ups lock
    await page.evaluate("MW.grownups.show('takehome-subtraction')")
    await asyncio.sleep(0.3)
    await page.click(".gu-body [data-step=left]")
    await asyncio.sleep(0.2)
    tab = await page.evaluate(TH_TAB)
    saved = await page.evaluate("MW.store.peek('takehome').step")
    check(f"takehome-gu ({name}): 'How many are left' picked: saved, on, and the progress below shows its grid",
          saved == "left" and tab["steps"][1][1] and tab["views"][1][1] and tab["cells"] == 45, json.dumps([saved, tab["steps"], tab["views"]]))
    await page.click(".gu-close")
    await asyncio.sleep(0.6)
    s = await th_state(page)
    check(f"takehome-gu ({name}): ... but the round being played carries on taking away", s["step"] == "take" and s["look"] == "counting" and not s["track"]
          and s["whole"] == 7, json.dumps(s))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    s = await th_open(t, page, None, [{"whole": 7, "take": 4}] * 5)
    check(f"takehome-gu ({name}): the next round is How many are left", s["step"] == "left" and s["track"] and s["sentence"] == "7 − 4 = _", json.dumps(s))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    # wholes in play limit the questions
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('takehome-subtraction')")
    await asyncio.sleep(0.3)
    for w in (2, 4, 6, 7, 8, 9, 10):
        await page.click(f".gu-body .takehome-whole:nth-child({w - 1})")
        await asyncio.sleep(0.05)
    tab = await page.evaluate(TH_TAB)
    on = [int(x[0]) for x in tab["wholes"] if x[1]]
    rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 300; i++) MW.takehome.makeRound().forEach(q => out.add(q.whole)); return Array.from(out).sort(); })()")
    check(f"takehome-gu ({name}): with only 3 and 5 in play, rounds use only 3 and 5", on == [3, 5] and await page.evaluate("MW.store.peek('takehome').wholes") == [3, 5]
          and rounds == [3, 5], json.dumps([on, rounds]))
    await page.click(".gu-body .takehome-whole:nth-child(2)")
    await page.click(".gu-body .takehome-whole:nth-child(4)")
    await asyncio.sleep(0.1)
    check(f"takehome-gu ({name}): the last whole in play can't be turned off", await page.evaluate("MW.store.peek('takehome').wholes") == [5])
    # clearing clears this game's progress only (its step and wholes stay; MeeMee Rescue's and MeeMee Rockets' answers stay)
    await page.click(".gu-body .takehome-clear")
    await asyncio.sleep(0.1)
    first = await page.evaluate("[document.querySelector('.gu-body .takehome-clear').textContent, MW.takehome.answers('take').length]")
    await page.click(".gu-body .takehome-clear")
    await asyncio.sleep(0.2)
    after = await page.evaluate("""(() => { const s = JSON.parse(localStorage.getItem('mimi-world')); return [s.games.takehome, s.answers.length, s.games.words.answers.length,
        document.querySelector('.gu-body .gu-lead').textContent]; })()""")
    check(f"takehome-gu ({name}): 'Clear this tablet's progress' asks first ('Tap again to clear'), then clears this game's answers only",
          first == ["Tap again to clear", 33] and after[0] == {"step": "left", "wholes": [5]} and after[1] == 1 and after[2] == 1
          and after[3] == "No questions answered this step on this tablet yet.", json.dumps([first, after]))
    await page.evaluate("MW.grownups.close()")
    check(f"takehome-gu ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# as while "Take MeeMee Home!" was still pending: MW.audio.recorded stubbed to say it isn't recorded (UNSTUB_PLACE_LINE undoes it)
STUB_TH_NAME_PENDING = """(() => { if (!window.__recorded) window.__recorded = MW.audio.recorded;
    MW.audio.recorded = id => id !== 'takehome-name' && window.__recorded(id); })()"""


async def test_takehome_map(p, name, vw, vh, dpr):
    """Place 2 is the game's: lit with its badge; it and its badge open the game after its title banner (its name is
    recorded); with the name stubbed as not recorded, straight away with no banner. The rocks stay locked and still say
    their line (the station is MeeMee Station's from 0.9.0)."""
    print(f"\n== Take MeeMee Home on the map ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-map-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await asyncio.sleep(1.0)
    await screenshot(page, f"takehome-{name}-map.png")
    info = await page.evaluate(PLACES_INFO)
    badge = await page.evaluate("(() => { const L = MW.LAYOUT.map.planets[2].badge; const b = Array.from(document.querySelectorAll('#screen-map .mw-planet-badge')).find(e => e.offsetLeft === L.x && e.offsetTop === L.y);"
                                " return b ? [!!b.querySelector('clipPath[id^=\"takehome-badge-c\"]'), b.getAttribute('aria-label')] : null; })()")
    check(f"takehome-map ({name}): place 2 (the small peach planet) is Take MeeMee Home's: lit, a mint halo and its badge (the house in its night window)",
          place_ok(info[2], "Take MeeMee Home") and badge and badge[0], json.dumps([info[2], badge]))
    check(f"takehome-map ({name}): MeeMee Rescue and MeeMee Rockets keep places 0 and 1, MeeMee Station has the station (4); the rocks (3) stay locked",
          place_ok(info[0], "MeeMee Rescue") and place_ok(info[1], "MeeMee Rockets") and place_ok(info[3], None) and place_ok(info[4], "MeeMee Station"), json.dumps(info))
    locked = await page.evaluate(MAP_LOCKED_LINE)
    for i in (3,):
        pl = await page.evaluate("MW.LAYOUT.map.planets[%d]" % i)
        said, screen = await tap_said(t, pl["x"], pl["y"])
        check(f"takehome-map ({name}): {WHAT[i]} still say the locked line ({locked}) and stay on the map",
              said == [locked] and screen == "screen-map", json.dumps([said, screen]))
        await asyncio.sleep(1.2)
    # its name is recorded: tapping place 2 shows its title banner while "Take MeeMee Home!" is said, then the game starts
    await page.evaluate("MW.takehome.nextRound = %s" % json.dumps([{"whole": 7, "take": 4}] * 5))
    pl = await page.evaluate(TH_PLACE)
    n0 = len(await t.said())
    await t.tap(pl["x"], pl["y"])
    up = await th_until(page, "MW.world.banner.up() && document.getElementById('banner').classList.contains('is-in')", 5)
    await asyncio.sleep(0.4)                                 # its fade-in (260 ms)
    bi = await page.evaluate(BANNER_INFO)
    size = await page.evaluate("(() => { const a = document.querySelector('#banner [data-art] svg'); return a ? [a.getAttribute('width'), a.getAttribute('height')] : null; })()")
    await screenshot(page, f"takehome-{name}-banner.png")
    check(f"takehome-map ({name}): tapping place 2 shows its title banner, 'Take MeeMee Home' and its badge at 112, while 'Take MeeMee Home!' is said",
          up and bi == {"up": True, "name": "Take MeeMee Home", "art": ["takehome-badge"], "phase": "opening", "screen": "screen-map"} and size == ["112", "112"]
          and (await t.said())[n0:][:1] == ["takehome-name"], json.dumps([bi, size, (await t.said())[n0:]]))
    ok = await t.wait_screen("screen-takehome-play", 10)
    gone = await page.evaluate("(() => { const g = MW.events.filter(e => e.type === 'banner' && e.detail === 'gone Take MeeMee Home').pop(), "
                               "r = MW.events.filter(e => e.type === 'round').pop(); return !!(g && r && g.t <= r.t); })()")
    check(f"takehome-map ({name}): ... and the game starts once the banner has gone", ok and gone)
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await asyncio.sleep(0.5)
    b = await page.evaluate("MW.LAYOUT.map.planets[2].badge")
    await t.tap(b["x"] + b["d"] / 2, b["y"] + b["d"] / 2)
    check(f"takehome-map ({name}): its badge opens it too (with its banner)",
          await th_until(page, "MW.world.banner.up()", 5) and await t.wait_screen("screen-takehome-play", 10))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await asyncio.sleep(0.5)
    # as while its name was still pending (stubbed): no banner, the game starts straight away
    await page.evaluate(STUB_TH_NAME_PENDING)
    try:
        await t.tap(pl["x"], pl["y"])
        ok = await t.wait_screen("screen-takehome-play", 3)
        check(f"takehome-map ({name}): with its name not recorded (stubbed), tapping place 2 opens the game straight away, no banner",
              ok and not await page.evaluate("MW.world.banner.up()")
              and await page.evaluate("MW.events.some(e => e.type === 'banner' && e.detail === 'none for Take MeeMee Home (takehome-name not recorded yet)')"))
    finally:
        await page.evaluate(UNSTUB_PLACE_LINE)
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    check(f"takehome-map ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_pause(p):
    """Hear-again; the screen going off mid-question; Home while a MeeMee or a tile is held, mid-celebration and from the end
    screen; the grown-ups area opened mid-hint and mid-celebration; Again on the end screen."""
    print("\n== Take MeeMee Home: Hear-again, pausing and Home ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "takehome-pause", 1046, 653, 1.22, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rnd = [{"whole": 7, "take": 4}, {"whole": 5, "take": 2}, {"whole": 6, "take": 3}, {"whole": 8, "take": 2}, {"whole": 4, "take": 1}]
    await th_open(t, page, "take", rnd)
    await n_quiet(t)
    n0 = len(await t.said())
    await t.tap(*HEAR)
    await asyncio.sleep(0.4)
    check("takehome-pause: Hear-again says the question again", (await t.said())[n0:] == [th_prompt("take", rnd[0], 0)], json.dumps((await t.said())[n0:]))
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.6)
    paused = await page.evaluate("MW.world.st.paused")
    n0 = len(await t.said())
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.5)
    check("takehome-pause: the screen going off pauses; coming back asks the question again", paused and (await t.said())[n0:][:1] == [th_prompt("take", rnd[0], 0)],
          json.dumps((await t.said())[n0:]))
    # a MeeMee held as the screen goes off goes back to its place
    await th_move(t, 1)
    await n_hold(t, 380, 205, 700, 300, touch_id=70)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.4)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.5)
    s = await th_state(page)
    home = await page.evaluate("MW.takehome.st.counters.filter(c => c.where === 'whole').every(c => Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5)")
    check("takehome-pause: a MeeMee held as the screen goes off goes back to its place (the one already moved stays)", s["going"] == 1 and s["whole"] == 6 and home, json.dumps(s))
    # Home while a MeeMee is held: nothing said after, the map
    await n_quiet(t)
    await n_hold(t, 380, 205, 700, 300, touch_id=71)
    await page.evaluate("MW.takehome.home()")               # Home (the other hand)
    n0 = len(await t.said())
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.8)
    s = await th_state(page)
    check("takehome-pause: Home while a MeeMee is held: the map, nothing said after, the game put away", s["screen"] == "screen-map" and (await t.said())[n0:] == []
          and s["whole"] == 0 and s["going"] == 0, json.dumps(s))
    # step 2: the grown-ups area opened mid-hint takes the hint away; closed, the question again; the next wrong number brings it back
    rnd2 = [{"whole": 7, "take": 4}, {"whole": 6, "take": 1}, {"whole": 9, "take": 3}, {"whole": 5, "take": 3}, {"whole": 8, "take": 4}]
    await th_open(t, page, "left", rnd2)
    await n_quiet(t)
    for n in (5, 6):
        await t.drag(*tile_xy(n), 210, 470)
        await n_check(t)
        await asyncio.sleep(0.1)
        if n == 5:
            await n_quiet(t)
    await asyncio.sleep(0.5)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    await asyncio.sleep(0.5)
    s = await th_state(page)
    check("takehome-pause: the grown-ups area opened mid-hint: the hint stops and is taken away (nothing faded, no ghosts)",
          not s["hinted"] and s["dim"] == 0 and s["ghosts"] == 0 and not await page.evaluate("MW.audio.speaking()"), json.dumps(s))
    n0 = len(await t.said())
    await page.click(".gu-close")
    await asyncio.sleep(0.5)
    check("takehome-pause: ... closed, the question is asked again", (await t.said())[n0:][:1] == [th_prompt("left", rnd2[0], 0)], json.dumps((await t.said())[n0:]))
    await n_quiet(t)
    await t.drag(*tile_xy(8), 210, 470)
    await n_check(t)
    s = await th_state(page)
    check("takehome-pause: ... and the next wrong number gives the hint again", s["hinted"] and s["dim"] == 4 and s["ghosts"] == 3, json.dumps(s))
    await n_quiet(t)
    # the grown-ups area opened mid-celebration: everything waits, then carries on
    await t.drag(*tile_xy(3), 210, 470)
    await n_check(t)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    n0 = len(await t.said())
    await asyncio.sleep(2.5)
    s = await th_state(page)
    check("takehome-pause: the grown-ups area opened mid-celebration: nothing is said while it's open, the answer stays",
          s["phase"] == "takehome-celebrate" and (await t.said())[n0:] == [] and s["carried"] == [None, 3, None], json.dumps(s))
    await page.click(".gu-close")
    s = await th_wait(page, ["takehome-open"], 30)
    check("takehome-pause: ... closed, the celebration carries on (the sentence said, the MeeMee home), then question 2",
          s["qi"] == 1 and th_said_sentence(th_q("left", rnd2[0])) in await t.said(), json.dumps(s))
    # Home mid-celebration: nothing more said
    await n_quiet(t)
    await t.drag(*tile_xy(5), 210, 470)
    await n_check(t)
    await t.tap(*HOME)
    n0 = len(await t.said())
    await asyncio.sleep(3)
    s = await th_state(page)
    check("takehome-pause: Home mid-celebration: back on the map, nothing more said, the tiles all back", s["screen"] == "screen-map" and (await t.said())[n0:] == []
          and s["out"] == [] and s["placed"] is None and s["hoppers"] == 0, json.dumps([(await t.said())[n0:], s]))
    # the end screen: Again starts a new round; Home goes back to the map
    await th_set(page, "take", [{"whole": 2, "take": 1}] * 5)
    pl = await page.evaluate(TH_PLACE)
    await t.tap(pl["x"], pl["y"])
    for _ in range(5):
        await th_wait(page, ["takehome-open"], 25)
        await th_move(t, 1)
        await n_check(t)
    await th_wait(page, ["takehome-done"], 25)
    await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'takehome-round-another')", 15)
    await page.evaluate("MW.takehome.nextRound = %s" % json.dumps(rnd))
    await t.tap(1160, 480)                                   # Again (1080, 400, 160 across)
    s = await th_wait(page, ["takehome-open"], 30)
    check("takehome-pause: Again on the end screen starts a new round", s["screen"] == "screen-takehome-play" and s["qi"] == 0 and s["whole"] == 7, json.dumps(s))
    await t.tap(*HOME)
    check("takehome-pause: Home goes back to the map", await t.wait_screen("screen-map", 5))
    check("takehome-pause: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


TH_PLAY_ROUNDS = """(n) => { const R = MW.takehome, out = { turns: [], rounds: [], lens: [] };
    for (let r = 0; r < n; r++) {
      out.turns.push(R.gapTurn());
      const round = R.makeRound();
      out.rounds.push(round.map(q => q.missing));
      round.forEach(q => { R.ask(q, 'numbers'); const s = R.st, tr = R.track(), c = MW.LAYOUT[s.target];
        R.drop(tr.tile(s.answer), c.x, c.y, false); R.podTap(); });
      out.lens.push(R.answers('numbers').length);
    }
    MW.world.home(); return out; }"""


async def test_takehome_words(p):
    """0.8.1: the number sentence's words take turns (the class uses every subtraction word): the next of take away,
    subtract and minus, and the next of is and equals, every answer in any step, carrying on across rounds. A word not
    recorded yet sits out its turn, so the sentence is never missing a word."""
    print("\n== Take MeeMee Home: the sentence's words take turns ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "takehome-words", 1046, 653, 1.22, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    say = "(n => { const w = MW.takehome.sentenceWords(n); return w.take.replace('takehome-', '') + '/' + w.is.replace('takehome-', ''); })"
    rec = await page.evaluate("['takehome-subtract', 'takehome-minus', 'takehome-equals'].map(id => MW.audio.recorded(id))")
    now = await page.evaluate(f"[0, 1, 2, 3, 4, 5].map({say})")
    want_now = [f"{['take-away', 'subtract', 'minus'][n % 3] if rec[0] and rec[1] else 'take-away'}/{['is', 'equals'][n % 2] if rec[2] else 'is'}" for n in range(6)]
    if not any(rec) or all(rec):
        check(f"takehome-words: with subtract, minus and equals {'recorded' if all(rec) else 'still waiting for their recordings'}, six turns say: {', '.join(want_now)}",
              now == want_now, json.dumps(now))
    turns = await page.evaluate(f"""(() => {{ const real = MW.audio.recorded, say = {say};
        MW.audio.recorded = id => ['takehome-subtract', 'takehome-minus', 'takehome-equals'].indexOf(id) >= 0 || real(id);
        const all = [0, 1, 2, 3, 4, 5].map(say);
        MW.audio.recorded = id => id === 'takehome-minus' || (id !== 'takehome-subtract' && id !== 'takehome-equals' && real(id));
        const one = [0, 1, 2, 3].map(say);
        MW.audio.recorded = real;
        return [all, one]; }})()""")
    check("takehome-words: all recorded, six turns say every pairing once: take away/is, subtract/equals, minus/is, take away/equals, subtract/is, minus/equals",
          turns[0] == ["take-away/is", "subtract/equals", "minus/is", "take-away/equals", "subtract/is", "minus/equals"], json.dumps(turns[0]))
    check("takehome-words: only minus recorded: take away and minus take turns, and is (equals sits out)",
          turns[1] == ["take-away/is", "minus/is", "take-away/is", "minus/is"], json.dumps(turns[1]))
    # the turn moves on with every answer and carries on into the next round
    await page.evaluate("(() => { const g = MW.store.game('takehome'); g.wordTurn = 4; MW.store.save(); })()")
    expect4 = await page.evaluate("(w => w.take + ' ' + w.is)(MW.takehome.sentenceWords(4))")
    await th_open(t, page, "take", [{"whole": 3, "take": 1}] * 5)
    await page.evaluate("window.__thq = performance.now()")
    await th_move(t, 1)
    await n_check(t)
    await th_until(page, "MW.events.some(e => e.type === 'words' && e.t > window.__thq)", 15)
    words = await page.evaluate("MW.events.filter(e => e.type === 'words').pop().detail")
    turn = await page.evaluate("MW.takehome.wordTurn()")
    check("takehome-words: a right answer at turn 4 uses turn 4's words and moves the turn on to 5", words == expect4 and turn == 5, json.dumps([words, expect4, turn]))
    await th_wait(page, ["takehome-open"], 30)
    await th_move(t, 1)
    await n_check(t)
    await th_wait(page, ["takehome-celebrate"], 5)
    turn = await page.evaluate("MW.takehome.wordTurn()")
    check("takehome-words: the next answer moves it on again, round past 5 to 0", turn == 0, str(turn))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await th_open(t, page, "take", [{"whole": 3, "take": 1}] * 5)
    check("takehome-words: a new round carries on from where the last one stopped", await page.evaluate("MW.takehome.wordTurn()") == 0)
    check("takehome-words: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_storage(p):
    """What the tablet keeps: each step its last 1000 answers (3000 for the game in all, as MeeMee Rescue keeps), so the
    one storage entry stays small; secure, practising and not yet still come out right with a full list; step 3's gap
    places keep turning once the list is full (a counter saved with the progress, not the list's length); MeeMee Rescue's
    Clear leaves this game's progress alone."""
    print("\n== Take MeeMee Home: what the tablet keeps ==")
    browser = await p.chromium.launch()
    rescue = secure_answers([(7, 3)])
    ctx, page, problems = await seeded(browser, rescue)
    E = lambda js, arg=None: page.evaluate(js, arg)
    await E("window.__now = %d; Date.now = () => window.__now" % T0)
    # step 1 full: 997 answers to 9 − 1 a minute apart, long ago, then 8 − 2 right first time on the last three days
    take = [{"t": T0 - 40 * DAY + i * 60_000, "whole": 9, "take": 1, "missing": "right", "tries": 0, "misses": 0, "hint": False} for i in range(997)]
    take += [{"t": T0 - d * DAY, "whole": 8, "take": 2, "missing": "right", "tries": 0, "misses": 0, "hint": False} for d in (3, 2, 1)]
    full = lambda s: [dict(a, missing=("left" if s == "left" else a["missing"])) for a in take]
    await E("""(a) => { const g = MW.store.game('takehome'); g.answers = { take: a.take, left: a.left, numbers: a.numbers }; g.step = 'numbers'; MW.store.save(); }""",
            {"take": take, "left": full("left"), "numbers": full("numbers")})
    size0 = await E("MW.store.bytes()")
    st0 = await E("(() => { const m = MW.takehomeFacts.statuses(MW.takehome.answers('take')); return [m['8:2'].status, m['9:1'].status, (m['7:4'] || {}).status || 'notyet']; })()")
    check("takehome-store: with every step's list full (1000 each, 3000 in all) the tablet's one entry stays small (under 300 KB)",
          size0 < 300_000 and await E("['take', 'left', 'numbers'].map(s => MW.takehome.answers(s).length)") == [1000] * 3, f"{size0} bytes")
    got = []
    for d in range(3):
        await E("window.__now = %d" % (T0 + d * DAY + 3600_000))
        await E(TH_ANSWER, {"q": {"whole": 7, "take": 4}, "step": "take"})
        got.append(await E("(() => { const a = MW.takehome.answers('take'); const m = MW.takehomeFacts.statuses(a); return [a.length, m['7:4'].status, m['8:2'].status, a[0].t]; })()"))
    check("takehome-store: a full list stays at 1000, the oldest answer making room; 7 − 4 right first time on three days becomes secure, 8 − 2 stays secure",
          st0 == ["secure", "practising", "notyet"] and [g[0] for g in got] == [1000] * 3 and [g[1] for g in got] == ["practising", "practising", "secure"]
          and all(g[2] == "secure" for g in got) and got[0][3] < got[1][3] < got[2][3], json.dumps([st0, got]))
    await E("window.__now = %d" % (T0 + 3 * DAY + 3600_000))
    await E(TH_ANSWER, {"q": {"whole": 7, "take": 4}, "step": "take", "wrong": True})
    st1 = await E("(() => { const a = MW.takehome.answers('take'); const m = MW.takehomeFacts.statuses(a); return [a.length, m['7:4'].status, m['8:2'].status]; })()")
    check("takehome-store: ... and a wrong answer at the cap moves 7 − 4 back to practising", st1 == [1000, "practising", "secure"], json.dumps(st1))
    # step 3: the list is full, so its length no longer changes; the gap's places keep turning (2, 2 and 1 a round, the
    # short one moving on each round), from the list's length the first time (1000: place 1) and then from the counter
    rot = await E(TH_PLAY_ROUNDS, 3)
    places = ["whole", "right", "left"]
    counts = [{m: r.count(m) for m in places} for r in rot["rounds"]]
    short = [min(c, key=c.get) for c in counts]
    total = {m: sum(c[m] for c in counts) for m in places}
    saved = await E("MW.store.peek('takehome').gapTurn")
    check("takehome-store: with step 3's list full (1000), the gap's places keep turning: rounds start at places 1, 0, 2 (the counter moves on 5 a round), "
          "2, 2 and 1 in each, the short one a different place each round, 5 of each in all",
          rot["lens"] == [1000] * 3 and rot["turns"] == [1, 0, 2] and all(sorted(c.values()) == [1, 2, 2] for c in counts) and len(set(short)) == 3
          and total == {"whole": 5, "right": 5, "left": 5} and saved == 1, json.dumps([rot, saved]))
    # MeeMee Rescue's Clear (its Progress tab) clears its own answers and leaves this game's progress as it was
    before = json.dumps(await E("MW.store.peek('takehome')"), sort_keys=True)
    await E("MW.grownups.openPanel(); MW.grownups.show('progress')")
    await asyncio.sleep(0.3)
    await page.click("text=Clear this tablet's progress")
    await page.click("text=Tap again to clear")
    await asyncio.sleep(0.3)
    after = await E("[MW.store.get('answers').length, MW.store.peek('takehome')]")
    await E("MW.grownups.close()")
    check("takehome-store: MeeMee Rescue's 'Clear this tablet's progress' clears its answers only; this game's progress stays as it was",
          after[0] == 0 and json.dumps(after[1], sort_keys=True) == before, str(after[0]))
    check("takehome-store: no console errors", not problems, "; ".join(problems[:3]))
    await ctx.close()
    await browser.close()


async def test_takehome_hop_pause(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """During the hop home: Hear-again says nothing and the hop carries on; the screen going off holds the round, and it
    carries on when the screen comes back; Home takes the hopping MeeMee away at once, and the next round starts clean."""
    print(f"\n== Take MeeMee Home: Home, pausing and Hear-again during the hop home ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-hop-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rnd = [{"whole": 7, "take": 4}, {"whole": 6, "take": 3}, {"whole": 8, "take": 5}, {"whole": 5, "take": 2}, {"whole": 9, "take": 4}]
    await th_open(t, page, "take", rnd)
    hopping = "MW.events.some(e => e.type === 'home' && e.t > window.__thq)"

    async def answer_and_hop(q):
        await n_quiet(t)
        await th_move(t, q["take"])
        await page.evaluate("window.__thq = performance.now()")
        await n_check(t)
        return await th_until(page, hopping, 20)

    # Hear-again while they hop: nothing said, the hop carries on, then question 2
    ok = await answer_and_hop(rnd[0])
    await asyncio.sleep(0.2)
    n0 = len(await t.said())
    s0 = await th_state(page)
    await t.tap(*HEAR)
    await asyncio.sleep(0.3)
    s1 = await th_state(page)
    check(f"takehome-hop ({name}): Hear-again while the MeeMee hop home says nothing, and the hop carries on",
          ok and s0["hoppers"] == 4 and s1["phase"] == "takehome-celebrate" and s1["hoppers"] == 4 and (await t.said())[n0:] == [], json.dumps([s0["hoppers"], s1]))
    s = await th_wait(page, ["takehome-open"], 30)
    check(f"takehome-hop ({name}): ... then question 2, the hoppers gone", s["qi"] == 1 and s["hoppers"] == 0 and s["whole"] == 6, json.dumps(s))
    # the screen going off mid-hop: the round waits (nothing said, no next question) until it comes back
    ok = await answer_and_hop(rnd[1])
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    n0 = len(await t.said())
    q0 = await page.evaluate("MW.events.filter(e => e.type === 'question').length")
    await asyncio.sleep(2.5)
    s = await th_state(page)
    held = s["phase"] == "takehome-celebrate" and s["qi"] == 1 and (await t.said())[n0:] == [] and await page.evaluate("MW.events.filter(e => e.type === 'question').length") == q0
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    s2 = await th_wait(page, ["takehome-open"], 30)
    check(f"takehome-hop ({name}): the screen going off while they hop holds the round (nothing said, no next question); back on, it carries on to question 3",
          ok and held and s2["qi"] == 2 and s2["hoppers"] == 0, json.dumps([s, s2]))
    # Home mid-hop: the map at once, the hopping MeeMee taken away, nothing said after; the next round starts clean
    ok = await answer_and_hop(rnd[2])
    await asyncio.sleep(0.15)
    await t.tap(*HOME)
    n0 = len(await t.said())
    await asyncio.sleep(0.3)
    s = await th_state(page)
    left = await page.evaluate("document.querySelectorAll('#screen-takehome-play .mw-counters .mw-mimi').length")
    await asyncio.sleep(2)
    check(f"takehome-hop ({name}): Home while they hop: the map, every hopping MeeMee taken away, nothing said after",
          ok and s["screen"] == "screen-map" and s["hoppers"] == 0 and left == 0 and (await t.said())[n0:] == [], json.dumps([s, left, (await t.said())[n0:]]))
    s = await th_open(t, page, "take", rnd)
    check(f"takehome-hop ({name}): ... and the next round starts clean (question 1, its 7 MeeMee, nobody hopping)",
          s["qi"] == 0 and s["whole"] == 7 and s["going"] == 0 and s["hoppers"] == 0, json.dumps(s))
    await t.tap(*HOME)
    check(f"takehome-hop ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_takehome_motion(p):
    """The MeeMee going home hop to their houses (about a second in all); with reduce motion they fade instead, and the
    track, the numbered MeeMee and the sentence fade rather than move."""
    print("\n== Take MeeMee Home: motion and reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    # each hopper's animations: [moves?, duration, how many hops (keyframes at the top of an arc), its turn (delay, ms)]
    hops = """(() => { const R = MW.takehome; return R.st.hoppers.map(c => c.el.getAnimations().map(a => {
        const k = a.effect.getKeyframes(), tm = a.effect.getTiming(); return [k.some(f => f.transform && f.transform !== 'none'), tm.duration,
        k.filter(f => f.easing === 'ease-in').length, tm.delay]; })); })()"""
    for reduce in (False, True):
        label = "reduce motion" if reduce else "motion"
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce" if reduce else "no-preference")
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
        # step 1, 9 − 6: six going home
        await page.evaluate("""(() => { const R = MW.takehome; R.ask({ whole: 9, take: 6 }, 'take'); R.st.counters.filter(m => m.where === 'whole').slice(0, 6).forEach(m => R.drop(m, 550, 470, false)); R.podTap(); })()""")
        await th_until(page, "MW.events.some(e => e.type === 'home')", 25)
        await asyncio.sleep(0.55)                               # the sixth sets off 420 ms after the first
        got = await page.evaluate(hops)
        gone = await page.evaluate("MW.takehome.st.counters.filter(c => c.where === 'right').map(c => [c.el.classList.contains('takehome-gone'), getComputedStyle(c.el).transitionProperty])")
        if reduce:
            doors = got[1::2]                                   # hoppers: each MeeMee, then the one that fades in by its house
            turns = [h[0][3] for h in doors if h]
            check(f"takehome ({label}): the six going home fade from their circle, and fade in and out by their houses, one after another: nothing hops (no movement)",
                  len(got) == 12 and all(not a[0] for h in got for a in h) and all(g[0] for g in gone) and len(gone) == 6
                  and len(turns) == 6 and turns[0] == 0 and turns == sorted(turns) and 300 <= turns[-1] <= 600, json.dumps([got, gone]))
        else:
            spans = [a[1] for h in got for a in h]
            turns = [h[0][3] for h in got if h]
            check(f"takehome ({label}): the six going home hop off to their houses, one journey of two hops each (340 ms a hop, 0.68 s), one after another "
                  f"(each its turn, the last setting off within about half a second: about a second in all)",
                  len(got) == 6 and all(len(h) == 1 and h[0][0] and h[0][2] == 2 and h[0][1] / h[0][2] >= 1000 / 3 for h in got) and max(spans) <= 800
                  and len(turns) == 6 and turns[0] == 0 and all(b - a >= 80 for a, b in zip(turns, turns[1:])) and 300 <= turns[-1] <= 600
                  and await page.evaluate("MW.events.filter(e => e.type === 'hop').length") == 6, json.dumps(got))
        # step 2: the track, the numbered MeeMee and the sentence
        res = await page.evaluate("""(() => { const R = MW.takehome; R.ask({ whole: 7, take: 4 }, 'left'); const tr = R.track(), c = MW.LAYOUT.left;
            R.drop(tr.tile(3), c.x, c.y, false); R.podTap(); const e = R.equation().el;
            const pop = Array.from(document.querySelectorAll('#screen-takehome-play .mw-numbered.is-popping')).map(x => getComputedStyle(x).animationName);
            const ts = getComputedStyle(tr.el);
            return { pop: pop, track: [ts.transform, ts.transitionProperty], sentence: e.getAnimations().map(a => a.transitionProperty || a.animationName) }; })()""")
        if reduce:
            check(f"takehome ({label}): a right answer in step 2: the numbered MeeMee fades in, the track fades away and the sentence fades in under the diagram",
                  res["pop"] == ["mw-arrive"] and res["track"][0] == "none" and res["sentence"] == ["mw-arrive"], json.dumps(res))
        else:
            check(f"takehome ({label}): a right answer in step 2: the numbered MeeMee pops up, the track slides away and the sentence slides under the diagram",
                  res["pop"] == ["mw-carry"] and res["track"][0] != "none" and "transform" in res["sentence"], json.dumps(res))
        await page.evaluate("MW.world.home()")
        check(f"takehome ({label}): no console errors", not problems, "; ".join(problems[:3]))
        await ctx.close()
    await browser.close()


async def test_takehome_moments(p, name, vw, vh, dpr):
    """The crew's moments at MeeMee Rescue's points: the lookout as a round starts (step 1 behind the home planet's curve;
    steps 2 and 3 behind the track, gone before the sentence comes up), the engineer on a right answer, the navigator as
    a star turns peach, the commander on the end screen (the cook's place before 0.9.0); never over the diagram or the
    sentence; none without a job."""
    print(f"\n== Take MeeMee Home: the crew's moments ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"takehome-moments-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await th_set(page, "take", [{"whole": 7, "take": 4}, {"whole": 5, "take": 2}, {"whole": 6, "take": 3}, {"whole": 8, "take": 2}, {"whole": 4, "take": 1}])
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    pl = await page.evaluate(TH_PLACE)
    await t.tap(pl["x"], pl["y"])
    await th_until(page, "MW.events.some(e => e.type === 'moment' && e.detail === 'lookout home') && !!document.querySelector('#screen-takehome-play [data-moment=lookout].is-shown')", 15)          # once the title banner has gone and the round starts
    await asyncio.sleep(0.6)                                 # its rise (450 ms)
    look = await page.evaluate("""(() => { const b = document.querySelector('#screen-takehome-play [data-moment=lookout].is-shown'); if (!b) return null;
        const lay = b.closest('.mw-moments'), home = MW.takehome.homePlanet();
        return { window: [b.offsetLeft, b.offsetTop, b.offsetWidth, b.offsetHeight], behind: !!(lay.compareDocumentPosition(home) & Node.DOCUMENT_POSITION_FOLLOWING),
                 flip: b.classList.contains('takehome-peek-flip') }; })()""")
    lb = await moment_box(page, "#screen-takehome-play [data-moment=lookout]")
    await screenshot(page, f"takehome-{name}-lookout-home.png")
    pills = [(505, 612, 90, 70), (165, 612, 90, 70)]
    check(f"takehome-moments ({name}): step 1: the lookout rises from behind the home planet's curve as the round starts (its window 690, 548, to the stage's foot)",
          look is not None and look["window"] == [690, 548, 250, 252] and look["behind"] and not look["flip"], json.dumps(look))
    check(f"takehome-moments ({name}): ... clear of the diagram and its pills", lb and not any(overlaps_circle(lb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)])
          and not any(overlap(lb, q) for q in pills), json.dumps(lb))
    await th_wait(page, ["takehome-asking", "takehome-open"], 20)
    down = await th_until(page, "!document.querySelector('#screen-takehome-play [data-moment=lookout]')", 10)
    check(f"takehome-moments ({name}): ... and ducks down once it has spotted the planet (1.8 s into the first question)", down)
    await th_wait(page, ["takehome-open"], 20)
    await th_move(t, 4)
    await n_check(t)
    await asyncio.sleep(0.5)
    eb = await moment_box(page, "#screen-takehome-play [data-moment=engineer]")
    check(f"takehome-moments ({name}): the engineer taps the ship on a right answer, clear of the diagram and of the sentence's place under it",
          eb is not None and not any(overlaps_circle(eb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]) and not overlap(eb, (180, 700, 400, 80)) and eb[1] + eb[3] < 530,
          json.dumps(eb))
    await screenshot(page, f"takehome-{name}-engineer.png")
    await page.evaluate("MW.crew.save({moggles: 'navigator', snuffles: 'commander'})")
    await th_wait(page, ["takehome-open"], 30)
    await th_until(page, "!document.querySelector('#screen-takehome-play [data-moment].is-shown')", 10)   # question 1's moments are over
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await th_move(t, 2)
    await n_check(t)
    await th_until(page, "MW.events.filter(e => e.type === 'moment').length > %d" % n0, 15)
    await asyncio.sleep(0.5)
    nb = await moment_box(page, "#screen-takehome-play [data-moment=navigator]")
    route = await page.evaluate("(() => { const r = document.querySelector('#screen-takehome-play .mw-route path'); return r ? r.getAttribute('d') : null; })()")
    check(f"takehome-moments ({name}): the navigator holds up the star map as the star turns peach, with a dotted route to the next star, clear of the diagram",
          nb is not None and route is not None and "NaN" not in route and not any(overlaps_circle(nb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]) and nb[1] > 95,
          json.dumps([nb, route]))
    for q in range(2, 5):
        s = await th_wait(page, ["takehome-open"], 30)
        await th_move(t, s["answer"])
        await n_check(t)
    await th_wait(page, ["takehome-done"], 30)
    call = await wait_call(page, "#screen-takehome-end")
    badges = await page.evaluate("Array.from(document.querySelectorAll('#screen-takehome-end .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    await asyncio.sleep(0.8)
    await screenshot(page, f"takehome-{name}-commander.png")
    check(f"takehome-moments ({name}): the commander's radio calls on the end screen (0.9.0, the cook's moment before); the end screen's cats wear their badges",
          call_ok(call, [770, 450, 104, 148], False) and badges == ["moggles:navigator", "snuffles:commander"], json.dumps([call, badges]))
    await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'takehome-round-another')", 15)
    said = await t.said()
    check(f"takehome-moments ({name}): no words in the moments", not any("job-" in x or "name-" in x for x in said), json.dumps(said[-3:]))
    await t.tap(*HOME)
    await asyncio.sleep(0.4)
    check(f"takehome-moments ({name}): Home clears them", await page.evaluate("document.querySelectorAll('#screen-takehome-play [data-moment], #screen-takehome-end [data-moment]').length") == 0)

    # steps 2 and 3: the lookout peeks over the track, mirrored, and is gone before the sentence comes up under Scruffles
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    await th_set(page, "numbers", [{"whole": 7, "take": 4, "missing": "right"}] * 5)
    await page.evaluate("""(() => { window.__both = 0; window.__seen = 0; const loop = () => { const b = document.querySelector('#screen-takehome-play [data-moment=lookout].is-shown');
        const e = MW.takehome.equation().el; if (b) window.__seen++; if (b && e.classList.contains('is-shown')) window.__both++; window.__loop = requestAnimationFrame(loop); }; loop(); })()""")
    await t.tap(pl["x"], pl["y"])
    await th_until(page, "MW.events.some(e => e.type === 'moment' && e.detail === 'lookout track') && !!document.querySelector('#screen-takehome-play [data-moment=lookout].is-shown')", 15)          # once the title banner has gone and the round starts
    await asyncio.sleep(0.6)                                 # its rise (450 ms)
    look = await page.evaluate(LOOKOUT_LOOK.replace("#screen-game", "#screen-takehome-play").replace("rescue-peek-flip", "takehome-peek-flip"))
    await screenshot(page, f"takehome-{name}-lookout-track.png")
    check(f"takehome-moments ({name}): step 3: the lookout peeks up from behind the track's right-hand end, mirrored towards the diagram (906, 519, 250 x 175)",
          look is not None and look["window"] == [906, 519, 250, 175] and look["flip"] and look["scale"] == "-1 1" and look["scopeLeft"], json.dumps(look))
    s = await th_state(page)
    check(f"takehome-moments ({name}): ... and Scruffles starts the new round thinking, not still grinning from the last round's last answer, his lights off",
          s["face"] == "thinking" and not s["lights"] and s["phase"] == "takehome-starting", json.dumps(s))
    s = await th_wait(page, ["takehome-open"], 30)
    await asyncio.sleep(0.5)
    both = await page.evaluate("[window.__seen, window.__both, !!document.querySelector('#screen-takehome-play [data-moment=lookout]')]")
    await page.evaluate("cancelAnimationFrame(window.__loop)")
    check(f"takehome-moments ({name}): ... and has ducked down before the sentence comes up under Scruffles (never both at once)",
          both[0] > 10 and both[1] == 0 and not both[2] and s["sentence"] == "7 − _ = 3", json.dumps(both))
    await t.drag(*tile_xy(4), 550, 470)
    await n_check(t)
    await asyncio.sleep(0.5)
    eb = await moment_box(page, "#screen-takehome-play [data-moment=engineer]")
    check(f"takehome-moments ({name}): step 3: the engineer on a right answer, clear of the diagram and the sentence's place under Scruffles",
          eb is not None and not any(overlaps_circle(eb, c) for c in [(380, 205, 115), (210, 470, 125), (550, 470, 125)]) and not overlap(eb, (790, 528, 440, 100)), json.dumps(eb))
    # nobody has a job: no moments
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.evaluate("MW.crew.save({moggles: null, snuffles: null})")
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    await th_set(page, "take", [{"whole": 3, "take": 1}] * 5)
    await t.tap(pl["x"], pl["y"])
    await th_wait(page, ["takehome-open"], 30)
    await th_move(t, 1)
    await page.evaluate("window.__thq = performance.now()")
    await n_check(t)
    hopped = await th_until(page, "MW.events.some(e => e.type === 'home' && e.t > window.__thq)", 20)   # past the engineer's and the navigator's points
    check(f"takehome-moments ({name}): no jobs, no moments", hopped and await page.evaluate("MW.events.filter(e => e.type === 'moment').length") == n0)
    check(f"takehome-moments ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# ---------------------------------------------------------------- 0.9.0: the commander, the got-it face, the station, the tab row
async def open_motion(p, vw, vh, dpr, reduce, mode="auto"):
    """open_tablet with reduce motion on or off."""
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True,
                                    reduced_motion="reduce" if reduce else "no-preference")
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    if mode:
        await page.evaluate("MW.store.setting('check', %s); MW.store.setting('checkPicked', true)" % json.dumps(mode))
    return browser, ctx, page, Tablet(page, await ctx.new_cdp_session(page)), problems


async def rescue_quick_round(t, page):
    """MeeMee Rescue from the map (or the start screen): ROUND, each answer dropped in at once (answers checked as they
    are made), to the end screen."""
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    if await page.evaluate("MW.shell.screen") == "screen-start":
        await t.tap(*PLAY)
        await t.wait_screen("screen-map")
    await t.tap(*RESCUE)
    for q in range(len(ROUND)):
        for _ in range(250):
            s = await t.state()
            if s["phase"] == "open" and s["qi"] == q:
                break
            await asyncio.sleep(0.1)
        cx, cy = CENTRES[s["target"]]
        await page.evaluate("""(a) => { for (let i = 0; i < a.n; i++) { const c = MW.rescue.st.counters.filter(c => c.where === 'tray').pop();
            MW.rescue.drop(c, a.x, a.y, false); } }""", {"n": s["answer"], "x": cx, "y": cy})
    return await t.wait_phase(["done"], 25)


async def words_quick_round(t, page):
    """MeeMee Rockets from the map: one word found and built, to the end screen."""
    await w_open(t, page, [{"word": "toy", "step": "tiles"}])
    await t.tap([r for r in await w_rockets(page) if r["word"] == "toy"][0]["x"], 450)
    await w_wait(page, ["words-build"])
    await w_build(t)
    return await w_wait(page, ["words-done"], 20)


async def takehome_quick_round(t, page):
    """Take MeeMee Home from the map: one question in step 1 (3 take away 1), to the end screen."""
    await th_open(t, page, "take", [{"whole": 3, "take": 1}])
    await th_move(t, 1)
    await n_check(t)
    return await th_wait(page, ["takehome-done"], 30)


async def test_commander_moments(p, name, vw, vh, dpr, reduce=False):
    """0.9.0: the commander's moment on each game's end screen, in the cook's place (boards Moment14): the radio grows in
    where the pan did (MeeMee Rescue and Take MeeMee Home: Moggles's place, 254, 494, not flipped, as on the boards; MeeMee
    Rockets: the commander pops up beside the little rockets, 880, 560, and holds the radio up at 800, 630), its call
    rising above it, with sparkles; once, nothing repeating; logged as 'moment commander' where the cook's was logged;
    no cook moment. With reduce motion it fades in. Moggles is the commander and Snuffles the lookout, as on the boards.
    MeeMee Station's end screen (0.9.0 part B) has it at Take MeeMee Home's place (board round14-end)."""
    label = f"commander-moments ({name}{', reduce motion' if reduce else ''})"
    print(f"\n== 0.9.0: the commander's moment on each end screen ({name}{', reduce motion' if reduce else ''}) ==")
    browser, ctx, page, t, problems = await open_motion(p, vw, vh, dpr, reduce)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rounds = [("MeeMee Rescue", "#screen-end", rescue_quick_round, [254, 450, 104, 148], False, "round-rescued-all", "round-another", "rescue"),
              ("MeeMee Rockets", "#screen-words-end", words_quick_round, [800, 580, 120, 170], False, "words-round-done", "words-round-another", "rockets"),
              ("Take MeeMee Home", "#screen-takehome-end", takehome_quick_round, [254, 450, 104, 148], False, "takehome-round-done", "takehome-round-another", "takehome"),
              ("MeeMee Station", "#screen-station-end", station_quick_round, [254, 450, 104, 148], False, "station-round-done", "station-round-another", "station")]
    for game, screen, play, box, flipped, done_line, another, short in rounds:
        t0 = await page.evaluate("performance.now()")
        await play(t, page)
        call = await wait_call(page, screen)
        await asyncio.sleep(0.1)
        if not reduce:
            await screenshot(page, f"0.9.0/{name}-end-{short}-commander.png")          # as board Moment14 (sparkles still there)
        logged = await page.evaluate("(t0 => MW.events.filter(e => e.type === 'moment' && e.t >= t0).map(e => e.detail))", t0)
        check(f"{label}: {game}'s end screen: the commander's radio and its call {'fade' if reduce else 'grow'} in at the cook's place ({box[0]}, {box[1] + box[3] - box[2]}, "
              f"{box[2]} across, the call rising {box[3] - box[2]} above it, not flipped, as on the boards), with sparkles, once; no cook moment",
              call_ok(call, box, flipped, reduce), json.dumps(call))
        extra = True
        if short == "rockets":
            cat = await page.evaluate("""(() => { const b = document.querySelector('#screen-words-end [data-moment=commander-cat]'); if (!b) return null;
                const c = b.querySelector('.mw-cat'); return [b.offsetLeft, b.offsetTop, b.offsetWidth, b.classList.contains('is-shown'), c.dataset.who, c.dataset.job]; })()""")
            extra = cat == [880, 560, 170, True, "moggles", "commander"]
            check(f"{label}: ... Moggles, wearing the commander's badge, pops up beside the little rockets (880, 560, 170 wide) to hold it", extra, json.dumps(cat))
        else:
            badges = await page.evaluate("Array.from(document.querySelectorAll('%s .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)" % screen)
            extra = badges == ["moggles:commander", "snuffles:lookout"]
            check(f"{label}: ... beside Moggles, who wears the commander's badge", extra, json.dumps(badges))
        for _ in range(100):
            if another in await t.said():
                break
            await asyncio.sleep(0.1)
        said = await page.evaluate("(t0 => MW.events.filter(e => (e.type === 'say' || e.type === 'moment') && e.t >= t0).map(e => e.type + ' ' + e.detail))", t0)
        at = [said.index(x) if x in said else -1 for x in ("say " + done_line, "moment commander", "say " + another)]
        check(f"{label}: ... logged 'moment commander' (once, where the cook's was: after the round's last line, before 'another go'), and no words in it",
              logged.count("commander") == 1 and "cook" not in logged and -1 < at[0] < at[1] < at[2]
              and not any(x.startswith("say ") and ("job-" in x or "name-" in x) for x in said), json.dumps([logged, at]))
        await t.tap(*HOME)
        await t.wait_screen("screen-map", 5)
        check(f"{label}: ... and Home clears it", await page.evaluate("document.querySelectorAll('[data-moment]').length") == 0)
    check(f"{label}: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# Moggles and Snuffles, each with its usual face and its got-it face (board Faces15): four cats in a row on a test
# screen, each wearing its badge (Moggles the commander, Snuffles the lookout)
FACES_SCREEN = """(() => { let s = document.getElementById('screen-kittest');
    if (!s) { s = MW.make('section', 'mw-screen', {id: 'screen-kittest'}); MW.$('stage').appendChild(s); }
    MW.shell.show('screen-kittest'); s.innerHTML = ''; window.__cats = [];
    [['moggles', 'commander', 'usual', 140], ['moggles', 'commander', 'got-it', 420], ['snuffles', 'lookout', 'usual', 720], ['snuffles', 'lookout', 'got-it', 1000]].forEach(c => {
        const box = MW.crew.cat(c[0], 200); box.setJob(c[1]); const w = MW.make('div', 'mw-abs', { style: 'left:' + (c[3] - 100) + 'px;top:210px' });
        w.appendChild(box); s.appendChild(w); window.__cats.push([box, c[2]]); });
    return true; })()"""
# what a cat box shows: box.face(), its data-face, and which face groups are drawn (computed display), the nose shared
FACE_INFO = """(i => { const box = window.__cats[i][0], svg = box.querySelector('svg');
    const g = n => getComputedStyle(svg.querySelector('[data-face="' + n + '"]')).display !== 'none';
    const happy = svg.querySelector('[data-face="got-it"]'), eye = box.dataset.who === 'moggles' ? 'moggles-eye' : 'snuffles-eye';
    return { face: box.face(), attr: box.dataset.face, usual: g('usual'), gotIt: g('got-it'),
             groups: svg.querySelectorAll('[data-face]').length, nose: /f-nose/.test(happy.nextElementSibling.getAttribute('class')),
             drawn: [happy.querySelectorAll('path.s-' + eye).length, happy.querySelectorAll('ellipse.f-nose-pink[opacity="0.5"]').length,
                     happy.querySelectorAll('.f-mouth').length, happy.querySelectorAll('.f-tongue').length],
             badge: box.dataset.job }; })"""


async def test_crew_faces(p, name, vw, vh, dpr):
    """0.9.0: the crew's got-it face (Crew card; board Faces15). MW.crew.cat's box.face('got-it') shows the got-it face
    (happy closed eyes in the cat's own eye colour, a nose-pink blush at 50%, an open smile with a tongue) and hides the
    usual one; box.face('usual') the reverse; box.face() says which shows; a new box shows the usual face. Both cats.
    Nothing in 0.9.0's part A uses it (MeeMee Station will)."""
    print(f"\n== 0.9.0: the crew's got-it face ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"faces-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate(FACES_SCREEN)
    for i, who in ((0, "Moggles"), (2, "Snuffles")):
        new = await page.evaluate(FACE_INFO, i)
        check(f"faces ({name}): a new {who} shows its usual face (two face groups, the nose shared, after them)",
              new["face"] == "usual" and new["attr"] == "usual" and new["usual"] and not new["gotIt"] and new["groups"] == 2 and new["nose"], json.dumps(new))
        got = await page.evaluate("(i => window.__cats[i][0].face('got-it'))", i)
        on = await page.evaluate(FACE_INFO, i)
        check(f"faces ({name}): {who}'s box.face('got-it') shows the got-it face and hides the usual one; box.face() says 'got-it'",
              got == "got-it" and on["face"] == "got-it" and on["attr"] == "got-it" and on["gotIt"] and not on["usual"], json.dumps(on))
        check(f"faces ({name}): ... drawn as the Crew card says: two closed eyes in {who}'s eye colour, a nose-pink blush at 50% on each cheek, an open mouth with a tongue",
              on["drawn"] == [2, 2, 1, 1], json.dumps(on["drawn"]))
        back = await page.evaluate("(i => window.__cats[i][0].face('usual'))", i)
        off = await page.evaluate(FACE_INFO, i)
        check(f"faces ({name}): {who}'s box.face('usual') shows the usual face again and hides the got-it one; the badge stays",
              back == "usual" and off["face"] == "usual" and off["attr"] == "usual" and off["usual"] and not off["gotIt"] and off["badge"] == new["badge"], json.dumps(off))
    await page.evaluate("window.__cats.forEach(c => c[0].face(c[1]))")   # usual, got it, usual, got it: as the board
    faces = await page.evaluate("window.__cats.map(c => c[0].face() + ':' + c[0].dataset.face)")
    check(f"faces ({name}): Moggles and Snuffles, usual and got it, side by side", faces == ["usual:usual", "got-it:got-it", "usual:usual", "got-it:got-it"], str(faces))
    await asyncio.sleep(0.2)
    await screenshot(page, f"0.9.0/{name}-faces-got-it.png")
    check(f"faces ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_saved_cook(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """0.9.0: a tablet with a cook saved (settings.crew holding 'cook') has that cat as the commander from the first load:
    the change is saved the first time the jobs are read, so the map's badge, the crew screen and the end screen show the
    commander; nothing else in the saved data changes."""
    print(f"\n== 0.9.0: a tablet with a cook saved ({name}) ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
    saved = {"v": 1, "music": True, "settings": {"check": "tap", "wholes": [2, 3, 4, 5, 6, 7, 8, 9, 10], "checkPicked": True, "answerMode": "counting",
                                                 "crew": {"moggles": "cook", "snuffles": "lookout"}},
             "answers": secure_answers([(7, 3)]), "games": {"words": {"half": "autumn-2", "week": 3}, "takehome": {"step": "take"}}}
    await ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('mimi-world', %s); sessionStorage.setItem('seeded', '1'); }"
                              % json.dumps(json.dumps(saved)))
    page = await ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    t = Tablet(page, await ctx.new_cdp_session(page))
    want = json.loads(json.dumps(saved))
    want["settings"]["crew"] = {"moggles": "commander", "snuffles": "lookout"}
    stored = await page.evaluate("JSON.parse(localStorage.getItem('mimi-world'))")
    check(f"saved cook ({name}): as the page opens, Moggles (saved as the cook) is saved as the commander, and nothing else in the saved data changes",
          stored == want, json.dumps(stored["settings"]))
    got = await page.evaluate("""[MW.crew.jobs(), MW.crew.who('commander'), MW.crew.who('cook'), MW.crew.ready(),
        MW.events.filter(e => e.type === 'crew' && e.detail === 'the cook is now the commander').length]""")
    check(f"saved cook ({name}): MW.crew.jobs() has Moggles as the commander (no cook), changed once only",
          got == [{"moggles": "commander", "snuffles": "lookout"}, "moggles", None, True, 1], json.dumps(got))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    badge = await page.evaluate("""(() => { const c = document.querySelector('#screen-map .mw-cat[data-who=moggles]'), b = c.querySelector('.mw-badge');
        return [c.dataset.job, !!b && b.innerHTML === document.getElementById('art-badge-commander').content.firstElementChild.innerHTML]; })()""")
    check(f"saved cook ({name}): on the map Moggles wears the commander's badge (the radio)", badge == ["commander", True], json.dumps(badge))
    await asyncio.sleep(1.4)
    await t.tap(*CREW_BTN)
    await t.wait_screen("screen-crew")
    await asyncio.sleep(0.6)
    st = await crew_state(page)
    at = await cat_at(page, "moggles")
    check(f"saved cook ({name}): on the crew screen Moggles stands at the commander's station (the radio), wearing its badge",
          st["jobs"] == {"moggles": "commander", "snuffles": "lookout"} and st["taken"] == ["lookout", "commander"] and "moggles:commander" in st["badges"]
          and abs(at[0] - STATION["commander"][0]) < 3, json.dumps([st, at]))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await takehome_quick_round(t, page)
    call = await wait_call(page, "#screen-takehome-end")
    badges = await page.evaluate("Array.from(document.querySelectorAll('#screen-takehome-end .mw-cat')).map(e => e.dataset.who + ':' + e.dataset.job)")
    check(f"saved cook ({name}): on an end screen (Take MeeMee Home's) Moggles is the commander: its badge, and the commander's moment at its place",
          badges == ["moggles:commander", "snuffles:lookout"] and call_ok(call, [254, 450, 104, 148], False), json.dumps([badges, call]))
    await screenshot(page, f"0.9.0/{name}-saved-cook-end.png")
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    await page.reload()
    await page.wait_for_load_state("load")
    again = await page.evaluate("""[JSON.parse(localStorage.getItem('mimi-world')).settings.crew, MW.crew.jobs(),
        MW.events.filter(e => e.type === 'crew' && e.detail === 'the cook is now the commander').length]""")
    check(f"saved cook ({name}): opened again, it stays the commander (nothing left to change)",
          again == [{"moggles": "commander", "snuffles": "lookout"}, {"moggles": "commander", "snuffles": "lookout"}, 0], json.dumps(again))
    check(f"saved cook ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# the station on the map (0.9.0, redrawn): its group, what it is made of, and whether it is dimmed to 62%
STATION_DRAWN = """(() => { const svg = document.querySelector('#screen-map > svg.mw-layer'), p = MW.LAYOUT.map.planets[4];
    const g = svg.querySelector('g[transform^="translate(' + p.x + ' ' + (p.y + 6) + ')"]'); if (!g) return null;
    return { transform: g.getAttribute('transform'), dimmed: !!g.closest('g[opacity="0.62"]'),
             modules: g.querySelectorAll('rect.f-moon[width="16"]').length, lit: g.querySelectorAll('circle.f-spark[r="4.6"]').length,
             dark: g.querySelectorAll('circle.f-night-raised[r="4.6"]').length, wings: g.querySelectorAll('rect.f-planet-indigo').length,
             collars: g.querySelectorAll('rect.f-mint[width="5"]').length, truss: g.querySelectorAll('rect.f-mint-deep').length,
             tower: g.querySelectorAll('circle.s-mint').length, dish: g.querySelectorAll('path.f-moon-dim').length }; })()"""


# the grown-ups header (0.9.0, BondGrid's tab row): the title's lines, the title and Close on one line with Close at its
# right, and every tab under them inside the panel (stage px)
TAB_ROW = """(() => { const k = MW.stage.scale, sb = r => [(r.left - MW.stage.offX) / k, (r.top - MW.stage.offY) / k, (r.right - MW.stage.offX) / k, (r.bottom - MW.stage.offY) / k];
    const panel = sb(document.querySelector('.gu-panel').getBoundingClientRect()), title = document.querySelector('.gu-title');
    const rg = document.createRange(); rg.selectNodeContents(title);
    const tr = sb(rg.getBoundingClientRect()), cr = sb(document.querySelector('.gu-close').getBoundingClientRect());
    const tabs = Array.from(document.querySelectorAll('.gu-tab')).map(b => [b.textContent, sb(b.getBoundingClientRect())]);
    const r = v => Math.round(v);
    return { title: title.textContent, lines: rg.getClientRects().length, titleBox: tr.map(r), closeBox: cr.map(r), panel: panel.map(r),
             tabs: tabs.map(x => x[0]), rows: new Set(tabs.map(x => r(x[1][1]))).size,
             sameLine: cr[1] < (tr[1] + tr[3]) / 2 && (tr[1] + tr[3]) / 2 < cr[3], closeRight: cr[0] > tr[2] && cr[2] <= panel[2] - 24,
             under: tabs.every(x => x[1][1] >= Math.max(tr[3], cr[3])),
             inside: tabs.every(x => x[1][0] >= panel[0] && x[1][2] <= panel[2] && x[1][3] <= panel[3]),
             tabsBox: tabs.length ? [r(Math.min(...tabs.map(x => x[1][0]))), r(Math.min(...tabs.map(x => x[1][1]))), r(Math.max(...tabs.map(x => x[1][2]))), r(Math.max(...tabs.map(x => x[1][3])))] : null }; })()"""
# one tab more than the page has (a ninth with the starter game's): a copy of a tab, before the world's Checks and Sound
ADD_TAB = """(() => { const tabs = document.querySelector('.gu-tabs'), checks = tabs.querySelector('[data-tab=checks]');
    const b = checks.cloneNode(true); b.textContent = 'Extra'; b.setAttribute('data-tab', 'test-extra'); b.classList.remove('is-on');
    tabs.insertBefore(b, checks); return tabs.children.length; })()"""


def tab_row_ok(r, n):
    return (r["title"] == "Grown-ups" and r["lines"] == 1 and r["sameLine"] and r["closeRight"] and len(r["tabs"]) == n and r["under"] and r["inside"])


async def tab_row_check(page, label, n, shot):
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show(MW.grownups.sections[0].id)")
    await asyncio.sleep(0.3)
    r = await page.evaluate(TAB_ROW)
    if len(r["tabs"]) < n:
        await page.evaluate(ADD_TAB)
        await asyncio.sleep(0.2)
        r = await page.evaluate(TAB_ROW)
    check(f"{label}: 'Grown-ups' on one line with Close at its right, and all {n} tabs ({', '.join(r['tabs'])}) on {'their own row' if r['rows'] == 1 else str(r['rows']) + ' rows'} under it, inside the panel",
          tab_row_ok(r, n), json.dumps(r))
    await screenshot(page, shot)
    await page.evaluate("MW.grownups.close()")
    return r


async def test_tab_row(p):
    """0.9.0: the grown-ups tab row (BondGrid card; board Grownups14): "Grown-ups" alone on the title line with Close at
    its right, the tabs on their own row under it (wrapping if they must), at both sizes: with today's tabs (Progress,
    Settings, Words, Subtraction, Station, Checks, Sound: seven since MeeMee Station, 0.9.0 part B), with the starter
    game's added (a test copy: eight), and with one more (nine, wrapping if it must)."""
    import shutil
    import subprocess
    print("\n== 0.9.0: the grown-ups tab row ==")
    sizes = (("fire", 1046, 653, 1.22), ("doogee", 1280, 800, 2))
    for name, vw, vh, dpr in sizes:
        browser, ctx, page, t, problems, _ = await open_tablet(p, f"tabs-{name}", vw, vh, dpr, mode=None)
        r = await tab_row_check(page, f"tab row ({name}, today's page)", 7, f"0.9.0/{name}-grownups-tabs-7.png")
        check(f"tab row ({name}, today's page): the tabs are Progress, Settings, Words, Subtraction, Station, Checks and Sound",
              r["tabs"] == ALL_TABS, json.dumps(r["tabs"]))
        check(f"tab row ({name}): no console errors", not problems, "; ".join(problems[:3]))
        await browser.close()
    here = pathlib.Path(__file__).resolve().parent
    out, src = here / "serve-template", here / "serve-template-src" / "starter"
    if src.parent.exists():
        shutil.rmtree(src.parent)
    shutil.copytree(ROOT / "games" / "_template", src, ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, str(ROOT / "tools"))
    import games as G
    free = [i for i in range(G.PLANETS) if i not in {g.get("planet") for g in G.load()}]
    if not free:
        check("tab row: with the starter game's tab", True, "skipped: every place has a game")
        return
    gj = json.loads((src / "game.json").read_text(encoding="utf-8"))
    gj["planet"] = free[0]
    (src / "game.json").write_text(json.dumps(gj), encoding="utf-8")
    res = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--no-audio", "--out", str(out), "--extra-game", str(src)], capture_output=True, text=True)
    check("tab row: a test copy with the starter game builds", res.returncode == 0, (res.stdout + res.stderr)[-300:])
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", TPL_PORT), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for name, vw, vh, dpr in sizes:
            browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
            page = await ctx.new_page()
            problems = []
            page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
            await page.goto(f"http://127.0.0.1:{TPL_PORT}/")
            await page.wait_for_load_state("load")
            await tab_row_check(page, f"tab row ({name}, with the starter game)", 8, f"0.9.0/{name}-grownups-tabs-8.png")
            await tab_row_check(page, f"tab row ({name}, with a ninth tab)", 9, f"0.9.0/{name}-grownups-tabs-9.png")
            check(f"tab row ({name}, test copy): no console errors", not problems, "; ".join(problems[:3]))
            await browser.close()
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------- 0.9.0 part B: MeeMee Station (games/station), the ten frame and bar model
ST_SHOTS = SHOTS9 / "station"                     # MeeMee Station's screenshots, named after the boards they match
ST_SHOTS.mkdir(exist_ok=True)
ST_PLACE = "MW.LAYOUT.map.planets[MW.world.games.find(g => g.id === 'station').planet]"
ST_STEPS = ("aboard", "more", "numbers")
ST_PRAISE = {"praise-found-it", "praise-thats-right", "praise-super-counting", "praise-well-done", "station-all-aboard"}   # MeeMee Rescue's four and its own
ST_UNDER = [180, 700]                              # the sentence's usual place (its box's top-left corner)
ST_ON_STATION = (430, 300)                         # step 1: a point on the station (the drop box is 40, 100 to 820, 500)
ST_ON_DECK = (930, 690)                            # step 1: a point on the deck (a touch there picks up the nearest MeeMee)
# What the game screen shows (stage px): the round's step and question, the windows (each one's state), the MeeMee, the
# tower's whole, the hull modules (value, waiting, success, hinting, number shown), the tiles, the sentence, the commander
ST_STATE = """(() => { const R = MW.station, s = R.st, tr = R.track(), e = R.equation(), g = document.getElementById('screen-station-play');
    const shown = el => !!el && getComputedStyle(el).display !== 'none' && !el.closest('.mw-off');
    const cat = g.querySelector('.station-commander .mw-cat'), box = g.querySelector('.station-commander');
    const bar = m => m ? [m.value, m.el.classList.contains('is-waiting'), m.el.classList.contains('is-success'), m.el.classList.contains('is-hinting'),
                          (m.el.querySelector('.station-bar-n') || {}).textContent || null] : null;
    const b = R.bars(), wh = g.querySelector('.station-whole');
    return { phase: MW.world.st.phase, qi: s.qi, step: R.step(), target: s.target, answer: s.answer, tries: s.tries, misses: s.misses,
             hinted: s.hinted, placed: s.placed ? s.placed.n : null, screen: MW.shell.screen,
             windows: R.windows().map(w => w.state), aboard: s.counters.filter(c => c.where === 'aboard').map(c => c.win),
             deck: s.counters.filter(c => c.where === 'deck').length, fixed: s.fixed.length, hintMimi: s.hintMimi.length,
             whole: wh ? wh.textContent : null, bars: b ? ['whole', 'left', 'right'].map(k => bar(b[k])) : null,
             track: shown(tr.el) && !tr.away(), away: tr.away(), out: tr.tiles.filter(t => t.out()).map(t => t.n),
             ghosts: g.querySelectorAll('.mw-ghost').length, lit: g.querySelectorAll('.mw-ghost.is-lit').length,
             face: g.querySelector('.mw-pod').dataset.face, ready: g.querySelector('.mw-pod').classList.contains('is-ready'),
             lights: g.querySelector('.mw-pod').classList.contains('is-celebrating'),
             sentence: e.el.classList.contains('is-shown') ? Array.from(e.el.children).map(c => c.textContent).join(' ') : '',
             at: [e.el.offsetLeft, e.el.offsetTop],
             commander: cat ? [cat.dataset.who, cat.dataset.face, cat.dataset.job, box.offsetLeft, box.offsetTop, cat.offsetWidth] : null,
             hintStation: !!g.querySelector('.station-hint'), sparks: g.querySelectorAll('.mw-spark').length,
             stars: Array.from(g.querySelectorAll('.mw-stars svg')).map(x => x.dataset.state).join(',') }; })()"""
ST_FACES = "MW.events.filter(e => e.type === 'commander' && e.t > (window.__stq || 0)).map(e => e.detail)"
# A line the game asked for on its own (its last 'say'): whether it is recorded, and whether the kit skipped it (the next
# say or audio-fail after it is the kit's "not recorded yet" for it). The say log has a line whether or not it is heard,
# so this tells a skipped line from a played one; the test passes whichever it really is (skipped exactly while pending).
ST_HEARD = """(id => { const ev = MW.events, i = ev.map(e => e.type + ' ' + e.detail).lastIndexOf('say ' + id); if (i < 0) return null;
    const next = ev.slice(i + 1).find(e => e.type === 'say' || e.type === 'audio-fail');
    return { recorded: MW.audio.recorded(id), skipped: !!next && next.type === 'audio-fail' && next.detail === 'not recorded yet: ' + id }; })"""


def st_q(step, q):
    """A question as the game has it: whole, a (already aboard), b (the rest), missing (where the answer goes)."""
    return {"whole": q["whole"], "a": q["a"], "b": q["whole"] - q["a"], "missing": q.get("missing") or "right"}


def st_answer(q):
    return q["whole"] if q["missing"] == "whole" else (q["a"] if q["missing"] == "left" else q["b"])


def st_prompt(step, q, qi, recorded=()):
    """What Scruffles says for a question, as the say log has it: MeeMee Rescue's "Let's make… seven. We've got… three."
    (and "How many more?" in steps 2 and 3), or for a missing whole "We've got… five… and four. How many altogether?". The
    first two questions of a round add "Bring more MeeMee aboard." (step 1) or "Find the number." (steps 2 and 3) once
    recorded (recorded: the lines stubbed as recorded), then "Tap Scruffles when you're ready."."""
    q = st_q(step, q)
    if step == "numbers" and q["missing"] == "whole":
        p = [f"q-weve-got num-mid-{q['a']} and num-end-{q['b']}", "q-how-many-altogether"]
    else:
        given = q["b"] if step == "numbers" and q["missing"] == "left" else q["a"]
        p = [f"q-lets-make num-end-{q['whole']}", f"q-weve-got num-end-{given}"] + (["q-how-many-more"] if step != "aboard" else [])
    if qi < 2:
        extra = "station-bring-aboard" if step == "aboard" else "station-find-number"
        p += ([extra] if extra in recorded else []) + ["tap-scruffles"]
    return " ".join(p)


def st_text(q):
    """The sentence as ST_STATE shows it: MeeMee Rescue's '3 + 4 = 7'."""
    return f"{q['a']} + {q['b']} = {q['whole']}"


def st_said_sentence(q):
    return f"num-mid-{q['a']} and num-mid-{q['b']} make num-end-{q['whole']}"


async def st_state(page):
    return await page.evaluate(ST_STATE)


async def st_wait(page, phases, timeout=25):
    for _ in range(int(timeout / 0.1)):
        s = await st_state(page)
        if s["phase"] in phases:
            return s
        await asyncio.sleep(0.1)
    return await st_state(page)


async def st_set(page, step=None, round_=None, wholes=None):
    """This game's own saved choices (its step, its wholes in play) and the next round, as a grown-up and the tests set them."""
    await page.evaluate("""(a) => { const g = MW.store.game('station'); if (a.step) g.step = a.step; if (a.wholes) g.wholes = a.wholes; MW.store.save();
        if (a.round) MW.station.nextRound = a.round; }""", {"step": step, "round": round_, "wholes": wholes})


async def st_open(t, page, step, round_):
    """Play (if on the start screen), then place 4 on the map: the round, in this step."""
    await st_set(page, step, round_)
    if await page.evaluate("MW.shell.screen") == "screen-start":
        await t.tap(*PLAY)
        await t.wait_screen("screen-map")
    pl = await page.evaluate(ST_PLACE)
    await t.tap(pl["x"], pl["y"])
    return await st_wait(page, ["station-open"], 30)


async def st_bring(t, n, to=ST_ON_STATION, frm=ST_ON_DECK):
    """Step 1: n MeeMee dragged from the deck (a touch on it picks up the nearest) onto the station."""
    for _ in range(n):
        await t.drag(*frm, *to)


async def st_berth(page):
    """The empty berth's middle (stage px)."""
    return await page.evaluate("(() => { const m = MW.station.st.berth; return [m.x + m.w / 2, m.y + m.h / 2]; })()")


async def st_shot(page, name, board):
    """A screenshot named after the board it matches, in tools/tests/shots/0.9.0/station/."""
    await page.screenshot(path=str(ST_SHOTS / f"{name}-{board}.png"))


def st_windows(a, w, kind=None):
    """The ten windows' states: '' up to a, then kind ('hinting', 'arrived' or '') up to w, 'closed' after (or all open)."""
    if kind is None:
        return [""] * 10
    return [""] * a + [kind] * (w - a) + ["closed"] * (10 - w)


async def st_round(t, page, step, round_, name, shots):
    """Play a whole round right first time, checking each question's look and words, the right answer, the commander's
    smile, the sentence and the stars. shots: take the boards' screenshots (question 1, and the first missing whole)."""
    for qi, q0 in enumerate(round_):
        q = st_q(step, q0)
        s = await st_wait(page, ["station-open"], 25)
        await n_quiet(t)
        said = await t.said()
        check(f"station-{step} ({name}): question {qi + 1} ({st_text(q)}, the answer in {q['missing']}) asked: '{st_prompt(step, q, qi)}'",
              s["qi"] == qi and said[-1:] == [st_prompt(step, q, qi)] and s["stars"] == ",".join(["done"] * qi + ["current"] + ["todo"] * (4 - qi)),
              json.dumps([said[-1:], s["stars"]]))
        ans = st_answer(q)
        if step == "aboard":
            check(f"station-aboard ({name}): question {qi + 1}: the whole ({q['whole']}) on the tower's screen, a MeeMee in each of the first {q['a']} windows, "
                  f"{10 - q['a']} waiting on the deck (enough to fill every window), all ten windows open; no track, no hull modules, no sentence",
                  s["whole"] == str(q["whole"]) and s["fixed"] == q["a"] and s["deck"] == 10 - q["a"] and s["windows"] == st_windows(q["a"], q["whole"])
                  and not s["track"] and s["bars"] is None and s["sentence"] == "", json.dumps(s))
            if shots and qi == 0:
                await st_bring(t, 2)
                await n_hold(t, *ST_ON_DECK, 790, 560, touch_id=80)        # a third on its way in (board s1ask)
                await asyncio.sleep(0.2)
                await st_shot(page, name, "s1ask")
                x2, y2 = await t.screen(*ST_ON_STATION)
                await touch(t, "touchMove", [(80, (x2, y2))])
                await asyncio.sleep(0.05)
                await touch(t, "touchEnd", [])
                await asyncio.sleep(0.4)
                await st_bring(t, q["b"] - 3)
            else:
                await st_bring(t, q["b"])
            s = await st_state(page)
            check(f"station-aboard ({name}): question {qi + 1}: {q['b']} brought aboard fill the next windows in ten-frame order ({q['a']} to {q['whole'] - 1}), "
                  f"the ship's lights glow",
                  sorted(s["aboard"]) == list(range(q["a"], q["whole"])) and s["deck"] == 10 - q["whole"] and s["ready"] and s["phase"] == "station-open", json.dumps(s))
        else:
            want = [[q["whole"], False, False, False, str(q["whole"])], [q["a"], False, False, False, str(q["a"])], [q["b"], False, False, False, str(q["b"])]]
            want[{"whole": 0, "left": 1, "right": 2}[q["missing"]]] = [None, True, False, False, None]
            if step == "more":
                check(f"station-more ({name}): question {qi + 1}: the station with a MeeMee in each of the first {q['a']} windows, all open; the hull modules: "
                      f"the whole {q['whole']}, the part {q['a']} and an empty berth; the track; no sentence",
                      s["fixed"] == q["a"] and s["windows"] == st_windows(q["a"], q["whole"]) and s["bars"] == want and s["track"] and s["sentence"] == ""
                      and s["deck"] == 0, json.dumps(s))
            else:
                check(f"station-numbers ({name}): question {qi + 1}: the hull modules alone (no station, no windows), the berth in its place ({q['missing']}); the track",
                      s["windows"] == [] and s["fixed"] == 0 and s["bars"] == want and s["track"] and s["sentence"] == "", json.dumps(s))
                if shots and q["missing"] != "whole" and qi == 0:
                    await asyncio.sleep(0.3)
                    await st_shot(page, name, "s3ten")
                if shots and q["missing"] == "whole" and qi == 1:
                    await asyncio.sleep(0.3)
                    await st_shot(page, name, "s3whole")
            berth = await st_berth(page)
            if shots and step == "more" and qi == 0:
                await n_hold(t, *tile_xy(ans), 580, 584, touch_id=81)          # board s2ask: tile 4 on its way to the berth
                await st_shot(page, name, "s2ask")
                x2, y2 = await t.screen(*berth)
                await touch(t, "touchMove", [(81, (x2, y2))])
                await asyncio.sleep(0.05)
                await touch(t, "touchEnd", [])
                await asyncio.sleep(0.4)
            else:
                await t.drag(*tile_xy(ans), berth[0] + 25, berth[1] - 15)
            s = await st_state(page)
            tile = await page.evaluate("(n => { const t = MW.station.track().tile(n); return [t.x, t.y]; })(%d)" % ans)
            check(f"station-{step} ({name}): question {qi + 1}: tile {ans} let go on the berth docks in its middle, the ship's lights glow",
                  s["placed"] == ans and abs(tile[0] - berth[0]) < 0.6 and abs(tile[1] - berth[1]) < 0.6 and s["ready"], json.dumps([s, tile, berth]))
        await page.evaluate("window.__stq = performance.now()")
        await n_check(t)
        s = await st_state(page)
        if shots and qi == 0 and step != "numbers":
            await st_shot(page, name, "s1right" if step == "aboard" else "s2right")
        if step == "aboard":
            look = s["windows"] == st_windows(q["a"], q["whole"], "arrived") and s["sparks"] == 5 * q["b"]
        else:
            filled = [[q["whole"], False, False, False, str(q["whole"])], [q["a"], False, False, False, str(q["a"])], [q["b"], False, False, False, str(q["b"])]]
            k = {"whole": 0, "left": 1, "right": 2}[q["missing"]]
            filled[k] = [ans, False, True, False, str(ans)]
            look = s["bars"] == filled and not s["track"] and s["placed"] is None
            if step == "more":
                look = look and s["windows"] == st_windows(q["a"], q["whole"], "arrived") and s["fixed"] == q["whole"] and s["sparks"] == 5 * q["b"]
            else:
                look = look and s["windows"] == [] and s["sparks"] == 5
        what = {"aboard": "the newcomers' windows glow peach (arrived), the spare windows shut, sparkles at each",
                "more": f"the berth becomes a hull module showing {ans} with the success ring, {q['b']} MeeMee pop into the empty windows (arrived), "
                        "the spare windows shut, sparkles, the track slides away",
                "numbers": f"the berth becomes a hull module showing {ans} with the success ring, sparkles, the track slides away"}[step]
        blinked = await th_until(page, "MW.events.filter(e => e.type === 'commander' && e.t > window.__stq).length >= 3", 5)
        faces = await page.evaluate(ST_FACES)
        check(f"station-{step} ({name}): question {qi + 1}: a tap on Scruffles checks it: right; {what}; the got-it face and the ship's lights; the commander "
              f"blinks, then smiles (its faces so far: got it, usual, got it)",
              s["phase"] == "station-celebrate" and s["face"] == "got-it" and s["lights"] and look and blinked and faces == ["got-it", "usual", "got-it"],
              json.dumps([s, faces]))
        ok = await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === %s && e.t > window.__stq)" % json.dumps(st_said_sentence(q)), 20)
        await asyncio.sleep(0.3)
        s = await st_state(page)
        if shots and qi == 0 and step != "numbers":
            await st_shot(page, name, "step1-smile" if step == "aboard" else "step2-smile")
        said = await t.said()
        sent = st_said_sentence(q)
        i = len(said) - 1 - said[::-1].index(sent) if sent in said else -1
        check(f"station-{step} ({name}): question {qi + 1}: praise, then the sentence shows under the picture ({st_text(q)}, 180, 700) and is said "
              f"('{sent}'), the commander smiling while it is said",
              ok and i > 0 and said[i - 1] in ST_PRAISE and s["sentence"] == st_text(q) and s["at"] == ST_UNDER and s["commander"][1] == "got-it", json.dumps([said[-3:], s]))
        await th_until(page, "MW.events.some(e => e.type === 'commander' && e.detail === 'usual' && e.t > window.__stq) && "
                             "MW.station.st.commander && MW.station.st.commander.face() === 'usual' && MW.world.st.phase === 'station-celebrate'", 10)
        faces = await page.evaluate(ST_FACES)
        check(f"station-{step} ({name}): question {qi + 1}: the commander blinked, then smiled until the sentence was said, then looks as before "
              f"(got it, usual, got it, usual)", faces == ["got-it", "usual", "got-it", "usual"], json.dumps(faces))
    s = await st_wait(page, ["station-done"], 25)
    if shots and step == "aboard":
        await wait_call(page, "#screen-station-end")
        await asyncio.sleep(0.1)
        await st_shot(page, name, "end")                    # board round14-end (the commander's radio, its sparkles still there)
    ok = await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'station-round-another')", 15)
    said = await page.evaluate("MW.events.filter(e => e.type === 'say' || e.type === 'moment').map(e => e.type + ' ' + e.detail)")
    at = [said.index(x) if x in said else -1 for x in ("say station-round-done", "moment commander", "say station-round-another")]
    heard = [await page.evaluate(ST_HEARD + "(%s)" % json.dumps(x)) for x in ("station-round-done", "station-round-another")]
    check(f"station-{step} ({name}): after five, the end screen: five stars; the game asks for 'All the MeeMee are aboard!', then the commander's moment, "
          f"then 'Another visit?' (the kit skips each while it is pending, and plays it once recorded)",
          ok and await page.evaluate("MW.shell.screen") == "screen-station-end" and -1 < at[0] < at[1] < at[2]
          and all(h is not None and h["skipped"] != h["recorded"] for h in heard)
          and await page.evaluate("Array.from(document.querySelectorAll('#screen-station-end .mw-stars svg')).map(x => x.dataset.state).join(',')") == ",".join(["done"] * 5),
          json.dumps([at, said[-4:], heard]))


async def test_station_round(p, step, name, vw, vh, dpr):
    """A whole round of one step, right first time, played by touch, with the boards' screenshots (round 13's ask and
    right, round 15's smile, round 14's end). Moggles is the commander and Snuffles the lookout, as on the boards."""
    print(f"\n== MeeMee Station: a round of step {ST_STEPS.index(step) + 1} ({step}, {name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-{step}-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rounds = {"aboard": [{"whole": 7, "a": 3}, {"whole": 5, "a": 1}, {"whole": 9, "a": 4}, {"whole": 2, "a": 1}, {"whole": 10, "a": 6}],
              "more": [{"whole": 7, "a": 3}, {"whole": 8, "a": 5}, {"whole": 6, "a": 1}, {"whole": 10, "a": 2}, {"whole": 4, "a": 3}],
              "numbers": [{"whole": 10, "a": 6, "missing": "right"}, {"whole": 9, "a": 5, "missing": "whole"}, {"whole": 6, "a": 2, "missing": "left"},
                          {"whole": 3, "a": 1, "missing": "right"}, {"whole": 8, "a": 7, "missing": "whole"}]}
    s = await st_open(t, page, step, rounds[step])
    said = await t.said()
    heard = await page.evaluate(ST_HEARD + "('station-round-ready')")
    check(f"station-{step} ({name}): place 4 opens MeeMee Station in this step: the game asks for 'Let's bring the MeeMee aboard!' (the kit skips it while "
          f"it is pending, and plays it once recorded), then question 1",
          s["screen"] == "screen-station-play" and s["step"] == step and s["qi"] == 0 and "station-round-ready" in said
          and said.index("station-round-ready") < len(said) - 1 and heard is not None and heard["skipped"] != heard["recorded"], json.dumps([s, said[-3:], heard]))
    check(f"station-{step} ({name}): the commander (Moggles, wearing the commander's badge) stands {'on the deck (1146, 598, 108 wide)' if step == 'aboard' else 'at the track’s right-hand end (1110, 498, 124 wide)'}",
          s["commander"] == (["moggles", "usual", "commander", 1146, 598, 108] if step == "aboard" else ["moggles", "usual", "commander", 1110, 498, 124]), json.dumps(s["commander"]))
    await st_round(t, page, step, rounds[step], name, True)
    saved = await page.evaluate("JSON.parse(localStorage.getItem('mimi-world'))")
    mine = saved["games"]["station"]["answers"]
    check(f"station-{step} ({name}): five answers saved in this game's own record for this step, each right first time; MeeMee Rescue's answers untouched",
          list(mine) == [step] and len(mine[step]) == 5 and all(a["tries"] == 0 and a["hint"] is False for a in mine[step])
          and [(a["whole"], a["a"], a["missing"]) for a in mine[step]] == [(q["whole"], q["a"], st_q(step, q)["missing"]) for q in rounds[step]]
          and saved["answers"] == [], json.dumps(saved["games"]["station"])[:300])
    check(f"station-{step} ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def st_newcomer(page, win):
    """Step 1: the middle of the newcomer in window win."""
    return await page.evaluate("(w => { const c = MW.station.st.counters.find(c => c.where === 'aboard' && c.win === w); return c ? [c.x, c.y] : null; })(%d)" % win)


async def st_in_order(page):
    """Step 1: every newcomer at its own window's middle, the windows filled in ten-frame order after those aboard."""
    return await page.evaluate("""(() => { const R = MW.station, s = R.st, w = R.windows(), list = s.counters.filter(c => c.where === 'aboard').sort((p, q) => p.win - q.win);
        return list.every((c, i) => c.win === s.q.a + i && Math.abs(c.x - w[c.win].x) < 0.5 && Math.abs(c.y - w[c.win].y) < 0.5)
            && s.counters.filter(c => c.where === 'deck').every(c => Math.abs(c.x - c.home.x) < 0.5 && Math.abs(c.y - c.home.y) < 0.5); })()""")


async def test_station_wrong_aboard(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """Step 1's wrong checks: nothing punishes ("Let's try again." before the hint; after it, only Scruffles's face, as in
    steps 2 and 3, MeeMee Rescue and Take MeeMee Home); too many has its own line; a MeeMee let go off the station floats
    back; one taken back out leaves no gap; two wrong checks bring the hint (the newcomers go back to the deck, the
    windows past the whole shut, and the windows from a + 1 to w light as they are counted on, board s1hint); the child
    still brings them, and only as many as the whole; a hinted fact isn't right first time. The commander never smiles
    at a wrong check or the hint."""
    print(f"\n== MeeMee Station: step 1's wrong checks and the hint ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-wrong-aboard-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await st_open(t, page, "aboard", [{"whole": 7, "a": 3}, {"whole": 5, "a": 2}, {"whole": 6, "a": 4}, {"whole": 8, "a": 2}, {"whole": 4, "a": 1}])
    await n_quiet(t)
    await page.evaluate("window.__stq = performance.now()")
    n0 = len(await t.said())
    await t.tap(*POD)                                        # none brought yet: too few, tapped twice in quick succession
    await asyncio.sleep(0.12)
    await t.tap(*POD)
    await asyncio.sleep(0.4)
    s = await st_state(page)
    waited = await page.evaluate("MW.events.some(e => e.type === 'check' && e.detail === 'still answering')")
    check(f"station-wrong-aboard ({name}): Scruffles double-tapped with none brought: 'Let's try again.' once, the try-again face, one try (the second "
          f"tap does nothing while he is answering), no hint",
          (await t.said())[n0:] == ["again-try-again"] and waited and s["face"] == "try-again" and s["tries"] == 1 and not s["hinted"] and s["phase"] == "station-open",
          json.dumps(s))
    await asyncio.sleep(1.8)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): ... and Scruffles is soon thinking again (no red, nothing taken away)", s["face"] == "thinking" and s["fixed"] == 3 and s["deck"] == 7, json.dumps(s))
    # a MeeMee let go off the station floats back to its place on the deck: not a try, a whoosh, nothing said
    n0 = len(await t.said())
    misses = "MW.events.filter(e => e.type === 'drop' && e.detail === 'miss').length"
    m0 = await page.evaluate(misses)
    for to in ((600, 590), (30, 300), (430, 560)):
        await t.drag(*ST_ON_DECK, *to)
        await asyncio.sleep(0.3)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): MeeMee let go off the station (the sky, left of it, under it) float back to their places on the deck "
          f"(a miss each, not a try, nothing said)",
          s["aboard"] == [] and s["deck"] == 7 and await st_in_order(page) and s["tries"] == 1 and (await t.said())[n0:] == [] and await page.evaluate(misses) - m0 == 3,
          json.dumps(s))
    # too many: its own line, a try, never the hint
    await st_bring(t, 6)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): six brought for 7 with 3 aboard fill windows 4 to 9, in ten-frame order (all ten windows are open)",
          sorted(s["aboard"]) == [3, 4, 5, 6, 7, 8] and await st_in_order(page) and s["windows"] == st_windows(3, 7), json.dumps(s))
    await n_check(t)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): nine aboard for 7: 'That's too many. Take one back.' (a try, never the hint)",
          (await t.said())[-1:] == ["too-many"] and s["tries"] == 2 and not s["hinted"] and len(s["aboard"]) == 6, json.dumps(s))
    await n_quiet(t)
    # one taken back out from the middle: back to the deck, and the ones after it close up
    xy = await st_newcomer(page, 5)
    await t.drag(*xy, 600, 590)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): the newcomer in window 6 taken back off the station goes back to the deck, and the ones after it close up "
          f"(windows 4 to 8 full, in order, no gap)",
          sorted(s["aboard"]) == [3, 4, 5, 6, 7] and s["deck"] == 2 and await st_in_order(page), json.dumps(s))
    for w in (7, 6, 5, 4):
        await t.drag(*(await st_newcomer(page, w)), 1000, 700)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): four more taken back (let go on the deck) leave one brought, in window 4", s["aboard"] == [3] and s["deck"] == 6, json.dumps(s))
    # too few: the hint. The newcomer goes back to the deck; the windows past the whole shut; 4 to 7 counted on from 3
    await n_check(t)
    s = await st_state(page)
    said = await t.said()
    check(f"station-wrong-aboard ({name}): then too few: the hint: 'Let's count on from… three. Four, five, six, seven.'; the newcomer back on the deck, "
          f"windows 8 to 10 shut, 4 to 7 lit for counting (a ghost in each)",
          said[-1:] == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"] and s["hinted"] and s["tries"] == 3 and s["aboard"] == []
          and s["deck"] == 7 and s["windows"] == st_windows(3, 7, "hinting") and s["ghosts"] == 4, json.dumps([said[-1:], s]))
    await th_until(page, "document.querySelectorAll('#screen-station-play .mw-ghost.is-lit').length >= 2", 8)
    await st_shot(page, name, "s1hint")
    await n_quiet(t)
    await asyncio.sleep(0.3)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): ... each window lights as its number is said, and they stay lit; the child still brings them",
          s["lit"] == 4 and s["phase"] == "station-open" and s["aboard"] == [], json.dumps(s))
    await st_bring(t, 2)
    n0 = len(await t.said())
    await n_check(t)
    await asyncio.sleep(0.6)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): two brought and a check, too few again after the hint: only the try-again face, nothing said (as in steps 2 "
          f"and 3, MeeMee Rescue and Take MeeMee Home); the hint stays",
          (await t.said())[n0:] == [] and s["face"] == "try-again" and s["tries"] == 4 and s["hinted"] and s["lit"] == 4 and s["phase"] == "station-open",
          json.dumps([(await t.said())[n0:], s]))
    await asyncio.sleep(1.2)
    check(f"station-wrong-aboard ({name}): ... and Scruffles is soon thinking again", (await st_state(page))["face"] == "thinking")
    await st_bring(t, 2)
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'no window').length")
    await st_bring(t, 1)
    s = await st_state(page)
    check(f"station-wrong-aboard ({name}): with the windows past the whole shut, the station takes only the whole: a fifth brought floats back to the deck",
          sorted(s["aboard"]) == [3, 4, 5, 6] and s["deck"] == 3 and await st_in_order(page)
          and await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'no window').length") == n0 + 1, json.dumps(s))
    await n_check(t)
    s = await st_state(page)
    rec = await page.evaluate("MW.station.answers('aboard').slice(-1)[0]")
    faces = await page.evaluate(ST_FACES)
    check(f"station-wrong-aboard ({name}): seven and a tap: right (the newcomers' windows arrived, the spare ones shut, the ghosts gone); saved with "
          f"4 wrong checks and the hint; the commander smiled only now",
          s["phase"] == "station-celebrate" and rec["tries"] == 4 and rec["hint"] is True and s["ghosts"] == 0
          and s["windows"] == st_windows(3, 7, "arrived") and faces[:1] == ["got-it"] and faces.count("got-it") <= 2, json.dumps([s, rec, faces]))
    # 5 with 2 aboard, right first time; the statuses: 7 with 3 not right first time (no day), 5 with 2 one day
    await st_wait(page, ["station-open"], 25)
    await st_bring(t, 3)
    await n_check(t)
    await st_wait(page, ["station-celebrate"], 5)
    days = await page.evaluate("(() => { const m = MW.stationFacts.statuses(MW.station.answers('aboard')); return [m['7:3'].days.length, m['7:3'].status, m['5:2'].days.length]; })()")
    check(f"station-wrong-aboard ({name}): a hinted fact isn't right first time (7 with 3 aboard: no day towards secure; 5 with 2: one)", days == [0, "practising", 1], json.dumps(days))
    check(f"station-wrong-aboard ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_wrong_more(p, name, vw, vh, dpr):
    """Step 2's wrong checks: a wrong number floats back and the berth is empty again; a tile let go elsewhere floats
    back; two wrong checks bring the hint (the windows past the whole shut, the empty ones counted on with ghosts, the
    berth's counting halo, board s2hint); the number still has to be dragged."""
    print(f"\n== MeeMee Station: step 2's wrong checks and the hint ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-wrong-more-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await st_open(t, page, "more", [{"whole": 7, "a": 3}, {"whole": 6, "a": 2}, {"whole": 9, "a": 5}, {"whole": 5, "a": 1}, {"whole": 3, "a": 2}])
    await n_quiet(t)
    await page.evaluate("window.__stq = performance.now()")
    berth = await st_berth(page)
    await t.drag(*tile_xy(5), *berth)
    s = await st_state(page)
    check(f"station-wrong-more ({name}): tile 5 on the berth docks there", s["placed"] == 5 and s["ready"], json.dumps(s))
    await n_check(t)
    s = await st_state(page)
    check(f"station-wrong-more ({name}): a wrong number: 'Let's try again.', the try-again face, the tile floats back and the berth is empty again",
          (await t.said())[-1:] == ["again-try-again"] and s["face"] == "try-again" and s["placed"] is None and s["out"] == [] and s["bars"][2] == [None, True, False, False, None]
          and s["tries"] == 1 and not s["hinted"] and not s["ready"], json.dumps(s))
    await asyncio.sleep(1.2)
    n0 = len(await t.said())
    # the sky, a window with a MeeMee in it, the station's truss, Scruffles
    for n, to in ((8, (900, 600)), (6, (260, 174)), (2, (170, 220)), (9, (1030, 300))):
        await t.drag(*tile_xy(n), *to)
    s = await st_state(page)
    check(f"station-wrong-more ({name}): tiles let go in the sky, on a window with a MeeMee in it, on the truss or on Scruffles float back to the track "
          f"(not a try, nothing said)",
          s["out"] == [] and s["placed"] is None and s["tries"] == 1 and (await t.said())[n0:] == [], json.dumps(s))
    got = []
    mods = await page.evaluate("(() => { const b = MW.station.bars(); return ['whole', 'left'].map(k => [b[k].x + b[k].w / 2, b[k].y + b[k].h / 2]); })()")
    win = await page.evaluate("(() => { const w = MW.station.windows()[7]; return [w.x, w.y]; })()")
    for what, to in (("the whole's hull module", mods[0]), ("the part's hull module", mods[1]), ("an empty window", win)):
        await t.drag(*tile_xy(4), *to)
        a = await st_state(page)
        tile = await page.evaluate("(() => { const t = MW.station.track().tile(4); return [t.x, t.y]; })()")
        await t.drag(*tile, 900, 600)
        b = await st_state(page)
        got.append([what, a["placed"], abs(tile[0] - berth[0]) < 0.6 and abs(tile[1] - berth[1]) < 0.6, b["placed"], b["out"]])
    check(f"station-wrong-more ({name}): a tile let go on the whole's or the part's hull module, or on an empty window, docks in the berth; taken back out, "
          f"it floats back and the berth is empty again",
          all(g[1] == 4 and g[2] and g[3] is None and g[4] == [] for g in got) and (await st_state(page))["tries"] == 1, json.dumps(got))
    # the second wrong number: the hint
    await t.drag(*tile_xy(2), *berth)
    await n_check(t)
    s = await st_state(page)
    said = await t.said()
    check(f"station-wrong-more ({name}): a second wrong number: 'Let's count on from… three. Four, five, six, seven.'; windows 8 to 10 shut, 4 to 7 lit "
          f"for counting (a ghost in each), the berth's counting halo",
          said[-1:] == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"] and s["hinted"] and s["tries"] == 2
          and s["windows"] == st_windows(3, 7, "hinting") and s["ghosts"] == 4 and s["bars"][2] == [None, True, False, True, None], json.dumps([said[-1:], s]))
    await th_until(page, "document.querySelectorAll('#screen-station-play .mw-ghost.is-lit').length >= 3", 8)
    await st_shot(page, name, "s2hint")
    await n_quiet(t)
    await asyncio.sleep(0.3)
    s = await st_state(page)
    check(f"station-wrong-more ({name}): ... the windows light as they are counted on, and stay lit until the number is dragged",
          s["lit"] == 4 and s["phase"] == "station-open" and s["placed"] is None and await page.evaluate(ST_FACES) == [], json.dumps(s))
    await t.drag(*tile_xy(4), *berth)
    await n_check(t)
    s = await st_state(page)
    rec = await page.evaluate("MW.station.answers('more').slice(-1)[0]")
    check(f"station-wrong-more ({name}): tile 4: right; the ghosts gone, the berth a hull module showing 4 (no halo now); saved with 2 wrong checks and the hint",
          s["phase"] == "station-celebrate" and s["ghosts"] == 0 and s["bars"][2] == [4, False, True, False, "4"] and rec["tries"] == 2 and rec["hint"] is True,
          json.dumps([s, rec]))
    check(f"station-wrong-more ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_wrong_numbers(p, name, vw, vh, dpr):
    """Step 3's hints, by where the berth is (board s3hint): a small station hangs under the modules; a part missing,
    the given part's MeeMee fill its first windows and the rest are counted on; the whole missing, both parts' MeeMee fill
    them and every one is counted. Hear-again cuts a hint short; the next wrong number gives it again in full; a right
    answer, and the small station fades away."""
    print(f"\n== MeeMee Station: step 3's wrong checks and the hints ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-wrong-numbers-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rnd = [{"whole": 10, "a": 6, "missing": "right"}, {"whole": 9, "a": 5, "missing": "whole"}, {"whole": 7, "a": 4, "missing": "left"},
           {"whole": 3, "a": 1, "missing": "right"}, {"whole": 4, "a": 2, "missing": "left"}]
    await st_open(t, page, "numbers", rnd)

    async def wrong(*tiles):
        for n in tiles:
            await n_quiet(t)
            await t.drag(*tile_xy(n), *(await st_berth(page)))
            await n_check(t)

    # 10 = 6 + ?: the small station; 6 MeeMee in its first windows; 7 to 10 counted on
    await wrong(2, 5)
    s = await st_state(page)
    check(f"station-wrong-numbers ({name}): 10 with 6 aboard, the rest missing, two wrong numbers: a small station under the modules, 6 MeeMee in its first "
          f"windows, 7 to 10 lit for counting; 'Let's count on from… six. Seven, eight, nine, ten.'; the berth's counting halo",
          s["hinted"] and s["hintStation"] and s["hintMimi"] == 6 and s["windows"] == st_windows(6, 10, "hinting") and s["ghosts"] == 4
          and s["bars"][2][3] and (await t.said())[-1:] == ["q-count-on-from num-end-6 num-mid-7 num-mid-8 num-mid-9 num-end-10"], json.dumps(s))
    await th_until(page, "document.querySelectorAll('#screen-station-play .mw-ghost.is-lit').length >= 2", 8)
    await st_shot(page, name, "s3hint")
    await t.tap(*HEAR)
    await asyncio.sleep(0.5)
    s = await st_state(page)
    check(f"station-wrong-numbers ({name}): Hear-again during the hint takes it away (the small station and its MeeMee gone, no ghosts, no halo); the question again",
          not s["hinted"] and not s["hintStation"] and s["hintMimi"] == 0 and s["ghosts"] == 0 and not s["bars"][2][3]
          and (await t.said())[-1:] == [st_prompt("numbers", rnd[0], 0)], json.dumps(s))
    await wrong(3)
    s = await st_state(page)
    check(f"station-wrong-numbers ({name}): the next wrong number gives the hint again in full", s["hinted"] and s["hintMimi"] == 6 and s["ghosts"] == 4 and s["tries"] == 3, json.dumps(s))
    await n_quiet(t)
    await t.drag(*tile_xy(4), *(await st_berth(page)))
    await n_check(t)
    s = await st_state(page)
    gone = await page.evaluate("[!!document.querySelector('#screen-station-play .station-hint.is-gone'), document.querySelectorAll('#screen-station-play .mw-counters .mw-mimi.is-rescued').length]")
    check(f"station-wrong-numbers ({name}): tile 4: right; the berth shows 4 with the success ring; the hint's small station and its MeeMee fade away",
          s["phase"] == "station-celebrate" and s["bars"][2] == [4, False, True, False, "4"] and gone == [True, 6], json.dumps([s, gone]))
    # 9 = 5 + 4, the whole missing: both parts' MeeMee in the small station, all counted
    await st_wait(page, ["station-open"], 25)
    hops0 = await page.evaluate("MW.events.filter(e => e.type === 'hint').length")
    await wrong(8, 7)
    s = await st_state(page)
    check(f"station-wrong-numbers ({name}): 5 and 4, the whole missing, two wrong numbers: both parts' MeeMee fill the small station's first 9 windows (the "
          f"tenth shut); 'Count them with me. One… nine.'; the whole's berth with the counting halo",
          s["hinted"] and s["hintMimi"] == 9 and s["windows"] == [""] * 9 + ["closed"] and s["ghosts"] == 0 and s["bars"][0][3]
          and (await t.said())[-1:] == ["again-count-with-me " + " ".join(f"num-mid-{i}" for i in range(1, 9)) + " num-end-9"]
          and await page.evaluate("MW.events.filter(e => e.type === 'hint').length") == hops0 + 1, json.dumps(s))
    await n_quiet(t)
    hopped = await page.evaluate("document.querySelectorAll('#screen-station-play .mw-counters .mw-mimi.is-hop').length")
    check(f"station-wrong-numbers ({name}): ... every MeeMee hops as it is counted", hopped == 9, str(hopped))
    await asyncio.sleep(0.3)
    await st_shot(page, name, "s3hint-whole")
    await t.drag(*tile_xy(9), *(await st_berth(page)))
    await n_check(t)
    check(f"station-wrong-numbers ({name}): tile 9 completes it", (await st_state(page))["phase"] == "station-celebrate")
    # ? + 3 = 7, the part aboard missing: the rest's 3 MeeMee, counted on from 3
    await st_wait(page, ["station-open"], 25)
    await n_quiet(t)
    check(f"station-wrong-numbers ({name}): 7 with the part aboard missing asked: 'Let's make… seven. We've got… three. How many more?'",
          (await t.said())[-1:] == [st_prompt("numbers", rnd[2], 2)], json.dumps((await t.said())[-1:]))
    await wrong(1, 2)
    s = await st_state(page)
    check(f"station-wrong-numbers ({name}): ... two wrong numbers: the rest's 3 MeeMee in the small station, 4 to 7 counted on from 3, the part's berth with its halo",
          s["hinted"] and s["hintMimi"] == 3 and s["windows"] == st_windows(3, 7, "hinting") and s["bars"][1][3]
          and (await t.said())[-1:] == ["q-count-on-from num-end-3 num-mid-4 num-mid-5 num-mid-6 num-end-7"], json.dumps(s))
    await n_quiet(t)
    await t.drag(*tile_xy(4), *(await st_berth(page)))
    await n_check(t)
    rec = await page.evaluate("MW.station.answers('numbers').slice(-1)[0]")
    check(f"station-wrong-numbers ({name}): tile 4: right; saved as 7 with 4 aboard, the berth in the part aboard's place, 2 wrong checks and the hint",
          (await st_state(page))["phase"] == "station-celebrate" and [rec["whole"], rec["a"], rec["missing"], rec["tries"], rec["hint"]] == [7, 4, "left", 2, True], json.dumps(rec))
    check(f"station-wrong-numbers ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_drag(p, name="fire", vw=1046, vh=653, dpr=1.22):
    """Step 1: a MeeMee let go anywhere on the station (its box, 40, 100 to 820, 500) goes into the next empty window, with
    the snap and a pop; just off it, it floats back; a newcomer can be picked up again (let go on the station it stays,
    off it, it goes back and the others close up); those already aboard can't be; a touch anywhere on the deck picks up
    the nearest. Steps 2 and 3: a tile on the berth docks there, taken out the berth is empty again, another replaces it.
    The new lines join once recorded and are left out while pending."""
    print(f"\n== MeeMee Station: dragging and dropping ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-drag-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await page.evaluate("MW.station.ask({ whole: 6, a: 2 }, 'aboard')")
    pops = "MW.events.filter(e => e.type === 'sfx' && e.detail === 'pop').length"
    got = []
    for i, pt in enumerate(((45, 105), (815, 105), (45, 495), (815, 495), (430, 150), (80, 300), (650, 430))):
        p0 = await page.evaluate(pops)
        await t.drag(*ST_ON_DECK, *pt)
        s = await st_state(page)
        got.append([pt, sorted(s["aboard"]) == list(range(2, 3 + i)), await page.evaluate(pops) - p0])
    check(f"station-drag ({name}): MeeMee let go anywhere on the station (its box's four corners, the tower, a wing, between windows) each go into the "
          f"next empty window in ten-frame order, with a pop",
          all(g[1] and g[2] == 1 for g in got) and await st_in_order(page), json.dumps(got))
    n0, said0 = await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'miss').length"), len(await t.said())
    for pt in ((34, 300), (826, 300), (430, 94), (430, 506)):
        await t.drag(*ST_ON_DECK, *pt)
    s = await st_state(page)
    check(f"station-drag ({name}): just off the station (6 px outside its box on each side) a MeeMee floats back to the deck (a miss, not a try, nothing said)",
          sorted(s["aboard"]) == list(range(2, 9)) and s["deck"] == 1 and await st_in_order(page) and s["tries"] == 0 and len(await t.said()) == said0
          and await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'miss').length") == n0 + 4, json.dumps(s))
    await t.drag(*ST_ON_DECK, *ST_ON_STATION)
    s = await st_state(page)
    check(f"station-drag ({name}): all ten windows are open: the last MeeMee fills the tenth (the child can bring too many)", sorted(s["aboard"]) == list(range(2, 10)) and s["deck"] == 0, json.dumps(s))
    await t.drag(*(await st_newcomer(page, 5)), 300, 200)
    s = await st_state(page)
    check(f"station-drag ({name}): a newcomer picked up from its window and let go on the station stays in its window", sorted(s["aboard"]) == list(range(2, 10)) and await st_in_order(page), json.dumps(s))
    home = await page.evaluate("(() => { const c = MW.station.st.counters.find(c => c.where === 'aboard' && c.win === 4); window.__out = c; return [c.home.x, c.home.y]; })()")
    await t.drag(*(await st_newcomer(page, 4)), 1000, 700)
    s = await st_state(page)
    back = await page.evaluate("[window.__out.where, Math.round(window.__out.x), Math.round(window.__out.y)]")
    check(f"station-drag ({name}): taken from the middle (window 5) and let go off the station, it goes back to its own place on the deck, and the ones after it close up",
          sorted(s["aboard"]) == list(range(2, 9)) and s["deck"] == 1 and back == ["deck", round(home[0]), round(home[1])] and await st_in_order(page), json.dumps([s, back]))
    await t.drag(212, 324, 1000, 700)                       # a MeeMee already aboard (window 1): not one to drag
    s = await st_state(page)
    check(f"station-drag ({name}): the MeeMee already aboard can't be picked up", s["fixed"] == 2 and sorted(s["aboard"]) == list(range(2, 9)) and s["deck"] == 1, json.dumps(s))
    # a touch anywhere on the deck (its empty right-hand end, by the commander) picks up the nearest waiting MeeMee
    await t.drag(1110, 730, *ST_ON_STATION)
    s = await st_state(page)
    check(f"station-drag ({name}): a touch anywhere on the deck picks up the waiting MeeMee nearest the finger", sorted(s["aboard"]) == list(range(2, 10)) and s["deck"] == 0, json.dumps(s))
    # taps on the deck (a child touching the MeeMee to count them) say nothing and log no miss
    await page.evaluate("MW.station.ask({ whole: 6, a: 2 }, 'aboard')")
    n0, said0 = await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'miss').length"), len(await t.said())
    for pt in ((772, 652), (852, 652), (812, 722), (1000, 700)):
        await t.tap(*pt)
        await asyncio.sleep(0.3)
    check(f"station-drag ({name}): taps on the deck say nothing, log no miss, and every MeeMee is back in its place",
          await page.evaluate("MW.events.filter(e => e.type === 'drop' && e.detail === 'miss').length") == n0 and len(await t.said()) == said0 and await st_in_order(page)
          and (await st_state(page))["deck"] == 8)

    # steps 2 and 3: the berth
    for step, q in (("more", {"whole": 7, "a": 3}), ("numbers", {"whole": 7, "a": 4, "missing": "left"}), ("numbers", {"whole": 9, "a": 5, "missing": "whole"}),
                    ("numbers", {"whole": 10, "a": 6, "missing": "right"})):
        await page.evaluate("(a) => MW.station.ask(a[0], a[1])", [q, step])
        await asyncio.sleep(0.4)
        qq = st_q(step, q)
        ans = st_answer(qq)
        berth = await st_berth(page)
        label = f"{step}, {st_text(qq)} with the berth in {qq['missing']}"
        await t.drag(*tile_xy(ans), *berth)
        a = await st_state(page)
        tile = await page.evaluate("(n => { const t = MW.station.track().tile(n); return [t.x, t.y]; })(%d)" % ans)
        await t.drag(*tile, 900, 600)
        b = await st_state(page)
        wrong_n = (ans + 1) % 11
        await t.drag(*tile_xy(wrong_n), *berth)
        await t.drag(*tile_xy(ans), berth[0] - 30, berth[1] + 20)
        c = await st_state(page)
        check(f"station-drag ({name}): {label}: a tile on the berth docks in its middle; taken out, it floats back and the berth is empty again; another "
              f"replaces the first, which floats back",
              a["placed"] == ans and abs(tile[0] - berth[0]) < 0.6 and abs(tile[1] - berth[1]) < 0.6 and b["placed"] is None and b["out"] == []
              and c["placed"] == ans and c["out"] == [ans], json.dumps([a["placed"], tile, berth, b["placed"], c["placed"], c["out"]]))
    # "Bring more MeeMee aboard.", "Find the number." and "All aboard!" join the first two questions and the praise once
    # they are recorded (stubbed); while they are pending they are left out, so nothing falls silent
    lines = await page.evaluate("""(() => { const R = MW.station, out = {}, three = ['station-bring-aboard', 'station-find-number', 'station-all-aboard'];
        const was = MW.audio.recorded;
        const look = () => [R.ask({ whole: 7, a: 3 }, 'aboard') && R.st.prompt.slice(-2), R.ask({ whole: 7, a: 3 }, 'more') && R.st.prompt.slice(-2),
                            R.ask({ whole: 7, a: 3, missing: 'whole' }, 'numbers') && R.st.prompt.slice(-2), R.praiseLines()];
        out.onPage = three.map(id => was(id));
        MW.audio.recorded = id => three.indexOf(id) < 0 && was(id);
        try { out.pending = look(); } finally { MW.audio.recorded = was; }
        MW.audio.recorded = id => three.indexOf(id) >= 0 || was(id);
        try { out.recorded = look(); } finally { MW.audio.recorded = was; }
        MW.world.home(); return out; })()""")
    praise = ["praise-found-it", "praise-thats-right", "praise-super-counting", "praise-well-done"]
    check(f"station-drag ({name}): while pending (as on this page: {lines['onPage']}; stubbed either way), 'Bring more MeeMee aboard.', 'Find the number.' "
          f"and 'All aboard!' are left out (so nothing falls silent)",
          lines["pending"] == [[["q-weve-got", "num-end-3"], ["tap-scruffles"]], [["q-how-many-more"], ["tap-scruffles"]], [["q-how-many-altogether"], ["tap-scruffles"]], praise],
          json.dumps(lines["pending"]))
    check(f"station-drag ({name}): once recorded (stubbed), they join: step 1's first questions end 'Bring more MeeMee aboard. Tap Scruffles…', steps 2 and 3's "
          f"'Find the number. Tap Scruffles…', and 'All aboard!' is one of the praise",
          lines["recorded"] == [[["station-bring-aboard"], ["tap-scruffles"]], [["station-find-number"], ["tap-scruffles"]], [["station-find-number"], ["tap-scruffles"]],
                                praise + ["station-all-aboard"]], json.dumps(lines["recorded"]))
    check(f"station-drag ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_questions(p):
    """Every question each step can ask is put on the screen and answered (a wrong one refused first): 45, 45 and 135.
    Rounds bring up every question; five each, one or two secure, at most two from one whole, never the same whole twice
    in a row; in step 3 the berth's place spread 2, 2 and 1 a round and about a third each; the wholes in play come up
    equally (no weighting). Writes notes/all-questions-station.md."""
    print("\n== MeeMee Station: every question ==")
    browser = await p.chromium.launch()
    ctx, page, problems = await seeded(browser, [])
    E = lambda js, arg=None: page.evaluate(js, arg)
    for step in ST_STEPS:
        qs = await E("(s) => MW.stationFacts.allQuestions(s, [2,3,4,5,6,7,8,9,10])", step)
        out = await E("""(a) => { const R = MW.station, out = [], step = a[0];
            a[1].forEach(q => { R.ask(q, step); const s = R.st, tr = R.track(), b = R.bars(), wh = document.querySelector('#screen-station-play .station-whole');
              const o = { q: q, prompt: s.prompt, fixed: s.fixed.length, deck: s.counters.filter(c => c.where === 'deck').length,
                          whole: wh ? wh.textContent : null, windows: R.windows().length,
                          bars: b ? ['whole', 'left', 'right'].map(k => b[k].value) : null, waiting: b ? ['whole', 'left', 'right'].filter(k => b[k].el.classList.contains('is-waiting')) : null };
              if (step === 'aboard') {
                R.podTap(); o.wrong = [s.tries, MW.world.st.phase];             // none brought: a wrong check
                s.talking = false;                                               // as once Scruffles is quiet
                s.counters.filter(m => m.where === 'deck').slice(0, q.whole - q.a).forEach(m => R.drop(m, 430, 300, false));
              } else {
                const m = s.berth, x = m.x + m.w / 2, y = m.y + m.h / 2;
                R.drop(tr.tile((s.answer + 1) % 11), x, y, false); R.podTap();
                o.wrong = [s.tries, s.placed, tr.tile((s.answer + 1) % 11).out()];
                s.talking = false;
                R.drop(tr.tile(s.answer), x, y, false);
              }
              R.podTap();
              const rec = R.answers(step).slice(-1)[0];
              o.right = [MW.world.st.phase, s.answer, step === 'aboard' ? s.counters.filter(c => c.where === 'aboard').length : s.berth.value,
                         step === 'aboard' ? null : s.berth.el.classList.contains('is-success')];
              o.rec = [rec.whole, rec.a, rec.missing];
              out.push(o); });
            MW.world.home(); return out; }""", [step, qs])
        bad = []
        for o in out:
            q = o["q"]
            ans = st_answer(q)
            p_ok = " ".join(" ".join(x) for x in o["prompt"]) == st_prompt(step, q, 0)
            if step == "aboard":
                look = o["whole"] == str(q["whole"]) and o["fixed"] == q["a"] and o["deck"] == 10 - q["a"] and o["windows"] == 10 and o["bars"] is None
                wrong = o["wrong"] == [1, "station-open"]
                right = o["right"] == ["station-celebrate", q["b"], q["b"], None]
            else:
                vals = [q["whole"], q["a"], q["b"]]
                vals[("whole", "left", "right").index(q["missing"])] = None
                look = o["bars"] == vals and o["waiting"] == [q["missing"]] and o["fixed"] == (q["a"] if step == "more" else 0) and o["whole"] is None \
                    and o["windows"] == (10 if step == "more" else 0)
                wrong = o["wrong"] == [1, None, False]
                right = o["right"] == ["station-celebrate", ans, ans, True]
            if not (p_ok and look and wrong and right and o["rec"] == [q["whole"], q["a"], q["missing"]]):
                bad.append(o)
        label = {"aboard": "step 1 (bring them aboard): 45", "more": "step 2 (how many more): 45", "numbers": "step 3 (numbers): 45 with the berth in each of its 3 places, 135"}[step]
        check(f"station-questions: every question of {label} on the screen as its step shows it, asked in its words, answered (a wrong check refused first)",
              len(out) == {"aboard": 45, "more": 45, "numbers": 135}[step] and not bad, json.dumps(bad[:2]))

    # rounds: every question comes up (every berth place in step 3)
    rounds = """(a) => { const out = []; for (let i = 0; i < a.n; i++) out.push(MW.stationFacts.pickRound({ step: a.step, wholes: a.wholes || [2,3,4,5,6,7,8,9,10],
        answers: a.answers || [], size: 5, turn: i * 5 })); return out; }"""
    seen = {}
    for step in ST_STEPS:
        rs = await E(rounds, {"step": step, "n": 3000})
        qs = [q for r in rs for q in r]
        seen[step] = (rs, qs)
        keys = {(q["whole"], q["a"], q["missing"]) for q in qs}
        want = 135 if step == "numbers" else 45
        check(f"station-questions: {step} rounds bring up every question ({want}), no zero facts",
              len(keys) == want and all(1 <= q["a"] < q["whole"] and q["b"] == q["whole"] - q["a"] for q in qs), str(len(keys)))
        check(f"station-questions: {step}: every round has five, at most two from one whole, never the same whole twice in a row",
              all(len(r) == 5 and max(sum(1 for q in r if q["whole"] == w) for w in range(2, 11)) <= 2 and all(r[i]["whole"] != r[i - 1]["whole"] for i in range(1, 5)) for r in rs))
    rs, qs = seen["numbers"]
    spread = [sorted(sum(1 for q in r if q["missing"] == m) for m in ("whole", "left", "right")) for r in rs]
    share = {m: sum(1 for q in qs if q["missing"] == m) / len(qs) for m in ("whole", "left", "right")}
    check("station-questions: step 3 spreads the berth's place: 2, 2 and 1 in every round, and about a third each across rounds",
          all(x == [1, 2, 2] for x in spread) and all(abs(v - 1 / 3) < 0.01 for v in share.values()), json.dumps(share))
    rs, qs = seen["aboard"]
    per = {w: sum(1 for q in qs if q["whole"] == w) / len(qs) for w in range(2, 11)}
    check("station-questions: the wholes in play come up equally (no weighting): each of 2 to 10 in about a ninth of the questions (whole 2's one fact as "
          "often as whole 10's nine together)", all(abs(v - 1 / 9) < 0.02 for v in per.values()), json.dumps({k: round(v, 3) for k, v in per.items()}))
    # one or two secure facts a round once some are secure: 7's six facts secure in step 1
    sec = [{"t": T0 + d * DAY + i * 1000, "whole": 7, "a": a, "missing": "right", "tries": 0, "misses": 0, "hint": False} for d in range(3) for i, a in enumerate(range(1, 7))]
    rs = await E(rounds, {"step": "aboard", "n": 400, "answers": sec})
    counts = sorted({sum(1 for q in r if q["status"] == "secure") for r in rs})
    check("station-questions: with some facts secure, every round has one or two of them, the rest practising or not met", counts == [1, 2], str(counts))
    few = await E(rounds, {"step": "aboard", "n": 200, "wholes": [3, 5]})
    check("station-questions: only the wholes in play (3 and 5) come up", {q["whole"] for r in few for q in r} == {3, 5})
    small = await E("() => MW.stationFacts.pickRound({ step: 'more', wholes: [2], answers: [], size: 5 })")
    check("station-questions: only 2 in play still makes a round (1 + 1 five times)", len(small) == 5 and all(q["whole"] == 2 and q["a"] == 1 for q in small), json.dumps(small))

    # notes/all-questions-station.md
    allq = {step: await E("(s) => MW.stationFacts.allQuestions(s, [2,3,4,5,6,7,8,9,10])", step) for step in ST_STEPS}

    def words(step, q):
        if step == "numbers" and q["missing"] == "whole":
            return f"We've got… {TH_N[q['a']]}… and {TH_N[q['b']]}. How many altogether?"
        given = q["b"] if step == "numbers" and q["missing"] == "left" else q["a"]
        return f"Let's make… {TH_N[q['whole']]}. We've got… {TH_N[given]}." + (" How many more?" if step != "aboard" else "")
    lines = ["# Every question MeeMee Station can ask", "",
             "Made by tools/tests/test_game.py from the game's own list (MW.stationFacts.allQuestions); don't edit it by hand.",
             "Step 1 (bring them aboard): the whole is on the station's tower and the MeeMee already aboard are in the first windows; the",
             "child brings the rest from the deck, then taps Scruffles. Step 2 (how many more): the child drags a number tile into the",
             "empty berth of the bar model. Step 3 (numbers): the bar model alone, the empty berth in any of its three places. The first",
             "two questions of a round also say \"Bring more MeeMee aboard.\" (step 1) or \"Find the number.\" (steps 2 and 3), and \"Tap",
             "Scruffles when you're ready.\" Every right answer is said as MeeMee Rescue's sentence: \"Three and four make seven.\"", ""]
    for step, title in (("aboard", "Step 1: Bring them aboard"), ("more", "Step 2: How many more"), ("numbers", "Step 3: Numbers")):
        lines += [f"## {title} ({len(allq[step])} questions)", ""]
        if step == "aboard":
            lines += ["| Whole | Already aboard | MeeMee to bring | Number sentence, once right | What Scruffles says |", "|---|---|---|---|---|"]
            lines += [f"| {q['whole']} | {q['a']} | {q['b']} | {st_text(q)} | {words(step, q)} |" for q in allq[step]]
        else:
            lines += ["| Whole | Bar model (? is the berth) | Answer | What Scruffles says |", "|---|---|---|---|"]
            for q in allq[step]:
                v = [str(q["whole"]), str(q["a"]), str(q["b"])]
                v[("whole", "left", "right").index(q["missing"])] = "?"
                lines.append(f"| {q['whole']} | {v[0]} = {v[1]} + {v[2]} | {st_answer(q)} | {words(step, q)} |")
        lines.append("")
    (ROOT / "notes" / "all-questions-station.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"   wrote notes/all-questions-station.md ({', '.join(f'{s}: {len(allq[s])}' for s in ST_STEPS)})")
    check("station-questions: the list has 45, 45 and 135 questions", [len(allq[s]) for s in ST_STEPS] == [45, 45, 135])
    check("station-questions: no console errors", not problems, "; ".join(problems[:3]))
    await ctx.close()
    await browser.close()


ST_ANSWER = """(a) => { const R = MW.station; R.ask(a.q, a.step); const s = R.st, tr = R.track();
    if (a.step === 'aboard') {
      if (a.wrong) R.podTap();                                // none brought: a wrong check
      s.counters.filter(m => m.where === 'deck').slice(0, a.q.whole - a.q.a).forEach(m => R.drop(m, 430, 300, false));
    } else {
      const m = s.berth, x = m.x + m.w / 2, y = m.y + m.h / 2;
      if (a.wrong) { R.drop(tr.tile((s.answer + 1) % 11), x, y, false); R.podTap(); }
      R.drop(tr.tile(s.answer), x, y, false);
    }
    s.talking = false;                                       // as once Scruffles is quiet: a tap while he answers does nothing
    R.podTap(); const out = MW.world.st.phase; MW.world.home(); return out; }"""
ST_STATUS = "(a) => { const m = MW.stationFacts.statuses(MW.station.answers(a[0])); const s = m[a[1]]; return s ? s.status : 'notyet'; }"


async def test_station_progress(p):
    """Secure: right first time on three different days (the date faked in the page); a wrong answer moves a fact back to
    practising. Each step keeps its own records; in step 3 a fact counts whichever place its berth was in. MeeMee
    Rescue's progress is untouched by this game, and this game's by MeeMee Rescue."""
    print("\n== MeeMee Station: progress ==")
    browser = await p.chromium.launch()
    rescue = secure_answers([(7, 3)]) + [ans(T0 + DAY, 5, 1, first=False)]
    ctx, page, problems = await seeded(browser, rescue)
    E = lambda js, arg=None: page.evaluate(js, arg)
    await E("window.__now = %d; Date.now = () => window.__now" % T0)
    got = []
    for d in range(3):
        await E("window.__now = %d" % (T0 + d * DAY + 3600_000))
        got.append(await E(ST_ANSWER, {"q": {"whole": 7, "a": 3}, "step": "aboard"}))
        got.append(await E(ST_STATUS, ["aboard", "7:3"]))
    check("station-progress: 7 with 3 aboard right first time on three different days (step 1): practising, practising, then secure",
          got == ["station-celebrate", "practising", "station-celebrate", "practising", "station-celebrate", "secure"], json.dumps(got))
    for i in range(3):
        await E("window.__now = %d" % (T0 + i * 60_000))
        await E(ST_ANSWER, {"q": {"whole": 8, "a": 2}, "step": "aboard"})
    check("station-progress: three times right on one day is still practising", await E(ST_STATUS, ["aboard", "8:2"]) == "practising")
    await E("window.__now = %d" % (T0 + 3 * DAY))
    await E(ST_ANSWER, {"q": {"whole": 7, "a": 3}, "step": "aboard", "wrong": True})
    check("station-progress: a wrong answer moves 7 with 3 aboard back to practising", await E(ST_STATUS, ["aboard", "7:3"]) == "practising")
    check("station-progress: 7 with 4 aboard (4 + 3) is a fact of its own (not yet), not 3 + 4", await E(ST_STATUS, ["aboard", "7:4"]) == "notyet")
    sep = await E("[MW.station.answers('more').length, MW.station.answers('numbers').length, MW.station.answers('aboard').length]")
    check("station-progress: each step keeps its own records: step 1's answers are in step 1's only", sep == [0, 0, 7], str(sep))
    for d, gap in enumerate(("right", "whole", "left")):
        await E("window.__now = %d" % (T0 + (5 + d) * DAY))
        await E(ST_ANSWER, {"q": {"whole": 7, "a": 3, "missing": gap}, "step": "numbers"})
    check("station-progress: in step 3, 7 with 3 aboard right first time on three days with its berth in a different place each day is secure",
          await E(ST_STATUS, ["numbers", "7:3"]) == "secure" and await E(ST_STATUS, ["aboard", "7:3"]) == "practising" and await E(ST_STATUS, ["more", "7:3"]) == "notyet")
    for d in range(3):
        await E("window.__now = %d" % (T0 + (9 + d) * DAY))
        await E(ST_ANSWER, {"q": {"whole": 6, "a": 1}, "step": "more"})
    check("station-progress: step 2 counts the same way, on its own", await E(ST_STATUS, ["more", "6:1"]) == "secure" and await E(ST_STATUS, ["aboard", "6:1"]) == "notyet")
    saved = await E("JSON.parse(localStorage.getItem('mimi-world'))")
    stn = saved["games"]["station"]
    check("station-progress: saved on the tablet in this game's own record, one list per step; MeeMee Rescue's answers untouched",
          sorted(stn["answers"]) == ["aboard", "more", "numbers"] and saved["answers"] == rescue and "takehome" not in saved["games"], json.dumps(sorted(stn)))
    before = json.dumps(stn, sort_keys=True)
    await E("""(() => { MW.store.setting('answerMode', 'numbers'); MW.store.setting('check', 'auto'); MW.rescue.ask({ whole: 5, left: 2, right: 3, missing: 'right' });
        MW.rescue.drop(MW.rescue.track().tile(3), 550, 470, false); MW.world.home(); })()""")
    saved = await E("JSON.parse(localStorage.getItem('mimi-world'))")
    check("station-progress: a MeeMee Rescue answer is saved with MeeMee Rescue's, and this game's progress is as it was",
          len(saved["answers"]) == len(rescue) + 1 and json.dumps(saved["games"]["station"], sort_keys=True) == before, str(len(saved["answers"])))
    # MeeMee Rescue's Clear (its Progress tab) leaves this game's progress alone
    await E("MW.grownups.openPanel(); MW.grownups.show('progress')")
    await asyncio.sleep(0.3)
    await page.click("text=Clear this tablet's progress")
    await page.click("text=Tap again to clear")
    await asyncio.sleep(0.3)
    after = await E("[MW.store.get('answers').length, MW.store.peek('station')]")
    await E("MW.grownups.close()")
    check("station-progress: MeeMee Rescue's 'Clear this tablet's progress' clears its answers only; this game's progress stays as it was",
          after[0] == 0 and json.dumps(after[1], sort_keys=True) == before, str(after[0]))
    # a tablet that has never played this game keeps nothing for it (reading its tab doesn't create it)
    ctx2, page2, problems2 = await seeded(browser, rescue)
    await page2.evaluate("MW.grownups.openPanel(); MW.grownups.show('station-tab')")
    await asyncio.sleep(0.3)
    kept = await page2.evaluate("(() => { MW.store.save(); return JSON.parse(localStorage.getItem('mimi-world')).games; })()")
    check("station-progress: opening the Station tab on a tablet that has never played keeps nothing for the game", "station" not in kept, json.dumps(kept))
    check("station-progress: no console errors", not (problems or problems2), "; ".join((problems + problems2)[:3]))
    await ctx2.close()
    await ctx.close()
    await browser.close()


ST_TAB = """(() => { const b = document.querySelector('.gu-body'), g = {};
    b.querySelectorAll('.gu-grid .mw-cell').forEach(c => { g[c.textContent.trim()] = c.className.split(' ').find(x => x.startsWith('is-')); });
    return { tabs: Array.from(document.querySelectorAll('.gu-tab')).map(x => x.textContent), on: (document.querySelector('.gu-tab.is-on') || {}).textContent,
             h3: Array.from(b.querySelectorAll('.gu-h3')).map(h => h.textContent),
             steps: Array.from(b.querySelectorAll('[data-step]')).map(x => [x.textContent, x.classList.contains('is-on')]),
             views: Array.from(b.querySelectorAll('[data-view]')).map(x => [x.textContent, x.classList.contains('is-on')]),
             wholes: Array.from(b.querySelectorAll('.station-whole-chip')).map(x => [x.textContent, x.classList.contains('is-on')]),
             paras: Array.from(b.querySelectorAll('.gu-p')).map(x => x.textContent), lead: (b.querySelector('.gu-lead') || {}).textContent,
             cells: Object.keys(g).length, rows: Array.from(b.querySelectorAll('.gu-grid-row')).map(r => r.querySelectorAll('.mw-cell').length), g: g,
             legend: Array.from(b.querySelectorAll('.gu-legend .mw-cell')).map(c => c.textContent.trim()),
             clear: Array.from(b.querySelectorAll('.gu-btn')).filter(x => /clear/i.test(x.textContent)).map(x => x.textContent) }; })()"""
ST_EXAMPLE = [(2, 1), (3, 2), (4, 1), (4, 2), (5, 1), (5, 2), (10, 5), (10, 9)]                       # the board's secure facts
ST_PRACTISING = [(3, 1), (5, 3), (6, 3), (7, 2), (7, 6), (8, 4)]
ALL_TABS = ["Progress", "Settings", "Words", "Subtraction", "Station", "Checks", "Sound"]


async def test_station_grownups(p, name, vw, vh, dpr):
    """The game's grown-ups tab, Station (boards round14-grownups-tab and -grid): which step (a change starts with the
    next round), wholes in play (they limit the questions), the grid for the step picked ("3 + 4" cells, 45), and
    clearing this game's progress only."""
    print(f"\n== MeeMee Station: the Station tab ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-gu-{name}", vw, vh, dpr, mode=None)
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    more = [{"t": T0 + d * DAY + i * 1000, "whole": w, "a": a, "missing": "right", "tries": 0, "misses": 0, "hint": False}
            for d in range(3) for i, (w, a) in enumerate(ST_EXAMPLE)]
    more += [{"t": T0 + 4 * DAY + i * 1000, "whole": w, "a": a, "missing": "right", "tries": 1, "misses": 0, "hint": False} for i, (w, a) in enumerate(ST_PRACTISING)]
    await page.evaluate("""(a) => { const g = MW.store.game('station'); g.answers = { more: a }; g.step = 'more'; MW.store.save();
        MW.store.get('answers').push({ t: 1, whole: 7, left: 3, right: 4, missing: 'right', tries: 0, misses: 0, hint: false, check: 'tap' });
        MW.store.game('takehome').answers = { take: [{ t: 1, whole: 7, take: 4, missing: 'right', tries: 0, misses: 0, hint: false }] }; MW.store.save(); }""", more)
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('station-tab')")
    await asyncio.sleep(0.4)
    tab = await page.evaluate(ST_TAB)
    check(f"station-gu ({name}): the tab 'Station' sits after Take MeeMee Home's Subtraction, before Checks and Sound", tab["tabs"] == ALL_TABS and tab["on"] == "Station", json.dumps(tab["tabs"]))
    check(f"station-gu ({name}): in order: Which step (How many more on, as saved), Wholes in play (2 to 10, all on), Showing progress for (How many more)",
          tab["h3"] == ["Which step", "Wholes in play", "Showing progress for"] and tab["steps"] == [["Bring them aboard", False], ["How many more", True], ["Numbers", False]]
          and tab["wholes"] == [[str(w), True] for w in range(2, 11)] and tab["views"] == [["Bring them aboard", False], ["How many more", True], ["Numbers", False]],
          json.dumps([tab["h3"], tab["steps"], tab["views"]]))
    want = ["Bring them aboard (the first step): the whole shows on the station's tower and some MeeMee are already in its ten windows. Your child drags MeeMee in from the deck until the station holds the whole, then taps Scruffles. All ten windows are open, so they have to stop at the right number.",
            "How many more: the ten frame shows the part already aboard, and the bar model under it shows the whole and that part. Your child drags a number tile into the empty part of the bar. Two wrong tries: the windows past the whole close, and the empty ones are counted together.",
            "Numbers: the bar model alone, and the empty space can be a part or the whole.",
            "A change starts with the next round. Each step keeps its own progress, separate from MeeMee Rescue's."]
    check(f"station-gu ({name}): the three explanations and the note, as round 14's board words them (British English, no exclamation marks)",
          tab["paras"][:4] == want and not any("!" in x for x in tab["paras"]), json.dumps(tab["paras"][:4]))
    check(f"station-gu ({name}): under Wholes in play, MeeMee Rescue's note", "Questions use only the wholes switched on. Changes start with the next round." in tab["paras"], json.dumps(tab["paras"]))
    check(f"station-gu ({name}): the summary: 'Secure: 8 of 45 facts. Practising: 6. Questions answered this step on this tablet: 30.'",
          tab["lead"] == "Secure: 8 of 45 facts. Practising: 6. Questions answered this step on this tablet: 30.", tab["lead"])
    check(f"station-gu ({name}): the grid: a row per whole (2 to 10), a cell per fact written 'part aboard + part to find', 45 in all; 2 + 3 secure, 3 + 3 practising, "
          f"3 + 4 not yet; the legend; the note",
          tab["rows"] == list(range(1, 10)) and tab["cells"] == 45 and tab["g"].get("2 + 3") == "is-secure" and tab["g"].get("3 + 3") == "is-practising"
          and tab["g"].get("3 + 4") == "is-notyet" and tab["g"].get("1 + 2") == "is-practising" and tab["legend"] == ["Secure", "Practising", "Not yet"]
          and tab["paras"][-1].startswith("Secure means right first time"), json.dumps(tab["g"]))
    await st_shot(page, name, "grownups-tab")
    await page.evaluate("(() => { const h = Array.from(document.querySelectorAll('.gu-body .gu-h3')).find(x => x.textContent === 'Showing progress for'); const b = document.querySelector('.gu-body');"
                        " b.scrollTop += (h.getBoundingClientRect().top - b.getBoundingClientRect().top) / MW.stage.scale + 50; })()")
    await asyncio.sleep(0.3)
    await st_shot(page, name, "grownups-grid")
    await page.click(".gu-body [data-view=numbers]")
    await asyncio.sleep(0.3)
    tab = await page.evaluate(ST_TAB)
    wide = await page.evaluate("(() => { const g = document.querySelector('.gu-grid'); const b = g.closest('.gu-body'); return [g.scrollWidth, b.clientWidth]; })()")
    check(f"station-gu ({name}): 'Numbers' shows step 3's grid: 45 cells, nothing answered yet (each step its own progress)",
          tab["views"] == [["Bring them aboard", False], ["How many more", False], ["Numbers", True]] and tab["cells"] == 45 and tab["rows"] == list(range(1, 10))
          and tab["lead"] == "No questions answered this step on this tablet yet." and tab["steps"][1][1] and wide[0] <= wide[1], json.dumps([tab["rows"], wide]))
    await page.evaluate("MW.grownups.close()")
    # a change of step starts with the next round
    await page.evaluate("(() => { const g = MW.store.game('station'); g.step = 'aboard'; MW.store.save(); })()")
    s = await st_open(t, page, None, [{"whole": 7, "a": 3}] * 5)
    await t.tap(46, 754, 3.3)                                # the grown-ups lock
    await page.evaluate("MW.grownups.show('station-tab')")
    await asyncio.sleep(0.3)
    await page.click(".gu-body [data-step=numbers]")
    await asyncio.sleep(0.2)
    tab = await page.evaluate(ST_TAB)
    saved = await page.evaluate("MW.store.peek('station').step")
    check(f"station-gu ({name}): 'Numbers' picked: saved, on, and the progress below shows its grid",
          saved == "numbers" and tab["steps"][2][1] and tab["views"][2][1] and tab["cells"] == 45, json.dumps([saved, tab["steps"], tab["views"]]))
    await page.click(".gu-close")
    await asyncio.sleep(0.6)
    s = await st_state(page)
    check(f"station-gu ({name}): ... but the round being played carries on bringing them aboard", s["step"] == "aboard" and s["deck"] == 7 and not s["track"], json.dumps(s))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    s = await st_open(t, page, None, [{"whole": 7, "a": 3, "missing": "whole"}] * 5)
    check(f"station-gu ({name}): the next round is Numbers", s["step"] == "numbers" and s["track"] and s["bars"][0][1], json.dumps(s))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    # wholes in play limit the questions
    await page.evaluate("MW.grownups.openPanel(); MW.grownups.show('station-tab')")
    await asyncio.sleep(0.3)
    for w in (2, 4, 6, 7, 8, 9, 10):
        await page.click(f".gu-body .station-whole-chip:nth-child({w - 1})")
        await asyncio.sleep(0.05)
    tab = await page.evaluate(ST_TAB)
    on = [int(x[0]) for x in tab["wholes"] if x[1]]
    rounds = await page.evaluate("(() => { const out = new Set(); for (let i = 0; i < 300; i++) MW.station.makeRound().forEach(q => out.add(q.whole)); return Array.from(out).sort(); })()")
    check(f"station-gu ({name}): with only 3 and 5 in play, rounds use only 3 and 5", on == [3, 5] and await page.evaluate("MW.store.peek('station').wholes") == [3, 5]
          and rounds == [3, 5], json.dumps([on, rounds]))
    await page.click(".gu-body .station-whole-chip:nth-child(2)")
    await page.click(".gu-body .station-whole-chip:nth-child(4)")
    await asyncio.sleep(0.1)
    check(f"station-gu ({name}): the last whole in play can't be turned off", await page.evaluate("MW.store.peek('station').wholes") == [5])
    # clearing clears this game's progress only (its step and wholes stay; MeeMee Rescue's and Take MeeMee Home's answers stay)
    await page.click(".gu-body .station-clear")
    await asyncio.sleep(0.1)
    first = await page.evaluate("[document.querySelector('.gu-body .station-clear').textContent, MW.station.answers('more').length]")
    await page.click(".gu-body .station-clear")
    await asyncio.sleep(0.2)
    after = await page.evaluate("""(() => { const s = JSON.parse(localStorage.getItem('mimi-world')); return [s.games.station, s.answers.length, s.games.takehome.answers.take.length,
        document.querySelector('.gu-body .gu-lead').textContent]; })()""")
    check(f"station-gu ({name}): 'Clear this tablet's progress' asks first ('Tap again to clear'), then clears this game's answers only",
          first == ["Tap again to clear", 30] and after[0] == {"step": "numbers", "wholes": [5]} and after[1] == 1 and after[2] == 1
          and after[3] == "No questions answered this step on this tablet yet.", json.dumps([first, after]))
    await page.evaluate("MW.grownups.close()")
    check(f"station-gu ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# as while "MeeMee Station!" is recorded: MW.audio.recorded stubbed (UNSTUB_PLACE_LINE undoes it); it is pending today
STUB_ST_NAME = """(() => { if (!window.__recorded) window.__recorded = MW.audio.recorded;
    MW.audio.recorded = id => id === 'station-name' || window.__recorded(id); })()"""


async def test_station_map(p, name, vw, vh, dpr):
    """0.9.0: place 4, the redrawn station (SolarMap card; board round14-map), is MeeMee Station's: lit at full colour
    with its halo and its badge at 944, 56, no lock; tapping it (or its badge) opens the game, with its title banner
    while "MeeMee Station!" is said once that is recorded (board round13-banner; stubbed here), straight away with no
    banner while it is pending (as today). The rocks (3) stay locked and say their line; the other games open as before.
    The station is drawn at 1.11, 6 px lower, its tap area 240."""
    print(f"\n== 0.9.0: MeeMee Station on the map ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-{name}", vw, vh, dpr, mode="tap")
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await asyncio.sleep(1.0)
    await screenshot(page, f"0.9.0/{name}-map.png")
    await st_shot(page, name, "map")
    lay = await page.evaluate("MW.LAYOUT.map.planets[4]")
    check(f"station ({name}): place 4 stays at 860, 182 with its 240 tap area; its badge's place is 944, 56 and its lock 966, 96",
          lay == {"x": 860, "y": 182, "tap": 240, "badge": {"x": 944, "y": 56, "d": 84, "pic": 56}, "lock": {"x": 966, "y": 96, "d": 56, "icon": 28}}, json.dumps(lay))
    info = await page.evaluate(PLACES_INFO)
    games = await page.evaluate("MW.world.games.map(g => g.planet)")
    check(f"station ({name}): five places: the four games' places lit (MeeMee Station on the station, 4), the rocks locked", len(info) == 5 and sorted(games) == [0, 1, 2, 4]
          and all(info[i]["game"] for i in (0, 1, 2, 4)) and place_ok(info[4], "MeeMee Station") and place_ok(info[3], None), json.dumps([info[3], info[4]]))
    badge = await page.evaluate("""(() => { const L = MW.LAYOUT.map.planets[4]; const b = Array.from(document.querySelectorAll('#screen-map .mw-planet-badge')).find(e => e.offsetLeft === L.badge.x && e.offsetTop === L.badge.y);
        const lock = Array.from(document.querySelectorAll('#screen-map .mw-planet-lock')).some(e => e.offsetLeft === L.lock.x && e.offsetTop === L.lock.y);
        return b ? [b.offsetLeft, b.offsetTop, b.offsetWidth, !!b.querySelector('clipPath[id^="station-badge-c"]'), b.getAttribute('aria-label'), lock] : null; })()""")
    check(f"station ({name}): its badge (the station in a round night window) at 944, 56, 84 across; no lock", badge == [944, 56, 84, True, "MeeMee Station", False], json.dumps(badge))
    drawn = await page.evaluate(STATION_DRAWN)
    check(f"station ({name}): the station is drawn as MeeMee Station, small (1.11), 6 px lower, at full colour (not dimmed): the truss, a wing at each end, "
          f"ten modules joined by mint collars, three windows lit, the tower with its round screen, and the dish",
          drawn == {"transform": "translate(860 188) scale(1.11)", "dimmed": False, "modules": 10, "lit": 3, "dark": 7, "wings": 4, "collars": 8, "truss": 1, "tower": 1, "dish": 1},
          json.dumps(drawn))
    reach = await page.evaluate(REACH_JS, [4])
    check(f"station ({name}): a tap anywhere on the station's drawing lands on place 4 or its badge", all(reach_ok(r) for r in reach), json.dumps(reach))
    locked = await page.evaluate(MAP_LOCKED_LINE)
    pl3 = await page.evaluate("MW.LAYOUT.map.planets[3]")
    said, screen = await tap_said(t, pl3["x"], pl3["y"])
    check(f"station ({name}): the rocks (3), still to come, say the locked line ({locked}) and stay on the map", said == [locked] and screen == "screen-map", json.dumps([said, screen]))
    await asyncio.sleep(1.2)
    # its name is pending (today): tapping place 4 opens the game straight away, no banner (and nothing silent: no title to read)
    rec = await page.evaluate("MW.audio.recorded('station-name')")
    await st_set(page, "aboard", [{"whole": 7, "a": 3}] * 5)
    await page.evaluate("window.__stq = performance.now()")
    if not rec:
        await t.tap(860, 182)
        ok = await t.wait_screen("screen-station-play", 3)
        check(f"station ({name}): with 'MeeMee Station!' pending (as today), tapping the station opens the game straight away, no banner",
              ok and not await page.evaluate("MW.world.banner.up()")
              and await page.evaluate("MW.events.some(e => e.type === 'banner' && e.detail === 'none for MeeMee Station (station-name not recorded yet)')"))
        await t.tap(*HOME_BTN)
        await t.wait_screen("screen-map", 5)
        await asyncio.sleep(0.5)
    # recorded (stubbed): its title banner, 'MeeMee Station' and its badge at 112, while the name is said; then the game
    await page.evaluate(STUB_ST_NAME)
    try:
        await st_set(page, "aboard", [{"whole": 7, "a": 3}] * 5)
        n0 = len(await t.said())
        await t.tap(860, 182)
        up = await th_until(page, "MW.world.banner.up() && document.getElementById('banner').classList.contains('is-in')", 5)
        await asyncio.sleep(0.4)
        bi = await page.evaluate(BANNER_INFO)
        size = await page.evaluate("(() => { const a = document.querySelector('#banner [data-art] svg'); return a ? [a.getAttribute('width'), a.getAttribute('height')] : null; })()")
        await st_shot(page, name, "banner")
        check(f"station ({name}): with 'MeeMee Station!' recorded (stubbed), tapping the station shows its title banner, 'MeeMee Station' and its badge at 112, while its name is said",
              up and bi == {"up": True, "name": "MeeMee Station", "art": ["station-badge"], "phase": "opening", "screen": "screen-map"} and size == ["112", "112"]
              and (await t.said())[n0:][:1] == ["station-name"], json.dumps([bi, size, (await t.said())[n0:]]))
        ok = await t.wait_screen("screen-station-play", 10)
        gone = await page.evaluate("(() => { const g = MW.events.filter(e => e.type === 'banner' && e.detail === 'gone MeeMee Station').pop(), "
                                   "r = MW.events.filter(e => e.type === 'round').pop(); return !!(g && r && g.t <= r.t); })()")
        check(f"station ({name}): ... and the game starts once the banner has gone", ok and gone)
        await t.tap(*HOME_BTN)
        await t.wait_screen("screen-map", 5)
        await asyncio.sleep(0.5)
        b = await page.evaluate("MW.LAYOUT.map.planets[4].badge")
        await t.tap(b["x"] + b["d"] / 2, b["y"] + b["d"] / 2)
        check(f"station ({name}): its badge opens it too (with its banner)", await th_until(page, "MW.world.banner.up()", 5) and await t.wait_screen("screen-station-play", 10))
        await t.tap(*HOME_BTN)
        await t.wait_screen("screen-map", 5)
        await asyncio.sleep(0.5)
    finally:
        await page.evaluate(UNSTUB_PLACE_LINE)
    opened = []
    for gid, screen, words in (("rescue", "screen-game", "map-mimi-rescue"), ("words", "screen-words-find", "words-name"), ("takehome", "screen-takehome-play", "takehome-name")):
        pl = await page.evaluate("MW.LAYOUT.map.planets[MW.world.games.find(g => g.id === '%s').planet]" % gid)
        if gid == "rescue":
            await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
        await t.tap(pl["x"], pl["y"])
        ok = await t.wait_screen(screen, 8)
        opened.append([gid, ok, words in await t.said()])
        await t.tap(*HOME_BTN)
        await t.wait_screen("screen-map", 5)
        await asyncio.sleep(0.5)
    check(f"station ({name}): MeeMee Rescue, MeeMee Rockets and Take MeeMee Home open as before (each its name and banner, then its screen)",
          all(o[1] and o[2] for o in opened), json.dumps(opened))
    check(f"station ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_commander(p, name, vw, vh, dpr, reduce=False):
    """The commander (round 15; Crew card): whoever has the job stands on the deck in step 1 (1146, 598, 108 wide) and at
    the track's right-hand end in steps 2 and 3 (1110, 498, 124 wide), wearing its badge. On each right answer it blinks,
    then smiles: got it 150 ms, usual 150 ms, then got it until the sentence has been said, then usual (its face log and
    data-face). Never during a wrong try or a hint. Nothing moves, so reduce motion changes nothing. With no commander,
    nobody stands there and the game plays the same."""
    label = f"station-commander ({name}{', reduce motion' if reduce else ''})"
    print(f"\n== MeeMee Station: the commander ({name}{', reduce motion' if reduce else ''}) ==")
    browser, ctx, page, t, problems = await open_motion(p, vw, vh, dpr, reduce, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'commander'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(*PLAY)
    await t.wait_screen("screen-map")
    await page.evaluate("MW.station.ask({ whole: 6, a: 2 }, 'aboard')")
    s = await st_state(page)
    check(f"{label}: step 1: the commander (Snuffles here) stands on the deck, its feet on it (1146, 598, 108 wide), wearing the commander's badge, its usual face",
          s["commander"] == ["snuffles", "usual", "commander", 1146, 598, 108], json.dumps(s["commander"]))
    # a wrong check and the hint: no smile
    await page.evaluate("window.__stq = performance.now(); MW.station.podTap()")
    await n_quiet(t)
    await page.evaluate("MW.station.podTap()")
    await th_until(page, "MW.station.st.hinted", 5)
    await n_quiet(t)
    faces = await page.evaluate(ST_FACES)
    s = await st_state(page)
    check(f"{label}: a wrong check and the hint: the commander doesn't smile (no face changes)", faces == [] and s["hinted"] and s["commander"][1] == "usual", json.dumps(faces))
    # the right answer: the blink and the smile, timed
    await page.evaluate("""(() => { const R = MW.station, s = R.st; window.__seen = []; const box = document.querySelector('#screen-station-play .station-commander');
        window.__anims = 0; const loop = () => { const c = box.querySelector('.mw-cat'); window.__seen.push([Math.round(performance.now()), c.dataset.face]);
          window.__anims = Math.max(window.__anims, box.getAnimations({ subtree: true }).length); window.__loop = requestAnimationFrame(loop); }; loop();
        s.counters.filter(m => m.where === 'deck').slice(0, 4).forEach(m => R.drop(m, 430, 300, false)); window.__stq = performance.now(); R.podTap(); })()""")
    ok = await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'num-mid-2 and num-mid-4 make num-end-6' && e.t > window.__stq)", 15)
    await asyncio.sleep(0.2)
    mid = await page.evaluate("document.querySelector('#screen-station-play .station-commander .mw-cat').dataset.face")
    await th_until(page, "!MW.audio.speaking() && MW.station.st.commander.face() === 'usual'", 10)
    await page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")   # the watcher sees the last face too
    await page.evaluate("cancelAnimationFrame(window.__loop)")
    log = await page.evaluate("MW.events.filter(e => e.type === 'commander' && e.t > window.__stq).map(e => [e.t - window.__stq, e.detail])")
    seen = await page.evaluate("window.__seen")
    runs = []
    for tm, f in seen:
        if not runs or runs[-1][1] != f:
            runs.append([tm, f])
    said_at = await page.evaluate("(() => { const e = MW.events.filter(e => e.type === 'say' && e.detail === 'num-mid-2 and num-mid-4 make num-end-6').pop(); return e.t - window.__stq; })()")
    check(f"{label}: on a right answer it blinks, then smiles: got it, usual after about 150 ms, got it again after about 300 ms, until the sentence has been "
          f"said, then usual (its face log and data-face)",
          ok and [x[1] for x in log] == ["got-it", "usual", "got-it", "usual"] and abs(log[1][0] - 150) < 80 and abs(log[2][0] - 300) < 100 and log[3][0] > said_at
          and mid == "got-it" and [r[1] for r in runs] == ["usual", "got-it", "usual", "got-it", "usual"], json.dumps([log, runs, said_at]))
    anims = await page.evaluate("window.__anims")
    check(f"{label}: nothing moves while it smiles (no animation on the commander{', as with reduce motion off' if reduce else ''})", anims == 0, str(anims))
    # steps 2 and 3: at the track's right-hand end
    for step, q in (("more", {"whole": 7, "a": 3}), ("numbers", {"whole": 9, "a": 5, "missing": "whole"})):
        await page.evaluate("(a) => MW.station.ask(a[0], a[1])", [q, step])
        s = await st_state(page)
        check(f"{label}: step {ST_STEPS.index(step) + 1}: the commander stands at the track's right-hand end (1110, 498, 124 wide)",
              s["commander"] == ["snuffles", "usual", "commander", 1110, 498, 124], json.dumps(s["commander"]))
    await t.drag(*tile_xy(9), *(await st_berth(page)))
    await page.evaluate("window.__stq = performance.now()")
    await n_check(t)
    await th_until(page, "MW.events.filter(e => e.type === 'commander' && e.t > window.__stq).length >= 4", 15)
    faces = await page.evaluate(ST_FACES)
    check(f"{label}: step 3: a right answer, the same blink and smile", faces == ["got-it", "usual", "got-it", "usual"], json.dumps(faces))
    await t.tap(*HOME)
    await t.wait_screen("screen-map", 5)
    # no commander: nobody stands there, and the game plays the same
    await page.evaluate("MW.crew.save({moggles: 'lookout', snuffles: 'engineer'})")
    s = await st_open(t, page, "aboard", [{"whole": 4, "a": 1}] * 5)
    empty = await page.evaluate("document.querySelector('#screen-station-play .station-commander').children.length")
    await st_shot(page, name + ("-reduce" if reduce else ""), "no-commander")
    await st_bring(t, 3)
    await page.evaluate("window.__stq = performance.now()")
    await n_check(t)
    s2 = await st_state(page)
    ok = await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'num-mid-1 and num-mid-3 make num-end-4' && e.t > window.__stq)", 15)
    check(f"{label}: with no commander, nobody stands on the deck, and a right answer plays the same (no face changes)",
          s["commander"] is None and empty == 0 and s2["phase"] == "station-celebrate" and ok and await page.evaluate(ST_FACES) == [], json.dumps([s["commander"], s2["phase"]]))
    await t.tap(*HOME)
    check(f"{label}: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def test_station_pause(p):
    """Hear-again; the screen going off mid-question; Home while a MeeMee is held, mid-celebration and from the end
    screen; the grown-ups area opened mid-hint and mid-celebration; Again on the end screen."""
    print("\n== MeeMee Station: Hear-again, pausing and Home ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "station-pause", 1046, 653, 1.22, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    rnd = [{"whole": 7, "a": 3}, {"whole": 5, "a": 2}, {"whole": 6, "a": 3}, {"whole": 8, "a": 2}, {"whole": 4, "a": 1}]
    await st_open(t, page, "aboard", rnd)
    await n_quiet(t)
    n0 = len(await t.said())
    await t.tap(*HEAR)
    await asyncio.sleep(0.4)
    check("station-pause: Hear-again says the question again", (await t.said())[n0:] == [st_prompt("aboard", rnd[0], 0)], json.dumps((await t.said())[n0:]))
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.6)
    paused = await page.evaluate("MW.world.st.paused")
    n0 = len(await t.said())
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.5)
    check("station-pause: the screen going off pauses; coming back asks the question again", paused and (await t.said())[n0:][:1] == [st_prompt("aboard", rnd[0], 0)],
          json.dumps((await t.said())[n0:]))
    # a MeeMee held as the screen goes off goes back to the deck
    await st_bring(t, 1)
    await n_hold(t, *ST_ON_DECK, 600, 400, touch_id=90)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await asyncio.sleep(0.4)
    await page.evaluate("Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange'))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.5)
    s = await st_state(page)
    check("station-pause: a MeeMee held as the screen goes off goes back to its place on the deck (the one already brought stays)",
          s["aboard"] == [3] and s["deck"] == 6 and await st_in_order(page), json.dumps(s))
    # Home while a MeeMee is held: nothing said after, the map
    await n_quiet(t)
    await n_hold(t, *ST_ON_DECK, 600, 400, touch_id=91)
    await page.evaluate("MW.station.home()")                # Home (the other hand)
    n0 = len(await t.said())
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.8)
    s = await st_state(page)
    check("station-pause: Home while a MeeMee is held: the map, nothing said after, the game put away", s["screen"] == "screen-map" and (await t.said())[n0:] == []
          and s["deck"] == 0 and s["aboard"] == [] and s["fixed"] == 0, json.dumps(s))
    # step 2: the grown-ups area opened mid-hint takes the hint away; closed, the question again; the next wrong number brings it back
    rnd2 = [{"whole": 7, "a": 3}, {"whole": 6, "a": 1}, {"whole": 9, "a": 3}, {"whole": 5, "a": 3}, {"whole": 8, "a": 4}]
    await st_open(t, page, "more", rnd2)
    await n_quiet(t)
    for n in (5, 6):
        await t.drag(*tile_xy(n), *(await st_berth(page)))
        await n_check(t)
        await asyncio.sleep(0.1)
        if n == 5:
            await n_quiet(t)
    await asyncio.sleep(0.5)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    await asyncio.sleep(0.5)
    s = await st_state(page)
    check("station-pause: the grown-ups area opened mid-hint: the hint stops and is taken away (the windows open again, no ghosts, no halo)",
          not s["hinted"] and s["ghosts"] == 0 and s["windows"] == st_windows(3, 7) and not s["bars"][2][3] and not await page.evaluate("MW.audio.speaking()"), json.dumps(s))
    n0 = len(await t.said())
    await page.click(".gu-close")
    await asyncio.sleep(0.5)
    check("station-pause: ... closed, the question is asked again", (await t.said())[n0:][:1] == [st_prompt("more", rnd2[0], 0)], json.dumps((await t.said())[n0:]))
    await n_quiet(t)
    await t.drag(*tile_xy(8), *(await st_berth(page)))
    await n_check(t)
    s = await st_state(page)
    check("station-pause: ... and the next wrong number gives the hint again", s["hinted"] and s["ghosts"] == 4 and s["windows"] == st_windows(3, 7, "hinting"), json.dumps(s))
    await n_quiet(t)
    # the grown-ups area opened mid-celebration: everything waits, then carries on
    await t.drag(*tile_xy(4), *(await st_berth(page)))
    await n_check(t)
    await page.evaluate("MW.world.pause('grown-ups'); MW.grownups.openPanel()")
    n0 = len(await t.said())
    await asyncio.sleep(2.5)
    s = await st_state(page)
    check("station-pause: the grown-ups area opened mid-celebration: nothing is said while it's open, the answer stays",
          s["phase"] == "station-celebrate" and (await t.said())[n0:] == [] and s["bars"][2] == [4, False, True, False, "4"], json.dumps(s))
    await page.click(".gu-close")
    s = await st_wait(page, ["station-open"], 30)
    check("station-pause: ... closed, the celebration carries on (the sentence said), then question 2",
          s["qi"] == 1 and st_said_sentence(st_q("more", rnd2[0])) in await t.said(), json.dumps(s))
    # Hear-again mid-celebration says nothing; Home mid-celebration: nothing more said
    await n_quiet(t)
    await t.drag(*tile_xy(5), *(await st_berth(page)))
    await n_check(t)
    n0 = len(await t.said())
    await t.tap(*HEAR)
    await asyncio.sleep(0.2)
    heard = (await t.said())[n0:]
    await t.tap(*HOME)
    n0 = len(await t.said())
    await asyncio.sleep(3)
    s = await st_state(page)
    check("station-pause: Hear-again mid-celebration says nothing new; Home mid-celebration: back on the map, nothing more said, the tiles all back",
          not any(x.startswith("q-") for x in heard) and s["screen"] == "screen-map" and (await t.said())[n0:] == [] and s["out"] == [] and s["placed"] is None,
          json.dumps([heard, (await t.said())[n0:], s]))
    # the end screen: Again starts a new round; Home goes back to the map
    await st_set(page, "aboard", [{"whole": 2, "a": 1}] * 5)
    pl = await page.evaluate(ST_PLACE)
    await t.tap(pl["x"], pl["y"])
    for _ in range(5):
        await st_wait(page, ["station-open"], 25)
        await st_bring(t, 1)
        await n_check(t)
    await st_wait(page, ["station-done"], 25)
    await th_until(page, "MW.events.some(e => e.type === 'say' && e.detail === 'station-round-another')", 15)
    end = await page.evaluate("""(() => { const s = document.getElementById('screen-station-end'), a = document.getElementById('station-again');
        return { again: [a.offsetLeft, a.offsetTop, a.offsetWidth], mimi: s.querySelectorAll('.station-end-mimi').length, windows: s.querySelectorAll('.station-pod').length,
                 cats: Array.from(s.querySelectorAll('.mw-cat')).map(c => [c.dataset.who, c.dataset.job, c.parentNode.offsetLeft, c.parentNode.offsetTop, c.offsetWidth]),
                 stars: s.querySelector('.mw-stars').offsetLeft, pod: [s.querySelector('.mw-pod').offsetLeft, s.querySelector('.mw-pod').offsetTop, s.querySelector('.mw-pod').dataset.face] }; })()""")
    check("station-pause: the end screen (board round14-end): Again at 1080, 420; ten windows each with a MeeMee in the station along the bottom; Moggles at 70, 330 "
          "and Snuffles at 790, 330 (240 wide) wearing their badges; the stars from 450; Scruffles's ship at 380, 110 grinning",
          end == {"again": [1080, 420, 160], "mimi": 10, "windows": 10, "cats": [["moggles", "commander", 70, 330, 240], ["snuffles", "lookout", 790, 330, 240]],
                  "stars": 450, "pod": [380, 110, "got-it"]}, json.dumps(end))
    await page.evaluate("MW.station.nextRound = %s" % json.dumps(rnd))
    await t.tap(1160, 500)                                   # Again (1080, 420, 160 across)
    s = await st_wait(page, ["station-open"], 30)
    check("station-pause: Again on the end screen starts a new round", s["screen"] == "screen-station-play" and s["qi"] == 0 and s["fixed"] == 3, json.dumps(s))
    await t.tap(*HOME)
    check("station-pause: Home goes back to the map", await t.wait_screen("screen-map", 5))
    check("station-pause: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


# What a moment must stay clear of on the game screen (stage boxes [x, y, w, h]): the station (its parts' boxes, from the
# layouts: step 1 the truss, wings and modules, the tower and its antenna, the dish; step 2 the station and its masts;
# step 3 the truss and wing), the deck's MeeMee, the hull modules and the berth, the hint's small station, the commander,
# and the sentence while it shows
ST_KEEP_CLEAR = """(() => { const R = MW.station, s = R.st, step = R.step(), out = [];
    const st = { aboard: [[38, 251, 784, 254], [348, 62, 164, 226], [615, 220, 80, 62]],
                 more: [[114, 121, 660, 198], [341, 302, 22, 74], [525, 302, 22, 74]], numbers: [[106, 176, 128, 250]] }[step];
    st.forEach(b => out.push(['the station', b]));
    s.counters.filter(c => c.where === 'deck').forEach(c => out.push(["the deck's MeeMee", [c.x - 36, c.y - 36, 72, 72]]));
    const b = R.bars(); if (b) ['whole', 'left', 'right'].forEach(k => out.push([b[k] === s.berth ? 'the berth' : 'the hull modules', [b[k].x, b[k].y, b[k].w, b[k].h]]));
    if (s.hintStation && !s.hintStation.classList.contains('is-gone')) out.push(['the small station', [289, 416, 390, 220]]);
    if (R.equation().el.classList.contains('is-shown')) out.push(['the sentence', [180, 700, 400, 80]]);
    const c = document.querySelector('#screen-station-play .station-commander .mw-cat');
    if (c) { const p = c.parentNode; out.push(['the commander', [p.offsetLeft, p.offsetTop, c.offsetWidth, c.offsetHeight]]); }
    return out; })()"""


ST_ROOM = 20                                       # the least gap round the engineer where it moved to (steps 1 and 3), stage px


def box_gap(a, b):
    """The gap between two stage boxes [x, y, w, h] (0 if they touch or overlap)."""
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0)
    dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0)
    return round((dx * dx + dy * dy) ** 0.5, 1)


async def st_moment_clear(page, sel, peek=False):
    """A moment's drawn box (clipped to its window, for the lookout's peek) and what it overlaps of ST_KEEP_CLEAR."""
    box = await moment_box(page, sel)
    if box and peek:
        win = await page.evaluate("(sel => { const e = document.querySelector(sel); return [e.offsetLeft, e.offsetTop, e.offsetWidth, e.offsetHeight]; })(%s)" % json.dumps(sel))
        x0, y0 = max(box[0], win[0]), max(box[1], win[1])
        x1, y1 = min(box[0] + box[2], win[0] + win[2]), min(box[1] + box[3], win[1] + win[3])
        box = [x0, y0, x1 - x0, y1 - y0]
    keep = await page.evaluate(ST_KEEP_CLEAR)
    return box, [k[0] for k in keep if box and overlap(box, k[1], 2)]


async def test_station_moments(p, name, vw, vh, dpr):
    """The crew's moments, at Take MeeMee Home's points, moved clear where its places would be over the station, the
    deck's MeeMee, the hull modules, the berth, the sentence or the commander: the lookout as a round starts (step 1 from
    the stage's foot below the station; steps 2 and 3 behind the track, left of the commander), never up with the
    sentence; the engineer on a right answer (step 2 by the ship's left fin; steps 1 and 3 under the picture's right-hand
    end, 110 wide, with room round it, clear of the ship and the commander too); the navigator as a star turns peach
    (under the stars' right end). None without a job; no words."""
    print(f"\n== MeeMee Station: the crew's moments ({name}) ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, f"station-moments-{name}", vw, vh, dpr, mode=None)
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    loop = """(() => { window.__both = 0; window.__seen = 0; const loop = () => { const b = document.querySelector('#screen-station-play [data-moment=lookout].is-shown');
        const e = MW.station.equation().el; if (b) window.__seen++; if (b && e.classList.contains('is-shown')) window.__both++; window.__loop = requestAnimationFrame(loop); }; loop(); })()"""
    for step, q in (("aboard", {"whole": 7, "a": 3}), ("more", {"whole": 7, "a": 3}), ("numbers", {"whole": 10, "a": 6, "missing": "right"})):
        k = ST_STEPS.index(step) + 1
        await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'lookout'})")
        await page.evaluate(loop)
        await st_set(page, step, [q] * 5)
        if await page.evaluate("MW.shell.screen") == "screen-start":
            await t.tap(*PLAY)
            await t.wait_screen("screen-map")
        pl = await page.evaluate(ST_PLACE)
        await t.tap(pl["x"], pl["y"])
        await th_until(page, "!!document.querySelector('#screen-station-play [data-moment=lookout].is-shown')", 15)
        await asyncio.sleep(0.6)                             # its rise (450 ms)
        look = await page.evaluate("""(() => { const b = document.querySelector('#screen-station-play [data-moment=lookout].is-shown'); if (!b) return null;
            return { window: [b.offsetLeft, b.offsetTop, b.offsetWidth, b.offsetHeight], flip: b.classList.contains('station-peek-flip'),
                     scale: getComputedStyle(b.querySelector('.mw-peek-inner')).scale }; })()""")
        lb, hits = await st_moment_clear(page, "#screen-station-play [data-moment=lookout]", peek=True)
        await st_shot(page, name, f"lookout-step{k}")
        want = [420, 548, 250, 252] if step == "aboard" else [856, 519, 250, 175]
        where = "rises from the stage's foot below the station, left of the deck" if step == "aboard" else "peeks up from behind the track, left of the commander"
        check(f"station-moments ({name}): step {k}: as the round starts the lookout {where}, mirrored to face the station ({', '.join(map(str, want))}), clear of "
              f"everything it must not cover", look is not None and look["window"] == want and look["flip"] and look["scale"] == "-1 1" and not hits, json.dumps([look, lb, hits]))
        s = await st_wait(page, ["station-open"], 20)
        down = await th_until(page, "!document.querySelector('#screen-station-play [data-moment=lookout]')", 10)
        check(f"station-moments ({name}): step {k}: ... and ducks down once it has spotted the station (1.8 s into the first question)", down)
        # the engineer on a right answer
        await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'engineer'})")
        if step == "aboard":
            await st_bring(t, 4)
        else:
            await t.drag(*tile_xy(4), *(await st_berth(page)))
        await n_check(t)
        await asyncio.sleep(0.5)
        eb, hits = await st_moment_clear(page, "#screen-station-play [data-moment=engineer]")
        place = await page.evaluate("""(() => { const b = document.querySelector('#screen-station-play [data-moment=engineer]'), c = b.querySelector('.mw-cat');
            return [b.offsetLeft, b.offsetTop, c.offsetWidth, getComputedStyle(c).scale]; })()""")
        await st_shot(page, name, f"engineer-step{k}")
        want = {"aboard": [545, 530, 110], "more": [700, 326, 140], "numbers": [700, 530, 110]}[step]
        where = {"aboard": "under the station's right-hand end (left of the deck, above the sentence's place)", "more": "by the ship's left fin (Take MeeMee Home's place)",
                 "numbers": "under the berth's right-hand end (left of the ship's fin)"}[step]
        check(f"station-moments ({name}): step {k}: the engineer's moment on a right answer, {where} ({want[0]}, {want[1]}, {want[2]} wide), not mirrored, "
              f"clear of everything it must not cover", eb is not None and place[:3] == want and place[3] in ("none", "1") and not hits, json.dumps([eb, place, hits]))
        if step != "more":
            # where it moved to (steps 1 and 3) is also clear of the ship's whole box, the deck and every deck slot (any may hold a MeeMee),
            # the sentence's place (its widest) and the hint's small station (while it fades), by at least ST_ROOM px
            ship = await moment_box(page, "#screen-station-play .mw-pod")
            more = [["the ship", ship], ["the sentence's place", [180, 700, 400, 80]]] + [[n_, b_] for n_, b_ in (await page.evaluate(ST_KEEP_CLEAR))]
            more += ([["the deck", [724, 642, 532, 124]]] + [["a deck slot", [x - 36, y - 36, 72, 72]] for x, y in [(772 + 80 * i, 652) for i in range(5)] + [(812 + 80 * i, 722) for i in range(4)]]
                     if step == "aboard" else [["the hint's small station", [289, 416, 390, 220]]])
            near = sorted((box_gap(eb, b_), n_) for n_, b_ in more)
            check(f"station-moments ({name}): step {k}: ... with room round it: at least {ST_ROOM} px from the ship, the commander and everything else it "
                  f"must not cover", eb is not None and near[0][0] >= ST_ROOM, json.dumps(near[:4]))
        # the navigator as the star turns peach
        await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: 'navigator'})")
        n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment' && e.detail.indexOf('navigator') === 0).length")
        await th_until(page, "MW.events.filter(e => e.type === 'moment' && e.detail.indexOf('navigator') === 0).length > %d" % n0, 15)
        await asyncio.sleep(0.5)
        nb, hits = await st_moment_clear(page, "#screen-station-play [data-moment=navigator]")
        route = await page.evaluate("(() => { const r = document.querySelector('#screen-station-play .mw-route path'); return r ? r.getAttribute('d') : null; })()")
        await st_shot(page, name, f"navigator-step{k}")
        check(f"station-moments ({name}): step {k}: the navigator holds up the star map as the star turns peach, with a dotted route to the next star, under the stars' "
              f"right end (784, 92), clear of everything it must not cover (the sentence is showing now)",
              nb is not None and route is not None and "NaN" not in route and not hits and nb[1] > 72, json.dumps([nb, hits]))
        await t.tap(*HOME)
        await t.wait_screen("screen-map", 5)
        both = await page.evaluate("[window.__seen, window.__both]")
        await page.evaluate("cancelAnimationFrame(window.__loop)")
        check(f"station-moments ({name}): step {k}: the lookout is never up while the sentence shows; Home clears every moment",
              both[0] > 10 and both[1] == 0 and await page.evaluate("document.querySelectorAll('#screen-station-play [data-moment], #screen-station-end [data-moment]').length") == 0,
              json.dumps(both))
    said = await t.said()
    check(f"station-moments ({name}): no words in the moments", not any("job-" in x or "name-" in x for x in said), json.dumps(said[-3:]))
    # nobody with those jobs: no moments
    await page.evaluate("MW.crew.save({moggles: 'commander', snuffles: null})")
    n0 = await page.evaluate("MW.events.filter(e => e.type === 'moment').length")
    s = await st_open(t, page, "aboard", [{"whole": 3, "a": 1}] * 5)
    await st_bring(t, 2)
    await page.evaluate("window.__stq = performance.now()")
    await n_check(t)
    await th_until(page, "MW.events.some(e => e.type === 'question' && e.t > window.__stq)", 20)
    check(f"station-moments ({name}): no lookout, engineer or navigator: no moments", await page.evaluate("MW.events.filter(e => e.type === 'moment').length") == n0)
    await t.tap(*HOME)
    check(f"station-moments ({name}): no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def station_quick_round(t, page):
    """MeeMee Station from the map: one question in step 1 (3 with 1 aboard), to the end screen."""
    await st_open(t, page, "aboard", [{"whole": 3, "a": 1}])
    await st_bring(t, 2)
    await n_check(t)
    return await st_wait(page, ["station-done"], 30)


async def test_station_motion(p):
    """Motion and reduce motion: a MeeMee snaps into its window (with reduce motion it is there at once); in step 2 the
    rest pop into their windows (a fade with reduce motion), the track slides away (fades), the sparkles grow (fade); in
    step 3 the hint's small station fades away either way; the windows' rings come in over 450 ms (at once)."""
    print("\n== MeeMee Station: motion and reduce motion ==")
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    for reduce in (False, True):
        label = "reduce motion" if reduce else "motion"
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True, reduced_motion="reduce" if reduce else "no-preference")
        page = await ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        await page.goto(ORIGIN + "/")
        await page.wait_for_load_state("load")
        await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
        res = await page.evaluate("""(() => { const R = MW.station; R.ask({ whole: 6, a: 2 }, 'aboard'); const c = R.st.counters.filter(m => m.where === 'deck')[0];
            R.drop(c, 430, 300, false); const w = R.windows()[2];
            return { moving: c.el.classList.contains('is-moving'), transition: getComputedStyle(c.el).transitionDuration, at: [c.x === w.x, c.y === w.y],
                     ring: getComputedStyle(w.el).transitionDuration }; })()""")
        if reduce:
            check(f"station ({label}): step 1: a MeeMee let go on the station is in its window at once (no snap), and the windows' rings come in at once",
                  not res["moving"] and res["at"] == [True, True] and res["ring"] == "0s", json.dumps(res))
        else:
            check(f"station ({label}): step 1: a MeeMee let go on the station snaps into its window (260 ms), and the windows' rings come in over 450 ms",
                  res["moving"] and res["at"] == [True, True] and res["transition"] == "0.26s" and res["ring"].startswith("0.45s"), json.dumps(res))
        res = await page.evaluate("""(() => { const R = MW.station; R.ask({ whole: 7, a: 3 }, 'more'); const tr = R.track(), m = R.st.berth;
            R.drop(tr.tile(4), m.x + m.w / 2, m.y + m.h / 2, false); R.podTap();
            const pop = Array.from(document.querySelectorAll('#screen-station-play .mw-mimi.station-pop .mw-mimi-art')).map(x => getComputedStyle(x).animationName);
            const ts = getComputedStyle(tr.el), sp = Array.from(document.querySelectorAll('#screen-station-play .mw-spark')).map(x => getComputedStyle(x).animationName);
            return { pop: pop, track: [ts.transform, ts.transitionProperty], sparks: Array.from(new Set(sp)) }; })()""")
        if reduce:
            check(f"station ({label}): step 2's right answer: the rest fade into their windows, the track fades away, the sparkles fade",
                  res["pop"] == ["mw-arrive"] * 4 and res["track"][0] == "none" and res["sparks"] == ["mw-spark-fade"], json.dumps(res))
        else:
            check(f"station ({label}): step 2's right answer: the rest pop into their windows (260 ms), the track slides away, the sparkles grow",
                  res["pop"] == ["station-pop"] * 4 and res["track"][0] != "none" and res["sparks"] == ["mw-spark"], json.dumps(res))
        await page.evaluate("MW.world.home()")
        res = await page.evaluate("""(() => { const R = MW.station, s = R.st; R.ask({ whole: 9, a: 5, missing: 'right' }, 'numbers'); const tr = R.track(), m = s.berth;
            R.drop(tr.tile(1), m.x + m.w / 2, m.y + m.h / 2, false); R.podTap(); s.talking = false;
            R.drop(tr.tile(2), m.x + m.w / 2, m.y + m.h / 2, false); R.podTap();
            const had = !!s.hintStation; s.talking = false; R.drop(tr.tile(4), m.x + m.w / 2, m.y + m.h / 2, false); R.podTap();
            const h = document.querySelector('#screen-station-play .station-hint'), cs = getComputedStyle(h);
            return [had, h.classList.contains('is-gone'), cs.transitionProperty, cs.transitionDuration]; })()""")
        check(f"station ({label}): step 3: after the hint, a right answer: the small station fades away (300 ms), as with {'motion' if reduce else 'reduce motion'}",
              res == [True, True, "opacity", "0.3s"], json.dumps(res))
        await page.evaluate("MW.world.home()")
        check(f"station ({label}): no console errors", not problems, "; ".join(problems[:3]))
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
        await test_words_halves(p)
        await test_words_move(p)
        await test_words_tab(p, "fire", 1046, 653, 1.22)
        await test_words_tab(p, "doogee", 1280, 800, 2)
        await test_words_shared(p)
        await test_words_mrs(p, "fire", 1046, 653, 1.22)
        await test_words_mrs(p, "doogee", 1280, 800, 2)
        await test_words_spring(p)
        await test_words_unrecorded(p)
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
        await test_places(p, "fire", 1046, 653, 1.22)
        await test_places(p, "doogee", 1280, 800, 2)
        await test_equation(p, "fire", 1046, 653, 1.22)
        await test_equation(p, "doogee", 1280, 800, 2)
        await test_equation_motion(p)
        await test_takehome_round(p, "take", "fire", 1046, 653, 1.22)
        await test_takehome_round(p, "take", "doogee", 1280, 800, 2)
        await test_takehome_round(p, "left", "fire", 1046, 653, 1.22)
        await test_takehome_round(p, "left", "doogee", 1280, 800, 2)
        await test_takehome_round(p, "numbers", "fire", 1046, 653, 1.22)
        await test_takehome_round(p, "numbers", "doogee", 1280, 800, 2)
        await test_takehome_wrong_take(p)
        await test_takehome_wrong_take(p, "doogee", 1280, 800, 2)
        await test_takehome_wrong_left(p, "fire", 1046, 653, 1.22)
        await test_takehome_wrong_left(p, "doogee", 1280, 800, 2)
        await test_takehome_wrong_numbers(p)
        await test_takehome_wrong_numbers(p, "doogee", 1280, 800, 2)
        await test_takehome_drag(p)
        await test_takehome_questions(p)
        await test_takehome_progress(p)
        await test_takehome_grownups(p, "fire", 1046, 653, 1.22)
        await test_takehome_grownups(p, "doogee", 1280, 800, 2)
        await test_takehome_map(p, "fire", 1046, 653, 1.22)
        await test_takehome_map(p, "doogee", 1280, 800, 2)
        await test_takehome_pause(p)
        await test_takehome_hop_pause(p)
        await test_takehome_hop_pause(p, "doogee", 1280, 800, 2)
        await test_takehome_storage(p)
        await test_takehome_words(p)
        await test_takehome_motion(p)
        await test_takehome_moments(p, "fire", 1046, 653, 1.22)
        await test_takehome_moments(p, "doogee", 1280, 800, 2)
        await test_commander_moments(p, "fire", 1046, 653, 1.22)
        await test_commander_moments(p, "doogee", 1280, 800, 2)
        await test_commander_moments(p, "fire", 1046, 653, 1.22, reduce=True)
        await test_crew_faces(p, "fire", 1046, 653, 1.22)
        await test_crew_faces(p, "doogee", 1280, 800, 2)
        await test_saved_cook(p)
        await test_station_map(p, "fire", 1046, 653, 1.22)
        await test_station_map(p, "doogee", 1280, 800, 2)
        await test_tab_row(p)
        for step in ST_STEPS:
            await test_station_round(p, step, "fire", 1046, 653, 1.22)
            await test_station_round(p, step, "doogee", 1280, 800, 2)
        await test_station_wrong_aboard(p)
        await test_station_wrong_aboard(p, "doogee", 1280, 800, 2)
        await test_station_wrong_more(p, "fire", 1046, 653, 1.22)
        await test_station_wrong_more(p, "doogee", 1280, 800, 2)
        await test_station_wrong_numbers(p, "fire", 1046, 653, 1.22)
        await test_station_wrong_numbers(p, "doogee", 1280, 800, 2)
        await test_station_drag(p)
        await test_station_questions(p)
        await test_station_progress(p)
        await test_station_grownups(p, "fire", 1046, 653, 1.22)
        await test_station_grownups(p, "doogee", 1280, 800, 2)
        await test_station_commander(p, "fire", 1046, 653, 1.22)
        await test_station_commander(p, "doogee", 1280, 800, 2)
        await test_station_commander(p, "fire", 1046, 653, 1.22, reduce=True)
        await test_station_pause(p)
        await test_station_moments(p, "fire", 1046, 653, 1.22)
        await test_station_moments(p, "doogee", 1280, 800, 2)
        await test_station_motion(p)
    srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
