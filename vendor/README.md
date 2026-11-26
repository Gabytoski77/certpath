# Third-party files

Served from this site so the app works on networks that block outside servers, and so the page can lock itself down with a Content Security Policy.

| File | Project | Version | License |
|---|---|---|---|
| three.min.js | three.js (github.com/mrdoob/three.js) | r128 | MIT, see LICENSE-three.txt |
| lenis.min.js | Lenis (github.com/darkroomengineering/lenis) | 1.1.13 | MIT, see LICENSE-lenis.txt |
| world.js | Apache ECharts world map (github.com/apache/echarts) | 4.9.0 | Apache-2.0, see LICENSE-echarts.txt and NOTICE-echarts.txt |

Fonts are in ../fonts (SIL Open Font License 1.1): Inter Tight and Geist (both trimmed to the characters used), and CP Mono, a trimmed copy of IBM Plex Mono renamed because its license reserves the name "Plex" for unmodified copies.

Our own code, not third-party: `pbq-engine.js` is the practice-exam engine for the logsel / rules / term / diagram PBQ types (MIT-style, same as the rest of the site's code). It is not in the service worker's install list; the page loads it only when a question bank that uses those types opens, and the service worker saves it the first time.
