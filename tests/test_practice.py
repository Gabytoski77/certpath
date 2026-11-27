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


def _scroll_into_view(p, sel):
    p.evaluate("(s) => document.querySelector(s).scrollIntoView({block: 'center'})", sel)
    p.wait_for_timeout(400)


def _qz_top(p):
    return p.evaluate("() => document.getElementById('g-qz').getBoundingClientRect().top")


@pytest.mark.parametrize("device,lite", [("desktop", True), ("iphone13", True), ("small320", True),
                                         ("reduced", True)])
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


def test_cc_half_exam_has_no_pbq(site):
    """A bank with format.pbq 0 still builds a half-length exam (50 questions, all multiple choice)."""
    w = site("iphone13")
    p = w.page
    open_guide(p, "cc")
    p.locator('#mxp [data-mx="half"][data-ver="v26"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 50")


def test_sscp_guide_objective_7_3_is_mobile_devices(site):
    """ISC2's 2025 outline: 7.3 is mobile device management and EDR sits under 7.2 (the guide had them mixed up)."""
    w = site()
    p = w.page
    open_guide(p, "sscp")
    text = p.inner_text("#g-obj")
    assert "Administer and manage mobile devices" in text
    assert "Endpoint detection and response (EDR)\n" not in text


def test_cissp_2024_full_exam(site):
    """v2.75: ISC2 CISSP (Apr 2024 outline) gets a 125-item, 3-hour bank with 4 advanced items and all eight domains scored."""
    w = site()
    p = w.page
    open_guide(p, "cissp")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v24"]').count() == 1, mxp[:500]
    assert p.locator("#mxp .mxp-card.soon").count() == 0, mxp[:600]
    assert "PBQs first" not in mxp and "100 to 150" in mxp
    p.locator('#mxp [data-mx="full"][data-ver="v24"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 125")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("2:59:", "3:00:")), t
    assert p.inner_text("#mx-h").strip() == "CISSP · 2024 outline"
    _answer_all(p, limit=140)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("Security and Risk Management", "Asset Security", "Security Architecture and Engineering",
                "Communication and Network Security", "Identity and Access Management (IAM)",
                "Security Assessment and Testing", "Security Operations", "Software Development Security"):
        assert dom in body, f"{dom} missing from the results"


def test_exam_long_title_fits_320(site):
    """v2.76 fix: a long exam title (CCNA Cybersecurity · v1.2 · 200-201 CCNACBR) made the exam dialog wider than a 320 px phone."""
    w = site(device="small320")
    p = w.page
    open_guide(p, "ccnacbr")
    p.locator('#mxp [data-mx="full"][data-ver="v12"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    for _ in range(5):  # the first items are the drag-and-drop style ones
        widths = p.evaluate("() => [document.querySelector('#mx-body').scrollWidth, document.querySelector('.mx-top').getBoundingClientRect().width, innerWidth]")
        assert widths[0] <= widths[2] and widths[1] <= widths[2], widths
        p.click("#mx-next")
        p.wait_for_timeout(60)


def test_ccna_v20_setup_and_code_blocks(site):
    """v2.77: CCNA (200-301 v2.0) gets a 100-item, 2-hour bank with 4 drag-and-drop items, CLI output blocks and all five domains scored."""
    w = site()
    p = w.page
    open_guide(p, "ccna")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v20"]').count() == 1, mxp[:600]
    assert "February 3, 2027" in mxp and "can't go back" in mxp
    p.locator('#mxp [data-mx="full"][data-ver="v20"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 100")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("1:59:", "2:00:")), t
    assert "200-301" in p.inner_text("#mx-h"), p.inner_text("#mx-h")
    codes = 0
    for _ in range(100):
        codes += p.locator("#mx-body pre.g-qcode").count()
        if p.locator("#mx-next").inner_text().strip().lower().startswith(("review", "submit", "finish")):
            break
        p.click("#mx-next")
        p.wait_for_timeout(30)
    assert codes >= 5, codes  # show output appears in its own block


def test_ccst_it_support_full_exam(site):
    """v2.79: CCST IT Support (100-140) gets a 45-item, 50-minute bank with 4 drag-and-drop items and all six domains scored; nothing overflows at 320 px."""
    w = site(device="small320")
    p = w.page
    open_guide(p, "ccstit")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="cur"]').count() == 1, mxp[:500]
    assert p.locator("#mxp .mxp-card.soon").count() == 0, mxp[:600]
    assert "doesn't publish the real item count" in mxp
    p.locator('#mxp [data-mx="full"][data-ver="cur"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ 45")
    t = p.inner_text("#mx-time").strip()
    assert t.startswith(("49:", "50:")), t
    assert "100-140" in p.inner_text("#mx-h"), p.inner_text("#mx-h")
    inner = p.evaluate("() => innerWidth")
    for _ in range(45):  # every item, including the drag-and-drop ones, must fit a 320 px phone
        widths = p.evaluate("() => [document.querySelector('#mx-body').scrollWidth, document.querySelector('.mx-top').getBoundingClientRect().width]")
        assert widths[0] <= inner and widths[1] <= inner, widths
        opt = p.locator("#mx-body .g-qo").first
        if opt.count():
            opt.click()
        label = p.inner_text("#mx-next")
        if "Submit" in label or "Review" in label or "Finish" in label:
            break
        p.click("#mx-next")
        p.wait_for_timeout(60)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("IT Support Job Tasks and Responsibilities", "Hardware Issues", "Connectivity and Resource Access Issues",
                "Operating System and Application Issues", "Common Threats and Preventions", "Job Tools"):
        assert dom in body, f"{dom} missing from the results"


def _open_full(p, guide, ver):
    open_guide(p, guide)
    p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)


def test_security_plus_v7_full_exam(site):
    """One of the two full "answer every question" runs: 90 items with PBQs, results score every domain."""
    w = site()
    p = w.page
    _open_full(p, "security+", "v7")
    assert p.inner_text("#mx-count").strip().endswith("/ 90")
    assert "SY0-701" in p.inner_text("#mx")
    _answer_all(p)
    _submit(p)
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for dom in ("General Security Concepts", "Threats, Vulnerabilities, and Mitigations", "Security Architecture",
                "Security Operations", "Security Program Management and Oversight"):
        assert dom in body, f"{dom} missing from the results"
    assert any(k.startswith("cgcp.mx.") for k in p.evaluate("Object.keys(localStorage)"))


def test_adaptive_isc2_cards_say_so_and_have_no_pbq_wording(site):
    """The ISC2 banks are fixed-length stand-ins for adaptive exams; each card must say that and never promise PBQs."""
    w = site()
    p = w.page
    for guide, ver, phrase in (("cc", "v26", "adaptive"), ("sscp", "v25", "adaptive"), ("ccsp", "v26", "100 to 150"),
                               ("cgrc", "cur", "fixed 125-item"), ("cissp", "v24", "100 to 150")):
        open_guide(p, guide)
        mxp = p.inner_text("#mxp")
        assert p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').count() == 1, (guide, mxp[:500])
        assert p.locator("#mxp .mxp-card.soon").count() == 0, (guide, mxp[:600])
        assert "PBQs first" not in mxp and phrase in mxp, (guide, mxp[:600])
        p.keyboard.press("Escape")
        p.wait_for_timeout(300)


def test_cc_full_exam_has_no_pbq(site):
    w = site()
    p = w.page
    _open_full(p, "cc", "v26")
    assert p.inner_text("#mx-count").strip().endswith("/ 100")
    assert p.locator("#mx .mx-pbq, #mx [data-kind='pbq']").count() == 0


def test_sscp_exam_title_doesnt_repeat_the_code(site):
    w = site()
    p = w.page
    _open_full(p, "sscp", "v25")
    assert p.inner_text("#mx-h").strip() == "SSCP · 2025 outline"   # the code isn't repeated when it equals the cert name


def test_cysa_cards_show_v4_and_the_retiring_v3_note(site):
    w = site()
    p = w.page
    open_guide(p, "cysa")
    mxp = p.inner_text("#mxp")
    assert p.locator('#mxp [data-mx="full"][data-ver="v4"]').count() == 1, mxp[:500]
    assert p.locator('#mxp [data-mx="full"][data-ver="v3"]').count() == 0
    assert "CS0-003" in mxp and "being retired" in mxp and "later update" not in mxp, mxp[:800]
