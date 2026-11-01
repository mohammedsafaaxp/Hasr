"""Supplier offers (free goods) as ERPNext Pricing Rules of the "Product" kind: buy X, get Y of the same item free."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def get_or_create_free_item_rule(
	supplier: str, company: str, item_code: str, paid_qty: float, free_qty: float, posting_date=None, note=None
) -> str:
	"""The Pricing Rule that explains free goods on a receipt.

	An active buying rule for this supplier and item that gives the same item free is reused. Otherwise one is
	created for the receipt date only (valid from and up to that day), so it records the offer without being
	applied to later purchases. It is created for the approver, who decided the receipt.
	"""
	day = getdate(posting_date or nowdate())
	found = frappe.db.sql(
		"""select pr.name from `tabPricing Rule` pr
		join `tabPricing Rule Item Code` i on i.parent = pr.name
		where pr.disable = 0 and pr.buying = 1 and pr.price_or_product_discount = 'Product'
			and pr.applicable_for = 'Supplier' and pr.supplier = %(supplier)s
			and i.item_code = %(item)s
			and (pr.same_item = 1 or pr.free_item = %(item)s)
			and (pr.company is null or pr.company = '' or pr.company = %(company)s)
			and (pr.valid_from is null or pr.valid_from <= %(day)s)
			and (pr.valid_upto is null or pr.valid_upto >= %(day)s)
		order by pr.priority desc, pr.modified desc limit 1""",
		{"supplier": supplier, "item": item_code, "company": company, "day": day},
	)
	if found:
		return found[0][0]

	rule = frappe.get_doc(
		{
			"doctype": "Pricing Rule",
			"title": _("{0}: {1} free with {2} {3}").format(supplier, frappe.format(free_qty), frappe.format(paid_qty), item_code)[:140],
			"apply_on": "Item Code",
			"items": [{"item_code": item_code}],
			"buying": 1,
			"selling": 0,
			"applicable_for": "Supplier",
			"supplier": supplier,
			"company": company,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"price_or_product_discount": "Product",
			"same_item": 1,
			"min_qty": flt(paid_qty),
			"free_qty": flt(free_qty),
			"free_item_rate": 0,
			"valid_from": day,
			"valid_upto": day,
			"rule_description": note,
		}
	)
	rule.insert(ignore_permissions=True)
	return rule.name


def make_free_row(pr, template_row, free_stock_qty: float, rule: str):
	"""A free row next to the paid one: same item and warehouse, price 0, in the stock unit, not linked to the
	purchase order (ERPNext counts only what was paid for against the order). The cost of the paid row is spread
	over all units in the moving average."""
	data = frappe._dict(template_row.as_dict(no_default_fields=True))
	for field in ("purchase_order", "purchase_order_item", "material_request", "material_request_item"):
		if field in data:
			data[field] = None
	row = pr.append("items", data)
	row.is_free_item = 1
	row.pricing_rules = rule
	row.uom = row.stock_uom
	row.conversion_factor = 1
	row.qty = row.received_qty = row.stock_qty = flt(free_stock_qty)
	if row.meta.has_field("received_stock_qty"):
		row.received_stock_qty = flt(free_stock_qty)
	row.rejected_qty = 0
	for field in ("rate", "price_list_rate", "base_rate", "base_price_list_rate", "amount", "base_amount", "net_rate", "net_amount", "discount_percentage", "discount_amount", "margin_rate_or_amount"):
		if row.meta.has_field(field):
			row.set(field, 0)
	row.allow_zero_valuation_rate = 1
	return row
