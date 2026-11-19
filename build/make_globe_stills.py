"""Render the still globe pictures used by Light mode (v2.58).

Light mode shows a picture of the real 3D globe instead of drawing one. This script opens the built site in
the full 3D version, turns the globe to face each vendor (arrow keys, so the mouse never tilts it), hides
everything but the globe canvas and saves:

  img/globe/<vendor-id>-1000.webp, -1300.webp, -1600.webp   one picture per vendor in three sizes, globe centred, see-through
                                                around it (the page shows the smaller one unless the screen needs more)
  img/globe/views.json   for each picture: where the globe sits and how big it is compared with the home screen's
                         layout globe (c), and where each badge tap target is, in globe radii (labels)

Run it after changing how the globe or the vendors look, then commit the results:
  python3 build/build_site.py && python3 build/make_globe_stills.py
Needs Playwright with Chrome (CHROME_PATH, default /usr/bin/google-chrome) and Pillow. It renders with
software WebGL, so it takes a few minutes.
"""
import json
import math
import os
import subprocess
import sys
import time
from io import BytesIO

from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img", "globe")
PORT = 8791
SIZE = 1800          # master size in pixels (square); the saved pictures are scaled down from it
SIZES = (1000, 1300, 1600) # saved picture sizes (1300 since v2.66: work laptops at 125–150% scaling need ~1100–1300 px)
SPAN = 1.5           # the picture covers 1.5 globe radii each side of the centre
FADE = (1.30, 1.48)  # stars and glow fade out between these radii, so the square edge never shows
QUALITY = 70         # WebP quality: about 75 KB per 1000 px picture

HIDE_ALL = """
*,*::before,*::after{visibility:hidden!important;background:transparent!important;box-shadow:none!important;
  animation:none!important;transition:none!important}
#globe{visibility:visible!important}
html,body{background:transparent!important}
"""


def wait_settled(page, ms=2600):
    page.wait_for_timeout(ms)


