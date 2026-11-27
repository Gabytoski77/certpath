"""v2.83: guides load when they're opened. index.html keeps only a small index of each guide; the rest is guides/<id>.json."""
import json
import pathlib
import re
from urllib.parse import urlparse

import pytest
from conftest import ROOT, open_guide, open_search, wait_until
from test_offline import _wait_for_sw
from test_readiness import _exam, _seed

INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def _inline():
    a = INDEX.index("var GUIDES={")
    return json.loads(INDEX[a + len("var GUIDES="): INDEX.index("\n};", a) + 2])


def _track(w):
    urls = []
    w.context.on("request", lambda r: urls.append(r.url))
    return urls


def _guide_files(urls):
    """Which guides/<id>.json files were requested (the search file doesn't count as a guide)."""
    return sorted({urlparse(u).path.rsplit("/guides/", 1)[1] for u in urls if "/guides/" in u and not urlparse(u).path.endswith("_search.json")})


def _sw_ready(p):
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(800)


def test_index_has_no_guide_text():
    lead = json.loads((ROOT / "guides/secplus.json").read_text(encoding="utf-8"))["lead"][:70]
    assert lead in (ROOT / "guides/secplus.json").read_text(encoding="utf-8")
    assert lead not in INDEX, "a guide's own text is still inside index.html"
    assert not re.search(r'(?m)^GUIDES\["', INDEX)
    assert len(INDEX) < 1_000_000, len(INDEX)
    g = _inline()["Security+"]
    assert g["lz"] and g["quizN"] > 0 and "quiz" not in g and "pbqs" not in g


def test_opening_a_guide_fetches_only_that_guide(site):
    w = site(lite=True)
    urls = _track(w)
    open_guide(w.page, "ccna")
    g = _inline()["CCNA"]
    assert _guide_files(urls) == ["ccna.json"], _guide_files(urls)
    assert any(u.endswith("guides/ccna.json?h=" + g["lz"]) for u in urls), "the guide address must carry its hash"


@pytest.mark.parametrize("feature", ["compare", "readiness", "continue", "search"])
def test_core_features_work_before_any_guide_is_fetched(site, feature):
    w = site(lite=True)
    p = w.page
    if feature in ("readiness", "continue"):
        _seed(w, "ready")
        if feature == "readiness":      # with a countdown set, the home screen shows the countdown card instead of Continue
            _exam(w, 20)
        p.evaluate("localStorage.setItem('cgcp.last', JSON.stringify({k:'g',g:'Security+',t:Date.now()}))")
        p.reload()
        p.wait_for_timeout(2500)
    urls = _track(w)
    if feature == "compare":
        p.click(".st-links [data-st='vendors']")
        p.wait_for_selector("#cmp .cm-slot", state="attached")
        assert p.locator("#cmp .cm-slot").count() == 2
    elif feature == "readiness":
        p.click(".st-card[data-st='exam']")
        p.wait_for_selector("#ex .ex-rd")
        assert "Ready" in p.inner_text("#ex .ex-rd")
    elif feature == "continue":
        card = p.locator(".st-card[data-st='guide']")
        card.wait_for()
        assert "Security+" in card.inner_text() and "Objectives" in card.inner_text()
    else:
        open_search(p, "security+")
        assert "Security+" in p.inner_text("#srch")
    assert _guide_files(urls) == [], "no guide should have been downloaded: %s" % _guide_files(urls)


def test_search_inside_guides_loads_its_own_file(site):
    w = site(lite=True)
    urls = _track(w)
    open_search(w.page, "port 443")        # words that live inside guides, not in cert names
    w.page.wait_for_function("document.querySelectorAll('#srch .sr-i, #srch [role=option], #srch li').length > 1", timeout=8000)
    assert any("guides/_search.json?h=" in u for u in urls)
    assert _guide_files(urls) == []


def test_offline_after_opening_a_guide_and_message_for_the_others(site):
    w = site(lite=True)          # Lite never downloads the rest in the background, so unopened guides are really unopened
    p = w.page
    _sw_ready(p)
    open_guide(p, "ccna")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(1500)
    w.context.set_offline(True)
    p.reload()
    p.wait_for_timeout(2000)
    open_guide(p, "ccna")                    # opened before: works offline
    p.reload()
    p.wait_for_timeout(2000)
    open_search(p, "isc2 cissp")             # never opened: the friendly message, not a blank panel
    p.keyboard.press("Enter")
    p.wait_for_selector("#guide .g-load-t", timeout=10000)
    t = p.inner_text("#guide .g-load")
    assert "Connect once to download it" in t and "Try again" in t, t
    w.context.set_offline(False)
    w.errors.clear()                    # the failed request while offline is on purpose


