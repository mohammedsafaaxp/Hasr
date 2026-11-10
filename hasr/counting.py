"""Stock count business logic. API modules check roles and parse input, then call into here.

A count moves Draft → Counting → (Recount) → Pending Approval → Approved, or Cancelled.
- Counters count blind: the phone never receives a system quantity.
- Each zone has one counter; counts of all zones add up per item and batch.
- A line outside its tolerance is recounted once by someone who did not count it; the supervisor test-counts a
  sample of the lines within tolerance.
- Approval creates a Stock Reconciliation for the differences, with a reason for each one.
"""

import math
import random

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, flt, getdate, now_datetime, nowdate

from hasr import barcodes
from hasr.erpnext_adapter import stock_count as erp_count
from hasr.permissions import check_warehouse_access, get_allowed_warehouses, is_approver, is_supervisor

COUNT = "Hasr Count Session"
FREEZE = "Hasr Stock Freeze"
ABC = "Hasr ABC Class"
EPSILON = 1e-6
REASONS = ("Theft", "Damage", "Receiving error", "Picking error", "Unit of measure error", "Unknown", "Other")
RECOUNT_ZONE = "Recount"


def settings():
	return frappe.get_cached_doc("Hasr Settings")


def tolerance_for(abc_class: str | None) -> float:
	s = settings()
	return flt({"A": s.tolerance_a_pct, "B": s.tolerance_b_pct}.get(abc_class, s.tolerance_c_pct))


def frequency_for(abc_class: str | None) -> int:
	s = settings()
	return cint({"A": s.frequency_a_days, "B": s.frequency_b_days}.get(abc_class, s.frequency_c_days)) or 180


def key(item_code, batch_no=None):
	return (item_code, batch_no or "")


# ---------------------------------------------------------------- access


def get_count_doc(name, for_update=False):
	if not frappe.db.exists(COUNT, name):
		frappe.throw(_("Stock count {0} not found.").format(name), frappe.DoesNotExistError)
	if for_update:
		frappe.db.sql("select name from `tabHasr Count Session` where name = %s for update", name)
	return frappe.get_doc(COUNT, name)


def check_count_supervisor(doc):
	if not is_supervisor():
		frappe.throw(_("Only a Hasr Supervisor can do this."), frappe.PermissionError)
	allowed = get_allowed_warehouses()
	if allowed is not None and doc.warehouse not in allowed:
		frappe.throw(_("You do not have access to this warehouse."), frappe.PermissionError)


def counted_by_users(doc) -> set[str]:
	return {e.counted_by for e in doc.entries if e.round in ("Count", "Recount")} | {
		z.counter for z in doc.zones
	} | {l.recount_by for l in doc.lines if l.recount_by}


def approval_block_reason(doc, user=None) -> str | None:
	user = user or frappe.session.user
	if not is_approver(user):
		return _("Your role cannot approve stock counts. See Hasr Settings.")
	if user in counted_by_users(doc):
		return _("You counted in this stock count. Another approver has to approve it.")
	allowed = get_allowed_warehouses(user)
	if allowed is not None and doc.warehouse not in allowed:
		return _("You do not have access to this warehouse.")
	return None


def check_count_approver(doc):
	reason = approval_block_reason(doc)
	if reason:
		frappe.throw(reason, frappe.PermissionError)


def require_status(doc, *statuses):
	if doc.status not in statuses:
		frappe.throw(_("Stock count {0} is {1}.").format(doc.name, _(doc.status)))


def save(doc):
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


# ---------------------------------------------------------------- scope and lines


def scope_items(doc) -> list[str]:
	wh = doc.warehouse
	if doc.scope_type == "Warehouse":
		items = erp_count.items_with_stock(wh)
	elif doc.scope_type == "Item Group":
		in_group = set(erp_count.stock_items({"item_group": ["in", erp_count.item_group_with_children(doc.item_group)]}))
		items = [i for i in _items_known_in(wh) if i in in_group]
	elif doc.scope_type == "Brand":
		in_brand = set(erp_count.stock_items({"brand": doc.brand}))
		items = [i for i in _items_known_in(wh) if i in in_brand]
	elif doc.scope_type == "Items":
		items = [r.item_code for r in doc.scope_items]
	elif doc.scope_type == "ABC Due":
		items = abc_due_items(wh)
	elif doc.scope_type == "Problem Items":
		items = problem_items(wh)
	else:
		frappe.throw(_("Choose what to count."))
	stock = set(erp_count.stock_items({"name": ["in", list(items) or [""]]}))
	return sorted(i for i in dict.fromkeys(items) if i in stock)


