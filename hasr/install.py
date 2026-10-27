import frappe

ROLES = ("Hasr Counter", "Hasr Supervisor")


def after_install():
	ensure_roles()


def after_migrate():
	ensure_roles()


def ensure_roles():
	"""Fixtures sync roles on migrate; this makes a fresh install work even before the first migrate."""
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
