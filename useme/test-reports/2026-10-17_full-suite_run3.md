# Test Report — 2026-10-17 — full suite run 3 (v1.2.0 release gate)

- **Suite:** `manage.py test` (venv python, Django test runner)
- **Version:** 1.2.0 · **git HEAD:** `671f458` (tag `v1.2.0`)
- **State under test:** the v1.2.0 release stack (billing WIP + brand sweep +
  shop-context/printing + sidebar split) — code identical to what was committed
  minutes later; only `VERSION` and these report files changed in between.
- **Result:** ✅ **OK — 139 tests, 0 failures, 0 errors** in 183.5s (finished 23:48 IST)
- **System check:** no issues (0 silenced); discovery echoed "Found 139 test(s)."
- **Count math:** 135 (run 2) + 4 new `PurchaseBillViewTests` = 139.

## What this run covers
- Everything from run 2: bill save → print redirect (`?ids=`), blank
  Rate/Amt/TOTAL print contract, `|whole` qty on paper, print 404 contracts,
  `get_default_site()` soft-delete fix.
- Sidebar split + label changes: sale shows "Customer Name" with the field
  rendering blank (no "Walk-in customer" default); purchase shows "Supplier Name".
- New `PurchaseBillViewTests`: auth gate + save-redirect contract for the
  purchase flow (mirror of the sale-side tests).

## Log noise note (not failures)
- Axes lockout tests intentionally trigger PermissionDenied / 404 — the WARNING
  tracebacks in raw output are expected negative-path evidence, same as runs 1-2.
- **Harness quirk worth remembering:** the run was piped through
  `2>&1 | Out-String` in Windows PowerShell and the tool wrapper reported
  "exit code 1" even though Django printed `Ran 139 tests in 183.546s` + `OK`
  with no `FAILED` marker. Python block-buffers stdout when piped, so stdout
  lines ("Found 139 test(s).", report prints like "MAT-DETAIL: …") appear
  AFTER the stderr-heavy tail in the merged capture. Django's own summary line
  is authoritative: this run is green.
