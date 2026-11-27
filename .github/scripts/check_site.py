#!/usr/bin/env python3
"""Checks the built CertPath site before it ships.

Run from the repo root:  python3 .github/scripts/check_site.py
Optional: set BASE_SHA to a commit to also check that sw.js VERSION was
bumped whenever index.html changed since that commit.

Uses only the Python standard library, so there is nothing to install.
"""
import base64
import datetime
import hashlib
import json
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
        # rel="canonical" only names the page's own address for search engines; nothing is loaded
        if tag == "link" and (a.get("rel") or "").lower() == "canonical":
            attr = None
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


def check_404():
    # 6. The "page not found" page: on-brand, links home, runs no scripts, loads nothing from outside (v2.46)
    if not os.path.isfile("404.html"):
        fail("404.html is missing, so wrong links show GitHub's plain error page")
        return
    with open("404.html", encoding="utf-8", newline="") as f:
        html = f.read()
    page = Page()
    page.feed(html)
    page.close()
    if page.outside:
        for tag, url in page.outside:
            fail(f"404.html loads from an outside server: <{tag}> {url[:80]}")
    if page.inline_scripts or re.search(r"<script\b", html, re.I):
        fail("404.html should not contain any script")
    if page.csp is None:
        fail("404.html has no Content-Security-Policy meta tag")
        return
    if directive(page.csp, "script-src") != ["'none'"] or directive(page.csp, "default-src") != ["'none'"]:
        fail("404.html CSP should have default-src 'none' and script-src 'none'")
    style_src = directive(page.csp, "style-src") or []
    if "'unsafe-inline'" not in style_src:
        allowed = {x.strip("'") for x in style_src if x.startswith("'sha256-")}
        for text in re.findall(r"<style>(.*?)</style>", html, re.S):
            digest = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode()
            if f"sha256-{digest}" not in allowed:
                fail("404.html inline style is not in its CSP; rebuild it with make_404.py")
    if 'href="/"' not in html:
        fail("404.html has no link back to the home page")
    if not failures or not any("404.html" in m for m in failures):
        ok("404.html is present, links home, runs no scripts and has a strict CSP")


# ---------- DoD 8140 data against the pinned matrix (v2.47) ----------
PINNED_8140 = os.path.join(".github", "data", "dod8140-v3.0.json")


def js_value(text, i=0):
    """Read one JavaScript literal (object, array, string, number, true/false/null) starting at text[i].
    Object keys may be bare names or quoted. Returns (value, index after it). Never runs any code."""
    def skip(i):
        while i < len(text):
            if text[i] in " \t\r\n":
                i += 1
            elif text.startswith("/*", i):
                i = text.index("*/", i) + 2
            elif text.startswith("//", i):
                i = text.index("\n", i) + 1
            else:
                break
        return i

    def string(i):
        q, i, out = text[i], i + 1, []
        while text[i] != q:
            if text[i] == "\\":
                out.append(text[i + 1])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out), i + 1

    i = skip(i)
    c = text[i]
    if c == "{":
        obj, i = {}, skip(i + 1)
        while text[i] != "}":
            if text[i] in "\"'":
                key, i = string(i)
            else:
                m = re.compile(r"[A-Za-z_$][\w$]*").match(text, i)
                key, i = m.group(0), m.end()
            i = skip(i)
            assert text[i] == ":", "expected ':' at %d" % i
            obj[key], i = js_value(text, i + 1)
            i = skip(i)
            if text[i] == ",":
                i = skip(i + 1)
        return obj, i + 1
    if c == "[":
        arr, i = [], skip(i + 1)
        while text[i] != "]":
            v, i = js_value(text, i)
            arr.append(v)
            i = skip(i)
            if text[i] == ",":
                i = skip(i + 1)
        return arr, i + 1
    if c in "\"'":
        return string(i)
    m = re.compile(r"-?\d+(\.\d+)?|true|false|null").match(text, i)
    assert m, "unexpected %r at %d" % (text[i:i + 20], i)
    t = m.group(0)
    return {"true": True, "false": False, "null": None}.get(t, float(t) if "." in t else int(t) if t[0] in "-0123456789" else t), m.end()


