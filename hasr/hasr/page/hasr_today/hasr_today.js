// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

// Today's shipments for the supervisor: one click for a shipment that matches its order,
// a review for everything else. Who may approve is decided by the server (Hasr Settings).
frappe.pages["hasr-today"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Today's Shipments"),
		single_column: true,
	});
	const $body = $('<div class="hasr-today"></div>').appendTo(page.main);
	page.set_secondary_action(__("Refresh"), () => load());

	const esc = frappe.utils.escape_html;

	function state(row) {
		if (row.status === "Approved") return `<span class="indicator-pill green">${__("Approved")}</span>`;
		if (row.status !== "Pending Approval") return `<span class="indicator-pill blue">${__(row.status)}</span>`;
		if (row.matches) return `<span class="indicator-pill green">${__("Matches the order")}</span>`;
		return `<span class="indicator-pill orange">${__("Needs review")}</span>
			<ul class="hasr-problems">${row.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`;
	}

	function action(row) {
		const review = `<a class="btn btn-default btn-sm" href="/app/hasr-receiving-session/${encodeURIComponent(row.name)}">${__("Review")}</a>`;
		if (row.status === "Approved" && row.purchase_receipt) {
			return `<a class="btn btn-default btn-sm" href="/app/purchase-receipt/${encodeURIComponent(row.purchase_receipt)}">${__("Purchase Receipt")}</a>`;
		}
		if (row.status !== "Pending Approval") return review;
		if (row.matches && !row.approval_block_reason) {
			return `<button class="btn btn-primary btn-sm" data-approve="${esc(row.name)}">${__("Approve")}</button> ${review}`;
		}
		const why = row.approval_block_reason ? `<div class="text-muted small">${esc(row.approval_block_reason)}</div>` : "";
		return review + why;
	}

	function render(rows) {
		if (!rows.length) {
			$body.html(`<div class="hasr-empty text-muted">${__("No shipments today, and nothing is waiting for approval.")}</div>`);
			return;
		}
		const ready = rows.filter((r) => r.matches && !r.approval_block_reason).length;
		$body.html(`
			<style>
				.hasr-today { padding: 12px 0; }
				.hasr-today table td { vertical-align: top; }
				.hasr-problems { margin: 6px 0 0; padding-inline-start: 18px; color: var(--text-muted); font-size: 12px; }
				.hasr-empty { padding: 48px 0; text-align: center; }
				.hasr-ready { margin-bottom: 12px; }
			</style>
			<p class="hasr-ready text-muted">${__("{0} shipments, {1} ready to approve with one click.", [rows.length, ready])}</p>
			<table class="table table-bordered">
				<thead><tr>
					<th>${__("Supplier")}</th><th>${__("Received by")}</th><th>${__("Supplier invoice")}</th>
					<th>${__("Status")}</th><th></th>
				</tr></thead>
				<tbody>${rows
					.map(
						(r) => `<tr>
							<td><b>${esc(r.supplier)}</b><div class="text-muted small">${esc(r.purchase_order)} · ${__("shipment {0}", [r.shipment_no])} · ${__("{0} lines", [r.lines])}</div></td>
							<td>${esc(r.received_by_name || r.received_by)}<div class="text-muted small">${r.finished_at ? frappe.datetime.str_to_user(r.finished_at) : ""}</div></td>
							<td>${esc(r.supplier_invoice_no || "—")}${r.invoice_files ? ` <span class="text-muted small">(${__("{0} files", [r.invoice_files])})</span>` : ""}</td>
							<td>${state(r)}</td>
							<td class="text-nowrap">${action(r)}</td>
						</tr>`
					)
					.join("")}</tbody>
			</table>`);
		$body.find("[data-approve]").on("click", (e) => {
			const btn = $(e.currentTarget).prop("disabled", true);
			frappe
				.call({ method: "hasr.api.receiving.quick_approve", args: { session: btn.attr("data-approve") }, freeze: true })
				.then((r) => {
					frappe.show_alert({ message: __("Approved: {0}", [r.message.purchase_receipt]), indicator: "green" });
					load();
				})
				.catch(() => btn.prop("disabled", false));
		});
	}

	function load() {
		frappe.call("hasr.api.receiving.todays_shipments").then((r) => render(r.message || []));
	}

	load();
};
