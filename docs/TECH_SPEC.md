# hasr — Technical Specification

This is the build contract. Where it says **VERIFY**, check the behaviour against the installed ERPNext
version before relying on it, and record what you found in `docs/QUESTIONS.md` if it differs.

---

## 1. Architecture

```
Phone (installable web app, Vue 3 + frappe-ui)
   │  same-origin HTTPS, Frappe session cookie
   ▼
hasr Frappe app  (whitelisted API, own DocTypes, hooks, scheduler jobs)
   │  Python calls through hasr/erpnext_adapter/ only
   ▼
ERPNext  (Purchase Order, Purchase Receipt, Stock Reconciliation, Item, Batch, Bin, Stock Ledger Entry)
```

- hasr is installed on the **same site** as ERPNext. No middle server, no CORS, no second login.
- The phone talks only to hasr's API. Only hasr's server code touches ERPNext documents.
- The phone never submits stock documents. hasr creates **drafts**; a user with the right role submits.

## 2. Repository layout

```
hasr/
├── CLAUDE.md, AGENTS.md, README.md, license.txt (GPLv3)
├── docs/                         PRD, this spec, milestones, design
├── hasr/
│   ├── hooks.py
│   ├── patches.txt
│   ├── fixtures/                 custom_field.json, role.json
│   ├── hasr/doctype/             all hasr DocTypes (module "Hasr")
│   ├── api/
│   │   ├── receiving.py
│   │   ├── counting.py
│   │   ├── items.py
│   │   └── sync.py
│   ├── erpnext_adapter/          the ONLY place that imports erpnext.*
│   │   ├── __init__.py           version detection
│   │   ├── purchase_receipt.py
│   │   ├── stock_reconciliation.py
│   │   ├── batches.py
│   │   └── stock.py              balances, bins, over-receipt allowance
│   ├── stock_freeze.py           SLE validation hook
│   ├── abc.py                    ABC classification job
│   ├── gs1.py                    GS1 parser (pure Python, fully unit-tested)
│   ├── tests/
│   ├── public/frontend/          build output (git-ignored except .gitkeep)
│   └── www/hasr.html             build output
└── frontend/                     Vite + Vue 3 + frappe-ui source
```

Start the frontend from the frappe-ui starter (`npx degit netchampfaris/frappe-ui-starter frontend`)
and follow the build-into-app pattern used by Frappe Helpdesk / CRM / Frappe HR.

## 3. hooks.py essentials

```python
app_name = "hasr"
app_title = "hasr"
app_publisher = "hasr contributors"
app_license = "GPL-3.0"
required_apps = ["erpnext"]

website_route_rules = [{"from_route": "/hasr/<path:app_path>", "to_route": "hasr"}]

doc_events = {
    "Stock Ledger Entry": {"validate": "hasr.stock_freeze.validate_sle"},
}

scheduler_events = {
    "hourly": ["hasr.stock_freeze.release_expired_freezes"],
    "weekly": ["hasr.abc.recompute_abc_classes"],
}

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["Hasr Counter", "Hasr Supervisor"]]]},
    {"dt": "Custom Field", "filters": [["module", "=", "Hasr"]]},
]
```

**VERIFY** that Stock Ledger Entries created by `make_sl_entries` run `validate` doc_events on both v15
and v16 (they are inserted as documents, so they should). If not, hook the parent vouchers'
`before_submit` instead (Purchase Receipt, Delivery Note, Sales Invoice, POS Invoice, Stock Entry,
Stock Reconciliation, Purchase Invoice) — keep the check in one function either way.

## 4. Roles and permissions

- **Hasr Counter** — receive and count on the phone. Reads POs, items, batches; creates/edits own sessions.
- **Hasr Supervisor** — opens counts, assigns zones, reviews, approves (creates and submits the ERPNext drafts), links unknown barcodes, lifts freezes.
- Existing **Stock User** / **Stock Manager** keep their ERPNext rights. Approval requires submit rights on Purchase Receipt / Stock Reconciliation in ERPNext; check `frappe.has_permission(doctype, "submit")`.

## 5. DocTypes

All in module **Hasr**. Naming series in brackets.

