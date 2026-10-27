"""Receiving business logic. API modules check roles and parse input, then call into here."""

import base64
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from hasr import erpnext_adapter as erp
from hasr.hasr.doctype.hasr_receiving_session.hasr_receiving_session import EDITABLE_STATUSES, EPSILON
from hasr.permissions import check_warehouse_access, get_allowed_warehouses, is_supervisor

SESSION = "Hasr Receiving Session"
MAX_PHOTO_BYTES = 8 * 1024 * 1024
UUID_RE = re.compile(r"^[A-Za-z0-9:_\-]{8,64}$")


# ---------------------------------------------------------------- orders


def list_open_orders(warehouse=None, search=None):
	allowed = get_allowed_warehouses()
	if warehouse and allowed is not None and warehouse not in allowed:
		frappe.throw(_("You do not have access to this warehouse."), frappe.PermissionError)

	orders = erp.get_open_purchase_orders(
		warehouses=sorted(allowed) if allowed is not None else None, warehouse=warehouse, search=search
	)
	if not orders:
		return []

	sessions = frappe.get_all(
		SESSION,
		filters={"purchase_order": ["in", [o.name for o in orders]], "status": ["!=", "Cancelled"]},
		fields=["name", "purchase_order", "status", "received_by", "shipment_no"],
	)
	by_po = {}
	for s in sessions:
		by_po.setdefault(s.purchase_order, []).append(s)

	for order in orders:
		mine = by_po.get(order.name, [])
		order.shipments = len(mine)
		active = next((s for s in mine if s.status in EDITABLE_STATUSES), None)
		order.open_session = active.name if active else None
		order.open_session_by = active.received_by if active else None
		order.open_session_status = active.status if active else None
		order.pending_sessions = len([s for s in mine if s.status == "Pending Approval"])
	return orders


def in_flight_qty(purchase_order, exclude_session=None) -> dict[str, float]:
	"""Stock-UOM qty per PO line that other sessions will still add to ERPNext.

	Pending Approval sessions, and Approved sessions whose Purchase Receipt is still a draft, are not yet
	in Purchase Order Item.received_qty.
	"""
	rows = frappe.db.sql(
		"""
		select l.po_item, sum(l.received_qty + l.rejected_qty) as qty
		from `tabHasr Receiving Line` l
		join `tabHasr Receiving Session` s on s.name = l.parent
		left join `tabPurchase Receipt` pr on pr.name = s.purchase_receipt
		where s.purchase_order = %(po)s and s.name != %(exclude)s
		and (s.status = 'Pending Approval' or (s.status = 'Approved' and pr.docstatus = 0))
		group by l.po_item
		""",
		{"po": purchase_order, "exclude": exclude_session or ""},
		as_dict=True,
	)
	return {r.po_item: flt(r.qty) for r in rows}


# ---------------------------------------------------------------- sessions


def start_session(purchase_order):
	po = erp.get_purchase_order(purchase_order)
	if not po:
		frappe.throw(_("Purchase order {0} not found.").format(purchase_order), frappe.DoesNotExistError)
	if not erp.is_receivable(purchase_order):
		frappe.throw(_("Purchase order {0} is not open for receiving.").format(purchase_order))
	check_warehouse_access(erp.get_purchase_order_warehouses(purchase_order))

	existing = frappe.db.get_value(
		SESSION, {"open_lock": purchase_order}, ["name", "received_by"], as_dict=True
	)
	if existing:
		frappe.throw(
			_("Purchase order {0} already has an open receiving session {1} by {2}. Finish it first.").format(
				purchase_order, existing.name, existing.received_by
			),
			title=_("Session already open"),
		)

	in_flight = in_flight_qty(purchase_order)
	lines = []
	for row in erp.get_po_lines_with_remaining(purchase_order):
		already = flt(row.received_qty) + in_flight.get(row.po_item, 0.0)
		pending = max(flt(row.ordered_qty) - already, 0.0)
		if pending <= EPSILON:
			continue
		lines.append(
			{
				"po_item": row.po_item,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"stock_uom": row.stock_uom,
				"warehouse": row.warehouse,
				"ordered_qty": row.ordered_qty,
				"already_received_qty": already,
				"pending_qty": pending,
				"allowed_qty": row.allowed_qty,
			}
		)
	if not lines:
		frappe.throw(_("Everything on purchase order {0} has been received or is waiting for approval.").format(purchase_order))

	shipment_no = (
		frappe.db.count(SESSION, {"purchase_order": purchase_order, "status": ["!=", "Cancelled"]}) + 1
	)
	doc = frappe.get_doc(
		{
			"doctype": SESSION,
			"purchase_order": purchase_order,
			"supplier": po.supplier,
			"company": po.company,
			"warehouse": po.set_warehouse or lines[0]["warehouse"],
			"status": "Open",
			"shipment_no": shipment_no,
			"received_by": frappe.session.user,
			"started_at": now_datetime(),
			"lines": lines,
		}
	)
	try:
		doc.insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		# another phone opened the same order a moment ago; the open_lock unique index caught it
		frappe.throw(
			_("Purchase order {0} already has an open receiving session. Finish it first.").format(purchase_order),
			title=_("Session already open"),
		)
	return doc


