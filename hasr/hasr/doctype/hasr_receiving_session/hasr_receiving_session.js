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
		// approve buttons follow the server's rules: approver roles (Hasr Settings), not the receiver, warehouses
		hasr_render_review(frm, (data) => {
			const can_act = !data.approval_block_reason;
			if (frm.doc.status === "Pending Approval") {
				if (can_act) {
					frm.add_custom_button(__("Send back"), () => hasr_send_back(frm));
					frm.page.set_primary_action(__("Approve and create Purchase Receipt"), () => hasr_approve(frm));
				} else {
					frm.dashboard.set_headline(
						`<span class="text-muted">${frappe.utils.escape_html(data.approval_block_reason)}</span>`
					);
				}
			}
			return can_act;
		});
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
		title: __("Link barcode {0} to an item", [frappe.utils.escape_html(unknown.barcode)]),
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

// An item that came but is not on the order: add a row to the purchase order and receive it here.
function hasr_add_to_order(frm, unknown) {
	const fields = [
		{
			fieldname: "qty",
			fieldtype: "Float",
			label: __("Quantity ({0})", [__(unknown.stock_uom || "")]),
			default: unknown.qty,
			reqd: 1,
		},
		{
			fieldname: "rate",
			fieldtype: "Currency",
			label: __("Rate per {0}", [__(unknown.stock_uom || "")]),
			default: unknown.suggested_rate,
			description: __("From the supplier's price list or the last purchase rate. Check it against the invoice."),
		},
	];
	if (unknown.has_batch_no) {
		fields.push({ fieldname: "expiry_date", fieldtype: "Date", label: __("Expiry date"), reqd: 1 });
	}
	const d = new frappe.ui.Dialog({
		title: __("Add {0} to purchase order {1}", [
			frappe.utils.escape_html(unknown.item_name || unknown.item_code),
			frappe.utils.escape_html(frm.doc.purchase_order),
		]),
		fields,
		primary_action_label: __("Add to the order and receive"),
		primary_action(values) {
			d.hide();
			hasr_call(
				frm,
				"add_to_order",
				{ name: unknown.name, qty: values.qty, rate: values.rate, expiry_date: values.expiry_date },
				__("Added to the purchase order")
			);
		},
	});
	d.show();
}

