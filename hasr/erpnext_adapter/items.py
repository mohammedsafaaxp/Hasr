"""Items, barcodes and units of measure from ERPNext."""

import frappe
from frappe import _
from frappe.utils import flt, strip_html_tags

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")


def get_conversion_factor(item_code: str, uom: str | None) -> float:
	"""Conversion factor from `uom` to the item's stock UOM (item row first, then ERPNext's resolver)."""
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	if not uom or uom == stock_uom:
		return 1.0
	cf = frappe.db.get_value(
		"UOM Conversion Detail", {"parent": item_code, "parenttype": "Item", "uom": uom}, "conversion_factor"
	)
	if not cf:
		from erpnext.stock.get_item_details import get_conversion_factor as erpnext_cf

		cf = (erpnext_cf(item_code, uom) or {}).get("conversion_factor")
	return flt(cf)


def resolve_barcode(code: str) -> dict | None:
	"""Barcode (or exact item code) → item, UOM and conversion factor to stock UOM. None when unknown."""
	code = (code or "").strip()
	if not code:
		return None

	item_code, uom, barcode = None, None, None
	row = frappe.db.get_value("Item Barcode", {"barcode": code, "parenttype": "Item"}, ["parent", "uom"], as_dict=True)
	if row:
		item_code, uom, barcode = row.parent, row.uom, code
	elif frappe.db.exists("Item", code):
		# typed item code: counts in stock UOM
		item_code = code
	else:
		return None

	item = frappe.get_cached_value(
		"Item", item_code, ["item_name", "stock_uom", "disabled", "has_batch_no", "is_stock_item"], as_dict=True
	)
	uom = uom or item.stock_uom
	return frappe._dict(
		item_code=item_code,
		item_name=item.item_name,
		barcode=barcode,
		uom=uom,
		stock_uom=item.stock_uom,
		conversion_factor=get_conversion_factor(item_code, uom),
		has_batch_no=item.has_batch_no,
		disabled=item.disabled,
	)


def add_item_barcode(item_code: str, barcode: str, uom: str | None = None) -> None:
	"""Attach a barcode to an item. ERPNext keeps Item Barcode.barcode unique (VERIFIED on v15)."""
	owner = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
	if owner == item_code:
		return
	if owner:
		frappe.throw(_("Barcode {0} already belongs to item {1}.").format(barcode, owner))
	item = frappe.get_doc("Item", item_code)
	item.append("barcodes", {"barcode": barcode, "uom": uom or None})
	item.flags.ignore_permissions = True
	item.save()


def get_item_details(item_code: str) -> dict:
	"""Everything the phone shows about an item. Never includes stock balances or valuation."""
	fields = [
		"name",
		"item_name",
		"description",
		"image",
		"item_group",
		"brand",
		"stock_uom",
		"has_batch_no",
		"has_expiry_date",
		"shelf_life_in_days",
		"weight_per_unit",
		"weight_uom",
		"disabled",
	]
	meta = frappe.get_meta("Item")
	if meta.has_field("hasr_storage"):
		fields.append("hasr_storage")
	item = frappe.db.get_value("Item", item_code, fields, as_dict=True)
	if not item:
		frappe.throw(_("Item {0} not found.").format(item_code), frappe.DoesNotExistError)

	uoms = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "parenttype": "Item"},
		fields=["uom", "conversion_factor"],
		order_by="idx asc",
	)
	barcodes = frappe.get_all(
		"Item Barcode",
		filters={"parent": item_code, "parenttype": "Item"},
		fields=["barcode", "uom", "barcode_type"],
		order_by="idx asc",
	)

	images = [item.image] if item.image else []
	for url in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Item", "attached_to_name": item_code, "is_folder": 0},
		pluck="file_url",
		order_by="creation asc",
	):
		if url and url.lower().endswith(IMAGE_EXTENSIONS) and url not in images:
			images.append(url)

	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"description": strip_html_tags(item.description or "").strip(),
		"image": item.image,
		"images": images,
		"item_group": item.item_group,
		"item_group_path": _item_group_path(item.item_group),
		"brand": item.brand,
		"stock_uom": item.stock_uom,
		"uoms": uoms,
		"barcodes": barcodes,
		"has_batch_no": item.has_batch_no,
		"has_expiry_date": item.has_expiry_date,
		"shelf_life_in_days": item.shelf_life_in_days,
		"weight_per_unit": item.weight_per_unit,
		"weight_uom": item.weight_uom,
		"hasr_storage": item.get("hasr_storage"),
		"disabled": item.disabled,
		"last_receipt": _last_receipt(item_code),
	}


def _item_group_path(item_group: str | None) -> list[str]:
	path = []
	while item_group and len(path) < 6:
		parent = frappe.get_cached_value("Item Group", item_group, "parent_item_group")
		if not parent:  # the root ("All Item Groups") is not shown
			break
		path.insert(0, item_group)
		item_group = parent
	return path


def _last_receipt(item_code: str) -> dict | None:
	rows = frappe.db.sql(
		"""
		select pr.name, pr.posting_date, sum(pri.stock_qty) as stock_qty
		from `tabPurchase Receipt Item` pri
		join `tabPurchase Receipt` pr on pr.name = pri.parent
		where pri.item_code = %s and pr.docstatus = 1 and pr.is_return = 0
		group by pr.name, pr.posting_date, pr.posting_time
		order by pr.posting_date desc, pr.posting_time desc
		limit 1
		""",
		item_code,
		as_dict=True,
	)
	return rows[0] if rows else None
