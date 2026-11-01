"""Desk scripts are not covered by Python tests; at least make sure each one parses."""

import os
import shutil
import subprocess

import frappe
from frappe.tests.utils import FrappeTestCase

CHECK = "const fs=require('fs');new Function(fs.readFileSync(process.argv[1],'utf8'))"


class TestDeskScripts(FrappeTestCase):
	def test_desk_scripts_parse(self):
		node = shutil.which("node")
		if not node:
			self.skipTest("node is not installed")
		doctype_dir = frappe.get_app_path("hasr", "hasr", "doctype")
		scripts = [
			os.path.join(base, name)
			for base, _dirs, files in os.walk(doctype_dir)
			for name in files
			if name.endswith(".js")
		]
		self.assertTrue(scripts)
		for path in scripts:
			out = subprocess.run([node, "-e", CHECK, path], capture_output=True, text=True)
			self.assertEqual(out.returncode, 0, f"{os.path.basename(path)}: {out.stderr.strip()[:400]}")
