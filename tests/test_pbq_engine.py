"""New PBQ types (v2.84): logsel, rules, term, diagram. Engine = vendor/pbq-engine.js, loaded only when a bank that has them opens.

Each test builds a saved exam (the same thing "resume" reads) with the PBQs it wants, resumes it and drives the real page:
tap, keyboard only, drag, 320 px width, reload/resume, scoring, weak spots and the "why" only after submit."""
import json, pathlib, sys, time

import pytest
from conftest import open_guide
from test_practice import _submit

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = json.loads((ROOT / "qbank" / "sy0-701.json").read_text(encoding="utf8"))
Q = {q["id"]: q for q in BANK["q"]}
NEW = [q["id"] for q in BANK["q"] if q.get("kind") in ("logsel", "rules", "term", "diagram")]


def fresh_item(qid):
    q = Q[qid]
    k = q["kind"]
    if k == "logsel":
        return {"id": qid, "ro": [], "pick": {"m": [0] * len(q["lines"]), "s": -1, "t": 0}}
    if k == "rules":
        return {"id": qid, "ro": list(range(len(q["rules"]))), "pick": {"set": []}}
    if k == "term":
        return {"id": qid, "ro": [], "pick": {"h": []}}
    return {"id": qid, "ro": list(range(len(q["devs"]))), "pick": {"pl": [""] * len(q["slots"])}}


def start(site, ids, device="desktop"):
    """Open the app with a saved Security+ exam holding these PBQs, resume it, return (watched, page, requests)."""
    w = site(device)
    p = w.page
    run = {"v": 1, "gid": "secplus", "cert": "Security+", "kind": "full", "src": "bank", "ver": "v7", "title": "Security+ V7",
           "items": [fresh_item(i) for i in ids], "i": 0, "dur": 5400, "used": 0, "t": int(time.time() * 1000)}
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", run)
    reqs = []
    p.on("request", lambda r: reqs.append(r.url))
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx[open]")
    p.wait_for_selector("#mx-body .px")
    return w, p, reqs


def finish(p):
    """Submit the exam and return its saved result record."""
    _submit(p)
    p.wait_for_selector("#mx-body .mx-list, #mx-body .mx-res", state="attached")
    return p.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.secplus'))[0]")


def no_sideways_scroll(p):
    assert p.evaluate("()=>{var b=document.getElementById('mx-body');return b.scrollWidth<=b.clientWidth+1}"), "the exam body scrolls sideways"


def test_engine_loads_only_for_banks_that_need_it(site):
    w = site()
    p = w.page
    reqs = []
    p.on("request", lambda r: reqs.append(r.url))
    open_guide(p, "security+")
    p.click('#mxp [data-mx="quick"]')                    # a quick set uses the guide quiz, no bank
    p.wait_for_selector("#mx[open]")
    assert not [u for u in reqs if "pbq-engine" in u], "the engine downloaded for an exam that has no new PBQ types"
    p.keyboard.press("Escape")
    w2, p2, reqs2 = start(site, ["s7-p-07"])
    assert [u for u in reqs2 if u.endswith("vendor/pbq-engine.js")], "the engine did not load for a bank that has the new types"


def test_logsel_keyboard_only_at_320_scores_and_explains_after_submit(site):
    w, p, _ = start(site, ["s7-p-07"], "small320")
    q = Q["s7-p-07"]
    p.focus(".px-ln")
    for i, l in enumerate(q["lines"]):                    # Space toggles, ArrowDown moves on: no mouse
        if l["bad"]:
            p.keyboard.press("Space")
        if i < len(q["lines"]) - 1:
            p.keyboard.press("ArrowDown")
    p.select_option("#px-ask", str(q["ask"]["a"]))
    no_sideways_scroll(p)
    body = p.inner_text("#mx-body")
    assert all(l["why"] not in body for l in q["lines"]), "a 'why' showed up during the exam"
    rec = finish(p)
    assert rec["s"] == 1, rec
    review = p.text_content("#mx-body")
    assert q["lines"][5]["why"] in review and q["ask"]["why"] in review


