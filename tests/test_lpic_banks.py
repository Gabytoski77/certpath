"""v2.95: the four LPIC banks are wired to their guides, (tests/test_bank_smoke.py opens every bank, these four included)."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANKS = {"101-500": ("LPIC-1", "e101"), "102-500": ("LPIC-1", "e102"),
         "201-450": ("LPIC-2", "e201"), "202-450": ("LPIC-2", "e202")}


def test_banks_headers_and_wiring():
    app = (ROOT / "src/app.html").read_text(encoding="utf-8")
    for code, (cert, ver) in BANKS.items():
        b = json.loads((ROOT / f"qbank/{code}.json").read_text(encoding="utf-8"))
        assert b["cert"] == cert and b["exam"] == code and b["ver"] == ver, code
        assert b["format"]["n"] == 60 and b["format"]["min"] == 90, code
        i = app.index(f'GUIDES["{cert}"]=')
        assert f'{ver}:"qbank/{code}.json"' in app[i:i + 1500], code

