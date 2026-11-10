"""Stock freeze during a count: stock movements of frozen items in that warehouse are refused.

Runs on every Stock Ledger Entry, so the active freezes are cached and the common case (nothing frozen) costs
one cache read.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

CACHE_KEY = "hasr_active_freezes"


def active_freezes() -> dict:
	"""{(warehouse, item_code or ""): count_session}"""
	cached = frappe.cache.get_value(CACHE_KEY)
	if cached is None:
		if not frappe.db.table_exists("Hasr Stock Freeze"):
			return {}  # installing or upgrading: ERPNext patches can move stock before hasr's tables exist
		rows = frappe.get_all(
			"Hasr Stock Freeze", filters={"active": 1}, fields=["warehouse", "item_code", "count_session"]
		)
		cached = [[f.warehouse, f.item_code or "", f.count_session] for f in rows]
		frappe.cache.set_value(CACHE_KEY, cached)
	return {(w, i): s for w, i, s in cached}


def clear_cache():
	frappe.cache.delete_value(CACHE_KEY)


def validate_sle(doc, method=None):
	freezes = active_freezes()
	if not freezes:
		return
	session = freezes.get((doc.warehouse, doc.item_code)) or freezes.get((doc.warehouse, ""))
	if not session:
		return
	if doc.voucher_type == "Stock Reconciliation" and (
		frappe.db.get_value("Hasr Count Session", session, "stock_reconciliation") == doc.voucher_no
	):
		return  # the count's own reconciliation
	frappe.throw(
		_("{0} is frozen in {1} for stock count {2}. Wait until the count is approved.").format(
			doc.item_code, doc.warehouse, session
		),
		title=_("Stock frozen for a count"),
	)


def release_expired_freezes():
	"""Hourly: a forgotten count never blocks the warehouse longer than Hasr Settings allows."""
	expired = frappe.get_all(
		"Hasr Stock Freeze", filters={"active": 1, "expires_at": ["<", now_datetime()]}, pluck="name"
	)
	for name in expired:
		frappe.db.set_value("Hasr Stock Freeze", name, {"active": 0, "released_at": now_datetime(), "released_by": "Administrator"})
	if expired:
		clear_cache()
	return len(expired)
