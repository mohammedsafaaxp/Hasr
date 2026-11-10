// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

frappe.query_reports["Hasr Inventory Accuracy"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -90), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "group_by", label: __("Group By"), fieldtype: "Select", options: ["Warehouse", "ABC Class", "Month"], default: "Warehouse" },
	],
};
