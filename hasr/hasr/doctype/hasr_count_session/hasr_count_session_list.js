// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

frappe.listview_settings["Hasr Count Session"] = {
	add_fields: ["status", "freeze"],
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Counting: "blue",
			Recount: "orange",
			"Pending Approval": "orange",
			Approved: "green",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
