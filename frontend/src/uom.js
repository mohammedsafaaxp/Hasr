import { __, formatNumber } from './i18n'

/** "1 Box = 12 Nos" for a barcode / UOM that is not the stock unit. */
export function conversionText(uom, cf, stockUom) {
  return __('1 {0} = {1} {2}', [__(uom), formatNumber(cf), __(stockUom)])
}

/** What the PO asks for, in the PO's unit and, when different, in stock units: "4 Box (48 Nos)". */
export function orderedText(line) {
  const stock = `${formatNumber(line.pending_qty)} ${__(line.stock_uom)}`
  if (!line.uom || line.uom === line.stock_uom || !line.conversion_factor) return stock
  return `${formatNumber(line.pending_qty / line.conversion_factor)} ${__(line.uom)} (${stock})`
}

/** Barcodes with the unit each one counts: [{ barcode, unit, cf }] — the case barcode shows "Box ×12". */
export function barcodeRows(line) {
  return (line.barcodes || []).map((b) => {
    const uom = b.uom || line.stock_uom
    const cf = (line.uoms || []).find((u) => u.uom === uom)?.conversion_factor || 1
    return { barcode: b.barcode, unit: cf === 1 ? __(uom) : `${__(uom)} ×${formatNumber(cf)}`, cf }
  })
}