### Hasr Settings (Single)
| Field | Type | Notes |
|---|---|---|
| default_rejected_warehouse | Link Warehouse | fallback if the PO item has none |
| expiry_warning_pct | Percent | warn when remaining shelf life < this % of Item.shelf_life_in_days. [TBD] |
| allow_freeze | Check | global switch |
| freeze_max_hours | Int | auto-release after this. [TBD] |
| tolerance_a_pct / _b_pct / _c_pct | Percent | variance tolerance per ABC class. Defaults 1 / 2 / 5 [TBD] |
| frequency_a_days / _b_days / _c_days | Int | cycle-count interval. Defaults 30 / 90 / 180 [TBD] |
| abc_a_share / abc_b_share | Percent | cumulative value cut-offs. Defaults 80 / 95 |
| test_count_sample_pct | Percent | supervisor test-count sample. [TBD] |
| gs1_enabled | Check | parse GS1 AIs on scan |

### Hasr Receiving Session [RCV-.YYYY.-.#####]
| Field | Type | Notes |
|---|---|---|
| purchase_order | Link Purchase Order | required, docstatus 1, status not Closed/Completed |
| supplier, company, warehouse | Link | fetched from PO |
| shipment_no | Int | 1, 2, 3… per PO |
| status | Select | Open, Pending Approval, Approved, Sent Back, Cancelled |
| supplier_delivery_note | Data | copied to Purchase Receipt `supplier_delivery_note` (**VERIFY** field name) |
| remaining_expected | Select | Still coming, Supplier will not send |
| received_by | Link User | |
| started_at, finished_at | Datetime | |
| purchase_receipt | Link Purchase Receipt | set on approval |
| lines | Table → Hasr Receiving Line | |

Constraint: at most one session with status **Open** per purchase_order.

### Hasr Receiving Line (child)
| Field | Type | Notes |
|---|---|---|
| po_item | Data | name of the Purchase Order Item row |
| item_code | Link Item | |
| stock_uom | Link UOM | |
| ordered_qty, already_received_qty, pending_qty | Float | snapshots in stock UOM at session start |
| received_qty | Float | stock UOM, sum of scans and manual edits |
| rejected_qty | Float | |
| over_allowance_state | Select | OK, Over (needs decision), Accepted, Capped |
| batches_json | JSON | `[{"expiry_date": "2026-12-20", "qty": 30, "supplier_batch": null}]` |

### Hasr Scan (idempotency log)
| Field | Type | Notes |
|---|---|---|
| client_uuid | Data | **unique**, generated on the phone |
| session_type | Select | Receiving, Count |
| session | Dynamic Link | |
| barcode, item_code, uom | Data / Link | |
| qty_stock_uom | Float | after UOM conversion |
| batch_no, expiry_date | Data / Date | from GS1 or entry |
| scanned_at | Datetime | device time |
| device_id, user | Data / Link User | |
| undone | Check | undo sets this, never deletes |

### Hasr Unknown Barcode
barcode, session (Dynamic Link), qty, note, photo (Attach Image), status (Open, Linked, Dismissed),
linked_item (Link Item), linked_uom (Link UOM). Linking adds an **Item Barcode** row to the item
(barcode is unique in ERPNext — **VERIFY**) and re-applies the qty to the session line.

### Hasr Count Session [CNT-.YYYY.-.#####]
| Field | Type | Notes |
|---|---|---|
| warehouse, company | Link | |
| count_type | Select | Full, Cycle |
| entry_method | Select | Scan, List |
| scope_type | Select | Warehouse, Item Group, Brand, Items, ABC Due, Problem Items |
| scope_value | Data / Dynamic | group, brand, or JSON list |
| freeze | Check | |
| status | Select | Draft, Counting, Recount, Pending Approval, Approved, Cancelled |
| snapshot_at | Datetime | balances captured at start (Full) |
| stock_reconciliation | Link Stock Reconciliation | |
| zones | Table → Hasr Count Zone (zone name, counter: Link User, handed_over: Check) |
| lines | Table → Hasr Count Line |

### Hasr Count Line (child)
item_code, batch_no (required when Item.has_batch_no), zone, system_qty (snapshot, **never sent to the
phone**), count_1_qty, count_1_by, count_2_qty, count_2_by, test_count_qty, final_qty, variance_qty,
variance_value, abc_class, within_tolerance (Check), reason (Select: Theft, Damage, Receiving error,
Picking error, Unit of measure error, Unknown, Other), reason_note.

