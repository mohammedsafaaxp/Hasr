import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


def line_of(payload, item_code):
	return next(l for l in payload["lines"] if l["item_code"] == item_code)


class TestBatches(HasrTestCase, FrappeTestCase):
	def setUp(self):
		self.po = fx.make_po([("HASR-CREAM-B", 48), ("HASR-LABNEH-B", 10), ("HASR-YOGURT", 5)])
		frappe.set_user(fx.COUNTER)
		self.s = api.start_session(self.po.name)
		self.cream = line_of(self.s, "HASR-CREAM-B")["po_item"]
		self.labneh = line_of(self.s, "HASR-LABNEH-B")["po_item"]
		self.d1, self.d2 = add_days(nowdate(), 20), add_days(nowdate(), 40)

	def test_payload_has_batch_and_uom_info(self):
		cream = line_of(self.s, "HASR-CREAM-B")
		self.assertTrue(cream["has_batch_no"])
		self.assertEqual((cream["uom"], cream["conversion_factor"], cream["batches"]), ("Nos", 1, []))
		self.assertFalse(cream["needs_expiry"])

	def test_scans_need_expiry_then_follow_single_date(self):
		sync.push_scans([fx.scan(self.s["name"], fx.CREAM_UNIT, qty=10)])
		self.assertTrue(line_of(api.get_session(self.s["name"]), "HASR-CREAM-B")["needs_expiry"])
		api.set_line(self.s["name"], self.cream, 10, 0, [{"expiry_date": self.d1, "qty": 10}])
		sync.push_scans([fx.scan(self.s["name"], fx.CREAM_UNIT, qty=5)])
		line = line_of(api.get_session(self.s["name"]), "HASR-CREAM-B")
		self.assertEqual(line["received_qty"], 15)
		self.assertEqual(line["batches"], [{"expiry_date": self.d1, "qty": 15}])
		self.assertFalse(line["needs_expiry"])

	def test_batch_quantities_must_add_up(self):
		with self.assertRaisesRegex(frappe.ValidationError, "add up to 40"):
			api.set_line(self.s["name"], self.cream, 48, 0, [{"expiry_date": self.d1, "qty": 30}, {"expiry_date": self.d2, "qty": 10}])

	def test_expired_and_invalid_dates_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Record expired goods as rejected"):
			api.set_line(self.s["name"], self.cream, 5, 0, [{"expiry_date": add_days(nowdate(), -1), "qty": 5}])
		self.assertRaises(frappe.ValidationError, api.set_line, self.s["name"], self.cream, 5, 0, [{"expiry_date": "", "qty": 5}])

	def test_same_date_rows_merge(self):
		out = api.set_line(self.s["name"], self.cream, 8, 0, [{"expiry_date": self.d1, "qty": 5}, {"expiry_date": self.d1, "qty": 3}])
		self.assertEqual(line_of(out, "HASR-CREAM-B")["batches"], [{"expiry_date": self.d1, "qty": 8}])

	def test_non_batch_item_refuses_batches(self):
		yogurt = line_of(self.s, "HASR-YOGURT")["po_item"]
		self.assertRaises(frappe.ValidationError, api.set_line, self.s["name"], yogurt, 1, 0, [{"expiry_date": self.d1, "qty": 1}])

	def test_finish_requires_expiry(self):
		sync.push_scans([fx.scan(self.s["name"], fx.CREAM_UNIT)])
		with self.assertRaisesRegex(frappe.ValidationError, "Enter the expiry date for: Fresh Cream 500 ml"):
			api.finish_session(self.s["name"])

	def test_approve_creates_batches_and_splits_rows(self):
		api.set_line(self.s["name"], self.cream, 48, 2, [{"expiry_date": self.d1, "qty": 30}, {"expiry_date": self.d2, "qty": 18}])
		api.set_line(self.s["name"], self.labneh, 10, 0, [{"expiry_date": self.d2, "qty": 10}])
		api.finish_session(self.s["name"])
		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(self.s["name"], decisions={self.cream: "Accept"})  # 48 + 2 rejected is over 48
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual(pr.docstatus, 0)

		cream_rows = [r for r in pr.items if r.item_code == "HASR-CREAM-B"]
		self.assertEqual(sorted((r.qty, r.rejected_qty) for r in cream_rows), [(18, 0), (30, 2)])
		for r in cream_rows:
			self.assertTrue(r.batch_no.startswith("HASR-CR-"), r.batch_no)
			self.assertEqual(r.use_serial_batch_fields, 1)
			self.assertEqual(r.purchase_order_item, self.cream)
		expiries = {str(frappe.db.get_value("Batch", r.batch_no, "expiry_date")) for r in cream_rows}
		self.assertEqual(expiries, {self.d1, self.d2})

		labneh = next(r for r in pr.items if r.item_code == "HASR-LABNEH-B")
		self.assertTrue(labneh.batch_no.startswith("BT-"), labneh.batch_no)
		self.assertEqual(frappe.db.get_value("Batch", labneh.batch_no, "reference_name"), pr.name)

	def test_submit_builds_bundles(self):
		api.set_line(self.s["name"], self.cream, 30, 1, [{"expiry_date": self.d1, "qty": 20}, {"expiry_date": self.d2, "qty": 10}])
		api.finish_session(self.s["name"])
		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(self.s["name"], submit=1)
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual(pr.docstatus, 1)
		for r in pr.items:
			self.assertTrue(r.serial_and_batch_bundle, "ERPNext built the bundle from batch_no")
		first = next(r for r in pr.items if r.rejected_qty)
		self.assertTrue(first.rejected_serial_and_batch_bundle)
		from erpnext.stock.doctype.batch.batch import get_batch_qty  # assertion only

		self.assertEqual(get_batch_qty(first.batch_no, fx.warehouse("Hasr Main")), 20)


