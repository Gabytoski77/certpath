"""Update C (v2.78): the What's new dialog and the "Facts last checked" date on every guide."""
import datetime
import importlib.util
import pathlib
import re

import pytest
from conftest import open_guide
from test_a11y import _axe, _check

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def _btn(p):
    return p.locator(".wn-btn:visible").first


def _open(p):
    _btn(p).click()
    p.wait_for_selector("#wnew[open]")


def _versions(p):
    return p.eval_on_selector_all("#wn-list .wn-v", "els=>els.map(e=>e.textContent)")


def test_opens_and_closes(site):
    p = site("desktop").page
    _open(p)
    assert p.is_visible("#wn-h")
    p.click("#wn-x")
    assert not p.evaluate("document.getElementById('wnew').open")
    _open(p)
    p.keyboard.press("Escape")
    assert not p.evaluate("document.getElementById('wnew').open"), "Esc should close it"
    _open(p)
    p.mouse.click(5, 5)   # tap outside the card
    assert not p.evaluate("document.getElementById('wnew').open")


def test_keyboard_opens_it(site):
    p = site("desktop").page
    _btn(p).focus()
    p.keyboard.press("Enter")
    p.wait_for_selector("#wnew[open]")
    assert p.evaluate("document.getElementById('wnew').contains(document.activeElement)"), "focus moves into the dialog"
    p.keyboard.press("Escape")
    assert p.evaluate("document.activeElement.classList.contains('wn-btn')"), "focus returns to the button"


def test_dot_clears_after_opening(site):
    w = site("desktop")
    p = w.page
    assert p.locator(".wn-btn.new:visible").count() >= 1, "a new visitor sees the dot"
    assert "new updates" in (p.locator(".wn-btn:visible .wn-vh").first.text_content() or "")
    _open(p)
    assert p.locator(".wn-btn.new").count() == 0, "the dot goes away once it has been opened"
    assert p.evaluate("localStorage.getItem('cgcp.wn')") == _versions(p)[0].lstrip("v")  # the newest entry, whatever release this is
    p.keyboard.press("Escape")
    p.reload()
    p.wait_for_timeout(1500)
    assert p.locator(".wn-btn.new").count() == 0, "and stays gone after a reload"
    # an older "last seen" version (an update happened since) brings the dot back
    p.evaluate("localStorage.setItem('cgcp.wn','2.77')")
    p.reload()
    p.wait_for_timeout(1500)
    assert p.locator(".wn-btn.new:visible").count() >= 1


def test_list_is_newest_first(site):
    p = site("desktop").page
    _open(p)
    vs = _versions(p)
    assert 1 <= len(vs) <= 8
    nums = [tuple(int(x) for x in v.lstrip("v").split(".")) for v in vs]
    assert nums == sorted(nums, reverse=True), vs
    dates = p.eval_on_selector_all("#wn-list time", "els=>els.map(e=>e.getAttribute('datetime'))")
    assert dates == sorted(dates, reverse=True), dates
    label = re.search(r"<span>v\.(2\.\d+)</span>", INDEX).group(1)
    assert vs[0] == "v" + label, "the newest entry must match the visible version label"
    for line in p.eval_on_selector_all("#wn-list .wn-t", "els=>els.map(e=>e.textContent)"):
        assert line.strip() and len(line) < 200


@pytest.mark.parametrize("device", ["small320", "zoom200"])
def test_fits_small_screens(site, device):
    p = site(device).page
    _open(p)
    r = p.evaluate("""()=>{var d=document.getElementById('wnew'),b=d.getBoundingClientRect();
      return {l:b.left,r:b.right,t:b.top,b:b.bottom,w:innerWidth,h:innerHeight,sw:d.scrollWidth,cw:d.clientWidth,
              x:document.getElementById('wn-x').getBoundingClientRect().right}}""")
    assert r["l"] >= 0 and r["r"] <= r["w"] + 0.5 and r["t"] >= 0 and r["b"] <= r["h"] + 0.5, r
    assert r["sw"] <= r["cw"] + 1, "no sideways scrolling inside the dialog: %r" % r
    p.evaluate("document.getElementById('wnew').scrollTop=1e5")   # long content scrolls, last entry is reachable
    assert p.is_visible("#wn-list li:last-child")


