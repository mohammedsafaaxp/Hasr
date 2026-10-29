import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def line_of(payload, item_code):
	return next(l for l in payload["lines"] if l["item_code"] == item_code)


class TestItemMismatch(HasrTestCase, FrappeTestCase):
	def setUp(self):
		self.po = fx.make_po([("HASR-YOGURT", 10), ("HASR-CHEESE", 5)])
		frappe.set_user(fx.COUNTER)
		self.s = api.start_session(self.po.name)
		self.yogurt = line_of(self.s, "HASR-YOGURT")["po_item"]
		sync.push_scans([fx.scan(self.s["name"], fx.YOGURT_UNIT, qty=10)])

	def report(self, qty=4, uuid=None):
		return api.report_mismatch(
			self.s["name"], self.yogurt, qty, PNG, "Cup says 400 g, not 500 g", fx.YOGURT_UNIT, uuid
		)

	def test_report_needs_photo_and_is_idempotent(self):
		self.assertRaises(frappe.ValidationError, api.report_mismatch, self.s["name"], self.yogurt, 4, None)
		out = self.report(uuid="mismatch-uuid-0001")
		self.report(uuid="mismatch-uuid-0001")
		self.assertEqual(len(out["mismatches"]), 1)
		m = out["mismatches"][0]
		self.assertEqual((m["status"], m["qty"], m["item_code"]), ("Open", 4, "HASR-YOGURT"))
		self.assertTrue(m["photo"])
		self.assertTrue(line_of(out, "HASR-YOGURT")["mismatch_open"])

	def test_open_report_blocks_approval_counter_cannot_decide(self):
		out = self.report()
		api.finish_session(self.s["name"])  # the worker can still send it; the supervisor decides
		name = out["mismatches"][0]["name"]
		frappe.set_user(fx.COUNTER)
		self.assertRaises(frappe.PermissionError, api.decide_mismatch, name, "Correct")
		frappe.set_user(fx.SUPERVISOR)
		self.assertRaisesRegex(frappe.ValidationError, "item mismatches", api.approve, self.s["name"])

	def test_correct_item_keeps_quantity(self):
		name = self.report()["mismatches"][0]["name"]
		api.finish_session(self.s["name"])
		frappe.set_user(fx.SUPERVISOR)
		out = api.decide_mismatch(name, "Correct")
		self.assertEqual(line_of(out, "HASR-YOGURT")["received_qty"], 10)
		self.assertRaises(frappe.ValidationError, api.decide_mismatch, name, "Wrong")  # decided once
		self.assertEqual(api.approve(self.s["name"])["status"], "Approved")

	def test_wrong_item_removes_quantity_and_photo_goes_to_receipt_and_invoice(self):
		name = self.report(qty=4)["mismatches"][0]["name"]
		api.attach_invoice(self.s["name"], PNG)
		api.finish_session(self.s["name"])
		frappe.set_user(fx.SUPERVISOR)
		out = api.decide_mismatch(name, "Wrong")
		self.assertEqual(line_of(out, "HASR-YOGURT")["received_qty"], 6)
		out = api.approve(self.s["name"], submit=1)
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual(pr.items[0].qty, 6)

		on_pr = frappe.get_all("File", filters={"attached_to_doctype": "Purchase Receipt", "attached_to_name": pr.name}, pluck="file_name")
		self.assertTrue(any(f.startswith("supplier-invoice-") for f in on_pr), on_pr)
		self.assertTrue(any(f.startswith("mismatch-") for f in on_pr), on_pr)

		# billing the receipt brings the same files to the Purchase Invoice
		frappe.set_user("Administrator")
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice  # setup only

		pi = make_purchase_invoice(pr.name)
		pi.insert()
		on_pi = frappe.get_all("File", filters={"attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name}, pluck="file_name")
		self.assertEqual(sorted(on_pi), sorted(on_pr))
		pi.save()  # saving again does not duplicate
		self.assertEqual(
			frappe.db.count("File", {"attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name}), len(on_pr)
		)

	def test_invoice_without_hasr_receipt_untouched(self):
		frappe.set_user("Administrator")
		po = fx.make_po([("HASR-BUTTER", 2)])
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice  # setup only

		pi = make_purchase_invoice(po.name)
		pi.insert()
		self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name}), 0)
