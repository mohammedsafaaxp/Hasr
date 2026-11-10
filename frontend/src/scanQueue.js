import { ref } from 'vue'
import { call } from 'frappe-ui'
import { lang } from './i18n'
import { isNetworkError } from './api'

/**
 * Every scan is kept on the phone until the server has answered it, then sent in order.
 * Nothing is dropped: a scan made while another is in flight waits its turn, and a scan that
 * cannot reach the server is retried. Retrying is safe because each scan carries its own
 * client_uuid and the server counts a uuid once.
 */
export function createScanQueue(session, onResult) {
  const key = `hasr_queue_${session}`
  const pending = ref(load())
  const offline = ref(false)
  let flushing = false
  let retryTimer = null
  let delay = 2000

  function load() {
    try {
      return JSON.parse(localStorage.getItem(key) || '[]')
    } catch (e) {
      return []
    }
  }

  function save() {
    try {
      localStorage.setItem(key, JSON.stringify(pending.value))
    } catch (e) {
      /* storage full or blocked: the queue still lives in memory */
    }
  }

  function add(scan) {
    pending.value = [...pending.value, scan]
    save()
    flush()
  }

  async function flush() {
    if (flushing) return
    flushing = true
    clearTimeout(retryTimer)
    try {
      while (pending.value.length) {
        const scan = pending.value[0]
        let out
        try {
          // other changes made while offline (a typed line, a count) wait here too, in order with the scans
          out = scan.method
            ? { answer: await call(`hasr.api.${scan.method}`, { ...scan.args, _lang: lang.value }) }
            : await call('hasr.api.sync.push_scans', { scans: [scan], _lang: lang.value })
        } catch (e) {
          if (isNetworkError(e)) {
            offline.value = true
            retryTimer = setTimeout(flush, delay)
            delay = Math.min(delay * 2, 30000)
            return
          }
          pending.value = pending.value.slice(1)
          save()
          onResult({ error: e }, scan)
          continue
        }
        offline.value = false
        delay = 2000
        pending.value = pending.value.slice(1)
        save()
        onResult(scan.method ? { answer: out.answer } : { result: out.results[0], lines: out.lines }, scan)
      }
    } finally {
      flushing = false
    }
  }

  function stop() {
    clearTimeout(retryTimer)
  }

  return { pending, offline, add, flush, stop }
}
