"""v2.65: the vendor crests next to the globe looked doubled and glitchy on work PCs.

Faded crests were see-through (opacity on the whole crest), so the globe picture's own vendor badges showed
through them; the still globe also re-decoded each picture inside the visible <img>. Now each crest sits on a
solid hexagon and the decoded globe picture is swapped in whole.
"""
import pytest


@pytest.mark.parametrize("lite", [pytest.param(False, marks=pytest.mark.xdist_group("3d")), True])
def test_crests_are_solid(site, lite):
    w = site(lite=lite)
    p = w.page
    r = p.evaluate("""(() => [...document.querySelectorAll('#ro-dots .crest')].map(c => {
        const h0 = c.querySelector('.h0');
        return [getComputedStyle(c).opacity, h0 ? getComputedStyle(h0).fill : null, c.getAttribute('aria-current')];
    }))()""")
    assert len(r) == 8
    for op, fill, cur in r:
        assert op == "1", r
        assert fill == "rgb(6, 9, 14)", r          # opaque: nothing behind shows through


def test_light_mode_keeps_one_decoded_globe_picture(site):
    w = site(lite=True, wait=3500)
    p = w.page
    cr = p.locator("#ro-dots .crest")
    for i in (3, 5, 2):
        b = cr.nth(i).bounding_box()
        p.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=3)
        p.wait_for_timeout(1200)
        imgs = p.evaluate("[...document.querySelectorAll('#gpic img')].map(i => [i.getAttribute('src'), i.complete && i.naturalWidth > 0])")
        assert len(imgs) == 1, imgs
        assert imgs[0][1], imgs
    assert "cisco" in imgs[0][0], imgs


@pytest.mark.parametrize("size", [(1366, 657), (1440, 900)])
def test_vendor_text_stays_put_while_hovering_crests(site, size):
    """A longer vendor blurb used to drop the text from above the wordmark to under it (unreadable) on work-laptop
    screens. Now the blurb keeps the height of the longest one, and if the text can't go above the word it gets a
    dark backing ("over")."""
    w = site(lite=True, wait=3000, viewport={"width": size[0], "height": size[1]})
    p = w.page
    seen = set()
    for i in range(8):
        b = p.locator("#ro-dots .crest").nth(i).bounding_box()
        p.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=2)
        p.wait_for_timeout(350)
        cls, top = p.evaluate("[document.getElementById('readout').className, Math.round(document.querySelector('.ro-head').getBoundingClientRect().top)]")
        assert "split" in cls or "over" in cls, cls
        seen.add((cls, top // 3))
    assert len({c for c, _ in seen}) == 1, seen
    tops = sorted(t for _, t in seen)
    assert tops[-1] - tops[0] <= 1, seen
