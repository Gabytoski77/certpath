"""Service worker: the app installs, works offline, and wrong links show the 404 page."""
from conftest import VERSION_LABEL


def _wait_for_sw(p):
    p.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== null", timeout=15000)


def test_offline_reload(site):
    w = site(wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(1500)
    w.context.set_offline(True)
    p.reload()
    p.wait_for_timeout(2000)
    assert VERSION_LABEL in p.inner_text("body"), "the app did not load offline"
    w.context.set_offline(False)


def test_sw_wrong_link_shows_404(site, base_url):
    w = site(wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.goto(base_url + "no/such/page")
    p.wait_for_timeout(800)
    assert "This page isn" in p.inner_text("body")


def test_sw_version_matches_cache_name():
    import re
    from conftest import ROOT
    sw = (ROOT / "sw.js").read_text()
    assert re.search(r'var VERSION = "certpath-v\d+";', sw)


# ---- v2.80: faster repeat opens, and Light mode no longer saves the 3D map file ----

def _sw_code():
    """sw.js with its /* comments */ removed, so a test can't be fooled by words in a comment."""
    import re
    from conftest import ROOT
    return re.sub(r"/\*.*?\*/", "", (ROOT / "sw.js").read_text(), flags=re.S)


def test_sw_page_fetch_asks_the_server_instead_of_no_store():
    """Opening the app asks 'has it changed?' ("no-cache") so an unchanged page isn't downloaded again.
    The install step keeps "no-store" on purpose, so a fresh install always gets the newest page."""
    code = _sw_code()
    nav = code[code.index('req.mode === "navigate"'):code.index("url.origin === location.origin")]
    assert 'cache: "no-cache"' in nav and "no-store" not in nav, "page opens must revalidate, not skip the cache"
    assert 'redirect: "manual"' in nav, "the redirect rule must stay"
    install = code[code.index('"install"'):code.index('"activate"')]
    assert 'cache: "no-store"' in install, "the install fetch must stay as it was"


def test_sw_page_open_sends_a_has_it_changed_question(site, base_url):
    """In a real browser the service worker's page fetch carries If-Modified-Since / If-None-Match (the question that
    lets GitHub Pages answer '304, nothing changed' with an empty reply)."""
    w = site(wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(1000)
    seen = []
    w.context.on("request", lambda r: seen.append(r))
    p.reload()
    p.wait_for_timeout(1500)
    pages = [r for r in seen if r.resource_type == "document" or r.url in (base_url, base_url + "index.html")]
    assert pages, "no page request seen"
    heads = [{k.lower() for k in r.all_headers()} for r in pages]
    assert any({"if-modified-since", "if-none-match"} & h for h in heads), heads


def test_sw_update_shows_right_away(browser, tmp_path):
    """The real sw.js on a tiny site: change the page on the server and the very next open shows the new page."""
    import functools, http.server, os, shutil, threading, time
    from conftest import ROOT
    shell = __import__("re").findall(r'"([^"]+)"', _sw_code().split("var SHELL")[1].split("];")[0])
    for f in shell:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_bytes(b"x")
    shutil.copy(ROOT / "sw.js", tmp_path / "sw.js")
    page_html = '<!doctype html><title>t</title><p id="v">%s</p><script>navigator.serviceWorker.register("sw.js")</script>'
    (tmp_path / "index.html").write_text(page_html % "first")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("localhost", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://localhost:%d/" % srv.server_address[1]
    ctx = browser.new_context()
    try:
        p = ctx.new_page()
        p.goto(url)
        p.evaluate("navigator.serviceWorker.ready")
        p.reload()
        _wait_for_sw(p)
        assert p.inner_text("#v") == "first"
        (tmp_path / "index.html").write_text(page_html % "second, newer")
        later = time.time() + 30  # file dates only have one-second detail: make sure the server sees a newer file
        os.utime(tmp_path / "index.html", (later, later))
        p.reload()
        assert p.inner_text("#v") == "second, newer", "an update must show on the next open, not a saved copy"
    finally:
        ctx.close()
        srv.shutdown()


def test_sw_does_not_save_world_js_at_install():
    code = _sw_code()
    shell = code.split("var SHELL")[1].split("];")[0]
    assert "world.js" not in shell, "the 3D map file must not be downloaded at install"


def test_light_first_visit_never_downloads_world_js(site):
    """Light mode with the service worker on: after the install finishes, nothing called world.js is in any cache."""
    w = site(lite=True, wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(1500)
    saved = p.evaluate("""async () => { const out = [];
      for (const k of await caches.keys()) { const c = await caches.open(k); for (const r of await c.keys()) out.push(r.url); }
      return out; }""")
    assert saved, "the install should have saved the app's files"
    assert not [u for u in saved if u.endswith("world.js")], saved
