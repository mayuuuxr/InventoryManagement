# Test Report — 2026-10-17 — full suite after brand sweep

- **Suite:** `manage.py test` (venv python, Django test runner)
- **Version:** 1.1.5 · **git HEAD:** `3793daf`
- **State under test:** WIP billing feature + brand sweep, both uncommitted.
- **Result:** ✅ **OK — 127 tests, 0 failures, 0 errors** in 162.0s
- **System check:** no issues (0 silenced).
- **Coverage notes:**
  - New in this run vs AGENTS.md's "101 tests": +26 (mostly `SaleBillViewTests` ×7 and
    the earlier-added audit/PWA/updater tests). The draft-keeper test now asserts the
    renamed `nibba_entry_draft` key and passes.
  - Typical warning noise in the log is expected/healthy: axes lockout tests intentionally
    trigger PermissionDenied paths; deliberate 404s from negative tests.
- **Also verified post-run:**
  - `db.sqlite3` integrity_check ok + VACUUM ok (brand scrub step).
  - Whole-directory mention scan → 0.
