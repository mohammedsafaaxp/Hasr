# Contributing to hasr

Read these before writing code:

1. [docs/PRD.md](docs/PRD.md): what we are building and why.
2. [docs/TECH_SPEC.md](docs/TECH_SPEC.md): architecture, DocTypes, APIs, ERPNext integration. This is the contract.
3. [docs/MILESTONES.md](docs/MILESTONES.md): the current milestone and its acceptance criteria. Build only that.
4. [docs/design/README.md](docs/design/README.md) and `docs/design/screens/*.png`: the UI to match.

## Ground rules

- **Never modify Frappe or ERPNext source.** Everything lives in this app: hooks, DocTypes,
  Custom Fields (as fixtures), API methods, the Vue frontend.
- **The phone never changes stock.** It only creates *draft* Purchase Receipts and *draft*
  Stock Reconciliations. Submitting is always a human with the right role, in Desk or the review screen.
- **ERPNext is the source of truth** for items, barcodes, UOMs, POs, batches, bins and accounting.
  Do not copy that data into hasr DocTypes except as snapshots the spec names explicitly.
- **Support ERPNext v15 and v16.** Keep version-specific code in `hasr/erpnext_adapter/`, the only
  package that imports `erpnext`.
- **Idempotent writes.** Every scan from the phone carries a client-generated UUID. The server accepts
  the same UUID twice without double-counting.
- **i18n from day one.** English is the default, Arabic (RTL) must work. Wrap every user-facing string
  (`_()` in Python, `__()` in the frontend and Desk scripts) and add it to `hasr/translations/ar.csv`.
  Use logical CSS (`ps-`, `pe-`, `ms-`, `me-`, `start`, `end`), never left/right.
- **Tests with every change** (`FrappeTestCase`), covering each acceptance criterion.
- **Small commits, one concern each**, with conventional messages (`feat:`, `fix:`, `test:`, `docs:`).
- **License GPLv3.** Do not paste code from sources with incompatible licenses.
- **No proprietary data.** Fixtures and test data use invented names.

## Commands

```bash
bench --site <site> run-tests --app hasr
cd apps/hasr/frontend && yarn && yarn dev     # frontend dev server
cd apps/hasr/frontend && yarn build           # builds into hasr/public/frontend + hasr/www/hasr.html
```

## When unsure

If the spec is silent or contradicts ERPNext behaviour, write the question into
[docs/QUESTIONS.md](docs/QUESTIONS.md) with what you found. Business rules (tolerances, approval limits,
freeze duration) are settings in **Hasr Settings**, not guesses in code.
