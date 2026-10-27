import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


def line_of(payload, item_code):
	return next(l for l in payload["lines"] if l["item_code"] == item_code)


class TestReceiving(HasrTestCase, FrappeTestCase):
	def start(self, po, user=fx.COUNTER):
		frappe.set_user(user)
		return api.start_session(po.name)

	def test_counter_sees_only_permitted_open_orders(self):
		main = fx.make_po([("HASR-MILK", 5)])
		second = fx.make_po([("HASR-MILK", 5)], wh=fx.warehouse("Hasr Second"))
		draft = fx.make_po([("HASR-MILK", 5)], submit=False)
		closed = fx.make_po([("HASR-MILK", 5)])
		closed.update_status("Closed")

		frappe.set_user("Administrator")
		perm = frappe.get_doc(
			{"doctype": "User Permission", "user": fx.COUNTER_2, "allow": "Warehouse", "for_value": fx.warehouse("Hasr Main")}
		).insert(ignore_permissions=True)
		try:
			frappe.set_user(fx.COUNTER_2)
			names = {o.name for o in api.list_open_orders()}
			self.assertIn(main.name, names)
			self.assertNotIn(second.name, names)
			self.assertNotIn(draft.name, names)
			self.assertNotIn(closed.name, names)
			self.assertRaises(frappe.PermissionError, api.start_session, second.name)
			self.assertRaises(frappe.PermissionError, api.list_open_orders, fx.warehouse("Hasr Second"))

			frappe.set_user(fx.COUNTER)  # no user permissions: every warehouse
			names = {o.name for o in api.list_open_orders()}
			self.assertTrue({main.name, second.name} <= names)
		finally:
			frappe.set_user("Administrator")
			perm.delete(ignore_permissions=True)

	def test_users_without_hasr_role_are_refused(self):
		fx.user("hasr.nobody@example.com", ["Stock User"])
		frappe.set_user("hasr.nobody@example.com")
		self.assertRaises(frappe.PermissionError, api.list_open_orders)

	def test_start_session_snapshots_lines(self):
		po = fx.make_po([("HASR-MILK", 2, "Box", 12), ("HASR-YOGURT", 36)])
		s = self.start(po)
		self.assertEqual(s["status"], "Open")
		self.assertEqual(s["shipment_no"], 1)
		self.assertEqual(s["received_by"], fx.COUNTER)
		milk = line_of(s, "HASR-MILK")
		self.assertEqual((milk["ordered_qty"], milk["pending_qty"], milk["stock_uom"]), (24, 24, "Nos"))
		self.assertEqual(s["supplier_name"], "Northfield Dairy Co.")

	def test_second_open_session_fails(self):
		po = fx.make_po([("HASR-MILK", 5)])
		first = self.start(po)
		frappe.set_user(fx.COUNTER_2)
		with self.assertRaisesRegex(frappe.ValidationError, f"already has an open receiving session {first['name']}"):
			api.start_session(po.name)

		# the unique index catches the race even if validate is bypassed
		frappe.set_user("Administrator")
		doc = frappe.get_doc(
			{"doctype": "Hasr Receiving Session", "purchase_order": po.name, "status": "Open", "open_lock": po.name}
		)
		doc.flags.ignore_validate = True
		self.assertRaises(frappe.UniqueValidationError, doc.insert, ignore_permissions=True)

	def test_second_session_allowed_after_finish(self):
		po = fx.make_po([("HASR-MILK", 10)])
		s = self.start(po)
		sync.push_scans([fx.scan(s["name"], fx.MILK_UNIT, qty=4)])
		api.finish_session(s["name"], "DN-1", "Still coming")
		s2 = self.start(po, fx.COUNTER_2)
		self.assertEqual(s2["shipment_no"], 2)
		# remaining excludes the shipment still pending approval
		self.assertEqual(line_of(s2, "HASR-MILK")["pending_qty"], 6)

	def test_counter_cannot_touch_others_session(self):
		po = fx.make_po([("HASR-MILK", 5)])
		s = self.start(po)
		frappe.set_user(fx.COUNTER_2)
		self.assertRaises(frappe.PermissionError, api.get_session, s["name"])
		self.assertRaises(frappe.PermissionError, api.set_line, s["name"], s["lines"][0]["po_item"], 1)

	def test_set_line_combines_with_scans(self):
		po = fx.make_po([("HASR-MILK", 30)])
		s = self.start(po)
		po_item = s["lines"][0]["po_item"]
		sync.push_scans([fx.scan(s["name"], fx.MILK_UNIT), fx.scan(s["name"], fx.MILK_UNIT)])
		out = api.set_line(s["name"], po_item, 10, 2)
		self.assertEqual((out["lines"][0]["received_qty"], out["lines"][0]["rejected_qty"]), (10, 2))
		out = sync.push_scans([fx.scan(s["name"], fx.MILK_UNIT)])  # a later scan adds on top
		self.assertEqual(out["lines"][0]["received_qty"], 11)
		self.assertRaises(frappe.ValidationError, api.set_line, s["name"], po_item, -1)

	def test_over_allowance_accept_and_cap(self):
		po = fx.make_po([("HASR-CHEESE", 48), ("HASR-YOGURT", 10)])  # cheese allowance 5% → 50.4
		s = self.start(po)
		cheese = line_of(s, "HASR-CHEESE")["po_item"]
		yogurt = line_of(s, "HASR-YOGURT")["po_item"]
		out = api.set_line(s["name"], cheese, 50)
		self.assertEqual(line_of(out, "HASR-CHEESE")["over_allowance_state"], "OK")
		out = api.set_line(s["name"], cheese, 54)
		self.assertEqual(line_of(out, "HASR-CHEESE")["over_allowance_state"], "Over")
		api.set_line(s["name"], yogurt, 12)  # no allowance: over
		api.finish_session(s["name"])

		frappe.set_user(fx.COUNTER)
		self.assertRaises(frappe.PermissionError, api.decide_line, s["name"], cheese, "Accept")

		frappe.set_user(fx.SUPERVISOR)
		self.assertRaisesRegex(frappe.ValidationError, "Decide on the over-receipt", api.approve, s["name"])
		out = api.decide_line(s["name"], cheese, "Accept")
		self.assertEqual(line_of(out, "HASR-CHEESE")["over_allowance_state"], "Accepted")
		self.assertEqual(line_of(out, "HASR-CHEESE")["received_qty"], 54)
		out = api.approve(s["name"], decisions={yogurt: "Cap"})
		self.assertEqual(line_of(out, "HASR-YOGURT")["over_allowance_state"], "Capped")
		self.assertEqual(line_of(out, "HASR-YOGURT")["received_qty"], 10)
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual({r.item_code: r.qty for r in pr.items}, {"HASR-CHEESE": 54, "HASR-YOGURT": 10})

	def test_approve_creates_draft_pr(self):
		po = fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 36), ("HASR-CHEESE", 5)])
		s = self.start(po)
		sync.push_scans([fx.scan(s["name"], fx.MILK_CASE), fx.scan(s["name"], fx.MILK_CASE)])
		api.set_line(s["name"], line_of(s, "HASR-YOGURT")["po_item"], 34, 2)
		api.finish_session(s["name"], "DN-4411", "Still coming")

		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(s["name"])
		self.assertEqual(out["status"], "Approved")
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual(pr.docstatus, 0, "approve must not submit unless asked")
		self.assertEqual(pr.supplier_delivery_note, "DN-4411")
		self.assertEqual(len(pr.items), 2, "cheese was not received and is left out")
		rows = {r.item_code: r for r in pr.items}
		self.assertEqual(rows["HASR-MILK"].purchase_order, po.name)
		self.assertEqual((rows["HASR-MILK"].qty, rows["HASR-MILK"].uom, rows["HASR-MILK"].stock_qty), (2, "Box", 24))
		self.assertEqual((rows["HASR-YOGURT"].qty, rows["HASR-YOGURT"].rejected_qty), (34, 2))
		self.assertEqual(rows["HASR-YOGURT"].rejected_warehouse, fx.warehouse("Hasr Rejected"))
		self.assertEqual(frappe.db.get_value("Purchase Order", po.name, "per_received"), 0)

		self.assertRaises(frappe.ValidationError, api.approve, s["name"])  # not pending any more

	def test_approve_with_submit(self):
		po = fx.make_po([("HASR-YOGURT", 6)])
		s = self.start(po)
		sync.push_scans([fx.scan(s["name"], fx.YOGURT_UNIT, qty=6)])
		api.finish_session(s["name"])
		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(s["name"], submit=1)
		self.assertEqual(frappe.db.get_value("Purchase Receipt", out["purchase_receipt"], "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Purchase Order", po.name, "per_received"), 100)

	def test_rejected_warehouse_fallback_required(self):
		po = fx.make_po([("HASR-YOGURT", 6)])
		s = self.start(po)
		api.set_line(s["name"], s["lines"][0]["po_item"], 5, 1)
		api.finish_session(s["name"])
		frappe.set_user("Administrator")
		frappe.db.set_single_value("Hasr Settings", "default_rejected_warehouse", None)
		frappe.clear_document_cache("Hasr Settings", "Hasr Settings")
		try:
			frappe.set_user(fx.SUPERVISOR)
			self.assertRaisesRegex(frappe.ValidationError, "no rejected warehouse", api.approve, s["name"])
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_single_value("Hasr Settings", "default_rejected_warehouse", fx.warehouse("Hasr Rejected"))
			frappe.clear_document_cache("Hasr Settings", "Hasr Settings")

	def test_counter_cannot_approve(self):
		po = fx.make_po([("HASR-YOGURT", 6)])
		s = self.start(po)
		sync.push_scans([fx.scan(s["name"], fx.YOGURT_UNIT)])
		api.finish_session(s["name"])
		frappe.set_user(fx.COUNTER)
		self.assertRaises(frappe.PermissionError, api.approve, s["name"])
		self.assertRaises(frappe.PermissionError, api.send_back, s["name"])
		self.assertEqual(frappe.db.get_value("Hasr Receiving Session", s["name"], "status"), "Pending Approval")

	def test_send_back_reopens_for_counter(self):
		po = fx.make_po([("HASR-CHEESE", 10)])
		s = self.start(po)
		api.set_line(s["name"], s["lines"][0]["po_item"], 12)
		api.finish_session(s["name"])
		frappe.set_user(fx.SUPERVISOR)
		api.decide_line(s["name"], s["lines"][0]["po_item"], "Accept")
		out = api.send_back(s["name"], "Recount the cheese")
		self.assertEqual(out["status"], "Sent Back")
		self.assertEqual(out["lines"][0]["over_allowance_state"], "Over", "decisions reset on send back")
		frappe.set_user(fx.COUNTER)
		out = api.set_line(s["name"], s["lines"][0]["po_item"], 10)
		self.assertEqual(out["review_note"], "Recount the cheese")
		self.assertEqual(out["lines"][0]["over_allowance_state"], "OK")
		self.assertEqual(api.finish_session(s["name"])["status"], "Pending Approval")

	def test_finish_requires_something(self):
		po = fx.make_po([("HASR-YOGURT", 6)])
		s = self.start(po)
		self.assertRaises(frappe.ValidationError, api.finish_session, s["name"])

	def test_unknown_barcode_link_and_dismiss(self):
		po = fx.make_po([("HASR-YOGURT", 20)])
		s = self.start(po)
		barcode = "62870" + frappe.generate_hash(length=8)
		photo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
		unk = api.report_unknown_barcode(s["name"], barcode, 6, "Label says Greek Yogurt", photo, "unk-uuid-" + barcode)
		again = api.report_unknown_barcode(s["name"], barcode, 6, "dup", None, "unk-uuid-" + barcode)
		self.assertEqual(unk["name"], again["name"], "reporting is idempotent")
		self.assertTrue(frappe.db.get_value("Hasr Unknown Barcode", unk["name"], "photo"))
		other = api.report_unknown_barcode(s["name"], "62870" + frappe.generate_hash(length=8), 1)
		api.finish_session(s["name"])

		frappe.set_user(fx.SUPERVISOR)
		self.assertRaisesRegex(frappe.ValidationError, "unknown barcodes", api.approve, s["name"])
		self.assertRaises(frappe.ValidationError, api.link_unknown_barcode, unk["name"], "HASR-BUTTER")  # not on PO
		api.link_unknown_barcode(unk["name"], "HASR-YOGURT")
		self.assertEqual(frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent"), "HASR-YOGURT")
		self.assertEqual(api.get_session(s["name"])["lines"][0]["received_qty"], 6)
		api.dismiss_unknown_barcode(other["name"])
		self.assertEqual(api.approve(s["name"])["status"], "Approved")

	def test_cancel_frees_the_order(self):
		po = fx.make_po([("HASR-YOGURT", 6)])
		s = self.start(po)
		api.cancel_session(s["name"])
		self.assertEqual(self.start(po, fx.COUNTER_2)["shipment_no"], 1)
