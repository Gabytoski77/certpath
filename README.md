# CG Cert Path

Certifications, career paths and CG COOL funding for Coast Guard IT, with full study guides
(objectives, study plan, resources, quiz, PBQs, roadmap) for CompTIA A+, Network+, Security+, Cloud+, CySA+, PenTest+, SecurityX, and ISC2 CC, SSCP, CCSP and CISSP.

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
