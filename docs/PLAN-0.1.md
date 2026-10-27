# Plan — milestone 0.1 (online receiving against a purchase order)

Target: ERPNext v15 (verified on 15.124.1); v16 kept working through the adapter and the CI matrix.
Dev bench: `hasr-bench` (Python 3.11, Node 20), site `hasr.test`.

## Files by task

| # | Task | Files |
|---|---|---|
| 1 | Scaffold | `pyproject.toml`, `LICENSE` (GPLv3), `README.md`, `hasr/__init__.py`, `hasr/hooks.py`, `hasr/modules.txt`, `hasr/patches.txt`, `hasr/fixtures/role.json`, `hasr/hasr/doctype/hasr_settings/*`, `hasr/install.py`, `.github/workflows/ci.yml` |
| 2 | Adapter | `hasr/erpnext_adapter/__init__.py` (version detection + public API), `purchase_order.py`, `items.py`, `stock.py`, `purchase_receipt.py`, `testing.py` |
| 3 | DocTypes | `hasr_receiving_session`, `hasr_receiving_line`, `hasr_scan`, `hasr_unknown_barcode` under `hasr/hasr/doctype/` |
| 4 | API | `hasr/api/__init__.py` (role guards), `receiving.py`, `sync.py`, `items.py`, `i18n.py` |
| 5 | Frontend scaffold | `frontend/` (Vite + Vue 3 + frappe-ui + Tailwind), `hasr/www/hasr.py` (boot context), build output `hasr/public/frontend`, `hasr/www/hasr.html` |
| 6 | Screens | `frontend/src/pages/{Login,Home,Receive,ItemDetails}.vue`, `components/{LineSheet,UnknownBarcodeSheet,BottomSheet,Toast,ImageZoom}.vue`, `hasr/translations/ar.csv` |
| 7 | Scanning | `frontend/src/components/{ScanInput,CameraSheet}.vue` (`@zxing/browser`) |
| 8 | Supervisor review | `hasr_receiving_session.js` (Desk form buttons + decisions panel), `receiving.approve / send_back / decide_line / link_unknown_barcode / dismiss_unknown_barcode` |

## Design decisions (assumptions logged in QUESTIONS.md)

- Line totals: `received_qty = scanned_qty + manual_adjust_qty`. `scanned_qty` is always recomputed
  from applied, non-undone `Hasr Scan` rows; `set_line` stores the difference as the manual adjustment.
- One-open-session rule is enforced twice: in `validate` and by a unique `open_lock` column that holds the
  PO name while the session is Open / Sent Back and NULL otherwise (closes the race between two phones).
- Idempotency: `Hasr Scan.client_uuid` is unique; rejected scans are logged too, so a replay of any uuid
  returns `duplicate` and never changes totals.
- Remaining qty (stock UOM) = `stock_qty − received_qty × conversion_factor − qty already in other sessions
  that are Pending Approval or Approved with a still-draft Purchase Receipt`.
- Over-allowance: limit = `stock_qty × (1 + allowance/100)` (item allowance, else Stock Settings).
  Over when `already_received + other_pending + received + rejected > limit` (ERPNext counts rejected qty
  in PO `received_qty`). Cap sets the line so that received + rejected = remaining ordered qty.
- PR rows: kept in the PO UOM when the stock qty divides evenly, otherwise switched to stock UOM with the rate
  divided by the conversion factor (avoids fractional cases on whole-number UOMs).

## How each acceptance criterion is tested

| Acceptance criterion | Test |
|---|---|
| Fresh install, no manual steps | CI job: `bench new-site` → `install-app hasr` → `run-tests`; locally the same on `hasr.test`. `test_install.py` asserts roles + settings exist after install. |
| Counter sees only submitted, not-closed POs for permitted warehouses | `test_adapter.py::test_open_purchase_orders_filters` (draft, closed, other-warehouse PO with a User Permission) |
| Unit barcode +1, case barcode + conversion factor | `test_sync.py::test_unit_and_case_scan` |
| Unknown barcode → sheet; phone cannot create Item | `test_sync.py::test_unknown_barcode_rejected_and_logged`, `test_api.py::test_counter_cannot_create_item`; UI: manual check of the sheet |
| Item not on PO rejected, not counted | `test_sync.py::test_item_not_on_po_rejected` |
| Over limit → Over; supervisor Accept / Cap | `test_receiving.py::test_over_allowance_accept_and_cap` |
| Same client_uuid twice changes totals once | `test_sync.py::test_idempotent_push` |
| Second Open session fails clearly | `test_receiving.py::test_second_open_session_fails` |
| Approve → draft PR with qty + rejected qty + rejected warehouse; no submit unless asked | `test_receiving.py::test_approve_creates_draft_pr`, `test_approve_with_submit`, `test_rejected_warehouse_fallback` |
| Counter cannot call approve | `test_receiving.py::test_counter_cannot_approve` |
| Item details never return balances | `test_items.py::test_item_details_have_no_balances` |
| Strings translatable; Arabic RTL, no left/right spacing | `test_i18n.py` (ar.csv covers every `__()` string in the frontend; frontend source has no `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`) + manual check in Arabic |
| CI green on v15 | `.github/workflows/ci.yml` matrix (v15 required, v16 also run) |