def js_var(html, name):
    m = re.search(r"\bvar %s\s*=\s*" % re.escape(name), html)
    if not m:
        return None
    return js_value(html, m.end())[0]


def check_dod8140():
    # 7. The DoD 8140 work-role data and version label match the pinned matrix (Ideas & Fixes #9)
    if not os.path.isfile(PINNED_8140):
        fail(f"{PINNED_8140} is missing, so the DoD 8140 data can't be checked")
        return
    with open(PINNED_8140, encoding="utf-8") as f:
        pin = json.load(f)
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    before = len(failures)
    try:
        q8, roles, todo, enonly = (js_var(html, n) for n in ("Q8", "Q8_ROLES", "Q8_TODO", "Q8_ENONLY"))
    except Exception as e:  # a malformed literal
        fail(f"DoD 8140 data in index.html could not be read: {e}")
        return
    if not q8 or not roles:
        fail("index.html has no Q8 / Q8_ROLES data")
        return
    if q8.get("ver") != pin["version"]:
        fail(f"DoD 8140 version label is {q8.get('ver')!r}, the pinned matrix is {pin['version']!r}")
    for label in sorted(set(re.findall(r"Matrix V\d+(?:\.\d+)?", html))):
        if label != "Matrix " + pin["version"]:
            fail(f"index.html still mentions '{label}' (pinned matrix is {pin['version']})")
    site, want = set(roles), set(pin["roles"])
    for code in sorted(want - site):
        fail(f"DoD 8140 role {code} is in the pinned matrix but not on the site")
    for code in sorted(site - want):
        fail(f"DoD 8140 role {code} is on the site but not in the pinned matrix")
    for code in sorted(site & want):
        R, P = roles[code], pin["roles"][code]
        if R.get("el") != P["element"]:
            fail(f"DoD 8140 role {code}: element {R.get('el')!r}, pinned {P['element']!r}")
        for lv in ("B", "I", "A"):
            got = R.get(lv)
            if got is None:
                fail(f"DoD 8140 role {code} {pin['levels'][lv]}: not filled in on the site")
                continue
            if len(got) != len(set(got)):
                fail(f"DoD 8140 role {code} {pin['levels'][lv]}: a cert is listed twice")
            extra, missing = sorted(set(got) - set(P[lv])), sorted(set(P[lv]) - set(got))
            if extra:
                fail(f"DoD 8140 role {code} {pin['levels'][lv]}: site lists {', '.join(extra)}, not in the pinned matrix")
            if missing:
                fail(f"DoD 8140 role {code} {pin['levels'][lv]}: pinned matrix lists {', '.join(missing)}, missing on the site")
    todo_codes = {r[0] for el in (todo or {}).values() for r in el}
    if todo_codes != set(pin["no_cert_option"]):
        fail(f"roles shown as 'no cert option' {sorted(todo_codes)} differ from the pinned {sorted(pin['no_cert_option'])}")
    if sorted((enonly or {}).keys()) != sorted(pin["enabler_only_certs"]):
        fail("Q8_ENONLY (certs approved only in Enabler roles) differs from the pinned matrix")
    if len(failures) == before:
        n = sum(len(P[lv]) for P in pin["roles"].values() for lv in ("B", "I", "A"))
        ok(f"DoD 8140 data matches the pinned matrix {pin['version']} ({len(want)} roles, {n} cert listings)")


def inline_guides(html):
    """The small guide index inside index.html (var GUIDES={ "Name":{...}, ... };), one guide per line, plain JSON (v2.83)."""
    a = html.find("var GUIDES={")
    if a < 0:
        return None
    b = html.find("\n};", a)
    if b < 0:
        return None
    try:
        return json.loads(html[a + len("var GUIDES="): b + 2])
    except ValueError:
        return None


