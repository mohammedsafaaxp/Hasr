"""Stock rules read from ERPNext: over-receipt allowance."""

import frappe
from frappe.utils import flt


def get_over_receipt_allowance(item_code: str) -> float:
	"""Item-level allowance if set, else the Stock Settings default (both in percent)."""
	allowance = flt(frappe.get_cached_value("Item", item_code, "over_delivery_receipt_allowance"))
	if not allowance:
		allowance = flt(frappe.db.get_single_value("Stock Settings", "over_delivery_receipt_allowance"))
	return allowance


def get_over_receipt_limit(item_code: str, ordered_qty: float) -> float:
	"""Maximum quantity ERPNext accepts against an ordered quantity (same unit as ordered_qty)."""
	return flt(ordered_qty) * (1 + get_over_receipt_allowance(item_code) / 100.0)


def get_warehouses(allowed: set[str] | None = None) -> list[dict]:
	"""Leaf, enabled warehouses (optionally limited to `allowed`)."""
	filters = {"is_group": 0, "disabled": 0}
	if allowed is not None:
		filters["name"] = ["in", sorted(allowed) or [""]]
	return frappe.get_all(
		"Warehouse", filters=filters, fields=["name", "warehouse_name", "company"], order_by="warehouse_name asc"
	)
