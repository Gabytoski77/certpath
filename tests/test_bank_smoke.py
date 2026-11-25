"""Smoke test for EVERY practice-exam bank, found automatically from qbank/ (a new bank needs no new test code).

Per bank: the guide's card offers it, the full exam opens with the bank's own question count, time and exam code,
a question renders and one answer can be picked, and ending the exam early shows a results screen (every domain of
this bank listed, no domain of a sibling bank of the same guide) without page errors. The few full "answer every
question" runs live in test_practice.py; the static checks (check_site.py) prove every bank can fill full and half exams.
"""
import json, re, sys

import pytest

from conftest import ROOT, open_guide

sys.path.insert(0, str(ROOT / "build"))
import show_guide  # noqa: E402  (reads src/app.html the same way the helper scripts do)


def _discover():
    """{bank path: (guide id, ver)} from each guide's mock:{ver:"qbank/x.json"} list."""
    lines = show_guide.SRC.read_text(encoding="utf-8").splitlines()
    found = {}
    for _name, a, b in show_guide.guides(lines):
        block = "\n".join(lines[a:b])
        gid, mock = re.search(r'\bid:"([^"]+)"', block), re.search(r'\bmock:\{([^}]*)\}', block)
        if gid and mock:
            for ver, path in re.findall(r'(\w+):"([^"]+)"', mock.group(1)):
                found[path] = (gid.group(1), ver)
    return found


GUIDE_OF = _discover()
BANKS = sorted(p.name for p in (ROOT / "qbank").glob("*.json"))


def _clock(minutes):
    """Timer text at the start: the full time, or one second less (it has already ticked)."""
    def f(sec):
        h, m = divmod(sec // 60, 60)
        return f"{h}:{m:02d}:" if h else f"{m}:"
    return f(minutes * 60), f(minutes * 60 - 1)


def test_every_bank_belongs_to_a_guide():
    assert BANKS, "no banks found"
    assert [b for b in BANKS if "qbank/" + b not in GUIDE_OF] == []


@pytest.mark.parametrize("bank", BANKS)
def test_bank_smoke(site, bank):
    path = "qbank/" + bank
    gid, ver = GUIDE_OF[path]
    b = json.loads((ROOT / path).read_text(encoding="utf-8"))
    F = b["format"]
    mine = {d["name"] for d in b["domains"]}
    w = site()
    p = w.page
    open_guide(p, gid)
    mxp = p.inner_text("#mxp")
    assert p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').count() == 1, mxp[:500]
    assert p.locator(f'#mxp [data-mx="half"][data-ver="{ver}"]').count() == 1, mxp[:500]
    assert p.locator("#mxp .mxp-card.soon").count() == 0, mxp[:600]   # a "coming later" line for a newer version is fine; an empty-bank card is not
    p.locator(f'#mxp [data-mx="full"][data-ver="{ver}"]').click()
    p.wait_for_selector("#mx[open]")
    p.wait_for_timeout(600)
    assert p.inner_text("#mx-count").strip().endswith("/ %d" % F["n"])
    t = p.inner_text("#mx-time").strip()
    assert any(t.startswith(x) for x in _clock(F["min"])), (t, F["min"])
    assert b["exam"].lower() in p.inner_text("#mx").lower()
    # a question renders; walk to the first multiple-choice one and pick an answer
    for _ in range(F["pbq"] + 2):
        assert p.inner_text("#mx-body").strip()
        if p.locator("#mx-body .g-qo").count():
            break
        p.click("#mx-next")
        p.wait_for_timeout(60)
    opts = p.locator("#mx-body .g-qo")
    assert opts.count() >= 2, p.inner_text("#mx-body")[:400]
    opts.first.click()
    # end early: review screen, then Submit
    p.click("#mx-revbtn")
    p.wait_for_selector("#mx-submit")
    p.click("#mx-submit")
    p.wait_for_selector("#mx-body .mx-res")
    body = p.inner_text("#mx-body")
    assert "%" in body, body[:500]
    for name in mine:
        assert name in body, f"{name} missing from the {bank} results"
    for other, (g2, _v) in GUIDE_OF.items():     # domains of the guide's other banks must not leak in
        if other != path and g2 == gid:
            for d in json.loads((ROOT / other).read_text(encoding="utf-8"))["domains"]:
                assert d["name"] in mine or d["name"] not in body, f"{d['name']} (from {other}) leaked into {bank} results"
