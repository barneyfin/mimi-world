"""Check how updates reach a tablet that already has an offline copy.

1. A tablet with the phase 0 test page (v0.1.2) is moved to the new game on its next visit, without a second visit.
2. A newer version switches over at the start screen.
3. A newer version never interrupts a round: it waits for Home (the map).

    python tools/tests/test_update.py PHASE0_DOCS_FOLDER
PHASE0_DOCS_FOLDER is a copy of docs/ as it was at phase 0 (git: the docs folder from commit beaf3b0).
"""
import asyncio
import functools
import http.server
import pathlib
import re
import shutil
import sys
import threading

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SERVE = pathlib.Path(__file__).resolve().parent / "serve"
PORT = 8792
FAILS = []
# the version just built, and two made-up newer ones the test publishes on top of it
BUILT = re.search(r"VERSION: '([^']+)'", (DOCS / "index.html").read_text(encoding="utf-8")).group(1)
NEWER1, NEWER2 = BUILT + "-next1", BUILT + "-next2"


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600")   # like GitHub Pages
        super().end_headers()

    def log_message(self, *a):
        pass


def publish(src, version=None):
    if SERVE.exists():
        shutil.rmtree(SERVE)
    shutil.copytree(src, SERVE)
    if version:
        html = (SERVE / "index.html").read_text(encoding="utf-8").replace(f"VERSION: '{BUILT}'", f"VERSION: '{version}'")
        (SERVE / "index.html").write_text(html, encoding="utf-8")
        sw = (SERVE / "sw.js").read_text(encoding="utf-8")
        sw = sw.replace(f"const VERSION = 'mimi-world-v{BUILT}-", f"const VERSION = 'mimi-world-v{version}-")
        (SERVE / "sw.js").write_text(sw, encoding="utf-8")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS.append(name)


async def version(page):
    return await page.evaluate("window.MW && MW.VERSION ? MW.VERSION : (window.__mimiTest ? 'phase 0 test page' : 'unknown')")


async def wait_version(page, want, secs=15):
    for _ in range(secs * 5):
        try:
            if await version(page) == want:
                return want
        except Exception:
            pass                                             # the page is navigating
        await asyncio.sleep(0.2)
    return await version(page)


async def main(phase0):
    publish(phase0)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=str(SERVE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, has_touch=True)
            page = await ctx.new_page()
            url = f"http://127.0.0.1:{PORT}/"
            await page.goto(url)
            await page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=8000)
            check("a tablet starts on the phase 0 test page", await version(page) == "phase 0 test page")

            # 1. the new game is published; the tablet opens its bookmark. The browser checks for a new version
            #    in the background (here: asked for straight away), and the open test page moves to the game.
            await asyncio.sleep(2)
            publish(DOCS)
            await page.reload()
            await page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
            v = await wait_version(page, BUILT, 20)
            check("once the new version is saved, the open test page moves to the game", v == BUILT, v)
            await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)

            # 2. a newer version, tablet on the start screen
            await asyncio.sleep(2)
            publish(DOCS, NEWER1)
            await page.reload()                                  # the page asks for updates itself 8 s after opening
            v = await wait_version(page, NEWER1, 25)
            check("a newer version switches over at the start screen", v == NEWER1, v)

            # 3. a newer version arrives mid-round: no interruption until Home
            await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
            await page.evaluate("MW.audio.unlock(); MW.rescue.start()")
            await asyncio.sleep(1)
            await asyncio.sleep(1)
            publish(DOCS, NEWER2)
            await page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
            await asyncio.sleep(6)
            v = await version(page)
            screen = await page.evaluate("MW.shell.screen")
            check("mid-round, the page doesn't reload", v == NEWER1 and screen == "screen-game", f"{v}, {screen}")
            check("the update is waiting", await page.evaluate("!!MW.shell.updateReady"))
            await page.evaluate("MW.rescue.home()")
            v = await wait_version(page, NEWER2, 15)
            check("tapping Home (back to the map) switches to the newer version", v == NEWER2, v)

            # offline afterwards
            await ctx.set_offline(True)
            await page.reload()
            await page.wait_for_load_state("load")
            await page.wait_for_function("MW.audio.status().decoded === MW.audio.status().total", timeout=15000)
            check("works offline after the updates", await version(page) == NEWER2)
            await browser.close()
    finally:
        srv.shutdown()
        shutil.rmtree(SERVE, ignore_errors=True)
    print("all update checks passed" if not FAILS else f"{len(FAILS)} update checks failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    asyncio.run(main(pathlib.Path(sys.argv[1])))
