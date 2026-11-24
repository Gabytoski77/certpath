#!/usr/bin/env python3
"""List every guide with its "Facts last checked" date and how many days ago that was, oldest first.
Reads src/app.html line by line. A helper for working sessions; not a public file.  Run:  python3 build/list_guides.py
"""
import datetime
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "app.html"


def main():
    name, rows, inside = None, [], False
    pat = re.compile(r'(?:GUIDES\["([^"]+)"\]=|"([^"]+)":)\{')
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if line.startswith("var GUIDES={"):
            inside = True
            continue
        if line.startswith("G_SECS="):
            break
        m = pat.match(line) if inside else None
        if m:
            name = m.group(1) or m.group(2)
            continue
        c = re.match(r'  checked:"([^"]*)"', line)
        if c and name:
            rows.append((c.group(1), name))
            name = None
    today = datetime.date.today()
    for d, n in sorted(rows):
        try:
            days = (today - datetime.date.fromisoformat(d)).days
            flag = "  <- over 45 days, fact check due" if days > 45 else ""
            print("%-28s %s  %3d days%s" % (n, d, days, flag))
        except ValueError:
            print("%-28s %s  (bad date)" % (n, d))
    print("%d guides" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
