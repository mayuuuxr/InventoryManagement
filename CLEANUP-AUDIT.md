# Cleanup Audit — nibba PHASE 1 (audit only, zero changes)

Behaviour must remain identical; deletions only after approval. <90% confidence items flagged DO NOT DELETE.

| # | Candidate | Evidence it is unused | Risk | Action if approved |
|---|---|---|---|---|
| 1 | `Procfile` (DO App Platform) | PC build runs `run_pc.bat`+waitress; grep shows Procfile referenced only by itself | Low | Delete file |
| 2 | `requirements.txt` cloud lines (psycopg2, gunicorn, sentry) | `requirements-pc.txt` is the PC env and excludes them; `settings.py` guards sentry import with try/except | Low | Keep file but stop installing it on PC (already done); optionally delete gunicorn/sentry lines |
| 3 | Cloud DigitalOcean/Postgres docs blocks (`.env.example:29-40`, settings comments, `architecture.md`, `AGENTS.md` deploy target) | PC threat model has no DO/Postgres; code path `DATABASE_URL` never set on PC | Low | Edit comments/docs only |
| 4 | `backup_*.json`, `db_backup_*.sqlite3`, `db_pre_handover*.sqlite3` in app root | Superseded by `Backup\db_<stamp>.sqlite3` rotation + live `db.sqlite3`; check `migrate --check` passes before deleting | Medium | Move to `Backup\archive\`, keep 1 latest |
| 5 | `notifications` push stack (VAPID keys, `push/` URLs, SW banner) | PC acceptance needs no push; triggers live in `entries/views.py` but fire only with keys set. ⚠️ <90% sure nothing else imports it — `core/urls.py:39` includes it | Medium | DO NOT DELETE yet — decide: keep dormant (recommended) vs remove app + URLs + triggers |
| 6 | Cloudinary photo stack (fields, photo2 slots, orphan-sweep command) | Photos optional since PC patch; fields still in models + 41 audit tests reference them. Deleting needs a migration | High | DO NOT DELETE — keep dormant with blank creds |
| 7 | PWA shell (`core/pwa.py`, `sw.js`, manifest, icons) | Phone access is via tunnel URL, not installed PWA; SW caches only 2xx. Harmless but unused for MVP | Medium | Keep (harmless, aids phone home-screen); revisit in v2 |
| 8 | `entries/importer.py` bulk path | Only path allowed to save without photos historically; no UI calls it in PC flow (verify: grep imports) | Medium | Flagged — confirm no management command depends on it before touching |
| 9 | Commented-out code / dead Tailwind dot-tokens | Prior audit claims fixed; re-grep `TODO|FIXME|XXX|HACK` before deleting anything | Low | Delete only exact commented blocks you approve |

Largest files (split only if approved, along app lines — never split balance logic out of `entries/`): `entries/forms.py` (~670 lines), `entries/models.py` (~656 lines). No split proposed in Phase 1.
