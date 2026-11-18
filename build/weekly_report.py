"""Weekly health report for MyNextCert (run by .github/workflows/weekly.yml, or by hand).

1. HTTPS certificates:
   - the one visitors see (Cloudflare's edge, renews itself),
   - GitHub Pages' own certificate behind Cloudflare (Let's Encrypt, 90 days). With the orange cloud on, GitHub
     can't renew it by itself: about 3 weeks before it expires, switch the DNS records to grey (DNS only) for
     ~30 minutes so GitHub renews it, then back to orange. If it expires, Cloudflare Full (strict) shows error 526.
   Fails when either certificate has fewer than WARN_DAYS left.
2. Bundled libraries in vendor/: compares the pinned versions with the newest published ones (report only;
   upgrading three.js from r128 is a project, not a weekly chore).

Writes a Markdown summary to $GITHUB_STEP_SUMMARY when it runs in GitHub Actions.
"""
import datetime as dt, json, os, socket, ssl, sys, urllib.request

HOST = "mynextcert.com"
GITHUB_PAGES_IP = "185.199.108.153"
WARN_DAYS = 21
LIBS = {  # npm package -> (version shipped in vendor/, what it is)
    "three": ("0.128.0", "3D globe (three.js r128)"),
    "lenis": ("1.1.13", "smooth scrolling"),
    "echarts": ("4.9.0", "world map outline (only map/js/world.js is used)"),
}

lines, failed = [], False


def cert_days(connect_host):
    ctx = ssl.create_default_context()
    if connect_host != HOST:
        # GitHub's origin: check the certificate it serves for our name, without trusting Cloudflare in between
        ctx.check_hostname = True
    with socket.create_connection((connect_host, 443), timeout=20) as s:
        with ctx.wrap_socket(s, server_hostname=HOST) as t:
            c = t.getpeercert()
    end = dt.datetime.strptime(c["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
    issuer = dict(x[0] for x in c["issuer"]).get("organizationName", "?")
    return (end - dt.datetime.now(dt.timezone.utc)).days, end.date().isoformat(), issuer


def main():
    global failed
    lines.append("## HTTPS certificates")
    for label, target in (("Cloudflare edge (what visitors see)", HOST), ("GitHub Pages origin (behind Cloudflare)", GITHUB_PAGES_IP)):
        try:
            days, end, issuer = cert_days(target)
            flag = "OK" if days >= WARN_DAYS else "RENEW SOON"
            if days < WARN_DAYS:
                failed = True
            lines.append("- %s: **%d days left** (expires %s, issuer %s) %s" % (label, days, end, issuer, flag))
            if target == GITHUB_PAGES_IP and days < WARN_DAYS:
                lines.append("  - Fix: Cloudflare DNS: set the 4 A records and the www CNAME to grey (DNS only), wait ~30 min until "
                             "GitHub Settings -> Pages shows the certificate is ready, then set them back to orange.")
        except Exception as e:  # noqa: BLE001
            failed = True
            lines.append("- %s: could not check (%s)" % (label, e))

    lines.append("\n## Bundled libraries (report only)")
    for pkg, (have, what) in LIBS.items():
        try:
            with urllib.request.urlopen("https://registry.npmjs.org/%s/latest" % pkg, timeout=20) as r:
                latest = json.load(r)["version"]
            note = "up to date" if latest == have else "newer version %s available" % latest
        except Exception as e:  # noqa: BLE001
            note = "could not check (%s)" % e
        lines.append("- %s %s (%s): %s" % (pkg, have, what, note))

    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
