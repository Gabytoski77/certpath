# MyNextCert

**Live at [mynextcert.com](https://mynextcert.com/).**


Certifications, career paths, funding (Tuition Assistance and CG COOL), colleges and SkillBridge for Coast Guard IT, with full study guides
(objectives, study plan, resources, quiz, PBQs, roadmap) for CompTIA A+, Network+, Security+, Server+, Cloud+, Linux+, CySA+, PenTest+, SecAI+, Project+ and SecurityX, ISC2 CC, SSCP, CGRC, CCSP and CISSP, Cisco CCST IT Support, CCST Networking, CCST Cybersecurity, CCNA Cybersecurity, CCNA, CCNP Enterprise, CCNP Security and CCNP Cybersecurity, TryHackMe SEC1, SAL1, SAL2 and PT1, LPI Linux Essentials, Security Essentials, LPIC-1 and LPIC-2, AWS Cloud Practitioner, Solutions Architect Associate and Security Specialty, and Microsoft Azure Fundamentals, Azure Administrator and Cloud and AI Security Engineer (SC-500).

**Not an official U.S. Coast Guard site.** Public information only. Vendor names are trademarks of their owners.
Quiz and PBQ questions are original.

## Files
| File | What it does |
|---|---|
| `index.html` | The whole site |
| `manifest.webmanifest` | Lets phones install it as an app |
| `sw.js` | Offline support and fast loading |
| `icon-*.png`, `apple-touch-icon.png`, `favicon.png` | App and browser icons |
| `src/` | The app source (`index.html` is built from it) |
| `build/` | Build, 404 and deploy scripts |
| `tests/` | Browser tests and check configs |

## Updating

Nothing goes live unless every check passes.

1. Make a branch, edit `src/app.html` (never `index.html`; it is generated), then `python3 build/build_site.py`.
2. If the page changed, bump the label in `src/app.html` and `VERSION` in `sw.js`, and rebuild.
3. `bash build/check_all.sh` runs every check locally. Push the branch and open a pull request.
4. CI (`.github/workflows/ci.yml`) runs: build-matches-source, site checks, secret scan (gitleaks), code scan (Semgrep),
   HTML/JS lint, actionlint, Playwright browser tests (desktop, iPhone, 320 px, 200% zoom, reduced motion, offline,
   CSP, practice exams), axe accessibility and Lighthouse.
5. Merge when green. `deploy.yml` re-checks the build and then publishes only the public files
   (`build/stage_site.py`). `post-deploy.yml` checks the live site; `weekly.yml` runs the OWASP ZAP baseline scan.
   `weekly.yml` checks links, HTTPS certificates and library versions every Monday.

See `CLAUDE.md` for the full rules.

Everything the app needs to run is served from this repo; it loads nothing from outside servers. Libraries are in `vendor/` (three.js, Lenis, ECharts world map) and fonts in `fonts/` (Inter Tight, Geist, and CP Mono, a trimmed copy of IBM Plex Mono), each with its license. The page locks itself down with a Content Security Policy.

## Disclaimer

Not an official U.S. Coast Guard or DoD site. Not affiliated with or endorsed by the U.S. Coast Guard, CompTIA, ISC2, Cisco, TryHackMe, LPI, AWS, Microsoft, WGU or any college listed. All names are trademarks of their owners. Quiz questions and PBQs are original; no real exam content is used.

## Your data

Your data stays on your device. MyNextCert has no accounts, no analytics and no cookies; your progress is saved in your browser and you can clear it anytime. The site is hosted on GitHub Pages, which keeps standard server logs.

## License

Copyright (c) 2026 Gabriel Rodriguez (Gabytoski77). All rights reserved. See LICENSE. Third-party components in `vendor/` and `fonts/` keep their own licenses.