def get_session_doc(name, for_update=False):
	if not frappe.db.exists(SESSION, name):
		frappe.throw(_("Receiving session {0} not found.").format(name), frappe.DoesNotExistError)
	if for_update:
		# serialize writers on the same session (two phones, or retries)
		frappe.db.sql("select name from `tabHasr Receiving Session` where name = %s for update", name)
	doc = frappe.get_doc(SESSION, name)
	if doc.received_by != frappe.session.user and not is_supervisor():
		frappe.throw(_("This receiving session belongs to {0}.").format(doc.received_by), frappe.PermissionError)
	return doc


def get_editable_session(name):
	doc = get_session_doc(name, for_update=True)
	if not doc.is_editable():
		frappe.throw(_("Session {0} is {1} and can no longer be changed.").format(doc.name, _(doc.status)))
	return doc


def session_payload(doc):
	items = {
		r.name: r
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", list({l.item_code for l in doc.lines}) or [""]]},
			fields=["name", "image", "has_batch_no"],
		)
	}
	barcodes = {}
	for b in frappe.get_all(
		"Item Barcode",
		filters={"parent": ["in", list(items) or [""]], "parenttype": "Item"},
		fields=["parent", "barcode", "uom"],
		order_by="idx asc",
	):
		barcodes.setdefault(b.parent, []).append({"barcode": b.barcode, "uom": b.uom})

	lines = []
	for l in doc.lines:
		item = items.get(l.item_code) or frappe._dict()
		lines.append(
			{
				"po_item": l.po_item,
				"idx": l.idx,
				"item_code": l.item_code,
				"item_name": l.item_name,
				"stock_uom": l.stock_uom,
				"image": item.image,
				"has_batch_no": item.has_batch_no,
				"barcodes": barcodes.get(l.item_code, []),
				"uoms": _line_uoms(l.item_code, l.stock_uom),
				"ordered_qty": flt(l.ordered_qty),
				"already_received_qty": flt(l.already_received_qty),
				"pending_qty": flt(l.pending_qty),
				"allowed_qty": flt(l.allowed_qty),
				"received_qty": flt(l.received_qty),
				"rejected_qty": flt(l.rejected_qty),
				"over_allowance_state": l.over_allowance_state,
			}
		)
	unknown = frappe.get_all(
		"Hasr Unknown Barcode",
		filters={"session_doctype": SESSION, "session": doc.name},
		fields=["name", "barcode", "qty", "note", "status", "photo", "linked_item"],
		order_by="creation asc",
	)
	po = erp.get_purchase_order(doc.purchase_order) or {}
	return {
		"name": doc.name,
		"purchase_order": doc.purchase_order,
		"supplier": doc.supplier,
		"supplier_name": po.get("supplier_name") or doc.supplier,
		"company": doc.company,
		"warehouse": doc.warehouse,
		"status": doc.status,
		"shipment_no": doc.shipment_no,
		"received_by": doc.received_by,
		"started_at": doc.started_at,
		"finished_at": doc.finished_at,
		"supplier_delivery_note": doc.supplier_delivery_note,
		"remaining_expected": doc.remaining_expected,
		"review_note": doc.review_note,
		"purchase_receipt": doc.purchase_receipt,
		"editable": doc.is_editable() and doc.received_by == frappe.session.user,
		"lines": lines,
		"unknown_barcodes": unknown,
	}


def _line_uoms(item_code, stock_uom):
	uoms = [{"uom": stock_uom, "conversion_factor": 1.0}]
	for row in frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "parenttype": "Item", "uom": ["!=", stock_uom]},
		fields=["uom", "conversion_factor"],
		order_by="idx asc",
	):
		uoms.append({"uom": row.uom, "conversion_factor": flt(row.conversion_factor)})
	return uoms


