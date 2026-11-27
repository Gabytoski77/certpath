"""v2.94: check_site fails a bank whose right answer is nearly always one of the two longest options."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))


def _bank(tmp_path, second_longest):
    """A tiny valid bank where the key is the second-longest option in `second_longest` of 10 questions."""
    qs = []
    for i in range(10):
        opts = [["Short wrong one", "No."], ["A medium wrong option", "No."],
                ["The longest wrong option of the four by far", "No."], ["Tiny", "No."]]
        key = "The right answer, second longest" if i < second_longest else "Right one"
        opts[0] = [key, "Right. It fits."]
        qs.append({"id": f"t-1-{i:02d}", "d": "1.0", "obj": "1.1", "q": f"Question number {i}?", "o": opts, "a": 0})
    b = {"app": "MyNextCert", "kind": "qbank", "v": 1, "ver": "cur", "cert": "T", "exam": "T", "title": "T", "rev": "2026-11-27",
         "format": {"n": 4, "min": 5, "pbq": 0, "half": 2}, "domains": [{"n": "1.0", "name": "D", "w": 100, "obj": 1}], "note": "x", "q": qs}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(b), encoding="utf-8")
    return str(p)


def test_top_two_tell_fails_only_when_extreme(tmp_path):
    import check_site
    check_site.failures.clear()
    check_site.check_qbank(_bank(tmp_path, 10), "cur")
    assert any("two longest" in m for m in check_site.failures)
    check_site.failures.clear()
    check_site.check_qbank(_bank(tmp_path, 4), "cur")
    assert not check_site.failures, check_site.failures
