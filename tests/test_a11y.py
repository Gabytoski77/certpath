"""Accessibility with axe-core (WCAG 2.1 A/AA rules).

Fails on "critical" and "serious" problems, except the ones listed in KNOWN below, which existed before the
pipeline was added (Nov 17, 2026) and are tracked to be fixed. A NEW problem fails the build.
To fix one: fix it in src/app.html, rebuild, and delete its line from KNOWN.
"""
import json, pathlib

import pytest

from conftest import open_guide

AXE = pathlib.Path(__file__).parent / "node_modules" / "axe-core" / "axe.min.js"

# rule id -> why it is allowed for now (filled from the first run)
KNOWN = json.loads((pathlib.Path(__file__).parent / "a11y-known.json").read_text())


def _axe(p):
    if not AXE.exists():
        pytest.skip("axe-core not installed (cd tests && npm ci)")
    # evaluate() runs through the browser's debugger, not as a page script, so the CSP does not block it
    p.evaluate(AXE.read_text() + ";0")
    return p.evaluate("""async () => (await axe.run(document, {
        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}, resultTypes: ['violations']
    })).violations.map(v => ({id: v.id, impact: v.impact, help: v.help, n: v.nodes.length,
                              where: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))""")


def _check(violations, screen):
    bad = [v for v in violations if v["impact"] in ("critical", "serious") and v["id"] not in KNOWN.get(screen, {})]
    assert not bad, "new accessibility problems on %s:\n%s" % (screen, json.dumps(bad, indent=1))


@pytest.mark.parametrize("device", ["desktop", "iphone13"])
def test_home_a11y(site, device):
    _check(_axe(site(device=device).page), "home")


def test_guide_a11y(site):
    p = site().page
    open_guide(p, "security+")
    _check(_axe(p), "guide")


def test_404_a11y(site):
    _check(_axe(site(path="missing-page", wait=600).page), "404")
