"""Invented test data (names follow the design mockups). Every helper is get-or-create."""

import frappe
from frappe.utils import add_days, nowdate

COUNTER = "hasr.counter@example.com"
COUNTER_2 = "hasr.counter2@example.com"
SUPERVISOR = "hasr.supervisor@example.com"

MILK_UNIT = "6281007030129"
MILK_CASE = "16281007030126"
YOGURT_UNIT = "6281100021457"
CHEESE_UNIT = "6281100098120"
BUTTER_UNIT = "6291003120045"
CREAM_UNIT = "6281007070444"
LABNEH_UNIT = "6281007091299"


def company():
	name = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all(
		"Company", pluck="name", limit=1
	)[0]
	return frappe.get_cached_doc("Company", name)


def warehouse(label):
	comp = company()
	name = f"{label} - {comp.abbr}"
	if not frappe.db.exists("Warehouse", name):
		parent = frappe.db.get_value("Warehouse", {"company": comp.name, "is_group": 1}, "name")
		frappe.get_doc(
			{"doctype": "Warehouse", "warehouse_name": label, "company": comp.name, "parent_warehouse": parent}
		).insert(ignore_permissions=True)
	return name


def supplier(name="Northfield Dairy Co."):
	if not frappe.db.exists("Supplier", name):
		group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
		frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group}).insert(
			ignore_permissions=True
		)
	return name


def uom(name, whole=1):
	if not frappe.db.exists("UOM", name):
		frappe.get_doc({"doctype": "UOM", "uom_name": name, "must_be_whole_number": whole}).insert(
			ignore_permissions=True
		)
	return name


def item(item_code, item_name, barcodes=(), uoms=(), allowance=0, **extra):
	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
		if doc.over_delivery_receipt_allowance != allowance:
			doc.over_delivery_receipt_allowance = allowance
			doc.save(ignore_permissions=True)
		return item_code
	group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_name,
			"item_group": group,
			"stock_uom": uom("Nos"),
			"is_stock_item": 1,
			"valuation_rate": 1,
			"over_delivery_receipt_allowance": allowance,
			"barcodes": [{"barcode": b, "uom": u} for b, u in barcodes],
			"uoms": [{"uom": uom(u), "conversion_factor": cf} for u, cf in uoms],
			**extra,
		}
	)
	doc.insert(ignore_permissions=True)
	return item_code


def setup_items():
	item("HASR-MILK", "Whole Milk 1 L", barcodes=[(MILK_UNIT, "Nos"), (MILK_CASE, "Box")], uoms=[("Box", 12)],
		 shelf_life_in_days=120, weight_per_unit=1.03, weight_uom=uom("Kg", 0), hasr_storage="Chilled",
		 description="<p>UHT full-fat cow's milk in a 1 L carton.</p>")
	item("HASR-YOGURT", "Greek Yogurt 500 g", barcodes=[(YOGURT_UNIT, "Nos")])
	item("HASR-CHEESE", "White Cheese 400 g", barcodes=[(CHEESE_UNIT, "Nos")], allowance=5)
	item("HASR-BUTTER", "Butter 200 g", barcodes=[(BUTTER_UNIT, "Nos")])
	# batch tracked: ERPNext names the batches from the item's series
	item("HASR-CREAM-B", "Fresh Cream 500 ml", barcodes=[(CREAM_UNIT, "Nos")], has_batch_no=1, has_expiry_date=1,
		 create_new_batch=1, batch_number_series="HASR-CR-.#####", shelf_life_in_days=30)
	# batch tracked without automatic batch numbers: hasr numbers them
	item("HASR-LABNEH-B", "Labneh 1 kg (batch)", barcodes=[(LABNEH_UNIT, "Nos")], has_batch_no=1, has_expiry_date=1,
		 create_new_batch=0, shelf_life_in_days=60)


def user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0].replace(".", " ").title(),
				"send_welcome_email": 0,
				"user_type": "System User",
			}
		).insert(ignore_permissions=True)
	doc = frappe.get_doc("User", email)
	missing = set(roles) - {r.role for r in doc.roles}
	if missing:
		doc.add_roles(*missing)
	return email


def setup_users():
	user(COUNTER, ["Hasr Counter"])
	user(COUNTER_2, ["Hasr Counter"])
	user(SUPERVISOR, ["Hasr Supervisor", "Stock User", "Stock Manager", "Purchase User"])


def setup_all():
	frappe.set_user("Administrator")
	setup_items()
	setup_users()
	warehouse("Hasr Main")
	warehouse("Hasr Second")
	warehouse("Hasr Rejected")
	supplier()
	frappe.db.set_single_value("Stock Settings", "over_delivery_receipt_allowance", 0)
	frappe.db.set_single_value("Hasr Settings", "default_rejected_warehouse", warehouse("Hasr Rejected"))
	frappe.clear_document_cache("Hasr Settings", "Hasr Settings")


def make_po(rows, wh=None, submit=True, supplier_name=None):
	"""rows: [(item_code, qty)] or [(item_code, qty, uom, conversion_factor)]."""
	frappe.set_user("Administrator")
	comp = company()
	wh = wh or warehouse("Hasr Main")
	items = []
	for row in rows:
		item_code, qty = row[0], row[1]
		uom_name = row[2] if len(row) > 2 else "Nos"
		cf = row[3] if len(row) > 3 else 1
		items.append(
			{
				"item_code": item_code,
				"qty": qty,
				"uom": uom_name,
				"conversion_factor": cf,
				"rate": 10,
				"warehouse": wh,
				"schedule_date": add_days(nowdate(), 1),
			}
		)
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": comp.name,
			"supplier": supplier(supplier_name or "Northfield Dairy Co."),
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 1),
			"set_warehouse": wh,
			"items": items,
		}
	)
	po.insert(ignore_permissions=True)
	if submit:
		po.submit()
	return po


def scan(session, barcode, uuid=None, qty=None, **extra):
	return {
		"client_uuid": uuid or frappe.generate_hash(length=20),
		"session": session,
		"session_type": "Receiving",
		"barcode": barcode,
		"qty": qty,
		"device_id": "test-device",
		**extra,
	}
