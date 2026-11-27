"""v2.93: the four new cloud banks (AZ-104, SC-500, SAA-C03, SCS-C03) are wired to their guides and fill a full exam."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
# bank file: (guide name, version key, domains, objectives, full exam items, minutes)
BANKS = {
    "az-104": ("Azure Administrator", "cur", 5, 15, 50, 100),
    "sc-500": ("Cloud and AI Security Engineer", "cur", 4, 12, 50, 100),
    "saa-c03": ("Solutions Architect Associate", "c03", 4, 14, 65, 130),
    "scs-c03": ("Security Specialty", "c03", 6, 16, 65, 170),
}
NEW_KINDS = {"logsel", "rules", "term", "diagram"}


def _bank(code):
    return json.loads((ROOT / f"qbank/{code}.json").read_text(encoding="utf-8"))


def test_headers_and_domains():
    for code, (cert, ver, ndom, nobj, n, mins) in BANKS.items():
        b = _bank(code)
        assert b["cert"] == cert and b["exam"] == code.upper() and b["ver"] == ver, code
        assert len(b["domains"]) == ndom and sum(d["obj"] for d in b["domains"]) == nobj, code
        assert b["format"]["n"] == n and b["format"]["min"] == mins, code


def test_every_objective_has_three_questions():
    for code, (_, _, _, nobj, _, _) in BANKS.items():
        count = {}
        for x in _bank(code)["q"]:
            if x.get("t") != "pbq":
                count[x["obj"]] = count.get(x["obj"], 0) + 1
        assert len(count) == nobj, (code, sorted(count))
        assert min(count.values()) >= 3, (code, count)


def test_new_engine_pbqs_with_three_kinds():
    for code in BANKS:
        kinds = [x["kind"] for x in _bank(code)["q"] if x.get("t") == "pbq"]
        assert set(kinds) <= NEW_KINDS and 4 <= len(kinds) <= 6 and len(set(kinds)) >= 3, (code, kinds)


def test_guides_point_at_the_banks():
    app = (ROOT / "src/app.html").read_text(encoding="utf-8")
    for code, (cert, ver, *_rest) in BANKS.items():
        i = app.index(f'GUIDES["{cert}"]=')
        head = app[i:i + 1200]
        assert f'mock:{{{ver}:"qbank/{code}.json"}}' in head, cert
        assert "mockText:" in head, cert
