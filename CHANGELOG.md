# Changelog

## 1.0.0 — 2026-11-10

First public release. Works on ERPNext v15 and v16, in English and Arabic.

### Receiving
- Receive against a submitted purchase order from the phone at `/hasr`, several shipments per order, one open
  shipment per order at a time.
- Scan, then type the quantity on an in-app keypad; the barcode decides the unit (a case barcode counts cases).
- Check the item against its photo before counting; an item that is not on the order is refused clearly and can
  be reported for the supervisor.
- Expiry dates on a six-digit keypad, month-and-year packs, several dates per delivery; ERPNext batches are
  created on approval, one receipt row per batch.
- GS1-128 and GS1 DataMatrix codes: the GTIN finds the item, the expiry date fills itself in.
- Supplier invoice number and photos or PDF, carried to the Purchase Receipt and the Purchase Invoice.
- Supplier offers: free goods as free rows with a Pricing Rule, so the cost is spread over all units.
- Unknown barcodes and items that do not match their photo are reported with a picture.

### Stock counts
- Full and cycle counts by warehouse, item group, brand, chosen items, ABC class due, or problem items.
- Zones with one counter each; blind counting per batch on the phone; recount by someone else; supervisor
  test counts; a reason for every difference.
- Optional stock freeze during a count, lifted on approval, cancellation, by hand or after a maximum time.
- Approval creates a Stock Reconciliation for the differences; weekly ABC classification; inventory accuracy
  report.
- Several counters can save to the same count at the same moment; whole-unit items are counted in whole numbers;
  without a freeze a recount is compared with the balance at the recount.

### Review and control
- Desk review of shipments and counts; Today's Shipments with one-click approval of matching shipments.
- Approver roles in Hasr Settings; nobody approves what they received or counted, or a count where their own test
  count changed a quantity; warehouse access from ERPNext User Permissions.
- Records change only through hasr's checks; uploads are checked; the phone never sees stock balances.

### Phone app
- Installs to the home screen with its own name and icon, in the app language.
- Works offline: the app opens without a connection, scans, quantities and counts wait on the phone and are sent
  in order. Each scan carries an ID, so nothing counts twice, and what waits on a shared phone is sent only by the
  person who scanned it.
