"""Invented demo data to try hasr: bench --site <site> execute hasr.demo.setup

Creates items with barcodes, a supplier, two purchase orders to receive, some stock and a draft stock count.
Meant for a test site: it changes Stock Settings and adds stock. All names are invented.
"""

import frappe


def setup():
	from hasr.tests import fixtures as fx

	fx.setup_all()
	main = fx.warehouse("Hasr Main")
	fx.make_po([("HASR-MILK", 4, "Box", 12), ("HASR-YOGURT", 24), ("HASR-CREAM-B", 36)])
	fx.make_po([("HASR-CHEESE", 20), ("HASR-BUTTER", 30)], supplier_name="Riverside Foods")

	for item_code, qty, rate in (("HASR-MILK", 30, 900), ("HASR-CHEESE", 15, 4000), ("HASR-BUTTER", 12, 3500)):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": fx.company().name,
				"items": [{"item_code": item_code, "qty": qty, "basic_rate": rate, "t_warehouse": main}],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

	count = frappe.get_doc(
		{
			"doctype": "Hasr Count Session",
			"warehouse": main,
			"count_type": "Cycle",
			"entry_method": "Scan",
			"scope_type": "Items",
			"scope_items": [{"item_code": i} for i in ("HASR-MILK", "HASR-CHEESE", "HASR-BUTTER")],
			"zones": [{"zone_name": "Cold room", "counter": fx.COUNTER}],
			"note": "Demo count: open it in Desk and press Start count.",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	print(
		"Demo ready. Users (set a password in Desk): "
		f"{fx.COUNTER} (Hasr Counter), {fx.SUPERVISOR} and {fx.SUPERVISOR_2} (Hasr Supervisor). "
		f"Draft stock count: {count.name}."
	)
