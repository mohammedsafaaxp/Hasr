"""Test bootstrap that needs ERPNext internals (kept here so tests never import erpnext directly)."""

import frappe
from frappe.utils import now_datetime


def before_tests():
	try:
		# v15
		from erpnext.setup.utils import before_tests as erpnext_before_tests
	except ImportError:
		# VERIFIED: v16 removed erpnext.setup.utils.before_tests (its suite bootstraps through
		# erpnext.tests.utils instead), so complete the setup wizard the same way v15 did.
		erpnext_before_tests = _complete_setup

	erpnext_before_tests()


def _complete_setup():
	frappe.clear_cache()
	if not frappe.db.a_row_exists("Company"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = now_datetime().year
		setup_complete(
			{
				"currency": "USD",
				"full_name": "Test User",
				"company_name": "Wind Power LLC",
				"timezone": "America/New_York",
				"company_abbr": "WP",
				"industry": "Manufacturing",
				"country": "United States",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@erpnext.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)
	frappe.db.commit()
