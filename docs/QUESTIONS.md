# Open questions

Agents: add one entry per question with what you found and what you assumed.

Checked against **ERPNext 15.124.1 / Frappe 15.124.0** unless noted. ✅ = verified, ❓ = needs a product
decision (the code follows the assumption until someone decides).

---

## Verified (TECH_SPEC "VERIFY" items)

### ✅ V1. Units of `Purchase Order Item.received_qty`
Found: the Purchase Receipt status updater writes `Σ PR.received_qty × PR.conversion_factor / PO.conversion_factor`
into `received_qty` (`purchase_receipt.py`, `target_conversion_factor`). So it is in the **PO line's UOM**, and it
**includes rejected quantity** (PR `received_qty = qty + rejected_qty`).
Applied: remaining (stock UOM) = `stock_qty − received_qty × conversion_factor − in-flight hasr sessions`.

### ✅ V2. `supplier_delivery_note` on Purchase Receipt
Exists (Data, "Supplier Delivery Note"). hasr copies the session's value into it.

### ✅ V3. `Item Barcode.barcode` is unique
Yes (`unique: 1`). Linking an unknown barcode that already belongs to another item fails with a clear message.

### ✅ V4. Purchase Receipt row UOM must equal the PO row UOM
Not in the spec, found while testing: `validate_with_previous_doc` compares `uom` with the Purchase Order Item.
So hasr keeps the PO line's UOM and sets `qty = stock qty / conversion_factor`. If that is a fraction and the UOM
is *must be whole number* (e.g. 30 units on a line ordered in boxes of 12), approval stops with a clear message.
See Q3.

### ✅ V5. Purchase Order Item has no `rejected_warehouse`
The field does not exist on v15 (it exists on Purchase Receipt and its rows). hasr therefore uses
**Hasr Settings → Default Rejected Warehouse**; the adapter would pick up a PO-row field if a version adds one.

### ✅ V6. `make_purchase_receipt` and partial rows
`make_purchase_receipt(po, args={"filtered_children": [...]})` keeps only the given rows, and skips rows ERPNext
already sees as fully received. hasr sets accepted / rejected / received qty per row and inserts a **draft**.
Over-receipt allowance is only enforced by ERPNext **on submit** (status updater `validate_qty`), so a draft with an
accepted over-receipt can be created; submitting it needs the *Role Allowed to Over Deliver/Receive* (see Q2).

### ✅ V7. Translations
v15 loads app translations from both `<app>/translations/<lang>.csv` and compiled `.po/.mo` files.
hasr ships `hasr/translations/ar.csv`. (v16: see the v16 section below.)

### ✅ V8. Tests bootstrap
`bench run-tests --app hasr` only runs the *hasr* `before_tests` hook, so hasr's hook calls ERPNext's
`before_tests` (through the adapter) to complete the setup wizard on a fresh test site.

### ⏭ Deferred to their milestones
- SLE `validate` doc_events on v15/v16 (stock freeze) → 0.3.
- `use_serial_batch_fields` / Serial and Batch Bundle per version → 0.2 (batches).
- `get_batch_qty` signature → 0.3.
- PWA service-worker scope under `/hasr` → 0.2.

---

## Product decisions needed

### ❓ Q1. Which PO statuses are receivable?
Assumed: submitted POs with `per_received < 100` whose status is not *Closed, Completed, On Hold, Delivered*.
Is **On Hold** really not receivable on the floor?

### ❓ Q2. Accepting an over-receipt vs. ERPNext's allowance
When the supervisor chooses **Accept** above the allowance, hasr creates the draft PR with the full quantity.
ERPNext will refuse to *submit* it unless the submitter has *Stock Settings → Role Allowed to Over Deliver/Receive*.
Should hasr warn about that in the review screen, or should "Accept" require that role?

### ❓ Q3. Cases split on a whole-number UOM
If a PO line is ordered in *Box* (must be whole) and 30 units arrive (2.5 boxes), ERPNext cannot record it on that
row. Today approval stops and asks to adjust the quantity or the PO. Alternatives: cap to whole boxes, or ask
purchasing to order in the stock UOM. Which one?

### ❓ Q4. What does "Cap" cap to?
Assumed (from the review mockup "Accept 48 only"): received + rejected = the quantity still ordered, i.e. the
allowance is not used. Should Cap instead allow up to the allowance limit?

### ❓ Q5. Does rejected quantity count against the over-receipt allowance?
ERPNext counts it (rejected is part of PO `received_qty`). hasr follows ERPNext: `already + received + rejected >
ordered × (1 + allowance)` marks the line Over.

### ❓ Q6. Unknown barcodes block approval
Assumed: a session cannot be approved while it has *Open* unknown barcodes; the supervisor links or dismisses each
one. Linking is allowed only to an item that is an open line on the same PO (its quantity is then added through an
idempotent scan). OK?

### ❓ Q7. Which POs does a Counter see?
Assumed: ERPNext **User Permissions on Warehouse** decide it (no restriction when the user has none). A PO is
visible when any of its lines is in an allowed warehouse. hasr reads POs server-side, so Counters do not need
read permission on Purchase Order in Desk. Is a separate "warehouse assignment" in hasr wanted later?

### ❓ Q8. Typed item codes
The scan field also accepts an exact **item code** (counts in stock UOM), so a worker can type when a label is
damaged. Should that be allowed, or should only barcodes count?

### ❓ Q9. Session ownership
A Counter can only see and change sessions they started; supervisors can see all. Should a second Counter be able
to take over an open session (e.g. shift change)?

### ❓ Q10. Approving permissions
Approve requires the **Hasr Supervisor** role *and* ERPNext *create* permission on Purchase Receipt (plus *submit*
when "Submit now" is ticked). Should Stock Manager without the hasr role be allowed too?

---

## v16

Checked on a second bench: **ERPNext 16.52.1 / Frappe 16.53.0**, Python 3.14, Node 24.

### ✅ V9. Fresh install on v16
`bench get-app <hasr repo>` + `install-app erpnext` + `install-app hasr` on a new site works with no manual steps;
`get-app` builds the phone app (`hasr/www/hasr.html` present).

### ✅ V10. `erpnext.setup.utils.before_tests` is gone in v16
ERPNext v16 bootstraps its own suite through `erpnext.tests.utils`. The adapter's `testing.before_tests` falls back
to completing the setup wizard itself (same arguments v15 used). All 51 tests pass on v15 and v16.

### ✅ V11. Deprecations
v16 warns that `get_all(limit_page_length=…)` is deprecated; hasr uses `limit=` (works on both). The one warning
left in the v16 test log comes from inside Frappe while inserting an Item, not from hasr.

### ✅ V12. CI matrix
v16 requires Python `>=3.14,<3.15` and Node `>=24` (from `frappe/version-16` pyproject and package.json); the CI
workflow uses 3.11/20 for v15 and 3.14/24 for v16.
