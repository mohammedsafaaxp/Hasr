"""Batches in ERPNext: creation on approval and attaching them to Purchase Receipt rows."""

import frappe
from frappe import _
from frappe.model.naming import make_autoname

# Used when the item does not create its own batch numbers (Item.create_new_batch is off).
FALLBACK_BATCH_SERIES = "BT-.YYYY.-.#####"


def get_batch_settings(item_code: str) -> dict:
	return frappe.get_cached_value(
		"Item",
		item_code,
		["has_batch_no", "has_expiry_date", "create_new_batch", "shelf_life_in_days"],
		as_dict=True,
	) or frappe._dict()


def create_batch(item_code: str, expiry_date: str, manufacturing_date: str | None = None) -> str:
	"""Create one Batch for an expiry date and return its name.

	The name comes from the item's own batch series when Item.create_new_batch is set (ERPNext names it);
	otherwise hasr gives it a number from FALLBACK_BATCH_SERIES, because ERPNext then requires a Batch ID.
	"""
	settings = get_batch_settings(item_code)
	if not settings.has_batch_no:
		frappe.throw(_("Item {0} is not batch tracked.").format(item_code))

	batch = frappe.get_doc(
		{
			"doctype": "Batch",
			"item": item_code,
			"expiry_date": expiry_date,
			"manufacturing_date": manufacturing_date,
		}
	)
	if not settings.create_new_batch:
		batch.batch_id = make_autoname(FALLBACK_BATCH_SERIES, "Batch")
	batch.flags.ignore_permissions = True
	batch.insert()
	return batch.name


def attach_batch(row, batch_no: str) -> None:
	"""Put a batch on a Purchase Receipt row.

	VERIFIED on v15 and v16: with use_serial_batch_fields = 1 and batch_no set, ERPNext builds the Serial and
	Batch Bundle on submit (make_bundle_using_old_serial_batch_fields), for both accepted and rejected qty.
	"""
	if row.meta.has_field("use_serial_batch_fields"):
		row.use_serial_batch_fields = 1
	row.batch_no = batch_no


def link_batches_to_voucher(batch_names: list[str], voucher_type: str, voucher_no: str) -> None:
	for name in batch_names:
		frappe.db.set_value("Batch", name, {"reference_doctype": voucher_type, "reference_name": voucher_no})
