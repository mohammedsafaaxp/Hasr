"""Whitelisted receiving API for the phone (Hasr Counter) and the review screen (Hasr Supervisor)."""

import frappe

from hasr import receiving
from hasr.api import parse_json_arg
from hasr.permissions import require_counter, require_supervisor


@frappe.whitelist()
def list_open_orders(warehouse=None, search=None):
	require_counter()
	return receiving.list_open_orders(warehouse=warehouse or None, search=(search or "").strip() or None)


@frappe.whitelist(methods=["POST"])
def start_session(purchase_order):
	require_counter()
	return receiving.session_payload(receiving.start_session(purchase_order))


@frappe.whitelist()
def get_session(name):
	require_counter()
	return receiving.session_payload(receiving.get_session_doc(name))


@frappe.whitelist()
def my_sessions():
	require_counter()
	return frappe.get_all(
		"Hasr Receiving Session",
		filters={"received_by": frappe.session.user, "status": ["in", ["Open", "Sent Back"]]},
		fields=["name", "purchase_order", "supplier", "status", "shipment_no", "modified"],
		order_by="modified desc",
	)


@frappe.whitelist(methods=["POST"])
def set_line(session, po_item, received_qty, rejected_qty=0, batches=None):
	require_counter()
	doc = receiving.set_line(session, po_item, received_qty, rejected_qty, parse_json_arg(batches))
	return receiving.session_payload(doc)


@frappe.whitelist(methods=["POST"])
def finish_session(session, supplier_delivery_note=None, remaining_expected=None):
	require_counter()
	return receiving.session_payload(receiving.finish_session(session, supplier_delivery_note, remaining_expected))


@frappe.whitelist(methods=["POST"])
def cancel_session(session):
	require_counter()
	return receiving.session_payload(receiving.cancel_session(session))


@frappe.whitelist(methods=["POST"])
def report_unknown_barcode(session, barcode, qty=1, note=None, photo=None, client_uuid=None):
	require_counter()
	doc = receiving.report_unknown_barcode(session, barcode, qty, note, photo, client_uuid)
	return {"name": doc.name, "barcode": doc.barcode, "qty": doc.qty, "status": doc.status}


# ---------------------------------------------------------------- supervisor


@frappe.whitelist()
def get_review(session):
	require_supervisor()
	return receiving.get_review(session)


@frappe.whitelist(methods=["POST"])
def decide_line(session, po_item, decision):
	require_supervisor()
	return receiving.session_payload(receiving.decide_line(session, po_item, decision))


@frappe.whitelist(methods=["POST"])
def approve(session, decisions=None, submit=0):
	require_supervisor()
	doc = receiving.approve(session, parse_json_arg(decisions, {}), frappe.utils.cint(submit))
	return receiving.session_payload(doc)


@frappe.whitelist(methods=["POST"])
def send_back(session, note=None):
	require_supervisor()
	return receiving.session_payload(receiving.send_back(session, note))


@frappe.whitelist(methods=["POST"])
def link_unknown_barcode(name, item_code, uom=None):
	require_supervisor()
	doc = receiving.link_unknown_barcode(name, item_code, uom or None)
	return {"name": doc.name, "status": doc.status, "linked_item": doc.linked_item}


@frappe.whitelist(methods=["POST"])
def dismiss_unknown_barcode(name):
	require_supervisor()
	doc = receiving.dismiss_unknown_barcode(name)
	return {"name": doc.name, "status": doc.status}
