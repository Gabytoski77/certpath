"""SAL1 practice exam (v2.100): qbank/sal1.json = MCQs + 7 SOC Simulator scenarios, each attempt draws 20 + 5.
Scored like the real exam: MCQs 200 points, scenarios 800, pass mark 750 of 1000.
Covers: the draw (20 + 5, 120 minutes, retakes differ), weighting and the pass mark (a perfect run = 1000), every scenario
answered from its own answer key through the real forms (keyboard-reachable controls), dynamic alerts appearing."""
import json, pathlib, time

import pytest
from conftest import open_guide
from test_practice import _submit

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = json.loads((ROOT / "qbank" / "sal1.json").read_text(encoding="utf8"))
SCEN = [q for q in BANK["q"] if q.get("t") == "pbq"]
MCQ = [q for q in BANK["q"] if q.get("t") != "pbq"]
KEY = "cgcp.mx.sal1"


def perfect_pick(q):
    """A saved scenario state that holds the model answers: taken, submitted, every tool used."""
    own, sub, r = {}, {}, {}
    for i, a in enumerate(q["alerts"]):
        an = a["ans"]
        own[a["id"]] = 1
        sub[a["id"]] = 10 + i
        tp = an["tp"]
        esc = an["esc"].get("v", tp)
        ioc = {"ip": [], "domain": [], "hash": [], "file": []}
        for c in an.get("iocs") or []:
            if c.get("need", 1):
                ioc[c["k"]].append(c["v"])
        host = an["host"]["v"] if an.get("host") else ""
        r[a["id"]] = {"c": "tp" if tp else "fp", "s": (an.get("sev") or {}).get("v", ""), "e": "y" if esc else "n",
                      "t": (an.get("tech") or {}).get("v", ""), "h": host[0] if isinstance(host, list) else host,
                      "a": (an.get("act") or {}).get("v", ""), "n": "model", "d": 1, "i": {k: " ".join(v) for k, v in ioc.items()}}
    idx = sorted({e["i"] for e in q["events"]})
    act = [{"k": "q", "s": f"index={i}\u0001all"} for i in idx]
    act += [{"k": "c", "s": c["run"][0]} for c in q.get("cmds", [])]
    act += [{"k": "t", "s": t["ind"]} for t in q.get("ti", [])]
    act += [{"k": "d", "s": "b64:AAAA"}, {"k": "d", "s": "url:AAAA"}]
    return {"el": 60, "tab": "al", "sel": "", "own": own, "sub": sub, "act": act[:60], "r": r, "up": 0, "lq": "", "lr": "all"}


def mcq_item(q, right=True):
    n = len(q["o"])
    if q.get("t") == "ms":
        return {"id": q["id"], "ord": list(range(n)), "pick": list(q["a"]) if right else []}
    return {"id": q["id"], "ord": list(range(n)), "pick": q["a"] if right else None}


def scen_item(q, perfect=True):
    return {"id": q["id"], "ro": [], "pick": perfect_pick(q) if perfect else {"el": 0, "tab": "al", "sel": "", "own": {}, "sub": {}, "act": [], "r": {}, "up": 0, "lq": "", "lr": "all"}}


def resume(site, items, minutes=7200):
    w = site("desktop", lite=True, service_workers="block")
    p = w.page
    run = {"v": 1, "gid": "sal1", "cert": "SAL1", "kind": "full", "src": "bank", "ver": "cur", "title": "Current exam",
           "items": items, "i": 0, "dur": minutes, "used": 0, "t": int(time.time() * 1000)}
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", run)
    open_guide(p, "sal1")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx[open]")
    return p


def score_of(p):
    p.click('#mx button:has-text("Review")')
    p.click("#mx-submit")
    _submit(p)
    p.wait_for_selector("#mx-body .mx-res, #mx-body .mx-list", state="attached")
    return p.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")


def test_bank_shape_and_pools():
    F = BANK["format"]
    assert (F["n"], F["pbq"], F["min"]) == (25, 5, 120) and F["pts"] == {"mcq": 200, "pbq": 800, "pass": 750}
    assert len(SCEN) == 7 and 55 <= len(MCQ) <= 70
    assert "shorter than the real exam" in BANK["note"].lower()
    for q in SCEN:
        assert 3 <= len(q["alerts"]) <= 6 and 150 <= len(q["events"]) <= 400 and 18 <= q["minutes"] <= 25, q["id"]
        assert any(a.get("after") or a.get("at") for a in q["alerts"]), q["id"] + " has no dynamic alert"
        assert any(a["ans"]["tp"] == 0 for a in q["alerts"]) and any(a["ans"]["tp"] == 1 for a in q["alerts"]), q["id"]
        assert q["cmds"] and q["ti"] and q["checks"] and all(a["ans"]["why"] for a in q["alerts"]), q["id"]


