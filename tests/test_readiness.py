"""Update B (v2.69): readiness score per cert, Countdown's Add to calendar (.ics), and the Clear button for recent runs."""
import json
import re
import time

import pytest
from conftest import open_guide

DAY = 86400000

SEED = r"""
(function(scen, now){
  var D=86400000, ticks=[];
  for(var a=0;a<5;a++) for(var b=0;b<12;b++) ticks.push(a+'-'+b);
  localStorage.setItem('cgcp.secplus.ver', JSON.stringify('v7'));
  localStorage.setItem('cgcp.secplus.v7.done', JSON.stringify(scen==='near'?ticks.slice(0,20):ticks));
  var ws={v:1,d:{},m:{}};
  ['1.0','2.0','3.0','4.0','5.0'].forEach(function(d,i){
    ws.d[d]={c:15,t:20,r:(scen==='near'&&i===2)?'11110000110000111100':'11111111111111111110'};});
  localStorage.setItem('cgcp.ws.secplus', JSON.stringify(ws));
  var p=scen==='near'?[78,88]:[90,88];
  localStorage.setItem('cgcp.mx.secplus', JSON.stringify([
    {t:now-D,k:'full',x:'SY0-701',n:90,s:p[0]*0.9,by:{},u:3000,d:5400,ids:[]},
    {t:now-3*D,k:'full',x:'SY0-701',n:90,s:p[1]*0.9,by:{},u:3000,d:5400,ids:[]}]));
})(%s, %d);
"""


def _seed(w, scen):
    w.page.evaluate(SEED % (json.dumps(scen), int(time.time() * 1000)))


def _exam(w, days=20):
    w.page.evaluate("""(d)=>{var t=new Date(Date.now()+d*86400000);
      var iso=t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0');
      localStorage.setItem('cgcp.exam',JSON.stringify({c:'Security+',d:iso,t:'09:30',w:[1,2,3,4,5,6],h:1.5,done:[]}));}""", days)


def test_readiness_empty_guide(site):
    w = site("desktop")
    open_guide(w.page)
    rd = w.page.inner_text("#rd")
    assert rd.startswith("0") and "Just starting" in rd
    assert "Take a full practice exam" in rd
    assert w.page.locator("#rd [data-fund='cool']").count() == 0


@pytest.mark.parametrize("device", ["desktop", "iphone13", "small320"])
def test_readiness_ready_shows_cool_link(site, device):
    w = site(device)
    _seed(w, "ready")
    w.page.reload()
    w.page.wait_for_timeout(2500)
    open_guide(w.page)
    rd = w.page.inner_text("#rd")
    assert rd.startswith("100") and "Ready" in rd
    btn = w.page.locator("#rd [data-goto='cool'][data-fund='cool']")
    assert btn.count() == 1
    # nothing in the card is wider than the screen
    over = w.page.evaluate("""()=>{var r=document.getElementById('rd').getBoundingClientRect();
      return [...document.querySelectorAll('#rd *')].some(e=>e.getBoundingClientRect().right>r.right+1);}""")
    assert not over


def test_readiness_almost_ready_tip_and_live_refresh(site):
    w = site("desktop")
    _seed(w, "near")
    w.page.reload()
    w.page.wait_for_timeout(2500)
    open_guide(w.page)
    rd = w.page.inner_text("#rd")
    assert "Almost ready" in rd
    assert "Drill 3.0" in rd and "70% or better" in rd
    assert "14 days" in rd
    before = int(re.search(r"(\d+)/28", rd).group(1))
    # ticking an objective updates the score without a reload
    head = w.page.locator("#g-doms .g-dh").last   # domain 5 has nothing ticked in this seed
    head.scroll_into_view_if_needed()
    head.click()
    w.page.wait_for_selector("#g-doms .g-dom.open .g-ck[aria-checked='false']")
    w.page.wait_for_timeout(600)
    w.page.locator("#g-doms .g-dom.open .g-ck[aria-checked='false']").first.click()
    w.page.wait_for_timeout(300)
    assert int(re.search(r"(\d+)/28", w.page.inner_text("#rd")).group(1)) == before + 1


