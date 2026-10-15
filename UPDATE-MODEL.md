# Update Model — nibba (offline app, GitHub Releases)

## For the developer (you): shipping an update
1. Make changes in `nibba/`, verify (`manage.py check` + tests), bump `VERSION` (e.g. `1.1.0`).
2. Commit + push, then `git tag v1.1.0 && git push origin v1.1.0`.
3. The `release` workflow builds `nibba-v1.1.0.zip` (code only — never DB/`.env`/`venv`/`Backup`) and attaches it to the Release with notes.
4. Never commit `.env`, `*.sqlite3`, `Backup/`, `tunnel.log` (all gitignored).

## For the client PC: applying an update
1. Owner opens Help → App updates shows the new version (needs ~2s internet; offline shows the version only).
2. Run the nibba Close icon (server must be stopped), then `update.bat v1.1.0`.
3. The script: verifies port 8000 free → copies `db.sqlite3` to `Backup\pre-update_<stamp>.sqlite3` and **aborts if the backup fails or size-mismatches** → downloads the release zip → copies code only (protected names skipped) → runs `migrate` (additive) → prints the new version.
4. Start with `run_all.bat`. Entries, materials, sites continue exactly as before.

## Data guarantee
Updates replace code files only. Saved data is never overwritten, never re-imported, never "migrated away" — it stays in the same `db.sqlite3`, guarded by a verified backup taken seconds before any change.
