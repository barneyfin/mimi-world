"""Headless checks for Mimi World (phase 3): the trial round and the kit, on Fire and Doogee screen sizes.

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


async def open_tablet(p, name, vw, vh, dpr, extra_args=()):
    browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", *extra_args])
    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dpr, has_touch=True, is_mobile=True)
    page = await ctx.new_page()
    problems, requests = [], []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    page.on("request", lambda r: requests.append(r.url))
    await page.goto(ORIGIN + "/")
    await page.wait_for_load_state("load")
    cdp = await ctx.new_cdp_session(page)
    return browser, ctx, page, Tablet(page, cdp), problems, requests


async def play_round(t, name, shots=True):
    page = t.page
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(900, 380)                                    # the Play button
    s = await t.wait_phase(["asking", "open"])
    check(f"{name}: Play starts the round", s["screen"] == "screen-game" and s["qi"] == 0, json.dumps(s))
    check(f"{name}: sound running after the tap", await page.evaluate("MW.audio.running()"))

    # Q1 missing right part 4 (whole 7, given 3)
    await t.fill(2, "right")
    s = await t.state()
    check(f"{name}: two Mimi dropped show 2 in the pill", s["placed"] == 2 and (await page.inner_text("#screen-game .mw-pill.is-waiting")) == "2")
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
    check(f"{name}: the fourth Mimi completes 3 + ? = 7", s["phase"] == "celebrate", json.dumps(s))
    await asyncio.sleep(2.6)
    if shots:
        await page.screenshot(path=str(SHOTS / f"{name}-2-celebrate.png"))
    eq = await page.inner_text("#screen-game .mw-equation")
    check(f"{name}: equation reads 3 + 4 = 7", eq.replace("\n", " ").split() == ["3", "+", "4", "=", "7"], eq)
    s = await t.wait_phase(["asking", "open"], 15)
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
    check(f"{name}: hint shows 5 ghost Mimi in the whole", ghosts == 5, str(ghosts))
    await asyncio.sleep(2.5)
    if shots:
        await page.screenshot(path=str(SHOTS / f"{name}-3-hint.png"))
    await t.fill(5, "whole")
    s = await t.wait_phase(["celebrate"], 3)
    check(f"{name}: five Mimi in the whole completes 2 + 3 = ?", s["phase"] == "celebrate", json.dumps(s))
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
    check(f"{name}: dragging a Mimi back out leaves 1", s["placed"] == 1, json.dumps(s))
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
    check(f"{name}: 'You rescued all the Mimi!' plays", "round-rescued-all" in said)
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
    await t.tap(900, 380)
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
    browser, ctx, page, t, problems, _ = await open_tablet(p, "tap", 1280, 800, 1)
    await page.evaluate("MW.store.setting('check', 'tap')")
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(900, 380)
    await t.wait_phase(["open"], 15)
    await t.fill(2, "right")
    await t.tap(1030, 300)                                   # tap Scruffles with 2 (too few)
    await asyncio.sleep(0.6)
    check("tap: too few says 'Let's look again.'", "again-look-again" in await t.said())
    await t.fill(4, "right")                                 # 6 > 4
    s = await t.state()
    check("tap: six Mimi can go in (no auto-complete)", s["placed"] == 6 and s["phase"] == "open", json.dumps(s))
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
    check("tap: four Mimi and a tap on Scruffles completes it", s["phase"] == "celebrate", json.dumps(s))
    rec = await page.evaluate("MW.store.get('answers').slice(-1)[0]")
    check("tap: saved with 3 wrong checks and the hint", rec["tries"] == 3 and rec["hint"] is True, json.dumps(rec))
    check("tap: no console errors", not problems, "; ".join(problems[:3]))
    await browser.close()


async def touch(t, kind, points):
    await t.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [
        {"x": x, "y": y, "id": i, "radiusX": 8, "radiusY": 8, "force": 1} for i, (x, y) in points]})


async def test_edge_cases(p):
    print("\n== edge cases ==")
    browser, ctx, page, t, problems, _ = await open_tablet(p, "edge", 1046, 653, 1.22)
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
    await t.tap(900, 380)
    await t.wait_phase(["open"], 15)

    # picking a Mimi up keeps it fully visible (no fade-in replay)
    free = await t.tray_free()
    x0, y0 = await t.screen(*free[-1])
    await touch(t, "touchStart", [(1, (x0, y0))])
    await asyncio.sleep(0.05)
    op = await page.evaluate("Math.min(...MW.rescue.st.counters.map(c => +getComputedStyle(c.el).opacity))")
    await touch(t, "touchEnd", [])
    await asyncio.sleep(0.4)
    check("edge: a picked-up Mimi stays fully visible", op > 0.99, str(op))

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

    # Home while a Mimi is held, then the finger lifts: nothing is said on the start screen
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
    check("edge: a Mimi let go after Home says nothing", len(await t.said()) == n_before, str((await t.said())[n_before:]))

    # an interrupted hint comes back on the next wrong try
    await page.evaluate("MW.rescue.nextRound = %s" % json.dumps(ROUND))
    await t.tap(900, 380)
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

    # rescued Mimi that were dropped in fade out with the rest
    await t.fill(4, "right")
    await t.wait_phase(["celebrate"], 3)
    for _ in range(80):
        if await page.evaluate("document.querySelectorAll('.mw-mimi.is-rescued').length") > 0:
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)
    ops = await page.evaluate("Array.from(document.querySelectorAll('.mw-mimi.is-rescued')).map(e => Math.round(+getComputedStyle(e).opacity * 100) / 100)")
    check("edge: every rescued Mimi is fading out (dropped ones too)", len(ops) == 7 and max(ops) < 0.5, str(ops))
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
    await browser.close()


async def main():
    srv = serve()
    async with async_playwright() as p:
        await test_device(p, "fire", 1046, 653, 1.22)
        await test_device(p, "doogee", 1280, 800, 2)
        await test_tap_mode(p)
        await test_edge_cases(p)
        await test_portrait(p)
        await test_reduce_motion(p)
    srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
