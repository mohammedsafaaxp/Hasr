"""Serves the phone app's service worker at /hasr-sw.js.

A service worker only controls pages under its own folder, so it cannot live in /assets/hasr/. Frappe's static
pages refuse .js files, hence this small page renderer (hooks.py → page_renderer).
"""

import os

import frappe
from werkzeug.wrappers import Response

ROUTE = "hasr-sw.js"


class ServiceWorker:
	def __init__(self, path, http_status_code=None):
		self.path = (path or "").strip("/ ")

	def can_render(self):
		return self.path == ROUTE

	def render(self):
		with open(os.path.join(frappe.get_app_path("hasr", "public"), "hasr-sw.js"), "rb") as f:
			body = f.read()
		response = Response(body, mimetype="application/javascript")
		response.headers["Service-Worker-Allowed"] = "/hasr"
		# the browser checks for a new worker on every visit; the worker itself decides what is cached
		response.headers["Cache-Control"] = "no-cache"
		return response