def blank_pdf_data_url():
	import base64
	import io

	from pypdf import PdfWriter

	writer, buf = PdfWriter(), io.BytesIO()
	writer.add_blank_page(width=200, height=200)
	writer.write(buf)
	return "data:application/pdf;base64," + base64.b64encode(buf.getvalue()).decode()


class TestInvoices(HasrTestCase, FrappeTestCase):
	PDF = blank_pdf_data_url()
	PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

	def test_invoice_attach_remove_and_move_to_receipt(self):
		po = fx.make_po([("HASR-YOGURT", 4)])
		frappe.set_user(fx.COUNTER)
		s = api.start_session(po.name)
		api.attach_invoice(s["name"], self.PNG)
		files = api.attach_invoice(s["name"], self.PDF)
		self.assertEqual(len(files), 2)
		self.assertTrue(all(f.is_private for f in files))
		self.assertRaises(frappe.ValidationError, api.attach_invoice, s["name"], "data:text/html;base64,PGI+")
		files = api.remove_invoice(s["name"], files[0].name)
		self.assertEqual(len(files), 1)
		self.assertEqual(len(api.get_session(s["name"])["invoices"]), 1)

		api.set_line(s["name"], s["lines"][0]["po_item"], 4)
		api.finish_session(s["name"])
		self.assertRaises(frappe.ValidationError, api.attach_invoice, s["name"], self.PNG)  # not editable any more

		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(s["name"])
		on_pr = frappe.get_all(
			"File", filters={"attached_to_doctype": "Purchase Receipt", "attached_to_name": out["purchase_receipt"]}, pluck="file_url"
		)
		self.assertEqual(on_pr, [files[0].file_url])

	def test_other_counter_cannot_attach(self):
		po = fx.make_po([("HASR-YOGURT", 4)])
		frappe.set_user(fx.COUNTER)
		s = api.start_session(po.name)
		frappe.set_user(fx.COUNTER_2)
		self.assertRaises(frappe.PermissionError, api.attach_invoice, s["name"], self.PNG)
