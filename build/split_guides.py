"""Split the cert guides out of src/app.html, at build time (v2.83).

src/app.html keeps every guide inline, exactly as authored (the claude.ai preview artifact, the helper scripts and the
guide skill all keep working). For the live site this module:

  * parses each guide (`var GUIDES={ "Security+":{...} };` and every `GUIDES["Name"]={...};` after it) as plain data,
    never running any code,
  * writes guides/<id>.json: the whole guide, fetched when someone opens it,
  * writes guides/_search.json: the parts the search needs (everything except the quiz and the long texts),
  * leaves a small inline index in the page: only what the page reads before any guide is opened.

Every file name is used with ?h=<8 hex chars of the file's sha256>, so a changed guide is a new address and an old copy
is never served.
"""
import hashlib
import json
import re

START = "var GUIDES={"
END = "var G_SECS="
INDEX_FACTS = ("Time", "Voucher")                  # the fact rows read before a guide opens (exam time, voucher price)
SEARCH_KEYS = ("id", "title", "versions", "pbqs", "extras", "keep", "resources", "tips")


class JSError(Exception):
    pass


# ---------- a small JavaScript literal reader (data only; anything else is an error) ----------
_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", "'": "'", '"': '"', "/": "/"}
_NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_NAME = re.compile(r"[A-Za-z_$][\w$]*")


def _skip(t, i):
    while i < len(t):
        if t[i] in " \t\r\n":
            i += 1
        elif t.startswith("/*", i):
            i = t.index("*/", i) + 2
        elif t.startswith("//", i):
            i = t.index("\n", i) + 1
        else:
            break
    return i


def _string(t, i):
    q, i, out = t[i], i + 1, []
    while True:
        c = t[i]
        if c == q:
            return "".join(out), i + 1
        if c == "\n":
            raise JSError("newline inside a string at %d" % i)
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = t[i + 1]
        if n == "u":
            if t[i + 2] == "{":
                j = t.index("}", i + 2)
                cp, i = int(t[i + 3:j], 16), j + 1
            else:
                cp, i = int(t[i + 2:i + 6], 16), i + 6
                if 0xD800 <= cp < 0xDC00 and t.startswith("\\u", i):
                    lo = int(t[i + 2:i + 6], 16)
                    if 0xDC00 <= lo < 0xE000:
                        cp, i = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00), i + 6
            if 0xD800 <= cp < 0xE000:
                raise JSError("lone surrogate in a string at %d" % i)
            out.append(chr(cp))
        elif n == "x":
            out.append(chr(int(t[i + 2:i + 4], 16)))
            i += 4
        elif n == "\n":
            i += 2
        elif n == "0" and not t[i + 2].isdigit():
            out.append("\0")
            i += 2
        elif n in _ESC:
            out.append(_ESC[n])
            i += 2
        elif n.isdigit():
            raise JSError("octal escape at %d" % i)
        else:
            out.append(n)
            i += 2


def parse(t, i=0):
    """One literal starting at t[i]. Returns (value, index after it)."""
    i = _skip(t, i)
    c = t[i]
    if c == "{":
        obj, i = {}, _skip(t, i + 1)
        while t[i] != "}":
            if t[i] in "\"'":
                key, i = _string(t, i)
            else:
                m = _NAME.match(t, i) or re.compile(r"\d+").match(t, i)
                if not m:
                    raise JSError("bad key at %d: %r" % (i, t[i:i + 30]))
                key, i = m.group(0), m.end()
            i = _skip(t, i)
            if t[i] != ":":
                raise JSError("expected ':' at %d" % i)
            obj[key], i = parse(t, i + 1)
            i = _skip(t, i)
            if t[i] == ",":
                i = _skip(t, i + 1)
        return obj, i + 1
    if c == "[":
        arr, i = [], _skip(t, i + 1)
        while t[i] != "]":
            v, i = parse(t, i)
            arr.append(v)
            i = _skip(t, i)
            if t[i] == ",":
                i = _skip(t, i + 1)
        return arr, i + 1
    if c in "\"'":
        return _string(t, i)
    for word, val in (("true", True), ("false", False), ("null", None)):
        if t.startswith(word, i) and not re.match(r"[\w$]", t[i + len(word):i + len(word) + 1] or " "):
            return val, i + len(word)
    m = _NUM.match(t, i)
    if not m:
        raise JSError("not plain data at %d: %r" % (i, t[i:i + 30]))
    s = m.group(0)
    return (float(s) if re.search(r"[.eE]", s) else int(s)), m.end()


