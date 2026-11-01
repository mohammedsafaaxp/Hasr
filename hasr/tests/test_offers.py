import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from hasr.api import receiving as api
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


def line_of(session, item_code):
	return next(l for l in session["lines"] if l["item_code"] == item_code)


def set_free_qty(on):
	frappe.db.set_single_value("Hasr Settings", "enable_free_qty", on)
	frappe.clear_document_cache("Hasr Settings", "Hasr Settings")


class TestSupplierOffers(HasrTestCase, FrappeTestCase):
	"""Free goods from a supplier offer: entered on the phone, a free row in the Purchase Receipt."""

	def setUp(self):
		frappe.set_user("Administrator")
		set_free_qty(1)
		for name in frappe.get_all("Pricing Rule", filters={"buying": 1, "price_or_product_discount": "Product"}, pluck="name"):
			frappe.delete_doc("Pricing Rule", name, force=True, ignore_permissions=True)
		self.po = fx.make_po([("HASR-YOGURT", 10), ("HASR-CREAM-B", 25)])
		frappe.set_user(fx.COUNTER)
		self.s = api.start_session(self.po.name)
		self.yogurt = line_of(self.s, "HASR-YOGURT")["po_item"]
		self.cream = line_of(self.s, "HASR-CREAM-B")["po_item"]

	def tearDown(self):
		frappe.set_user("Administrator")
		set_free_qty(0)

	def test_free_quantity_is_off_by_default(self):
		frappe.set_user("Administrator")
		set_free_qty(0)
		frappe.set_user(fx.COUNTER)
		self.assertFalse(api.get_session(self.s["name"])["free_qty_enabled"])
		self.assertRaisesRegex(frappe.ValidationError, "turned off", api.set_line, self.s["name"], self.yogurt, 12, None, 2)

	def test_free_quantity_is_not_more_than_received(self):
		self.assertRaises(frappe.ValidationError, api.set_line, self.s["name"], self.yogurt, 2, None, 3)

	def test_offer_becomes_a_free_row_with_a_pricing_rule(self):
		out = api.set_line(self.s["name"], self.yogurt, 12, None, 2)
		line = line_of(out, "HASR-YOGURT")
		self.assertEqual((line["received_qty"], line["free_qty"], line["over_allowance_state"]), (12, 2, "OK"))
		d1, d2 = add_days(nowdate(), 30), add_days(nowdate(), 60)
		api.set_line(self.s["name"], self.cream, 30, [{"expiry_date": d1, "qty": 20}, {"expiry_date": d2, "qty": 10}], 5)
		api.finish_session(self.s["name"])

		frappe.set_user(fx.SUPERVISOR)
		self.assertTrue(any("free" in p for p in api.get_review(self.s["name"])["match_problems"]))
		pr = frappe.get_doc("Purchase Receipt", api.approve(self.s["name"], submit=1)["purchase_receipt"])
		self.assertEqual(pr.docstatus, 1)
		frappe.set_user("Administrator")

		paid = [r for r in pr.items if r.item_code == "HASR-YOGURT" and not r.is_free_item]
		free = [r for r in pr.items if r.item_code == "HASR-YOGURT" and r.is_free_item]
		self.assertEqual([(r.qty, r.purchase_order_item) for r in paid], [(10, self.yogurt)])
		self.assertEqual([(r.qty, r.rate, r.purchase_order_item) for r in free], [(2, 0, None)])
		rule = frappe.get_doc("Pricing Rule", free[0].pricing_rules)
		self.assertEqual((rule.buying, rule.price_or_product_discount, rule.supplier, rule.same_item), (1, "Product", pr.supplier, 1))
		self.assertEqual((str(rule.valid_from), str(rule.valid_upto)), (str(pr.posting_date), str(pr.posting_date)), "only for this day")

		# the free part comes off the last expiry date: 20 paid / 5 paid + 5 free
		cream = sorted(((r.qty, r.is_free_item, str(frappe.db.get_value("Batch", r.batch_no, "expiry_date"))) for r in pr.items if r.item_code == "HASR-CREAM-B"))
		self.assertEqual(cream, [(5, 0, d2), (5, 1, d2), (20, 0, d1)])

		# only what was paid counts against the order; the cost is spread over all units
		self.assertEqual(frappe.db.get_value("Purchase Order", self.po.name, "per_received"), 100)
		sle = frappe.get_all(
			"Stock Ledger Entry",
			filters={"voucher_no": pr.name, "item_code": "HASR-YOGURT", "is_cancelled": 0},
			fields=["actual_qty", "stock_value_difference"],
		)
		self.assertEqual(sum(flt(e.actual_qty) for e in sle), 12)
		self.assertAlmostEqual(sum(flt(e.stock_value_difference) for e in sle), 100, places=2, msg="10 paid × 10, 2 free at 0")

	def test_an_active_offer_in_erpnext_is_reused(self):
		rule = frappe.get_doc(
			{
				"doctype": "Pricing Rule",
				"title": "Buy 10 yogurt get 2",
				"apply_on": "Item Code",
				"items": [{"item_code": "HASR-YOGURT"}],
				"buying": 1,
				"applicable_for": "Supplier",
				"supplier": self.po.supplier,
				"company": self.po.company,
				"currency": frappe.get_cached_value("Company", self.po.company, "default_currency"),
				"price_or_product_discount": "Product",
				"same_item": 1,
				"min_qty": 10,
				"free_qty": 2,
			}
		).insert(ignore_permissions=True)
		api.set_line(self.s["name"], self.yogurt, 12, None, 2)
		api.finish_session(self.s["name"])
		frappe.set_user(fx.SUPERVISOR)
		pr = frappe.get_doc("Purchase Receipt", api.approve(self.s["name"])["purchase_receipt"])
		self.assertEqual(next(r for r in pr.items if r.is_free_item).pricing_rules, rule.name)
