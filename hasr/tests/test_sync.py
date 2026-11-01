import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


class TestSync(HasrTestCase, FrappeTestCase):
	def setUp(self):
		self.po = fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 36)])
		frappe.set_user(fx.COUNTER)
		self.session = api.start_session(self.po.name)["name"]

	def received(self, item_code):
		lines = api.get_session(self.session)["lines"]
		return next(l["received_qty"] for l in lines if l["item_code"] == item_code)

	def test_unit_and_case_scan(self):
		out = sync.push_scans([fx.scan(self.session, fx.MILK_UNIT)])
		self.assertEqual(out["results"][0]["status"], "applied")
		self.assertEqual(self.received("HASR-MILK"), 1)
		out = sync.push_scans([fx.scan(self.session, fx.MILK_CASE)])
		r = out["results"][0]
		self.assertEqual((r["status"], r["uom"], r["conversion_factor"], r["qty_stock_uom"]), ("applied", "Box", 12, 12))
		self.assertEqual(self.received("HASR-MILK"), 13)
		sync.push_scans([fx.scan(self.session, fx.MILK_CASE, qty=2)])
		self.assertEqual(self.received("HASR-MILK"), 37)

	def test_idempotent_push(self):
		scan = fx.scan(self.session, fx.MILK_CASE, uuid="7f1c2a9e-0b7d-4c55-9d1e-3f2b6a8c9d10")
		first = sync.push_scans([scan])
		second = sync.push_scans([scan, scan])
		self.assertEqual(first["results"][0]["status"], "applied")
		self.assertEqual([r["status"] for r in second["results"]], ["duplicate", "duplicate"])
		self.assertEqual(self.received("HASR-MILK"), 12)
		self.assertEqual(frappe.db.count("Hasr Scan", {"client_uuid": scan["client_uuid"]}), 1)

	def test_same_uuid_in_one_batch(self):
		scan = fx.scan(self.session, fx.YOGURT_UNIT)
		out = sync.push_scans([scan, scan])
		self.assertEqual([r["status"] for r in out["results"]], ["applied", "duplicate"])
		self.assertEqual(self.received("HASR-YOGURT"), 1)

	def test_unknown_barcode_rejected_and_logged(self):
		out = sync.push_scans([fx.scan(self.session, "6287001234569", uuid="unknown-scan-0001")])
		r = out["results"][0]
		self.assertEqual((r["status"], r["code"]), ("rejected", "unknown_barcode"))
		self.assertFalse(frappe.db.exists("Item Barcode", {"barcode": "6287001234569"}))
		self.assertEqual(frappe.db.get_value("Hasr Scan", {"client_uuid": "unknown-scan-0001"}, "status"), "Rejected")
		replay = sync.push_scans([fx.scan(self.session, "6287001234569", uuid="unknown-scan-0001")])
		self.assertEqual(replay["results"][0]["status"], "duplicate")

	def test_counter_cannot_create_item(self):
		self.assertFalse(frappe.has_permission("Item", "create", user=fx.COUNTER))
		self.assertRaises(
			frappe.PermissionError,
			frappe.get_doc({"doctype": "Item", "item_code": "HASR-PHONE-MADE", "item_group": "All Item Groups", "stock_uom": "Nos"}).insert,
		)

	def test_item_not_on_po_becomes_exception(self):
		out = sync.push_scans([fx.scan(self.session, fx.BUTTER_UNIT), fx.scan(self.session, fx.BUTTER_UNIT, qty=2)])
		r = out["results"][0]
		self.assertEqual((r["status"], r["code"]), ("exception", "not_on_po"))
		self.assertIn("Not on purchase order", r["message"])
		self.assertEqual(sum(l["received_qty"] for l in out["lines"]), 0, "not counted on any line")
		exceptions = [u for u in api.get_session(self.session)["unknown_barcodes"] if u["kind"] == "Not on order"]
		self.assertEqual(len(exceptions), 1, "repeated scans add to one exception")
		self.assertEqual((exceptions[0]["item_code"], exceptions[0]["qty"]), ("HASR-BUTTER", 3))

	def test_not_on_order_blocks_approval_until_returned(self):
		sync.push_scans([fx.scan(self.session, fx.YOGURT_UNIT), fx.scan(self.session, fx.BUTTER_UNIT)])
		api.finish_session(self.session)
		frappe.set_user(fx.SUPERVISOR)
		self.assertRaisesRegex(frappe.ValidationError, "not on the order", api.approve, self.session)
		exception = next(u for u in api.get_session(self.session)["unknown_barcodes"] if u["kind"] == "Not on order")
		self.assertRaisesRegex(frappe.ValidationError, "Return it to the supplier", api.link_unknown_barcode, exception["name"], "HASR-YOGURT")
		api.dismiss_unknown_barcode(exception["name"])
		self.assertEqual(api.approve(self.session)["status"], "Approved")

	def test_undo(self):
		scan = fx.scan(self.session, fx.MILK_CASE)
		sync.push_scans([scan])
		undo = fx.scan(self.session, None, undo_of=scan["client_uuid"])
		out = sync.push_scans([undo, undo])
		self.assertEqual([r["status"] for r in out["results"]], ["applied", "duplicate"])
		self.assertEqual(self.received("HASR-MILK"), 0)
		self.assertEqual(frappe.db.get_value("Hasr Scan", {"client_uuid": scan["client_uuid"]}, "undone"), 1)
		again = sync.push_scans([fx.scan(self.session, None, undo_of=scan["client_uuid"])])
		self.assertEqual(again["results"][0]["code"], "nothing_to_undo")

	def test_scans_refused_once_pending(self):
		sync.push_scans([fx.scan(self.session, fx.YOGURT_UNIT)])
		api.finish_session(self.session)
		out = sync.push_scans([fx.scan(self.session, fx.YOGURT_UNIT)])
		self.assertEqual(out["results"][0]["status"], "rejected")
		self.assertEqual(self.received("HASR-YOGURT"), 1)

	def test_invalid_uuid(self):
		out = sync.push_scans([fx.scan(self.session, fx.YOGURT_UNIT, uuid="x")])
		self.assertEqual(out["results"][0]["code"], "invalid")

	def test_scans_accepts_json_string(self):
		out = sync.push_scans(frappe.as_json([fx.scan(self.session, fx.YOGURT_UNIT)]))
		self.assertEqual(out["results"][0]["status"], "applied")


