"""v2.98: "Ready to book" (two full timed practice exams in a row at 85%+) and the Hex Break mark on the launch screen.

Each exam test saves a Security+ run of plain multiple-choice questions with a set number answered right, plus
(optionally) an earlier result in the history, then resumes and submits it through the real page."""
import json, pathlib, time

import pytest
from conftest import open_guide
from test_practice import _submit

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = json.loads((ROOT / "qbank" / "sy0-701.json").read_text(encoding="utf8"))
MCQ = [q for q in BANK["q"] if not q.get("t") and not q.get("kind") and isinstance(q.get("a"), int)][:20]
RB = "#rbook"


def _past(kind, pct, n=100, ago=86400000):
    return {"t": int(time.time() * 1000) - ago, "k": kind, "x": "SY0-701", "n": n, "s": round(n * pct / 100), "by": {}, "u": 600, "d": 5400, "ids": []}


def _run(right, kind="full"):
    items = []
    for k, q in enumerate(MCQ):
        a = q["a"] if k < right else (q["a"] + 1) % len(q["o"])
        items.append({"id": q["id"], "ord": list(range(len(q["o"]))), "pick": a})
    return {"v": 1, "gid": "secplus", "cert": "Security+", "kind": kind, "src": "bank", "ver": "v7", "title": "Security+ V7",
            "items": items, "i": len(items) - 1, "dur": 5400, "used": 60, "t": int(time.time() * 1000)}


def _take(site, right, past=None, kind="full", ready=None, **kw):
    """Submit a saved exam with `right` of 20 correct after `past` earlier results; return the page."""
    p = site(**kw).page
    p.evaluate("([h,r,ready]) => { localStorage.setItem('cgcp.mx.secplus', JSON.stringify(h)); localStorage.setItem('cgcp.mx.run', JSON.stringify(r));"
               " if (ready) localStorage.setItem('cgcp.ready', JSON.stringify(ready)); }", [past or [], _run(right, kind), ready])
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx[open]")
    _submit(p)
    p.wait_for_selector("#mx-body .mx-res", state="attached")
    p.wait_for_timeout(1800)   # the dialog waits for the score to count up
    return p


def _open(p):
    return p.evaluate("document.getElementById('rbook').open")


@pytest.mark.parametrize("before,now,shown", [(84, 18, False), (90, 16, False), (85, 17, True), (100, 20, True)])
def test_two_full_exams_in_a_row_at_85(site, before, now, shown):
    # now = right answers out of 20: 18 = 90%, 16 = 80%, 17 = 85%
    p = _take(site, now, [_past("full", before)])
    assert _open(p) == shown, (before, now)
    if shown:
        assert "Security+" in p.inner_text("#rb-h")
        assert p.get_attribute("#rb-book", "href") == "https://www.pearsonvue.com/us/en/comptia"
        assert "secplus" in json.loads(p.evaluate("localStorage.getItem('cgcp.ready')"))


def test_shorter_practice_sets_do_not_count(site):
    p = _take(site, 20, [_past("full", 95)], kind="half")
    assert not _open(p)
    # and a half exam between two good full exams breaks nothing: only full runs are compared
    p = _take(site, 18, [_past("half", 50, ago=3600000), _past("full", 95)])
    assert _open(p)


def test_shows_once_per_cert(site):
    p = _take(site, 19, [_past("full", 95)], ready=["secplus"])
    assert not _open(p)


def test_tag_stays_after_a_lower_score(site):
    p = _take(site, 14, [_past("full", 90), _past("full", 90)], ready=["secplus"])   # 70% now
    assert not _open(p)
    p.click("#mx [data-mxa='close']")
    p.wait_for_selector("#mx", state="hidden")
    assert p.locator(".g-hero .rb-tag").count() == 1


def test_focus_moves_in_and_back_and_escape_closes(site):
    p = _take(site, 18, [_past("full", 90)])
    assert _open(p)
    assert p.evaluate("document.activeElement.id") == "rb-cool"
    assert p.evaluate("document.getElementById('rbook').getAttribute('aria-labelledby')") == "rb-h"
    p.keyboard.press("Escape")
    p.wait_for_timeout(300)
    assert not _open(p)
    assert p.evaluate("!!document.activeElement.closest('#mx')"), "focus goes back to the exam results"
    # Keep studying closes it too, and it doesn't come back for this cert
    assert json.loads(p.evaluate("localStorage.getItem('cgcp.ready')")) == ["secplus"]


def test_cg_cool_step_opens_the_funding_page(site):
    p = _take(site, 18, [_past("full", 90)])
    p.click("#rb-cool")
    p.wait_for_timeout(1200)
    assert not _open(p) and not p.evaluate("document.getElementById('mx').open")
    assert p.locator("#fp-cool").count() == 1


@pytest.mark.parametrize("kw", [{}, {"lite": False, "reduced_motion": "reduce"}])
def test_no_motion_in_lite_or_reduced(site, kw):
    p = _take(site, 18, [_past("full", 90)], **kw)
    assert _open(p)
    assert p.evaluate("!document.getElementById('rbook').classList.contains('go')")
    names = p.evaluate("[getComputedStyle(document.querySelector('.rb-mark'),'::before').animationName, getComputedStyle(document.querySelector('.rb-mark svg')).animationName]")
    assert names == ["none", "none"], names


def test_ready_key_is_backed_up():
    src = (ROOT / "src" / "app.html").read_text(encoding="utf8")
    import re
    bk = re.search(r"var BK_RE=/(.+?)/, BK_SKIP=/(.+?)/;", src)
    assert re.match(bk.group(1).replace("\\.", r"\."), "cgcp.ready") and not re.match(bk.group(2), "cgcp.ready")


# ---- launch screen: the Hex Break mark ----

@pytest.mark.xdist_group("3d")
def test_mark_draws_on_the_first_load_and_reload_skips_the_splash(site):
    w = site(lite=False, wait=0)
    p = w.page
    p.wait_for_selector("#splash.go", state="attached", timeout=15000)
    assert p.evaluate("getComputedStyle(document.querySelector('.sp-hex')).animationName") == "spHex"
    p.wait_for_selector("#splash", state="detached", timeout=20000)
    t = time.time()
    p.reload()
    p.wait_for_selector("#start", state="attached", timeout=15000)
    assert p.locator("#splash").count() == 0 or p.evaluate("!document.getElementById('splash')"), "a reload in the same visit skips the launch screen"
    assert time.time() - t < 10


@pytest.mark.xdist_group("3d")
def test_mark_is_still_with_reduced_motion(site):
    w = site(lite=False, reduced_motion="reduce")
    ctx = w.page.context
    # a new tab has a fresh visit (sessionStorage), so the launch screen runs again; record the mark before it goes
    ctx.add_init_script("""new MutationObserver(function(){var s=document.getElementById('splash'),h=document.querySelector('.sp-hex');
      if(s&&h&&s.classList.contains('still')&&!window.__still) window.__still=[getComputedStyle(h).strokeDashoffset,getComputedStyle(h).animationName];
    }).observe(document,{subtree:true,childList:true,attributes:true});""")
    p = ctx.new_page()
    p.goto(w.page.url)
    p.wait_for_selector("#splash", state="detached", timeout=20000)
    assert p.evaluate("window.__still") in (["0", "none"], ["0px", "none"])
