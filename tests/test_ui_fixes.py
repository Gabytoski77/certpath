"""v2.96: six small navigation fixes.

1. Guide header (laptop): the empty outlined box is now the logo, a button that goes home.
2. Phones: the floating "Jump to" button hides while you scroll down and returns on scroll up or near the end.
3. Laptop guide facts row: the DoD 8140 value fits its card.
4. Search: a cert with two practice exams shows the version in each title.
5. The bottom bar says what it is for.
6. Phone vendor row: a fade shows which side still has badges.
"""
import pytest

from conftest import open_guide, open_search, wait_until


def _scroll(p, y):
    p.evaluate("document.getElementById('panel').scrollTop=%d" % y)
    p.wait_for_timeout(500)


def _away(p):
    return p.evaluate("document.getElementById('g-jump').classList.contains('gj-away')")


def test_guide_logo_is_a_home_button(site):
    p = site("desktop").page
    open_guide(p, "security+")
    b = p.locator("#p-mark")
    assert b.evaluate("e => e.tagName") == "BUTTON"
    assert b.get_attribute("aria-label") == "MyNextCert home"
    assert b.locator("svg").count() == 1
    b.click()
    wait_until(p, "!document.querySelector('#panel.in-guide')", timeout=10000)


@pytest.mark.parametrize("device", ["iphone13", "small320"])
def test_jump_button_hides_on_scroll_down_and_returns(site, device):
    p = site(device).page
    open_guide(p, "security+")
    p.locator("#gj-btn").wait_for(state="visible")
    _scroll(p, 600)
    _scroll(p, 1500)
    assert _away(p)
    assert p.locator("#gj-btn").is_hidden()
    _scroll(p, 1300)
    assert not _away(p)
    p.locator("#gj-btn").wait_for(state="visible")
    _scroll(p, 600)
    _scroll(p, 1500)
    assert _away(p)
    _scroll(p, 10 ** 6)   # the very end
    assert not _away(p)
    # at the end nothing sits under the button: the last line ends above it
    r = p.evaluate("""() => { const b = document.getElementById('gj-btn').getBoundingClientRect();
      const f = document.querySelector('.p-foot').getBoundingClientRect(); return [f.bottom, b.top]; }""")
    assert r[0] <= r[1] + 1, r


def test_jump_button_reduced_motion_has_no_transition(site):
    p = site("iphone13", reduced_motion="reduce").page
    open_guide(p, "security+")
    p.locator("#gj-btn").wait_for(state="visible")
    # the site's reduced-motion rule leaves only a short fade: nothing slides
    assert "transform" not in p.evaluate("getComputedStyle(document.getElementById('g-jump')).transitionProperty")
    _scroll(p, 600)
    _scroll(p, 1500)
    assert _away(p)


@pytest.mark.parametrize("w", [1440, 1280])
def test_facts_row_values_fit_their_cards(site, w):
    ctx = site("desktop")
    p = ctx.page
    p.set_viewport_size({"width": w, "height": 900})
    open_guide(p, "security+")
    bad = p.evaluate("""() => [...document.querySelectorAll('.g-facts div')].map(d => {
      const b = d.querySelector('b'), r = d.getBoundingClientRect(), t = b.getBoundingClientRect();
      return [b.textContent, b.scrollWidth > b.clientWidth + 1 || t.right > r.right + 0.5, parseFloat(getComputedStyle(b).fontSize)]; })
      .filter(x => x[1] || x[2] < 14)""")
    assert not bad, bad
    assert p.evaluate("[...document.querySelectorAll('.g-facts b')].some(b => /8140|Intermediate/.test(b.closest('div').textContent))")


def test_search_titles_show_the_exam_version(site):
    p = site("desktop").page
    open_search(p, "security+ practice exam")
    names = p.evaluate("[...document.querySelectorAll('#srch-list .sr-opt')].map(e => e.textContent)")
    mine = [n for n in names if "practice exam" in n]
    assert any("V8 (new)" in n for n in mine), mine
    assert any("V7 (older)" in n for n in mine), mine
    p2 = site("desktop").page
    open_search(p2, "a+ practice exam")
    t = p2.evaluate("[...document.querySelectorAll('#srch-list .sr-opt')].map(e => e.textContent).filter(x => /practice exam/.test(x)).join('|')")
    assert "A+ practice exam · Core 1" in t and "A+ practice exam · Core 2" in t and "(new)" not in t, t


@pytest.mark.parametrize("device,word", [("desktop", "Click"), ("iphone13", "Swipe up"), ("small320", "Swipe up")])
def test_bottom_bar_hint(site, device, word):
    p = site(device).page
    h = p.locator("#sh-hint")
    assert h.inner_text().startswith(word + ": career paths, 8140 roles, CG funding")
    r = p.evaluate("""() => { const h = document.getElementById('sh-hint'), g = document.getElementById('sh-grab');
      const a = h.getBoundingClientRect(), b = g.getBoundingClientRect();
      return [h.scrollWidth > h.clientWidth, a.height < 14, a.left >= 0, a.right <= innerWidth, a.bottom <= b.bottom + 0.5]; }""")
    assert all(r[1:]) and not r[0], r


@pytest.mark.parametrize("device", ["iphone13", "small320"])
def test_vendor_row_fades_where_badges_are_hidden(site, device):
    p = site(device).page
    cls = lambda: p.evaluate("document.getElementById('ro-dots').className")
    wait_until(p, "document.getElementById('ro-dots').classList.contains('fr')", timeout=8000)
    assert "fl" not in cls().split()
    p.evaluate("(d => { d.style.scrollSnapType = 'none'; d.scrollLeft=(d.scrollWidth-d.clientWidth)/2; })(document.getElementById('ro-dots'))")
    p.wait_for_timeout(300)
    assert {"fl", "fr"} <= set(cls().split())
    assert p.evaluate("getComputedStyle(document.getElementById('ro-dots')).maskImage").startswith("linear-gradient")
    p.evaluate("document.getElementById('ro-dots').scrollLeft=1e6")
    p.wait_for_timeout(300)
    c = cls().split()
    assert "fl" in c and "fr" not in c