def check_guide_dates():
    # Every guide carries checked:"YYYY-MM-DD" (shown on the guide as "Facts last checked"). Missing, malformed or
    # future dates fail; a date older than 45 days only warns (the monthly fact check is due).
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    guides = inline_guides(html)
    if not guides or len(guides) < 30:
        fail("the guide index (var GUIDES={ ... }; as plain JSON) wasn't found in index.html, so guide dates can't be checked")
        return
    today = datetime.date.today()
    before, stale = len(failures), []
    for name, g in guides.items():
        c = g.get("checked")
        if c is None:
            fail(f'guide "{name}" has no checked:"YYYY-MM-DD" field')
            continue
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c):
                raise ValueError
            d = datetime.date.fromisoformat(c)
        except (ValueError, TypeError):
            fail(f'guide "{name}" has a bad checked date {c!r} (use YYYY-MM-DD)')
            continue
        if d > today + datetime.timedelta(days=1):
            fail(f'guide "{name}" has a checked date in the future: {c}')
        elif (today - d).days > 45:
            stale.append(f"{name} ({c}, {(today - d).days} days)")
    if stale:
        print(f"WARN  {len(stale)} guide(s) not fact-checked in over 45 days: " + "; ".join(stale))
    if len(failures) == before:
        ok(f"all {len(guides)} guides have a valid checked date")


def check_guide_files():
    """v2.83: every guide lives in guides/<id>.json, loaded when it opens. The files must match the inline index."""
    sys.path.insert(0, os.path.join("build"))
    import split_guides
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    guides = inline_guides(html)
    if not guides:
        return  # check_guide_dates already reported it
    before = len(failures)
    if re.search(r'(?m)^GUIDES\["', html):
        fail('index.html still holds a whole guide (GUIDES["..."]=); guides must be in guides/*.json')
    want = {g.get("id") + ".json" for g in guides.values()} | {"_search.json"}
    have = set(os.listdir("guides")) if os.path.isdir("guides") else set()
    for extra in sorted(have - want):
        fail(f"guides/{extra} isn't used by any guide in the index")
    for name, g in guides.items():
        path = f"guides/{g['id']}.json"
        if not os.path.isfile(path):
            fail(f"{path} is missing ({name})")
            continue
        raw = open(path, "rb").read()
        try:
            full = json.loads(raw)
        except ValueError as e:
            fail(f"{path} isn't valid JSON ({e})")
            continue
        if split_guides.sha8(raw) != g.get("lz"):
            fail(f"{path}: its hash doesn't match the index (run python3 build/build_site.py)")
        if full.get("id") != g["id"] or not full.get("quiz"):
            fail(f"{path}: wrong id or no quiz")
        if split_guides.slim(full, g.get("lz")) != g:
            fail(f"{path}: the inline index entry for {name} doesn't match the guide file")
    sp = "guides/_search.json"
    lazy = re.search(r'var GUIDES_LAZY=\{"search":"([0-9a-f]{8})"\};', html)
    if not lazy:
        fail("index.html has no GUIDES_LAZY search hash")
    elif not os.path.isfile(sp) or split_guides.sha8(open(sp, "rb").read()) != lazy.group(1):
        fail(f"{sp} is missing or its hash doesn't match the one in index.html")
    if len(failures) == before:
        ok(f"{len(guides)} guide files + search file match the index and their hashes")


def jpeg_size(path):
    """(width, height) of a baseline or progressive JPEG, read from its SOF marker."""
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker, length = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + length
    return None


def check_share_preview():
    # 8. Link previews in Teams, iMessage, email and social apps (Ideas & Fixes #13)
    with open("index.html", encoding="utf-8") as f:
        head = f.read().split("</head>")[0]
    meta = dict(re.findall(r'<meta (?:property|name)="((?:og|twitter):[\w:]+)" content="([^"]*)"', head))
    before = len(failures)
    for key in ("og:title", "og:description", "og:type", "og:url", "og:image", "og:image:width", "og:image:height",
                "og:image:alt", "twitter:card"):
        if not meta.get(key):
            fail(f"share preview: <meta {key}> is missing or empty")
    for key in ("og:url", "og:image", "twitter:image"):
        v = meta.get(key, "")
        if v and not v.startswith("https://mynextcert.com/"):
            fail(f"share preview: {key} should be an https://mynextcert.com/ address, not {v}")
    img = meta.get("og:image", "").replace("https://mynextcert.com/", "")
    if img:
        if not os.path.isfile(img):
            fail(f"share preview: {img} is missing")
        else:
            if os.path.getsize(img) > 300 * 1024:
                fail(f"share preview: {img} is over 300 KB (some apps then skip the picture)")
            size = jpeg_size(img) if img.lower().endswith((".jpg", ".jpeg")) else None
            if size and (str(size[0]), str(size[1])) != (meta.get("og:image:width"), meta.get("og:image:height")):
                fail(f"share preview: {img} is {size[0]}x{size[1]} but the tags say {meta.get('og:image:width')}x{meta.get('og:image:height')}")
    if len(failures) == before:
        ok("share preview tags are complete and point at mynextcert.com")