def main():
    os.makedirs(OUT, exist_ok=True)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "-d", ROOT],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    views = {"v": 1, "span": SPAN, "sizes": list(SIZES), "views": {}}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"),
                                   args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            ctx = b.new_context(viewport={"width": 2400, "height": 1500}, device_scale_factor=1.6)
            p = ctx.new_page()
            p.add_init_script("localStorage.setItem('cgcp.lite','off');localStorage.setItem('cgcp.gfx','high');")
            p.goto(f"http://localhost:{PORT}/index.html", wait_until="load")
            p.wait_for_timeout(9000)   # launch animation and map fade-in
            n = p.evaluate("document.querySelectorAll('#ro-dots .crest').length")
            assert n == len(VENDOR_IDS), f"{n} crests on the page but {len(VENDOR_IDS)} vendors in src/app.html"
            for target in range(n):
                cur = p.evaluate("Array.from(document.querySelectorAll('#ro-dots .crest')).findIndex(function(b){return b.getAttribute('aria-current')==='true'})")
                steps = (target - cur) % n
                if steps == 0:   # face it explicitly, so the globe stops auto-rotating
                    p.keyboard.press("ArrowRight"); p.wait_for_timeout(150); p.keyboard.press("ArrowLeft")
                else:
                    for _ in range(steps):
                        p.keyboard.press("ArrowRight"); p.wait_for_timeout(120)
                wait_settled(p)
                info = p.evaluate("""(function(){
                  var app=document.getElementById('app'), cs=getComputedStyle(app), ar=app.getBoundingClientRect();
                  var gx=parseFloat(cs.getPropertyValue('--gx')), gy=parseFloat(cs.getPropertyValue('--gy')), gr=parseFloat(cs.getPropertyValue('--gr'));
                  var labs=Array.from(document.querySelectorAll('#labels .bl')).map(function(el){
                    var m=/translate\\(([-\\d.]+)px,\\s*([-\\d.]+)px\\)/.exec(el.style.transform||'')||[0,0,0];
                    return {x:+m[1],y:+m[2],o:parseFloat(el.style.opacity||'0'),off:el.classList.contains('off'),
                            front:el.classList.contains('front'),mt:parseFloat(el.style.getPropertyValue('--mt'))||0};});
                  var slug=document.querySelector('#ro-name').textContent;
                  return {gx:gx,gy:gy,gr:gr,ax:ar.left,ay:ar.top,labs:labs,name:slug,dpr:devicePixelRatio};})()""")
                style = p.add_style_tag(content=HIDE_ALL)
                p.wait_for_timeout(400)
                # capture the whole screen, then find the globe disk itself: shrink the opaque area so badges,
                # beams and stars drop out, take what's left, and grow it back. The 3D globe isn't always at
                # the layout centre (--gx/--gy), so measuring it is more reliable than assuming.
                png = p.screenshot(omit_background=True)
                p.evaluate("(el)=>el.remove()", style)
                img = Image.open(BytesIO(png)).convert("RGBA")
                dpr = info["dpr"]
                k = 8
                small = img.getchannel("A").resize((img.width // k, img.height // k), Image.BOX).point(lambda v: 255 if v > 140 else 0)
                er = int(info["gr"] * dpr / k * .35) | 1
                core = small.filter(ImageFilter.MinFilter(min(er, 61)))
                bb = core.getbbox()
                assert bb, "globe not found in the screenshot"
                grow = min(er, 61) // 2
                x0, y0, x1, y1 = [(v + (grow if i > 1 else -grow)) * k for i, v in enumerate(bb)]
                gcx_px, gcy_px = (x0 + x1) / 2, (y0 + y1) / 2
                r_img = ((x1 - x0) + (y1 - y0)) / 4
                # refine the radius on the full-size picture along 72 rays from the found centre
                a = img.getchannel("A"); radii = []
                for q in range(72):
                    ang = 2 * math.pi * q / 72; edge = None
                    for rr in range(int(r_img * .8), int(r_img * 1.2)):
                        x = int(gcx_px + rr * math.cos(ang)); y = int(gcy_px + rr * math.sin(ang))
                        if not (0 <= x < img.width and 0 <= y < img.height) or a.getpixel((x, y)) < 110:
                            edge = rr; break
                    if edge: radii.append(edge)
                radii.sort(); r_img = radii[len(radii) // 4]   # lower quartile: rays through badges and beams run long
                box = (gcx_px - r_img * SPAN, gcy_px - r_img * SPAN, gcx_px + r_img * SPAN, gcy_px + r_img * SPAN)
                img = img.crop(tuple(int(round(v)) for v in box)).resize((SIZE, SIZE), Image.LANCZOS)
                mask = Image.new("L", (SIZE, SIZE), 0)
                mp = mask.load(); c = SIZE / 2; rpx = SIZE / (2 * SPAN)
                for yy in range(SIZE):
                    for xx in range(SIZE):
                        d = math.hypot(xx + .5 - c, yy + .5 - c) / rpx
                        t = 1.0 if d <= FADE[0] else 0.0 if d >= FADE[1] else 1 - (d - FADE[0]) / (FADE[1] - FADE[0])
                        mp[xx, yy] = int(255 * t * t * (3 - 2 * t))
                img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", img.size, 0), mask))
                # sphere centre and radius in CSS px, relative to the layout centre the app uses
                scx, scy, Rr = gcx_px / dpr - info["ax"], gcy_px / dpr - info["ay"], r_img / dpr
                centre = [round((scx - info["gx"]) / info["gr"], 4), round((scy - info["gy"]) / info["gr"], 4), round(Rr / info["gr"], 4)]
                vid = VENDOR_IDS[target]
                if os.environ.get("MASTER_DIR"):
                    img.save(os.path.join(os.environ["MASTER_DIR"], vid + ".png"))
                for sz in SIZES:
                    img.resize((sz, sz), Image.LANCZOS).save(os.path.join(OUT, f"{vid}-{sz}.webp"), "WEBP", quality=QUALITY, alpha_quality=70, method=6)
                labs = []
                for j, L in enumerate(info["labs"]):
                    if L["off"] or L["o"] < .35:
                        continue
                    labs.append({"i": j, "x": round((L["x"] - scx) / Rr, 4), "y": round((L["y"] - scy) / Rr, 4),
                                 "mt": round(L["mt"] / Rr, 4), "front": L["front"]})
                views["views"][vid] = {"c": centre, "labels": labs}
                kb = " + ".join(f"{os.path.getsize(os.path.join(OUT, f'{vid}-{sz}.webp')) // 1024} KB" for sz in SIZES)
                print(f"{vid:9} {kb}  centre/radius vs layout {centre}  labels {len(labs)}")
            b.close()
    finally:
        srv.terminate()
    with open(os.path.join(OUT, "views.json"), "w") as f:
        json.dump(views, f, separators=(",", ":"))


def vendor_ids():
    """Vendor ids in VENDORS order, read from src/app.html (the crest order on the home screen)."""
    import re
    s = open(os.path.join(ROOT, "src", "app.html"), encoding="utf-8").read()
    i = s.index("var VENDORS = [")
    j = s.index("\n];", i)
    return re.findall(r'^\s*\{\s*id:"([a-z0-9-]+)"', s[i:j], re.M) or re.findall(r'\{id:"([a-z0-9-]+)"', s[i:j])


VENDOR_IDS = vendor_ids()

if __name__ == "__main__":
    print("vendors:", VENDOR_IDS)
    main()
