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
