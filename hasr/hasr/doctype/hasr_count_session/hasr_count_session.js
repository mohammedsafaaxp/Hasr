// Copyright (c) 2026, hasr contributors
// License: GNU General Public License v3. See LICENSE

const HASR_COUNT_API = "hasr.api.counting.";
const COUNT_COLORS = {
	Draft: "gray",
	Counting: "blue",
	Recount: "orange",
	"Pending Approval": "orange",
	Approved: "green",
	Cancelled: "gray",
};

frappe.ui.form.on("Hasr Count Session", {
	setup(frm) {
		frm.set_query("warehouse", () => ({ filters: { is_group: 0, disabled: 0 } }));
		frm.set_query("counter", "zones", () => ({ query: "frappe.core.doctype.user.user.user_query" }));
	},

	refresh(frm) {
		frm.page.set_indicator(__(frm.doc.status), COUNT_COLORS[frm.doc.status] || "gray");
		if (frm.doc.status !== "Draft") frm.disable_save();
		if (frm.is_new()) return;

		if (frm.doc.stock_reconciliation) {
			frm.add_custom_button(__("Open Stock Reconciliation"), () =>
				frappe.set_route("Form", "Stock Reconciliation", frm.doc.stock_reconciliation)
			);
		}
		if (["Draft", "Counting", "Recount", "Pending Approval"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Cancel count"), () =>
				frappe.confirm(__("Cancel this stock count? Nothing is posted to stock and a freeze is lifted."), () =>
					count_call(frm, "cancel")
				)
			);
		}
		if (frm.doc.status === "Draft") {
			frm.page.set_primary_action(__("Start count"), () => {
				const run = () => count_call(frm, "start", {}, __("Counting started"));
				frm.is_dirty() ? frm.save().then(run) : run();
			});
			frm.get_field("review_html").$wrapper.html(
				`<p class="text-muted">${__(
					"Choose what to count and who counts which zone, then start. The counters see the count on their phones; they never see the system quantity."
				)}</p>`
			);
			return;
		}
		count_render(frm);
	},
});

function count_call(frm, method, args = {}, message) {
	return frappe
		.call({ method: HASR_COUNT_API + method, args: { session: frm.doc.name, ...args }, freeze: true })
		.then((r) => {
			if (message) frappe.show_alert({ message, indicator: "green" });
			frm.reload_doc();
			return r.message;
		});
}

