"""v2.64–v2.65: in-page dropdowns.

On some locked-down work PCs the browser never shows its own pop-up lists (<select> menus, date and
time pickers). On mouse/trackpad devices the site now draws its own list inside the page (#pk), and
the real <select>/<input> keeps the value. Phones keep their native pickers.
"""
import pytest
from conftest import open_guide


def _pk_open(p):
    return p.evaluate("() => { const b = document.getElementById('pk'); return !!b && b.matches(':popover-open'); }")


def _native_open(p, sel):
    return p.evaluate("s => { const e = document.querySelector(s); try { return e.matches(':open'); } catch (x) { return false; } }", sel)


def _click(p, loc):
    loc.scroll_into_view_if_needed()
    p.wait_for_timeout(700)   # let scroll and reveal animations settle
    b = loc.bounding_box()
    p.mouse.click(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    p.wait_for_timeout(250)


@pytest.mark.parametrize("lite", [pytest.param(False, marks=pytest.mark.xdist_group("3d")), True])
def test_guide_pbq_dropdown_opens_in_page(site, lite):
    w = site(lite=lite)
    p = w.page
    open_guide(p, "security+")
    assert p.evaluate("document.documentElement.classList.contains('pk')")
    s = p.locator("#g-pbq select").first
    s.scroll_into_view_if_needed()
    p.wait_for_timeout(700)
    # v2.65: the real <select> never receives the mouse (Edge on locked-down PCs started its own broken list)
    hit = p.evaluate("(() => { const s = document.querySelector('#g-pbq select'), b = s.getBoundingClientRect(); const t = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return [t === s, !!t.closest('.g-sel')]; })()")
    assert hit == [False, True], hit
    _click(p, s)
    assert _pk_open(p), "the in-page list should open on click"
    assert not _native_open(p, "#g-pbq select"), "the browser's own pop-up should not open"
    n_opts = p.evaluate("document.querySelector('#g-pbq select').options.length")
    assert p.locator("#pk [role=option]").count() == n_opts
    # the list sits right under the dropdown and inside the window
    box = p.evaluate("(() => { const b = document.getElementById('pk').getBoundingClientRect(), s = document.querySelector('#g-pbq select').getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom, innerWidth, innerHeight, s.top, s.bottom]; })()")
    assert abs(box[1] - box[7]) < 12 or box[3] <= box[6] + 2, box
    assert box[0] >= 0 and box[2] <= box[4] and box[3] <= box[5] + 1, box
    # pick the second option with the mouse
    want = p.evaluate("document.querySelector('#g-pbq select').options[1].value")
    p.locator("#pk [role=option]").nth(1).click()
    p.wait_for_timeout(200)
    assert not _pk_open(p)
    assert p.evaluate("document.querySelector('#g-pbq select').value") == want
    assert p.evaluate("document.querySelector('#g-pbq select').closest('.g-sel').classList.contains('set')")
    assert p.evaluate("document.activeElement === document.querySelector('#g-pbq select')")


def test_guide_pbq_dropdown_keyboard_and_escape(site):
    w = site()
    p = w.page
    open_guide(p, "security+")
    s = p.locator("#g-pbq select").first
    s.scroll_into_view_if_needed()
    s.focus()
    p.keyboard.press("Enter")
    p.wait_for_timeout(150)
    assert _pk_open(p)
    p.keyboard.press("Escape")
    p.wait_for_timeout(150)
    assert not _pk_open(p)
    assert p.evaluate("document.activeElement === document.querySelector('#g-pbq select')")
    p.keyboard.press("Alt+ArrowDown")
    p.wait_for_timeout(150)
    assert _pk_open(p)
    p.keyboard.press("ArrowDown")
    p.keyboard.press("ArrowDown")
    p.keyboard.press("Enter")
    p.wait_for_timeout(150)
    assert not _pk_open(p)
    want = p.evaluate("document.querySelector('#g-pbq select').options[2].value")
    assert p.evaluate("document.querySelector('#g-pbq select').value") == want
    # clicking somewhere else closes it without changing anything
    _click(p, s)
    assert _pk_open(p)
    p.mouse.click(5, 300)
    p.wait_for_timeout(150)
    assert not _pk_open(p)
    assert p.evaluate("document.querySelector('#g-pbq select').value") == want


def test_practice_exam_pbq_dropdown_inside_the_dialog(site):
    # a saved exam holding one table PBQ: the full exam picks its PBQs at random and can now pick the newer types
    # (log / rules / terminal / diagram), which do not use this dropdown
    import json, pathlib, time
    bank = json.loads((pathlib.Path(__file__).resolve().parent.parent / "qbank" / "sy0-701.json").read_text(encoding="utf8"))
    q = next(x for x in bank["q"] if x["id"] == "s7-p-01")
    item = {"id": q["id"], "ro": list(range(len(q["rows"]))), "co": [list(range(len(o))) for o in q["opts"]],
            "pick": [[-1] * len(q["cols"]) for _ in q["rows"]]}
    run = {"v": 1, "gid": "secplus", "cert": "Security+", "kind": "full", "src": "bank", "ver": "v7", "title": "Security+ V7",
           "items": [item], "i": 0, "dur": 5400, "used": 0, "t": int(time.time() * 1000)}
    w = site()
    p = w.page
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", run)
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(500)
    s = p.locator("#mx-body select").first
    _click(p, s)
    assert _pk_open(p)
    assert p.evaluate("!!document.getElementById('pk').closest('dialog#mx')"), "the list must live inside the exam dialog"
    p.locator("#pk [role=option]").nth(1).click()
    p.wait_for_timeout(200)
    assert p.evaluate("document.querySelector('#mx-body select').value") != "-1"
    assert p.evaluate("document.querySelector('#mx-body .g-sel').classList.contains('set')")
    assert p.locator("#mx[open]").count() == 1, "picking must not close the exam"
    # Escape closes only the list, not the exam
    _click(p, s)
    assert _pk_open(p)
    p.keyboard.press("Escape")
    p.wait_for_timeout(200)
    assert not _pk_open(p)
    assert p.locator("#mx[open]").count() == 1


def _open_countdown(p):
    p.click("#hdr-explore")
    p.wait_for_timeout(800)
    p.click('#sheet button[aria-selected][data-go="exam"]')
    p.wait_for_selector("#ex-c", state="visible")
    p.wait_for_timeout(400)


def test_countdown_exam_date_and_time_pickers(site):
    w = site()
    p = w.page
    _open_countdown(p)
    # exam list keeps the vendor groups
    _click(p, p.locator("#ex-c"))
    assert _pk_open(p)
    assert p.locator("#pk .pk-g").count() >= 3
    p.locator("#pk [role=option]", has_text="Network+").first.click()
    p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('ex-c').value") == "Network+"
    # date: calendar in the page, next month, the 15th
    assert p.locator('[data-pk="ex-d"]').is_visible()
    _click(p, p.locator('[data-pk="ex-d"]'))
    assert _pk_open(p)
    assert p.locator("#pk [role=grid]").count() == 1
    p.click('#pk .pk-nav[aria-label="Next month"]')
    p.wait_for_timeout(150)
    day = p.locator("#pk .pk-d:not(.out):not([disabled])", has_text="15").first
    want = day.get_attribute("data-d")
    day.click()
    p.wait_for_timeout(200)
    assert not _pk_open(p)
    assert p.evaluate("document.getElementById('ex-d').value") == want
    # time: list in 15-minute steps
    _click(p, p.locator('[data-pk="ex-t"]'))
    assert _pk_open(p)
    p.locator("#pk [role=option]", has_text="9:30 AM").first.click()
    p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('ex-t').value") == "09:30"
    assert "Network+" in p.inner_text("#ex-prev") or p.inner_text("#ex-prev").strip()


def test_countdown_calendar_keyboard(site):
    w = site()
    p = w.page
    _open_countdown(p)
    before = p.evaluate("document.getElementById('ex-d').value")
    p.locator("#ex-d").focus()
    p.keyboard.press("Alt+ArrowDown")
    p.wait_for_timeout(150)
    assert _pk_open(p)
    p.keyboard.press("ArrowRight")
    p.keyboard.press("Enter")
    p.wait_for_timeout(150)
    after = p.evaluate("document.getElementById('ex-d').value")
    assert after != before and after > before, (before, after)


def test_phones_keep_native_pickers(site):
    w = site(device="iphone13")
    p = w.page
    assert not p.evaluate("document.documentElement.classList.contains('pk')")
    _open_countdown(p)
    assert not p.locator('[data-pk="ex-d"]').is_visible()
    p.locator("#ex-c").tap()
    p.wait_for_timeout(200)
    assert not _pk_open(p)


def test_countdown_exam_click_hits_wrapper_not_select(site):
    w = site()
    p = w.page
    _open_countdown(p)
    hit = p.evaluate("(() => { const s = document.getElementById('ex-c'), b = s.getBoundingClientRect(); return document.elementFromPoint(b.left + 20, b.top + b.height / 2) === s; })()")
    assert hit is False
    _click(p, p.locator("#ex-c"))
    assert _pk_open(p)
    p.locator("#pk [role=option]", has_text="CySA+").first.click()
    p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('ex-c').value") == "CySA+"
    assert not _pk_open(p)
