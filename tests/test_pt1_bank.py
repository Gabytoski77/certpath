"""PT1 practice exam (v2.102): qbank/pt1.json = MCQs + 5 simulated Pentest Lab engagements, each attempt draws 20 + 5.
Scored like the real exam's weighting: MCQs 200 points, engagements 800, pass mark 750 of 1000. Made-up targets, nothing runs.
Covers: bank shape and the "different from the real exam" note, the draw (20 + 5, 150 minutes, retakes differ), weighting and the
pass mark (a perfect run = 1000), every engagement completed by keyboard from its own walkthrough (full marks), and an
out-of-scope touch losing points."""
import json, pathlib, time

import pytest
from conftest import open_guide
from test_practice import _submit

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = json.loads((ROOT / "qbank" / "pt1.json").read_text(encoding="utf8"))
LABS = [q for q in BANK["q"] if q.get("t") == "pbq"]
MCQ = [q for q in BANK["q"] if q.get("t") != "pbq"]
KEY = "cgcp.mx.pt1"
# the exact keyboard steps that finish each engagement: ("tm"|"ms", command) or ("wb", address, try id)
WALKS = json.loads(r'''{
"pt1-pl1": [
[
"tm",
"nmap -sV 10.10.31.10"
],
[
"tm",
"gobuster dir -u http://10.10.31.10/ -w /usr/share/wordlists/lab-common.txt"
],
[
"tm",
"curl -I http://10.10.31.10/"
],
[
"wb",
"10.10.31.10/login.php",
"sqli1"
],
[
"wb",
"10.10.31.10/login.php",
"sqli2"
],
[
"wb",
"10.10.31.10/admin/panel",
"up1"
],
[
"wb",
"10.10.31.10/admin/panel",
"up2"
],
[
"wb",
"10.10.31.10/admin/panel",
"up3"
]
],
"pt1-pl2": [
[
"tm",
"nmap -sV -p- 10.10.32.10"
],
[
"tm",
"gobuster dir -u http://10.10.32.10/ -w /usr/share/wordlists/lab-common.txt"
],
[
"tm",
"curl -I http://10.10.32.10/"
],
[
"tm",
"curl http://10.10.32.10/static/app.js"
],
[
"wb",
"10.10.32.10/orders/1042",
"idor1"
],
[
"wb",
"10.10.32.10/api/customers",
"api1"
],
[
"wb",
"10.10.32.10/api/customers",
"api2"
]
],
"pt1-pl3": [
[
"tm",
"nmap -sV -sC 10.10.33.5"
],
[
"tm",
"searchsploit labftpd"
],
[
"tm",
"curl -I http://10.10.33.5/"
],
[
"ms",
"search labftpd"
],
[
"ms",
"use exploit/lab/ftp/labftpd_cmd_exec"
],
[
"ms",
"set RHOSTS 10.10.33.5"
],
[
"ms",
"set LHOST 10.10.14.7"
],
[
"ms",
"set PAYLOAD lab/payload/reverse_demo"
],
[
"ms",
"check"
],
[
"ms",
"run"
],
[
"ms",
"getuid"
],
[
"ms",
"cat /home/ftpsvc/user.txt"
],
[
"ms",
"shell"
],
[
"ms",
"sudo -l"
],
[
"ms",
"find / -perm -4000"
],
[
"ms",
"exit"
],
[
"ms",
"background"
],
[
"ms",
"use exploit/lab/local/sudo_find_root"
],
[
"ms",
"set RHOSTS 10.10.33.5"
],
[
"ms",
"set LHOST 10.10.14.7"
],
[
"ms",
"set PAYLOAD lab/payload/reverse_demo"
],
[
"ms",
"run"
],
[
"ms",
"getuid"
],
[
"ms",
"cat /root/root.txt"
]
],
"pt1-pl4": [
[
"tm",
"nmap -sV 10.10.34.5"
],
[
"tm",
"enum4linux 10.10.34.5"
],
[
"tm",
"smbclient -L //10.10.34.5/"
],
[
"tm",
"hydra -l svc-backup -P /usr/share/wordlists/lab-passwords.txt ssh://10.10.34.5"
],
[
"tm",
"ssh svc-backup@10.10.34.5"
],
[
"tm",
"Welcome2026"
],
[
"tm",
"whoami /priv"
],
[
"tm",
"type user.txt"
],
[
"tm",
"type service-audit.txt"
],
[
"tm",
"exit"
],
[
"ms",
"use exploit/lab/local/unquoted_service_path"
],
[
"ms",
"set RHOSTS 10.10.34.5"
],
[
"ms",
"set LHOST 10.10.14.7"
],
[
"ms",
"set PAYLOAD lab/payload/reverse_demo"
],
[
"ms",
"run"
],
[
"ms",
"getuid"
],
[
"ms",
"cat root.txt"
]
],
"pt1-pl5": [
[
"tm",
"nmap -sV 10.10.35.10"
],
[
"tm",
"hydra -l deploy -P /usr/share/wordlists/lab-passwords.txt ssh://10.10.35.10"
],
[
"tm",
"ssh deploy@10.10.35.10"
],
[
"tm",
"Deploy2026"
],
[
"tm",
"cat flag-dmz.txt"
],
[
"tm",
"cat deploy-notes.txt"
],
[
"tm",
"exit"
],
[
"tm",
"ssh -L 2222:10.10.35.20:22 deploy@10.10.35.10"
],
[
"tm",
"nmap -sV 10.10.35.20"
],
[
"tm",
"ssh deploy@10.10.35.20"
],
[
"tm",
"Deploy2026"
],
[
"tm",
"cat internal-flag.txt"
],
[
"tm",
"exit"
],
[
"tm",
"curl -I http://10.10.35.10/"
]
]
}''')


