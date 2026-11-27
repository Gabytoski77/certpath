"""v2.81: three links that had gone dead (issue #55) are replaced and must not come back."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
# the page, plus the guides (since v2.83 each guide's links live in guides/<id>.json)
INDEX = (ROOT / "index.html").read_text(encoding="utf-8") + "".join(f.read_text(encoding="utf-8") for f in sorted((ROOT / "guides").glob("*.json")))


def test_dead_links_are_gone_and_replacements_are_there():
    for dead in ("sunyempire.edu/veteran-military/other-groups-served",
                 "lecbyo.files.cmp.optimizely.com/download/b6c8cb98e95511ef89da52ed0d48d8ee",
                 "evalcenter/evaluate-windows-server\""):
        assert dead not in INDEX, dead
    for new in ("sunyempire.edu/student-support/military-veterans/programs/coast-guard.html",
                "comptia.org/en-us/resources/ce/learn/continuing-education-renewal-fees/",
                "evalcenter/evaluate-windows-server-2025"):
        assert new in INDEX, new
