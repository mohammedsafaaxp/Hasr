import frappe
from frappe.tests.utils import FrappeTestCase

from hasr import hooks


class TestInstall(FrappeTestCase):
	def test_requires_erpnext(self):
		self.assertIn("erpnext", hooks.required_apps)
		self.assertIn("erpnext", frappe.get_installed_apps())

	def test_roles_and_fields_exist(self):
		for role in ("Hasr Counter", "Hasr Supervisor"):
			self.assertTrue(frappe.db.exists("Role", role), role)
		self.assertTrue(frappe.get_meta("Item").has_field("hasr_storage"))

	def test_settings_defaults(self):
		settings = frappe.get_single("Hasr Settings")
		self.assertEqual(settings.tolerance_a_pct, 1)
		self.assertEqual(settings.tolerance_b_pct, 2)
		self.assertEqual(settings.tolerance_c_pct, 5)
		self.assertEqual(settings.abc_a_share, 80)
		self.assertEqual(settings.abc_b_share, 95)

	def test_settings_validates_shares(self):
		settings = frappe.get_single("Hasr Settings")
		settings.abc_a_share, settings.abc_b_share = 96, 95
		self.assertRaises(frappe.ValidationError, settings.save)

	def test_one_open_session_index_is_unique(self):
		rows = frappe.db.sql(
			"show index from `tabHasr Receiving Session` where Column_name = 'open_lock'", as_dict=True
		)
		self.assertTrue(rows and rows[0].Non_unique == 0)
		rows = frappe.db.sql("show index from `tabHasr Scan` where Column_name = 'client_uuid'", as_dict=True)
		self.assertTrue(rows and rows[0].Non_unique == 0)