def alloc(n, domains):
    """Split n questions across domains by weight, largest remainder (same as the page's mxAlloc)."""
    tot = sum(d["w"] for d in domains)
    out, parts, used = {}, [], 0
    for d in domains:
        x = n * d["w"] / tot
        out[d["n"]] = int(x)
        used += int(x)
        parts.append((x - int(x), d["n"]))
    parts.sort(key=lambda p: -p[0])
    i = 0
    while used < n:
        out[parts[i % len(parts)][1]] += 1
        used += 1
        i += 1
    return out


NEW_PBQ_KINDS = ("logsel", "rules", "term", "diagram")


def obj_prefix(d):
    """What a domain's objectives start with: CompTIA-style "1.0" -> "1" (objectives 1.1, 1.2...);
    LPI-style topic "011" -> "011" (objectives 011.1, 011.2...)."""
    return d[:-2] if d.endswith(".0") else d


def check_new_pbq(q, dset):
    """The new PBQ types (v2.84): same rules as vendor/pbq-engine.js, plus the content rules the page can't check:
    every scored part has a non-empty "why", references resolve, and the question has something to get wrong."""
    out = []

    def text(x, n=900):
        return isinstance(x, str) and 0 < len(x.strip()) <= n

    def why(x, label):
        if not isinstance(x, dict) or not text(x.get("why"), 700):
            out.append(f"{label} has no 'why'")
            return
        d = x.get("d", q["d"])
        if "d" in x and x["d"] not in dset:
            out.append(f"{label} has unknown domain {x['d']!r}")
        if "obj" in x and not re.fullmatch(r"\d+\.\d+", str(x["obj"])) or ("obj" in x and str(x["obj"]).split(".")[0] != obj_prefix(d)):
            out.append(f"{label} objective {x.get('obj')!r} doesn't fit domain {d}")

    if not text(q.get("title"), 200) or not text(q.get("scenario")):
        out.append("needs a title and a scenario")
    if "ticket" in q and not text(q["ticket"], 700):
        out.append("bad ticket text")
    k = q["kind"]
    if k == "logsel":
        lines = q.get("lines") or []
        if not 3 <= len(lines) <= 30 or not any(l.get("bad") for l in lines) or all(l.get("bad") for l in lines):
            out.append("needs 3-30 lines, with at least one bad and one normal line")
        for i, l in enumerate(lines):
            if not text(l.get("text"), 320) or l.get("bad") not in (0, 1):
                out.append(f"line {i + 1} needs text and bad = 0 or 1")
            why(l, f"line {i + 1}")
        a = q.get("ask")
        if a is not None:
            if not text(a.get("label"), 200) or not 2 <= len(a.get("opts", [])) <= 6 or not isinstance(a.get("a"), int) or not 0 <= a["a"] < len(a.get("opts", [])):
                out.append("ask needs a label, 2-6 options and a valid answer")
            why(a, "ask")
    elif k == "rules":
        rules = q.get("rules") or []
        ids = {r.get("id"): r for r in rules}
        if not 3 <= len(rules) <= 14 or len(ids) != len(rules):
            out.append("needs 3-14 rules with unique ids")
        if sum(1 for r in rules if r.get("need")) < 2 or all(r.get("need") for r in rules):
            out.append("needs at least 2 needed rules and at least 1 decoy rule")
        for r in rules:
            if not text(r.get("text"), 200) or r.get("need") not in (0, 1) or not re.fullmatch(r"[a-z0-9]{1,6}", str(r.get("id"))):
                out.append(f"rule {r.get('id')!r} needs an id, text and need = 0 or 1")
            why(r, f"rule {r.get('id')!r}")
        for b in q.get("before", []):
            if not (ids.get(b.get("a"), {}).get("need") and ids.get(b.get("b"), {}).get("need")) or b["a"] == b["b"]:
                out.append("a 'before' pair must name two different needed rules")
            why(b, "a 'before' pair")
        if "last" in q:
            if not ids.get((q["last"] or {}).get("id"), {}).get("need"):
                out.append("'last' must name a needed rule")
            why(q["last"] or {}, "'last'")
    elif k == "term":
        cmds, checks = q.get("cmds") or [], q.get("checks") or []
        if not 2 <= len(cmds) <= 40 or not 2 <= len(checks) <= 8:
            out.append("needs 2-40 commands and 2-8 checks")
        facts = set()
        for c in cmds:
            if not c.get("run") or len(c["run"]) > 16 or not all(text(r, 120) and r.count("{ip}") <= 1 for r in c["run"]) or not isinstance(c.get("out"), str) or len(c.get("out", "")) > 1500:
                out.append(f"command {str((c.get('run') or ['?'])[0])!r} needs 'run' lines and 'out'")
            fx = c.get("fx", [])
            facts.update([fx] if isinstance(fx, str) else fx)
        pats = [re.compile("^" + re.escape(f).replace(re.escape("{ip}"), r"(?:\d{1,3}\.){3}\d{1,3}") + "$") for f in facts]
        known = lambda f: any(p.match(f) for p in pats)  # noqa: E731
        as_list = lambda v: v if isinstance(v, list) else [v]  # noqa: E731
        for c in checks:
            if not text(c.get("t"), 200):
                out.append("every check needs a 't' (what the learner has to do)")
            why(c, f"check {str(c.get('t'))[:30]!r}")
            kinds = [x for x in ("has", "lacks", "after") if x in c]
            if len(kinds) != 1:
                out.append(f"check {str(c.get('t'))[:30]!r} needs exactly one of has / lacks / after")
                continue
            refs = as_list(c["has"] if "has" in c else c["lacks"] if "lacks" in c else c["after"]) + (as_list(c.get("of", [])) if "after" in c else [])
            for f in refs:
                if not known(f):
                    out.append(f"check {str(c.get('t'))[:30]!r} uses '{f}', which no command produces")
    elif k == "diagram":
        slots, devs = q.get("slots") or [], q.get("devs") or []
        if not 2 <= len(slots) <= 8 or len(devs) <= len(slots) or len(devs) > 12:
            out.append("needs 2-8 spots and more devices than spots (so some are decoys)")
        used = [d.get("slot") for d in devs if isinstance(d.get("slot"), int) and d["slot"] >= 0]
        if sorted(used) != list(range(len(slots))):
            out.append("every spot needs exactly one correct device")
        if not any(d.get("slot") == -1 for d in devs):
            out.append("needs at least one decoy device (slot -1)")
        for s in slots:
            if not text(s.get("label"), 60) or not text(s.get("zone"), 40):
                out.append("every spot needs a label and a zone")
        for d in devs:
            if not text(d.get("name"), 40) or not re.fullmatch(r"[a-z0-9]{1,6}", str(d.get("id"))):
                out.append(f"device {d.get('id')!r} needs an id and a name")
            why(d, f"device {d.get('id')!r}")
    return out


