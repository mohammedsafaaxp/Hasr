import frappe

from hasr.permissions import COUNTER_ROLES, has_any_role


def has_app_permission():
	return has_any_role(COUNTER_ROLES)


def parse_json_arg(value, default=None):
	if value is None or value == "":
		return default
	if isinstance(value, str):
		return frappe.parse_json(value)
	return value