function count_render(frm) {
	const wrapper = frm.get_field("review_html").$wrapper;
	frappe.call({ method: HASR_COUNT_API + "review", args: { session: frm.doc.name } }).then((r) => {
		const data = r.message;
		const esc = frappe.utils.escape_html;
		const fmt = (v) => format_number(v, null, 3).replace(/\.?0+$/, "") || "0";
		const money = (v) => format_currency(v, data.currency);
		const t = data.totals;
		count_actions(frm, data);

		const zones = data.zones
			.map(
				(z) => `<div class="hasr-zone">
					<b>${esc(z.zone)}</b> · ${esc(z.counter_name || z.counter)}
					<span class="text-muted">· ${__("{0} counted", [z.entries])}</span>
					${
						z.handed_over
							? `<span class="indicator-pill green">${__("Handed over")}</span>`
							: data.status === "Counting"
							? `<span class="indicator-pill blue">${__("Counting")}</span>`
							: ""
					}
				</div>`
			)
			.join("");

		const freeze = data.frozen
			? `<div class="hasr-card hasr-warn"><div class="hasr-card-body">
					<div class="hasr-card-title">${__("Stock is frozen")}</div>
					<div class="text-muted">${
						data.frozen_until
							? __("Movements of these items in this warehouse are refused until {0}, or until the count is approved.", [
									frappe.datetime.str_to_user(data.frozen_until),
							  ])
							: __("Movements of these items in this warehouse are refused until the count is approved.")
					}</div></div></div>`
			: "";

		const steps = [];
		if (data.status === "Recount") {
			if (t.needs_recount)
				steps.push(
					__("{0} of {1} lines outside tolerance recounted.", [t.recounted, t.needs_recount]) +
						(t.unassigned_recount ? " " + __("{0} not given to a recounter yet.", [t.unassigned_recount]) : "")
				);
			if (t.test_sample) steps.push(__("{0} of {1} test counts entered.", [t.test_counted, t.test_sample]));
		}
		if (data.status === "Pending Approval" && t.missing_reasons)
			steps.push(__("{0} differences still need a reason.", [t.missing_reasons]));
		if (data.status === "Pending Approval" && data.approval_block_reason) steps.push(esc(data.approval_block_reason));

		const summary = `<div class="hasr-summary">
			<span>${__("{0} of {1} lines counted", [t.counted, t.lines])}</span>
			${
				["Pending Approval", "Approved"].includes(data.status)
					? `<span>${__("Differences")}: <b>${t.differences}</b></span>
					   <span>${__("Gain")}: <b class="text-success">${money(t.gain_value)}</b></span>
					   <span>${__("Loss")}: <b class="text-danger">${money(t.loss_value)}</b></span>`
					: ""
			}
		</div>`;

		const show_final = ["Pending Approval", "Approved"].includes(data.status);
		const state = (l) => {
			if (l.needs_recount && !l.recounted) return `<span class="indicator-pill orange">${__("Recount")}</span>`;
			if (l.test_sample && !l.test_counted) return `<span class="indicator-pill blue">${__("Test count")}</span>`;
			if (!l.counted && data.status === "Counting") return `<span class="indicator-pill gray">${__("Not counted")}</span>`;
			if (show_final && Math.abs(l.variance_qty) > 1e-6)
				return `<span class="indicator-pill ${l.within_tolerance ? "yellow" : "red"}">${
					l.within_tolerance ? __("Within tolerance") : __("Outside tolerance")
				}</span>`;
			if (data.status === "Counting") return `<span class="indicator-pill green">${__("Counted")}</span>`;
			return `<span class="indicator-pill green">${__("Matches")}</span>`;
		};
		const lines = data.lines
			.map(
				(l) => `<tr>
				<td>${esc(l.item_name)}<div class="text-muted small">${esc(l.item_code)}${l.batch_no ? " · " + esc(l.batch_no) : ""}${
					l.added_by_counter ? " · " + __("found during the count") : ""
				}</div></td>
				<td class="text-muted">${esc(l.abc_class || "")}</td>
				<td class="hasr-num">${fmt(l.system_qty)}</td>
				<td class="hasr-num">${l.counted ? fmt(l.count_1_qty) : "—"}</td>
				<td class="hasr-num">${l.recounted ? fmt(l.count_2_qty) : l.needs_recount ? "…" : ""}</td>
				<td class="hasr-num">${l.test_counted ? fmt(l.test_count_qty) : l.test_sample ? "…" : ""}</td>
				<td class="hasr-num">${show_final ? `<b>${fmt(l.final_qty)}</b>` : ""}</td>
				<td class="hasr-num ${l.variance_qty < 0 ? "text-danger" : l.variance_qty > 0 ? "text-success" : ""}">${
					show_final && Math.abs(l.variance_qty) > 1e-6 ? fmt(l.variance_qty) + `<div class="small">${money(l.variance_value)}</div>` : ""
				}</td>
				<td>${state(l)}${l.reason ? `<div class="small">${esc(__(l.reason))}${l.reason_note ? ": " + esc(l.reason_note) : ""}</div>` : ""}</td>
			</tr>`
			)
			.join("");

		wrapper.html(`
			<style>
				.hasr-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; margin-bottom: 8px;
					border: 1px solid var(--border-color); border-radius: 8px; }
				.hasr-warn { background: #FFF3E0; border-color: #F5D5A8; }
				.hasr-card-body { flex: 1; min-width: 0; }
				.hasr-card-title { font-weight: 500; }
				.hasr-summary { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin: 12px 0; }
				.hasr-zone { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 6px 0;
					border-bottom: 1px solid var(--border-color); }
				.hasr-lines td { vertical-align: middle; }
				.hasr-num { text-align: end; white-space: nowrap; }
				.hasr-steps { margin: 8px 0; padding-inline-start: 18px; }
			</style>
			${freeze}
			<h5>${__("Zones")}</h5>
			${zones}
			${steps.length ? `<ul class="hasr-steps">${steps.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}
			${summary}
			<table class="table table-sm hasr-lines">
				<thead><tr>
					<th>${__("Item")}</th><th>${__("ABC")}</th><th class="hasr-num">${__("System")}</th>
					<th class="hasr-num">${__("Count")}</th><th class="hasr-num">${__("Recount")}</th>
					<th class="hasr-num">${__("Test count")}</th><th class="hasr-num">${__("Final")}</th>
					<th class="hasr-num">${__("Difference")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody>${lines}</tbody>
			</table>`);
	});
}

function count_actions(frm, data) {
	const t = data.totals;
	if (data.frozen) {
		frm.add_custom_button(__("Lift freeze"), () =>
			frappe.confirm(__("Lift the freeze now? Stock can move again while the count is still open."), () =>
				count_call(frm, "release_freeze", {}, __("Freeze lifted"))
			)
		);
	}
	if (data.status === "Counting") {
		const open = data.zones.filter((z) => !z.handed_over).length;
		frm.page.set_primary_action(__("Close counting"), () => {
			const go = () => count_call(frm, "close_counting", {}, __("Counting closed"));
			open
				? frappe.confirm(
						__("{0} zones have not been handed over. Items they did not count are taken as not found. Close anyway?", [open]),
						go
				  )
				: go();
		});
	}
	if (data.status === "Recount") {
		if (t.needs_recount) frm.add_custom_button(__("Give recount to…"), () => count_assign(frm, data));
		if (t.test_sample) frm.add_custom_button(__("Enter test counts"), () => count_test(frm, data));
		frm.page.set_primary_action(__("Finish review"), () => count_call(frm, "finish_review", {}, __("Ready for approval")));
	}
	if (data.status === "Pending Approval") {
		if (t.differences) frm.add_custom_button(__("Reasons for differences"), () => count_reasons(frm, data));
		if (!data.approval_block_reason) {
			frm.page.set_primary_action(__("Approve and create Stock Reconciliation"), () => count_approve(frm, data));
		}
	}
}

function count_assign(frm, data) {
	const d = new frappe.ui.Dialog({
		title: __("Give the recount to"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"{0} lines are outside tolerance. Someone who did not count them the first time counts them again, blind.",
					[data.totals.needs_recount]
				)}</p>`,
			},
			{ fieldname: "user", fieldtype: "Link", options: "User", label: __("Recounter"), reqd: 1 },
		],
		primary_action_label: __("Give recount"),
		primary_action(values) {
			d.hide();
			count_call(frm, "assign_recount", { user: values.user }).then((res) => {
				if (res && res.refused && res.refused.length)
					frappe.msgprint(__("{0} counted these the first time; give them to someone else: {1}", [values.user, res.refused.join(", ")]));
			});
		},
	});
	d.show();
}