def _items_known_in(warehouse) -> list[str]:
	return frappe.get_all("Bin", filters={"warehouse": warehouse}, pluck="item_code")


def abc_due_items(warehouse) -> list[str]:
	if not frappe.db.exists(ABC, {"warehouse": warehouse}):
		from hasr.abc import classify_warehouse

		classify_warehouse(warehouse)
	today = getdate(nowdate())
	due = [
		r.item_code
		for r in frappe.get_all(ABC, filters={"warehouse": warehouse}, fields=["item_code", "next_due_on"])
		if not r.next_due_on or getdate(r.next_due_on) <= today
	]
	classified = set(frappe.get_all(ABC, filters={"warehouse": warehouse}, pluck="item_code"))
	return due + [i for i in erp_count.items_with_stock(warehouse) if i not in classified]


def problem_items(warehouse) -> list[str]:
	"""A difference outside tolerance in an approved count of the last 180 days, or a negative balance."""
	recent = frappe.db.sql(
		"""
		select distinct l.item_code from `tabHasr Count Line` l
		join `tabHasr Count Session` s on s.name = l.parent
		where s.warehouse = %s and s.status = 'Approved' and s.approved_at >= %s and l.within_tolerance = 0
		""",
		(warehouse, add_days(nowdate(), -180)),
		pluck=True,
	)
	return list(recent) + erp_count.items_with_negative_stock(warehouse)


def abc_class_of(item_code, warehouse) -> str:
	return frappe.db.get_value(ABC, {"item_code": item_code, "warehouse": warehouse}, "abc_class") or "C"


def new_line(doc, item_code, batch_no=None, system_qty=0.0, added=False):
	item = frappe.get_cached_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
	abc_class = abc_class_of(item_code, doc.warehouse)
	return doc.append(
		"lines",
		{
			"item_code": item_code,
			"item_name": item.item_name,
			"batch_no": batch_no or None,
			"stock_uom": item.stock_uom,
			"abc_class": abc_class,
			"tolerance_pct": tolerance_for(abc_class),
			"system_qty": system_qty,
			"snapshot_at": now_datetime(),
			"valuation_rate": erp_count.valuation_rate(item_code, doc.warehouse),
			"added_by_counter": 1 if added else 0,
		},
	)


def build_lines(doc):
	doc.set("lines", [])
	for item_code in scope_items(doc):
		if frappe.get_cached_value("Item", item_code, "has_batch_no"):
			balances = erp_count.get_batch_balances(item_code, doc.warehouse)
			for batch_no, qty in sorted(balances.items()):
				new_line(doc, item_code, batch_no, qty)
			if not balances:
				new_line(doc, item_code)  # keeps the item in the count; a counted batch gets its own line
		else:
			new_line(doc, item_code, None, erp_count.get_balance(item_code, doc.warehouse))


def current_balance(doc, line) -> float:
	if line.batch_no:
		return erp_count.get_batch_balance(line.batch_no, doc.warehouse)
	return erp_count.get_balance(line.item_code, doc.warehouse)


def refresh_snapshot(doc, line):
	"""Without a freeze, the balance is taken when the item is counted, so movements before then do not count."""
	line.system_qty = current_balance(doc, line)
	line.snapshot_at = now_datetime()


# ---------------------------------------------------------------- supervisor: start, close, recount, approve


