import { api, isNetworkError } from './api'

// What the phone last saw from the server, for when there is no connection. Small JSON only; photos and the
// app itself are kept by the service worker (hasr/public/hasr-sw.js).
const PREFIX = 'hasr_cache_'

export function readCache(key) {
  try {
    return JSON.parse(localStorage.getItem(PREFIX + key) || 'null')
  } catch (e) {
    return null
  }
}

export function writeCache(key, data) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ data, at: Date.now() }))
  } catch (e) {
    /* storage full or blocked: works online only */
  }
}

/**
 * api() that remembers its answer. Without a connection it returns the last answer instead, marked
 * { offline: true, at }; any other error is thrown as usual.
 */
export async function cachedApi(key, method, args) {
  try {
    const data = await api(method, args)
    writeCache(key, data)
    return { data, offline: false }
  } catch (e) {
    const hit = isNetworkError(e) && readCache(key)
    if (!hit) throw e
    return { data: hit.data, offline: true, at: hit.at }
  }
}

export function clearCache() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIX)) // queued scans stay: they are sent when this user signs in again
      .forEach((k) => localStorage.removeItem(k))
  } catch (e) {
    /* nothing stored */
  }
}

export function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) return
  navigator.serviceWorker
    .register('/hasr-sw.js', { scope: '/hasr' })
    .then(() => navigator.serviceWorker.ready)
    .then((reg) => {
      // keep the files this page loaded, and load every screen now so all of them open offline later
      const urls = performance
        .getEntriesByType('resource')
        .map((r) => r.name)
        .filter((u) => u.startsWith(location.origin + '/assets/'))
      reg.active?.postMessage({ type: 'cache-urls', urls })
      for (const page of [
        () => import('./pages/Home.vue'),
        () => import('./pages/Receive.vue'),
        () => import('./pages/ItemDetails.vue'),
        () => import('./pages/CountList.vue'),
        () => import('./pages/Count.vue'),
      ])
        page().catch(() => {})
    })
    .catch(() => {})
}

export function forgetUserData() {
  clearCache()
  navigator.serviceWorker?.controller?.postMessage({ type: 'clear' })
}
