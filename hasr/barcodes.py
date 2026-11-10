"""What a scanned code is: an item barcode, an item code, or a GS1 code carrying a GTIN, batch and expiry."""

import frappe
from frappe.utils import cint

from hasr import erpnext_adapter as erp
from hasr import gs1


def gs1_enabled() -> bool:
	return bool(cint(frappe.get_cached_doc("Hasr Settings").gs1_enabled))


def resolve(code: str):
	"""erp.resolve_barcode, plus GS1: the GTIN in a GS1 code is looked up in every form it may be stored in.

	A GS1 result also carries `gs1_batch`, `expiry_date` and `production_date` when the code has them.
	"""
	code = (code or "").strip()
	resolved = erp.resolve_barcode(code)
	if resolved or not gs1_enabled():
		return resolved
	parsed = gs1.parse(code)
	if not parsed or not parsed.get("gtin"):
		return None
	for candidate in gs1.gtin_candidates(parsed["gtin"]):
		resolved = erp.resolve_barcode(candidate)
		if resolved and resolved.barcode:
			resolved.update(
				gs1=1,
				gs1_batch=parsed.get("batch"),
				expiry_date=parsed.get("expiry_date") or parsed.get("best_before"),
				production_date=parsed.get("production_date"),
			)
			return resolved
	return None
