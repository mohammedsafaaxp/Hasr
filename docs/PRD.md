# PRD: hasr

**Receiving and stock counts from a phone, on top of ERPNext**

Status: draft 1 · Updated: 27 Oct 2026 · Owner: Mohammed Safaa · License: GPLv3

## Problem Alignment

In most warehouses that run ERPNext, receiving and stock counts still happen on paper or in Excel and are keyed into the system later. That causes data-entry errors, stock balances that lag reality by hours or days, and counts that take days and stop operations.

ERPNext screens are built for a desktop, not for a worker standing between shelves with a phone in one hand and gloves on. Dedicated handheld scanners are expensive, while most workers already carry an Android or iOS phone.

There is no open-source tool that lets a worker receive and count directly into ERPNext from a phone, in a way that respects audit controls and keeps working when the network drops.

## Why Now

ERPNext adoption keeps growing in retail, grocery and distribution, and most teams solve this with private customizations nobody shares. ERPNext v15 changed how batches and serials are stored (Serial and Batch Bundle), which broke many older solutions, so a tool built for the current model is timely. frappe-ui is mature, and Frappe's own apps (Helpdesk, CRM, Frappe HR) show that a modern web frontend on Frappe works. The team has first-hand warehouse experience, so decisions come from the floor, not assumptions.

## Solution Summary

hasr is an open-source Frappe app installed on the same site as ERPNext. It serves a mobile web app that installs to the home screen and works offline.

ERPNext stays the source of truth. hasr reads purchase orders, items, barcodes, UOMs, balances and batches, and writes drafts only: Purchase Receipts and Stock Reconciliations. A supervisor always approves. ERPNext itself posts stock and accounting entries. hasr never modifies ERPNext code.

**Receiving.** The worker picks a purchase order and scans items with the camera or a hardware scanner. Each line passes three checks: the barcode is known, the item is on the order, and the quantity is within ERPNext's over-receipt allowance. A case barcode converts to units through the item's barcode UOM and conversion factor. For batch-tracked items the worker only enters the expiry date and the system creates one batch per expiry date; the final batch number is fixed on approval. GS1 barcodes that carry batch (AI 10) and expiry (AI 17) fill those fields automatically. Damaged goods are recorded as rejected and go to the rejected warehouse. An unknown barcode is saved with a photo and a note for the supervisor to link; the phone never creates items.

One purchase order can be received across several shipments. Each shipment is its own receiving session and produces one draft Purchase Receipt. Remaining quantities exclude shipments still pending approval. Only one open shipment per order at a time. When finishing, the worker says whether the rest is still coming; the supervisor decides whether to close the order.

**Counting.** Counting follows three international references: ISA 501 for count procedures an auditor accepts, ASCM/APICS cycle-counting practice, and the GS1 barcode standard. There are two count types: a full count with the whole scope frozen, and a cycle count in small ABC batches. The supervisor picks the scope (whole warehouse, item group, brand, hand-picked items, the ABC batch that is due, or problem items) and how people enter counts (scan, or pick from a list and type the quantity).

Counts are blind: system stock is hidden. Batch-tracked items are always counted per batch. Each zone has one counter; a variance outside tolerance is recounted once by someone else, and the supervisor test-counts a sample of lines without variance. The result is a draft Stock Reconciliation dated at count time, with a reason recorded for every approved variance.

**Freeze.** When a count starts, in-scope items can be frozen in that warehouse. hasr validates every Stock Ledger Entry and rejects sales, receipts and transfers on frozen items, except the session's own reconciliation. The freeze lifts on approval or cancellation, manually by a manager, or automatically after a maximum duration. Freezing is optional; a cycle count can run without it by comparing against the balance at the moment each item is counted.

**Item details.** Every receiving and counting screen shows the item photo, which opens full-screen to zoom, plus code, description, group, brand, units, barcodes, shelf life, weight and last receipt. During counts the balance is never shown.

**Supervisor review.** Supervisors review sessions in Desk, with pending decisions ready to act on (accept or cap an over-receipt, link an unknown barcode), then approve to create the Purchase Receipt or Stock Reconciliation.

## Target Users

The primary user is the storekeeper or warehouse worker who receives shipments and counts shelves from a phone and needs something fast, one-handed, glove-friendly, and usable in a cold room without signal. The warehouse supervisor opens counts, assigns zones, reviews shipments and variances, and approves; they need clear control and an audit trail. The accountant cares that balances, valuation and entries are right and that counts survive an audit. The ERPNext developer or admin installs, configures and may contribute; they need a simple install, clear docs and code that survives ERPNext upgrades. Target businesses are retail, grocery, dark stores, distributors and pharmacies, in any country and language.

