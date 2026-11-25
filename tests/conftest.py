"""Shared setup for the MyNextCert browser tests (pytest + Playwright, Chromium).

Every page opened through the `site` fixture is watched for:
  * JavaScript errors and console errors,
  * requests to any outside server (the site must load nothing from outside),
and the test fails at the end if any happened.

Local run:   pip install -r tests/requirements.txt && python -m playwright install chromium
             pytest tests -q
Use a system Chrome instead of the downloaded one:  CHROME_PATH=/usr/bin/google-chrome pytest tests -q
"""
import os, pathlib, re, sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from ghp_server import start  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# what the page should show as its version label, read from the built page itself
_label = re.search(r'v\.2\.\d+', (ROOT / "index.html").read_text(encoding="utf8"))
VERSION_LABEL = _label.group(0) if _label else None

DEVICES = {
    "desktop": dict(viewport={"width": 1440, "height": 900}),
    "iphone13": dict(viewport={"width": 390, "height": 664}, device_scale_factor=3, is_mobile=True, has_touch=True,
                     user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    "small320": dict(viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True),
    "zoom200": dict(viewport={"width": 640, "height": 450}),   # a 1280x900 laptop at 200% zoom
    "reduced": dict(viewport={"width": 1440, "height": 900}, reduced_motion="reduce"),
}

# console messages that are expected and harmless
IGNORED_CONSOLE = (
    re.compile(r"Failed to load resource: the server responded with a status of 404"),  # the 404 tests ask for missing pages on purpose
)


@pytest.fixture(scope="session")
def base_url():
    srv, url = start()
    yield url
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]  # software WebGL so the real 3D globe can run
    with sync_playwright() as p:
        kw = {"args": args}
        if os.environ.get("CHROME_PATH"):
            kw["executable_path"] = os.environ["CHROME_PATH"]
        b = p.chromium.launch(**kw)
        yield b
        b.close()


class Watched:
    """A page plus everything bad it did."""

    def __init__(self, context, page, base_url):
        self.context, self.page, self.base_url = context, page, base_url
        self.errors, self.outside = [], []
        page.on("pageerror", lambda e: self.errors.append("pageerror: %s" % e))
        page.on("console", self._console)
        context.on("request", self._request)

    def _console(self, m):
        if m.type == "error" and not any(p.search(m.text) for p in IGNORED_CONSOLE):
            self.errors.append("console: %s" % m.text)

    def _request(self, r):
        u = r.url
        if not (u.startswith(self.base_url) or u.startswith(("data:", "blob:", "about:", "chrome-extension:"))):
            self.outside.append(u)

    def check(self):
        assert not self.errors, "errors on the page:\n" + "\n".join(self.errors)
        assert not self.outside, "requests to outside servers:\n" + "\n".join(self.outside)


@pytest.fixture
def site(browser, base_url):
    """site(device="desktop", lite=None, path="", wait=2500) -> Watched; checked for errors when the test ends."""
    opened = []

    def open_site(device="desktop", lite=None, path="", wait=2500, **extra):
        ctx = browser.new_context(**{**DEVICES[device], **extra})
        if lite is not None:  # force Lite on or off (the site keeps the choice in localStorage)
            ctx.add_init_script("try{localStorage.setItem('cgcp.lite',%r)}catch(e){}" % ("on" if lite else "off"))
        page = ctx.new_page()
        # Tests run 2 at a time (-n 2) on a 2-core CI runner with no GPU, where a full-3D page can use a whole core.
        # Give page loads and reloads 60 s there (Playwright's default is 30 s; a reload of the 3D home timed out at
        # 30 s on Nov 24, 2026). A load that is fine still returns at once.
        page.set_default_navigation_timeout(60000)
        w = Watched(ctx, page, base_url)
        opened.append(w)
        page.goto(base_url + path)
        page.wait_for_timeout(wait)
        return w

    yield open_site
    try:
        for w in opened:
            w.check()
    finally:
        for w in opened:
            w.context.close()


def open_search(page, text):
    # Ctrl+K is ignored until the launch screen and intro are done; on a slow CI runner that can take a
    # while, so press it again instead of failing on the first try.
    for _ in range(6):
        page.keyboard.press("Control+k")
        try:
            page.wait_for_selector("#srch.on", timeout=5000)
            break
        except Exception:
            continue
    page.wait_for_selector("#srch.on")
    page.fill("#srch-in", text)
    page.wait_for_timeout(350)


def open_guide(page, name="security+"):
    open_search(page, name)
    page.keyboard.press("Enter")
    page.wait_for_selector("#guide #g-obj", state="attached")
    page.wait_for_timeout(800)