def set_line(session, po_item, received_qty, rejected_qty=0, batches=None):
	doc = get_editable_session(session)
	line = doc.get_line(po_item)
	received_qty, rejected_qty = flt(received_qty), flt(rejected_qty)
	if received_qty < 0 or rejected_qty < 0:
		frappe.throw(_("Quantities cannot be negative."))
	doc.recompute_line(line)
	line.manual_adjust_qty = received_qty - flt(line.scanned_qty)
	line.rejected_qty = rejected_qty
	if batches is not None:
		line.batches_json = frappe.as_json(batches)  # used from milestone 0.2
	doc.recompute_line(line)
	doc.save(ignore_permissions=True)
	return doc


def finish_session(session, supplier_delivery_note=None, remaining_expected=None):
	doc = get_editable_session(session)
	if doc.received_by != frappe.session.user and not is_supervisor():
		frappe.throw(_("Only {0} can finish this session.").format(doc.received_by), frappe.PermissionError)
	has_qty = any(flt(l.received_qty) or flt(l.rejected_qty) for l in doc.lines)
	has_unknown = frappe.db.exists(
		"Hasr Unknown Barcode", {"session_doctype": SESSION, "session": doc.name, "status": "Open"}
	)
	if not has_qty and not has_unknown:
		frappe.throw(_("Scan at least one item before sending the shipment for review."))
	if remaining_expected and remaining_expected not in ("Still coming", "Supplier will not send"):
		frappe.throw(_("Invalid value for remaining quantity."))
	if supplier_delivery_note is not None:
		doc.supplier_delivery_note = (supplier_delivery_note or "").strip()[:140] or None
	if remaining_expected:
		doc.remaining_expected = remaining_expected
	doc.status = "Pending Approval"
	doc.finished_at = now_datetime()
	doc.save(ignore_permissions=True)
	return doc


def cancel_session(session):
	doc = get_session_doc(session, for_update=True)
	if doc.status not in ("Open", "Sent Back", "Pending Approval"):
		frappe.throw(_("Session {0} is {1} and cannot be cancelled.").format(doc.name, _(doc.status)))
	if doc.status == "Pending Approval" and not is_supervisor():
		frappe.throw(_("Only a Hasr Supervisor can cancel a session waiting for approval."), frappe.PermissionError)
	doc.status = "Cancelled"
	doc.save(ignore_permissions=True)
	return doc


# ---------------------------------------------------------------- scans


def push_scans(scans):
	"""Apply a list of scans; idempotent on client_uuid. Returns per-scan results and touched lines."""
	results, touched = [], {}
	for scan in scans or []:
		scan = frappe._dict(scan)
		savepoint = "hasr_scan"
		frappe.db.savepoint(savepoint)
		try:
			result = _apply_scan(scan, touched)
		except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
			# a concurrent request logged the same client_uuid first
			frappe.db.rollback(save_point=savepoint)
			frappe.clear_messages()
			result = _duplicate_result(scan.client_uuid)
		except frappe.ValidationError as e:
			frappe.db.rollback(save_point=savepoint)
			frappe.clear_messages()
			result = {"client_uuid": scan.client_uuid, "status": "rejected", "code": "invalid", "message": str(e)}
		results.append(result)

	lines = []
	for doc in touched.values():
		doc.save(ignore_permissions=True)
		lines.extend(session_payload(doc)["lines"])
	return {"results": results, "lines": lines}


def _duplicate_result(client_uuid):
	prev = frappe.db.get_value(
		"Hasr Scan", {"client_uuid": client_uuid}, ["status", "message", "po_item", "item_code"], as_dict=True
	) or {}
	return {
		"client_uuid": client_uuid,
		"status": "duplicate",
		"original_status": (prev.get("status") or "").lower(),
		"message": prev.get("message") or _("Already received."),
		"po_item": prev.get("po_item"),
		"item_code": prev.get("item_code"),
	}


