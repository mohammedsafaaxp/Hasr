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

	def test_item_not_on_po_rejected(self):
		out = sync.push_scans([fx.scan(self.session, fx.BUTTER_UNIT)])
		r = out["results"][0]
		self.assertEqual((r["status"], r["code"]), ("rejected", "not_on_po"))
		self.assertIn("is not on purchase order", r["message"])
		self.assertEqual(out["lines"] and sum(l["received_qty"] for l in out["lines"]), 0)

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
