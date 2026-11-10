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


MAX_QTY = 1e9


def parse_qty(value) -> float:
	"""A quantity from the phone or a Desk dialog: a finite number, never negative. Anything else is refused,
	so a typo is never saved as 0."""
	import math

	from frappe import _

	if isinstance(value, bool) or value is None:
		frappe.throw(_("Type a quantity."))
	if isinstance(value, str):
		value = value.strip().replace(",", "")
	try:
		qty = float(value)
	except (TypeError, ValueError):
		frappe.throw(_("{0} is not a quantity.").format(value))
	if not math.isfinite(qty) or qty > MAX_QTY:
		frappe.throw(_("{0} is not a quantity.").format(value))
	if qty < 0:
		frappe.throw(_("Quantities cannot be negative."))
	return qty


def is_write_conflict(e) -> bool:
	"""Two people saved the same record at the same moment (deadlock, or MariaDB's "record has changed")."""
	if isinstance(e, frappe.QueryDeadlockError | frappe.TimestampMismatchError):
		return True
	return bool(getattr(e, "args", None)) and e.args[0] in (1020, 1213)


def retry_on_conflict(doctype, arg="session", attempts=6):
	"""Run a whitelisted write again when it lost a race for its record.

	The second try locks the record before it reads anything, so it waits its turn and then sees the other
	person's change instead of failing.
	"""
	import functools
	import random
	import time

	def decorator(fn):
		@functools.wraps(fn)
		def wrapper(*args, **kwargs):
			for attempt in range(attempts):
				try:
					return fn(*args, **kwargs)
				except Exception as e:
					if not is_write_conflict(e) or attempt == attempts - 1:
						raise
					frappe.db.rollback()
					frappe.clear_messages()
					time.sleep(random.uniform(0.02, 0.08) * (attempt + 1))
					name = kwargs.get(arg) or (args[0] if args else None)
					if name and isinstance(name, str):
						frappe.db.sql(f"select name from `tab{doctype}` where name = %s for update", name)

		return wrapper

	return decorator