def blank_pick():
    return {"el": 0, "tab": "br", "up": 0, "sub": 0, "n": 0, "fx": [], "oos": [], "tl": [], "ml": [], "sh": None, "aw": None,
            "ms": {"mod": "", "o": {}, "ses": [], "cur": 0, "msh": 0}, "wb": "", "ad": "", "rp": {"rows": [], "sum": ""}}


def perfect_pick(q, oos=None):
    """A saved engagement that holds every fact and a model report."""
    p = blank_pick()
    fx = [l["fx"] for l in q["loot"]] + [f for c in q.get("checks", []) for f in c["has"]] + [e["fx"] for e in q["evid"] if e.get("fx")]
    p["fx"] = list(dict.fromkeys(fx))
    p["n"] = 10
    p["sub"] = 1
    p["rp"]["rows"] = [{"t": f["title"], "h": f["host"], "s": f["sev"], "e": list(f["ev"]), "r": f["rem"]} for f in q["findings"]]
    p["oos"] = list(oos or [])
    return p


def mcq_item(q, right=True):
    n = len(q["o"])
    return {"id": q["id"], "ord": list(range(n)), "pick": q["a"] if right else None}


def lab_item(q, perfect=True, oos=None):
    return {"id": q["id"], "ro": [], "pick": perfect_pick(q, oos) if perfect else blank_pick()}


def resume(site, items, minutes=9000):
    w = site("desktop", lite=True, service_workers="block")
    p = w.page
    run = {"v": 1, "gid": "pt1", "cert": "PT1", "kind": "full", "src": "bank", "ver": "cur", "title": "Current exam",
           "items": items, "i": 0, "dur": minutes, "used": 0, "t": int(time.time() * 1000)}
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", run)
    open_guide(p, "pt1")
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
    assert (F["n"], F["pbq"], F["min"]) == (25, 5, 150) and F["pts"] == {"mcq": 200, "pbq": 800, "pass": 750}
    assert len(LABS) == 5 and 70 <= len(MCQ) <= 80
    note = BANK["note"].lower()
    assert "different from the real exam" in note and "48-hour" in note and "no multiple choice" in note
    for q in LABS:
        assert q["kind"] == "pentestlab" and 20 <= q["minutes"] <= 30, q["id"]
        assert any(h["scope"] == "out" for h in q["hosts"]) and any(h["scope"] == "in" for h in q["hosts"]), q["id"]
        assert "legal" in q["brief"]["note"].lower(), q["id"]
        assert len(q["findings"]) >= 3 and len([l for l in q["loot"] if l["k"] == "flag"]) >= 2, q["id"]
        assert all(l["why"] for l in q["loot"] if l["k"] == "flag") and all(f["why"] for f in q["findings"]), q["id"]
    guide = (ROOT / "guides" / "pt1.json").read_text(encoding="utf8")
    assert "qbank/pt1.json" in guide and "different from the real exam" in guide


