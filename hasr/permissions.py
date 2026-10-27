import frappe
from frappe import _

COUNTER_ROLES = ("Hasr Counter", "Hasr Supervisor", "System Manager")
SUPERVISOR_ROLES = ("Hasr Supervisor", "System Manager")


def has_any_role(roles, user=None) -> bool:
	return bool(set(roles) & set(frappe.get_roles(user or frappe.session.user)))


def require_counter():
	if not has_any_role(COUNTER_ROLES):
		frappe.throw(_("You need the Hasr Counter role to use hasr."), frappe.PermissionError)


def require_supervisor():
	if not has_any_role(SUPERVISOR_ROLES):
		frappe.throw(_("Only a Hasr Supervisor can do this."), frappe.PermissionError)


def is_supervisor(user=None) -> bool:
	return has_any_role(SUPERVISOR_ROLES, user)


def get_allowed_warehouses(user=None) -> set[str] | None:
	"""Warehouses the user may work in, from ERPNext User Permissions. None means no restriction."""
	user = user or frappe.session.user
	perms = frappe.permissions.get_user_permissions(user).get("Warehouse")
	if not perms:
		return None
	return {p.get("doc") for p in perms if p.get("doc")}


def check_warehouse_access(warehouses, user=None):
	allowed = get_allowed_warehouses(user)
	if allowed is None:
		return
	if not set(filter(None, warehouses)) & allowed:
		frappe.throw(_("You do not have access to this warehouse."), frappe.PermissionError)
