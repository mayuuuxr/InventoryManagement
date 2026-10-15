# Update Model — nibba (offline app, GitHub Releases)

## For the developer (you): shipping an update
1. Make changes in `nibba/`, verify (`manage.py check` + tests), bump `VERSION` (e.g. `1.1.0`).
2. Commit + push, then `git tag v1.1.0 && git push origin v1.1.0`.
3. The `release` workflow builds `nibba-v1.1.0.zip` (code only — never DB/`.env`/`venv`/`Backup`) and attaches it to the Release with notes.
4. Never commit `.env`, `*.sqlite3`, `Backup/`, `tunnel.log` (all gitignored).

## For the client PC: applying an update (one click)
1. Owner opens Help → App updates shows the new version (needs ~2s internet; offline shows the version only).
2. Owner clicks **Install update**. Nothing else to do: the app backs up `db.sqlite3` to `Backup\pre-update_<stamp>.sqlite3` (**aborts if the backup fails or size-mismatches**), downloads the release zip, stages it, then restarts itself — stop, code-only replace (protected names skipped), `migrate`, start — in about a minute. The browser waits on an updating page and lands back on the dashboard.
3. Entries, materials, stock continue exactly as before. Help → App updates shows the new version plus the last-update result.
4. Fallback (support only): close the app, run `update.bat vX.Y.Z` — same backup-first, code-only logic by hand.

## Data guarantee
Updates replace code files only. Saved data is never overwritten, never re-imported, never "migrated away" — it stays in the same `db.sqlite3`, guarded by a verified backup taken seconds before any change.
