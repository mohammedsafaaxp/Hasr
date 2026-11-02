import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import i18n
from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

SESSION = "Hasr Receiving Session"


class TestSecurity(HasrTestCase, FrappeTestCase):
	"""Ways around hasr's checks that must stay closed."""

	def setUp(self):
		self.po = fx.make_po([("HASR-YOGURT", 10)])
		frappe.set_user(fx.COUNTER)
		self.s = api.start_session(self.po.name)
		self.po_item = self.s["lines"][0]["po_item"]

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_workers_only_read_their_own_shipments_through_the_rest_api(self):
		doc = frappe.get_doc(SESSION, self.s["name"])
		self.assertTrue(frappe.has_permission(SESSION, "read", doc, user=fx.COUNTER))
		self.assertFalse(frappe.has_permission(SESSION, "read", doc, user=fx.COUNTER_2))
		self.assertFalse(frappe.has_permission(SESSION, "write", doc, user=fx.COUNTER))

	def test_supervisors_cannot_write_records_or_settings_directly(self):
		for doctype in (SESSION, "Hasr Unknown Barcode", "Hasr Item Mismatch", "Hasr Settings"):
			self.assertFalse(frappe.has_permission(doctype, "write", user=fx.SUPERVISOR), doctype)
		self.assertTrue(frappe.has_permission("Hasr Settings", "read", user=fx.SUPERVISOR))

	def test_a_shipment_is_not_edited_around_the_api(self):
		frappe.set_user("Administrator")
		doc = frappe.get_doc(SESSION, self.s["name"])
		doc.status = "Approved"
		self.assertRaises(frappe.PermissionError, doc.save)  # Desk form and /api/resource save like this
		self.assertEqual(frappe.db.get_value(SESSION, doc.name, "status"), "Open")

	def test_a_supervisor_cannot_change_someone_elses_shipment(self):
		# otherwise they could change the quantities and then approve it, since they did not receive it
		frappe.set_user(fx.SUPERVISOR)
		self.assertEqual(api.get_session(self.s["name"])["name"], self.s["name"], "reading is fine")
		self.assertRaises(frappe.PermissionError, api.set_line, self.s["name"], self.po_item, 99)
		self.assertRaises(frappe.PermissionError, sync.push_scans, [fx.scan(self.s["name"], fx.YOGURT_UNIT)])
		self.assertRaises(frappe.PermissionError, api.finish_session, self.s["name"])
		frappe.set_user(fx.COUNTER)
		self.assertEqual(api.get_session(self.s["name"])["lines"][0]["received_qty"], 0)

	def test_a_supervisor_only_sees_shipments_of_their_warehouses(self):
		perm = fx.restrict(fx.SUPERVISOR_2, fx.warehouse("Hasr Second"))
		try:
			frappe.set_user(fx.SUPERVISOR_2)
			self.assertRaises(frappe.PermissionError, api.get_session, self.s["name"])
		finally:
			frappe.set_user("Administrator")
			perm.delete(ignore_permissions=True)

	def test_uploads_must_be_what_they_claim(self):
		html = "data:image/png;base64," + base64.b64encode(b"<html><script>alert(1)</script></html>").decode()
		self.assertRaisesRegex(frappe.ValidationError, "not a valid PNG", api.attach_invoice, self.s["name"], html)
		fake_pdf = "data:application/pdf;base64," + base64.b64encode(b"<svg onload=alert(1)>").decode()
		self.assertRaisesRegex(frappe.ValidationError, "not a valid PDF", api.attach_invoice, self.s["name"], fake_pdf)

	def test_guests_are_not_told_the_version(self):
		frappe.set_user("Guest")
		self.assertIsNone(i18n.get_boot()["version"])
