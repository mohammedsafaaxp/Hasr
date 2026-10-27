import frappe
from frappe.translate import get_translations_from_apps


@frappe.whitelist(allow_guest=True)
def get_translations(lang=None):
	"""hasr's own strings for the phone app (the sign-in screen needs them before login)."""
	lang = (lang or frappe.local.lang or "en").split("-")[0].lower()
	if lang == "en" or not frappe.db.exists("Language", lang):
		return {}
	cache_key = f"hasr_translations:{lang}"
	messages = frappe.cache.get_value(cache_key)
	if messages is None:
		messages = get_translations_from_apps(lang, apps=["hasr"])
		frappe.cache.set_value(cache_key, messages)
	return messages


@frappe.whitelist(allow_guest=True)
def get_boot():
	user = frappe.session.user
	return {
		"user": user,
		"full_name": frappe.utils.get_fullname(user) if user != "Guest" else None,
		"lang": frappe.local.lang,
		"site_name": frappe.local.site,
		"version": frappe.get_attr("hasr.__version__"),
	}
