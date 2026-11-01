import frappe


def execute():
	"""hasr no longer records rejected quantity: lines decided as "Excess rejected" are decided again."""
	frappe.db.sql(
		"""update `tabHasr Receiving Line` l
		join `tabHasr Receiving Session` s on s.name = l.parent
		set l.over_allowance_state = 'Over'
		where l.over_allowance_state = 'Excess rejected' and s.status not in ('Approved', 'Cancelled')"""
	)