def test_logsel_partial_credit_and_blank_scores_zero(site):
    w, p, _ = start(site, ["s7-p-07"])
    p.click('.px-ln[data-i="0"]')                         # one right line, nothing else
    p.click('.px-ln[data-i="3"]')                         # one wrong line (a normal one)
    rec = finish(p)
    assert 0 < rec["s"] < 1, rec                          # partial credit
    w2, p2, _ = start(site, ["s7-p-07"])
    assert finish(p2)["s"] == 0, "a PBQ nobody touched must score 0"


def test_rules_tap_buttons_and_drag_at_320(site):
    w, p, _ = start(site, ["s7-p-09"], "small320")
    for rid in "abcd":
        p.click(f'[data-add="{rid}"]')
    ids = lambda: p.eval_on_selector_all("#px-set .px-rc", "els=>els.map(e=>e.dataset.id)")  # noqa: E731
    assert ids() == list("abcd")
    p.click('[data-up="d"]')                              # buttons reorder
    assert ids() == list("abdc")
    p.click('[data-dn="d"]')
    assert ids() == list("abcd")
    # drag the first rule one place down with the mouse (touch uses the same pointer events)
    g = p.locator('[data-grip="a"]').bounding_box()
    second = p.locator('#px-set .px-rc').nth(1).bounding_box()
    p.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
    p.mouse.down()
    p.mouse.move(g["x"] + 5, second["y"] + second["height"] * 0.8, steps=8)
    p.mouse.up()
    assert ids() == list("bacd"), ids()
    p.click('[data-up="a"]')
    assert ids() == list("abcd"), ids()
    no_sideways_scroll(p)
    assert finish(p)["s"] == 1


def test_rules_wrong_order_and_decoys_lose_parts_but_keep_credit(site):
    w, p, _ = start(site, ["s7-p-09"])
    for rid in "bace":                                    # b above a (wrong), decoy e added, d left out
        p.click(f'[data-add="{rid}"]')
    rec = finish(p)
    assert 0 < rec["s"] < 1, rec


def test_term_scores_the_result_not_the_spelling_and_caps_history(site):
    w, p, _ = start(site, ["s7-p-11"], "small320")
    run = lambda c: (p.fill(".px-term input", c), p.press(".px-term input", "Enter"))  # noqa: E731
    run("cat /var/log/auth.log | grep -i FAILED")         # different spelling, same result
    run("sudo   iptables -A INPUT -s 203.0.113.50 -j drop")
    run("rm -rf /")                                       # not available in the lab
    assert "Not available in this lab" in p.inner_text(".px-scr")
    run("iptables -L -n")
    no_sideways_scroll(p)
    assert finish(p)["s"] == 1
    # the saved history is capped
    w2, p2, _ = start(site, ["s7-p-11"])
    for i in range(32):
        p2.fill(".px-term input", "whoami")
        p2.press(".px-term input", "Enter")
    assert "Command limit reached" in p2.inner_text(".px-scr")
    n = p2.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.h.length")
    assert n == 30, n


def test_term_blocking_the_admin_loses_that_part(site):
    w, p, _ = start(site, ["s7-p-11"])
    for c in ["grep Failed /var/log/auth.log", "ufw deny from 203.0.113.50", "ufw deny from 10.20.10.44", "ufw status"]:
        p.fill(".px-term input", c)
        p.press(".px-term input", "Enter")
    assert finish(p)["s"] == pytest.approx(0.75)


def test_term_doing_nothing_does_not_earn_the_didnt_do_it_part(site):
    w, p, _ = start(site, ["s7-p-12"])
    assert finish(p)["s"] == 0


