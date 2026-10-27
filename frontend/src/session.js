import { reactive } from 'vue'
import { call } from 'frappe-ui'

export const session = reactive({
  user: 'Guest',
  fullName: null,
  lang: 'en',
  siteName: '',
  version: '',
  get loggedIn() {
    return this.user && this.user !== 'Guest'
  },
})

export async function loadBoot() {
  // production: injected by hasr/www/hasr.py; dev server: fetched
  const boot = window.hasr_boot && typeof window.hasr_boot === 'object' ? window.hasr_boot : await call('hasr.api.i18n.get_boot')
  session.user = boot.user
  session.fullName = boot.full_name
  session.lang = boot.lang
  session.siteName = boot.site_name
  session.version = boot.version
}

export async function login(usr, pwd) {
  await call('login', { usr, pwd })
  // reload so the page gets a fresh CSRF token for the new session
  window.location.href = '/hasr'
}

export async function logout() {
  await call('logout').catch(() => {})
  window.location.href = '/hasr/login'
}

export function initials(name) {
  return (name || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')
}
