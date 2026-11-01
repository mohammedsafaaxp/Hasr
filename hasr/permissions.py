import frappe
from frappe import _

COUNTER_ROLES = ("Hasr Counter", "Hasr Supervisor", "System Manager")
SUPERVISOR_ROLES = ("Hasr Supervisor", "System Manager")


def has_any_role(roles, user=None) -> bool:
	return bool(set(roles) & set(frappe.get_roles(user or frappe.session.user)))


def require_counter():
	if not has_any_role(COUNTER_ROLES):
		frappe.throw(_("You need the Hasr Counter role to use hasr."), frappe.PermissionError)


def approver_roles() -> tuple[str, ...]:
	"""Roles from Hasr Settings → Roles That Can Approve (Hasr Supervisor when empty); System Manager always."""
	rows = frappe.get_cached_doc("Hasr Settings").get("approver_roles") or []
	roles = [r.role for r in rows if r.role] or ["Hasr Supervisor"]
	return (*roles, "System Manager")


def require_supervisor():
	"""See every session and its review (supervisors and approvers)."""
	if not is_supervisor():
		frappe.throw(_("Only a Hasr Supervisor can do this."), frappe.PermissionError)


def is_supervisor(user=None) -> bool:
	return has_any_role((*SUPERVISOR_ROLES, *approver_roles()), user)


def is_approver(user=None) -> bool:
	return has_any_role(approver_roles(), user)


def require_approver():
	if not is_approver():
		frappe.throw(_("Your role cannot approve receipts. See Hasr Settings."), frappe.PermissionError)


def approval_block_reason(doc, user=None) -> str | None:
	"""Why `user` may not approve or decide on this session, or None. Segregation of duties + warehouses."""
	user = user or frappe.session.user
	if not is_approver(user):
		return _("Your role cannot approve receipts. See Hasr Settings.")
	if doc.received_by == user:
		return _("You received this shipment. Another approver has to approve it.")
	allowed = get_allowed_warehouses(user)
	if allowed is not None:
		missing = sorted({l.warehouse for l in doc.lines if l.warehouse and l.warehouse not in allowed})
		if missing:
			return _("You do not have access to these warehouses: {0}").format(", ".join(missing))
	return None


def check_approver(doc):
	reason = approval_block_reason(doc)
	if reason:
		frappe.throw(reason, frappe.PermissionError)


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
