#!/usr/bin/env python3
"""Print ONE guide from src/app.html, so nobody has to open the 1.7 MB file. A helper for working sessions; not a public file.

  python3 build/show_guide.py "CCST IT Support"             the whole guide object
  python3 build/show_guide.py "CCST IT Support" --outline    just each top-level key (cut to 110 chars), to see its shape
  python3 build/show_guide.py --names                        every guide name

Output starts with the line numbers in src/app.html (for Read offset/limit) so you can then edit with the Edit tool.
"""
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "app.html"


def guides(lines):
    """[(name, first_line_index, last_line_index_exclusive)] for every GUIDES["Name"]={ block."""
    top = next((i for i, l in enumerate(lines) if l.startswith("var GUIDES={")), 0)  # the first guide ("Security+") sits right under it
    end_all = next((i for i, l in enumerate(lines) if l.startswith("G_SECS=")), len(lines))
    pat = re.compile(r'(?:GUIDES\["([^"]+)"\]=|"([^"]+)":)\{')
    starts = [(i, m.group(1) or m.group(2)) for i in range(top, end_all) if (m := pat.match(lines[i]))]
    return [(n, i, starts[k + 1][0] if k + 1 < len(starts) else end_all) for k, (i, n) in enumerate(starts)]


def main(argv):
    lines = SRC.read_text(encoding="utf-8").splitlines()
    found = guides(lines)
    if "--names" in argv or not [a for a in argv if not a.startswith("--")]:
        print("\n".join(n for n, _, _ in found))
        return 0
    want = [a for a in argv if not a.startswith("--")][0].lower()
    hit = [g for g in found if g[0].lower() == want] or [g for g in found if want in g[0].lower()]
    if len(hit) != 1:
        print("no single match for %r; guides: %s" % (want, ", ".join(n for n, _, _ in found)), file=sys.stderr)
        return 1
    name, a, b = hit[0]
    print("# %s: src/app.html lines %d-%d" % (name, a + 1, b))
    for i in range(a, b):
        l = lines[i]
        if "--outline" in argv and not re.match(r'^(GUIDES\[|"[^"]+":\{|  [A-Za-z_]+:)', l):
            continue
        print("%d: %s" % (i + 1, l[:110] + ("..." if len(l) > 110 else "") if "--outline" in argv else l))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
