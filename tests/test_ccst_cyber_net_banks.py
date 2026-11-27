"""v2.89: the two new Cisco CCST banks (Cybersecurity 100-160, Networking 100-150) are wired to their guides."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANKS = {"100-160": ("CCST Cybersecurity", 5, 23), "100-150": ("CCST Networking", 6, 25)}
NEW_KINDS = {"logsel", "rules", "term", "diagram"}


def _bank(code):
    return json.loads((ROOT / f"qbank/{code}.json").read_text(encoding="utf-8"))


def test_headers_and_domains():
    for code, (cert, ndom, nobj) in BANKS.items():
        b = _bank(code)
        assert b["cert"] == cert and b["exam"] == code and b["ver"] == "cur"
        assert len(b["domains"]) == ndom and sum(d["obj"] for d in b["domains"]) == nobj
        assert b["format"]["n"] == 45 and b["format"]["min"] == 50


def test_every_objective_has_two_questions():
    for code, (_, _, nobj) in BANKS.items():
        b = _bank(code)
        count = {}
        for x in b["q"]:
            if x.get("t") != "pbq":
                count[x["obj"]] = count.get(x["obj"], 0) + 1
        assert len(count) == nobj, (code, sorted(count))
        assert min(count.values()) >= 2, (code, count)


def test_four_to_six_new_engine_pbqs():
    for code in BANKS:
        kinds = [x["kind"] for x in _bank(code)["q"] if x.get("t") == "pbq" and x.get("kind") in NEW_KINDS]
        assert 4 <= len(kinds) <= 6 and len(set(kinds)) >= 3, (code, kinds)


def test_guides_point_at_the_banks():
    app = (ROOT / "src/app.html").read_text(encoding="utf-8")
    for code, (cert, _, _) in BANKS.items():
        i = app.index(f'GUIDES["{cert}"]=')
        head = app[i:i + 900]
        assert f'mock:{{cur:"qbank/{code}.json"}}' in head, cert
        assert "mockText:" in head and "doesn't publish" in head, cert