def start(name):
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Draft")
	if not doc.zones:
		frappe.throw(_("Add at least one zone with its counter."))
	for z in doc.zones:
		roles = set(frappe.get_roles(z.counter))
		if not roles & {"Hasr Counter", "Hasr Supervisor", "System Manager"}:
			frappe.throw(_("{0} needs the Hasr Counter role to count.").format(z.counter))
	build_lines(doc)
	if not doc.lines:
		frappe.throw(_("Nothing to count: no stock items match this scope in {0}.").format(doc.warehouse))
	doc.status = "Counting"
	doc.started_at = now_datetime()
	if doc.freeze:
		freeze_items(doc)
	save(doc)
	return doc


def freeze_items(doc):
	if not cint(settings().allow_freeze):
		frappe.throw(_("Stock freeze is turned off in Hasr Settings."))
	hours = cint(settings().freeze_max_hours)
	expires = add_to_date(now_datetime(), hours=hours) if hours > 0 else None
	items = [None] if doc.scope_type == "Warehouse" else sorted({l.item_code for l in doc.lines})
	for item_code in items:
		frappe.get_doc(
			{
				"doctype": FREEZE,
				"warehouse": doc.warehouse,
				"item_code": item_code,
				"count_session": doc.name,
				"active": 1,
				"frozen_at": now_datetime(),
				"expires_at": expires,
			}
		).insert(ignore_permissions=True)
	doc.frozen_until = expires
	from hasr.stock_freeze import clear_cache

	clear_cache()


def is_frozen(doc) -> bool:
	return bool(frappe.db.exists(FREEZE, {"count_session": doc.name, "active": 1}))


def release_freeze(name, by=None):
	freezes = frappe.get_all(FREEZE, filters={"count_session": name, "active": 1}, pluck="name")
	for f in freezes:
		frappe.db.set_value(FREEZE, f, {"active": 0, "released_at": now_datetime(), "released_by": by or frappe.session.user})
	if freezes:
		from hasr.stock_freeze import clear_cache

		clear_cache()
	return len(freezes)


def manual_release(name):
	doc = get_count_doc(name)
	check_count_supervisor(doc)
	release_freeze(name)
	return doc


def entry_total(doc, line, round_):
	k = key(line.item_code, line.batch_no)
	rows = [e for e in doc.entries if e.round == round_ and key(e.item_code, e.batch_no) == k]
	return sum(flt(e.qty) for e in rows), bool(rows)


def within_tolerance(line, qty) -> bool:
	allowed = flt(line.tolerance_pct) / 100.0 * abs(flt(line.system_qty))
	return abs(flt(qty) - flt(line.system_qty)) <= allowed + EPSILON


def close_counting(name):
	"""Counting ends: totals per line, what must be recounted, and the supervisor's test sample."""
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Counting")
	frozen = is_frozen(doc)
	for line in doc.lines:
		line.count_1_qty, line.counted = entry_total(doc, line, "Count")
		if not frozen and not line.counted:
			refresh_snapshot(doc, line)  # not found: compared with the balance now
		line.needs_recount = 0 if within_tolerance(line, line.count_1_qty) else 1
	pick_test_sample(doc)
	doc.closed_at = now_datetime()
	if any(l.needs_recount or l.test_sample for l in doc.lines):
		doc.status = "Recount"
	else:
		set_final(doc)
		doc.status = "Pending Approval"
	save(doc)
	return doc


def pick_test_sample(doc):
	pct = flt(settings().test_count_sample_pct)
	pool = [l for l in doc.lines if not l.needs_recount and l.counted and flt(l.count_1_qty) > 0]
	size = min(len(pool), math.ceil(len(pool) * pct / 100.0)) if pct > 0 else 0
	for line in random.SystemRandom().sample(pool, size):
		line.test_sample = 1


def assign_recount(name, user):
	"""Give the lines outside tolerance to `user`, who must not have counted them the first time."""
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Recount")
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found.").format(user))
	first = {}
	for e in doc.entries:
		if e.round == "Count":
			first.setdefault(key(e.item_code, e.batch_no), set()).add(e.counted_by)
	zone_counters = {z.counter for z in doc.zones}
	assigned, refused = 0, []
	for line in doc.lines:
		if not line.needs_recount or line.recounted:
			continue
		counted = first.get(key(line.item_code, line.batch_no)) or zone_counters
		if user in counted:
			refused.append(line.item_name or line.item_code)
			continue
		line.recount_by = user
		assigned += 1
	if not assigned and refused:
		frappe.throw(_("{0} counted these items the first time. Choose someone else.").format(user))
	save(doc)
	return doc, refused


