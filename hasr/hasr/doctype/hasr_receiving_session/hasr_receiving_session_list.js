// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

frappe.listview_settings["Hasr Receiving Session"] = {
	add_fields: ["status"],
	onload(listview) {
		listview.page.add_inner_button(__("Today's Shipments"), () => frappe.set_route("hasr-today"));
	},
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
