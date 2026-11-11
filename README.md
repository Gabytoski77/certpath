# CG Cert Path

Certifications, career paths, funding (Tuition Assistance and CG COOL), colleges and SkillBridge for Coast Guard IT, with full study guides
(objectives, study plan, resources, quiz, PBQs, roadmap) for CompTIA A+, Network+, Security+, Cloud+, CySA+, PenTest+, Project+ and SecurityX, ISC2 CC, SSCP, CCSP and CISSP, Cisco CCST Networking, CCST Cybersecurity, CCNA Cybersecurity, CCNA and CCNP Security, TryHackMe SAL1 and PT1, and LPI Linux Essentials and LPIC-1.

**Not an official U.S. Coast Guard site.** Public information only. Vendor names are trademarks of their owners.
Quiz and PBQ questions are original.

## Files
| File | What it does |
|---|---|
| `index.html` | The whole site |
| `manifest.webmanifest` | Lets phones install it as an app |
| `sw.js` | Offline support and fast loading |
| `icon-*.png`, `apple-touch-icon.png`, `favicon.png` | App and browser icons |

## Updating
1. Replace `index.html` with the new version (Add file → Upload files).
2. In `sw.js`, bump `VERSION` (for example `certpath-v1` → `certpath-v2`) so installed copies refresh.

Everything the app needs is served from this repo: no outside servers. Libraries are in `vendor/` (three.js, Lenis, ECharts world map) and fonts in `fonts/` (Inter Tight, Geist, IBM Plex Mono), each with its license. The page locks itself down with a Content Security Policy.

## Disclaimer

Not an official U.S. Coast Guard or DoD site. Not affiliated with or endorsed by the U.S. Coast Guard, CompTIA, ISC2, Cisco, TryHackMe, LPI, AWS, Microsoft, WGU or any college listed. All names are trademarks of their owners. Quiz questions and PBQs are original; no real exam content is used.

## Your data

Your data stays on your device. CertPath has no accounts, cookies or analytics; your progress is saved in your browser and you can clear it anytime. The site is hosted on GitHub Pages, which keeps standard server logs.

## License

Copyright (c) 2026 Gabriel Rodriguez (Gabytoski77). All rights reserved. See LICENSE. Third-party components in `vendor/` and `fonts/` keep their own licenses.
