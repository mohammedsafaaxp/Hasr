# Privacy policy

hasr is a Frappe app that runs inside your own ERPNext site. This page says what it stores and where.

## What hasr stores

- Receiving shipments and stock counts: the purchase order, items, quantities, batches and expiry dates, who
  scanned and when, and the supervisor's decisions.
- Files you add: photos or PDFs of supplier invoices, photos of unknown barcodes and of items that do not match.
- On the phone: the last screens it loaded and the scans waiting to be sent, kept in the browser's local storage
  so the app works offline. They are cleared when someone else signs in on the same phone.

All of it is stored in your ERPNext site's database and file storage, under ERPNext's own permissions.

## What hasr sends elsewhere

Nothing. hasr has no analytics, no tracking and no outside services. The phone app talks only to your own site,
and its fonts and barcode reader are bundled with it.

## Your data

You control it the same way as the rest of your ERPNext data: back it up, export it or delete it from your site.
Uninstalling hasr removes its own document types and their records. Invoice files that were attached to a
Purchase Receipt stay with that receipt, like any other ERPNext attachment.

## Contact

Questions about this policy: [open an issue](https://github.com/mohammedsafaaxp/Hasr/issues).
