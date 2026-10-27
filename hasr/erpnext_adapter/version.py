"""ERPNext version detection. Everything version-specific branches on these helpers."""

import functools


@functools.cache
def erpnext_version() -> tuple[int, int]:
	from erpnext import __version__

	parts = __version__.split(".")
	try:
		return int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
	except ValueError:
		return (0, 0)


def erpnext_major() -> int:
	return erpnext_version()[0]


def uses_serial_batch_bundle() -> bool:
	"""v15 introduced Serial and Batch Bundle; v14 and older store batch_no on the row."""
	return erpnext_major() >= 15
