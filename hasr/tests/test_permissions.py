import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

APPROVER = "hasr.approver@example.com"


def line_of(payload, item_code):
	return next(l for l in payload["lines"] if l["item_code"] == item_code)


def set_approver_roles(roles):
	settings = frappe.get_single("Hasr Settings")
	settings.set("approver_roles", [{"role": r} for r in roles])
	settings.save(ignore_permissions=True)


class TestPermissions(HasrTestCase, FrappeTestCase):
	def finished_session(self, rows, counter=fx.COUNTER):
		po = fx.make_po(rows)
		frappe.set_user(counter)
		s = api.start_session(po.name)
		for line in s["lines"]:
			api.set_line(s["name"], line["po_item"], line["pending_qty"])
		api.finish_session(s["name"])
		return s

	def test_approver_roles_come_from_settings(self):
		fx.user(APPROVER, ["Stock Manager", "Stock User"])
		s = self.finished_session([("HASR-YOGURT", 2)])
		frappe.set_user("Administrator")
		set_approver_roles(["Stock Manager"])
		try:
			frappe.set_user(fx.SUPERVISOR)  # Hasr Supervisor + Stock Manager: still allowed through Stock Manager
			self.assertIsNone(api.get_session(s["name"])["approval_block_reason"])
			frappe.set_user("Administrator")
			set_approver_roles(["Purchase Manager"])
			frappe.set_user(fx.SUPERVISOR)  # no Purchase Manager role
			self.assertRaises(frappe.PermissionError, api.approve, s["name"])
			frappe.set_user("Administrator")
			set_approver_roles(["Stock Manager"])
			frappe.set_user(APPROVER)  # not a Hasr Supervisor, but the setting says Stock Manager may approve
			self.assertEqual(api.approve(s["name"])["status"], "Approved")
		finally:
			frappe.set_user("Administrator")
			set_approver_roles([])

	def test_receiver_cannot_approve_own_shipment(self):
		s = self.finished_session([("HASR-YOGURT", 2)], counter=fx.SUPERVISOR)
		frappe.set_user(fx.SUPERVISOR)
		self.assertIn("Another approver", api.get_session(s["name"])["approval_block_reason"])
		self.assertRaisesRegex(frappe.PermissionError, "Another approver", api.approve, s["name"])
		self.assertRaises(frappe.PermissionError, api.send_back, s["name"])
		frappe.set_user(fx.SUPERVISOR_2)
		self.assertEqual(api.approve(s["name"])["status"], "Approved")

	def test_counter_only_gets_lines_of_their_warehouses(self):
		po = fx.make_po([("HASR-YOGURT", 5), ("HASR-CHEESE", 4, "Nos", 1, fx.warehouse("Hasr Second"))])
		po_item_second = po.items[1].name
		perm = fx.restrict(fx.COUNTER_2, fx.warehouse("Hasr Main"))
		try:
			frappe.set_user(fx.COUNTER_2)
			s = api.start_session(po.name)
			self.assertEqual([l["item_code"] for l in s["lines"]], ["HASR-YOGURT"])
			r = sync.push_scans([fx.scan(s["name"], fx.CHEESE_UNIT)])["results"][0]
			self.assertEqual((r["status"], r["reason"]), ("rejected", "other_warehouse"))
			self.assertNotIn(po_item_second, [l["po_item"] for l in api.get_session(s["name"])["lines"]])
		finally:
			frappe.set_user("Administrator")
			perm.delete(ignore_permissions=True)

	def test_approver_needs_every_warehouse_of_the_shipment(self):
		po = fx.make_po([("HASR-YOGURT", 5), ("HASR-CHEESE", 4, "Nos", 1, fx.warehouse("Hasr Second"))])
		frappe.set_user(fx.COUNTER)
		s = api.start_session(po.name)
		for line in s["lines"]:
			api.set_line(s["name"], line["po_item"], line["pending_qty"])
		api.finish_session(s["name"])
		perm = fx.restrict(fx.SUPERVISOR_2, fx.warehouse("Hasr Main"))
		try:
			frappe.set_user(fx.SUPERVISOR_2)
			self.assertRaisesRegex(frappe.PermissionError, "Hasr Second", api.approve, s["name"])
		finally:
			frappe.set_user("Administrator")
			perm.delete(ignore_permissions=True)
		frappe.set_user(fx.SUPERVISOR_2)
		self.assertEqual(api.approve(s["name"])["status"], "Approved")
