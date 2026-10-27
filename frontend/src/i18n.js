import { ref } from 'vue'
import { call } from 'frappe-ui'

// Languages written right-to-left; the whole UI mirrors for them.
const RTL = ['ar', 'fa', 'he', 'ur', 'ps', 'ckb', 'ku', 'dv', 'yi']
export const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'ar', label: 'العربية' },
]
const STORAGE_KEY = 'hasr_lang'

const messages = ref({})
export const lang = ref('en')

function format(text, args) {
  if (!args) return text
  const list = Array.isArray(args) ? args : [args]
  return text.replace(/{(\d+)}/g, (m, i) => (list[i] !== undefined ? list[i] : m))
}

/** Translate a source string. Every user-facing string goes through this. */
export function __(text, args) {
  return format(messages.value[text] || text, args)
}

export const isRTL = (code) => RTL.includes((code || '').split('-')[0])

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch (e) {
    return null
  }
}

export function pickLanguage(bootLang) {
  const stored = readStored()
  const device = (navigator.language || 'en').split('-')[0]
  const candidate = stored || (bootLang && bootLang !== 'en' ? bootLang : device)
  return LANGUAGES.some((l) => l.value === candidate) ? candidate : 'en'
}

export async function setLanguage(code, { remember = false } = {}) {
  code = (code || 'en').split('-')[0]
  if (remember) {
    try {
      localStorage.setItem(STORAGE_KEY, code)
    } catch (e) {
      /* private mode: language just isn't remembered */
    }
  }
  messages.value = code === 'en' ? {} : await call('hasr.api.i18n.get_translations', { lang: code }).catch(() => ({}))
  lang.value = code
  const html = document.documentElement
  html.setAttribute('lang', code)
  html.setAttribute('dir', isRTL(code) ? 'rtl' : 'ltr')
}

export const translationPlugin = {
  install(app) {
    app.config.globalProperties.__ = __
    window.__ = __
  },
}

export function formatNumber(value, maxFractionDigits = 3) {
  const n = Number(value || 0)
  return new Intl.NumberFormat(lang.value, { maximumFractionDigits: maxFractionDigits }).format(n)
}

export function formatDate(value, options = { day: 'numeric', month: 'short' }) {
  if (!value) return ''
  const d = new Date(String(value).replace(' ', 'T'))
  return new Intl.DateTimeFormat(lang.value, options).format(d)
}

export function formatTime(value) {
  return new Intl.DateTimeFormat(lang.value, { hour: 'numeric', minute: '2-digit' }).format(value || new Date())
}
