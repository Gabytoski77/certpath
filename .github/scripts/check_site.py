#!/usr/bin/env python3
"""Checks the built CertPath site before it ships.

Run from the repo root:  python3 .github/scripts/check_site.py
Optional: set BASE_SHA to a commit to also check that sw.js VERSION was
bumped whenever index.html changed since that commit.

Uses only the Python standard library, so there is nothing to install.
"""
import base64
import hashlib
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

ZERO_SHA = "0" * 40
OUTSIDE = re.compile(r"^\s*(https?:)?//", re.I)
# Tags that make the browser fetch something, and the attribute that says where from.
# Ordinary <a href> links to other sites are fine: they load nothing until clicked.
LOADERS = {
    "script": "src", "link": "href", "img": "src", "iframe": "src",
    "source": "src", "video": "src", "audio": "src", "embed": "src",
    "object": "data",
}

failures = []


def fail(msg):
    failures.append(msg)
    print(f"FAIL  {msg}")


def ok(msg):
    print(f"ok    {msg}")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.outside = []        # (tag, url) loaded from another server
        self.inline_scripts = [] # text of each inline <script>
        self.csp = None
        self._in_inline = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        attr = LOADERS.get(tag)
        if attr and a.get(attr) and OUTSIDE.match(a[attr]):
            self.outside.append((tag, a[attr]))
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "content-security-policy":
            self.csp = a.get("content") or ""
        if tag == "script" and "src" not in a:
            kind = (a.get("type") or "").lower()
            # JSON data blocks are not executed, so the CSP does not need their hash
            if kind in ("", "text/javascript", "module", "application/javascript"):
                self._in_inline = True
                self._buf = []

    def handle_data(self, data):
        if self._in_inline:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_inline:
            self.inline_scripts.append("".join(self._buf))
            self._in_inline = False


def directive(csp, name):
    for part in csp.split(";"):
        words = part.split()
        if words and words[0].lower() == name:
            return words[1:]
    return None


def check_index():
    with open("index.html", encoding="utf-8", newline="") as f:
        html = f.read()
    page = Page()
    page.feed(html)
    page.close()

    # 1. Nothing is loaded from another server
    if page.outside:
        for tag, url in page.outside:
            fail(f"index.html loads from an outside server: <{tag}> {url[:80]}")
    else:
        ok("index.html loads nothing from outside servers")

    # 2. A Content Security Policy is present and strict
    if page.csp is None:
        fail("index.html has no Content-Security-Policy meta tag")
        return
    ok("Content-Security-Policy meta tag is present")

    if directive(page.csp, "default-src") != ["'self'"]:
        fail("CSP default-src should be exactly 'self'")
    else:
        ok("CSP default-src is 'self'")

    script_src = directive(page.csp, "script-src") or []
    for bad in ("'unsafe-inline'", "'unsafe-eval'", "*", "http:", "https:"):
        if bad in script_src:
            fail(f"CSP script-src contains {bad}, which would let injected scripts run")
    outside_hosts = [s for s in script_src if not s.startswith("'")]
    if outside_hosts:
        fail(f"CSP script-src allows outside hosts: {' '.join(outside_hosts)}")

    # 3. Every inline script matches a hash in the CSP (a hand-edited script breaks this)
    allowed = {s.strip("'") for s in script_src if s.startswith("'sha256-")}
    missing = 0
    for i, text in enumerate(page.inline_scripts, 1):
        digest = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode()
        if f"sha256-{digest}" not in allowed:
            missing += 1
            fail(f"inline script #{i} is not in the CSP (sha256-{digest}); rebuild with the build script")
    if not missing:
        ok(f"all {len(page.inline_scripts)} inline scripts match a CSP hash")


def sw_version(text):
    m = re.search(r'var\s+VERSION\s*=\s*"(certpath-v\d+)"', text)
    return m.group(1) if m else None


def check_sw():
    with open("sw.js", encoding="utf-8") as f:
        sw = f.read()

    version = sw_version(sw)
    if not version:
        fail('sw.js VERSION should look like "certpath-v37"')
    else:
        ok(f"sw.js VERSION is {version}")

    # 4. Every file the service worker caches on install exists.
    #    One missing file makes the whole install fail, so the app would not work offline.
    m = re.search(r"var\s+SHELL\s*=\s*\[(.*?)\]", sw, re.S)
    if not m:
        fail("sw.js has no SHELL list")
        return version
    files = re.findall(r'"([^"]+)"', m.group(1))
    gone = [p for p in files if not os.path.isfile(p)]
    for p in gone:
        fail(f"sw.js SHELL lists a file that is not in the repo: {p}")
    if not gone:
        ok(f"all {len(files)} files in the sw.js SHELL list exist")
    return version


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def check_bump(version):
    # 5. If index.html changed, VERSION must change too, or installed phones keep the old copy
    base = os.environ.get("BASE_SHA", "").strip()
    if not base or base == ZERO_SHA:
        print("skip  version-bump check (no BASE_SHA to compare against)")
        return
    if git("cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        print(f"skip  version-bump check (commit {base[:7]} is not available)")
        return
    if git("diff", "--quiet", base, "HEAD", "--", "index.html").returncode == 0:
        ok("index.html unchanged, so no version bump is needed")
        return
    old = git("show", f"{base}:sw.js")
    old_version = sw_version(old.stdout) if old.returncode == 0 else None
    if old_version and old_version == version:
        fail(f"index.html changed but sw.js VERSION is still {version}; bump it so phones update")
    else:
        ok(f"index.html changed and sw.js VERSION was bumped ({old_version} -> {version})")


def main():
    check_index()
    version = check_sw()
    check_bump(version)
    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