def set_test_count(name, line_name, qty):
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Recount")
	line = next((l for l in doc.lines if l.name == line_name), None)
	if not line or not line.test_sample:
		frappe.throw(_("This line is not in the test sample."))
	qty = flt(qty)
	if qty < 0:
		frappe.throw(_("Quantities cannot be negative."))
	line.test_count_qty = qty
	line.test_counted = 1
	_upsert_entry(doc, "Test", "", line.item_code, line.batch_no, qty)
	save(doc)
	return doc


def finish_review(name):
	"""Recounts and test counts are in: on to approval."""
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Recount")
	missing = [l.item_name or l.item_code for l in doc.lines if l.needs_recount and not l.recounted]
	if missing:
		frappe.throw(_("Still to be recounted: {0}").format(", ".join(missing[:10])), title=_("Recount not finished"))
	untested = [l.item_name or l.item_code for l in doc.lines if l.test_sample and not l.test_counted]
	if untested:
		frappe.throw(_("Enter your test counts first: {0}").format(", ".join(untested[:10])), title=_("Test count not finished"))
	set_final(doc)
	doc.status = "Pending Approval"
	save(doc)
	return doc


def set_final(doc):
	for line in doc.lines:
		final = flt(line.count_2_qty) if line.recounted else flt(line.count_1_qty)
		if line.test_counted and abs(flt(line.test_count_qty) - final) > EPSILON:
			final = flt(line.test_count_qty)  # the supervisor's own count wins over a count that did not hold
		line.final_qty = final
		line.variance_qty = final - flt(line.system_qty)
		line.variance_value = flt(line.variance_qty) * flt(line.valuation_rate)
		line.within_tolerance = 1 if within_tolerance(line, final) else 0
		if abs(flt(line.variance_qty)) <= EPSILON:
			line.reason, line.reason_note = None, None


def set_reasons(name, reasons):
	"""reasons: {line_name: {"reason": ..., "note": ...}} for lines with a difference."""
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Pending Approval")
	lines = {l.name: l for l in doc.lines}
	for line_name, value in (reasons or {}).items():
		line = lines.get(line_name)
		if not line:
			continue
		reason = (value or {}).get("reason") or None
		if reason and reason not in REASONS:
			frappe.throw(_("{0} is not a reason.").format(reason))
		line.reason = reason
		line.reason_note = ((value or {}).get("note") or "").strip()[:140] or None
	save(doc)
	return doc


def approve(name, submit=False):
	doc = get_count_doc(name, for_update=True)
	require_status(doc, "Pending Approval")
	check_count_approver(doc)
	if not frappe.has_permission("Stock Reconciliation", "create"):
		frappe.throw(_("You need permission to create Stock Reconciliations."), frappe.PermissionError)
	if submit and not frappe.has_permission("Stock Reconciliation", "submit"):
		frappe.throw(_("You need permission to submit Stock Reconciliations."), frappe.PermissionError)
	differences = [l for l in doc.lines if abs(flt(l.variance_qty)) > EPSILON]
	missing = [l.item_name or l.item_code for l in differences if not l.reason]
	if missing:
		frappe.throw(_("Give a reason for every difference: {0}").format(", ".join(missing[:10])), title=_("Reason needed"))

	if differences:
		rows = reconciliation_rows(doc, differences)
		sr = erp_count.create_stock_reconciliation(
			doc.company, doc.warehouse, rows, _("Stock count {0} with hasr.").format(doc.name)
		)
		doc.stock_reconciliation = sr.name
	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = now_datetime()
	save(doc)
	mark_counted(doc)
	if differences and cint(submit):
		erp_count.submit_stock_reconciliation(doc.stock_reconciliation)  # releases the freeze (hooks)
	elif not differences:
		release_freeze(doc.name)
	return doc


