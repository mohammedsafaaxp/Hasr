# Contributing to hasr

Start with [README.md](README.md) and the feature guide, [docs/FEATURES.md](docs/FEATURES.md): they describe what
hasr does today. Open an issue before a large change, so we agree on the behaviour first.

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
- **Keep the docs in step.** A change that adds, removes or changes what users see also updates
  [README.md](README.md) and [docs/FEATURES.md](docs/FEATURES.md)
  (and the screenshots in `docs/screenshots/` when a screen changed), in the same pull request.
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

If ERPNext behaves differently from what you expect, say so in the pull request with what you found. Business
rules (tolerances, approval roles, limits) are settings in **Hasr Settings**, not guesses in code, and every
setting explains itself on the settings page.
