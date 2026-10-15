# Skill — PC-Only Django Conversion (reusable)

## 1. Name
pc-only-django-conversion

## 2. Description
Use when the user says: "run this Django app only on my PC", "no server / data on my PC", "PC only, no phones", "make photo optional", "lean PC build". Do NOT use for cloud deploys, phone/LAN access, multi-branch sync, or offline-first PWA work.

## 3. Instructions
1. Freeze scope first: users (owner + staff on the same PC), MVP (Purchase/Sale/Balance/Reports?), photos (yes/no?), done-test (entry saved → balance updates on screen?).
2. Copy the project to a NEW folder (never edit the original); exclude `venv/`, `__pycache__/`, `.git/`, `staticfiles/`. Verify original `git status` clean.
3. Remove photo models/fields via migration (old migrations must not import third-party fields); remove push/notification stack; prove fresh `migrate` with those packages absent.
4. Add `requirements-pc.txt` (Django, axes, dotenv, Pillow, openpyxl, reportlab, whitenoise, waitress — nothing else). Create venv, install, run `migrate --check`.
5. Add shop launcher: backup `db.sqlite3` → `Backup\db_<stamp>.sqlite3` (keep 30), serve `waitress --listen=127.0.0.1:8000` ONLY (never 0.0.0.0), open app-mode browser.
6. Write PRD-PC.md (10 sections) then DESIGN-PC.md (frozen tokens).
7. Security audit report only (ranked, with file:line + exploit + fix). Never edit code in this step.
8. E2E: list J1/J2/J3 journeys, add Playwright config + auth fixture + seed/cleanup + CI. No phone/tunnel journeys exist.
9. Cleanup audit table with risk levels; delete nothing under 90% confidence without approval.
10. Commit plan with Conventional Commits; verify `check` passes each step.
11. Lockdown check: no `0.0.0.0` listener, no tunnel helper, `ALLOWED_HOSTS` localhost-only, strong `SECRET_KEY` + `DEBUG=False` + secret admin path on the shop PC.

## 4. Rules and constraints
- Original folder stays untouched (verify `git status` clean before and after).
- No code changes during security/cleanup audits.
- Balance logic never rewritten, only reused.
- Browser localStorage is never the master DB (SQLite file is).
- Must never share real secrets (rotate if a `.env` was copied).

## 5. Output format
End with: files created/changed (paths), verification commands run + result, original-clean proof, next single action for the user.

## 6. Worked example
Input: "PC only, data on PC, no photos, same UI." Output: `nibba/` copy, photo-removal migration, `requirements-pc.txt` + shop launcher + `Backup/`, PRD-PC/DESIGN-PC, SECURITY-AUDIT, e2e J1–J3, cleanup table, commit plan, kit boots fresh with login 200.

## 7. Failure modes
- Editing the original instead of the copy → always copy first + `git status` both folders.
- Old migrations importing removed third-party fields → fresh installs break; swap to plain fields, prove with import-blocked `migrate`.
- Multi-line `{# #}` template comments → Django renders them as text; comments must stay single-line.
- Page does not open → server stopped; reopen shop launcher, wait, retry. No network involved by design.
