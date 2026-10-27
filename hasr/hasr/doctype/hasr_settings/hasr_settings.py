# Copyright (c) 2026, hasr contributors
# License: GNU General Public License v3. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HasrSettings(Document):
	def validate(self):
		if flt(self.abc_a_share) > flt(self.abc_b_share):
			frappe.throw(_("Class A share cannot be greater than class B share."))


def get_settings():
	return frappe.get_cached_doc("Hasr Settings")