### Hasr Stock Freeze
item_code, warehouse, count_session, active (Check), frozen_at, expires_at. Index on (item_code, warehouse, active).

### Hasr ABC Class
item_code, warehouse, abc_class (A/B/C), annual_value, last_counted_on, next_due_on.

### Custom Fields (fixtures)
- Item `hasr_storage` (Select: Ambient, Chilled, Frozen) — shown on item details.

## 6. ERPNext integration (adapter layer)

All of this lives in `hasr/erpnext_adapter/`.

**Purchase orders.** Read `Purchase Order` (docstatus 1) and its items: `item_code, qty, stock_qty, uom, conversion_factor, received_qty, warehouse, rejected_warehouse`. Remaining per line (stock UOM) = `stock_qty − received_qty × conversion_factor − qty in sessions Pending Approval` (**VERIFY** units of `received_qty`).

**Over-receipt allowance.** Item-level `over_delivery_receipt_allowance` if set, else Stock Settings `over_delivery_receipt_allowance`. Limit = ordered × (1 + allowance/100). Above the limit the line becomes `Over` and needs a supervisor decision.

**Barcodes and UOMs.** Look up `Item Barcode` (barcode → parent item, `uom`). Convert with `UOM Conversion Detail.conversion_factor` on the item. Unknown barcode → Hasr Unknown Barcode.

**Creating the Purchase Receipt (on approval).**
```python
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
pr = make_purchase_receipt(session.purchase_order)
# keep only lines in this session; set qty, rejected_qty, rejected_warehouse,
# supplier_delivery_note; split rows per batch
pr.insert()          # draft
# supervisor submits from the review screen (pr.submit()) or in Desk
```

**Batches.** For each (item, expiry_date) group create a `Batch` with `item` and `expiry_date` (and `manufacturing_date` when known). Its name comes from the item's `batch_number_series` when `create_new_batch` is set. Then attach it to the PR row. **VERIFY per version:** in v15+ prefer setting `use_serial_batch_fields = 1` and `batch_no` on the row so ERPNext builds the Serial and Batch Bundle on submit; if that field is unavailable, create the bundle through ERPNext's serial-batch utilities. Wrap both in `batches.attach_batch(row, batch_no, qty)`.

**Stock Reconciliation (on count approval).**
```python
sr = frappe.new_doc("Stock Reconciliation")
sr.purpose = "Stock Reconciliation"
sr.company = session.company
sr.set_posting_time = 1
sr.posting_date, sr.posting_time = count_datetime  # snapshot_at for Full, per-line counted_at for Cycle
for line in final_lines:
    sr.append("items", {"item_code": ..., "warehouse": ..., "qty": line.final_qty,
                        "batch_no": line.batch_no, "use_serial_batch_fields": 1})  # VERIFY per version
sr.insert()  # draft; supervisor submits
```
Back-dated reconciliations trigger ERPNext reposting; that is expected.

**Balances for counting.** Snapshot from `Bin.actual_qty` per item/warehouse, and per batch with
`erpnext.stock.doctype.batch.batch.get_batch_qty` (**VERIFY** signature per version). Never return these to Counter users.

## 7. Stock freeze

```python
def validate_sle(doc, method=None):
    if not frappe.db.exists("Hasr Stock Freeze", {"active": 1}):   # fast path, cache this
        return
    freeze = frappe.db.get_value("Hasr Stock Freeze",
        {"item_code": doc.item_code, "warehouse": doc.warehouse, "active": 1},
        ["name", "count_session"], as_dict=True)
    if not freeze:
        return
    if doc.voucher_type == "Stock Reconciliation" and \
       frappe.db.get_value("Hasr Count Session", freeze.count_session, "stock_reconciliation") == doc.voucher_no:
        return
    frappe.throw(_("{0} is frozen in {1} for stock count {2}.").format(doc.item_code, doc.warehouse, freeze.count_session))
```
Release on approval, cancellation, manual unfreeze (Supervisor), or `expires_at` (hourly job).
Cache active (item, warehouse) pairs in `frappe.cache` and clear on change; this runs on every stock movement.

## 8. API (whitelisted, JSON)

All methods check roles and return translated error messages. Prefix: `hasr.api`.

