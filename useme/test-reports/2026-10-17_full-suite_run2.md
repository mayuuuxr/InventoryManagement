# Test Report — 2026-10-17 — full suite run 2 (bill printing + sites fix)

- **Suite:** `manage.py test` (venv python, Django test runner)
- **Version:** 1.1.5 · **git HEAD:** `3793daf`
- **State under test (all UNCOMMITTED):** billing WIP + purchase/sale bill print flow +
  brand sweep (earlier run 1) + `get_default_site()` soft-delete fix + bill-print tests.
- **Result:** ✅ **OK — 135 tests, 0 failures, 0 errors** in 167.5s
- **System check:** no issues (0 silenced). `makemigrations --check --dry-run` → "No changes detected".
- **Count math:** 127 (run 1) + 5 new `BillPrintViewTests` + 3 new `GetDefaultSiteTests` = 135.

## What this run covers
- Sale/purchase bill save → redirect to printable bill (`?ids=`).
- Print layout invariants: SALE/PURCHASE titles, blank `Rate`/`Amt`/`TOTAL` cells,
  whole-number qty on paper (`|whole`), supplier line on purchase prints.
- Print 404 contract: unknown ids / junk ids / empty ids.
- `get_default_site()`: soft-deleted sites ignored; two actives → None; single active → Shop.
- All prior suites (entries ledgers & guards, materials, accounts/axes, reports, core PWA/updater).

## Log noise note (not failures)
Axes lockout tests intentionally trigger PermissionDenied / 404 paths — the WARNING
tracebacks in raw output are expected negative-path evidence, mirrored from run 1.