def reconciliation_rows(doc, lines) -> list[dict]:
	"""The balance now plus the counted difference: movements since the count stay in the books."""
	rows = []
	for line in lines:
		qty = current_balance(doc, line) + flt(line.variance_qty)
		if qty < -EPSILON:
			frappe.throw(
				_("{0}: the stock moved since it was counted and would become negative. Recount it.").format(
					line.item_name or line.item_code
				)
			)
		rows.append(
			{"item_code": line.item_code, "batch_no": line.batch_no, "qty": max(qty, 0.0), "valuation_rate": line.valuation_rate}
		)
	return rows


def refresh_reconciliation(sr, method=None):
	"""Stock Reconciliation before_validate: a draft made by a count keeps balance now + counted difference."""
	if sr.docstatus != 0 or not sr.name or sr.is_new():
		return
	name = frappe.db.get_value(COUNT, {"stock_reconciliation": sr.name}, "name")
	if not name:
		return
	doc = frappe.get_doc(COUNT, name)
	variance = {key(l.item_code, l.batch_no): l for l in doc.lines if abs(flt(l.variance_qty)) > EPSILON}
	for row in sr.items:
		line = variance.get(key(row.item_code, row.batch_no))
		if line:
			row.qty = max(current_balance(doc, line) + flt(line.variance_qty), 0.0)


def reconciliation_done(sr, method=None):
	"""Stock Reconciliation on_submit / on_cancel: the count's freeze ends with its reconciliation."""
	name = frappe.db.get_value(COUNT, {"stock_reconciliation": sr.name}, "name")
	if name:
		release_freeze(name, by=frappe.session.user)


def mark_counted(doc):
	today = getdate(nowdate())
	for item_code in sorted({l.item_code for l in doc.lines if l.counted or l.recounted}):
		name = frappe.db.get_value(ABC, {"item_code": item_code, "warehouse": doc.warehouse})
		abc = frappe.get_doc(ABC, name) if name else frappe.new_doc(ABC)
		abc.update({"item_code": item_code, "warehouse": doc.warehouse, "abc_class": abc.abc_class or "C", "last_counted_on": today})
		abc.next_due_on = add_days(today, frequency_for(abc.abc_class))
		abc.flags.ignore_permissions = True
		abc.save()


def cancel(name):
	doc = get_count_doc(name, for_update=True)
	check_count_supervisor(doc)
	require_status(doc, "Draft", "Counting", "Recount", "Pending Approval")
	doc.status = "Cancelled"
	save(doc)
	release_freeze(doc.name)
	return doc


def review(name):
	"""What the supervisor sees in Desk; quantities included."""
	doc = get_count_doc(name)
	check_count_supervisor(doc)
	lines = doc.lines
	differences = [l for l in lines if abs(flt(l.variance_qty)) > EPSILON]
	return {
		"name": doc.name,
		"status": doc.status,
		"frozen": is_frozen(doc),
		"frozen_until": doc.frozen_until,
		"zones": [
			{
				"zone": z.zone_name,
				"counter": z.counter,
				"counter_name": frappe.utils.get_fullname(z.counter),
				"handed_over": z.handed_over,
				"entries": len([e for e in doc.entries if e.round == "Count" and e.zone == z.zone_name]),
			}
			for z in doc.zones
		],
		"totals": {
			"lines": len(lines),
			"counted": len([l for l in lines if l.counted]),
			"needs_recount": len([l for l in lines if l.needs_recount]),
			"recounted": len([l for l in lines if l.recounted]),
			"unassigned_recount": len([l for l in lines if l.needs_recount and not l.recount_by]),
			"test_sample": len([l for l in lines if l.test_sample]),
			"test_counted": len([l for l in lines if l.test_counted]),
			"differences": len(differences),
			"missing_reasons": len([l for l in differences if not l.reason]),
			"variance_value": sum(flt(l.variance_value) for l in differences),
			"gain_value": sum(flt(l.variance_value) for l in differences if flt(l.variance_value) > 0),
			"loss_value": sum(flt(l.variance_value) for l in differences if flt(l.variance_value) < 0),
		},
		"lines": [
			{
				"name": l.name,
				"item_code": l.item_code,
				"item_name": l.item_name,
				"batch_no": l.batch_no,
				"stock_uom": l.stock_uom,
				"abc_class": l.abc_class,
				"system_qty": flt(l.system_qty),
				"count_1_qty": flt(l.count_1_qty),
				"counted": l.counted,
				"needs_recount": l.needs_recount,
				"recount_by": l.recount_by,
				"count_2_qty": flt(l.count_2_qty),
				"recounted": l.recounted,
				"test_sample": l.test_sample,
				"test_count_qty": flt(l.test_count_qty),
				"test_counted": l.test_counted,
				"final_qty": flt(l.final_qty),
				"variance_qty": flt(l.variance_qty),
				"variance_value": flt(l.variance_value),
				"within_tolerance": l.within_tolerance,
				"tolerance_pct": flt(l.tolerance_pct),
				"reason": l.reason,
				"reason_note": l.reason_note,
				"added_by_counter": l.added_by_counter,
			}
			for l in lines
		],
		"reasons": list(REASONS),
		"approval_block_reason": approval_block_reason(doc),
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency") if doc.company else None,
	}


