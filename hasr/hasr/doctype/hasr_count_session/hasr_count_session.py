# Copyright (c) 2026, hasr contributors
# License: GNU General Public License v3. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class HasrCountSession(Document):
	def validate(self):
		self.refuse_direct_changes()
		if self.warehouse:
			self.company = frappe.get_cached_value("Warehouse", self.warehouse, "company")
		names = [z.zone_name.strip() for z in self.zones if z.zone_name]
		if len(names) != len(set(n.lower() for n in names)):
			frappe.throw(_("Each zone needs its own name."))
		counters = [z.counter for z in self.zones]
		if len(counters) != len(set(counters)):
			frappe.throw(_("Give each counter one zone; a zone has one counter."))

	def refuse_direct_changes(self):
		"""A draft is set up in Desk. Once counting starts, the count changes only through hasr's actions, which
		check who counts, who approves and the warehouses (they save with ignore_permissions)."""
		if self.flags.ignore_permissions or frappe.flags.in_install or frappe.flags.in_migrate:
			return
		before = self.get_doc_before_save()
		if self.status == "Draft" and (not before or before.status == "Draft"):
			return
		frappe.throw(_("A stock count is changed with its buttons once counting has started."), frappe.PermissionError)

	def on_trash(self):
		if self.status not in ("Draft", "Cancelled"):
			frappe.throw(_("Only a draft or cancelled stock count can be deleted."))
		frappe.db.delete("Hasr Stock Freeze", {"count_session": self.name, "active": 0})
