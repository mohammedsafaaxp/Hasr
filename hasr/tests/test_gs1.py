import datetime
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from hasr import gs1
from hasr.api import items as items_api
from hasr.api import receiving as api
from hasr.api import sync
from hasr.tests import fixtures as fx
from hasr.tests.utils import HasrTestCase

GS = gs1.GS


def yymmdd(iso):
	return getdate(iso).strftime("%y%m%d")


class TestGS1Parser(unittest.TestCase):
	def test_bracketed(self):
		self.assertEqual(
			gs1.parse("(01)09501101530003(17)270315(10)AB12"),
			{"gtin": "09501101530003", "expiry_date": "2027-03-15", "batch": "AB12"},
		)

	def test_raw_with_group_separators_and_symbology_prefix(self):
		code = "]d2" + "0109501101530003" + "10AB-12" + GS + "17270300" + "21SN1"
		self.assertEqual(
			gs1.parse(code),
			{"gtin": "09501101530003", "batch": "AB-12", "expiry_date": "2027-03-31", "serial": "SN1"},
		)

	def test_raw_without_prefix_fixed_fields_first(self):
		self.assertEqual(
			gs1.parse("0109501101530003172703151" + "0LOT9"),
			{"gtin": "09501101530003", "expiry_date": "2027-03-15", "batch": "LOT9"},
		)

	def test_production_date_best_before_and_count(self):
		out = gs1.parse("(01)09501101530003(11)260101(15)261231(30)24")
		self.assertEqual(out["production_date"], "2026-01-01")
		self.assertEqual(out["best_before"], "2026-12-31")
		self.assertEqual(out["count"], 24)

	def test_plain_barcodes_are_not_gs1(self):
		for code in ("6281007070444", "16281007030126", "HASR-MILK", "", None, "(99)123"):
			self.assertIsNone(gs1.parse(code), code)

	def test_broken_codes_are_refused(self):
		for code in (
			"(01)0950110153000(17)270315",  # GTIN too short
			"(01)09501101530003(17)271315",  # month 13
			"(01)09501101530003(17)270231",  # 31 February
			"(01)09501101530003junk",
			"0109501101530003" + "10" + "X" * 21,  # batch longer than 20
			"0109501101530003" + "99X",  # unknown AI
			"(10)",
		):
			self.assertIsNone(gs1.parse(code), code)

	def test_batch_only(self):
		self.assertEqual(gs1.parse("(10)LOT-7"), {"batch": "LOT-7"})

	def test_century(self):
		year = datetime.date.today().year
		self.assertEqual(gs1.parse_date(f"{(year + 10) % 100:02d}0101"), f"{year + 10}-01-01")
		self.assertEqual(gs1.parse_date(f"{(year - 20) % 100:02d}0101"), f"{year - 20}-01-01")
		self.assertEqual(gs1.parse_date("240200"), "2024-02-29")  # day 00 is the last day of the month
		self.assertIsNone(gs1.parse_date("2401"))
		self.assertIsNone(gs1.parse_date("24ab01"))

	def test_gtin_candidates(self):
		self.assertEqual(gs1.gtin_candidates("06281007070444"), ["06281007070444", "6281007070444"])
		self.assertEqual(gs1.gtin_candidates("00012345678905"), ["00012345678905", "0012345678905", "012345678905"])
		self.assertEqual(gs1.gtin_candidates("00000096385074"), ["00000096385074", "0000096385074", "000096385074", "96385074"])


class TestGS1Receiving(HasrTestCase, FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("Hasr Settings", "gs1_enabled", 1)
		frappe.clear_document_cache("Hasr Settings", "Hasr Settings")
		self.po = fx.make_po([("HASR-CREAM-B", 48), ("HASR-YOGURT", 5)])
		frappe.set_user(fx.COUNTER)
		self.s = api.start_session(self.po.name)
		self.d1 = add_days(nowdate(), 20)
		self.d2 = add_days(nowdate(), 25)

	def code(self, expiry, lot="L1"):
		return f"(01)0{fx.CREAM_UNIT}(17){yymmdd(expiry)}(10){lot}"

	def line(self, out):
		return next(l for l in out["lines"] if l["item_code"] == "HASR-CREAM-B")

	def test_resolve_reads_gtin_batch_and_expiry(self):
		r = items_api.resolve_barcode(self.code(self.d1, "LOT5"))
		self.assertTrue(r["found"])
		self.assertEqual((r["item_code"], r["gs1_batch"], str(r["expiry_date"])), ("HASR-CREAM-B", "LOT5", self.d1))

	def test_scans_fill_the_expiry_rows(self):
		sync.push_scans([fx.scan(self.s["name"], self.code(self.d1), qty=6)])
		out = sync.push_scans([fx.scan(self.s["name"], self.code(self.d2), qty=4)])
		line = self.line(out)
		self.assertEqual(line["received_qty"], 10)
		self.assertEqual(line["batches"], [{"expiry_date": self.d1, "qty": 6}, {"expiry_date": self.d2, "qty": 4}])
		self.assertFalse(line["needs_expiry"])

	def test_undo_takes_the_quantity_off_its_date(self):
		sync.push_scans([fx.scan(self.s["name"], self.code(self.d1), qty=6)])
		second = fx.scan(self.s["name"], self.code(self.d2), qty=4)
		sync.push_scans([second])
		out = sync.push_scans([fx.scan(self.s["name"], None, undo_of=second["client_uuid"])])
		line = self.line(out)
		self.assertEqual(line["batches"], [{"expiry_date": self.d1, "qty": 6}])
		self.assertFalse(line["needs_expiry"])

	def test_expired_code_is_refused(self):
		out = sync.push_scans([fx.scan(self.s["name"], self.code(add_days(nowdate(), -1)))])
		self.assertEqual(out["results"][0]["code"], "expired")
		self.assertEqual(self.line(api.get_session(self.s["name"]))["received_qty"], 0)

	def test_identify_passes_the_expiry_to_the_phone(self):
		r = api.identify(self.s["name"], self.code(self.d1))
		self.assertEqual((r["status"], str(r["expiry_date"])), ("line", self.d1))

	def test_switched_off(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("Hasr Settings", "gs1_enabled", 0)
		frappe.clear_document_cache("Hasr Settings", "Hasr Settings")
		frappe.set_user(fx.COUNTER)
		self.assertFalse(items_api.resolve_barcode(self.code(self.d1))["found"])
