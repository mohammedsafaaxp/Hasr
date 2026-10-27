// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

frappe.listview_settings["Hasr Receiving Session"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colors = {
			Open: "blue",
			"Pending Approval": "orange",
			Approved: "green",
			"Sent Back": "red",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
