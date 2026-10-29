"""Create Purchase Receipts in ERPNext. hasr only ever inserts drafts here; submit is a separate call."""

import frappe
from frappe import _
from frappe.utils import flt

from hasr.erpnext_adapter.batches import attach_batch, create_batch, get_batch_settings, link_batches_to_voucher


def create_draft_purchase_receipt(
	purchase_order: str,
	lines: list[dict],
	supplier_delivery_note: str | None = None,
	default_rejected_warehouse: str | None = None,
	remarks: str | None = None,
):
	"""Insert a draft Purchase Receipt for `lines` of `purchase_order`.

	Each line: {"po_item", "qty", "rejected_qty", "rejected_warehouse"?, "batches"?} with quantities in stock
	UOM. `batches` is [{"expiry_date", "qty"}] for batch-tracked items: one Batch is created per expiry date and
	the PO row is split into one Purchase Receipt row per batch (rejected qty goes on the first one).
	Returns the inserted (docstatus 0) Purchase Receipt.
	"""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	wanted = {
		line["po_item"]: line for line in lines if flt(line.get("qty")) > 0 or flt(line.get("rejected_qty")) > 0
	}
	if not wanted:
		frappe.throw(_("Nothing was received in this session."))

	pr = make_purchase_receipt(purchase_order, args={"filtered_children": list(wanted)})

	planned = []  # (template row, accepted, rejected, batch_no)
	created_batches = {}
	for row in pr.items:
		line = wanted.get(row.purchase_order_item)
		if not line:
			continue
		accepted, rejected = flt(line.get("qty")), flt(line.get("rejected_qty"))
		batches = line.get("batches") or []
		if not get_batch_settings(row.item_code).has_batch_no:
			planned.append((row, accepted, rejected, None))
			continue
		if not batches:
			frappe.throw(_("{0} is batch tracked. Enter the expiry date for what was received.").format(row.item_code))
		for i, entry in enumerate(batches):
			key = (row.item_code, str(entry["expiry_date"]))
			if key not in created_batches:
				created_batches[key] = create_batch(row.item_code, entry["expiry_date"], entry.get("manufacturing_date"))
			qty, rej = flt(entry.get("qty")), rejected if i == 0 else 0.0
			if qty or rej:
				planned.append((row, qty, rej, created_batches[key]))

	items = []
	for row, accepted, rejected, batch_no in planned:
		if any(r is row for r in items):
			row = frappe._dict(row.as_dict(no_default_fields=True))  # another batch of the same PO line
			row = pr.append("items", row)
		_set_row_quantities(row, accepted, rejected)
		if batch_no:
			attach_batch(row, batch_no)
		if flt(row.rejected_qty):
			line = wanted[row.purchase_order_item]
			row.rejected_warehouse = line.get("rejected_warehouse") or default_rejected_warehouse
			if not row.rejected_warehouse:
				frappe.throw(
					_(
						"Row {0}: {1} has a rejected quantity but no rejected warehouse. Set a default in Hasr Settings."
					).format(row.idx, row.item_code)
				)
		items.append(row)

	missing = set(wanted) - {row.purchase_order_item for row in items}
	if missing:
		names = ", ".join(
			frappe.db.get_value("Purchase Order Item", po_item, "item_code") or po_item for po_item in missing
		)
		frappe.throw(
			_("ERPNext considers these lines fully received already, so they cannot be added: {0}").format(names)
		)

	pr.set("items", items)
	for idx, row in enumerate(pr.items, start=1):
		row.idx = idx
	if supplier_delivery_note:
		pr.supplier_delivery_note = supplier_delivery_note
	if remarks:
		pr.remarks = remarks
	pr.insert()
	link_batches_to_voucher(list(created_batches.values()), pr.doctype, pr.name)
	return pr


def _set_row_quantities(row, accepted_stock_qty: float, rejected_stock_qty: float) -> None:
	"""Set accepted/rejected qty from stock-UOM numbers, in the PO line's UOM.

	VERIFIED on v15: Purchase Receipt validate_with_previous_doc requires the row UOM to equal the
	Purchase Order Item UOM, so the row cannot be switched to the stock UOM.
	"""
	cf = flt(row.conversion_factor) or 1.0
	qty, rejected = accepted_stock_qty / cf, rejected_stock_qty / cf
	if not (_is_whole(qty) and _is_whole(rejected)) and frappe.get_cached_value("UOM", row.uom, "must_be_whole_number"):
		frappe.throw(
			_(
				"{0}: {1} received and {2} rejected {3} is not a whole number of {4} (1 {4} = {5} {3}). "
				"Adjust the quantity, or change the unit on the purchase order."
			).format(
				row.item_code,
				frappe.format(accepted_stock_qty),
				frappe.format(rejected_stock_qty),
				row.stock_uom,
				row.uom,
				frappe.format(cf),
			),
			title=_("Not a whole number of {0}").format(row.uom),
		)

	row.qty = qty
	row.rejected_qty = rejected
	row.received_qty = qty + rejected
	row.stock_qty = accepted_stock_qty
	if row.meta.has_field("received_stock_qty"):
		row.received_stock_qty = accepted_stock_qty + rejected_stock_qty
	if row.meta.has_field("rejected_stock_qty"):
		row.rejected_stock_qty = rejected_stock_qty
	row.amount = flt(row.qty) * flt(row.rate)


def _is_whole(value: float) -> bool:
	return abs(value - round(value)) < 1e-9


def submit_purchase_receipt(name: str):
	pr = frappe.get_doc("Purchase Receipt", name)
	pr.submit()
	return pr


def get_purchase_receipt_docstatus(name: str) -> int | None:
	return frappe.db.get_value("Purchase Receipt", name, "docstatus")