function count_test(frm, data) {
	const sample = data.lines.filter((l) => l.test_sample);
	const fields = [
		{
			fieldtype: "HTML",
			options: `<p class="text-muted">${__(
				"Count these yourself, as a spot check of lines that looked right. Do not look at the earlier count first."
			)}</p>`,
		},
		...sample.map((l) => ({
			fieldname: l.name,
			fieldtype: "Float",
			label: `${l.item_name}${l.batch_no ? " · " + l.batch_no : ""} (${__(l.stock_uom)})`,
			default: l.test_counted ? l.test_count_qty : undefined,
		})),
	];
	const d = new frappe.ui.Dialog({
		title: __("Test counts"),
		fields,
		primary_action_label: __("Save"),
		async primary_action(values) {
			d.hide();
			for (const l of sample) {
				if (values[l.name] === undefined || values[l.name] === null || values[l.name] === "") continue;
				await frappe.call({
					method: HASR_COUNT_API + "set_test_count",
					args: { session: frm.doc.name, line: l.name, qty: values[l.name] },
					freeze: true,
				});
			}
			frm.reload_doc();
		},
	});
	d.show();
}

function count_reasons(frm, data) {
	const diffs = data.lines.filter((l) => Math.abs(l.variance_qty) > 1e-6);
	const fmt = (v) => format_number(v, null, 3).replace(/\.?0+$/, "") || "0";
	const options = ["", ...data.reasons].map((r) => ({ value: r, label: r ? __(r) : "" }));
	const fields = [
		{ fieldname: "all", fieldtype: "Select", label: __("Same reason for every line without one"), options },
	];
	for (const l of diffs) {
		fields.push(
			{ fieldtype: "Section Break", label: `${l.item_name}${l.batch_no ? " · " + l.batch_no : ""}: ${fmt(l.variance_qty)} ${__(l.stock_uom)}` },
			{ fieldname: `r_${l.name}`, fieldtype: "Select", label: __("Reason"), options, default: l.reason || "" },
			{ fieldtype: "Column Break" },
			{ fieldname: `n_${l.name}`, fieldtype: "Data", label: __("Note"), default: l.reason_note || "" }
		);
	}
	const d = new frappe.ui.Dialog({
		title: __("Reasons for differences"),
		size: "large",
		fields,
		primary_action_label: __("Save"),
		primary_action(values) {
			const reasons = {};
			for (const l of diffs) {
				reasons[l.name] = { reason: values[`r_${l.name}`] || values.all || null, note: values[`n_${l.name}`] || null };
			}
			d.hide();
			count_call(frm, "set_reasons", { reasons }, __("Saved"));
		},
	});
	d.show();
}

function count_approve(frm, data) {
	const can_submit = frappe.model.can_submit("Stock Reconciliation");
	const d = new frappe.ui.Dialog({
		title: __("Approve the count"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${
					data.totals.differences
						? __(
								"A draft Stock Reconciliation is created for the {0} differences. Stock changes when it is submitted; a freeze lasts until then.",
								[data.totals.differences]
						  )
						: __("Every line matches the system. Nothing is posted.")
				}</p>`,
			},
			{
				fieldname: "submit",
				fieldtype: "Check",
				label: __("Submit the Stock Reconciliation now"),
				hidden: can_submit && data.totals.differences ? 0 : 1,
			},
		],
		primary_action_label: __("Approve"),
		primary_action(values) {
			d.hide();
			count_call(frm, "approve", { submit: values.submit ? 1 : 0 }, __("Count approved"));
		},
	});
	d.show();
}
