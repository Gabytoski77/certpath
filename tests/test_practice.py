import pytest
"""Practice exams: quick timed set start to finish, the full V7 exam setup, and saved results."""
from conftest import open_guide


def _answer_all(p, limit=120):
    """Pick the first option on every question and press Next until the exam can be submitted."""
    for _ in range(limit):
        opt = p.locator("#mx-body .g-qo").first
        if opt.count():
            opt.click()
        label = p.inner_text("#mx-next")
        if "Submit" in label or "Review" in label or "Finish" in label:
            return label
        p.click("#mx-next")
        p.wait_for_timeout(60)
    raise AssertionError("never reached the end of the exam")


def _submit(p):
    """From the last question, get to the results (through the review screen if there is one)."""
    for _ in range(4):
        if p.locator("#mx-body .mx-res, #mx-body [class*=result], #mx-body [class*=score]").count():
            return
        btns = p.locator("#mx button:visible", has_text="Submit")
        if btns.count():
            btns.last.click()
        else:
            p.click("#mx-next")
        p.wait_for_timeout(500)
        # a confirm step inside the dialog (unanswered/flagged questions)
        confirm = p.locator("#mx button:visible", has_text="Submit exam")
        if confirm.count():
            confirm.last.click()
            p.wait_for_timeout(500)


def test_quick_timed_set(site):
    w = site()
    p = w.page
    open_guide(p, "security+")
    p.click('#mxp [data-mx="quick"]')
    p.wait_for_selector("#mx[open]")
    assert p.inner_text("#mx-count").strip().endswith("/ 10")
    assert ":" in p.inner_text("#mx-time")      # the timer runs
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, "no score shown after submitting:\n" + body[:500]
    # the run is saved for the history and weak-spot tracker
    keys = p.evaluate("Object.keys(localStorage)")
    assert any(k.startswith("cgcp.mx.") for k in keys), keys
    assert any(k.startswith("cgcp.ws.") for k in keys), keys


def test_full_v7_exam_setup(site):
    w = site()
    p = w.page
    open_guide(p, "security+")
    p.click('#mxp [data-mx="full"][data-ver="v7"]')
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("89:", "90:", "1:29", "1:30")), t
    # PBQs come first: the first item is not a plain 4-option MCQ list
    assert p.locator("#mx-body .g-qo").count() == 0 or "PBQ" in p.inner_text("#mx-body").upper()
    # Esc closes the exam and keeps it for later (resume banner)
    p.keyboard.press("Escape")
    p.wait_for_timeout(700)
    assert p.evaluate("document.getElementById('mx').open") is False
    assert p.evaluate("localStorage.getItem('cgcp.mx.run')") is not None


def test_question_bank_rejects_bad_path(site, base_url):
    """Only qbank/<name>.json on this site can be loaded as a bank."""
    w = site()
    r = w.page.request.get(base_url + "qbank/sy0-701.json")
    assert r.status == 200 and r.json().get("format")


def test_network_plus_v9_full_exam(site):
    """v2.50: the Network+ V9 bank loads, builds a full 90-item exam with PBQs, and scores every domain."""
    w = site()
    p = w.page
    open_guide(p, "network+")
    full = p.locator('#mxp [data-mx="full"][data-ver="v9"]')
    assert full.count() == 1, p.inner_text("#mxp")[:400]
    full.click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, "no score shown after submitting:\n" + body[:500]
    for dom in ("Networking Concepts", "Network Implementation", "Network Operations",
                "Network Security", "Network Troubleshooting"):
        assert dom in body, f"{dom} missing from the results"
    assert any(k.startswith("cgcp.mx.") and "net" in k for k in p.evaluate("Object.keys(localStorage)"))


def test_aplus_core1_full_exam(site):
    """v2.52: A+ has two exams in one guide. Core 1 gets a full exam from its own bank."""
    w = site()
    p = w.page
    open_guide(p, "a+")
    mxp = p.inner_text("#mxp")
    full = p.locator('#mxp [data-mx="full"][data-ver="core1"]')
    assert full.count() == 1, mxp[:500]
    full.click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    assert "220-1201" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Mobile Devices", "Networking", "Hardware", "Virtualization and Cloud Computing",
                "Hardware and Network Troubleshooting"):
        assert dom in body, f"{dom} missing from the results"
    assert "Operating Systems" not in body      # Core 2 domain names must not leak into Core 1 results


