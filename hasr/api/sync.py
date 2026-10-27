import frappe
from frappe import _

from hasr import receiving
from hasr.api import parse_json_arg
from hasr.permissions import require_counter

MAX_BATCH = 500


@frappe.whitelist(methods=["POST"])
def push_scans(scans):
	"""Apply scans from the phone. Idempotent on each scan's client_uuid.

	Returns {"results": [{client_uuid, status: applied|duplicate|rejected, message, ...}], "lines": [...]}.
	"""
	require_counter()
	scans = parse_json_arg(scans, [])
	if not isinstance(scans, list):
		frappe.throw(_("scans must be a list."))
	if len(scans) > MAX_BATCH:
		frappe.throw(_("Send at most {0} scans at a time.").format(MAX_BATCH))
	return receiving.push_scans(scans)