# ---------------------------------------------------------------- counters on the phone


def my_counts():
	user = frappe.session.user
	rows = frappe.db.sql(
		"""
		select distinct s.name from `tabHasr Count Session` s
		left join `tabHasr Count Zone` z on z.parent = s.name and z.parenttype = %(dt)s
		left join `tabHasr Count Line` l on l.parent = s.name and l.parenttype = %(dt)s
		where (s.status = 'Counting' and z.counter = %(user)s)
		or (s.status = 'Recount' and l.recount_by = %(user)s)
		""",
		{"user": user, "dt": COUNT},
		pluck=True,
	)
	out = []
	for name in rows:
		doc = frappe.get_doc(COUNT, name)
		zone = my_zone(doc)
		mine = [e for e in doc.entries if e.counted_by == user and e.round == current_round(doc)]
		out.append(
			{
				"name": doc.name,
				"warehouse": doc.warehouse,
				"warehouse_name": frappe.get_cached_value("Warehouse", doc.warehouse, "warehouse_name"),
				"count_type": doc.count_type,
				"status": doc.status,
				"round": current_round(doc),
				"zone": zone.zone_name if zone else RECOUNT_ZONE,
				"handed_over": bool(zone and zone.handed_over),
				"counted": len({key(e.item_code, e.batch_no) for e in mine}),
				"to_recount": len([l for l in doc.lines if l.recount_by == user]) if doc.status == "Recount" else 0,
				"started_at": doc.started_at,
			}
		)
	return sorted(out, key=lambda c: (c["handed_over"], str(c["started_at"] or "")), reverse=False)


def current_round(doc) -> str:
	return "Recount" if doc.status == "Recount" else "Count"


def my_zone(doc, user=None):
	user = user or frappe.session.user
	return next((z for z in doc.zones if z.counter == user), None)


def get_counter_doc(name, for_update=False):
	"""The count, for someone who counts in it now (zone counter, or recounter)."""
	doc = get_count_doc(name, for_update=for_update)
	user = frappe.session.user
	if doc.status == "Counting" and my_zone(doc, user):
		return doc
	if doc.status == "Recount" and any(l.recount_by == user for l in doc.lines):
		return doc
	if doc.status in ("Counting", "Recount"):
		frappe.throw(_("You are not counting in stock count {0}.").format(doc.name), frappe.PermissionError)
	frappe.throw(_("Stock count {0} is {1}; counting has ended.").format(doc.name, _(doc.status)))


