"""Copy only the public website files into _site/ for deployment.

Before the pipeline, GitHub Pages published the whole repo. Now only what is listed in PUBLIC goes live, so the
source, build scripts, tests and notes stay private. Every top-level file in the repo must be listed in PUBLIC or
PRIVATE: a new file fails the build until someone decides whether it should be public.

  python3 build/stage_site.py [_site]
"""
import pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "_site"

PUBLIC = {
    "index.html", "404.html", "sw.js", "manifest.webmanifest", "robots.txt", "sitemap.xml", "CNAME", "LICENSE",
    "og-image.jpg", "apple-touch-icon.png", "favicon.ico", "favicon.png", "favicon-96.png",
    "icon-192.png", "icon-512.png", "icon-maskable-512.png",
    ".well-known", "fonts", "vendor", "qbank",
}
PRIVATE = {
    ".github", ".gitignore", ".claude", "CLAUDE.md", "README.md", "_config.yml", "src", "build", "tests",
}


def tracked_top_level():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {line.split("/")[0] for line in out.splitlines() if line}


def main():
    unknown = tracked_top_level() - PUBLIC - PRIVATE
    if unknown:
        sys.exit("FAIL: decide if these are public (add to PUBLIC) or private (add to PRIVATE) in build/stage_site.py: "
                 + ", ".join(sorted(unknown)))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for name in sorted(PUBLIC):
        src = ROOT / name
        if not src.exists():
            sys.exit("FAIL: public file missing: " + name)
        if src.is_dir():
            shutil.copytree(src, OUT / name)
        else:
            shutil.copy2(src, OUT / name)
    # everything the service worker caches on install must be in the deployed site, or offline install fails
    sw = (OUT / "sw.js").read_text()
    shell = re.findall(r'"([^"]+)"', re.search(r"var\s+SHELL\s*=\s*\[(.*?)\]", sw, re.S).group(1))
    missing = [f for f in shell if not (OUT / f).exists()]
    if missing:
        sys.exit("FAIL: sw.js SHELL lists files that are not deployed: " + ", ".join(missing))
    n = sum(1 for p in OUT.rglob("*") if p.is_file())
    print("staged %d files in %s" % (n, OUT))


if __name__ == "__main__":
    main()
