"""v2.97: home "Pick up where you left off" card (reads only cgcp.resume) and the retiring-soon banner."""
import json
import re

import pytest

from conftest import open_guide, wait_until

CARD = ".st-card[data-st='guide']"


def _set(p, key, value):
    p.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, value if isinstance(value, str) else json.dumps(value)])
    p.reload()
    p.wait_for_timeout(2000)


def _rec(**kw):
    r = {"n": "Security+", "p": 40, "s": 82, "o": {"id": "1-2", "t": "Compare threat actors"}, "all": False, "t": 1760000000000}
    r.update(kw)
    return r


def _home(site):
    w = site(lite=True)
    # a returning visitor: the old "last opened" marker is there too
    w.page.evaluate("localStorage.setItem('cgcp.last', JSON.stringify({k:'g',g:'Security+',t:Date.now()}))")
    return w


def test_no_record_means_no_card(site):
    p = _home(site).page
    p.reload()
    p.wait_for_timeout(1500)
    assert p.locator(CARD).count() == 0


def test_card_with_score_and_next_objective(site):
    p = _home(site).page
    _set(p, "cgcp.resume", _rec())
    t = p.locator(CARD).inner_text()
    assert "Security+" in t and "Last exam 82%" in t and "Compare threat actors" in t
    assert p.locator(CARD).evaluate("e => e.tagName") == "BUTTON"
    assert "Continue" in p.locator(CARD).get_attribute("aria-label")
    assert p.locator(CARD + " .k").inner_text().lower().startswith("pick up")
    assert not p.locator(".st-card [aria-label*='ismiss'], .st-card .x").count(), "no dismiss button"


@pytest.mark.parametrize("score", [None, 0])
def test_card_leaves_out_a_missing_score_and_never_shows_zero(site, score):
    p = _home(site).page
    _set(p, "cgcp.resume", _rec(s=score))
    t = p.locator(CARD).inner_text()
    assert "Compare threat actors" in t and "Last exam" not in t and "0%" not in t


def test_card_when_every_objective_is_ticked(site):
    p = _home(site).page
    _set(p, "cgcp.resume", _rec(o=None, all=True, p=100))
    t = p.locator(CARD).inner_text()
    assert "Take a practice exam" in t and "Next:" not in t
    p.locator(CARD).click()
    p.wait_for_selector("#guide #mxp", state="attached", timeout=60000)
    wait_until(p, "!!document.querySelector('#mxp') && document.querySelector('#mxp').contains(document.activeElement)", timeout=15000)


def test_continue_opens_the_guide_at_the_objective(site):
    p = _home(site).page
    _set(p, "cgcp.resume", _rec(o={"id": "1-0", "t": "x"}))
    p.locator(CARD).click()
    p.wait_for_selector("#guide #g-obj", state="attached", timeout=60000)
    wait_until(p, "document.activeElement && document.activeElement.dataset.id==='1-0'", timeout=15000)
    assert p.evaluate("document.activeElement.closest('.g-dom').classList.contains('open')")


@pytest.mark.parametrize("bad", ["{not json", "[]", "null", '"x"', json.dumps({"n": "No such cert", "t": 1, "all": True}),
                                 json.dumps({"n": "Security+", "t": 1, "all": False, "o": {"id": "<img>", "t": "x"}}),
                                 json.dumps({"n": "Security+", "t": "yesterday", "all": True}), json.dumps({"n": 5})])
def test_broken_stored_data_hides_the_card_quietly(site, bad):
    w = _home(site)
    _set(w.page, "cgcp.resume", bad)
    assert w.page.locator(CARD).count() == 0
    assert w.page.locator("#st-act button").count() == 1   # the normal Build my path button, no error


