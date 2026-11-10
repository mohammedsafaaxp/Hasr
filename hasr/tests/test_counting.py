import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_to_date, flt, getdate, now_datetime, nowdate

from hasr import abc, counting, stock_freeze
from hasr.api import counting as api
from hasr.erpnext_adapter import stock_count as erp_count
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

COUNT = "Hasr Count Session"


def set_setting(**values):
	for field, value in values.items():
		frappe.db.set_single_value("Hasr Settings", field, value)
	frappe.clear_document_cache("Hasr Settings", "Hasr Settings")


def stock_entry(purpose, item_code, qty, wh, batch_no=None, rate=100):
	frappe.set_user("Administrator")
	row = {"item_code": item_code, "qty": qty, "basic_rate": rate, "conversion_factor": 1}
	row["t_warehouse" if purpose == "Material Receipt" else "s_warehouse"] = wh
	if batch_no:
		row.update(batch_no=batch_no, use_serial_batch_fields=1)
	se = frappe.get_doc(
		{"doctype": "Stock Entry", "stock_entry_type": purpose, "purpose": purpose, "company": fx.company().name, "items": [row]}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def batch(item_code, batch_id, days=60):
	if not frappe.db.exists("Batch", batch_id):
		frappe.get_doc(
			{"doctype": "Batch", "item": item_code, "batch_id": batch_id, "expiry_date": add_days(nowdate(), days)}
		).insert(ignore_permissions=True)
	return batch_id


def new_count(items=None, scope_type="Items", zones=None, **extra):
	frappe.set_user(fx.SUPERVISOR)
	doc = frappe.get_doc(
		{
			"doctype": COUNT,
			"warehouse": fx.warehouse("Hasr Count"),
			"count_type": extra.pop("count_type", "Cycle"),
			"entry_method": "Scan",
			"scope_type": scope_type,
			"scope_items": [{"item_code": i} for i in items or []],
			"zones": zones or [{"zone_name": "Aisle 1", "counter": fx.COUNTER}],
			**extra,
		}
	).insert()
	api.start(doc.name)
	return doc.name


def count(name, item_code, qty, batch_no=None, user=fx.COUNTER):
	frappe.set_user(user)
	return api.set_count(name, item_code, qty, batch_no=batch_no, client_uuid=frappe.generate_hash(length=20))


def line(name, item_code, batch_no=None):
	frappe.set_user("Administrator")
	doc = frappe.get_doc(COUNT, name)
	return next(l for l in doc.lines if l.item_code == item_code and (l.batch_no or None) == batch_no)


class TestCounting(HasrTestCase, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.wh = fx.warehouse("Hasr Count")
		stock_entry("Material Receipt", "HASR-MILK", 20, cls.wh, rate=1000)
		stock_entry("Material Receipt", "HASR-CHEESE", 10, cls.wh, rate=50)
		cls.cream_batch = batch("HASR-CREAM-B", "HASR-CNT-CR-1")
		stock_entry("Material Receipt", "HASR-CREAM-B", 12, cls.wh, batch_no=cls.cream_batch, rate=30)

	def setUp(self):
		frappe.set_user("Administrator")
		set_setting(test_count_sample_pct=0, allow_freeze=1, freeze_max_hours=24, tolerance_c_pct=0, tolerance_a_pct=0, tolerance_b_pct=0)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all(COUNT, filters={"status": ["not in", ["Approved", "Cancelled"]]}, pluck="name"):
			frappe.db.set_value(COUNT, name, "status", "Cancelled")
		frappe.db.set_value("Hasr Stock Freeze", {"active": 1}, "active", 0)
		stock_freeze.clear_cache()
		super().tearDown()

	def balance(self, item_code):
		return erp_count.get_balance(item_code, self.wh)

	def test_the_phone_never_sees_system_quantities(self):
		name = new_count(["HASR-MILK", "HASR-CREAM-B"])
		frappe.set_user(fx.COUNTER)
		payload = api.get_count(name)
		text = json.dumps(payload, default=str)
		for word in ("system_qty", "valuation", "variance", "actual_qty"):
			self.assertNotIn(word, text)
		self.assertEqual({i["item_code"] for i in payload["items"]}, {"HASR-MILK", "HASR-CREAM-B"})
		cream = next(i for i in payload["items"] if i["item_code"] == "HASR-CREAM-B")
		self.assertIn(self.cream_batch, [b["batch_no"] for b in cream["batches"]])

	def test_exact_count_is_approved_without_a_reconciliation(self):
		milk = self.balance("HASR-MILK")
		name = new_count(["HASR-MILK"])
		count(name, "HASR-MILK", milk)
		frappe.set_user(fx.SUPERVISOR)
		self.assertEqual(api.close_counting(name)["status"], "Pending Approval")
		frappe.set_user(fx.SUPERVISOR_2)
		out = api.approve(name)
		self.assertEqual(out["status"], "Approved")
		self.assertIsNone(frappe.db.get_value(COUNT, name, "stock_reconciliation"))
		abc_row = frappe.db.get_value(
			"Hasr ABC Class", {"item_code": "HASR-MILK", "warehouse": self.wh}, ["last_counted_on", "next_due_on"], as_dict=True
		)
		self.assertEqual(getdate(abc_row.last_counted_on), getdate(nowdate()))
		self.assertGreater(getdate(abc_row.next_due_on), getdate(nowdate()))

	def test_difference_is_recounted_by_someone_else_and_reconciled(self):
		milk = self.balance("HASR-MILK")
		name = new_count(["HASR-MILK", "HASR-CHEESE"])
		count(name, "HASR-MILK", milk - 2)
		count(name, "HASR-CHEESE", self.balance("HASR-CHEESE"))
		frappe.set_user(fx.SUPERVISOR)
		review = api.close_counting(name)
		self.assertEqual((review["status"], review["totals"]["needs_recount"]), ("Recount", 1))
		self.assertRaisesRegex(frappe.ValidationError, "counted these items", api.assign_recount, name, fx.COUNTER)
		api.assign_recount(name, fx.COUNTER_2)

		frappe.set_user(fx.COUNTER_2)
		payload = api.get_count(name)
		self.assertEqual([i["item_code"] for i in payload["items"]], ["HASR-MILK"], "only the lines to recount")
		self.assertRaises(frappe.ValidationError, count, name, "HASR-CHEESE", 1, user=fx.COUNTER_2)
		count(name, "HASR-MILK", milk - 2, user=fx.COUNTER_2)

		frappe.set_user(fx.SUPERVISOR)
		review = api.finish_review(name)
		self.assertEqual(review["status"], "Pending Approval")
		milk_line = next(l for l in review["lines"] if l["item_code"] == "HASR-MILK")
		self.assertEqual((milk_line["final_qty"], milk_line["variance_qty"]), (milk - 2, -2))
		self.assertEqual(milk_line["variance_value"], -2000)

		frappe.set_user(fx.SUPERVISOR_2)
		self.assertRaisesRegex(frappe.ValidationError, "reason", api.approve, name)
		frappe.set_user(fx.SUPERVISOR)
		api.set_reasons(name, {milk_line["name"]: {"reason": "Damage", "note": "two cartons leaking"}})
		frappe.set_user(fx.SUPERVISOR_2)
		api.approve(name, submit=1)
		sr = frappe.db.get_value(COUNT, name, "stock_reconciliation")
		self.assertEqual(frappe.db.get_value("Stock Reconciliation", sr, "docstatus"), 1)
		self.assertEqual(self.balance("HASR-MILK"), milk - 2)

	def test_counters_cannot_approve_and_others_cannot_count(self):
		name = new_count(["HASR-CHEESE"], zones=[{"zone_name": "Front", "counter": fx.SUPERVISOR}])
		frappe.set_user(fx.COUNTER)
		self.assertRaises(frappe.PermissionError, api.get_count, name)
		count(name, "HASR-CHEESE", self.balance("HASR-CHEESE"), user=fx.SUPERVISOR)
		frappe.set_user(fx.SUPERVISOR_2)
		api.close_counting(name)
		frappe.set_user(fx.SUPERVISOR)
		self.assertRaisesRegex(frappe.PermissionError, "You counted", api.approve, name)

	def test_hand_over_closes_the_zone(self):
		name = new_count(["HASR-CHEESE"])
		count(name, "HASR-CHEESE", 3)
		frappe.set_user(fx.COUNTER)
		self.assertTrue(api.hand_over(name)["handed_over"])
		self.assertRaisesRegex(frappe.ValidationError, "handed over", count, name, "HASR-CHEESE", 4)
		frappe.set_user(fx.SUPERVISOR)
		self.assertTrue(api.review(name)["zones"][0]["handed_over"])

	def test_zones_add_up_and_a_count_replaces_the_earlier_one(self):
		cheese = self.balance("HASR-CHEESE")
		name = new_count(
			["HASR-CHEESE"],
			zones=[{"zone_name": "Front", "counter": fx.COUNTER}, {"zone_name": "Back", "counter": fx.COUNTER_2}],
		)
		count(name, "HASR-CHEESE", 99)
		count(name, "HASR-CHEESE", cheese - 4)  # corrected: replaces 99
		count(name, "HASR-CHEESE", 4, user=fx.COUNTER_2)
		frappe.set_user(fx.SUPERVISOR)
		review = api.close_counting(name)
		self.assertEqual(review["status"], "Pending Approval")
		self.assertEqual(review["lines"][0]["final_qty"], cheese)

	def test_batch_items_are_counted_per_batch(self):
		cream = erp_count.get_batch_balance(self.cream_batch, self.wh)
		name = new_count(["HASR-CREAM-B"])
		self.assertRaisesRegex(frappe.ValidationError, "per batch", count, name, "HASR-CREAM-B", 5)
		count(name, "HASR-CREAM-B", cream + 3, batch_no=self.cream_batch)
		frappe.set_user(fx.SUPERVISOR)
		api.close_counting(name)
		api.assign_recount(name, fx.COUNTER_2)
		count(name, "HASR-CREAM-B", cream + 3, batch_no=self.cream_batch, user=fx.COUNTER_2)
		frappe.set_user(fx.SUPERVISOR)
		review = api.finish_review(name)
		cream_line = next(l for l in review["lines"] if l["batch_no"] == self.cream_batch)
		api.set_reasons(name, {cream_line["name"]: {"reason": "Receiving error"}})
		frappe.set_user(fx.SUPERVISOR_2)
		api.approve(name, submit=1)
		self.assertEqual(erp_count.get_batch_balance(self.cream_batch, self.wh), cream + 3)

	def test_freeze_blocks_stock_movements_but_not_the_counts_reconciliation(self):
		milk = self.balance("HASR-MILK")
		name = new_count(["HASR-MILK"], freeze=1)
		self.assertTrue(frappe.db.get_value(COUNT, name, "frozen_until"))
		self.assertRaisesRegex(frappe.ValidationError, "frozen", stock_entry, "Material Issue", "HASR-MILK", 1, self.wh)
		stock_entry("Material Issue", "HASR-CHEESE", 1, self.wh)  # other items move
		count(name, "HASR-MILK", milk + 1)
		frappe.set_user(fx.SUPERVISOR)
		api.close_counting(name)
		api.assign_recount(name, fx.COUNTER_2)
		count(name, "HASR-MILK", milk + 1, user=fx.COUNTER_2)
		frappe.set_user(fx.SUPERVISOR)
		review = api.finish_review(name)
		api.set_reasons(name, {review["lines"][0]["name"]: {"reason": "Receiving error"}})
		frappe.set_user(fx.SUPERVISOR_2)
		api.approve(name)  # draft reconciliation: the freeze holds until it is submitted
		self.assertTrue(counting.is_frozen(frappe.get_doc(COUNT, name)))
		sr = frappe.db.get_value(COUNT, name, "stock_reconciliation")
		frappe.set_user("Administrator")
		frappe.get_doc("Stock Reconciliation", sr).submit()
		self.assertFalse(counting.is_frozen(frappe.get_doc(COUNT, name)))
		self.assertEqual(self.balance("HASR-MILK"), milk + 1)
		stock_entry("Material Issue", "HASR-MILK", 1, self.wh)

	def test_freezes_expire(self):
		name = new_count(["HASR-CHEESE"], freeze=1)
		frappe.set_user("Administrator")
		frappe.db.set_value("Hasr Stock Freeze", {"count_session": name}, "expires_at", add_to_date(now_datetime(), hours=-1))
		self.assertEqual(stock_freeze.release_expired_freezes(), 1)
		stock_entry("Material Issue", "HASR-CHEESE", 1, self.wh)

	def test_without_freeze_the_balance_is_taken_when_the_item_is_counted(self):
		name = new_count(["HASR-MILK"])
		stock_entry("Material Issue", "HASR-MILK", 2, self.wh)  # sold before the counter got there
		count(name, "HASR-MILK", self.balance("HASR-MILK"))
		frappe.set_user(fx.SUPERVISOR)
		self.assertEqual(api.close_counting(name)["status"], "Pending Approval")

	def test_supervisor_test_count_wins_when_it_differs(self):
		set_setting(test_count_sample_pct=100)
		cheese = self.balance("HASR-CHEESE")
		name = new_count(["HASR-CHEESE"])
		count(name, "HASR-CHEESE", cheese)
		frappe.set_user(fx.SUPERVISOR)
		review = api.close_counting(name)
		self.assertEqual((review["status"], review["totals"]["test_sample"]), ("Recount", 1))
		self.assertRaisesRegex(frappe.ValidationError, "test counts", api.finish_review, name)
		api.set_test_count(name, review["lines"][0]["name"], cheese - 1)
		review = api.finish_review(name)
		self.assertEqual((review["lines"][0]["final_qty"], review["lines"][0]["within_tolerance"]), (cheese - 1, 0))

	def test_whole_warehouse_count_takes_items_found_on_the_shelf(self):
		name = new_count(scope_type="Warehouse")
		self.assertTrue(line(name, "HASR-MILK"))
		count(name, "HASR-BUTTER", 2)
		self.assertTrue(line(name, "HASR-BUTTER").added_by_counter)
		other = new_count(["HASR-MILK"])
		self.assertRaisesRegex(frappe.ValidationError, "not part of this count", count, other, "HASR-BUTTER", 1)

	def test_a_started_count_is_not_edited_directly(self):
		name = new_count(["HASR-MILK"])
		frappe.set_user("Administrator")
		doc = frappe.get_doc(COUNT, name)
		doc.status = "Approved"
		self.assertRaises(frappe.PermissionError, doc.save)

	def test_abc_classes_follow_usage_value(self):
		stock_entry("Material Issue", "HASR-MILK", 5, self.wh)  # 5 × 1000
		stock_entry("Material Issue", "HASR-CHEESE", 1, self.wh)  # 1 × 50
		classes = abc.classify_warehouse(self.wh)
		self.assertEqual(classes["HASR-MILK"], "A")
		self.assertEqual(classes["HASR-CHEESE"], "C")
		self.assertEqual(counting.tolerance_for("A"), 0)

	def test_gs1_lot_picks_the_batch(self):
		frappe.db.set_single_value("Hasr Settings", "gs1_enabled", 1)
		frappe.clear_document_cache("Hasr Settings", "Hasr Settings")
		name = new_count(["HASR-CREAM-B"])
		frappe.set_user(fx.COUNTER)
		expiry = getdate(add_days(nowdate(), 60)).strftime("%y%m%d")
		out = api.identify(name, f"(01)0{fx.CREAM_UNIT}(17){expiry}(10){self.cream_batch}")
		self.assertEqual((out["status"], out["item_code"], out["batch_no"]), ("item", "HASR-CREAM-B", self.cream_batch))
		self.assertEqual(api.identify(name, fx.BUTTER_UNIT)["status"], "not_in_count")

	def test_same_client_uuid_counts_once(self):
		name = new_count(["HASR-CHEESE"])
		frappe.set_user(fx.COUNTER)
		api.set_count(name, "HASR-CHEESE", 5, client_uuid="uuid-count-0001")
		self.assertEqual(api.set_count(name, "HASR-CHEESE", 7, client_uuid="uuid-count-0001")["status"], "duplicate")
		self.assertEqual(flt(api.get_count(name)["counts"][0]["qty"]), 5)

	def test_accuracy_report(self):
		from hasr.hasr.report.hasr_inventory_accuracy.hasr_inventory_accuracy import execute

		cheese = self.balance("HASR-CHEESE")
		name = new_count(["HASR-CHEESE", "HASR-MILK"])
		count(name, "HASR-CHEESE", cheese)
		count(name, "HASR-MILK", self.balance("HASR-MILK"))
		frappe.set_user(fx.SUPERVISOR)
		api.close_counting(name)
		frappe.set_user(fx.SUPERVISOR_2)
		api.approve(name)
		frappe.set_user(fx.SUPERVISOR)
		for group_by in ("Warehouse", "ABC Class", "Month"):
			cols, rows, _msg, chart = execute({"warehouse": self.wh, "group_by": group_by})
			self.assertTrue(rows, group_by)
		row = execute({"warehouse": self.wh})[1][0]
		self.assertEqual(row["warehouse"], self.wh)
		self.assertGreaterEqual(row["lines"], 2)
		self.assertLessEqual(row["ira"], 100)