# ---------- the split ----------
def dumps(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def file_bytes(v):
    return (dumps(v) + "\n").encode("utf-8")


def sha8(b):
    return hashlib.sha256(b).hexdigest()[:8]


def slim(g, h):
    """What the page needs before a guide opens (search, Compare, Readiness, Countdown, planner, Continue card...)."""
    out = {"id": g["id"]}
    for k in ("title", "checked", "planHours", "planAll", "laneOnly", "dod", "mock"):
        if k in g:
            out[k] = g[k]
    out["quizN"] = len(g.get("quiz") or [])
    out["facts"] = [r for r in g.get("facts") or [] if r and r[0] in INDEX_FACTS]
    vers = {}
    for k, V in g["versions"].items():
        vv = {f: V[f] for f in ("label", "code", "status", "numbered") if f in V}
        vv["domains"] = [{"n": d["n"], "name": d["name"], "w": d["w"], "obj": [[o[0]] for o in d["obj"]]} for d in V["domains"]]
        vers[k] = vv
    out["versions"] = vers
    out["lz"] = h
    return out


def split(art):
    """art = the text of src/app.html. Returns (new_text, {"guides/<name>.json": bytes}, {name: guide})."""
    a, b = art.index(START), art.index(END)
    region = art[a:b]
    guides, cuts = {}, []                      # cuts: (start, end, replacement) inside `region`
    first, e = parse(region, len(START) - 1)
    if region[e] != ";":
        raise JSError("var GUIDES={...} must end with ';'")
    guides.update(first)
    cuts.append((0, e + 1, "@@INDEX@@"))
    for m in re.finditer(r'(?m)^GUIDES\["([^"]+)"\]=', region[e + 1:]):
        start = e + 1 + m.start()
        val, end = parse(region, e + 1 + m.end())
        if region[end] != ";":
            raise JSError("GUIDES[%r]={...} must end with ';'" % m.group(1))
        if m.group(1) in guides:
            raise JSError("guide %r is defined twice" % m.group(1))
        guides[m.group(1)] = val
        end += 1
        if region[end:end + 1] == "\n":
            end += 1
        cuts.append((start, end, ""))
    ids = [g["id"] for g in guides.values()]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-z0-9]+", i) for i in ids):
        raise JSError("guide ids must be unique and plain lowercase letters/digits")
    files, lines = {}, []
    for name, g in guides.items():
        fb = file_bytes(g)
        files["guides/%s.json" % g["id"]] = fb
        lines.append(dumps(name) + ":" + dumps(slim(g, sha8(fb))))
    sb = file_bytes({n: {k: g[k] for k in SEARCH_KEYS if k in g} for n, g in guides.items()})
    files["guides/_search.json"] = sb
    index_js = ("var GUIDES={\n" + ",\n".join(lines) + "\n};").replace("</", "<\\/")
    out, pos = [], 0
    for s, e2, rep in cuts:
        out.append(region[pos:s])
        out.append(index_js if rep == "@@INDEX@@" else rep)
        pos = e2
    out.append(region[pos:])
    text = art[:a] + "".join(out) + art[b:]
    lazy = 'var GUIDES_LAZY=null;'
    if text.count(lazy) != 1:
        raise JSError("src/app.html must have exactly one line: var GUIDES_LAZY=null;")
    text = text.replace(lazy, 'var GUIDES_LAZY={"search":"%s"};' % sha8(sb))
    return text, files, guides
