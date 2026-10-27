import frappe

no_cache = 1


def get_context(context):
	from hasr.api.i18n import get_boot

	context.no_cache = 1
	context.boot = {
		"csrf_token": frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else "",
		"hasr_boot": get_boot(),
	}
	return context
