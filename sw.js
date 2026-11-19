/* MyNextCert service worker: makes the site installable and usable offline.
   Change VERSION whenever you upload a new index.html so phones pick it up quickly. */
var VERSION = "certpath-v80";
/* everything the app needs lives on this site (no outside servers). The page, map and fonts are cached on install;
   three.js and Lenis are saved the first time they're used (Lite mode never loads them). */
var SHELL = [ "manifest.webmanifest", "icon-192.png", "icon-512.png",
             "icon-maskable-512.png", "apple-touch-icon.png", "favicon.png", "favicon-96.png",
             "vendor/world.js",
             "fonts/fonts.css", "fonts/inter-tight.woff", "fonts/geist.woff",
             "fonts/cp-mono-regular.woff", "fonts/cp-mono-medium.woff"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) {
    return Promise.all([c.addAll(SHELL), fetch("index.html", { cache: "no-store" }).then(function (r) { return c.put("index.html", r); })]);
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    var old = keys.filter(function (k) { return k !== VERSION; });
    /* practice exam question banks (qbank/) and the still globe pictures (img/globe/) are saved the first time
       they're used; carry them into the new cache so they still work offline right after an update (v2.48, v2.58).
       They refresh in the background when online. */
    return caches.open(VERSION).then(function (cur) {
      return Promise.all(old.map(function (k) {
        return caches.open(k).then(function (c) {
          return c.keys().then(function (reqs) {
            return Promise.all(reqs.filter(function (r) { return /\/(qbank\/[a-z0-9-]+\.json|img\/globe\/[a-z0-9-]+\.(webp|json))$/.test(new URL(r.url).pathname); }).map(function (r) {
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

  /* the page itself: network first so updates show right away, cache when offline */
  if (req.mode === "navigate") {
    /* "no-store" skips the browser's saved copy, so an update shows up the moment it's live */
    /* redirect: "manual" hands a moved page (e.g. a new domain) straight back to the browser to follow,
       instead of failing and leaving people stuck on an old saved copy (v2.43) */
    /* the app's own address ("/" or "/index.html"), as opposed to another file opened in the tab (robots.txt, 404.html...) */
    var home = url.pathname === new URL("./", location.href).pathname || url.pathname === new URL("index.html", location.href).pathname;
    e.respondWith(fetch(req.url, { cache: "no-store", credentials: "same-origin", redirect: "manual" }).then(function (res) {
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
    }).catch(function () { return caches.match("index.html"); }));
    return;
  }

  /* own files (page, libraries, fonts): serve from cache, refresh in the background */
  if (url.origin === location.origin) {
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(req).then(function (hit) {
        var net = fetch(req).then(function (res) {
          if (res && res.ok) c.put(req, res.clone());
          return res;
        }).catch(function () { return hit; });
        return hit || net;
      });
    }));
  }
});
