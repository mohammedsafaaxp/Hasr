import frappe


def before_tests():
	frappe.get_attr("hasr.erpnext_adapter.testing.before_tests")()


class HasrTestCase:
	"""Mixin: shared invented data, and always end a test as Administrator."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from hasr.tests.fixtures import setup_all

		setup_all()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()