def count_payload(doc):
	"""Everything the phone needs to count, offline too. Never a system quantity."""
	from hasr.receiving import _line_uoms

	user = frappe.session.user
	round_ = current_round(doc)
	zone = my_zone(doc, user) if round_ == "Count" else None
	lines = [l for l in doc.lines if round_ == "Count" or l.recount_by == user]
	codes = list(dict.fromkeys(l.item_code for l in lines))
	items = {
		r.name: r
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", codes or [""]]},
			fields=["name", "item_name", "image", "stock_uom", "has_batch_no", "brand"],
		)
	}
	item_barcodes = {}
	for b in frappe.get_all(
		"Item Barcode",
		filters={"parent": ["in", codes or [""]], "parenttype": "Item"},
		fields=["parent", "barcode", "uom"],
		order_by="idx asc",
	):
		item_barcodes.setdefault(b.parent, []).append({"barcode": b.barcode, "uom": b.uom})
	batches = erp_count.item_batches([c for c in codes if items.get(c) and items[c].has_batch_no])
	# a recount is of the lines given to this person only, batch by batch
	recount_batches = {}
	if round_ == "Recount":
		for l in lines:
			recount_batches.setdefault(l.item_code, []).append(l.batch_no or "")

	zone_name = zone.zone_name if zone else RECOUNT_ZONE
	counts = [
		{"item_code": e.item_code, "batch_no": e.batch_no, "qty": flt(e.qty), "counted_at": e.counted_at}
		for e in doc.entries
		if e.round == round_ and e.zone == zone_name and e.counted_by == user
	]
	return {
		"name": doc.name,
		"warehouse": doc.warehouse,
		"warehouse_name": frappe.get_cached_value("Warehouse", doc.warehouse, "warehouse_name"),
		"count_type": doc.count_type,
		"entry_method": doc.entry_method,
		"scope_type": doc.scope_type,
		"open_scope": doc.scope_type == "Warehouse",
		"status": doc.status,
		"round": round_,
		"zone": zone_name,
		"note": doc.note,
		"handed_over": bool(zone and zone.handed_over),
		"editable": not (zone and zone.handed_over),
		"items": [
			{
				"item_code": c,
				"item_name": items[c].item_name,
				"image": items[c].image,
				"brand": items[c].brand,
				"stock_uom": items[c].stock_uom,
				"has_batch_no": items[c].has_batch_no,
				"uoms": _line_uoms(c, items[c].stock_uom),
				"barcodes": item_barcodes.get(c, []),
				"batches": batches.get(c, []),
				"recount_batches": recount_batches.get(c),
			}
			for c in codes
			if c in items
		],
		"counts": counts,
	}


def get_count(name):
	return count_payload(get_counter_doc(name))


def identify(name, code):
	"""Which item of the count a scanned code is (with the batch, when a GS1 code names it)."""
	doc = get_counter_doc(name)
	resolved = barcodes.resolve(code)
	if not resolved:
		return {"status": "unknown", "barcode": code, "message": _("Barcode {0} is not linked to any item.").format(code)}
	if resolved.disabled:
		return {"status": "rejected", "message": _("Item {0} is disabled.").format(resolved.item_code)}
	in_count = any(l.item_code == resolved.item_code for l in doc.lines)
	if not in_count and not (doc.scope_type == "Warehouse" and doc.status == "Counting"):
		return {
			"status": "not_in_count",
			"item_code": resolved.item_code,
			"message": _("{0} is not part of this count.").format(resolved.item_name),
		}
	batch_no = erp_count.find_batch(resolved.item_code, resolved.gs1_batch) if resolved.get("gs1_batch") else None
	return {
		"status": "item",
		"item_code": resolved.item_code,
		"item_name": resolved.item_name,
		"uom": resolved.uom if resolved.barcode else None,
		"conversion_factor": flt(resolved.conversion_factor) or 1.0,
		"batch_no": batch_no,
		"expiry_date": resolved.get("expiry_date"),
		"in_count": in_count,
	}


