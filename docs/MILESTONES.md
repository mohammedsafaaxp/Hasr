# Milestones

Build one milestone at a time. A milestone is done only when every acceptance criterion passes in tests
or in a recorded manual check, and `README.md` explains how to try it.

---

## 0.1 — Online receiving against a purchase order  ← CURRENT

Goal: a Hasr Counter receives a PO on a phone (online only) and a Hasr Supervisor turns it into a draft
Purchase Receipt.

### Tasks, in order

1. **Scaffold the app.** `bench new-app hasr`, module "Hasr", GPLv3 `license.txt`, `required_apps = ["erpnext"]`,
   roles Hasr Counter and Hasr Supervisor as fixtures, `Hasr Settings` single DocType, CI workflow
   that installs ERPNext v15 and runs `bench run-tests --app hasr`.
2. **Adapter layer.** `hasr/erpnext_adapter/` with version detection and functions:
   `get_open_purchase_orders`, `get_po_lines_with_remaining`, `resolve_barcode`, `get_over_receipt_limit`,
   `create_draft_purchase_receipt`. Unit-test each against fixtures created in tests.
3. **DocTypes.** Hasr Receiving Session, Hasr Receiving Line, Hasr Scan, Hasr Unknown Barcode
   (fields per TECH_SPEC §5; batches_json can stay unused until 0.2).
4. **API.** `receiving.list_open_orders`, `start_session`, `get_session`, `set_line`, `finish_session`,
   `approve`; `sync.push_scans` (online use, but already idempotent); `items.resolve_barcode`,
   `items.get_item_details`.
5. **Frontend scaffold.** frappe-ui starter, build into the app, served at `/hasr`, login via Frappe session,
   English + Arabic strings, `dir` switching.
6. **Screens.** Sign in (Frappe login redirect is fine), Home (receive tab), Receiving, Line sheet
   (quantity, UOM, rejected qty — no batches yet), Item details with zoomable photo, Unknown barcode sheet.
   Match `docs/design/screens/`.
7. **Camera scanning** with `@zxing/browser`, plus keyboard-wedge input.
8. **Supervisor review** in Desk: a form view of Hasr Receiving Session with buttons
   "Approve and create Purchase Receipt" and "Send back", and the over-allowance decision per line.

### Acceptance criteria

- Installing on a fresh site with ERPNext v15 works with `bench get-app` + `install-app` and no manual steps.
- A Counter sees only submitted, not-closed POs for warehouses they can access.
- Scanning a unit barcode adds 1; scanning a case barcode adds the case's conversion factor in stock UOM.
- Scanning an unknown barcode opens the unknown-barcode sheet; the phone cannot create an Item.
- A scan for an item not on the PO is rejected with a clear message and is not counted.
- Exceeding ordered × (1 + allowance%) marks the line Over; the supervisor can Accept or Cap.
- Sending the same `client_uuid` twice changes the totals once.
- Starting a second Open session on the same PO fails with a clear message.
- Approve creates a **draft** Purchase Receipt linked to the PO with the session's qty and rejected qty
  (rejected warehouse from the PO item or Hasr Settings); nothing is submitted unless the supervisor chooses to.
- The Counter role cannot call `approve`.
- Item details never return stock balances.
- All UI strings are translatable; the Arabic UI renders RTL with no left/right-hardcoded spacing.
- CI is green on ERPNext v15.

---

## 0.2 — Field-ready receiving

Offline queue and sync (TECH_SPEC §9), installable PWA, batches with expiry and automatic batch creation on
approval, GS1 parsing, expiry warnings, multiple shipments per PO with remaining-qty math including
pending sessions, finish-shipment sheet (supplier delivery note, remaining expected), undo, sound and
vibration. CI on v15 and v16.

## 0.3 — Counting

Count sessions (Full / Cycle, Scan / List, all scopes), zones, blind counting per batch, recount by a
different user, supervisor test counts, ABC classification job, stock freeze hook with auto-release,
variance reasons, draft Stock Reconciliation at count time, IRA report per warehouse.

## 1.0 — Public release

English and Arabic docs, demo site with invented data, screenshots, contribution guide, issue templates,
release workflow, announcement on the Frappe forum.