class TestTypedItems(HasrTestCase, FrappeTestCase):
	def setUp(self):
		self.po = fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 10)])
		frappe.set_user(fx.COUNTER)
		self.session = api.start_session(self.po.name)["name"]

	def received(self, item_code):
		return next(l["received_qty"] for l in api.get_session(self.session)["lines"] if l["item_code"] == item_code)

	def test_typed_item_code_with_unit(self):
		out = sync.push_scans([fx.scan(self.session, None, item_code="HASR-MILK", uom="Box", qty=2)])
		r = out["results"][0]
		self.assertEqual((r["status"], r["uom"], r["qty_stock_uom"]), ("applied", "Box", 24))
		sync.push_scans([fx.scan(self.session, None, item_code="HASR-MILK", qty=3)])  # no unit: stock unit
		self.assertEqual(self.received("HASR-MILK"), 27)

	def test_scan_with_quantity(self):
		sync.push_scans([fx.scan(self.session, fx.MILK_CASE, qty=3)])  # scanned once, 3 boxes typed
		self.assertEqual(self.received("HASR-MILK"), 36)

	def test_item_code_in_barcode_field_asks_for_unit(self):
		r = sync.push_scans([fx.scan(self.session, "HASR-YOGURT")])["results"][0]
		self.assertEqual((r["status"], r["code"]), ("rejected", "use_item_entry"))
		self.assertEqual(self.received("HASR-YOGURT"), 0)

	def test_typed_unknown_item_and_bad_unit(self):
		r = sync.push_scans([fx.scan(self.session, None, item_code="NO-SUCH-ITEM")])["results"][0]
		self.assertEqual(r["code"], "unknown_item")
		r = sync.push_scans([fx.scan(self.session, None, item_code="HASR-YOGURT", uom="Box")])["results"][0]
		self.assertEqual(r["status"], "rejected")