def _apply_scan(scan, touched):
	uuid = (scan.client_uuid or "").strip()
	if not UUID_RE.match(uuid):
		return {"client_uuid": uuid, "status": "rejected", "code": "invalid", "message": _("Missing or invalid scan id.")}
	if frappe.db.exists("Hasr Scan", {"client_uuid": uuid}):
		return _duplicate_result(uuid)
	if (scan.session_type or "Receiving") != "Receiving":
		return {"client_uuid": uuid, "status": "rejected", "code": "invalid", "message": _("Counting arrives in a later version.")}

	doc = touched.get(scan.session)
	if not doc:
		doc = get_editable_session(scan.session)
		if doc.received_by != frappe.session.user and not is_supervisor():
			frappe.throw(_("This receiving session belongs to {0}.").format(doc.received_by), frappe.PermissionError)
		touched[doc.name] = doc

	if scan.undo_of:
		return _apply_undo(doc, scan, uuid)

	resolved = erp.resolve_barcode(scan.barcode)
	if not resolved:
		msg = _("Barcode {0} is not linked to any item.").format(scan.barcode)
		_log_scan(doc, scan, uuid, "Rejected", msg)
		return {"client_uuid": uuid, "status": "rejected", "code": "unknown_barcode", "barcode": scan.barcode, "message": msg}

	if resolved.disabled:
		msg = _("Item {0} is disabled.").format(resolved.item_code)
		_log_scan(doc, scan, uuid, "Rejected", msg, resolved)
		return {"client_uuid": uuid, "status": "rejected", "code": "disabled", "message": msg, "item_code": resolved.item_code}

	return apply_item_qty(doc, scan, uuid, resolved, qty=flt(scan.qty) or 1.0)


def apply_item_qty(doc, scan, uuid, resolved, qty):
	line = _match_line(doc, resolved.item_code, scan.po_item)
	if not line:
		on_po = frappe.db.exists(
			"Purchase Order Item", {"parent": doc.purchase_order, "item_code": resolved.item_code}
		)
		if on_po:
			msg = _("{0} is already fully received on purchase order {1}.").format(
				resolved.item_name or resolved.item_code, doc.purchase_order
			)
			code = "fully_received"
		else:
			msg = _("{0} is not on purchase order {1}. It was not counted.").format(
				resolved.item_name or resolved.item_code, doc.purchase_order
			)
			code = "not_on_po"
		_log_scan(doc, scan, uuid, "Rejected", msg, resolved)
		return {"client_uuid": uuid, "status": "rejected", "code": code, "message": msg, "item_code": resolved.item_code}

	cf = flt(resolved.conversion_factor)
	if cf <= 0:
		msg = _("No conversion factor from {0} to {1} for {2}.").format(resolved.uom, resolved.stock_uom, resolved.item_code)
		_log_scan(doc, scan, uuid, "Rejected", msg, resolved)
		return {"client_uuid": uuid, "status": "rejected", "code": "no_conversion", "message": msg}
	if qty <= 0:
		return {"client_uuid": uuid, "status": "rejected", "code": "invalid", "message": _("Quantity must be greater than zero.")}

	qty_stock = qty * cf
	_log_scan(doc, scan, uuid, "Applied", None, resolved, po_item=line.po_item, qty=qty, qty_stock=qty_stock)
	doc.recompute_line(line)
	return {
		"client_uuid": uuid,
		"status": "applied",
		"po_item": line.po_item,
		"item_code": resolved.item_code,
		"item_name": resolved.item_name,
		"uom": resolved.uom,
		"qty": qty,
		"conversion_factor": cf,
		"qty_stock_uom": qty_stock,
		"received_qty": flt(line.received_qty),
		"over_allowance_state": line.over_allowance_state,
		"message": _("Added {0} {1} of {2}").format(f"{qty:g}", _(resolved.uom), resolved.item_name),
	}


def _match_line(doc, item_code, po_item=None):
	candidates = [l for l in doc.lines if l.item_code == item_code and (not po_item or l.po_item == po_item)]
	if not candidates:
		return None
	for line in candidates:
		if flt(line.received_qty) + flt(line.rejected_qty) < flt(line.pending_qty) - EPSILON:
			return line
	return candidates[-1]


def _apply_undo(doc, scan, uuid):
	original = frappe.db.get_value(
		"Hasr Scan",
		{"client_uuid": scan.undo_of, "session": doc.name, "session_doctype": SESSION},
		["name", "status", "undone", "po_item"],
		as_dict=True,
	)
	if not original or original.status != "Applied" or original.undone:
		return {"client_uuid": uuid, "status": "rejected", "code": "nothing_to_undo", "message": _("Nothing to undo.")}
	frappe.db.set_value("Hasr Scan", original.name, "undone", 1)
	_log_scan(doc, scan, uuid, "Undo", None, po_item=original.po_item)
	line = doc.get_line(original.po_item)
	doc.recompute_line(line)
	return {
		"client_uuid": uuid,
		"status": "applied",
		"undo_of": scan.undo_of,
		"po_item": line.po_item,
		"received_qty": flt(line.received_qty),
		"over_allowance_state": line.over_allowance_state,
		"message": _("Scan undone."),
	}


