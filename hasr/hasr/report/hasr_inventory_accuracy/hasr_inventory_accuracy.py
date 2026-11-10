# Copyright (c) 2026, hasr contributors
# License: GNU General Public License v3. See LICENSE
"""Inventory record accuracy (IRA): the share of counted lines whose system balance was within tolerance."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate

from hasr.permissions import get_allowed_warehouses


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.get("group_by")
	if group_by not in ("Warehouse", "ABC Class", "Month"):
		group_by = "Warehouse"
	rows = data(filters, group_by)
	return columns(group_by), rows, None, chart(rows, group_by)


def columns(group_by):
	first = {
		"Warehouse": {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 200},
		"ABC Class": {"fieldname": "abc_class", "label": _("ABC Class"), "fieldtype": "Data", "width": 100},
		"Month": {"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 100},
	}[group_by]
	return [
		first,
		{"fieldname": "counts", "label": _("Counts"), "fieldtype": "Int", "width": 80},
		{"fieldname": "lines", "label": _("Lines Counted"), "fieldtype": "Int", "width": 110},
		{"fieldname": "accurate", "label": _("Within Tolerance"), "fieldtype": "Int", "width": 120},
		{"fieldname": "ira", "label": _("Accuracy (%)"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "gain_value", "label": _("Gain"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "loss_value", "label": _("Loss"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "net_value", "label": _("Net Difference"), "fieldtype": "Currency", "width": 130},
	]


def data(filters, group_by):
	conditions = ["s.status = 'Approved'", "date(s.approved_at) between %(from_date)s and %(to_date)s"]
	values = {
		"from_date": filters.get("from_date") or add_days(nowdate(), -90),
		"to_date": filters.get("to_date") or nowdate(),
	}
	if filters.get("company"):
		conditions.append("s.company = %(company)s")
		values["company"] = filters.company
	if filters.get("warehouse"):
		conditions.append("s.warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse
	allowed = get_allowed_warehouses()
	if allowed is not None:
		conditions.append("s.warehouse in %(allowed)s")
		values["allowed"] = tuple(allowed) or ("",)
	key = {
		"Warehouse": "s.warehouse",
		"ABC Class": "coalesce(nullif(l.abc_class, ''), 'C')",
		"Month": "date_format(s.approved_at, '%%Y-%%m')",
	}[group_by]
	fieldname = {"Warehouse": "warehouse", "ABC Class": "abc_class", "Month": "month"}[group_by]
	rows = frappe.db.sql(
		f"""
		select {key} as grp, count(distinct s.name) as counts, count(*) as line_count,
			sum(l.within_tolerance) as accurate,
			sum(case when l.variance_value > 0 then l.variance_value else 0 end) as gain_value,
			sum(case when l.variance_value < 0 then l.variance_value else 0 end) as loss_value
		from `tabHasr Count Line` l
		join `tabHasr Count Session` s on s.name = l.parent and l.parenttype = 'Hasr Count Session'
		where {" and ".join(conditions)} and (l.counted = 1 or l.recounted = 1 or l.system_qty != 0)
		group by grp order by grp
		""",
		values,
		as_dict=True,
	)
	return [
		{
			fieldname: r.grp,
			"counts": r.counts,
			"lines": r.line_count,
			"accurate": flt(r.accurate),
			"ira": flt(r.accurate) / r.line_count * 100 if r.line_count else 0,
			"gain_value": flt(r.gain_value),
			"loss_value": flt(r.loss_value),
			"net_value": flt(r.gain_value) + flt(r.loss_value),
		}
		for r in rows
	]


def chart(rows, group_by):
	if not rows:
		return None
	fieldname = {"Warehouse": "warehouse", "ABC Class": "abc_class", "Month": "month"}[group_by]
	return {
		"data": {
			"labels": [r[fieldname] for r in rows],
			"datasets": [{"name": _("Accuracy (%)"), "values": [round(r["ira"], 1) for r in rows]}],
		},
		"type": "bar",
		"colors": ["#171717"],
	}
