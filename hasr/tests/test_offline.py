import frappe
from frappe.tests.utils import FrappeTestCase

from hasr.service_worker import ServiceWorker


class TestServiceWorker(FrappeTestCase):
	def test_served_as_javascript_that_may_control_the_app(self):
		self.assertIn("hasr.service_worker.ServiceWorker", frappe.get_hooks("page_renderer"))
		sw = ServiceWorker("/hasr-sw.js")
		self.assertTrue(sw.can_render())
		response = sw.render()
		self.assertEqual(response.mimetype, "application/javascript")
		self.assertEqual(response.headers["Service-Worker-Allowed"], "/hasr")
		self.assertIn(b"addEventListener('fetch'", response.get_data())

	def test_other_paths_are_left_alone(self):
		for path in ("hasr", "hasr/sw.js", "app/hasr-sw.js", "assets/hasr/hasr-sw.js"):
			self.assertFalse(ServiceWorker(path).can_render(), path)

	def test_the_worker_never_caches_the_api(self):
		body = ServiceWorker("hasr-sw.js").render().get_data().decode()
		self.assertNotIn("/api/", body.split("self.addEventListener('fetch'")[1])
