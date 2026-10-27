"""Create Purchase Receipts in ERPNext. hasr only ever inserts drafts here; submit is a separate call."""

import frappe
from frappe import _
from frappe.utils import flt


def create_draft_purchase_receipt(
	purchase_order: str,
	lines: list[dict],
	supplier_delivery_note: str | None = None,
	default_rejected_warehouse: str | None = None,
	remarks: str | None = None,
):
	"""Insert a draft Purchase Receipt for `lines` of `purchase_order`.

	Each line: {"po_item", "qty", "rejected_qty", "rejected_warehouse"?} with quantities in stock UOM.
	Returns the inserted (docstatus 0) Purchase Receipt.
	"""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	wanted = {
		line["po_item"]: line for line in lines if flt(line.get("qty")) > 0 or flt(line.get("rejected_qty")) > 0
	}
	if not wanted:
		frappe.throw(_("Nothing was received in this session."))

	pr = make_purchase_receipt(purchase_order, args={"filtered_children": list(wanted)})

	items = []
	for row in pr.items:
		line = wanted.get(row.purchase_order_item)
		if not line:
			continue
		_set_row_quantities(row, flt(line.get("qty")), flt(line.get("rejected_qty")))
		if flt(row.rejected_qty):
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
