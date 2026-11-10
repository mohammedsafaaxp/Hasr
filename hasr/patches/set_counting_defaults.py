"""Counting settings that had no default before 1.0 were saved as 0 on sites that already had Hasr Settings:
a stock freeze then never expires and the supervisor is never asked for test counts. The fields were hidden
until 1.0, so a 0 here was never somebody's choice."""

import frappe

DEFAULTS = {"freeze_max_hours": 24, "test_count_sample_pct": 10}


def execute():
	for field, value in DEFAULTS.items():
		if not frappe.utils.flt(frappe.db.get_single_value("Hasr Settings", field)):
			frappe.db.set_single_value("Hasr Settings", field, value)
	frappe.clear_document_cache("Hasr Settings", "Hasr Settings")
