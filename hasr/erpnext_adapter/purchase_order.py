"""Read purchase orders and their lines from ERPNext."""

import frappe
from frappe.utils import flt

from hasr.erpnext_adapter.stock import get_over_receipt_allowance

# Purchase Order statuses that can no longer be received against
NOT_RECEIVABLE_STATUSES = ("Closed", "Completed", "On Hold", "Delivered", "Cancelled")


def is_receivable(purchase_order: str) -> bool:
	po = frappe.db.get_value("Purchase Order", purchase_order, ["docstatus", "status", "per_received"], as_dict=True)
	return bool(
		po and po.docstatus == 1 and po.status not in NOT_RECEIVABLE_STATUSES and flt(po.per_received) < 100
	)


def get_purchase_order(purchase_order: str) -> dict | None:
	return frappe.db.get_value(
		"Purchase Order",
		purchase_order,
		[
			"name",
			"supplier",
			"supplier_name",
			"company",
			"set_warehouse",
			"schedule_date",
			"transaction_date",
			"status",
			"docstatus",
			"per_received",
		],
		as_dict=True,
	)


def get_purchase_order_warehouses(purchase_order: str) -> list[str]:
	return frappe.get_all(
		"Purchase Order Item", filters={"parent": purchase_order}, pluck="warehouse", distinct=True
	)


def get_open_purchase_orders(
	warehouses: list[str] | None = None,
	warehouse: str | None = None,
	search: str | None = None,
	limit: int = 100,
) -> list[dict]:
	"""Submitted purchase orders that still expect goods.

	`warehouses` restricts to orders with at least one line in those warehouses (None = no restriction);
	`warehouse` is the screen's warehouse picker.
	"""
	filters = [
		["docstatus", "=", 1],
		["status", "not in", NOT_RECEIVABLE_STATUSES],
		["per_received", "<", 100],
	]

	for allowed in (warehouses, [warehouse] if warehouse else None):
		if allowed is None:
			continue
		names = frappe.get_all(
			"Purchase Order Item",
			filters={"warehouse": ["in", list(allowed) or [""]], "docstatus": 1},
			pluck="parent",
			distinct=True,
		)
		filters.append(["name", "in", names or [""]])

	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = [["name", "like", like], ["supplier", "like", like], ["supplier_name", "like", like]]

	orders = frappe.get_all(
		"Purchase Order",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"company",
			"set_warehouse",
			"schedule_date",
			"transaction_date",
			"status",
			"per_received",
		],
		order_by="schedule_date asc, name asc",
		limit=limit,
	)
	if not orders:
		return []

	rows = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": ["in", [o.name for o in orders]]},
		fields=["parent", "qty", "received_qty", "delivered_by_supplier"],
	)
	counts = {}
	for row in rows:
		if row.delivered_by_supplier:
			continue
		c = counts.setdefault(row.parent, {"item_count": 0, "items_received": 0})
		c["item_count"] += 1
		if flt(row.received_qty) >= flt(row.qty):
			c["items_received"] += 1

	for order in orders:
		order.update(counts.get(order.name, {"item_count": 0, "items_received": 0}))
	return orders