def test_failed_fetch_shows_message_and_retry_works(site):
    w = site(lite=True, service_workers="block")
    p = w.page
    w.context.route("**/guides/ccna.json*", lambda r: r.abort())
    open_search(p, "ccna")
    p.keyboard.press("Enter")
    p.wait_for_selector("#guide .g-load-t", timeout=10000)
    assert "Couldn't load this guide" in p.inner_text("#guide .g-load")
    w.context.unroute("**/guides/ccna.json*")
    p.click("#guide .g-load-retry")
    p.wait_for_selector("#guide #g-obj", state="attached", timeout=10000)
    assert p.locator("#guide .g-load").count() == 0
    w.errors.clear()                    # the blocked request is on purpose


def test_loading_and_failed_views_fit_320_in_light_mode(site):
    w = site("small320", lite=True, service_workers="block")
    p = w.page
    assert p.evaluate("document.documentElement.classList.contains('lite')")
    w.context.route("**/guides/ccna.json*", lambda r: r.abort())
    open_search(p, "ccna")
    p.keyboard.press("Enter")
    p.wait_for_selector("#guide .g-load-retry", timeout=10000)
    r = p.evaluate("""()=>{const b=document.querySelector('.g-load-retry').getBoundingClientRect();
      return {r:b.right,l:b.left,w:innerWidth,sw:document.documentElement.scrollWidth}}""")
    assert r["l"] >= 0 and r["r"] <= r["w"] + 0.5 and r["sw"] <= r["w"] + 1, r
    w.errors.clear()                    # the blocked request is on purpose


def test_old_copies_of_a_guide_are_deleted(site, base_url):
    w = site(lite=True)
    p = w.page
    _sw_ready(p)
    p.evaluate("""async (u)=>{const k=(await caches.keys())[0];const c=await caches.open(k);
      await c.put(u+'guides/ccna.json?h=deadbeef', new Response('{}'));}""", base_url)
    open_guide(p, "ccna")
    p.wait_for_timeout(1500)
    keys = p.evaluate("""async ()=>{const out=[];for(const k of await caches.keys()){const c=await caches.open(k);
      for(const r of await c.keys()) if(r.url.includes('guides/ccna.json')) out.push(r.url);}return out;}""")
    assert len(keys) == 1 and keys[0].endswith("?h=" + _inline()["CCNA"]["lz"]), keys


def test_carry_over_matches_guide_addresses_with_their_query_string():
    sw = (ROOT / "sw.js").read_text()
    m = re.search(r"return (/\\/\(qbank.*?\$/)\.test\(new URL\(r\.url\)\.pathname\)", sw)
    assert m, "the carry-over test in sw.js moved"
    rx = re.compile(m.group(1)[1:-1].replace("\\/", "/"))
    for u in ("https://x.test/guides/ccna.json?h=ab12cd34", "https://x.test/guides/_search.json?h=ab12cd34", "https://x.test/qbank/sy0-701.json"):
        assert rx.search(urlparse(u).path), u
    assert not rx.search(urlparse("https://x.test/guides/../index.html").path)


@pytest.mark.xdist_group("3d")
def test_background_download_fetches_the_rest_but_not_in_lite(site):
    n_guides = len(_inline()) + 1
    count = """async ()=>{let n=0;for(const k of await caches.keys()){const c=await caches.open(k);
      for(const r of await c.keys()) if(r.url.includes('/guides/')) n++;}return n;}"""
    w = site(lite=False)
    p = w.page
    _sw_ready(p)
    wait_until(p, "(" + count + ")().then(n => n >= %d)" % n_guides, timeout=120000, every=2000)  # idle download is slower on a busy CI runner
    lite = site(lite=True)
    q = lite.page
    _sw_ready(q)
    q.wait_for_timeout(9000)
    assert q.evaluate(count) == 0, "Lite mode must not download the other guides"
