"""After a deploy: check the LIVE site (https://mynextcert.com) is the version we just shipped and still locked down.

Retries for up to SMOKE_WAIT seconds (default 600) because GitHub Pages and Cloudflare take a moment to update.
No browser needed; standard library only.

  python3 tests/smoke_live.py [https://mynextcert.com/]
"""
import os, pathlib, re, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://mynextcert.com/").rstrip("/") + "/"
WAIT = int(os.environ.get("SMOKE_WAIT", "600"))
UA = "MyNextCert-deploy-check/1.0 (+https://mynextcert.com/)"

local_index = (ROOT / "index.html").read_text(encoding="utf8")
LABEL = re.search(r"v\.2\.\d+", local_index).group(0)
CSP = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', local_index).group(1)
SW_VERSION = re.search(r'var VERSION = "(certpath-v\d+)"', (ROOT / "sw.js").read_text()).group(1)


def get(path):
    req = urllib.request.Request(BASE + path + ("&" if "?" in path else "?") + "smoke=%d" % time.time(),
                                 headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode("utf8", "replace")


def checks():
    problems = []
    s, h, body = get("")
    if s != 200:
        return ["home page returned %s" % s]
    if LABEL not in body:
        problems.append("home page does not show %s yet" % LABEL)
    if CSP not in body:
        problems.append("live CSP is different from the committed index.html")
    if h.get("x-content-type-options", "").lower() != "nosniff":
        problems.append("missing X-Content-Type-Options: nosniff")
    if "sameorigin" not in h.get("x-frame-options", "").lower():
        problems.append("missing X-Frame-Options: SAMEORIGIN (Cloudflare Managed Transform)")
    for bad in ("rocket-loader", "email-decode", "cloudflareinsights", "beacon.min.js"):
        if bad in body:
            problems.append("Cloudflare injected %s into the page (turn it off; the CSP blocks it)" % bad)
    s, _, sw = get("sw.js")
    if s != 200 or SW_VERSION not in sw:
        problems.append("sw.js is not %s yet (status %s)" % (SW_VERSION, s))
    for path, want in (("404.html", 200), ("manifest.webmanifest", 200), ("robots.txt", 200), ("sitemap.xml", 200),
                       (".well-known/security.txt", 200), ("qbank/sy0-701.json", 200), ("vendor/three.min.js", 200),
                       ("fonts/fonts.css", 200), ("this-page-does-not-exist", 404)):
        s, _, b = get(path)
        if s != want:
            problems.append("%s returned %s, expected %s" % (path, s, want))
        if path == "this-page-does-not-exist" and "This page isn" not in b:
            problems.append("missing pages do not show the MyNextCert 404 page")
    # private files must NOT be online (they were before the pipeline)
    for path in ("src/app.html", "build/build_site.py", "tests/conftest.py", "README.md", ".github/scripts/check_site.py"):
        s, _, _ = get(path)
        if s == 200:
            problems.append("private file is public: /" + path)
    return problems


def main():
    deadline = time.time() + WAIT
    while True:
        problems = checks()
        if not problems:
            print("ok: %s is live at %s and every check passed" % (LABEL, BASE))
            return 0
        if time.time() > deadline:
            print("FAIL: live site checks failed:\n  " + "\n  ".join(problems))
            return 1
        print("waiting for the live site (%s)..." % "; ".join(problems[:2]))
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
