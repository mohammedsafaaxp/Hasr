// GS1 codes on the phone, so a carton's GS1 code matches a line without asking the server (also offline).
// The server reads them the same way (hasr/gs1.py) and decides; this only finds the line and the date.

const GS = '\x1d'
const AIS = { '00': 18, '01': 14, '02': 14, 10: -20, 11: 6, 13: 6, 15: 6, 17: 6, 21: -20, 30: -8, 37: -8 }

function parseDate(v) {
  if (!/^\d{6}$/.test(v)) return null
  const now = new Date().getFullYear()
  let year = now - (now % 100) + Number(v.slice(0, 2))
  if (year - now > 49) year -= 100
  else if (now - year > 50) year += 100
  const month = Number(v.slice(2, 4))
  if (month < 1 || month > 12) return null
  const last = new Date(year, month, 0).getDate()
  const day = Number(v.slice(4)) || last
  if (day > last) return null
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function fields(code) {
  const out = {}
  if (code.startsWith('(')) {
    const re = /\((\d{2})\)([^()]*)/g
    let pos = 0
    for (const m of code.matchAll(re)) {
      if (m.index !== pos || !(m[1] in AIS)) return null
      out[m[1]] = m[2]
      pos = m.index + m[0].length
    }
    return pos === code.length ? out : null
  }
  let i = 0
  while (i < code.length) {
    if (code[i] === GS) {
      i++
      continue
    }
    const ai = code.slice(i, i + 2)
    const len = AIS[ai]
    if (!len) return null
    let end = len > 0 ? i + 2 + len : code.indexOf(GS, i + 2)
    if (end === -1) end = code.length
    out[ai] = code.slice(i + 2, end)
    i = end
  }
  return out
}

/** { gtin, batch, expiry } from a GS1 code, or null for an ordinary barcode. */
export function parseGs1(code) {
  if (!code) return null
  code = code.trim()
  const prefixed = /^\][A-Za-z]\d/.test(code)
  if (prefixed) code = code.slice(3)
  const raw = prefixed || code.includes(GS) || (code.length > 16 && /^0[12]\d{14}/.test(code))
  if (!code.startsWith('(') && !raw) return null
  const f = fields(code)
  if (!f || !(f['01'] || f['02'] || f['10'])) return null
  return { gtin: f['01'] || f['02'] || null, batch: f['10'] || null, expiry: parseDate(f['17'] || f['15'] || '') }
}

/** The forms a GTIN may be stored in as an item barcode: GTIN-14, EAN-13, UPC-A, EAN-8. */
export function gtinCandidates(gtin) {
  const out = [gtin]
  let s = gtin
  while (s.startsWith('0') && s.length > 8) {
    s = s.slice(1)
    if ([13, 12, 8].includes(s.length)) out.push(s)
  }
  return out
}