def _log_scan(doc, scan, uuid, status, message, resolved=None, po_item=None, qty=None, qty_stock=None):
	resolved = resolved or frappe._dict()
	frappe.get_doc(
		{
			"doctype": "Hasr Scan",
			"client_uuid": uuid,
			"status": status,
			"message": message,
			"session_type": "Receiving",
			"session_doctype": SESSION,
			"session": doc.name,
			"po_item": po_item,
			"barcode": (scan.barcode or "")[:140] or None,
			"item_code": resolved.get("item_code"),
			"uom": resolved.get("uom"),
			"qty": qty,
			"conversion_factor": resolved.get("conversion_factor"),
			"qty_stock_uom": qty_stock,
			"scanned_at": _device_time(scan.scanned_at),
			"device_id": (scan.device_id or "")[:140] or None,
			"user": frappe.session.user,
			"undo_of": scan.undo_of,
		}
	).insert(ignore_permissions=True)


def _device_time(value):
	if not value:
		return now_datetime()
	try:
		return frappe.utils.get_datetime(str(value).replace("T", " ").replace("Z", "")[:26])
	except Exception:
		return now_datetime()


# ---------------------------------------------------------------- unknown barcodes


def report_unknown_barcode(session, barcode, qty=1, note=None, photo=None, client_uuid=None):
	doc = get_editable_session(session)
	barcode = (barcode or "").strip()
	if not barcode:
		frappe.throw(_("Barcode is required."))
	if erp.resolve_barcode(barcode):
		frappe.throw(_("Barcode {0} is linked to an item now. Scan it again.").format(barcode))
	if client_uuid:
		existing = frappe.db.get_value("Hasr Unknown Barcode", {"client_uuid": client_uuid})
		if existing:
			return frappe.get_doc("Hasr Unknown Barcode", existing)

	unknown = frappe.get_doc(
		{
			"doctype": "Hasr Unknown Barcode",
			"barcode": barcode[:140],
			"session_doctype": SESSION,
			"session": doc.name,
			"qty": max(flt(qty), 0) or 1,
			"note": (note or "").strip()[:1000] or None,
			"status": "Open",
			"reported_by": frappe.session.user,
			"client_uuid": client_uuid or None,
		}
	).insert(ignore_permissions=True)

	if photo:
		file_doc = _save_photo(photo, unknown)
		unknown.db_set("photo", file_doc.file_url)
	return unknown


def _save_photo(data_url, unknown):
	match = re.match(r"^data:(image/(?:jpeg|png|webp));base64,(.+)$", data_url or "", re.S)
	if not match:
		frappe.throw(_("The photo must be a JPEG, PNG or WebP image."))
	content = base64.b64decode(match.group(2))
	if len(content) > MAX_PHOTO_BYTES:
		frappe.throw(_("The photo is too large."))
	ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[match.group(1)]
	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"unknown-{frappe.scrub(unknown.barcode)}.{ext}",
			"content": content,
			"attached_to_doctype": unknown.doctype,
			"attached_to_name": unknown.name,
			"attached_to_field": "photo",
			"is_private": 1,
		}
	).insert(ignore_permissions=True)


def link_unknown_barcode(name, item_code, uom=None):
	unknown = frappe.get_doc("Hasr Unknown Barcode", name)
	if unknown.status != "Open":
		frappe.throw(_("Unknown barcode {0} is already {1}.").format(unknown.barcode, _(unknown.status)))
	doc = get_session_doc(unknown.session, for_update=True)
	if doc.status not in (*EDITABLE_STATUSES, "Pending Approval"):
		frappe.throw(_("Session {0} is {1} and can no longer be changed.").format(doc.name, _(doc.status)))
	if not any(l.item_code == item_code for l in doc.lines):
		frappe.throw(
			_("{0} is not an open line on purchase order {1}. Dismiss the barcode instead.").format(
				item_code, doc.purchase_order
			)
		)

	erp.add_item_barcode(item_code, unknown.barcode, uom)
	resolved = erp.resolve_barcode(unknown.barcode)
	scan = frappe._dict(barcode=unknown.barcode, scanned_at=unknown.creation, device_id="supervisor")
	result = apply_item_qty(doc, scan, f"unknown:{unknown.name}", resolved, qty=flt(unknown.qty) or 1)
	if result["status"] != "applied":
		frappe.throw(result["message"])
	doc.save(ignore_permissions=True)

	unknown.status = "Linked"
	unknown.linked_item = item_code
	unknown.linked_uom = resolved.uom
	unknown.save(ignore_permissions=True)
	return unknown


