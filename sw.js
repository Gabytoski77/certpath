/* MyNextCert service worker: makes the site installable and usable offline.
   Change VERSION whenever you upload a new index.html so phones pick it up quickly. */
var VERSION = "certpath-v101";
/* everything the app needs lives on this site (no outside servers). The page, icons and fonts are cached on install;
   three.js, Lenis and the 3D map file (world.js) are saved the first time they're used. Lite mode never loads them,
   so it never downloads them either. */
var SHELL = [ "manifest.webmanifest", "icon-192.png", "icon-512.png",
             "icon-maskable-512.png", "apple-touch-icon.png", "favicon.png", "favicon-96.png",
             "fonts/fonts.css", "fonts/inter-tight.woff2", "fonts/geist.woff2",
             "fonts/cp-mono-regular.woff2", "fonts/cp-mono-medium.woff2"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) {
    return Promise.all([c.addAll(SHELL), fetch("index.html", { cache: "no-store" }).then(function (r) { return c.put("index.html", r); })]);
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    var old = keys.filter(function (k) { return k !== VERSION; });
    /* practice exam question banks (qbank/), the practice-exam PBQ engine (vendor/pbq-engine.js, v2.84: saved the first time a bank that needs it opens, never in SHELL), the still globe pictures (img/globe/) and the guides (guides/, v2.83) are
       saved the first time they're used; carry them into the new cache so they still work offline right after an update
       (v2.48, v2.58). Banks and pictures refresh in the background when online. A guide's address ends in ?h=<hash of the
       file>, so the test below looks at the path only (the ?h= part is ignored), and the guide is carried over under its
       full address. If two old caches hold the same guide under different hashes, only one is kept. */
    var carried = {};
    return caches.open(VERSION).then(function (cur) {
      return Promise.all(old.map(function (k) {
        return caches.open(k).then(function (c) {
          return c.keys().then(function (reqs) {
            return Promise.all(reqs.filter(function (r) { return /\/(qbank\/[a-z0-9-]+\.json|vendor\/pbq-engine\.js|img\/globe\/[a-z0-9-]+\.(webp|json)|guides\/[a-z0-9_]+\.json)$/.test(new URL(r.url).pathname); }).map(function (r) {
              var path = new URL(r.url).pathname;
              if (/\/guides\//.test(path)) {
                if (carried[path]) return null;
                carried[path] = 1;
              }
              return cur.match(r).then(function (have) { return have ? null : c.match(r).then(function (res) { return res ? cur.put(r, res) : null; }); });
            }));
          });
        });
      }));
    }).catch(function () {}).then(function () {
      return Promise.all(old.map(function (k) { return caches.delete(k); }));
    });
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);

  /* the page itself. The app's home page opens from the saved copy and checks for an update in the background (v2.86);
     any other page (robots.txt, 404.html, a wrong link) comes from the network, with the saved app as the offline fallback */
  if (req.mode === "navigate") {
    /* "no-cache" still asks the server every time ("has the page changed?"). If nothing changed, the server answers
       "no" with an empty reply and the saved copy is used, so the ~544 KB page isn't downloaded again (v2.80).
       The install step above keeps "no-store" on purpose. */
    /* redirect: "manual" hands a moved page (e.g. a new domain) straight back to the browser to follow,
       instead of failing and leaving people stuck on an old saved copy (v2.43) */
    /* the app's own address ("/" or "/index.html"), as opposed to another file opened in the tab (robots.txt, 404.html...) */
    var home = url.pathname === new URL("./", location.href).pathname || url.pathname === new URL("index.html", location.href).pathname;
    var fromNet = function (res) {
      if (res.type === "opaqueredirect") return res;
      /* an error page never replaces the saved app. A wrong address (404 anywhere but the home page) shows the
         site's own "page not found" page (v2.46); a server error, or a 404 for the home page itself, shows the saved app */
      if (!res.ok) {
        if (res.status === 404 && !home) return res;
        return caches.match("index.html").then(function (m) { return m || res; });
      }
      /* only the app itself is saved as the offline copy (v2.46: opening /robots.txt or /404.html used to replace it) */
      if (home && /text\/html/i.test(res.headers.get("content-type") || "")) {
        var copy = res.clone(); caches.open(VERSION).then(function (c) { c.put("index.html", copy); });
      }
      return res;
    };
    var net = fetch(req.url, { cache: "no-cache", credentials: "same-origin", redirect: "manual" });
    if (home) {
      /* v2.86: open from the saved copy at once, so a slow network never holds up the first screen. The server is
         still asked in the background (pageRefresh); when the page changed, the new one is saved and the open windows
         show "New version ready - Refresh". Ignoring that is fine: the next open uses the new saved copy.
         With no saved copy yet (first visit, cleared data) the page comes from the network as before. */
      var saved = caches.match("index.html");
      e.respondWith(saved.then(function (hit) { return hit || net.then(fromNet).catch(function () { return caches.match("index.html"); }); }));
      e.waitUntil(saved.then(function (hit) { if (hit) return net.then(pageRefresh); }).catch(function () {}));
      return;
    }
    e.respondWith(net.then(fromNet).catch(function () { return caches.match("index.html"); }));
    return;
  }

  /* own files (page, libraries, fonts): serve from cache, refresh in the background */
  if (url.origin === location.origin) {
    /* a guide file's address carries its hash (guides/<id>.json?h=...), so what's saved under it never goes stale:
       use the saved copy without asking the network, and when a new hash is saved, delete the older copies of that
       same guide so they don't pile up with every release (v2.83) */
    var guide = /\/guides\/[a-z0-9_]+\.json$/.test(url.pathname) && url.search.indexOf("h=") >= 0;
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(req).then(function (hit) {
        if (hit && guide) return hit;
        var net = fetch(req).then(function (res) {
          if (res && res.ok) {
            c.put(req, res.clone());
            if (guide) c.keys().then(function (ks) {
              ks.forEach(function (k) { var u = new URL(k.url); if (u.pathname === url.pathname && u.search !== url.search) c.delete(k); });
            });
          }
          return res;
        }).catch(function () { return hit; });
        return hit || net;
      });
    }));
  }
});

/* v2.86: the background check behind an instant open. The saved page is compared with the server's; when they differ,
   the new one replaces it and every open window is told (the page then shows "New version ready - Refresh"). */
function pageRefresh(res) {
  /* the site moved (a redirect): forget the saved copy, so the next open follows the move instead of staying on it (v2.43) */
  if (res.type === "opaqueredirect") return caches.open(VERSION).then(function (c) { return c.delete("index.html"); }).then(tellPages);
  if (!res.ok || !/text\/html/i.test(res.headers.get("content-type") || "")) return null;
  return caches.match("index.html").then(function (old) {
    if (!old) return caches.open(VERSION).then(function (c) { return c.put("index.html", res); });
    var tag = res.headers.get("etag");
    if (tag && tag === old.headers.get("etag")) return null;   /* same file: nothing to do */
    return Promise.all([old.text(), res.clone().text()]).then(function (t) {
      if (t[0] === t[1]) return null;
      return caches.open(VERSION).then(function (c) { return c.put("index.html", res); }).then(tellPages);
    });
  });
}
/* the window that is opening may not be listed yet, so look again a few times before giving up */
function tellPages() {
  var tries = 0;
  function again() {
    return self.clients.matchAll({ type: "window" }).then(function (list) {
      if (!list.length && ++tries < 10) return new Promise(function (r) { setTimeout(r, 500); }).then(again);
      list.forEach(function (c) { c.postMessage({ type: "update-ready" }); });
      return null;
    });
  }
  return again();
}
