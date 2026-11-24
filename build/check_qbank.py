#!/usr/bin/env python3
"""Fast check of ONE practice-exam question bank, using the exact same rules as .github/scripts/check_site.py
(structure, explanations, coverage, duplicates, answer-length tell). A helper for working sessions; not a public file.

  python3 build/check_qbank.py qbank/100-140.json
"""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
os.chdir(ROOT)
import check_site  # noqa: E402


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    path = argv[0]
    try:
        ver = json.load(open(path, encoding="utf-8")).get("ver")
    except Exception as e:
        print("FAIL  can't read %s (%s)" % (path, e))
        return 1
    check_site.check_qbank(path, ver)
    return 1 if check_site.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
