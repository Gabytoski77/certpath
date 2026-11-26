"""v2.87 Navigation release.

1. Phones: a floating "Jump to" button (thumb reach) lists every guide section; the top bar's row scrolled sideways
   and was easy to miss.
2. Smoother zoom: the color bloom is a Web Animation on transform (compositor), and the vendor page is built after
   the camera stops, so the globe no longer hitches just before the page opens.
3. Links into the app: #guide/<id>/<section> opens a guide at a section; every section heading has a Link button.
4. Share a set by link: #set/<id>/<version>/<ids> carries only question ids; the site looks them up in its own bank.
"""
import json

import pytest

from conftest import ROOT, open_guide, wait_until

LINK = "https://mynextcert.com/"


def _clipboard(w):
    origin = w.page.evaluate("location.origin")
    w.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)


def _read_clipboard(page):
    return wait_until(page, "navigator.clipboard.readText().then(t => t || false)", timeout=8000)


def _section_near_top(page, sec):
    wait_until(page, "(() => {const s = document.querySelector('#g-%s'); if (!s) return false;"
                     " const t = s.getBoundingClientRect().top; return t > 0 && t < 170;})()" % sec, timeout=10000,
               msg="section %s did not scroll to the top" % sec)


# ---------- 1. phone Jump to button ----------

def test_phone_jump_button(site):
    w = site("iphone13")
    p = w.page
    open_guide(p, "security+")
    btn = p.locator("#gj-btn")
    btn.wait_for(state="visible")
    bb = btn.bounding_box()
    assert bb["height"] >= 44, "tap target too small"
    assert bb["x"] + bb["width"] <= 390 - 10 and bb["y"] + bb["height"] <= 664 - 10, bb
    assert bb["x"] > 390 / 2, "should sit on the right, in thumb reach"
    assert p.locator("#gj-n").inner_text() == "01"
    assert btn.get_attribute("aria-label").startswith("Jump to 01")

    btn.click()
    p.wait_for_selector("#gj-list:not([hidden])")
    assert p.locator("#gj-list [data-sec]").count() == 7
    assert p.locator('#gj-list [aria-current="true"]').get_attribute("data-sec") == "obj"
    p.locator('#gj-list [data-sec="pbq"]').click()
    assert p.locator("#gj-list").is_hidden()
    _section_near_top(p, "pbq")
    wait_until(p, "document.getElementById('gj-n').textContent === '05'", timeout=5000)

    # Esc closes the list and leaves the guide open
    btn.click()
    p.wait_for_selector("#gj-list:not([hidden])")
    p.keyboard.press("Escape")
    assert p.locator("#gj-list").is_hidden()
    p.wait_for_timeout(400)
    assert p.locator("#guide #g-obj").count() == 1

    # a tap anywhere else closes it too
    btn.click()
    p.wait_for_selector("#gj-list:not([hidden])")
    p.evaluate("document.getElementById('p-title').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))")
    assert p.locator("#gj-list").is_hidden()

    # leaving the guide removes it
    p.click("#g-nav-back")
    wait_until(p, "!document.getElementById('g-jump')", timeout=8000)


def test_phone_jump_list_fits_320(site):
    w = site("small320")
    p = w.page
    open_guide(p, "network+")
    p.click("#gj-btn")
    p.wait_for_selector("#gj-list:not([hidden])")
    box = p.locator("#gj-list").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 320 and box["y"] >= 0, box
    assert p.evaluate("document.documentElement.scrollWidth <= 320")


def test_no_jump_button_on_desktop(site):
    w = site("desktop")
    p = w.page
    open_guide(p, "security+")
    assert p.locator("#g-jump").count() == 1
    assert p.locator("#gj-btn").is_hidden()


# ---------- 2. smoother zoom ----------

@pytest.mark.xdist_group("3d")
def test_bloom_runs_on_the_compositor(site):
    w = site("desktop", lite=False)
    p = w.page
    p.wait_for_selector("#splash", state="detached", timeout=60000)
    p.wait_for_timeout(1500)
    p.evaluate("""(() => {
      const d = document.querySelector('#flood .fl-d'), pn = document.getElementById('panel'), t0 = performance.now();
      window.__an = null; window.__pt = null;
      const iv = setInterval(() => {
        const a = d.getAnimations();
        if (a.length && !window.__an) window.__an = {t: performance.now() - t0, props: Object.keys(a[0].effect.getKeyframes()[0])};
        if (!pn.hidden && window.__pt === null) window.__pt = performance.now() - t0;
        if (window.__an && window.__pt !== null) clearInterval(iv);
      }, 16);
      document.querySelectorAll('#ro-dots .crest')[0].click();
    })()""")
    wait_until(p, "document.querySelector('#flood.full.solid') && !document.getElementById('panel').hidden", timeout=30000)
    an = p.evaluate("window.__an")
    assert an, "the bloom did not run as a Web Animation"
    props = set(an["props"]) - {"offset", "easing", "composite", "computedOffset"}
    assert props == {"transform"}, "the bloom should animate transform only (compositor), got %s" % props
    assert p.evaluate("window.__pt") > an["t"], "the vendor page should be built after the bloom has started"
    # back to the globe: the bloom shrinks away
    p.keyboard.press("Escape")
    wait_until(p, "!document.getElementById('flood').classList.contains('on')", timeout=30000)