@pytest.mark.parametrize("opts", [dict(device="desktop"), dict(device="desktop", lite=True), dict(device="reduced")])
def test_axe_clean_in_normal_light_and_reduced_motion(site, opts):
    p = site(**opts).page
    _open(p)
    _check(_axe(p), "whats-new")
    if opts.get("lite"):
        assert p.evaluate("document.documentElement.classList.contains('lite')")


def test_dot_does_not_animate(site):
    p = site("reduced").page
    names = p.evaluate("[...document.querySelectorAll('.wn-dot, #wnew, #wnew *')].map(e=>getComputedStyle(e).animationName)")
    assert set(names) <= {"none"}


# ---- fact-check dates ----
GUIDE_ISO = re.compile(r'"checked":"(\d{4}-\d{2}-\d{2})"')   # the guide index inside index.html is plain JSON (v2.83)


def test_every_guide_has_an_iso_checked_date():
    a = INDEX.index("var GUIDES={")
    dates = GUIDE_ISO.findall(INDEX[a:INDEX.index("\n};", a)])
    assert len(dates) >= 38, len(dates)
    today = datetime.date.today()
    for s in dates:
        d = datetime.date.fromisoformat(s)
        assert d <= today + datetime.timedelta(days=1), s


@pytest.mark.parametrize("name", ["security+", "ccna", "isc2 cissp"])
def test_guide_shows_fact_check_date(site, name):
    p = site("desktop").page
    open_guide(p, name)
    t = p.text_content(".g-chk")
    assert re.search(r"Facts last checked: [A-Z][a-z]{2} \d{1,2}, 202\d", t), t
    assert "checked monthly against the vendor" in t
    iso = p.get_attribute(".g-chk time", "datetime")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso)


def test_guide_fact_check_fits_320(site):
    p = site("small320").page
    open_guide(p, "security+")
    r = p.evaluate("""()=>{var c=document.querySelector('.g-chk').getBoundingClientRect();
      return {r:c.right,w:innerWidth,sw:document.documentElement.scrollWidth}}""")
    assert r["r"] <= r["w"] + 0.5 and r["sw"] <= r["w"] + 1, r


# ---- the checker itself ----
def _checker(tmp_path, monkeypatch, html):
    spec = importlib.util.spec_from_file_location("check_site_t", ROOT / ".github" / "scripts" / "check_site.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    m.failures.clear()
    m.check_guide_dates()
    return m.failures


def test_checker_passes_real_site(tmp_path, monkeypatch):
    assert _checker(tmp_path, monkeypatch, INDEX) == []


def test_checker_fails_missing_bad_and_future(tmp_path, monkeypatch, capsys):
    future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    html = INDEX.replace('"checked":"', '"checkedX":"', 1)                       # one guide loses its field
    html = re.sub(r'"checked":"\d{4}-\d{2}-\d{2}"', '"checked":"Nov 6, 2026"', html, count=1)   # one bad format
    html = re.sub(r'(?m)^("Network\+":\{.*?"checked":)"[^"]*"', r'\1"%s"' % future, html, count=1)
    f = _checker(tmp_path, monkeypatch, html)
    text = "\n".join(f)
    assert "no checked" in text or "bad checked date" in text, text
    assert "future" in text, text


def test_checker_only_warns_when_old(tmp_path, monkeypatch, capsys):
    html = re.sub(r'"checked":"\d{4}-\d{2}-\d{2}"', '"checked":"2026-01-02"', INDEX, count=1)
    assert _checker(tmp_path, monkeypatch, html) == []
    assert "WARN" in capsys.readouterr().out
