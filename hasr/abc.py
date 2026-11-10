"""ABC classification per warehouse, from the value of what left it in the last 12 months (weekly job).

Items making up the first abc_a_share % of that value are A, up to abc_b_share % B, the rest C. Items with
stock that did not move are C. The class sets the count tolerance and how often an item is due for a count.
"""

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from hasr.erpnext_adapter import stock_count as erp_count

ABC = "Hasr ABC Class"


def recompute_abc_classes():
	for warehouse in erp_count.stock_warehouses():
		classify_warehouse(warehouse)


def classify_warehouse(warehouse: str) -> dict[str, str]:
	from hasr.counting import frequency_for

	settings = frappe.get_cached_doc("Hasr Settings")
	a_share = flt(settings.abc_a_share) or 80.0
	b_share = max(flt(settings.abc_b_share) or 95.0, a_share)
	usage = erp_count.annual_usage_value(warehouse)
	items = set(usage) | set(erp_count.items_with_stock(warehouse))
	if not items:
		return {}
	total = sum(usage.values())
	classes, running = {}, 0.0
	for item_code in sorted(items, key=lambda i: (-usage.get(i, 0.0), i)):
		value = usage.get(item_code, 0.0)
		if not value or not total:
			classes[item_code] = "C"
			continue
		# the item that crosses a cut-off still belongs to the class it starts in
		share = running / total * 100.0
		running += value
		classes[item_code] = "A" if share < a_share else "B" if share < b_share else "C"

	existing = {
		r.item_code: r
		for r in frappe.get_all(ABC, filters={"warehouse": warehouse}, fields=["name", "item_code", "last_counted_on"])
	}
	for item_code, abc_class in classes.items():
		row = existing.get(item_code)
		last = row.last_counted_on if row else None
		values = {
			"abc_class": abc_class,
			"annual_value": usage.get(item_code, 0.0),
			"next_due_on": add_days(getdate(last), frequency_for(abc_class)) if last else nowdate(),
		}
		if row:
			frappe.db.set_value(ABC, row.name, values)
		else:
			frappe.get_doc({"doctype": ABC, "item_code": item_code, "warehouse": warehouse, **values}).insert(
				ignore_permissions=True
			)
	return classes
