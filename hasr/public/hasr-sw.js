/* hasr service worker: the phone app opens and works without a connection.
 *
 * - Pages under /hasr: network first, the last copy of the app when offline.
 * - The app's built files, icons and fonts: from the cache (their names change with every build).
 * - Item photos: the cached copy at once, refreshed in the background.
 * - The API is never cached here; the app keeps its own copy of what it shows and queues what it sends.
 */
const SHELL = 'hasr-shell-v1'
const STATIC = 'hasr-static-v1'
const PHOTOS = 'hasr-photos-v1'
const MAX_PHOTOS = 400

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((c) => c.add(new Request('/hasr', { credentials: 'include' })))
      .catch(() => {})
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  const keep = [SHELL, STATIC, PHOTOS]
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('hasr-') && !keep.includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  const msg = event.data || {}
  if (msg.type === 'cache-urls') {
    // the app sends the files it has loaded, so they are there next time without a connection
    event.waitUntil(caches.open(STATIC).then((c) => Promise.all(msg.urls.map((u) => c.add(u).catch(() => {})))))
  } else if (msg.type === 'clear') {
    // signed out: nothing of this user stays on the phone
    event.waitUntil(Promise.all([SHELL, PHOTOS].map((k) => caches.delete(k))))
  }
})

const isStatic = (url) =>
  url.pathname.startsWith('/assets/hasr/') || url.pathname.startsWith('/assets/frappe/') || /\.(woff2?|ttf)$/.test(url.pathname)
const isPhoto = (url) => /^\/(private\/)?files\//.test(url.pathname) && /\.(png|jpe?g|webp|gif|avif)$/i.test(url.pathname)

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return

  if (req.mode === 'navigate' && (url.pathname === '/hasr' || url.pathname.startsWith('/hasr/'))) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone()
            caches.open(SHELL).then((c) => c.put('/hasr', copy))
          }
          return res
        })
        .catch(() => caches.match('/hasr', { cacheName: SHELL }).then((res) => res || Response.error())),
    )
    return
  }

  if (isStatic(url)) {
    event.respondWith(
      caches.match(req, { cacheName: STATIC }).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone()
              caches.open(STATIC).then((c) => c.put(req, copy))
            }
            return res
          }),
      ),
    )
    return
  }

  if (isPhoto(url)) {
    event.respondWith(
      caches.open(PHOTOS).then((cache) =>
        cache.match(req).then((hit) => {
          const fresh = fetch(req)
            .then((res) => {
              if (res.ok) cache.put(req, res.clone()).then(() => trim(cache))
              return res
            })
            .catch(() => hit || Response.error())
          return hit || fresh
        }),
      ),
    )
  }
})

async function trim(cache) {
  const keys = await cache.keys()
  for (const key of keys.slice(0, Math.max(keys.length - MAX_PHOTOS, 0))) await cache.delete(key)
}