def set_count(name, item_code, qty, batch_no=None, client_uuid=None, counted_at=None):
	"""What the counter counted of an item (and batch) in their zone, in stock units. Replaces their earlier count."""
	from hasr.receiving import UUID_RE, _device_time

	uuid = (client_uuid or "").strip()
	if uuid and not UUID_RE.match(uuid):
		frappe.throw(_("Missing or invalid scan id."))
	if uuid and frappe.db.exists("Hasr Scan", {"client_uuid": uuid}):
		return {"status": "duplicate", "client_uuid": uuid}

	doc = get_counter_doc(name, for_update=True)
	user = frappe.session.user
	round_ = current_round(doc)
	zone = my_zone(doc, user) if round_ == "Count" else None
	if zone and zone.handed_over:
		frappe.throw(_("You handed over zone {0}; it can no longer be changed.").format(zone.zone_name))
	qty = flt(qty)
	if qty < 0:
		frappe.throw(_("Quantities cannot be negative."))
	item = frappe.db.get_value("Item", item_code, ["item_name", "has_batch_no", "is_stock_item", "disabled"], as_dict=True)
	if not item or not item.is_stock_item:
		frappe.throw(_("Item {0} not found.").format(item_code))
	batch_no = (batch_no or "").strip() or None
	if item.has_batch_no and not batch_no:
		frappe.throw(_("{0} is counted per batch. Choose the batch.").format(item.item_name))
	if not item.has_batch_no:
		batch_no = None
	if batch_no and frappe.db.get_value("Batch", batch_no, "item") != item_code:
		frappe.throw(_("Batch {0} is not a batch of {1}.").format(batch_no, item.item_name))

	line = find_line(doc, item_code, batch_no)
	if round_ == "Recount":
		if not line or line.recount_by != user:
			frappe.throw(_("{0} is not on your recount list.").format(item.item_name))
	elif not line:
		if not any(l.item_code == item_code for l in doc.lines) and doc.scope_type != "Warehouse":
			frappe.throw(_("{0} is not part of this count.").format(item.item_name))
		# found during the count: a batch with no balance, or (whole warehouse) an item that should not be here
		line = new_line(doc, item_code, batch_no, 0.0, added=not any(l.item_code == item_code for l in doc.lines))
		if not is_frozen(doc):
			refresh_snapshot(doc, line)
		else:
			line.system_qty = current_balance(doc, line)

	if round_ == "Count" and not line.counted and not is_frozen(doc):
		refresh_snapshot(doc, line)  # cycle or unfrozen count: the balance at the moment it is counted
	zone_name = zone.zone_name if zone else RECOUNT_ZONE
	_upsert_entry(doc, round_, zone_name, item_code, batch_no, qty, _device_time(counted_at))
	if round_ == "Count":
		line.counted = 1
	else:
		line.count_2_qty, line.recounted = entry_total(doc, line, "Recount")
	frappe.get_doc(
		{
			"doctype": "Hasr Scan",
			"client_uuid": uuid or frappe.generate_hash(length=20),
			"status": "Applied",
			"session_type": "Count",
			"session_doctype": COUNT,
			"session": doc.name,
			"item_code": item_code,
			"batch_no": batch_no,
			"qty": qty,
			"qty_stock_uom": qty,
			"scanned_at": _device_time(counted_at),
			"user": user,
		}
	).insert(ignore_permissions=True)
	save(doc)
	return {"status": "applied", "client_uuid": uuid, "item_code": item_code, "batch_no": batch_no, "qty": qty}


def find_line(doc, item_code, batch_no):
	k = key(item_code, batch_no)
	line = next((l for l in doc.lines if key(l.item_code, l.batch_no) == k), None)
	if not line and batch_no:
		# the placeholder of a batch item with no balance becomes the line of the first batch counted
		line = next((l for l in doc.lines if l.item_code == item_code and not l.batch_no and not l.counted), None)
		if line:
			line.batch_no = batch_no
	return line


def _upsert_entry(doc, round_, zone, item_code, batch_no, qty, counted_at=None):
	user = frappe.session.user
	k = key(item_code, batch_no)
	entry = next(
		(
			e
			for e in doc.entries
			if e.round == round_ and e.zone == zone and e.counted_by == user and key(e.item_code, e.batch_no) == k
		),
		None,
	)
	if not entry:
		entry = doc.append("entries", {"round": round_, "zone": zone, "item_code": item_code, "batch_no": batch_no, "counted_by": user})
	entry.qty = qty
	entry.counted_at = counted_at or now_datetime()


def hand_over(name):
	doc = get_counter_doc(name, for_update=True)
	zone = my_zone(doc)
	if not zone or doc.status != "Counting":
		frappe.throw(_("Only a zone being counted can be handed over."))
	zone.handed_over = 1
	zone.handed_over_at = now_datetime()
	save(doc)
	return doc