## Definition of Success

For the first release, success means at least one real warehouse receives and counts with hasr instead of paper for [TBD] weeks without going back. In operation we track inventory record accuracy (share of counted lines within tolerance); the common industry target is 95% or higher, ours is [TBD]. We also track time from shipment arrival to draft receipt [TBD] and receipts that need correction after approval [TBD]. As an open-source project we track sites installed, outside contributors and languages added, targets [TBD].

## UX/Design Principles

The interface follows Frappe's own apps: white, gray and black, thin borders, Lucide line icons, 8px corners, no gradients or shadows except a soft one under toasts. Status colors (green complete, orange warning, red error, blue frozen) mean status only. One black button per screen shows the next step, and every tap target is at least 44px. The scan field is always ready and accepts keyboard-wedge scanners; every scan gives sound, vibration and an undo. English LTR is the default; the app follows the device language and mirrors for RTL scripts such as Arabic; dates and numbers follow the locale. Fonts are Inter for Latin and numbers and IBM Plex Sans Arabic for Arabic. The brand is "hasr" (Arabic lockup "حَصر"); the mark is a tally in a black square with the crossing stroke in safety yellow #F5B800, used for the logo only. Workers see only what they need: balances are hidden during counts, and sensitive decisions belong to the supervisor.

## Scope and Capabilities

### In-Scope

Release one covers receiving against a purchase order with the three checks and case-to-unit conversion; multiple shipments per order; automatic batches with required expiry for tracked items; GS1 parsing of batch and expiry; rejected quantity; unknown barcodes with photo; full and cycle counts, by scan or by list, per batch; blind counting, recount and test counts; freeze during counts; draft Purchase Receipts and Stock Reconciliations; supervisor review in Desk; item details with photos and zoom; offline work with a unique ID per scan; English and Arabic; sign-in with the ERPNext account, existing roles plus a new counter role; ERPNext v15 and v16.

### Out-of-Scope

Release one does not cover receiving without a purchase order (release two, behind a role and supervisor approval), serial numbers (release two), bin locations, warehouse transfers, supplier returns, barcode label printing, native store apps (hasr stays an installable web app), or running as a separate app that talks to ERPNext remotely (the code stays layered so it can be added later).

## Delivery, Risks and Open Questions

### Delivery

hasr is a Frappe app with `required_apps = ["erpnext"]`, installed with `bench get-app` and `install-app`. The frontend is Vue with frappe-ui served from the same site; the API is whitelisted methods. Milestones: 0.1 online receiving against a purchase order; 0.2 offline, hardware scanners, batches and expiry, rejected quantity, multiple shipments; 0.3 counting with freeze; 1.0 public release with docs in English and Arabic, a demo site with invented data, CI on v15 and v16, and an announcement on the Frappe forum. Dates are [TBD] until weekly hours are set.

### Risks

Freezing stops sales on frozen items, so dark-store orders containing them fail during a count; mitigated by making freeze optional, counting in small batches or at night, and a maximum freeze duration. iOS Safari lacks the built-in BarcodeDetector API, so we ship a JS scanner library; camera access and home-screen install require HTTPS. Batch storage differs across ERPNext versions; mitigated by an adapter layer and CI on both versions. Some hosting (for example shared plans on Frappe Cloud) does not allow custom apps. The idea came from real work at a company, so the code is written from scratch on personal time with no code, data or names from that job. Workers return to paper if the app is slower at first; mitigated by an early field pilot.

### Open Questions

Is there an existing open-source app on the Frappe marketplace or GitHub we should contribute to instead? Are the name, domain and GitHub org available internationally? What tolerance per ABC class (suggested start A ±1%, B ±2%, C ±5%) and does it vary by item value [TBD]? Count frequency per class (suggested A monthly, B quarterly, C twice a year) [TBD]? Test-count sample size [TBD]? Variance approval limits by value and who approves each [TBD]? Maximum freeze duration [TBD]? Minimum remaining shelf life accepted at receipt before warning [TBD]? If a batch-tracked item is counted without batches by mistake, reject it or allocate the variance to the earliest-expiring batch? Which warehouse runs the first field pilot?
