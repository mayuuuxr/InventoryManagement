# Bug Log (newest first)

Format per entry: `date | VERSION | git HEAD | status (OPEN / FIXED / WATCH) | detail`

The old brand string (removed 2026-10-17) is never spelled in these logs —
referred to as "the old brand string".

---

## 2026-10-18 | 1.2.0 | 623306c | OPEN | update.bat is parse-broken ("…was unexpected at this time.")

Discovered while updating the shop PC's installed copy to v1.2.0. `cmd /c update.bat`
exits 255 immediately — even with NO arguments — dying at batch parse before the file
prints its own usage text ("Usage: update.bat v1.1.0"). Same bytes in the repo and in
the installed copy (`git diff v1.1.5 v1.2.0 -- update.bat` is empty; deploy was made
from the same tree). Suspect: the fragile multi-caret `powershell -Command ^` block
(lines ~95-104); not yet root-caused line-precisely.

Second latent defect in the same file: `UPDATE_REPO` is read from the shell ENV only —
the batch never parses `.env` — and the built-in fallback is the placeholder
`__YOUR_GITHUB_REPO__` (confirmed at v1.2.0). A shop owner running the documented
`update.bat v1.2.0` flow would try to download from a bogus URL. It fails safe
(update aborts before any code change; db backup already taken), but the documented
path is dead until fixed.

**Fix plan:** rewrite the brittle construct in the repo's `update.bat`, bake/parse the
real repo name (`mayuuuxr/InventoryManagement`) instead of the placeholder, then ship
in the next tagged release and exercise the fix through the app's own Install button
(that also tests the in-app `core/selfupdate.py` path end-to-end, still unexercised).
Workaround used tonight: the bat's algorithm executed by hand — script
`%TEMP%\opencode\apply_v120.ps1` + `apply_v120_finish2.ps1` (scratch tools, logged
here for rollback archaeology). Successful result: v1.2.0 live on the installed copy
(see change-log 2026-10-18 pass).

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