def test_clear_recent_runs_needs_two_taps(site):
    w = site("desktop")
    _seed(w, "ready")
    w.page.reload()
    w.page.wait_for_timeout(2500)
    open_guide(w.page)
    clear = w.page.locator("[data-mx='histclear']")
    clear.scroll_into_view_if_needed()
    clear.click()
    w.page.wait_for_timeout(200)
    assert "again" in w.page.inner_text("[data-mx='histclear']").lower()
    assert w.page.evaluate("localStorage.getItem('cgcp.mx.secplus')") not in (None, "null")
    w.page.click("[data-mx='histclear']")
    w.page.wait_for_timeout(400)
    assert w.page.locator(".mxp-hist").count() == 0
    assert w.page.evaluate("localStorage.getItem('cgcp.mx.secplus')") in (None, "null")
    assert w.page.inner_text("#rd").split("\n")[0] == "50"   # practice part gone, objectives + domains stay


def test_clear_runs_disarms_after_4_seconds(site):
    w = site("desktop")
    _seed(w, "ready")
    w.page.reload()
    w.page.wait_for_timeout(2500)
    open_guide(w.page)
    clear = w.page.locator("[data-mx='histclear']")
    clear.scroll_into_view_if_needed()
    clear.click()
    w.page.wait_for_timeout(4300)
    assert w.page.inner_text("[data-mx='histclear']").strip().lower() == "clear"
    clear.click()
    w.page.wait_for_timeout(300)
    assert w.page.evaluate("localStorage.getItem('cgcp.mx.secplus')") not in (None, "null")


@pytest.mark.parametrize("device", ["desktop", "iphone13"])
def test_countdown_readiness_and_calendar_file(site, device, tmp_path):
    w = site(device, lite=True, accept_downloads=True)
    _seed(w, "ready")
    _exam(w, 20)
    w.page.reload()
    w.page.wait_for_timeout(2500)
    w.page.click(".st-card[data-st='exam']")
    w.page.wait_for_selector("#ex .ex-rd")
    assert "Ready" in w.page.inner_text("#ex .ex-rd")
    with w.page.expect_download() as dl:
        w.page.click("#ex [data-ex='ics']")
    d = dl.value
    assert d.suggested_filename == "MyNextCert-securityplus-study-plan.ics"
    path = tmp_path / "plan.ics"
    d.save_as(path)
    raw = path.read_bytes()
    assert raw.startswith(b"BEGIN:VCALENDAR\r\n") and raw.endswith(b"END:VCALENDAR\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")          # CRLF only
    lines = raw.split(b"\r\n")
    assert max(len(l) for l in lines) <= 75                # folded at 75 bytes
    text = raw.decode("utf-8").replace("\r\n ", "")        # unfold
    assert text.count("BEGIN:VEVENT") == text.count("END:VEVENT") >= 2
    assert "SUMMARY:Security+ exam" in text and "TRIGGER:-P1D" in text
    assert re.search(r"DTSTART;VALUE=DATE:\d{8}", text)
    uids = re.findall(r"UID:(\S+)", text)
    assert len(uids) == len(set(uids))
    # the CG COOL link opens the Funding page on CG COOL
    w.page.wait_for_timeout(2800)
    w.page.click("#ex .ex-rd [data-fund='cool']")
    w.page.wait_for_timeout(1200)
    assert w.page.evaluate("!document.getElementById('fp-cool').hidden")


def test_recent_runs_show_all_12_kept(site):
    """v2.70: the list shows every run the site keeps (12), not just the latest 5."""
    w = site("desktop")
    w.page.evaluate("""()=>{var n=Date.now(), h=[];
      for(var i=0;i<14;i++) h.push({t:n-i*3600000,k:'quick',x:'quiz',n:10,s:7,by:{},u:300,d:600,ids:[]});
      localStorage.setItem('cgcp.mx.secplus',JSON.stringify(h));}""")
    w.page.reload()
    w.page.wait_for_timeout(2500)
    open_guide(w.page)
    assert w.page.locator(".mxp-hist li").count() == 12
