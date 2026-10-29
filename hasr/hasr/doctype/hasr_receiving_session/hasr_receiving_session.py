# Copyright (c) 2026, hasr contributors
# License: GNU General Public License v3. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Statuses in which the counter can still change the session; they hold the one-open-session lock.
EDITABLE_STATUSES = ("Open", "Sent Back")
EPSILON = 1e-6


class HasrReceivingSession(Document):
	def validate(self):
		self.open_lock = self.purchase_order if self.status in EDITABLE_STATUSES else None
		self.validate_one_open_session()
		for line in self.lines:
			update_line_state(line)

	def validate_one_open_session(self):
		if not self.open_lock:
			return
		other = frappe.db.get_value(
			"Hasr Receiving Session",
			{"open_lock": self.open_lock, "name": ["!=", self.name or ""]},
			["name", "received_by"],
			as_dict=True,
		)
		if other:
			frappe.throw(
				_("Purchase order {0} already has an open receiving session {1} by {2}. Finish it first.").format(
					self.purchase_order, other.name, other.received_by
				),
				title=_("Session already open"),
			)

	def get_line(self, po_item):
		for line in self.lines:
			if line.po_item == po_item:
				return line
		frappe.throw(_("Line {0} is not part of session {1}.").format(po_item, self.name))

	def recompute_line(self, line):
		"""Totals always come from applied, non-undone scans plus the manual adjustment."""
		line.scanned_qty = flt(
			frappe.db.sql(
				"""select coalesce(sum(qty_stock_uom), 0) from `tabHasr Scan`
				where session_doctype = %s and session = %s and po_item = %s
				and status = 'Applied' and undone = 0""",
				(self.doctype, self.name, line.po_item),
			)[0][0]
		)
		line.received_qty = max(flt(line.scanned_qty) + flt(line.manual_adjust_qty), 0.0)
		sync_single_batch(line)
		update_line_state(line)

	def is_editable(self):
		return self.status in EDITABLE_STATUSES


def sync_single_batch(line):
	"""With one expiry date on the line, later scans belong to it: the worker enters the date once and keeps scanning."""
	if not line.batches_json:
		return
	batches = frappe.parse_json(line.batches_json)
	if len(batches) == 1 and flt(batches[0]["qty"]) != flt(line.received_qty):
		batches[0]["qty"] = flt(line.received_qty)
		line.batches_json = frappe.as_json(batches)


def line_total(line) -> float:
	"""Everything ERPNext will count against the PO line (it includes rejected quantity)."""
	return flt(line.already_received_qty) + flt(line.received_qty) + flt(line.rejected_qty)


def is_over(line) -> bool:
	return line_total(line) > flt(line.allowed_qty) + EPSILON


def update_line_state(line):
	"""OK / Over from the quantities; a supervisor's Accepted or Capped decision is kept while it still holds."""
	if is_over(line):
		line.over_allowance_state = "Accepted" if line.over_allowance_state == "Accepted" else "Over"
	else:
		line.over_allowance_state = "Capped" if line.over_allowance_state == "Capped" else "OK"
