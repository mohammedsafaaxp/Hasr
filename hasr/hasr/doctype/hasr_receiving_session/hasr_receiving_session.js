// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

const HASR_API = "hasr.api.receiving.";
const STATUS_COLORS = {
	Open: "blue",
	"Pending Approval": "orange",
	Approved: "green",
	"Sent Back": "red",
	Cancelled: "gray",
};

frappe.ui.form.on("Hasr Receiving Session", {
	refresh(frm) {
		frm.disable_save();
		const is_supervisor = frappe.user.has_role(["Hasr Supervisor", "System Manager"]);
		frm.page.set_indicator(__(frm.doc.status), STATUS_COLORS[frm.doc.status] || "gray");

		if (is_supervisor && frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("Send back"), () => hasr_send_back(frm));
			frm.page.set_primary_action(__("Approve and create Purchase Receipt"), () => hasr_approve(frm));
		}
		if (frm.doc.purchase_receipt) {
			frm.add_custom_button(__("Open Purchase Receipt"), () =>
				frappe.set_route("Form", "Purchase Receipt", frm.doc.purchase_receipt)
			);
		}
		if (is_supervisor && ["Open", "Sent Back", "Pending Approval"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Cancel session"), () =>
				frappe.confirm(__("Cancel this receiving session? Nothing is posted to stock."), () =>
					hasr_call(frm, "cancel_session", { session: frm.doc.name })
				)
			);
		}
		hasr_render_review(frm, is_supervisor);
	},
});

function hasr_call(frm, method, args, message) {
	return frappe
		.call({ method: HASR_API + method, args, freeze: true })
		.then((r) => {
			if (message) frappe.show_alert({ message, indicator: "green" });
			frm.reload_doc();
			return r.message;
		});
}

