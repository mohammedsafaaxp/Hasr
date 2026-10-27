import { call } from 'frappe-ui'
import { __ } from './i18n'

const BASE = 'hasr.api.'

export function api(method, args = {}) {
  return call(BASE + method, args)
}

/** A readable message from a frappe-ui request error. */
export function errorMessage(error) {
  const messages = (error && error.messages) || []
  const text = messages
    .map((m) => (typeof m === 'string' ? m : m.message || ''))
    .filter(Boolean)
    .join(' ')
  const plain = text.replace(/<[^>]+>/g, '')
  if (plain) return plain
  if (error && /fetch|network/i.test(String(error.message))) return __('No connection. Try again.')
  return __('Something went wrong. Try again.')
}

/** UUIDv4 that also works on plain-http LAN addresses, where crypto.randomUUID is missing. */
export function uuid4() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID()
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = [...b].map((x) => x.toString(16).padStart(2, '0'))
  return `${h.slice(0, 4).join('')}-${h.slice(4, 6).join('')}-${h.slice(6, 8).join('')}-${h.slice(8, 10).join('')}-${h.slice(10).join('')}`
}

export function deviceId() {
  try {
    let id = localStorage.getItem('hasr_device')
    if (!id) {
      id = uuid4()
      localStorage.setItem('hasr_device', id)
    }
    return id
  } catch (e) {
    return 'unknown'
  }
}
