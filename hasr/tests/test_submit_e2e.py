"""End to end: a shipment received on the phone, approved and submitted, checked against ERPNext's own ledgers."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


def bin_qty(item_code, warehouse):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


class TestSubmitEndToEnd(HasrTestCase, FrappeTestCase):
	def test_received_shipment_posts_stock_batches_and_accounts(self):
		main = fx.warehouse("Hasr Main")
		before = {
			"milk": bin_qty("HASR-MILK", main),
			"cream": bin_qty("HASR-CREAM-B", main),
			"yogurt": bin_qty("HASR-YOGURT", main),
		}
		frappe.db.set_value("UOM", "Box", "must_be_whole_number", 1)
		po = fx.make_po([("HASR-MILK", 2, "Box", 12), ("HASR-CREAM-B", 10), ("HASR-YOGURT", 5)])

		# the phone: two case scans, a batch item with two expiry dates, and yogurt
		frappe.set_user(fx.COUNTER)
		s = api.start_session(po.name)
		lines = {l["item_code"]: l["po_item"] for l in s["lines"]}
		sync.push_scans([fx.scan(s["name"], fx.MILK_CASE), fx.scan(s["name"], fx.MILK_CASE)])
		d1, d2 = add_days(nowdate(), 30), add_days(nowdate(), 60)
		api.set_line(s["name"], lines["HASR-CREAM-B"], 10, [{"expiry_date": d1, "qty": 6}, {"expiry_date": d2, "qty": 4}])
		api.set_line(s["name"], lines["HASR-YOGURT"], 5)
		api.finish_session(s["name"], None, None, "INV-E2E-1")

		# the supervisor approves and submits
		frappe.set_user(fx.SUPERVISOR)
		out = api.approve(s["name"], submit=1)
		frappe.set_user("Administrator")
		pr = frappe.get_doc("Purchase Receipt", out["purchase_receipt"])
		self.assertEqual(pr.docstatus, 1)

		# warehouse balances moved by exactly what was received, in stock units
		self.assertEqual(bin_qty("HASR-MILK", main) - before["milk"], 24)
		self.assertEqual(bin_qty("HASR-CREAM-B", main) - before["cream"], 10)
		self.assertEqual(bin_qty("HASR-YOGURT", main) - before["yogurt"], 5)

		# stock ledger agrees with the receipt
		sle = frappe.db.sql(
			"""select item_code, warehouse, sum(actual_qty) from `tabStock Ledger Entry`
			where voucher_type = 'Purchase Receipt' and voucher_no = %s and is_cancelled = 0
			group by item_code, warehouse""",
			pr.name,
		)
		ledger = {(i, w): flt(q) for i, w, q in sle}
		self.assertEqual(ledger[("HASR-MILK", main)], 24)
		self.assertEqual(ledger[("HASR-CREAM-B", main)], 10)
		self.assertEqual(ledger[("HASR-YOGURT", main)], 5)

		# one batch per expiry date, each holding its quantity
		from erpnext.stock.doctype.batch.batch import get_batch_qty  # assertion only

		cream_rows = [r for r in pr.items if r.item_code == "HASR-CREAM-B"]
		per_batch = {
			str(frappe.db.get_value("Batch", r.batch_no, "expiry_date")): get_batch_qty(r.batch_no, main) for r in cream_rows
		}
		self.assertEqual(per_batch, {d1: 6, d2: 4})

		# accounting entries were posted (perpetual inventory) and the order is fully received
		self.assertTrue(frappe.db.exists("GL Entry", {"voucher_type": "Purchase Receipt", "voucher_no": pr.name, "is_cancelled": 0}))
		self.assertEqual(frappe.db.get_value("Purchase Order", po.name, "per_received"), 100)
		self.assertIn("INV-E2E-1", pr.remarks)
