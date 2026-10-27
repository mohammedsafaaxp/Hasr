app_name = "hasr"
app_title = "hasr"
app_publisher = "hasr contributors"
app_description = "Receiving and stock counts from a phone, on top of ERPNext"
app_email = "hasr@example.org"
app_license = "GPL-3.0"
required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "hasr",
		"logo": "/assets/hasr/images/logo.svg",
		"title": "hasr",
		"route": "/hasr",
		"has_permission": "hasr.api.has_app_permission",
	}
]

# The phone app is a single-page app served from /hasr
website_route_rules = [{"from_route": "/hasr/<path:app_path>", "to_route": "hasr"}]

fixtures = [
	{"dt": "Role", "filters": [["name", "in", ["Hasr Counter", "Hasr Supervisor"]]]},
	{"dt": "Custom Field", "filters": [["module", "=", "Hasr"]]},
]

after_install = "hasr.install.after_install"
after_migrate = "hasr.install.after_migrate"

before_tests = "hasr.tests.utils.before_tests"

# Stock freeze (doc_events on Stock Ledger Entry) and scheduler jobs arrive in milestone 0.3.
