"""The home page loads cleanly on every screen we care about."""
import pytest

from conftest import DEVICES, VERSION_LABEL


@pytest.mark.parametrize("device", list(DEVICES))
def test_home_loads(site, device):
    w = site(device=device)
    p = w.page
    # version label matches the built page
    assert VERSION_LABEL and VERSION_LABEL in p.inner_text("body"), "version label %s not shown" % VERSION_LABEL
    # the parts every visitor needs
    for sel in ("#hdr-search", "#hdr-explore", "#cta", "#sheet"):
        assert p.locator(sel).count() == 1, sel
    assert "Not an official U.S. Coast Guard site" in p.inner_text("body")
    # nothing sticks out sideways (a horizontal scrollbar on a phone = something broke)
    over = p.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 1, "page is %d px wider than the screen" % over


@pytest.mark.xdist_group("3d")
def test_full_mode_real_globe(site):
    """Full (non-Lite) mode with the real 3D globe: three.js and Lenis load from vendor/, no errors."""
    w = site(device="desktop", lite=False, wait=5000)
    loaded = w.page.evaluate("[...document.scripts].map(s => s.src).filter(Boolean)")
    assert any(s.endswith("vendor/three.min.js") for s in loaded), loaded
    assert w.page.evaluate("typeof THREE") == "object"


def test_lite_mode_skips_3d(site):
    """Lite mode never downloads three.js (it is what keeps CG laptops fast)."""
    w = site(device="desktop", lite=True)
    loaded = w.page.evaluate("[...document.scripts].map(s => s.src).filter(Boolean)")
    assert not any("three.min.js" in s for s in loaded), loaded


def test_page_structure_is_closed_properly():
    """v2.51: the built page has one explicit </head><body>, and closes with a single </body></html> at the very end
    (the update script used to land after the app's own </body></html>)."""
    import pathlib
    html = (pathlib.Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf8")
    assert html.count("\n</head>\n<body>\n") == 1
    assert html.count("</body>") - html.count("</body>';") == 1, "stray </body> outside the anti-framing string"
    assert html.rstrip().endswith("</body>\n</html>")
    assert html.rindex("serviceWorker") < html.rindex("</body>")
