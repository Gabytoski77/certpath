"""Fail the build on NEW Semgrep findings only.

The app builds its screens with innerHTML on purpose; every string from data or the user goes through gEsc()
first. Semgrep flags each innerHTML use, so the ones that existed when the pipeline was added (Nov 17, 2026)
are listed in tests/semgrep-baseline.json. A new one fails the check, so a human has to look at it.

  python3 build/semgrep_gate.py semgrep.json            # compare with the baseline (CI)
  python3 build/semgrep_gate.py semgrep.json --update   # accept the current findings (after reviewing them!)

A finding is identified by its rule plus the text of the flagged code (not the line number), so moving code
around doesn't trip the gate but adding or changing a flagged line does.
"""
import collections, hashlib, json, pathlib, sys

BASE = pathlib.Path(__file__).resolve().parent.parent / "tests" / "semgrep-baseline.json"
BLOCK = {"ERROR", "WARNING"}


_files = {}


def flagged_code(r):
    """The exact code Semgrep flagged, read from the file (the CLI hides it as "requires login" when logged out)."""
    path = r["path"]
    if path not in _files:
        _files[path] = pathlib.Path(path).read_bytes()
    return _files[path][r["start"]["offset"]:r["end"]["offset"]].decode("utf8", "replace")


def key(r):
    code = " ".join(flagged_code(r).split())
    return r["check_id"].split(".")[-1] + " " + hashlib.sha256(code.encode()).hexdigest()[:16]


def main():
    data = json.load(open(sys.argv[1]))
    if data.get("errors"):
        for e in data["errors"]:
            print("note: semgrep:", str(e.get("message") or e.get("type"))[:200])
    found = [r for r in data["results"] if r["extra"].get("severity") in BLOCK]
    now = collections.Counter(key(r) for r in found)
    if "--update" in sys.argv:
        BASE.write_text(json.dumps(dict(sorted(now.items())), indent=1) + "\n")
        print("baseline updated:", sum(now.values()), "findings")
        return 0
    base = collections.Counter(json.loads(BASE.read_text()))
    new = now - base
    if not new:
        print("ok: no new Semgrep findings (%d known, all in the baseline)" % sum(now.values()))
        return 0
    print("NEW Semgrep findings (check each one; if it is safe, run the --update command in this file's header):")
    for r in found:
        k = key(r)
        if new[k] > 0:
            new[k] -= 1
            print("  %s:%s  %s\n      %s\n      %s" % (r["path"], r["start"]["line"], r["check_id"].split(".")[-1],
                                                     " ".join(flagged_code(r).split())[:240], r["extra"]["message"][:240]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
