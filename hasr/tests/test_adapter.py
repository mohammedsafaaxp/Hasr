import frappe
from frappe.tests.utils import FrappeTestCase

from hasr import erpnext_adapter as erp
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase


class TestAdapter(HasrTestCase, FrappeTestCase):
	def test_version_detection(self):
		major = erp.erpnext_major()
		self.assertIn(major, (15, 16), "hasr supports ERPNext v15 and v16")
		self.assertTrue(erp.uses_serial_batch_bundle())

	def test_open_purchase_orders_filters(self):
		open_po = fx.make_po([("HASR-MILK", 10)])
		draft_po = fx.make_po([("HASR-MILK", 10)], submit=False)
		closed_po = fx.make_po([("HASR-MILK", 10)])
		closed_po.update_status("Closed")
		other_wh_po = fx.make_po([("HASR-MILK", 10)], wh=fx.warehouse("Hasr Second"))

		names = {o.name for o in erp.get_open_purchase_orders()}
		self.assertIn(open_po.name, names)
		self.assertIn(other_wh_po.name, names)
		self.assertNotIn(draft_po.name, names)
		self.assertNotIn(closed_po.name, names)

		restricted = {o.name for o in erp.get_open_purchase_orders(warehouses=[fx.warehouse("Hasr Main")])}
		self.assertIn(open_po.name, restricted)
		self.assertNotIn(other_wh_po.name, restricted)

		searched = erp.get_open_purchase_orders(search=open_po.name)
		self.assertEqual([o.name for o in searched], [open_po.name])
		self.assertEqual(searched[0].item_count, 1)

	def test_po_lines_with_remaining_in_stock_uom(self):
		po = fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 36)])
		lines = erp.get_po_lines_with_remaining(po.name)
		milk = next(l for l in lines if l.item_code == "HASR-MILK")
		self.assertEqual(milk.ordered_qty, 48)
		self.assertEqual(milk.remaining_qty, 48)

		# receive 1 box accepted + 1 box rejected through ERPNext: remaining drops by 24 units
		pr = erp.create_draft_purchase_receipt(
			po.name,
			[{"po_item": milk.po_item, "qty": 12, "rejected_qty": 12}],
			default_rejected_warehouse=fx.warehouse("Hasr Rejected"),
		)
		pr.submit()
		milk = next(l for l in erp.get_po_lines_with_remaining(po.name) if l.item_code == "HASR-MILK")
		self.assertEqual(milk.received_qty, 24)
		self.assertEqual(milk.remaining_qty, 24)

	def test_resolve_barcode(self):
		unit = erp.resolve_barcode(fx.MILK_UNIT)
		self.assertEqual((unit.item_code, unit.uom, unit.conversion_factor), ("HASR-MILK", "Nos", 1))
		case = erp.resolve_barcode(fx.MILK_CASE)
		self.assertEqual((case.item_code, case.uom, case.conversion_factor), ("HASR-MILK", "Box", 12))
		typed = erp.resolve_barcode("HASR-YOGURT")
		self.assertEqual((typed.item_code, typed.conversion_factor), ("HASR-YOGURT", 1))
		self.assertIsNone(erp.resolve_barcode("0000000000000"))
		self.assertIsNone(erp.resolve_barcode("  "))

	def test_over_receipt_limit(self):
		self.assertEqual(erp.get_over_receipt_limit("HASR-CHEESE", 48), 48 * 1.05)  # item allowance 5%
		self.assertEqual(erp.get_over_receipt_limit("HASR-YOGURT", 10), 10)
		frappe.db.set_single_value("Stock Settings", "over_delivery_receipt_allowance", 10)
		try:
			self.assertAlmostEqual(erp.get_over_receipt_limit("HASR-YOGURT", 10), 11)
			self.assertEqual(erp.get_over_receipt_limit("HASR-CHEESE", 48), 48 * 1.05)  # item wins
		finally:
			frappe.db.set_single_value("Stock Settings", "over_delivery_receipt_allowance", 0)

	def test_create_draft_purchase_receipt(self):
		po = fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 36), ("HASR-CHEESE", 10)])
		rows = {r.item_code: r.name for r in po.items}
		pr = erp.create_draft_purchase_receipt(
			po.name,
			[
				{"po_item": rows["HASR-MILK"], "qty": 36, "rejected_qty": 0},  # 3 boxes
				{"po_item": rows["HASR-YOGURT"], "qty": 34, "rejected_qty": 2},
				{"po_item": rows["HASR-CHEESE"], "qty": 0, "rejected_qty": 0},  # skipped
			],
			supplier_delivery_note="DN-778",
			default_rejected_warehouse=fx.warehouse("Hasr Rejected"),
		)
		self.assertEqual(pr.docstatus, 0)
		self.assertEqual(pr.supplier_delivery_note, "DN-778")
		self.assertEqual(len(pr.items), 2)
		milk = next(r for r in pr.items if r.item_code == "HASR-MILK")
		self.assertEqual((milk.uom, milk.conversion_factor, milk.qty, milk.stock_qty), ("Box", 12, 3, 36))
		self.assertEqual(milk.purchase_order, po.name)
		yogurt = next(r for r in pr.items if r.item_code == "HASR-YOGURT")
		self.assertEqual((yogurt.qty, yogurt.rejected_qty, yogurt.received_qty), (34, 2, 36))
		self.assertEqual(yogurt.rejected_warehouse, fx.warehouse("Hasr Rejected"))

	def test_whole_cases_keep_po_uom(self):
		po = fx.make_po([("HASR-MILK", 4, "Box", 12)])
		pr = erp.create_draft_purchase_receipt(po.name, [{"po_item": po.items[0].name, "qty": 24, "rejected_qty": 0}])
		row = pr.items[0]
		self.assertEqual((row.uom, row.conversion_factor, row.qty, row.stock_qty), ("Box", 12, 2, 24))

	def test_fraction_of_whole_number_uom_fails_clearly(self):
		frappe.db.set_value("UOM", "Box", "must_be_whole_number", 1)
		po = fx.make_po([("HASR-MILK", 4, "Box", 12)])
		with self.assertRaisesRegex(frappe.ValidationError, "not a whole number of Box"):
			erp.create_draft_purchase_receipt(po.name, [{"po_item": po.items[0].name, "qty": 30, "rejected_qty": 0}])

	def test_fraction_allowed_when_uom_allows_it(self):
		uom = fx.uom("Hasr Tray", whole=0)
		if not frappe.db.exists("UOM Conversion Detail", {"parent": "HASR-YOGURT", "uom": uom}):
			yogurt = frappe.get_doc("Item", "HASR-YOGURT")
			yogurt.append("uoms", {"uom": uom, "conversion_factor": 6})
			yogurt.save()
		po = fx.make_po([("HASR-YOGURT", 2, uom, 6)])
		pr = erp.create_draft_purchase_receipt(po.name, [{"po_item": po.items[0].name, "qty": 9, "rejected_qty": 0}])
		self.assertEqual((pr.items[0].qty, pr.items[0].stock_qty), (1.5, 9))

	def test_rejected_without_warehouse_fails(self):
		po = fx.make_po([("HASR-YOGURT", 5)])
		self.assertRaises(
			frappe.ValidationError,
			erp.create_draft_purchase_receipt,
			po.name,
			[{"po_item": po.items[0].name, "qty": 4, "rejected_qty": 1}],
		)

	def test_item_details_from_adapter(self):
		details = erp.get_item_details("HASR-MILK")
		self.assertEqual(details["hasr_storage"], "Chilled")
		self.assertEqual(details["shelf_life_in_days"], 120)
		self.assertIn({"uom": "Box", "conversion_factor": 12.0}, [dict(u) for u in details["uoms"]])
		self.assertEqual({b.barcode for b in details["barcodes"]}, {fx.MILK_UNIT, fx.MILK_CASE})
		self.assertEqual(details["description"], "UHT full-fat cow's milk in a 1 L carton.")