def test_full_exam_draws_20_questions_and_5_engagements_and_retakes_differ(site):
    w = site("desktop", lite=True, service_workers="block")
    p = w.page
    open_guide(p, "pt1")
    draws = []
    for _ in range(3):
        p.click('#mxp [data-mx="full"]')
        p.wait_for_selector("#mx[open]")
        run = p.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.run'))")
        ids = [it["id"] for it in run["items"]]
        assert len(ids) == 25 and run["dur"] == 9000
        assert sum(i.startswith("pt1-pl") for i in ids) == 5 and len(set(ids)) == 25
        draws.append(set(ids))
        p.evaluate("localStorage.removeItem('cgcp.mx.run')")
        p.reload()
        open_guide(p, "pt1")
    assert len({frozenset(d) for d in draws}) > 1, "three attempts drew the same 25 items"


@pytest.mark.parametrize("name,mcq_right,lab_perfect,pts,passed", [
    ("perfect", True, True, 1000, True),
    ("engagements only", False, True, 800, True),
    ("questions only", True, False, 200, False),
    ("blank", False, False, 0, False),
])
def test_weighting_and_pass_mark(site, name, mcq_right, lab_perfect, pts, passed):
    items = [mcq_item(q, mcq_right) for q in MCQ[:20]] + [lab_item(q, lab_perfect) for q in LABS]
    p = resume(site, items)
    rec = score_of(p)
    assert rec["pts"] == pts and rec["pass"] == 750 and rec["top"] == 1000, rec
    low = p.inner_text("#mx-body").lower()
    assert f"{pts} of 1000 points (pass 750)" in low
    assert ("reached the pass mark" in low or "above the pass mark" in low) == passed
    if name == "perfect":
        assert rec["s"] == 25


def test_out_of_scope_touch_loses_points_and_says_why(site):
    q = LABS[0]
    oos = [h["ip"] for h in q["hosts"] if h["scope"] == "out"]
    items = [mcq_item(x) for x in MCQ[:20]] + [lab_item(q, True, oos)] + [lab_item(x) for x in LABS[1:]]
    p = resume(site, items)
    rec = score_of(p)
    assert 0 < rec["pts"] < 1000 and rec["s"] < 25, rec
    body = p.text_content("#mx-body")
    assert "Stay out of " + oos[0] in body and "not in the signed scope" in body


def type_in(p, kind, text):
    if p.is_visible("#pl-t-" + kind):
        p.focus("#pl-t-" + kind); p.keyboard.press("Enter")
    p.fill("#pl-in-" + kind, text)
    p.press("#pl-in-" + kind, "Enter")


@pytest.mark.parametrize("q", LABS, ids=[q["id"] for q in LABS])
def test_engagement_is_completable_by_keyboard_and_scores_full_marks(site, q):
    item = {"id": q["id"], "ro": [], "pick": blank_pick()}
    p = resume(site, [item])
    p.wait_for_selector("#mx-body .pl")
    for step in WALKS[q["id"]]:
        if step[0] == "wb":
            if p.is_visible("#pl-t-wb"):
                p.focus("#pl-t-wb"); p.keyboard.press("Enter")
            p.select_option("#pl-wsel", step[1])
            p.focus("#pl-wgo"); p.keyboard.press("Enter")
            p.focus(f'[data-t="{step[2]}"]'); p.keyboard.press("Enter")
        else:
            type_in(p, step[0], step[1])
    # flags captured on their own
    if p.is_visible("#pl-t-lt"):
        p.focus("#pl-t-lt"); p.keyboard.press("Enter")
    loot = p.inner_text("#pl-p-lt")
    for l in q["loot"]:
        if l["k"] == "flag":
            assert l["v"] in loot, l["v"]
    if p.is_visible("#pl-t-rp"):
        p.focus("#pl-t-rp"); p.keyboard.press("Enter")
    for f in q["findings"]:
        p.focus("#pl-add"); p.keyboard.press("Enter")
        row = p.locator(".pl-fnd").last
        row.locator('[data-f="t"]').select_option(f["title"])
        row.locator('[data-f="h"]').select_option(f["host"])
        row.locator('[data-f="s"]').select_option(f["sev"])
        for e in f["ev"]:
            row.locator('[data-e="%s"]' % e).check()
        row.locator('[data-f="r"]').select_option(f["rem"])
    p.focus("#pl-sub"); p.keyboard.press("Enter")
    p.wait_for_function("()=>JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.sub===1")
    assert p.evaluate("()=>JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.oos") == []
    _submit(p)
    p.wait_for_selector("#mx-body .mx-res, #mx-body .mx-list", state="attached")
    rec = p.evaluate(f"JSON.parse(localStorage.getItem('{KEY}'))[0]")
    assert rec["s"] == 1, rec
