# Bug Log (newest first)

Format per entry: `date | VERSION | git HEAD | status (OPEN / FIXED / WATCH) | detail`

The old brand string (removed 2026-10-17) is never spelled in these logs —
referred to as "the old brand string".

---

## 2026-10-18 | 1.2.1 | WATCH | Portable-runtime pip fails TLS setup during update.bat package sync

During the first real update.bat run (v1.2.1 install on the shop copy), the pip step
printed a full traceback ending `FileNotFoundError ... certifi.where()` inside
`pip._vendor.truststore` (the portable runtime's certifi layout). The bat correctly
downgraded it to "WARNING: package sync had errors - continuing with migrate anyway"
and the update proceeded — requirements-pc.txt is identical between v1.2.0 and
v1.2.1, so nothing needed installing. **Risk:** if a future release ADDS a
dependency, the automatic package sync through update.bat will fail on the portable
runtime; stopgap = run the sync manually (`runtime\Scripts\python.exe -m pip install
-r requirements-pc.txt` from the install dir, or venv). Root cause not investigated
tonight — repair later, before a dependency-changing release ships.

---

## 2026-10-18 | 1.2.1 | FIXED | update.bat was parse-broken on every invocation

Root cause proven by an A/B sandbox probe (scratch tools
`%TEMP%\opencode\probe_updatebat.ps1` + `trace_updatebat.ps1`; original bytes replayed
from `git show HEAD:update.bat`). Five unescaped `(`/`)` in `echo` text inside
`if (...)` blocks — cmd parses a whole `if (...)` block when reached, BEFORE evaluating
its condition:

- **line 25** (no-runtime error): broke the parse on EVERY invocation — the exact
  shop-PC signature ". was unexpected at this time.", exit 255, no output, args or not
  (pristine-HEAD replay reproduced it exactly).
- **line 70** (usage tip inside the TAG-empty gate): its nested group swallowed the
  block's closing paren, so `pause` + `exit /b 1` escaped OUTSIDE the gate — with a
  valid tag the updater paused and exited before ever reaching the download
  (echo-ON trace proved it). Historically one download per release means the parens
  landed after that era.
- **lines 58, 81, 91** (backup-mismatch / download-failed / extract-failed echoes):
  same landmine in paths that trigger on a bad day only.
- All five rewritten without parens (message wording kept). Same line-25 clone in
  `reset-pin.bat` fixed identically.
- Second defect closed: `UPDATE_REPO` now resolves process env → `.env` → baked real
  repo (`mayuuuxr/InventoryManagement`); the `__YOUR_GITHUB_REPO__` placeholder is gone.
- Probe results after fix: busy-gate clean, usage gate clean, and a full sandbox walk
  with tag v1.2.0 — backup verified, correct GitHub URL, download + extract + copy OK,
  then (sandbox-only) pip/migrate fail exactly as expected without a real runtime.

Real end-to-end verification of the fixed bat happens on the installed shop copy
when it self-updates to v1.2.1 (change-log 2026-10-18 v1.2.1 entry). The in-app
`core/selfupdate.py` Install path remains UNEXERCISED (WATCH).

## 2026-10-17 | 1.1.5 | 3793daf | FIXED | Legacy DB blocked by soft-deleted site row

`get_default_site()` used to return None whenever `Site.objects.count() != 1`, and this
handover DB holds "Shop" (active, ~95.5k inward / 70.5k outward entries) plus one
soft-deleted legacy row → every quick/bill screen redirected to Sites on the live data.
FIXED in `sites/models.py`: only non-deleted sites count (covered by
`sites/tests.py::GetDefaultSiteTests`). Bill screens now resolve "Shop" on the live DB.

## 2026-10-17 | 1.1.5 | 3793daf | FIXED | Logout never wiped the offline page cache

`base.html` logout handler purged cache name `nibba-shell-v1`, but the service worker
builds its shell cache as `nibba-shell-v2` (renamed in the brand sweep). So a shared-PC
logout could offline-serve the previous user's pages from v2. Renamed the purge to v2.
(Watch: keep the two names in sync if the SW cache version ever bumps.)

---

## 2026-10-17 | 1.1.5 | 3793daf | WATCH | Legacy DB still has multiple sites → `get_default_site()` returns None

`db.sqlite3` contains site rows: pk=12 **"Shop"** (formerly the old site name; Devada;
~95.5k inward / 70.5k outward entries attached) and pk=15 "park-2" (soft-deleted).
`sites/models.py::get_default_site()` returns `None` whenever `Site.objects.count() != 1`,
so the single-shop quick/bill screens redirect with "more than one site exists".
This is the legacy multi-site handover DB, not a fresh install — behavior is by design,
but worth remembering: this particular shop-PC DB never became "one site" shape.
Owner decision required if bill screens should work on it (merge/purge the extra site, or
make the default-site resolution smarter). Logged during the brand sweep.
**Superseded 2026-10-17 (same day): FIXED above — soft-deleted rows are now ignored.**

---

## 2026-10-17 | 1.1.5 | 3793daf | FIXED | Old brand string persisted in DB + backups (source was clean, data wasn't)

- Live `db.sqlite3`: site name + 8 audit-summary snapshots — scrubbed + VACUUMed (see change-log).
- 13 snapshot files deleted (11 rotating backups, 2 handover dbs) — owner-approved.
- Stale `.pyc` bytecode caches deleted.
- Final scan: 0 mentions anywhere in the project directory.