function hasr_approve(frm) {
	const can_submit = frappe.model.can_submit("Purchase Receipt");
	const d = new frappe.ui.Dialog({
		title: __("Approve and create Purchase Receipt"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"A draft Purchase Receipt is created from this session. Stock changes only when the receipt is submitted."
				)}</p>`,
			},
			{
				fieldname: "submit",
				fieldtype: "Check",
				label: __("Submit the Purchase Receipt now"),
				hidden: can_submit ? 0 : 1,
			},
		],
		primary_action_label: __("Approve"),
		primary_action(values) {
			d.hide();
			hasr_call(
				frm,
				"approve",
				{ session: frm.doc.name, submit: values.submit ? 1 : 0 },
				__("Purchase Receipt created")
			);
		},
	});
	d.show();
}

function hasr_send_back(frm) {
	frappe.prompt(
		{ fieldname: "note", fieldtype: "Small Text", label: __("What should the counter fix?") },
		(values) => hasr_call(frm, "send_back", { session: frm.doc.name, note: values.note }, __("Sent back")),
		__("Send back"),
		__("Send back")
	);
}

function hasr_link_unknown(frm, unknown) {
	const d = new frappe.ui.Dialog({
		title: __("Link barcode {0} to an item", [unknown.barcode]),
		fields: [
			{
				fieldname: "item_code",
				fieldtype: "Link",
				options: "Item",
				label: __("Item"),
				reqd: 1,
				get_query: () => ({
					filters: { name: ["in", (frm.doc.lines || []).map((l) => l.item_code)] },
				}),
			},
			{
				fieldname: "uom",
				fieldtype: "Link",
				options: "UOM",
				label: __("Barcode unit"),
				description: __("Leave empty when the barcode is on a single unit."),
			},
		],
		primary_action_label: __("Link"),
		primary_action(values) {
			d.hide();
			hasr_call(
				frm,
				"link_unknown_barcode",
				{ name: unknown.name, item_code: values.item_code, uom: values.uom },
				__("Barcode linked")
			);
		},
	});
	d.show();
}

function hasr_render_review(frm, is_supervisor) {
	const wrapper = frm.get_field("review_html").$wrapper;
	wrapper.empty();
	if (frm.is_new()) return;

	frappe.call({ method: HASR_API + "get_review", args: { session: frm.doc.name } }).then((r) => {
		const data = r.message;
		const pending = data.status === "Pending Approval" && is_supervisor;
		const esc = frappe.utils.escape_html;
		const fmt = (v) => format_number(v, null, 3).replace(/\.?0+$/, "");
		const cards = [];

		for (const line of data.lines) {
			if (!["Over", "Accepted", "Capped"].includes(line.over_allowance_state)) continue;
			const total = line.already_received_qty + line.received_qty + line.rejected_qty;
			const over = total - line.allowed_qty;
			const state = line.over_allowance_state;
			cards.push(`
				<div class="hasr-card ${state === "Over" ? "hasr-warn" : ""}">
					<div class="hasr-card-body">
						<div class="hasr-card-title">${__("{0}: received {1}, ordered {2}", [
							esc(line.item_name),
							fmt(line.received_qty),
							fmt(line.pending_qty),
						])}</div>
						<div class="text-muted">${
							state === "Over"
								? __("{0} {1} over the {2}% over-receipt allowance", [
										fmt(over),
										esc(__(line.stock_uom)),
										fmt(data.allowance[line.po_item] || 0),
								  ])
								: __("Decision: {0}", [__(state)])
						}</div>
					</div>
					${
						pending
							? `<button class="btn btn-default btn-sm" data-decide="Cap" data-po-item="${line.po_item}">
									${__("Accept {0} only", [fmt(Math.max(line.pending_qty - line.rejected_qty, 0))])}</button>
								<button class="btn btn-primary btn-sm" data-decide="Accept" data-po-item="${line.po_item}">
									${__("Accept {0}", [fmt(line.received_qty)])}</button>`
							: ""
					}
				</div>`);
		}

		for (const u of data.unknown_barcodes) {
			const photo = u.photo
				? `<a href="${esc(u.photo)}" target="_blank"><img src="${esc(u.photo)}" class="hasr-photo"></a>`
				: `<div class="hasr-photo hasr-photo-empty">${frappe.utils.icon("image", "md")}</div>`;
			cards.push(`
				<div class="hasr-card">
					${photo}
					<div class="hasr-card-body">
						<div class="hasr-card-title">${__("Unknown barcode {0} · {1} units", [esc(u.barcode), fmt(u.qty)])}</div>
						<div class="text-muted">${u.note ? __("Note: {0}", [esc(u.note)]) : ""} ${
				u.status !== "Open" ? `· ${__(u.status)} ${esc(u.linked_item || "")}` : ""
			}</div>
					</div>
					${
						is_supervisor && u.status === "Open"
							? `<button class="btn btn-default btn-sm" data-dismiss="${u.name}">${__("Dismiss")}</button>
								<button class="btn btn-primary btn-sm" data-link="${u.name}">${__("Link to item")}</button>`
							: ""
					}
				</div>`);
		}

		const batch_lines = data.lines.filter((l) => l.has_batch_no && (l.received_qty || l.rejected_qty));
		const facts = [];
		if (data.invoices.length) {
			const links = data.invoices
				.map((f) => {
					const is_pdf = /\.pdf$/i.test(f.file_name);
					return `<a href="${esc(f.file_url)}" target="_blank" class="hasr-invoice">${
						is_pdf ? frappe.utils.icon("file", "lg") : `<img src="${esc(f.file_url)}">`
					}</a>`;
				})
				.join("");
			facts.push(`
				<div class="hasr-card">
					<div class="hasr-card-body">
						<div class="hasr-card-title">${__("Supplier invoice")}</div>
						<div class="text-muted">${__("Check the received quantities against it. It is attached to the Purchase Receipt on approval.")}</div>
						<div class="hasr-invoices">${links}</div>
					</div>
				</div>`);
		} else if (data.status === "Pending Approval") {
			facts.push(`<p class="text-muted">${__("No supplier invoice was attached.")}</p>`);
		}
		if (batch_lines.length) {
			const rows = batch_lines
				.map((l) => {
					const parts = (l.batches || []).map(
						(b) => `${frappe.datetime.str_to_user(b.expiry_date)} × ${fmt(b.qty)}`
					);
					return `<tr><td>${esc(l.item_name)}</td><td>${
						parts.length ? parts.join(", ") : `<span class="text-danger">${__("Expiry date needed")}</span>`
					}</td></tr>`;
				})
				.join("");
			facts.push(`
				<div class="hasr-card">
					<div class="hasr-card-body">
						<div class="hasr-card-title">${__("Expiry dates")}</div>
						<div class="text-muted">${__("One new batch is created per expiry date on approval.")}</div>
						<table class="table table-sm hasr-batches"><tbody>${rows}</tbody></table>
					</div>
				</div>`);
		}

		const counts = data.scan_counts || {};
		const sync = __("{0} scans applied, {1} rejected, {2} undone.", [
			counts.Applied || 0,
			counts.Rejected || 0,
			counts.Undo || 0,
		]);

		wrapper.html(`
			<style>
				.hasr-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; margin-bottom: 8px;
					border: 1px solid var(--border-color); border-radius: 8px; }
				.hasr-warn { background: #FFF3E0; border-color: #F5D5A8; }
				.hasr-card-body { flex: 1; min-width: 0; }
				.hasr-card-title { font-weight: 500; }
				.hasr-photo { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
				.hasr-invoices { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
				.hasr-invoice { display: flex; align-items: center; justify-content: center; width: 120px; height: 160px;
					border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
				.hasr-invoice img { width: 100%; height: 100%; object-fit: cover; }
				.hasr-batches { margin: 8px 0 0; }
				.hasr-photo-empty { display: flex; align-items: center; justify-content: center; background: var(--control-bg); }
			</style>
			${cards.length ? cards.join("") : `<p class="text-muted">${__("Nothing needs your decision.")}</p>`}
			${facts.join("")}
			<p class="text-muted small">${sync}</p>
		`);

		wrapper.find("[data-decide]").on("click", (e) => {
			const btn = $(e.currentTarget);
			hasr_call(frm, "decide_line", {
				session: frm.doc.name,
				po_item: btn.attr("data-po-item"),
				decision: btn.attr("data-decide"),
			});
		});
		wrapper.find("[data-link]").on("click", (e) => {
			const name = $(e.currentTarget).attr("data-link");
			hasr_link_unknown(
				frm,
				data.unknown_barcodes.find((u) => u.name === name)
			);
		});
		wrapper.find("[data-dismiss]").on("click", (e) => {
			const name = $(e.currentTarget).attr("data-dismiss");
			frappe.confirm(__("Dismiss this barcode? Its quantity is not received."), () =>
				hasr_call(frm, "dismiss_unknown_barcode", { name })
			);
		});
	});
}
