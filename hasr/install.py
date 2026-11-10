import frappe

ROLES = ("Hasr Counter", "Hasr Supervisor")


def after_install():
	ensure_roles()
	ensure_batch_access()


def after_migrate():
	ensure_roles()
	ensure_batch_access()


def ensure_roles():
	"""Fixtures sync roles on migrate; this makes a fresh install work even before the first migrate."""
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def ensure_batch_access():
	"""Supervisors read batches: a count's Stock Reconciliation checks the user's Batch permission (VERIFIED on
	v16), and ERPNext gives Batch to Item Manager only. Added once; an administrator may change it later."""
	role = "Hasr Supervisor"
	if not frappe.db.exists("DocType", "Batch") or not frappe.db.exists("Role", role):
		return
	for table in ("DocPerm", "Custom DocPerm"):
		if frappe.db.exists(table, {"parent": "Batch", "role": role}):
			return
	from frappe.permissions import add_permission

	add_permission("Batch", role, 0, "read")