- `receiving.list_open_orders(warehouse=None, search=None)` → POs with supplier, item count, schedule date, status badge data.
- `receiving.start_session(purchase_order)` → session with lines and remaining qty. Fails if an Open session exists.
- `receiving.get_session(name)`
- `receiving.set_line(session, po_item, received_qty, rejected_qty, batches)` → updated line + over-allowance state.
- `receiving.finish_session(session, supplier_delivery_note, remaining_expected)` → Pending Approval.
- `receiving.approve(session, decisions)` (Supervisor) → creates draft PR, optionally submits.
- `counting.create_session(...)`, `counting.get_my_zone(session)` (no system qty), `counting.set_count(...)`, `counting.hand_over(session, zone)`, `counting.review(session)` (Supervisor, with variances), `counting.approve(session, reasons)`.
- `items.get_item_details(item_code)` → image, extra images (File attached to Item with image extension), description, item_group, brand, stock_uom, uoms, barcodes, shelf_life_in_days, weight_per_unit + weight_uom, hasr_storage, last receipt. Exclude stock balances.
- `sync.push_scans(scans: list)` → per-scan result `{client_uuid, status: "applied" | "duplicate" | "rejected", message}` plus updated line states. Must be idempotent on `client_uuid`.
- `items.resolve_barcode(code)` → item, uom, conversion, GS1-parsed batch/expiry.

## 9. Offline sync

- The phone caches the open session, its lines, item details and thumbnails in IndexedDB.
- Each scan is written locally first with a UUIDv4, then queued. The queue flushes in order with `sync.push_scans` when online; retries with backoff.
- The server dedupes on `Hasr Scan.client_uuid` (unique index). Undo is a new event that marks the original `undone`.
- Line totals are always recomputed server-side from non-undone scans plus manual edits; the phone shows the server's numbers after each sync.
- The UI shows `Offline · N queued` until the queue is empty.

## 10. GS1 parsing (`hasr/gs1.py`)

Support both human-readable `(01)…(10)…(17)…` and raw FNC1/GS (`\x1d`) separated strings.
AIs: 01 GTIN-14 (fixed 14), 10 batch (variable, max 20), 17 expiry YYMMDD (fixed 6), 11 production date
YYMMDD, 21 serial (parse but ignore in v1). Day `00` means the last day of the month. Map GTIN to an
Item Barcode (try GTIN-14 and its GTIN-13 form without the leading zero). 100% unit test coverage.

## 11. ABC classification (`hasr/abc.py`, weekly)

Per warehouse, annual usage value per item = Σ |actual_qty| × valuation_rate over outgoing Stock Ledger
Entries in the last 365 days. Sort descending, cumulative share ≤ abc_a_share → A, ≤ abc_b_share → B,
else C. Store in Hasr ABC Class; `next_due_on = last_counted_on + frequency`.

## 12. Frontend

- Routes: `/hasr` (home, receive/count tabs), `/hasr/receive/:session`, `/hasr/receive/:session/line/:poItem`,
  `/hasr/items/:itemCode`, `/hasr/count/new`, `/hasr/count/:session`.
- Use frappe-ui components (`Button`, `TextInput`, `Dialog`, `Badge`, `TabButtons`, `createResource`).
- Scanner: one `ScanInput` component that always holds focus for keyboard-wedge scanners and opens a
  `@zxing/browser` camera sheet. Beep + `navigator.vibrate` on success; distinct sound on error.
- RTL: set `dir` on `<html>` from the user's language; use logical Tailwind utilities only.
- Match `docs/design/screens/*.png`. Tokens in `docs/design/README.md`.
- PWA: `vite-plugin-pwa` with the hasr icon set; **VERIFY** service-worker scope when served under `/hasr`
  (follow how Frappe HR serves its PWA). Camera and install need HTTPS.

## 13. Testing and CI

- Unit tests: `gs1.py`, UOM conversion, remaining-qty math, over-allowance, idempotent `push_scans`,
  freeze hook (blocks a Delivery Note, allows the session's reconciliation), ABC classification.
- Integration tests create a PO in a test company, run a session through approval and assert the draft PR
  (qty, rejected qty, batches with expiry).
- GitHub Actions matrix: ERPNext `version-15` and `version-16` (or `develop` until 16 is tagged — **VERIFY**).