def get_po_lines_with_remaining(purchase_order: str) -> list[dict]:
	"""Purchase order lines in stock UOM with what ERPNext still expects.

	VERIFIED on v15: Purchase Order Item.received_qty is kept in the PO line's UOM and includes rejected
	quantity (status updater: Σ PR received_qty × PR cf / PO cf), so received in stock UOM is
	received_qty × conversion_factor.
	"""
	rows = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": purchase_order},
		fields=[
			"name",
			"idx",
			"item_code",
			"item_name",
			"qty",
			"stock_qty",
			"uom",
			"stock_uom",
			"conversion_factor",
			"received_qty",
			"warehouse",
			"delivered_by_supplier",
			*(["rejected_warehouse"] if _po_item_has_rejected_warehouse() else []),
		],
		order_by="idx asc",
	)
	lines = []
	for row in rows:
		if row.delivered_by_supplier:
			continue
		cf = flt(row.conversion_factor) or 1.0
		ordered = flt(row.stock_qty) or flt(row.qty) * cf
		received = flt(row.received_qty) * cf
		allowance = get_over_receipt_allowance(row.item_code)
		lines.append(
			frappe._dict(
				po_item=row.name,
				idx=row.idx,
				item_code=row.item_code,
				item_name=row.item_name,
				uom=row.uom,
				stock_uom=row.stock_uom,
				conversion_factor=cf,
				warehouse=row.warehouse,
				rejected_warehouse=row.get("rejected_warehouse"),
				ordered_qty=ordered,
				received_qty=received,
				remaining_qty=max(ordered - received, 0.0),
				allowance_pct=allowance,
				allowed_qty=ordered * (1 + allowance / 100.0),
			)
		)
	return lines


def _po_item_has_rejected_warehouse() -> bool:
	# VERIFIED: Purchase Order Item has no rejected_warehouse on v15; keep the code ready if a version adds it.
	return frappe.get_meta("Purchase Order Item").has_field("rejected_warehouse")


def suggested_purchase_rate(purchase_order: str, item_code: str) -> float:
	"""Rate per stock unit for a new row: the supplier's price in the order's buying price list, else the
	price list's general price, else the item's last purchase rate, else 0 (the supervisor can type one)."""
	po = frappe.db.get_value("Purchase Order", purchase_order, ["buying_price_list", "supplier"], as_dict=True) or {}
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if po.get("buying_price_list"):
		prices = frappe.get_all(
			"Item Price",
			filters={"item_code": item_code, "price_list": po["buying_price_list"], "uom": ["in", [stock_uom, "", None]]},
			fields=["price_list_rate", "supplier"],
		)
		for price in sorted(prices, key=lambda p: p.supplier != po.get("supplier")):
			if not price.supplier or price.supplier == po.get("supplier"):
				return flt(price.price_list_rate)
	return flt(frappe.db.get_value("Item", item_code, "last_purchase_rate"))


def add_item_to_purchase_order(purchase_order: str, item_code: str, qty: float, rate: float, warehouse: str) -> str:
	"""Add a row (in the stock unit) to a submitted purchase order with ERPNext's own "Update Items".

	It runs as the current user, so ERPNext checks their right to change the order. Update Items
	deletes rows that are not passed, so every existing row goes back unchanged. Returns the new row name.
	VERIFIED on v15 and v16: erpnext.controllers.accounts_controller.update_child_qty_rate.
	"""
	from erpnext.controllers.accounts_controller import update_child_qty_rate

	po = frappe.get_doc("Purchase Order", purchase_order)
	before = {row.name for row in po.items}
	trans_items = [
		{
			"docname": row.name,
			"idx": row.idx,
			"item_code": row.item_code,
			"qty": row.qty,
			"rate": row.rate,
			"uom": row.uom,
			"conversion_factor": row.conversion_factor,
			"schedule_date": str(row.schedule_date),
			"warehouse": row.warehouse,
		}
		for row in po.items
	]
	trans_items.append(
		{
			"idx": len(trans_items) + 1,
			"item_code": item_code,
			"qty": flt(qty),
			"rate": flt(rate),
			"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
			"conversion_factor": 1,
			"schedule_date": str(po.schedule_date or frappe.utils.nowdate()),
			"warehouse": warehouse,
		}
	)
	update_child_qty_rate("Purchase Order", frappe.as_json(trans_items), purchase_order)
	added = [
		name for name in frappe.get_all("Purchase Order Item", filters={"parent": purchase_order}, pluck="name") if name not in before
	]
	if not added:
		frappe.throw(frappe._("Could not add {0} to purchase order {1}.").format(item_code, purchase_order))
	return added[0]
