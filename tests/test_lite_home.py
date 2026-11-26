"""v2.85: Lite and home fixes.

- One click or tap on a cert card opens it in Lite (it used to need a double-click).
- Choosing a vendor in Lite never shows two globes, and never leaves none.
- The title doesn't react to the mouse in Lite (it redrew the whole word every frame on slow PCs).
- The globe stays on its spot and the bottom bar stays inside the window at laptop and app-window sizes, including
  when the window changes size after the page has loaded.
- Balanced graphics hold the globe still until you drag it.
"""
import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAM = json.dumps({"c": "Security+", "d": "2099-02-01", "t": "09:00", "w": [1, 3, 5], "h": 1.5, "done": []})
SIZES = [(1536, 730), (1280, 620), (1100, 750), (880, 600)]   # 1080p at 125% and 150%, a Claude-app-like window, 125% of that window


def open_vendor(p, i=0):
    p.evaluate("document.querySelectorAll('.crest')[%d].click()" % i)
    p.wait_for_selector(".flex-fb > *:nth-child(2)", timeout=15000)
    p.wait_for_timeout(700)


def test_lite_one_click_opens_a_card_with_the_mouse(site):
    p = site(lite=True, wait=3000).page
    open_vendor(p)
    p.click(".flex-fb > *:nth-child(2)")
    p.wait_for_selector("#panel.in-guide", timeout=10000)


def test_lite_one_tap_opens_a_card_on_touch(site):
    p = site("iphone13", lite=True, wait=3000).page
    p.evaluate("document.querySelectorAll('.crest')[0].click()")
    p.wait_for_selector(".flex-fb > *:nth-child(2)", timeout=15000)
    p.wait_for_timeout(700)
    p.tap(".flex-fb > *:nth-child(2)")
    p.wait_for_selector("#panel.in-guide", timeout=10000)


def test_lite_dragging_the_row_does_not_open_a_card(site):
    p = site(lite=True, wait=3000).page
    open_vendor(p)
    box = p.locator(".flex-fb > *:nth-child(2)").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    p.mouse.move(x, y)
    p.mouse.down()
    p.mouse.move(x - 120, y, steps=6)
    p.mouse.up()
    p.wait_for_timeout(800)
    assert not p.evaluate("!!document.querySelector('#panel.in-guide')")


def test_lite_vendor_switch_shows_exactly_one_globe_every_frame(site):
    p = site(lite=True, wait=3500).page
    p.evaluate("""() => { window.__g = []; (function f() {
      const d = document.querySelector('#gpic'); const im = d ? [...d.querySelectorAll('img')] : [];
      window.__g.push(im.filter(i => getComputedStyle(i).visibility !== 'hidden').length);
      requestAnimationFrame(f); })(); }""")
    crests = p.query_selector_all(".crest")
    for i in (2, 4, 1, 5, 0):
        crests[i].hover()
        p.wait_for_timeout(700)
    seen = p.evaluate("window.__g")
    assert len(seen) > 100
    assert max(seen) == 1, f"two globes were visible in {sum(1 for n in seen if n > 1)} frames"
    assert min(seen) == 1, "the globe blinked out for a frame"


def test_lite_title_ignores_the_mouse(site):
    p = site(lite=True, wait=3500).page
    box = p.evaluate("(() => { const b = document.getElementById('tt').getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; })()")
    before = p.evaluate("document.getElementById('tt').toDataURL()")
    for row in (0.3, 0.45, 0.6):
        for k in range(12):
            p.mouse.move(box[0] + box[2] * (0.2 + k * 0.05), box[1] + box[3] * row)
            p.wait_for_timeout(25)
    assert p.evaluate("document.getElementById('tt').toDataURL()") == before, "the title redrew under the mouse in Lite"


GEOM = """() => { const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return {l: b.left, t: b.top, r: b.right, b: b.bottom}; };
  return {iw: innerWidth, ih: innerHeight, app: r('#app'), stage: r('#stage'), pic: r('#gpic'), sheet: r('#sheet'), grab: r('#sh-grab'), start: r('#start')}; }"""


def check_layout(g, where):
    assert g["sheet"]["r"] <= g["iw"] + 0.5 and g["sheet"]["l"] >= -0.5, f"{where}: the bottom bar sticks out sideways {g['sheet']}"
    assert g["grab"]["b"] <= g["ih"] + 1.5, f"{where}: the bottom bar is cut off at the bottom {g['grab']}"
    assert abs((g["sheet"]["l"] + g["sheet"]["r"]) / 2 - g["iw"] / 2) <= 1.5, f"{where}: the bottom bar is off center"
    assert abs(g["grab"]["t"] - g["app"]["b"]) <= 3, f"{where}: the bottom bar isn't right under the app {g['grab']} {g['app']}"
    sc = (g["stage"]["l"] + g["stage"]["r"]) / 2
    if g["pic"]:
        assert abs((g["pic"]["l"] + g["pic"]["r"]) / 2 - sc) <= 3, f"{where}: the globe isn't centered on its spot {g['pic']} {g['stage']}"
    assert g["start"]["r"] <= g["stage"]["l"] + g["stage"]["r"] and g["start"]["l"] >= 0, f"{where}: the start card left the window"


@pytest.mark.parametrize("w,h", SIZES)
def test_home_layout_at_laptop_and_app_window_sizes(site, w, h):
    s = site(lite=True, viewport={"width": w, "height": h}, wait=500)
    p = s.page
    p.evaluate("localStorage.setItem('cgcp.exam', %r)" % EXAM)
    p.reload()
    p.wait_for_timeout(3000)
    check_layout(p.evaluate(GEOM), f"{w}x{h}")


def test_globe_follows_the_window_when_it_changes_size_after_load(site):
    s = site(lite=True, viewport={"width": 1920, "height": 950}, wait=500)
    p = s.page
    p.evaluate("localStorage.setItem('cgcp.exam', %r)" % EXAM)
    p.reload()
    p.wait_for_timeout(3000)
    for w, h in [(1280, 620), (1536, 730), (1100, 750), (1920, 950)]:
        p.set_viewport_size({"width": w, "height": h})
        p.wait_for_timeout(900)
        check_layout(p.evaluate(GEOM), f"resized to {w}x{h}")


def test_balanced_globe_is_set_to_hold_still():
    src = (ROOT / "src" / "app.html").read_text(encoding="utf8")
    assert "AUTO=(reduced||GFX.tier>=1)?0:0.085" in src, "only High may turn the globe by itself"
    assert "if(t>=1) AUTO=0;" in src, "stepping down to Balanced must stop the spin"
    assert "GFX.tier===1&&fps<40?2" in src