def check_qbank(path, ver):
    """One practice-exam bank: structure, explanations, coverage, pool sizes, duplicates, answer-length tells."""
    tag = f"question bank {path}"
    try:
        with open(path, encoding="utf-8") as f:
            b = json.load(f)
    except Exception as e:
        fail(f"{tag}: can't be read ({e})")
        return
    if os.path.getsize(path) > 600 * 1024:
        fail(f"{tag}: over 600 KB")
    if b.get("app") != "MyNextCert" or b.get("kind") != "qbank" or b.get("v") != 1 or b.get("ver") != ver:
        fail(f"{tag}: header must be app MyNextCert, kind qbank, v 1, ver {ver!r}")
        return
    F, doms = b.get("format") or {}, b.get("domains") or []
    if not (0 < F.get("n", 0) <= 200 and 0 < F.get("min", 0) <= 400 and 0 <= F.get("pbq", -1) <= 10):
        fail(f"{tag}: format needs n, min and pbq in range")
        return
    if sum(d.get("w", 0) for d in doms) != 100:
        fail(f"{tag}: domain weights add up to {sum(d.get('w', 0) for d in doms)}, not 100")
    dset = {d["n"]: d for d in doms}
    ids, texts, before = set(), set(), len(failures)
    mc_long = mc_n = 0
    per_dom, per_obj = {}, {}
    for q in b.get("q", []):
        qid = q.get("id", "?")
        if not re.fullmatch(r"[a-z0-9-]{3,40}", str(qid)) or qid in ids:
            fail(f"{tag}: bad or repeated id {qid!r}")
        ids.add(qid)
        if q.get("d") not in dset:
            fail(f"{tag}: {qid} has unknown domain {q.get('d')!r}")
            continue
        obj = str(q.get("obj", ""))
        m = re.fullmatch(r"(\d+)\.(\d+)", obj)
        if not m or m.group(1) != obj_prefix(q["d"]) or int(m.group(2)) > dset[q["d"]].get("obj", 99):
            fail(f"{tag}: {qid} objective {obj!r} doesn't fit domain {q['d']}")
        if q.get("t") == "pbq":
            if q.get("kind") == "table":
                good = q.get("cols") and len(q.get("opts", [])) == len(q["cols"]) and q.get("rows") and all(
                    len(r.get("a", [])) == len(q["cols"]) and all(0 <= v < len(q["opts"][ci]) for ci, v in enumerate(r["a"])) and r.get("why") for r in q["rows"])
            elif q.get("kind") == "match":
                good = q.get("choices") and q.get("items") and all(0 <= it.get("a", -1) < len(q["choices"]) and it.get("why") and (it.get("log") or it.get("text")) for it in q["items"])
            elif q.get("kind") in NEW_PBQ_KINDS:
                problems = check_new_pbq(q, dset)
                for pr in problems:
                    fail(f"{tag}: PBQ {qid}: {pr}")
                good = True
            else:
                good = False
            if not good:
                fail(f"{tag}: PBQ {qid} is malformed (every row/item needs a valid answer and a why)")
            continue
        o, a = q.get("o", []), q.get("a")
        if not q.get("q") or not (4 <= len(o) <= 6) or not all(isinstance(x, list) and len(x) == 2 and x[0].strip() and x[1].strip() for x in o):
            fail(f"{tag}: {qid} needs a question and 4-6 options, each with an explanation")
            continue
        if len({x[0].strip().lower() for x in o}) != len(o):
            fail(f"{tag}: {qid} repeats an option")
        right = a if q.get("t") == "ms" else [a]
        if not all(isinstance(x, int) and 0 <= x < len(o) for x in right) or len(set(right)) != len(right):
            fail(f"{tag}: {qid} answer index out of range")
            continue
        if q.get("t") == "ms" and (len(right) < 2 or len(o) < len(right) + 2):
            fail(f"{tag}: {qid} multi-select needs 2+ answers and at least 2 wrong options")
        marked = [i for i, x in enumerate(o) if x[1].startswith("Right.")]
        if sorted(marked) != sorted(right):
            fail(f"{tag}: {qid} explanations starting 'Right.' don't match the answer")
        key = re.sub(r"\W+", " ", q["q"].lower()).strip()
        if key in texts:
            fail(f"{tag}: {qid} duplicates another question")
        texts.add(key)
        per_dom[q["d"]] = per_dom.get(q["d"], 0) + 1
        per_obj[obj] = per_obj.get(obj, 0) + 1
        if q.get("t") != "ms":
            mc_n += 1
            others = max(len(x[0]) for i, x in enumerate(o) if i != a)
            if len(o[a][0]) > others:
                mc_long += 1
    for d in doms:
        for k in range(1, d.get("obj", 0) + 1):
            if per_obj.get(f"{obj_prefix(d['n'])}.{k}", 0) < 2:
                fail(f"{tag}: objective {obj_prefix(d['n'])}.{k} has fewer than 2 questions")
    need = alloc(F["n"] - F["pbq"], doms)
    for dn, n in need.items():
        if per_dom.get(dn, 0) < n:
            fail(f"{tag}: domain {dn} has {per_dom.get(dn, 0)} questions but a full exam needs {n}")
    pbqs = sum(1 for q in b.get("q", []) if q.get("t") == "pbq")
    if pbqs < F["pbq"]:
        fail(f"{tag}: {pbqs} PBQs but a full exam needs {F['pbq']}")
    # the half-length exam (same sums as the page's mxBuild): half of the items, PBQs scaled down, same domain split
    half = F.get("half") or round(F["n"] / 2)
    half_pbq = min(max(1, round(F["pbq"] * half / F["n"])), half) if F["pbq"] else 0
    if not 0 < half < F["n"]:
        fail(f"{tag}: format.half must be between 1 and n ({F['n']})")
    if pbqs < half_pbq:
        fail(f"{tag}: {pbqs} PBQs but a half exam needs {half_pbq}")
    for dn, n in alloc(half - half_pbq, doms).items():
        if per_dom.get(dn, 0) < n:
            fail(f"{tag}: domain {dn} has {per_dom.get(dn, 0)} questions but a half exam needs {n}")
    if mc_n and mc_long / mc_n > 0.4:
        fail(f"{tag}: the right answer is the longest option in {mc_long}/{mc_n} questions (a giveaway); keep it under 40%")
    if len(failures) == before:
        ok(f"{tag}: {len(ids)} items, every objective covered, full exam fits, longest-answer tell {round(100 * mc_long / max(mc_n, 1))}%")