def test_aplus_core2_full_exam(site):
    """v2.53: Core 2 gets its own bank, so both A+ exams have full and half exams and no "coming later" note."""
    w = site()
    p = w.page
    open_guide(p, "a+")
    mxp = p.inner_text("#mxp")
    for ver in ("core1", "core2"):
        assert p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').count() == 1, mxp[:500]
        assert p.locator(f'#mxp [data-mx="half"][data-ver="{ver}"]').count() == 1, mxp[:500]
    assert "later update" not in mxp, mxp[:600]
    p.locator('#mxp [data-mx="full"][data-ver="core2"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    assert "220-1202" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Operating Systems", "Security", "Software Troubleshooting", "Operational Procedures"):
        assert dom in body, f"{dom} missing from the results"
    assert "Virtualization and Cloud Computing" not in body   # Core 1 domain names must not leak into Core 2 results
    assert any(k.startswith("cgcp.mx.") and "aplus" in k for k in p.evaluate("Object.keys(localStorage)"))


def test_cysa_v4_full_exam(site):
    """v2.54: CySA+ V4 gets an 85-question, 165-minute bank. V3 is retiring, so its note says it won't get one."""
    w = site()
    p = w.page
    open_guide(p, "cysa+")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v4"]').count() == 1, mxp[:500]
    assert p.locator('#mxp [data-mx="full"][data-ver="v3"]').count() == 0
    assert "CS0-003" in mxp and "being retired" in mxp and "later update" not in mxp, mxp[:800]
    p.locator('#mxp [data-mx="full"][data-ver="v4"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 85")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("2:44:", "2:45:")), t
    assert "CS0-004" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Security Operations", "Vulnerability Management", "Incident Response and Management",
                "Reporting and Communication"):
        assert dom in body, f"{dom} missing from the results"


def test_security_plus_v8_full_exam(site):
    """v2.56: Security+ V8 (SY0-801) gets its own bank, so both versions have full exams and no "later update" note."""
    w = site()
    p = w.page
    open_guide(p, "security+")
    mxp = p.inner_text("#mxp")
    for ver in ("v7", "v8"):
        assert p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').count() == 1, mxp[:500]
    assert "later update" not in mxp and "being retired" not in mxp, mxp[:800]
    p.locator('#mxp [data-mx="full"][data-ver="v8"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    assert "SY0-801" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("General Security Concepts", "Threats, Vulnerabilities, and Attacks", "Security Architecture",
                "Security Operations", "Security Program Management and Oversight"):
        assert dom in body, f"{dom} missing from the results"
    assert "Threats, Vulnerabilities, and Mitigations" not in body   # the V7 domain name must not leak into V8 results


def test_pentest_plus_v3_full_exam(site):
    """v2.57: PenTest+ PT0-003 gets a 90-question, 165-minute bank with PBQs and all five domains scored."""
    w = site()
    p = w.page
    open_guide(p, "pentest+")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v3"]').count() == 1, mxp[:500]
    assert "later update" not in mxp, mxp[:600]
    p.locator('#mxp [data-mx="full"][data-ver="v3"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("2:44:", "2:45:")), t
    assert "PT0-003" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Engagement Management", "Reconnaissance and Enumeration", "Vulnerability Discovery and Analysis",
                "Attacks and Exploits", "Post-exploitation and Lateral Movement"):
        assert dom in body, f"{dom} missing from the results"


def test_linux_plus_v8_full_exam(site):
    """v2.60: Linux+ XK0-006 gets a 90-question, 90-minute bank with PBQs and all five domains scored."""
    w = site()
    p = w.page
    open_guide(p, "linux+")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v8"]').count() == 1, mxp[:500]
    assert "later update" not in mxp, mxp[:600]
    p.locator('#mxp [data-mx="full"][data-ver="v8"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("1:29:", "1:30:")), t
    assert "XK0-006" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("System Management", "Services and User Management", "Security",
                "Automation, Orchestration, and Scripting", "Troubleshooting"):
        assert dom in body, f"{dom} missing from the results"


def test_securityx_v5_full_exam(site):
    """v2.61: SecurityX CAS-005 gets a 90-question, 165-minute bank with PBQs and all four domains scored."""
    w = site()
    p = w.page
    open_guide(p, "securityx")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v5"]').count() == 1, mxp[:500]
    assert "later update" not in mxp, mxp[:600]
    p.locator('#mxp [data-mx="full"][data-ver="v5"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("2:44:", "2:45:")), t
    assert "CAS-005" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Governance, Risk, and Compliance", "Security Architecture", "Security Engineering",
                "Security Operations"):
        assert dom in body, f"{dom} missing from the results"


def _scroll_into_view(p, sel):
    p.evaluate("(s) => document.querySelector(s).scrollIntoView({block: 'center'})", sel)
    p.wait_for_timeout(400)


def _qz_top(p):
    return p.evaluate("() => document.getElementById('g-qz').getBoundingClientRect().top")


@pytest.mark.parametrize("device,lite", [("desktop", None), ("iphone13", None), ("small320", None),
                                         ("reduced", None), ("desktop", True), ("iphone13", True)])
def test_untimed_check_next_question_stays_on_the_quiz(site, device, lite):
    """v2.59: "Next question" in the untimed check used to jump to the top of the Practice section (the practice exam
    cards, weak spots and recent runs sit above the check since v2.48), so you had to scroll back down. It must keep
    the check in view: the new question starts just under the section bar."""
    w = site(device=device, lite=lite)
    p = w.page
    open_guide(p, "security+")
    _scroll_into_view(p, "#g-qz")
    p.locator("#g-qz .g-qo").first.click()
    p.click("#g-qgo")                      # Check answer
    p.wait_for_selector("#g-qx.open")
    _scroll_into_view(p, "#g-qgo")         # read the explanation, then reach for Next
    p.click("#g-qgo")                      # Next question
    p.wait_for_timeout(1600)               # smooth scroll settles
    assert "02" in p.inner_text("#g-qz .g-qtop"), p.inner_text("#g-qz .g-qtop")
    top, vh = _qz_top(p), p.evaluate("() => innerHeight")
    assert 0 <= top < vh * .4, f"the check's top is at {top:.0f}px of a {vh}px screen"
    cards = p.evaluate("() => document.getElementById('mxp').getBoundingClientRect().bottom")
    assert cards <= top + 1, "scrolled back up to the practice exam cards"


def test_untimed_check_next_question_doesnt_scroll_when_already_in_view(site):
    """If the check is already near the top of the screen, Next question leaves the page where it is."""
    w = site()
    p = w.page
    open_guide(p, "security+")
    p.evaluate("""() => { const b = document.getElementById('g-qz'), pn = b.closest('.panel,#panel') || document.scrollingElement;
        pn.scrollTop += b.getBoundingClientRect().top - 140; }""")
    p.wait_for_timeout(400)
    p.locator("#g-qz .g-qo").first.click()
    p.click("#g-qgo")
    p.wait_for_selector("#g-qx.open")
    p.wait_for_timeout(700)
    before = _qz_top(p)
    p.evaluate("() => document.getElementById('g-qgo').click()")   # a real tap on a visible button: no test auto-scroll
    p.wait_for_timeout(1600)
    assert abs(_qz_top(p) - before) < 4, (before, _qz_top(p))


def test_untimed_check_retake_stays_on_the_quiz(site):
    """Retake quiz on the results screen also keeps the check in view, not the top of Practice."""
    w = site(device="iphone13")
    p = w.page
    open_guide(p, "security+")
    for _ in range(40):
        if p.locator("#g-qagain").count():
            break
        _scroll_into_view(p, "#g-qz .g-qo")
        p.locator("#g-qz .g-qo").first.click()
        p.click("#g-qgo")
        p.wait_for_selector("#g-qx.open")
        p.click("#g-qgo")
        p.wait_for_timeout(250)
    assert p.locator("#g-qagain").count() == 1
    _scroll_into_view(p, "#g-qagain")
    p.click("#g-qagain")
    p.wait_for_timeout(1600)
    top, vh = _qz_top(p), p.evaluate("() => innerHeight")
    assert 0 <= top < vh * .4, f"the check's top is at {top:.0f}px of a {vh}px screen"
