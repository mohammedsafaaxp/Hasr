import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import items as api
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

BALANCE_KEYS = {"actual_qty", "projected_qty", "reserved_qty", "valuation_rate", "stock_value", "bin", "balance", "qty_after_transaction", "ordered_qty"}


def all_keys(value):
	if isinstance(value, dict):
		for k, v in value.items():
			yield k
			yield from all_keys(v)
	elif isinstance(value, list):
		for v in value:
			yield from all_keys(v)


class TestItems(HasrTestCase, FrappeTestCase):
	def test_item_details_have_no_balances(self):
		frappe.set_user(fx.COUNTER)
		details = api.get_item_details("HASR-MILK")
		self.assertEqual(details["item_name"], "Whole Milk 1 L")
		self.assertFalse(set(all_keys(details)) & BALANCE_KEYS, set(all_keys(details)) & BALANCE_KEYS)
		self.assertEqual(details["weight_per_unit"], 1.03)
		self.assertIn("item_group_path", details)

	def test_last_receipt(self):
		po = fx.make_po([("HASR-BUTTER", 7)])
		from hasr import erpnext_adapter as erp

		erp.create_draft_purchase_receipt(po.name, [{"po_item": po.items[0].name, "qty": 7, "rejected_qty": 0}]).submit()
		frappe.set_user(fx.COUNTER)
		self.assertEqual(api.get_item_details("HASR-BUTTER")["last_receipt"]["stock_qty"], 7)

	def test_resolve_barcode(self):
		frappe.set_user(fx.COUNTER)
		self.assertEqual(api.resolve_barcode(fx.MILK_CASE)["conversion_factor"], 12)
		self.assertFalse(api.resolve_barcode("nope")["found"])

	def test_requires_role(self):
		fx.user("hasr.nobody@example.com", ["Stock User"])
		frappe.set_user("hasr.nobody@example.com")
		self.assertRaises(frappe.PermissionError, api.get_item_details, "HASR-MILK")