function hasr_render_review(frm, on_data) {
	const wrapper = frm.get_field("review_html").$wrapper;
	wrapper.empty();
	if (frm.is_new()) return;

	frappe.call({ method: HASR_API + "get_review", args: { session: frm.doc.name } }).then((r) => {
		const data = r.message;
		const is_supervisor = on_data(data);
		const pending = data.status === "Pending Approval" && is_supervisor;
		const esc = frappe.utils.escape_html;
		const fmt = (v) => format_number(v, null, 3).replace(/\.?0+$/, "");
		const cards = [];

		for (const line of data.lines) {
			if (!["Over", "Accepted", "Capped"].includes(line.over_allowance_state)) continue;
			const total = line.already_received_qty + line.received_qty - (line.free_qty || 0);
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
							? (() => {
									const keep = Math.max(line.pending_qty, 0);
									const excess = Math.max(line.received_qty - keep, 0);
									return `<div class="hasr-decide">
										<button class="btn btn-default btn-sm" data-decide="Cap" data-po-item="${line.po_item}"
											title="${__("The excess is not received and goes back to the supplier.")}">
											${__("Accept {0}, return {1}", [fmt(keep), fmt(excess)])}</button>
										<button class="btn btn-primary btn-sm" data-decide="Accept" data-po-item="${line.po_item}">
											${__("Accept all {0}", [fmt(line.received_qty)])}</button>
									</div>`;
							  })()
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
						<div class="hasr-card-title">${
							u.kind === "Not on order"
								? __("{0} is not on the order · {1} units", [esc(u.item_code), fmt(u.qty)])
								: __("Unknown barcode {0} · {1} units", [esc(u.barcode), fmt(u.qty)])
						}</div>
						<div class="text-muted">${u.note ? __("Note: {0}", [esc(u.note)]) : ""} ${
				u.status !== "Open" ? `· ${__(u.status)} ${esc(u.linked_item || "")}` : u.kind === "Not on order" ? `· ${__("Return it, or add it to the purchase order if you want it.")}` : ""
			}</div>
					</div>
					${
						is_supervisor && u.status === "Open"
							? u.kind === "Not on order"
								? `<button class="btn btn-default btn-sm" data-dismiss="${u.name}">${__("Return to supplier")}</button>
								<button class="btn btn-primary btn-sm" data-add-to-order="${u.name}">${__("Add to the purchase order")}</button>`
								: `<button class="btn btn-default btn-sm" data-dismiss="${u.name}">${__("Dismiss")}</button>
								<button class="btn btn-primary btn-sm" data-link="${u.name}">${__("Link to item")}</button>`
							: ""
					}
				</div>`);
		}

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
		const counts = data.scan_counts || {};
		const sync = __("{0} scans applied, {1} rejected, {2} undone.", [
			counts.Applied || 0,
			counts.Rejected || 0,
			counts.Undo || 0,
		]);

		// summary + the lines as the supervisor reads them (the raw child table stays collapsed below)
		const done = data.lines.filter((l) => l.received_qty - (l.free_qty || 0) >= l.pending_qty).length;
		const summary = `
			<div class="hasr-summary">
				<span class="indicator-pill ${data.match_problems.length ? "orange" : "green"}">${
			data.match_problems.length
				? __("To check: {0}", [data.match_problems.length])
				: __("Matches the order")
		}</span>
				<span>${__("{0} of {1} lines complete", [done, data.lines.length])}</span>
				<span>${__("Supplier invoice")}: <b>${esc(data.supplier_invoice_no || "—")}</b></span>
			</div>`;
		const status_chip = (l) => {
			const short = l.pending_qty - (l.received_qty - (l.free_qty || 0));
			if (["Over", "Accepted"].includes(l.over_allowance_state))
				return `<span class="indicator-pill orange">${__("Over limit")}</span>`;
			if (l.needs_expiry) return `<span class="indicator-pill orange">${__("Expiry date needed")}</span>`;
			if (l.whole_unit_issue) return `<span class="indicator-pill orange">${__("Not a whole unit")}</span>`;
			if (l.mismatch_open) return `<span class="indicator-pill orange">${__("Does not match?")}</span>`;
			if (!l.received_qty) return `<span class="indicator-pill gray">${__("Not received")}</span>`;
			if (short > 0.000001) return `<span class="indicator-pill gray">${__("{0} short", [fmt(short)])}</span>`;
			return `<span class="indicator-pill green">${__("Complete")}</span>`;
		};
		const lines_table = `
			<table class="table table-sm hasr-lines">
				<thead><tr>
					<th>#</th><th>${__("Item")}</th><th class="hasr-num">${__("Ordered")}</th>
					<th class="hasr-num">${__("Received")}</th>
					<th>${__("Expiry dates")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody>${data.lines
					.map(
						(l) => `<tr>
							<td class="text-muted">${l.idx}</td>
							<td>${esc(l.item_name)}<div class="text-muted small">${esc(l.item_code)}${
							l.uom && l.uom !== l.stock_uom
								? ` · ${__("1 {0} = {1} {2}", [esc(__(l.uom)), fmt(l.conversion_factor), esc(__(l.stock_uom))])}`
								: ""
						}</div></td>
							<td class="hasr-num">${fmt(l.pending_qty)}</td>
							<td class="hasr-num ${l.received_qty - (l.free_qty || 0) > l.pending_qty ? "text-warning" : ""}"><b>${fmt(l.received_qty)}</b>${
								l.free_qty ? `<div class="small text-success">${__("{0} free (offer)", [fmt(l.free_qty)])}</div>` : ""
							}</td>
							<td class="small">${(l.batches || [])
								.map((b) => `${frappe.datetime.str_to_user(b.expiry_date)} × ${fmt(b.qty)}`)
								.join("<br>") || (l.has_batch_no ? "—" : "")}</td>
							<td>${status_chip(l)}</td>
						</tr>`
					)
					.join("")}</tbody>
			</table>`;

		wrapper.html(`
			<style>
				.hasr-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; margin-bottom: 8px;
					border: 1px solid var(--border-color); border-radius: 8px; }
				.hasr-warn { background: #FFF3E0; border-color: #F5D5A8; }
				.hasr-card-body { flex: 1; min-width: 0; }
				.hasr-card-title { font-weight: 500; }
				.hasr-photo { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
				.hasr-summary { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 12px; }
				.hasr-lines-title { margin: 16px 0 8px; }
				.hasr-lines td { vertical-align: middle; }
				.hasr-num { text-align: end; }
				.hasr-decide { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
				.hasr-invoices { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
				.hasr-invoice { display: flex; align-items: center; justify-content: center; width: 120px; height: 160px;
					border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
				.hasr-invoice img { width: 100%; height: 100%; object-fit: cover; }
				.hasr-batches { margin: 8px 0 0; }
				.hasr-photo-empty { display: flex; align-items: center; justify-content: center; background: var(--control-bg); }
			</style>
			${summary}
			${cards.length ? cards.join("") : `<p class="text-muted">${__("Nothing needs your decision.")}</p>`}
			${facts.join("")}
			<h5 class="hasr-lines-title">${__("Lines")}</h5>
			${lines_table}
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
		wrapper.find("[data-add-to-order]").on("click", (e) => {
			const name = $(e.currentTarget).attr("data-add-to-order");
			hasr_add_to_order(
				frm,
				data.unknown_barcodes.find((u) => u.name === name)
			);
		});
		wrapper.find("[data-mismatch]").on("click", (e) => {
			const btn = $(e.currentTarget);
			const go = () =>
				hasr_call(frm, "decide_mismatch", {
					name: btn.attr("data-mismatch"),
					decision: btn.attr("data-decision"),
				});
			if (btn.attr("data-decision") === "Wrong") {
				frappe.confirm(__("Remove this quantity from the receipt? It will not be received."), go);
			} else {
				go();
			}
		});
		wrapper.find("[data-dismiss]").on("click", (e) => {
			const name = $(e.currentTarget).attr("data-dismiss");
			frappe.confirm(__("Dismiss this barcode? Its quantity is not received."), () =>
				hasr_call(frm, "dismiss_unknown_barcode", { name })
			);
		});
	});
}
