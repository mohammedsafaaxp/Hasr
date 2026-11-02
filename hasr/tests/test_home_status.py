import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.api import receiving as api
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


def order(name):
	return next(o for o in api.list_open_orders() if o["name"] == name)


class TestHomeStatus(HasrTestCase, FrappeTestCase):
	"""The order list shows shipments waiting for approval, not only what ERPNext has received."""

	def test_status_follows_shipments_waiting_for_approval(self):
		po = fx.make_po([("HASR-YOGURT", 10), ("HASR-CHEESE", 5)])
		frappe.set_user(fx.COUNTER)
		o = order(po.name)
		self.assertEqual((o["items_done"], o["items_left"], o["waiting_shipments"]), (0, 2, 0))

		# part of the order sent for review: one item done, one still to receive
		s = api.start_session(po.name)
		yogurt = next(l["po_item"] for l in s["lines"] if l["item_code"] == "HASR-YOGURT")
		api.set_line(s["name"], yogurt, 10)
		api.finish_session(s["name"], None, "Still coming")
		o = order(po.name)
		self.assertEqual((o["items_done"], o["items_left"], o["waiting_shipments"]), (1, 1, 1))

		# the rest too: nothing left to receive, so the order no longer opens
		s2 = api.start_session(po.name)
		self.assertEqual([l["item_code"] for l in s2["lines"]], ["HASR-CHEESE"])
		api.set_line(s2["name"], s2["lines"][0]["po_item"], 5)
		api.finish_session(s2["name"])
		o = order(po.name)
		self.assertEqual((o["items_done"], o["items_left"], o["waiting_shipments"]), (2, 0, 2))
		self.assertRaises(frappe.ValidationError, api.start_session, po.name)

		# approved as drafts: still waiting until the receipts are submitted
		frappe.set_user(fx.SUPERVISOR)
		api.approve(s["name"])
		frappe.set_user(fx.COUNTER)
		self.assertEqual(order(po.name)["waiting_shipments"], 2)
