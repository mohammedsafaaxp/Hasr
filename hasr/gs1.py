"""GS1 barcode parsing: GTIN, batch and dates from a GS1-128 or GS1 DataMatrix scan.

Pure Python with no Frappe imports, so it is easy to test. Two forms are read:
- human-readable, with the AIs in brackets: (01)09501101530003(17)270315(10)AB12
- raw, as scanners send it: 01095011015300031727031510AB12, variable fields ended by the GS character
  (\x1d), optionally after a symbology prefix such as ]C1, ]d2 or ]Q3.
"""

import calendar
import datetime
import re

GS = "\x1d"
# AI → (fixed length or None for variable, max length)
AIS = {
	"00": (18, 18),  # SSCC
	"01": (14, 14),  # GTIN
	"02": (14, 14),  # GTIN of contained items
	"10": (None, 20),  # batch or lot
	"11": (6, 6),  # production date YYMMDD
	"13": (6, 6),  # packaging date
	"15": (6, 6),  # best before
	"17": (6, 6),  # expiry
	"21": (None, 20),  # serial (read, not used)
	"30": (None, 8),  # count of items
	"37": (None, 8),  # count of trade items
}
DATE_AIS = ("11", "13", "15", "17")
SYMBOLOGY_PREFIX = re.compile(r"^\][A-Za-z][0-9]")
BRACKETED = re.compile(r"\((\d{2,4})\)([^()]*)")


def parse(code: str) -> dict | None:
	"""The GS1 fields of a scan, or None when it is not a GS1 code (a plain EAN or UPC is not).

	Returns {"gtin", "batch", "expiry_date", "production_date", "best_before", "serial", "count"} with only
	the fields present; dates are ISO strings.
	"""
	if not code:
		return None
	code = code.strip()
	prefixed = bool(SYMBOLOGY_PREFIX.match(code))
	if prefixed:
		code = code[3:]
	if code.startswith("("):
		fields = _parse_bracketed(code)
	elif prefixed or GS in code or _looks_raw(code):
		fields = _parse_raw(code.lstrip(GS))
	else:
		return None
	if not fields or not ({"01", "02"} & fields.keys() or "10" in fields):
		return None
	return _to_result(fields)


def _looks_raw(code: str) -> bool:
	# a raw GS1 code starts with AI 01 and a 14-digit GTIN followed by more AIs; a 13-digit EAN cannot
	return len(code) > 16 and code[:2] in ("01", "02") and code[2:16].isdigit()


def _parse_bracketed(code: str) -> dict | None:
	fields = {}
	pos = 0
	for m in BRACKETED.finditer(code):
		if m.start() != pos:
			return None
		ai, value = m.group(1), m.group(2).strip()
		if ai not in AIS or not _valid(ai, value):
			return None
		fields[ai] = value
		pos = m.end()
	return fields if pos == len(code) else None


def _parse_raw(code: str) -> dict | None:
	fields = {}
	i = 0
	while i < len(code):
		if code[i] == GS:
			i += 1
			continue
		ai = code[i : i + 2]
		if ai not in AIS:
			return None
		fixed, max_len = AIS[ai]
		start = i + 2
		if fixed:
			value = code[start : start + fixed]
			i = start + fixed
		else:
			end = code.find(GS, start)
			end = len(code) if end == -1 else end
			value = code[start:end]
			if len(value) > max_len:
				return None
			i = end
		if not _valid(ai, value):
			return None
		fields[ai] = value
	return fields


def _valid(ai: str, value: str) -> bool:
	fixed, max_len = AIS[ai]
	if fixed:
		if ai in DATE_AIS:
			return parse_date(value) is not None
		return len(value) == fixed and value.isdigit()
	if ai in ("30", "37"):
		return 0 < len(value) <= max_len and value.isdigit()
	return 0 < len(value) <= max_len


def _to_result(fields: dict) -> dict:
	out = {}
	gtin = fields.get("01") or fields.get("02")
	if gtin:
		out["gtin"] = gtin
	if "10" in fields:
		out["batch"] = fields["10"]
	if "21" in fields:
		out["serial"] = fields["21"]
	if fields.get("30") or fields.get("37"):
		out["count"] = int(fields.get("30") or fields["37"])
	for ai, key in (("17", "expiry_date"), ("11", "production_date"), ("15", "best_before")):
		if ai in fields:
			out[key] = parse_date(fields[ai])
	return out


def parse_date(yymmdd: str) -> str | None:
	"""GS1 YYMMDD as an ISO date. Day 00 means the last day of the month.

	The century follows the GS1 rule: years more than 49 ahead of now belong to the previous century.
	"""
	if len(yymmdd) != 6 or not yymmdd.isdigit():
		return None
	yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
	this_year = datetime.date.today().year
	year = this_year - this_year % 100 + yy
	if year - this_year > 49:
		year -= 100
	elif this_year - year > 50:
		year += 100
	if not 1 <= mm <= 12:
		return None
	last = calendar.monthrange(year, mm)[1]
	if dd == 0:
		dd = last
	if dd > last:
		return None
	return datetime.date(year, mm, dd).isoformat()


def gtin_candidates(gtin: str) -> list[str]:
	"""The forms the same GTIN may be stored in on an Item Barcode: GTIN-14, EAN-13, UPC-A, EAN-8."""
	out = [gtin]
	stripped = gtin
	while stripped.startswith("0") and len(stripped) > 8:
		stripped = stripped[1:]
		if len(stripped) in (13, 12, 8):
			out.append(stripped)
	return out
