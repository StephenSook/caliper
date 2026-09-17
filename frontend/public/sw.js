/*
  CALIPER service worker.

  This exists for one reason: so a judge can add CALIPER to a phone home screen
  and open it as an app, with no browser chrome and no install. It is not an
  offline strategy and it deliberately does not try to be one.

  The governing risk is the opposite of the usual one. The usual PWA worry is a
  user offline; ours is a stale worker serving yesterday's JavaScript at a
  judging table while the backend has moved on. Every decision below is made
  against that risk:

    - the worker takes over immediately (skipWaiting plus claim) rather than
      waiting for every tab to close, so a deploy cannot be half applied
    - navigations are network first, so the freshly built index.html always wins
      when the network is there
    - only Vite's content hashed bundles are served cache first, and those are
      safe by construction because a changed file gets a changed name
    - /api, /ws and /judge are never touched at all. The product's whole claim
      is that nothing on screen is stale or mocked, and a cached API response
      would make that claim false.
*/

const VERSION = "caliper-v3";
const SHELL = `${VERSION}-shell`;

// Only paths whose names are stable at author time. The hashed bundles are not
// listed here because their filenames are not knowable until the build runs;
// they are picked up by the runtime cache-first rule instead.
const PRECACHE = [
  "/",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
];

// Anything under these prefixes is passed straight through to the network. A
// cached answer here would be a wrong answer.
const NEVER_CACHE = ["/api/", "/ws", "/judge"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      // addAll rejects the whole install if any single entry 404s, which would
      // leave the page with no worker at all. Failing soft per entry is the
      // right trade for a shell this small.
      .then((cache) => Promise.all(PRECACHE.map((p) => cache.add(p).catch(() => undefined))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function cacheable(response) {
  return response && response.status === 200 && response.type === "basic";
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (NEVER_CACHE.some((p) => url.pathname === p || url.pathname.startsWith(p))) return;

  // Navigations: network first, cache only as a last resort. A judge on a
  // conference network gets the real page; a judge on no network at least gets
  // the shell and an honest failure from the API rather than a browser error.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (cacheable(res)) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put("/", copy));
          }
          return res;
        })
        .catch(() => caches.match("/").then((hit) => hit || Response.error())),
    );
    return;
  }

  // Vite emits content hashed bundles under /assets. A changed file gets a
  // changed name, so serving these from cache can never be stale.
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (cacheable(res)) {
              const copy = res.clone();
              caches.open(SHELL).then((c) => c.put(req, copy));
            }
            return res;
          }),
      ),
    );
    return;
  }

  // Everything else same origin (icons, the manifest, the audio worklet):
  // serve what we have and refresh it in the background.
  event.respondWith(
    caches.match(req).then((hit) => {
      const network = fetch(req)
        .then((res) => {
          if (cacheable(res)) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || network;
    }),
  );
});

// Lets the page force an update without a reload cycle, used by the version
// check in the app shell.
self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});
