/* CG Cert Path service worker: makes the site installable and usable offline.
   Change VERSION whenever you upload a new index.html so phones pick it up quickly. */
var VERSION = "certpath-v51";
/* everything the app needs lives on this site (no outside servers), so it is all cached on install */
var SHELL = [ "manifest.webmanifest", "icon-192.png", "icon-512.png",
             "icon-maskable-512.png", "apple-touch-icon.png", "favicon.png",
             "vendor/three.min.js", "vendor/lenis.min.js", "vendor/world.js",
             "fonts/fonts.css", "fonts/inter-tight.woff", "fonts/geist.woff",
             "fonts/IBMPlexMono-Regular.ttf", "fonts/IBMPlexMono-Medium.ttf"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) {
    return Promise.all([c.addAll(SHELL), fetch("index.html", { cache: "no-store" }).then(function (r) { return c.put("index.html", r); })]);
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);

  /* the page itself: network first so updates show right away, cache when offline */
  if (req.mode === "navigate") {
    /* "no-store" skips the browser's saved copy, so an update shows up the moment it's live */
    e.respondWith(fetch(req.url, { cache: "no-store", credentials: "same-origin" }).then(function (res) {
      var copy = res.clone(); caches.open(VERSION).then(function (c) { c.put("index.html", copy); });
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
