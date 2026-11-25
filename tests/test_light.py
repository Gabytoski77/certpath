"""v2.58: Light (the Lite switch, or Graphics set to Light) shows a still picture of the real 3D globe.

Nothing on the home screen is drawn or animated, so slow work computers stay smooth. The pictures come from
build/make_globe_stills.py; if they can't load, the globe is drawn instead.
"""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _requests(w):
    urls = []
    w.context.on("request", lambda r: urls.append(r.url))
    return urls


def test_light_home_is_a_picture(site):
    w = site(device="desktop", lite=True, wait=3000)
    p = w.page
    src = p.get_attribute("#gpic img", "src")
    assert src and src.startswith("img/globe/comptia-") and src.endswith(".webp"), src
    assert p.evaluate("document.querySelector('#gpic img').naturalWidth") >= 1000
    assert p.locator("#gstill").count() == 0, "the drawn globe should only be the fallback"
    assert p.evaluate("typeof THREE") == "undefined"
    scripts = p.evaluate("[...document.scripts].map(s => s.src).filter(Boolean)")
    assert not any(s.endswith("world.js") for s in scripts), "the map outlines aren't needed with the picture"
    # no animations running on the home screen
    assert p.evaluate("document.getAnimations().filter(a => a.playState === 'running').length") == 0
    # the picture sits on the layout's globe: centred within 3% of the radius, the size the views file says
    box = p.evaluate("""(() => {const a=document.getElementById('app'), cs=getComputedStyle(a), r=document.getElementById('gpic').getBoundingClientRect(), ar=a.getBoundingClientRect();
      return {cx:r.left-ar.left+r.width/2, cy:r.top-ar.top+r.height/2, w:r.width, gx:parseFloat(cs.getPropertyValue('--gx')), gy:parseFloat(cs.getPropertyValue('--gy')), gr:parseFloat(cs.getPropertyValue('--gr'))};})()""")
    views = json.loads((ROOT / "img/globe/views.json").read_text())
    c = views["views"]["comptia"]["c"]
    assert abs(box["cx"] - (box["gx"] + c[0] * box["gr"])) < .03 * box["gr"], box
    assert abs(box["cy"] - (box["gy"] + c[1] * box["gr"])) < .03 * box["gr"], box
    assert abs(box["w"] - 2 * views["span"] * c[2] * box["gr"]) < 2, box


def test_light_switching_vendors_swaps_the_picture(site):
    w = site(device="desktop", lite=True, wait=3000)
    p = w.page
    p.keyboard.press("ArrowRight")
    p.wait_for_function("() => (document.querySelector('#gpic img').getAttribute('src')||'').indexOf('img/globe/isc2-') === 0", timeout=5000)
    assert "ISC2" in p.inner_text("#ro-name")
    # the badge tap targets follow the picture: ISC2's own target is live and marked as the front one
    front = p.evaluate("[...document.querySelectorAll('#labels .bl')].findIndex(el => el.classList.contains('front'))")
    assert front == 1, front


def test_light_badge_tap_opens_the_vendor(site):
    w = site(device="desktop", lite=True, wait=3000)
    p = w.page
    # a badge that isn't the front one and isn't behind the side panels (some sit under them, as in the 3D version)
    pick = p.evaluate("""() => [...document.querySelectorAll('#labels .bl')].map((el, i) => {
        const bt = el.querySelector('button'), r = bt.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
        return {i: i, x: x, y: y, ok: !el.classList.contains('off') && !el.classList.contains('front') && document.elementFromPoint(x, y) === bt};
      }).filter(o => o.ok)""")
    assert pick, "no clickable badge besides the front one"
    other, box = pick[0], pick[0]
    p.mouse.click(box["x"], box["y"])
    p.wait_for_function("() => document.getElementById('app').classList.contains('covered')", timeout=5000)
    names = p.evaluate("[...document.querySelectorAll('#ro-dots .crest')].map(b => (b.getAttribute('aria-label')||'').split(': open ')[1])")
    assert names[other["i"]] in p.inner_text("body"), names[other["i"]]

def test_light_falls_back_to_the_drawn_globe(site, browser, base_url):
    """If the pictures can't load (offline before they were ever saved), the globe is drawn instead."""
    from conftest import DEVICES, Watched
    ctx = browser.new_context(**DEVICES["desktop"])
    ctx.add_init_script("try{localStorage.setItem('cgcp.lite','on')}catch(e){}")
    ctx.route("**/img/globe/**", lambda route: route.fulfill(status=404, body="gone"))
    p = ctx.new_page()
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    try:
        p.goto(base_url)
        p.wait_for_selector("#gstill", state="attached", timeout=6000)
        assert p.locator("#gpic").count() == 0
        assert p.evaluate("document.querySelectorAll('#labels .bl:not(.off)').length") == 0
        assert not errors, errors
    finally:
        ctx.close()


@pytest.mark.xdist_group("3d")
def test_graphics_light_is_the_same_still_version(site):
    """Graphics set to Light (not the Lite switch) gives the same still picture and turns off animations."""
    w = site(device="desktop", lite=False, wait=3000)
    p = w.page
    p.evaluate("localStorage.setItem('cgcp.gfx','light')")
    p.reload()
    p.wait_for_timeout(3000)
    assert p.evaluate("document.documentElement.classList.contains('lite')")
    assert (p.get_attribute("#gpic img", "src") or "").startswith("img/globe/")
    assert p.evaluate("typeof THREE") == "undefined"
    assert p.inner_text("#lite-pill").strip().lower() == "light"


def test_every_vendor_has_both_picture_sizes():
    views = json.loads((ROOT / "img/globe/views.json").read_text())
    import re
    src = (ROOT / "src/app.html").read_text(encoding="utf-8")
    block = src[src.index("var VENDORS = ["):src.index("\n];", src.index("var VENDORS = ["))]
    ids = re.findall(r'\{id:"([a-z0-9-]+)"', block)
    assert ids and sorted(ids) == sorted(views["views"]), (ids, list(views["views"]))
    for vid in ids:
        for sz in views["sizes"]:
            f = ROOT / f"img/globe/{vid}-{sz}.webp"
            assert f.exists() and 10_000 < f.stat().st_size < 260_000, f
        for L in views["views"][vid]["labels"]:
            assert 0 <= L["i"] < len(ids) and abs(L["x"]) < views["span"] and abs(L["y"]) < views["span"], (vid, L)