def test_diagram_tap_keyboard_and_drag(site):
    w, p, _ = start(site, ["s7-p-13"], "small320")
    p.click('.px-dev[data-d="fw"]')                       # tap a device, tap a spot
    p.click('.px-slot[data-s="0"]')
    p.focus('.px-dev[data-d="web"]')                      # keyboard: Enter on the device, Enter on the spot
    p.keyboard.press("Enter")
    p.focus('.px-slot[data-s="1"]')
    p.keyboard.press("Enter")
    d = p.locator('.px-dev[data-d="file"]').bounding_box()   # drag the last one
    s = p.locator('.px-slot[data-s="2"]').bounding_box()
    p.mouse.move(d["x"] + d["width"] / 2, d["y"] + d["height"] / 2)
    p.mouse.down()
    p.mouse.move(s["x"] + s["width"] / 2, s["y"] + s["height"] / 2, steps=8)
    p.mouse.up()
    assert p.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.pl") == ["fw", "web", "file"]
    p.click('.px-slot[data-s="2"]')                       # tapping a placed device takes it back
    assert p.locator('.px-dev[data-d="file"]').count() == 1
    p.click('.px-dev[data-d="file"]')
    p.click('.px-slot[data-s="2"]')
    no_sideways_scroll(p)
    assert finish(p)["s"] == 1


def test_resume_keeps_work_and_flag_survives(site):
    w, p, _ = start(site, ["s7-p-07", "s7-p-13"])
    p.click('.px-ln[data-i="2"]')
    p.click("#mx-flag")
    assert p.get_attribute("#mx-flag", "aria-pressed") == "true"
    p.keyboard.press("Escape")
    p.wait_for_timeout(500)
    p.reload()
    p.wait_for_timeout(2500)
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx-body .px")
    assert p.get_attribute('.px-ln[data-i="2"]', "aria-checked") == "true"
    assert p.get_attribute("#mx-flag", "aria-pressed") == "true"


def test_weak_spots_split_one_question_across_part_domains(site):
    w, p, _ = start(site, ["s7-p-07"])
    p.click('.px-ln[data-i="0"]')
    finish(p)
    ws = p.evaluate("JSON.parse(localStorage.getItem('cgcp.ws.secplus'))")["d"]
    assert set(ws) == {"4.0", "2.0"}, ws                  # the diagnosis part counts in 2.0, the lines in 4.0
    assert sum(v["t"] for v in ws.values()) == pytest.approx(1.0, abs=0.02), ws   # one PBQ = one question, never more


def test_every_new_pbq_runs_through_review_without_errors(site):
    w, p, _ = start(site, NEW)
    for _ in range(len(NEW) - 1):
        p.click("#mx-next")
        p.wait_for_selector("#mx-body .px")
    rec = finish(p)
    assert rec["n"] == len(NEW) and rec["s"] == 0         # nothing touched = nothing earned
    review = p.text_content("#mx-body")
    for qid in NEW:
        assert Q[qid]["title"] in review


def test_check_site_rejects_a_part_without_a_why():
    sys.path.insert(0, str(ROOT / ".github" / "scripts"))
    import check_site
    dset = {d["n"]: d for d in BANK["domains"]}
    for qid in NEW:
        assert check_site.check_new_pbq(Q[qid], dset) == [], qid
    bad = json.loads(json.dumps(Q["s7-p-09"]))
    del bad["rules"][1]["why"]
    assert any("why" in m for m in check_site.check_new_pbq(bad, dset))
    bad = json.loads(json.dumps(Q["s7-p-11"]))
    bad["checks"][1]["has"] = "block:nobody"
    assert any("no command produces" in m for m in check_site.check_new_pbq(bad, dset))
    bad = json.loads(json.dumps(Q["s7-p-13"]))
    bad["devs"] = [d for d in bad["devs"] if d["slot"] >= 0]
    assert check_site.check_new_pbq(bad, dset)            # no decoys
    bad = json.loads(json.dumps(Q["s7-p-07"]))
    bad["ask"]["obj"] = "3.1"                             # objective from the wrong domain
    assert check_site.check_new_pbq(bad, dset)
