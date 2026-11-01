// Expiry dates typed as digits on the keypad: "150327" is 15/03/2027, and "0327" (month only) is 31/03/2027.

export function digitsToIso(digits, monthOnly) {
  if (digits.length < (monthOnly ? 4 : 6)) return ''
  let day = monthOnly ? 0 : Number(digits.slice(0, 2))
  const month = Number(monthOnly ? digits.slice(0, 2) : digits.slice(2, 4))
  const year = 2000 + Number(monthOnly ? digits.slice(2, 4) : digits.slice(4, 6))
  if (month < 1 || month > 12) return null
  if (monthOnly) day = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  return `${year}-${pad(month)}-${pad(day)}`
}

export function isoToDigits(iso) {
  const m = /^\d{2}(\d{2})-(\d{2})-(\d{2})$/.exec(iso || '')
  return m ? m[3] + m[2] + m[1] : ''
}

/** "15 / 03 / 27" with blanks for what is still to type. */
export function slotParts(digits, monthOnly) {
  const size = monthOnly ? 4 : 6
  const filled = digits.padEnd(size, '_')
  const parts = []
  for (let i = 0; i < size; i += 2) parts.push(filled.slice(i, i + 2))
  return parts
}

export function displayDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : ''
}

export function daysUntil(iso, today = new Date()) {
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((Date.parse(iso + 'T00:00:00Z') - start) / 86400000)
}

function pad(n) {
  return String(n).padStart(2, '0')
}
