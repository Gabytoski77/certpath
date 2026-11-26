"""v2.86 (PR 3): the "New version ready" bar, the Install app link, .woff2 fonts and the preview-only icon."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "src" / "app.html").read_text(encoding="utf-8")


def _wait_for_sw(p):
    p.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== null", timeout=45000)


# ---- "New version ready - Refresh" ----

def test_update_bar_shows_on_message_and_refreshes(site):
    w = site(wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.wait_for_timeout(800)
    assert not p.is_visible("#upd-tip"), "the bar must stay hidden until there is an update"
    p.evaluate("navigator.serviceWorker.dispatchEvent(new MessageEvent('message',{data:{type:'update-ready'}}))")
    p.wait_for_selector("#upd-tip:not([hidden])", timeout=3000)
    assert "New version ready" in p.inner_text("#upd-tip")
    p.evaluate("window.__before = 1")
    with p.expect_navigation():
        p.click("#upd-go")
    assert p.evaluate("window.__before") is None, "Refresh should reload the page"


def test_update_bar_can_be_dismissed_and_ignores_other_messages(site):
    w = site(wait=1500)
    p = w.page
    p.evaluate("navigator.serviceWorker.ready")
    p.reload()
    _wait_for_sw(p)
    p.evaluate("navigator.serviceWorker.dispatchEvent(new MessageEvent('message',{data:{type:'something-else'}}))")
    p.wait_for_timeout(300)
    assert not p.is_visible("#upd-tip")
    p.evaluate("navigator.serviceWorker.dispatchEvent(new MessageEvent('message',{data:{type:'update-ready'}}))")
    p.wait_for_selector("#upd-tip:not([hidden])", timeout=3000)
    p.click("#upd-x")
    assert not p.is_visible("#upd-tip")


def test_new_service_worker_no_longer_reloads_under_the_reader():
    """The update script shows the bar on controllerchange instead of calling location.reload() by itself."""
    tail = (ROOT / "src" / "site-tail.html").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", tail, flags=re.S)
    cc = code[code.index('"controllerchange"'):]
    cc = cc[:cc.index(");") + 2]
    assert "showUpdate" in cc and "reload" not in cc, cc


# ---- Install app ----

_FAKE_PROMPT = """() => {
  window.__prompted = 0;
  const e = new Event('beforeinstallprompt', {cancelable: true});
  e.prompt = () => { window.__prompted++; return Promise.resolve(); };
  e.userChoice = Promise.resolve({outcome: 'accepted'});
  window.dispatchEvent(e);
}"""


def test_install_link_hidden_until_the_browser_offers_it(site):
    p = site("desktop").page
    assert not p.locator(".inst-btn:visible").count(), "no Install link without the browser's offer"
    p.evaluate(_FAKE_PROMPT)
    assert p.locator(".inst-btn:visible").count() == 1, "one Install app link in the visible footer"
    p.locator(".inst-btn:visible").first.click()
    assert p.evaluate("window.__prompted") == 1, "the click should open the browser's install prompt"
    p.wait_for_timeout(300)
    assert not p.locator(".inst-btn:visible").count(), "the prompt runs once, so the link hides after it"


def test_install_section_in_settings(site):
    p = site("desktop").page
    p.evaluate(_FAKE_PROMPT)
    assert p.evaluate("!document.getElementById('set-inst').hidden")
    assert p.evaluate("!document.getElementById('set-inst-b').hidden")
    assert "Start menu" in p.text_content("#set-inst-p")
    p.evaluate("window.dispatchEvent(new Event('appinstalled'))")
    assert p.evaluate("document.getElementById('set-inst').hidden"), "hide it once installed"
    assert not p.locator(".inst-btn:visible").count()


def test_iphone_gets_add_to_home_screen_hint(site):
    p = site("iphone13").page
    assert p.evaluate("!document.getElementById('set-inst').hidden"), "iPhone has no prompt, so Settings explains it"
    assert p.evaluate("document.getElementById('set-inst-b').hidden")
    assert "Add to Home Screen" in p.text_content("#set-inst-p")
    assert not p.locator(".inst-btn:visible").count()


def test_settings_search_finds_install(site):
    assert re.search(r'snorm\("install app add to home screen', APP)


# ---- fonts and the preview icon ----

def test_fonts_are_woff2_only():
    css = (ROOT / "fonts" / "fonts.css").read_text()
    urls = re.findall(r'url\("([^"]+)"\)', css)
    assert urls and all(u.endswith(".woff2") for u in urls), urls
    for u in urls:
        assert (ROOT / "fonts" / u).stat().st_size > 1000, u
    assert not list((ROOT / "fonts").glob("*.woff")), "old .woff files should be gone"
    assert 'type="font/woff2"' in INDEX and ".woff\"" not in INDEX


def test_fonts_load_from_woff2(site):
    w = site("desktop")
    p = w.page
    # ask for each font explicitly (a font the screen hasn't used yet isn't loaded on its own)
    got = p.evaluate("""async () => {
      const out = {};
      for (const f of ['600 16px "Inter Tight"', '16px "Geist"', '400 16px "CP Mono"', '500 16px "CP Mono"']) {
        const faces = await document.fonts.load(f);
        out[f] = faces.length && faces.every(x => x.status === 'loaded');
      }
      return out; }""")
    assert all(got.values()), got


def test_preview_icon_is_preview_only():
    """src/app.html (the claude.ai preview) carries the real icon; the live index.html keeps its own icon tags only."""
    head = APP[:APP.index('<meta name="referrer"')]
    assert re.search(r'<link rel="icon" type="image/png" sizes="96x96" href="data:image/png;base64,', head)
    assert "data:image/png;base64" not in INDEX
