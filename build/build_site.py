"""Build the live site (index.html) from the source files in src/.

  src/app.html        the app itself, same file as the claude.ai preview artifact (loads libraries/fonts from CDNs)
  src/site-head.html  the live site's own <head> start: title, SEO/share tags, icons, manifest (everything before
                      <meta name="referrer">)
  src/site-tail.html  the service worker registration + </body></html>

The live site serves libraries and fonts itself (vendor/, fonts/) and locks the page down with a Content Security
Policy whose script hashes are computed here, so they always match the inline scripts that ship.

Usage:
  python3 build/build_site.py            # writes index.html and guides/*.json
  python3 build/build_site.py --check    # builds in memory, fails if index.html or guides/*.json differ (used by CI)

The guides are split out of src/app.html by build/split_guides.py: each one becomes guides/<id>.json (fetched when the
guide opens) and only a small index of them stays inline in index.html.
"""
import base64, hashlib, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import split_guides

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "index.html"
GUIDES_DIR = ROOT / "guides"


def swap(s, a, b, n=1):
    assert s.count(a) == n, ("expected %d of" % n, a[:80], s.count(a))
    return s.replace(a, b)


def build():
    art = (SRC / "app.html").read_text(encoding="utf8")
    art, files, _ = split_guides.split(art)
    pre = (SRC / "site-head.html").read_text(encoding="utf8")
    reg = (SRC / "site-tail.html").read_text(encoding="utf8")
    body = art[art.index('<meta name="referrer"'):]
    # The app's own "</body></html>" is cut off, so site-tail.html (update script + "</body></html>") closes the page.
    end = body.rindex("</body>")
    assert body[end:].split() == ["</body></html>"], "src/app.html should end with </body></html>"
    body = body[:end]
    # The app's styles and scripts belong to <head>; the page itself starts at the splash screen.
    body = swap(body, '\n<div id="splash"', '\n</head>\n<body>\n<div id="splash"')

    # fonts: our own files instead of Google Fonts
    body = swap(body, '<link rel="preconnect" href="https://fonts.googleapis.com">\n', '')
    body = swap(body, '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n', '')
    body = swap(body,
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=Geist:wght@300..700&family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500&display=swap">',
        '<link rel="preload" href="fonts/inter-tight.woff" as="font" type="font/woff" crossorigin>\n'
        '<link rel="preload" href="fonts/geist.woff" as="font" type="font/woff" crossorigin>\n'
        '<link rel="stylesheet" href="fonts/fonts.css">')
    # libraries: our own copies (the page writes these tags itself, only when the 3D globe / smooth scrolling will run)
    body = swap(body, '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js" crossorigin="anonymous" referrerpolicy="no-referrer"><\\/script>',
                '<script src="vendor/three.min.js"><\\/script>')
    body = swap(body, '<script src="https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js" crossorigin="anonymous" referrerpolicy="no-referrer"><\\/script>',
                '<script src="vendor/lenis.min.js"><\\/script>')
    body = swap(body, 's.src="https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/js/world.js";', 's.src="vendor/world.js";')

    page = pre + body.rstrip() + "\n" + reg
    for host in ("cdnjs.cloudflare.com", "cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "unpkg.com"):
        assert host not in page, "outside host left in the page: " + host
    assert "goatcounter" not in page.lower() and "zgo.at" not in page

    # Content Security Policy: this site's own files only; inline scripts allowed by exact hash only
    assert "Content-Security-Policy" not in page
    inline = re.findall(r'<script>(.*?)</script>', page, flags=re.S)
    hashes = " ".join("'sha256-%s'" % base64.b64encode(hashlib.sha256(x.encode("utf8")).digest()).decode() for x in inline)
    csp = ("default-src 'self'; script-src 'self' %s; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
           "font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; "
           "base-uri 'self'; form-action 'none'; frame-src 'none'; upgrade-insecure-requests") % hashes
    page = swap(page, '<meta charset="utf-8">\n', '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="%s">\n' % csp)
    return page, len(inline), files


def main():
    page, n, files = build()
    if "--check" in sys.argv:
        have = {"guides/" + f.name for f in GUIDES_DIR.glob("*")} if GUIDES_DIR.is_dir() else set()
        bad = sorted(set(files) ^ have) + sorted(k for k, v in files.items() if k in have and (ROOT / k).read_bytes() != v)
        if bad:
            sys.exit("FAIL: guides/ does not match a fresh build of src/ (%s). Run: python3 build/build_site.py" % ", ".join(bad[:8]))
        cur = OUT.read_text(encoding="utf8") if OUT.exists() else ""
        if cur != page:
            import difflib
            diff = list(difflib.unified_diff(cur.splitlines(), page.splitlines(), "index.html (committed)", "index.html (built from src/)", n=1, lineterm=""))
            print("\n".join(d[:300] for d in diff[:60]))
            sys.exit("FAIL: index.html does not match a fresh build of src/. Run: python3 build/build_site.py")
        print("ok: index.html and %d guide files match a fresh build of src/ (%d inline scripts hashed)" % (len(files), n))
        return
    GUIDES_DIR.mkdir(exist_ok=True)
    for old in GUIDES_DIR.glob("*"):
        if "guides/" + old.name not in files:
            old.unlink()
    for k, v in files.items():
        (ROOT / k).write_bytes(v)
    OUT.write_text(page, encoding="utf8")
    print("built", OUT.name, len(page), "bytes;", n, "inline scripts hashed")


if __name__ == "__main__":
    main()
