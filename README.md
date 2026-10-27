# hasr · حَصر

Receive goods and count stock from a phone, on top of ERPNext.

hasr is an open-source Frappe app installed on the same site as ERPNext. Warehouse staff open
`https://<your-site>/hasr` on their phone, pick a purchase order and scan what arrives. hasr only
creates **draft** Purchase Receipts; a supervisor reviews and approves in Desk. ERPNext stays the
source of truth for items, barcodes, units, orders and stock.

Status: **0.1, online receiving against a purchase order.** Counting, offline mode and batches come in
later milestones (see [docs/MILESTONES.md](docs/MILESTONES.md)).

Supports ERPNext **v15** and **v16**. License: GPLv3.

## Install

```bash
cd frappe-bench
bench get-app https://github.com/<you>/hasr
bench --site <site> install-app hasr
```

No extra steps: the roles **Hasr Counter** and **Hasr Supervisor**, the `Hasr Settings` page and
the Item field *Storage* are created on install. The built phone app is part of the install;
to rebuild it yourself run `cd apps/hasr/frontend && yarn && yarn build`.

## Try 0.1

1. In ERPNext, create (or use) a submitted **Purchase Order** whose items have barcodes
   (Item → Barcodes). Give a case barcode a UOM such as *Box* and add the *Box* conversion factor
   under Item → Units of Measure.
2. Create a user with the **Hasr Counter** role (plus ERPNext's *Stock User* if they also use Desk).
   To limit them to some warehouses, add **User Permissions** on *Warehouse*.
3. Give your supervisor the **Hasr Supervisor** role and permission to create Purchase Receipts
   (for example *Stock User* or *Purchase User*).
4. Optional: set **Hasr Settings → Default Rejected Warehouse**; it is used for rejected quantity,
   because the Purchase Order line has no rejected warehouse in ERPNext.
5. On the phone open `https://<site>/hasr`, sign in, pick the order and scan:
   - a unit barcode adds 1, a case barcode adds the case's conversion factor in stock units;
   - a barcode nobody knows opens the *Unknown barcode* sheet (photo + note for the supervisor);
   - an item that is not on the order is refused and not counted;
   - tap a line to type the quantity, choose the unit and enter rejected (damaged) quantity.
6. Tap **Finish shipment and send for review**.
7. In Desk open **Hasr Receiving Session**, decide any over-receipt (Accept / Cap), link or dismiss
   unknown barcodes, then **Approve and create Purchase Receipt**. The receipt is a draft unless you
   tick *Submit now*.

Camera scanning needs HTTPS (or `localhost`). Hardware (keyboard-wedge) scanners work anywhere.

## Development

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app hasr

cd apps/hasr/frontend
yarn
yarn dev        # http://localhost:8080/hasr, proxies API calls to the bench on :8000 (VITE_BENCH_PORT)
yarn build      # writes hasr/public/frontend and hasr/www/hasr.html
```

Read [CLAUDE.md](CLAUDE.md) and [docs/TECH_SPEC.md](docs/TECH_SPEC.md) before contributing.
All ERPNext calls go through `hasr/erpnext_adapter/`. Open questions live in
[docs/QUESTIONS.md](docs/QUESTIONS.md).
