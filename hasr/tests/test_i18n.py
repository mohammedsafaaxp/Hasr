"""Every user-facing string is translatable and translated to Arabic; the UI never hard-codes left/right."""

import csv
import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

APP_ROOT = os.path.dirname(frappe.get_app_path("hasr"))
FRONTEND = os.path.join(APP_ROOT, "frontend", "src")
JS_STRING = re.compile(r"""__\(\s*(['"])((?:\\.|(?!\1).)*)\1""")
PY_STRING = re.compile(r"""\b_\(\s*((?:(['"])(?:\\.|(?!\2).)*\2\s*)+)\)""")
# physical-direction utilities; use ps-/pe-/ms-/me-/start-/end-/text-start/text-end instead
PHYSICAL = re.compile(
	r"""(?<![\w-])(?:-?(?:ml|mr|pl|pr|left|right|border-l|border-r|rounded-l|rounded-r|rounded-tl|rounded-tr|rounded-bl|rounded-br|scroll-ml|scroll-mr)-[\w\[\]./]+|text-left|text-right|float-left|float-right)(?![\w-])"""
)


def frontend_files():
	for base, _dirs, files in os.walk(FRONTEND):
		for name in files:
			if name.endswith((".vue", ".js")):
				yield os.path.join(base, name)


def python_strings():
	for base, dirs, files in os.walk(frappe.get_app_path("hasr")):
		if "tests" in base.split(os.sep):
			continue
		for name in files:
			if name.endswith(".py"):
				text = open(os.path.join(base, name)).read()
				for m in PY_STRING.finditer(text):
					yield "".join(p[1] for p in re.findall(r"""(['"])((?:\\.|(?!\1).)*)\1""", m.group(1)))


def arabic():
	with open(frappe.get_app_path("hasr", "translations", "ar.csv")) as f:
		return {row[0]: row[1] for row in csv.reader(f) if row}


class TestI18n(FrappeTestCase):
	def setUp(self):
		if not os.path.isdir(FRONTEND):
			self.skipTest("frontend source not present")

	def test_frontend_strings_have_arabic(self):
		ar = arabic()
		missing = set()
		for path in frontend_files():
			for m in JS_STRING.finditer(open(path).read()):
				if m.group(2).replace("\\'", "'") not in ar:
					missing.add(m.group(2))
		self.assertFalse(missing, f"add to hasr/translations/ar.csv: {sorted(missing)}")

	def test_desk_strings_have_arabic(self):
		ar = arabic()
		missing = set()
		for base, _dirs, files in os.walk(frappe.get_app_path("hasr", "hasr", "doctype")):
			for name in files:
				if name.endswith(".js"):
					for m in JS_STRING.finditer(open(os.path.join(base, name)).read()):
						if m.group(2) not in ar:
							missing.add(m.group(2))
		self.assertFalse(missing, f"add to hasr/translations/ar.csv: {sorted(missing)}")

	def test_python_strings_have_arabic(self):
		ar = arabic()
		missing = sorted({s for s in python_strings() if s not in ar})
		self.assertFalse(missing, f"add to hasr/translations/ar.csv: {missing}")

	def test_no_physical_direction_classes(self):
		offenders = []
		for path in frontend_files():
			for n, line in enumerate(open(path), 1):
				for m in PHYSICAL.finditer(line):
					offenders.append(f"{os.path.relpath(path, FRONTEND)}:{n} {m.group(0)}")
		self.assertFalse(offenders, offenders)

	def test_translations_served(self):
		from hasr.api.i18n import get_translations

		frappe.cache.delete_value("hasr_translations:ar")
		messages = get_translations("ar")
		self.assertEqual(messages.get("Scan or type a barcode"), "امسح الباركود أو اكتبه")
		self.assertEqual(get_translations("en"), {})