def test_bloom_without_motion(site):
    # Light mode (reduced motion inside the site): no bloom animation, the page opens straight away
    w = site("desktop")
    p = w.page
    p.wait_for_selector("#splash", state="detached", timeout=60000)
    p.locator("#ro-dots .crest").first.click()
    wait_until(p, "document.querySelector('#flood.full.solid') && !document.getElementById('panel').hidden", timeout=10000)
    assert p.evaluate("document.querySelector('#flood .fl-d').getAnimations().length") == 0
    p.keyboard.press("Escape")
    wait_until(p, "!document.getElementById('flood').classList.contains('on')", timeout=10000)


# ---------- 3. section links ----------

def test_section_link_copies_and_opens(site):
    w = site("desktop")
    p = w.page
    _clipboard(w)
    open_guide(p, "security+")
    p.locator('.g-slink[data-slink="pbq"]').click()
    assert _read_clipboard(p) == LINK + "#guide/secplus/pbqs"
    wait_until(p, "document.getElementById('toast').classList.contains('show')", timeout=4000)

    w2 = site("iphone13", path="#guide/secplus/pbqs")
    p2 = w2.page
    p2.wait_for_selector("#guide #g-pbq", state="attached", timeout=60000)
    _section_near_top(p2, "pbq")
    assert p2.evaluate("location.hash") == "", "the link should be cleared so a reload doesn't reopen it"
    wait_until(p2, "document.getElementById('gj-n').textContent === '05'", timeout=5000)


def test_bad_links_are_ignored_safely(site):
    w = site("desktop", path="#guide/not-a-guide/pbqs")
    p = w.page
    p.on("dialog", lambda d: (_ for _ in ()).throw(AssertionError("a dialog opened: " + d.message)))
    wait_until(p, "document.getElementById('toast').textContent.includes(\"doesn't open\")", timeout=20000)
    assert p.locator("#guide").count() == 0

    # markup in a shared-set link is never shown or run: it doesn't even pass the check
    w2 = site("desktop", path="#set/secplus/v7/%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E")
    p2 = w2.page
    p2.on("dialog", lambda d: (_ for _ in ()).throw(AssertionError("a dialog opened: " + d.message)))
    wait_until(p2, "document.getElementById('toast').textContent.includes(\"doesn't open\")", timeout=20000)
    assert p2.locator("#mxp-shared").count() == 0 and p2.locator("img[src='x']").count() == 0

    # a version the guide doesn't have
    w3 = site("desktop", path="#set/secplus/v99/s7-1-01")
    wait_until(w3.page, "document.getElementById('toast').textContent.includes(\"doesn't open\")", timeout=20000)


# ---------- 4. share a set by link ----------

def _bank_ids(n):
    bank = json.loads((ROOT / "qbank" / "sy0-701.json").read_text(encoding="utf8"))
    return [q["id"] for q in bank["q"] if q.get("t") != "pbq"][:n]


def test_shared_bank_set_opens_and_reshares(site):
    ids = _bank_ids(3)
    w = site("desktop", path="#set/secplus/v7/" + "_".join(ids + ["zz-not-real", ids[0]]))
    p = w.page
    _clipboard(w)
    p.wait_for_selector("#mxp-shared", timeout=60000)
    card = p.locator("#mxp-shared").inner_text()
    assert "3 questions" in card and "V7" in card, card   # the unknown id and the repeat are dropped
    _section_near_top(p, "quiz")
    p.click('#mxp-shared [data-mx="shared"]')
    p.wait_for_selector("#mx[open]")
    assert p.locator("#mx-kind").text_content() == "Shared set"
    assert p.locator("#mx-count").inner_text().replace(" ", "") == "1/3"
    assert p.locator("#mxp-shared").count() == 0, "the card goes once the set is started"
    for _ in range(3):
        p.locator("#mx-body .g-qo").first.click()
        p.click("#mx-next")
    p.click("#mx-submit")
    p.wait_for_selector("#mx.done")
    p.click('[data-mxa="share"][data-which="all"]')
    assert _read_clipboard(p) == LINK + "#set/secplus/v7/" + "_".join(ids)
    wait_until(p, "document.querySelector('[data-mxa=\"share\"][data-which=\"all\"]').textContent.includes('copied')", timeout=4000)


def test_quick_set_round_trip(site):
    # share a quick timed set (guide questions), then open that link like a friend would
    w = site("desktop")
    p = w.page
    _clipboard(w)
    open_guide(p, "network+")
    p.click('#mxp [data-mx="quick"]')
    p.wait_for_selector("#mx[open]")
    n = int(p.locator("#mx-count").inner_text().split("/")[1])
    p.click("#mx-revbtn")
    p.click("#mx-submit")
    p.wait_for_selector("#mx.done")
    share = p.locator('[data-mxa="share"][data-which="all"]')
    assert share.count() == 1
    share.click()
    url = _read_clipboard(p)
    assert url.startswith(LINK + "#set/netplus/quiz/") or url.startswith(LINK + "#set/"), url
    assert len(url.split("/")[-1].split("_")) == n

    w2 = site("desktop", path="#" + url.split("#", 1)[1])
    p2 = w2.page
    p2.wait_for_selector("#mxp-shared", timeout=60000)
    assert ("%d questions" % n) in p2.locator("#mxp-shared").inner_text()
    p2.click('#mxp-shared [data-mx="shared"]')
    p2.wait_for_selector("#mx[open]")
    assert p2.locator("#mx-count").inner_text().replace(" ", "") == "1/%d" % n
