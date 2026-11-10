"""What a stock count reads from ERPNext (balances, batches, usage) and the Stock Reconciliation it writes."""

import frappe
from frappe.utils import add_days, flt, nowdate


def item_group_with_children(item_group: str) -> list[str]:
	return [item_group, *frappe.db.get_descendants("Item Group", item_group)]


def stock_items(filters: dict | None = None) -> list[str]:
	return frappe.get_all("Item", filters={"is_stock_item": 1, "disabled": 0, **(filters or {})}, pluck="name")


def items_with_stock(warehouse: str) -> list[str]:
	"""Items with a balance (positive or negative) in the warehouse."""
	return frappe.get_all("Bin", filters={"warehouse": warehouse, "actual_qty": ["!=", 0]}, pluck="item_code")


def items_with_negative_stock(warehouse: str) -> list[str]:
	return frappe.get_all("Bin", filters={"warehouse": warehouse, "actual_qty": ["<", 0]}, pluck="item_code")


def get_balance(item_code: str, warehouse: str) -> float:
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def _batch_rows(item_code=None, warehouse=None, batch_no=None) -> list[dict]:
	"""Batch balances, expired and negative batches included: a count must see everything on the shelf.

	VERIFIED: v16's whitelisted get_batch_qty checks the user's Batch permission; hasr checks warehouse access
	itself, so it calls get_auto_batch_nos, which get_batch_qty uses on both v15 and v16.
	"""
	from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import get_auto_batch_nos

	return get_auto_batch_nos(
		frappe._dict(
			item_code=item_code,
			warehouse=warehouse,
			batch_no=batch_no,
			based_on=frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on"),
			for_stock_levels=True,
			consider_negative_batches=True,
		)
	) or []


def get_batch_balances(item_code: str, warehouse: str) -> dict[str, float]:
	"""Balance per batch of an item in a warehouse (batches with a balance only)."""
	out = {}
	for r in _batch_rows(item_code=item_code, warehouse=warehouse):
		if flt(r.get("qty")) and r.get("warehouse", warehouse) == warehouse:
			out[r["batch_no"]] = out.get(r["batch_no"], 0.0) + flt(r["qty"])
	return out


def get_batch_balance(batch_no: str, warehouse: str) -> float:
	item_code = frappe.db.get_value("Batch", batch_no, "item")
	return get_batch_balances(item_code, warehouse).get(batch_no, 0.0) if item_code else 0.0


def valuation_rate(item_code: str, warehouse: str) -> float:
	rate = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate"))
	return rate or flt(frappe.get_cached_value("Item", item_code, "valuation_rate"))


def item_batches(item_codes: list[str]) -> dict[str, list[dict]]:
	"""Batches a counter may pick, per item: enabled, newest expiry first."""
	out = {}
	if not item_codes:
		return out
	filters = {"item": ["in", item_codes]}
	if frappe.get_meta("Batch").has_field("disabled"):
		filters["disabled"] = 0
	for b in frappe.get_all(
		"Batch", filters=filters, fields=["name", "item", "expiry_date"], order_by="expiry_date desc, creation desc"
	):
		out.setdefault(b.item, []).append({"batch_no": b.name, "expiry_date": b.expiry_date})
	return out


def find_batch(item_code: str, batch_id: str) -> str | None:
	"""A batch of the item by its number, as printed on the pack (GS1 lot)."""
	return frappe.db.get_value("Batch", {"item": item_code, "name": batch_id}) or frappe.db.get_value(
		"Batch", {"item": item_code, "batch_id": batch_id}
	)


def annual_usage_value(warehouse: str) -> dict[str, float]:
	"""Value of what left the warehouse per item in the last 365 days (ABC classification)."""
	rows = frappe.db.sql(
		"""
		select item_code, sum(abs(actual_qty) * valuation_rate) as value
		from `tabStock Ledger Entry`
		where warehouse = %s and actual_qty < 0 and is_cancelled = 0 and posting_date >= %s
		group by item_code
		""",
		(warehouse, add_days(nowdate(), -365)),
		as_dict=True,
	)
	return {r.item_code: flt(r.value) for r in rows}


def stock_warehouses() -> list[str]:
	return frappe.get_all("Warehouse", filters={"is_group": 0, "disabled": 0}, pluck="name")


def create_stock_reconciliation(company: str, warehouse: str, rows: list[dict], remarks: str):
	"""A draft Stock Reconciliation posted now. rows: [{item_code, batch_no, qty, valuation_rate}].

	VERIFIED on v15 and v16: with use_serial_batch_fields = 1 and batch_no, ERPNext builds the Serial and Batch
	Bundle for the batch row on submit, like it does for Purchase Receipts.
	"""
	sr = frappe.new_doc("Stock Reconciliation")
	sr.purpose = "Stock Reconciliation"
	sr.company = company
	sr.remarks = remarks
	for r in rows:
		row = {
			"item_code": r["item_code"],
			"warehouse": warehouse,
			"qty": r["qty"],
			"valuation_rate": r.get("valuation_rate") or None,
		}
		if r.get("batch_no"):
			row.update(batch_no=r["batch_no"], use_serial_batch_fields=1)
		sr.append("items", row)
	sr.flags.ignore_permissions = True
	sr.insert()
	return sr


def submit_stock_reconciliation(name: str):
	sr = frappe.get_doc("Stock Reconciliation", name)
	sr.flags.ignore_permissions = True
	sr.submit()
	return sr
