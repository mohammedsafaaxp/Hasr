"""Whitelisted stock count API: the phone (counters) and the count's Desk form (supervisors)."""

import frappe

from hasr import counting
from hasr.api import parse_json_arg, retry_on_conflict
from hasr.permissions import require_approver, require_counter, require_supervisor

# ---------------------------------------------------------------- phone


@frappe.whitelist()
def my_counts():
	require_counter()
	return counting.my_counts()


@frappe.whitelist()
def get_count(name):
	require_counter()
	return counting.get_count(name)


@frappe.whitelist()
def identify(session, code):
	require_counter()
	return counting.identify(session, code)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def set_count(session, item_code, qty, batch_no=None, client_uuid=None, counted_at=None):
	require_counter()
	return counting.set_count(session, item_code, qty, batch_no, client_uuid, counted_at)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def hand_over(session):
	require_counter()
	return counting.count_payload(counting.hand_over(session))


# ---------------------------------------------------------------- supervisor (Desk)


@frappe.whitelist()
def review(session):
	require_supervisor()
	return counting.review(session)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def start(session):
	require_supervisor()
	return counting.review(counting.start(session).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def close_counting(session):
	require_supervisor()
	return counting.review(counting.close_counting(session).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def assign_recount(session, user):
	require_supervisor()
	doc, refused = counting.assign_recount(session, user)
	return {**counting.review(doc.name), "refused": refused}


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def set_test_count(session, line, qty):
	require_supervisor()
	return counting.review(counting.set_test_count(session, line, qty).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def finish_review(session):
	require_supervisor()
	return counting.review(counting.finish_review(session).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def set_reasons(session, reasons):
	require_supervisor()
	return counting.review(counting.set_reasons(session, parse_json_arg(reasons, {})).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def approve(session, submit=0):
	require_approver()
	return counting.review(counting.approve(session, frappe.utils.cint(submit)).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def cancel(session):
	require_supervisor()
	return counting.review(counting.cancel(session).name)


@frappe.whitelist(methods=["POST"])
@retry_on_conflict("Hasr Count Session")
def release_freeze(session):
	require_supervisor()
	return counting.review(counting.manual_release(session).name)