def test_opening_a_guide_and_ticking_writes_the_record(site):
    p = site("desktop").page
    open_guide(p, "security+")
    r = json.loads(p.evaluate("localStorage.getItem('cgcp.resume')"))
    assert r["n"] == "Security+" and r["s"] is None and r["all"] is False and r["o"]["id"] == "0-0"
    p.locator("#g-doms .g-ck").first.evaluate("e => e.click()")
    r = json.loads(p.evaluate("localStorage.getItem('cgcp.resume')"))
    assert r["o"]["id"] == "0-1" and r["p"] > 0
    p.locator("#g-doms .g-ck").first.evaluate("e => e.click()")
    assert json.loads(p.evaluate("localStorage.getItem('cgcp.resume')"))["o"]["id"] == "0-0"


def test_resume_key_survives_backup_and_restore(site):
    p = site("desktop").page
    rec = json.dumps(_rec())
    p.evaluate("([v]) => localStorage.setItem('cgcp.resume', v)", [rec])
    p.evaluate("document.getElementById('bk-copy').click()")
    wait_until(p, "document.getElementById('bk-out').value.length>0", timeout=8000)
    text = p.evaluate("document.getElementById('bk-out').value")
    assert "cgcp.resume" in text
    p.evaluate("localStorage.removeItem('cgcp.resume')")
    p.evaluate("([t]) => { const a=document.getElementById('bk-ta'); a.value=t; document.getElementById('bk-check').click(); }", [text])
    p.evaluate("document.getElementById('bk-yes').click()")
    p.wait_for_timeout(2500)
    assert json.loads(p.evaluate("localStorage.getItem('cgcp.resume')")) == json.loads(rec)


# ---- retiring-soon banner. The list has CySA+ V3 on 2026-12-22; the page clock is moved to test each distance. ----
RT = "#st-ret .st-rt"


def _at(site, iso_day, extra=None):
    w = site(lite=True)
    p = w.page
    p.clock.install(time=iso_day + "T12:00:00")
    for k, v in (extra or {}).items():
        p.evaluate("([k, v]) => localStorage.setItem(k, v)", [k, v])
    p.reload()
    p.wait_for_timeout(2000)
    return p


# 2026-12-22 minus N days
@pytest.mark.parametrize("day,days,shown", [("2026-09-22", 91, False), ("2026-09-23", 90, True), ("2026-12-21", 1, True),
                                           ("2026-12-22", 0, True), ("2026-12-23", -1, False)])
def test_banner_window(site, day, days, shown):
    p = _at(site, day)
    assert (p.locator(RT).count() == 1) == shown, days
    if shown:
        t = p.locator(RT).inner_text()
        assert "CySA+" in t and "2026-12-22" in t
        a = p.locator(RT + " a")
        assert a.get_attribute("href").startswith("https://www.comptia.org/") and "noopener" in a.get_attribute("rel")


def test_closing_the_banner_is_remembered_and_another_cert_still_shows(site):
    p = _at(site, "2026-12-01")                    # CySA+ (21 days) only; Security+ is 192 days out
    assert p.locator(RT).count() == 1
    p.locator(RT + " button").click()
    assert p.locator(RT).count() == 0 and p.locator("#st-ret").is_hidden()
    p.reload()
    p.wait_for_timeout(1500)
    assert p.locator(RT).count() == 0, "stays closed after a reload"
    # 2027-04-01: Security+ V7 (2027-06-11) is 71 days away, CySA+ is over; its own banner shows
    p.clock.install(time="2027-04-01T12:00:00")
    p.reload()
    p.wait_for_timeout(1500)
    assert p.locator(RT).count() == 1 and "Security+" in p.locator(RT).inner_text()


def test_switch_defaults_on_and_off_renders_nothing():
    """showRetiringBanner lives in the page's script (the CSP hashes it), so an off page can't be served edited: check the code path."""
    src = open("src/app.html", encoding="utf-8").read()
    assert "SITE_CONFIG={showRetiringBanner:true}" in src, "default is on"
    body = src[src.index("function rtRender(){"):src.index("rtRender();\n(function(){")]
    # with the switch false, html stays "" and n stays 0: the element is emptied and hidden
    assert 'html="", n=0' in body and "if(SITE_CONFIG.showRetiringBanner){" in body and "el.innerHTML=html;el.hidden=!n;" in body
