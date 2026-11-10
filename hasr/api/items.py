import frappe
from frappe import _

from hasr import barcodes
from hasr import erpnext_adapter as erp
from hasr.permissions import require_counter


@frappe.whitelist()
def resolve_barcode(code):
	"""Barcode → item, UOM and conversion to stock UOM (and GS1 batch and expiry), or {"found": false}."""
	require_counter()
	resolved = barcodes.resolve(code)
	if not resolved:
		return {"found": False, "barcode": code}
	return {"found": True, **resolved}


@frappe.whitelist()
def get_item_details(item_code):
	"""Item card for the phone. Deliberately has no stock balance or valuation fields."""
	require_counter()
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found.").format(item_code), frappe.DoesNotExistError)
	return erp.get_item_details(item_code)