def dismiss_unknown_barcode(name):
	unknown = frappe.get_doc("Hasr Unknown Barcode", name)
	if unknown.status != "Open":
		frappe.throw(_("Unknown barcode {0} is already {1}.").format(unknown.barcode, _(unknown.status)))
	unknown.status = "Dismissed"
	unknown.save(ignore_permissions=True)
	return unknown


# ---------------------------------------------------------------- supervisor


def decide_line(session, po_item, decision):
	doc = get_session_doc(session, for_update=True)
	_require_pending(doc)
	_apply_decision(doc, doc.get_line(po_item), decision)
	doc.save(ignore_permissions=True)
	return doc


def _apply_decision(doc, line, decision):
	if decision not in ("Accept", "Cap"):
		frappe.throw(_("Decision must be Accept or Cap."))
	doc.recompute_line(line)
	if line.over_allowance_state not in ("Over", "Accepted", "Capped"):
		frappe.throw(_("{0} is within the allowance; nothing to decide.").format(line.item_name or line.item_code))
	if decision == "Accept":
		line.over_allowance_state = "Accepted"
	else:
		# keep received + rejected within what is still ordered
		target = max(flt(line.pending_qty) - flt(line.rejected_qty), 0.0)
		line.manual_adjust_qty = target - flt(line.scanned_qty)
		line.over_allowance_state = "Capped"
		doc.recompute_line(line)


def _require_pending(doc):
	if doc.status != "Pending Approval":
		frappe.throw(_("Session {0} is {1}, not waiting for approval.").format(doc.name, _(doc.status)))


def approve(session, decisions=None, submit=False):
	doc = get_session_doc(session, for_update=True)
	_require_pending(doc)

	if not frappe.has_permission("Purchase Receipt", "create"):
		frappe.throw(_("You need permission to create Purchase Receipts."), frappe.PermissionError)
	if submit and not frappe.has_permission("Purchase Receipt", "submit"):
		frappe.throw(_("You need permission to submit Purchase Receipts."), frappe.PermissionError)

	for po_item, decision in (decisions or {}).items():
		_apply_decision(doc, doc.get_line(po_item), decision)
	for line in doc.lines:
		doc.recompute_line(line)

	undecided = [l.item_name or l.item_code for l in doc.lines if l.over_allowance_state == "Over"]
	if undecided:
		frappe.throw(
			_("Decide on the over-receipt first: {0}").format(", ".join(undecided)), title=_("Needs your decision")
		)
	if frappe.db.exists("Hasr Unknown Barcode", {"session_doctype": SESSION, "session": doc.name, "status": "Open"}):
		frappe.throw(_("Link or dismiss the unknown barcodes first."), title=_("Needs your decision"))

	settings = frappe.get_cached_doc("Hasr Settings")
	pr = erp.create_draft_purchase_receipt(
		doc.purchase_order,
		[
			{"po_item": l.po_item, "qty": l.received_qty, "rejected_qty": l.rejected_qty}
			for l in doc.lines
		],
		supplier_delivery_note=doc.supplier_delivery_note,
		default_rejected_warehouse=settings.default_rejected_warehouse,
		remarks=_("Received with hasr, session {0}").format(doc.name),
	)
	doc.purchase_receipt = pr.name
	doc.status = "Approved"
	doc.save(ignore_permissions=True)

	if cint(submit):
		erp.submit_purchase_receipt(pr.name)
	return doc


def send_back(session, note=None):
	doc = get_session_doc(session, for_update=True)
	_require_pending(doc)
	doc.status = "Sent Back"
	doc.review_note = (note or "").strip() or None
	for line in doc.lines:
		if line.over_allowance_state == "Accepted":
			line.over_allowance_state = "Over"
	try:
		doc.save(ignore_permissions=True)
	except frappe.UniqueValidationError:
		frappe.throw(_("Another shipment of this purchase order is open. Finish or cancel it first."))
	return doc


def get_review(session):
	doc = get_session_doc(session)
	payload = session_payload(doc)
	scans = frappe.db.sql(
		"""select status, count(*) as n from `tabHasr Scan`
		where session_doctype = %s and session = %s group by status""",
		(SESSION, doc.name),
		as_dict=True,
	)
	payload["scan_counts"] = {s.status: s.n for s in scans}
	payload["allowance"] = {l.po_item: erp.get_over_receipt_allowance(l.item_code) for l in doc.lines}
	return payload
