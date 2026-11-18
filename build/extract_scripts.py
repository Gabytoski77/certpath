"""Copy each inline <script> of index.html into build/out/inline-N.js so code scanners (ESLint, Semgrep)
can read the app's JavaScript. The copies are for checking only and are never committed (build/out/ is in .gitignore)."""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# optional folder argument (CI passes a temp folder; Semgrep skips anything under build/ by default)
OUT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "build" / "out"
OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("inline-*.js"):
    old.unlink()
html = (ROOT / "index.html").read_text(encoding="utf8")
scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
for i, s in enumerate(scripts, 1):
    (OUT / ("inline-%d.js" % i)).write_text(s, encoding="utf8")
print("wrote %d inline scripts to %s" % (len(scripts), OUT))
