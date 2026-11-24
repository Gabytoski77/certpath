"""v2.82: three CCST IT Support questions were reworded so the question matches its one right answer."""
import json
import pathlib

BANK = {x["id"]: x for x in json.loads((pathlib.Path(__file__).resolve().parent.parent / "qbank/100-140.json").read_text(encoding="utf-8"))["q"]}


def _right(i):
    x = BANK[i]
    return x, x["o"][x["a"]][0]


def test_it_4_25_asks_for_a_cause_and_the_answer_is_one():
    x, right = _right("it-4-25")
    assert "likely cause" in x["q"] and "saved" in right and not right.lower().startswith("update"), right


def test_it_4_16_answer_names_the_steps():
    _, right = _right("it-4-16")
    assert "airplane" in right and "cellular" in right and "VPN" in right, right


def test_it_3_12_says_the_panel_is_on():
    x, right = _right("it-3-12")
    assert "is on" in x["q"] and "restart" in right, (x["q"], right)
