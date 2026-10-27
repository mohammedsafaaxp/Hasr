"""Test bootstrap that needs ERPNext internals (kept here so tests never import erpnext directly)."""


def before_tests():
	from erpnext.setup.utils import before_tests as erpnext_before_tests

	erpnext_before_tests()
