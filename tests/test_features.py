"""The main features work: search, guides, the Explore sheet tabs, privacy page and path sheet."""
import pytest

from conftest import open_guide, open_search


def test_search_acronym_meaning(site):
    p = site().page
    open_search(p, "siem")
    card = p.locator("#srch-list .sr-def")
    assert card.count() == 1
    assert "Security Information and Event Management" in card.inner_text()


def test_search_finds_cert(site):
    p = site().page
    open_search(p, "security+")
    first = p.locator("#srch-list .sr-opt").first
    assert "Security+" in first.inner_text()


@pytest.mark.parametrize("device", ["desktop", "iphone13", "small320"])
def test_security_plus_guide(site, device):
    w = site(device=device)
    p = w.page
    open_guide(p, "security+")
    for sec in ("#g-obj", "#g-plan", "#g-res", "#g-quiz", "#g-pbq", "#g-map", "#g-keep"):
        assert p.locator(sec).count() == 1, sec
    assert "Security+" in p.inner_text("#p-title")
    assert p.locator("#g-doms .g-dd, #g-doms > div").count() >= 5   # 5 exam domains
    over = p.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 1


@pytest.mark.parametrize("name", ["network+", "cissp", "ccna", "sal1", "lpic-1", "aws cloud practitioner"])
def test_other_guides_open(site, name):
    p = site().page
    open_guide(p, name)
    assert p.locator("#g-obj").count() == 1


def test_privacy_page_from_link(site):
    p = site(path="#privacy").page
    p.wait_for_selector("#privacy[open]")
    assert "cookies" in p.inner_text("#privacy").lower()


def test_path_sheet_from_link(site):
    p = site(path="#print").page
    p.wait_for_selector("#psheet[open]")
    assert p.locator("#ps-chips button, #ps-chips [role=checkbox], #ps-chips input").count() >= 1
    assert p.locator("#ps-doc table").count() >= 1


def test_explore_sheet_tabs(site):
    w = site()
    p = w.page
    p.click("#hdr-explore")
    p.wait_for_timeout(800)
    assert p.locator("#sh-grab[aria-expanded=true]").count() == 1
    text = p.inner_text("#sheet")
    for tab in ("Overview", "Career paths", "DoD 8140", "Funding", "Settings"):
        assert tab in text, tab


def test_guide_quiz_to_the_end(site):
    p = site().page
    open_guide(p, "security+")
    for _ in range(12):
        if not p.locator("#g-qgo").count():
            break
        p.locator("#g-qz .g-qo").first.click()
        p.click("#g-qgo")                        # check answer
        p.wait_for_timeout(120)
        if p.locator("#g-qgo").count() and "Check" not in p.inner_text("#g-qgo"):
            p.click("#g-qgo")                    # next question
            p.wait_for_timeout(120)
    text = p.inner_text("#g-qz")
    assert "/10" in text.replace(" ", "") and "Retake quiz" in text, text[:300]


@pytest.mark.parametrize("device", ["iphone13", "small320"])
def test_notch_safe_areas(site, device):
    """iPhone notch and home bar: the header stays below the top inset and the sheet's pull tab above the bottom one."""
    p = site(device=device).page
    p.evaluate("""() => { const s = document.documentElement.style;
        s.setProperty('--sat', '59px'); s.setProperty('--sab', '34px'); dispatchEvent(new Event('resize')); }""")
    p.wait_for_timeout(900)
    top = p.evaluate("document.querySelector('#hdr-search').getBoundingClientRect().top")
    grab = p.evaluate("document.querySelector('#sh-grab').getBoundingClientRect().bottom")
    h = p.evaluate("innerHeight")
    assert top >= 59, "header is under the notch (top %s px)" % top
    assert grab <= h - 34 + 1, "pull tab is under the home bar (bottom %s of %s px)" % (grab, h)