def test_full_exam_draws_20_questions_and_5_scenarios_and_retakes_differ(site):
    w = site("desktop", lite=True, service_workers="block")
    p = w.page
    open_guide(p, "sal1")
    draws = []
    for _ in range(3):
        p.click('#mxp [data-mx="full"]')
        p.wait_for_selector("#mx[open]")
        run = p.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.run'))")
        ids = [it["id"] for it in run["items"]]
        assert len(ids) == 25 and run["dur"] == 7200
        assert sum(i.startswith("sal-sc-") for i in ids) == 5
        assert len({i for i in ids if i.startswith("sal-sc-")}) == 5
        draws.append(set(ids))
        p.evaluate("localStorage.removeItem('cgcp.mx.run')")
        p.reload()
        open_guide(p, "sal1")
    assert len({frozenset(d) for d in draws}) > 1, "three attempts drew the same 25 items"


@pytest.mark.parametrize("name,mcq_right,scen_perfect,pts,passed", [
    ("perfect", True, True, 1000, True),
    ("scenarios only", False, True, 800, True),
    ("questions only", True, False, 200, False),
    ("blank", False, False, 0, False),
])
def test_weighting_and_pass_mark(site, name, mcq_right, scen_perfect, pts, passed):
    items = [mcq_item(q, mcq_right) for q in MCQ[:20]] + [scen_item(q, scen_perfect) for q in SCEN[:5]]
    p = resume(site, items)
    rec = score_of(p)
    assert rec["pts"] == pts and rec["pass"] == 750 and rec["top"] == 1000, rec
    text = p.inner_text("#mx-body")
    assert f"{pts} of 1000 points (pass 750)" in text.lower()
    low = text.lower()
    assert ("reached the pass mark" in low or "above the pass mark" in low) == passed
    assert passed or "below the pass mark of 750" in low
    if name == "perfect":
        assert rec["s"] == 25


def test_every_scenario_scores_full_marks_from_its_answer_key(site):
    """Two runs of five scenarios (1-5 and 3-7) cover all seven; with the questions blank a perfect scenario run is 800."""
    for group in (SCEN[:5], SCEN[2:]):
        items = [mcq_item(q, False) for q in MCQ[:20]] + [scen_item(q) for q in group]
        p = resume(site, items)
        rec = score_of(p)
        assert rec["pts"] == 800, ([q["id"] for q in group], rec)


@pytest.mark.parametrize("q", SCEN, ids=[q["id"] for q in SCEN])
def test_scenario_is_completable_through_the_forms_and_dynamic_alerts_appear(site, q):
    """Real clicks and typing: the queue starts with the non-dynamic alerts, the follow-ups appear on their own, and the
    model answers typed into the case report forms score 100%."""
    w = site("desktop", lite=True, service_workers="block")
    p = w.page
    p.clock.install()
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", {
        "v": 1, "gid": "sal1", "cert": "SAL1", "kind": "full", "src": "bank", "ver": "cur", "title": "Current exam",
        "items": [scen_item(q, False)], "i": 0, "dur": 7200, "used": 0, "t": int(time.time() * 1000)})
    open_guide(p, "sal1")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx-body .ss")
    first = [a for a in q["alerts"] if not a.get("after") and not a.get("at")]
    dyn = [a for a in q["alerts"] if a.get("after") or a.get("at")]
    for a in dyn:
        assert p.locator(f'.ss-ab[data-id="{a["id"]}"]').count() == 0, a["id"] + " is in the queue too early"
    todo = list(q["alerts"])
    done = set()
    while len(done) < len(todo):
        a = next(x for x in todo if x["id"] not in done and (x in first or not x.get("after") or x["after"] in done))
        if a in dyn:
            p.clock.run_for((a.get("at") or 0) * 1000 + 2000)
            p.wait_for_selector(f'.ss-ab[data-id="{a["id"]}"]', timeout=8000)
        p.focus(f'.ss-ab[data-id="{a["id"]}"]'); p.keyboard.press("Enter")
        p.focus(f"#ss-p-al [data-take={a['id']}]"); p.keyboard.press("Enter")
        an = a["ans"]
        p.select_option("#ss-c", "tp" if an["tp"] else "fp")
        p.select_option("#ss-e", "y" if an["esc"].get("v", an["tp"]) else "n")
        if an["tp"]:
            p.select_option("#ss-s", an["sev"]["v"]); p.select_option("#ss-a", an["act"]["v"]); p.select_option("#ss-t", an["tech"]["v"])
            h = an["host"]["v"]; p.fill("#ss-h", h[0] if isinstance(h, list) else h)
            for k in ("ip", "domain", "hash", "file"):
                v = " ".join(c["v"] for c in an.get("iocs", []) if c["k"] == k and c.get("need", 1))
                if v:
                    p.fill(f"[data-i={k}]", v)
        p.focus(".ss-f button[type=submit]"); p.keyboard.press("Enter")
        assert "Closed" in p.inner_text("#ss-p-al") or "Escalated" in p.inner_text("#ss-p-al")
        done.add(a["id"])
    rec = score_of(p)
    # the case reports are all right; the tool checks are not, because nothing was searched here
    assert 0 < rec["s"] < 1
