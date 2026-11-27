"""v2.66: Light mode polish for slow work PCs.

- The home screen's frame loop goes to sleep when nothing moves (it used to wake 60 times a second).
- Changing vendor never leaves the still globe empty: the old picture stays until the new one is on screen.
- The Explore sheet opens and switches tabs in one step (no fades that lit two tabs at once).
- Laptops at 125-150% scaling get the new 1300 px globe picture instead of the 1600 px one.
"""
import pytest
from conftest import open_guide, wait_until  # noqa: F401  (open_guide keeps the import style of the other test files)

RAF_COUNTER = """() => { window.__raf = 0; const o = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function (cb) { window.__raf++; return o(cb); }; }"""


def test_home_loop_sleeps_in_light_and_wakes_on_input(site):
    w = site(lite=True, wait=4000)
    p = w.page
    p.evaluate(RAF_COUNTER)
    p.mouse.move(3, 3)
    p.wait_for_timeout(1500)            # wakes, then sleeps after about 45 calm frames
    p.evaluate("window.__raf = 0")
    p.wait_for_timeout(2000)
    idle = p.evaluate("window.__raf")
    assert idle <= 3, f"the Light home screen still asked for {idle} frames in 2 s at rest"
    # the wordmark still reacts: moving over it wakes the loop
    p.evaluate("window.__raf = 0")
    box = p.evaluate("(() => { const c = document.getElementById('tt') || document.querySelector('canvas'); const b = c.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; })()")
    for k in range(8):
        p.mouse.move(box[0] + box[2] * (0.25 + k * 0.05), box[1] + box[3] * 0.5)
        p.wait_for_timeout(40)
    assert p.evaluate("window.__raf") > 5


@pytest.mark.xdist_group("3d")
def test_normal_mode_loop_keeps_running(site):
    w = site(lite=False, wait=3000)
    p = w.page
    if "lite" in p.evaluate("document.documentElement.className"):
        pytest.skip("Auto graphics stepped down to Light on this runner")
    p.evaluate(RAF_COUNTER)
    # the 3D globe is slow under software WebGL, but it never stops: wait for the frames, not a fixed time
    wait_until(p, "window.__raf >= 3", timeout=30000, msg="the 3D globe drew fewer than 3 frames in 30 s")


def test_vendor_change_never_leaves_the_globe_empty(site):
    w = site(lite=True, wait=3500)
    p = w.page
    p.evaluate("""() => { window.__empty = 0; window.__seen = 0; const g = document.getElementById('gpic');
      (function tick() { const ok = [...g.querySelectorAll('img')].some(i => i.complete && i.naturalWidth > 0);
        window.__seen++; if (!ok) window.__empty++; requestAnimationFrame(tick); })(); }""")
    crests = p.locator("#ro-dots .crest")
    for i in (3, 5, 1, 6, 2):
        b = crests.nth(i).bounding_box()
        p.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=2)
        p.wait_for_timeout(700)
    assert p.evaluate("window.__seen") > 30
    assert p.evaluate("window.__empty") == 0
    assert p.locator("#gpic img").count() == 1


def test_explore_opens_and_switches_in_one_step_in_light(site):
    w = site(lite=True, wait=3000)
    p = w.page
    p.click("#hdr-explore")
    p.wait_for_timeout(30)
    running = p.evaluate("document.getElementById('sh-scroll').getAnimations().length")
    assert running == 0, "the panel should not fade in Light"
    p.wait_for_timeout(500)
    p.click('#sheet button[aria-selected][data-go="dod"]')
    p.wait_for_timeout(20)
    # only the picked tab is lit, at once
    cols = p.evaluate("[...document.querySelectorAll('#sheet .tabs [data-go]')].map(b => [b.dataset.go, getComputedStyle(b).transitionDuration])")
    assert all(d in ("0s", "0s, 0s") or set(d.replace(" ", "").split(",")) == {"0s"} for _, d in cols), cols
    assert p.evaluate("getComputedStyle(document.getElementById('veil')).transitionDuration").startswith("0s")


@pytest.mark.parametrize("vp,dpr,size", [((1536, 730), 1.25, 1300), ((1280, 620), 1.5, 1300), ((1366, 657), 1, 1000)])
def test_globe_picture_size_for_work_laptops(site, vp, dpr, size):
    w = site(lite=True, wait=3000, viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=dpr)
    p = w.page
    p.wait_for_function("document.querySelector('#gpic img') && document.querySelector('#gpic img').getAttribute('src')", timeout=30000)
    src = p.evaluate("document.querySelector('#gpic img').getAttribute('src')")
    assert src.endswith(f"-{size}.webp"), src
