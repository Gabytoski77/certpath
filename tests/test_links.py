"""v2.81: three links that had gone dead (issue #55) are replaced and must not come back."""
import pathlib

INDEX = (pathlib.Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")


def test_dead_links_are_gone_and_replacements_are_there():
    for dead in ("sunyempire.edu/veteran-military/other-groups-served",
                 "lecbyo.files.cmp.optimizely.com/download/b6c8cb98e95511ef89da52ed0d48d8ee",
                 "evalcenter/evaluate-windows-server\""):
        assert dead not in INDEX, dead
    for new in ("sunyempire.edu/student-support/military-veterans/programs/coast-guard.html",
                "comptia.org/en-us/resources/ce/learn/continuing-education-renewal-fees/",
                "evalcenter/evaluate-windows-server-2025"):
        assert new in INDEX, new