def check_bank_domains(path, ver, gid):
    """A bank's domains must be the guide version's domains (same numbers and names): the results screen and the
    weak-spot tracker look domain names up in the guide by number, so a mismatch shows "Domain 1.0" or the wrong name."""
    tag = f"question bank {path}"
    try:
        with open(f"guides/{gid}.json", encoding="utf-8") as f:
            gdoms = (json.load(f).get("versions") or {}).get(ver, {}).get("domains") or []
        with open(path, encoding="utf-8") as f:
            bdoms = json.load(f).get("domains") or []
    except Exception as e:
        fail(f"{tag}: can't compare with guides/{gid}.json ({e})")
        return
    want = [(d.get("n"), d.get("name")) for d in gdoms]
    got = [(d.get("n"), d.get("name")) for d in bdoms]
    if want != got:
        fail(f"{tag}: domains {got} don't match guide {gid} version {ver} {want}")


def check_qbanks():
    # 9. Practice-exam question banks referenced by the guides (v2.48)
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    refs = {}
    for g in (inline_guides(html) or {}).values():
        for ver, path in (g.get("mock") or {}).items():
            if not re.fullmatch(r"qbank/[a-z0-9-]{3,40}\.json", path):
                fail(f"question bank path {path!r} must be qbank/<name>.json")
                continue
            refs[path] = (ver, g.get("id"))
    for path, (ver, gid) in sorted(refs.items()):
        if not os.path.isfile(path):
            fail(f"{path} is referenced by a guide but missing")
        else:
            check_qbank(path, ver)
            check_bank_domains(path, ver, gid)
    if os.path.isdir("qbank"):
        for f in sorted(os.listdir("qbank")):
            if f.endswith(".json") and "qbank/" + f not in refs:
                fail(f"qbank/{f} isn't used by any guide (remove it or add it to a guide's mock list)")
    if not refs:
        ok("no practice-exam banks yet")


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
    check_404()
    check_dod8140()
    check_guide_dates()
    check_guide_files()
    check_share_preview()
    check_qbanks()
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
