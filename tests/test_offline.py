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
