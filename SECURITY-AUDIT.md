# Security Audit — nibba PC build (report only, no code changed)

> **Addendum Oct 15 2026 (PC-only decision):** phones and the tunnel are
> removed — `run_all.bat`/`tunnel_env.py` deleted, waitress listens on
> `127.0.0.1:8000` only, `ALLOWED_HOSTS` is localhost-only. Threat model
> is now: one shop PC, local users only, no network attacker. Status of
> old findings: CRITICAL-1 FIXED (Cloudinary secret deleted from `.env`);
> HIGH-1/HIGH-2 CLOSED (no tunnel → no remote exposure; `/admin/` only
> reachable from this PC); MEDIUM-2 downgraded (only local logins can
> hit endpoints). The findings below are kept as history.

Scope: `C:\Users\mayuuuxr\Downloads\nibba` app code only (venv excluded).
Threat model (original): 1 owner PC + 2–3 phone users over Cloudflare tunnel. Data must stay on PC.

## Ranked findings

### CRITICAL-1 — Real Cloudinary API secret copied into nibba/.env
- File/line: `nibba/.env:10-11` (`[REDACTED]`, `[REDACTED]`)
- Status 2026-10-22: credential values redacted in this file; the original pair remains in git history - rotate/revoke the key pair in the Cloudinary dashboard (owner action).
- Exploit: anyone who receives this folder (pen drive, zip, screenshot) can manage/delete your Cloudinary assets and burn quota. Secret was copied verbatim from the original project.
- Fix: rotate the key pair in Cloudinary dashboard NOW; delete both lines from `nibba/.env` (photos are optional in PC build — blank is fine); never copy `.env` between projects; confirm `.gitignore` covers `.env` before any `git init`.

### HIGH-1 — Tunnel exposes app while DEBUG=True + placeholder SECRET_KEY
- File/line: `nibba/.env:3-5` (`DJANGO_SECRET_KEY=change-me-...`, `DEBUG=True`, `ALLOWED_HOSTS=localhost,127.0.0.1`); `core/settings.py:50-66,354-364`
- Exploit: once cloudflared maps `localhost:8000` to a public URL, DEBUG tracebacks disclose paths/settings, and a weak/guessable SECRET_KEY lets an attacker forge sessions if the app ever runs with DEBUG=False on that key. Current `.env` also lacks the tunnel host in ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS, so saves will 400/403 — staff will then be tempted to set `ALLOWED_HOSTS=*`.
- Fix: before sharing any tunnel URL: generate a strong key (`venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`), set `DEBUG=False`, set `ALLOWED_HOSTS=localhost,127.0.0.1,<tunnel-host>`, `CSRF_TRUSTED_ORIGINS=https://<tunnel-host>`, restart waitress. Fail-fast in settings already refuses to boot DEBUG=False on the insecure key — keep it.

### HIGH-2 — Admin login at guessable `/admin/` while internet-exposed
- File/line: `core/settings.py:72-73` default `admin/`; `nibba/.env` sets no `DJANGO_ADMIN_PATH`; `core/urls.py:28`
- Exploit: bots scan `/admin/` on every tunnel domain; axes slows them (5 tries → 1h per IP+username) but the endpoint stays discoverable.
- Fix: set `DJANGO_ADMIN_PATH=manage-<random>/` in `nibba/.env` before exposing; staff keep using `/accounts/login/`.

### MEDIUM-1 — Backup + live DB files live inside the app directory
- File/line: `nibba/db.sqlite3`, `nibba/db_*.sqlite3`, `nibba/Backup\` (new), `nibba/backup_*.json`
- Exploit: Django itself never serves these paths (only static/media URLs exist), so direct URL fetch 404s — but one misconfigured static route or an accidental `Backup` download share would hand over the full database.
- Fix: keep `Backup\` outside the Django project dir (e.g. `C:\nibba-backups\`), or at minimum never add a URL/static mapping for it; verify no directory listing is enabled.

### MEDIUM-2 — No throttling on entry-create and report-export endpoints
- File/line: `entries/views.py` (Inward/Outward create), `reports/views.py:585+` exports; only `notifications/views.py:74,119` has per-user throttle keys; login has axes (`core/settings.py:90-102`)
- Exploit: any logged-in phone can spam creates/exports (disk fill, CPU on PDF/xlsx). Low risk with 3 trusted users, but no backstop exists.
- Fix (v2): add per-user rate limit on POST exports + creates; for v1 accept risk + rely on axes + trusted users. Do NOT remove axes.

### LOW-1 — Throwaway VAPID private key lives in nibba/.env
- File/line: `nibba/.env:14-15`
- Exploit: push is dormant (blank-or-test keys = off), but if push is ever enabled with this committed test key, attacker could craft pushes.
- Fix: leave push OFF (blank keys) in PC build; if push is ever needed, generate a fresh pair per deployment and never commit it.

### LOW-2 — One-time on-screen PIN is shoulder-surfable
- File/line: per AGENTS.md design (PIN shown on screen once)
- Exploit: someone behind the owner reads the new staff PIN.
- Fix: accept (documented trade-off, avoids plaintext credential files); reset PIN if exposed.

## Explicitly clean (with evidence)
- SQL/NoSQL/command injection: clean — Django ORM only; no `raw()`, `extra()`, `RawSQL`, `os.system`, `subprocess` in app code (only inside venv/cffi).
- XSS: clean — Django autoescape; `mark_safe` appears only inside vendored `cloudinary` lib, not app templates.
- CSRF: clean — `CsrfViewMiddleware` present (`core/settings.py:157`), never removed; tunnel requires CSRF_TRUSTED_ORIGINS entry (operational, not a code gap).
- CORS: clean — no `django-cors-headers`, no `Access-Control-Allow-Origin: *` in app code (only axes' optional CORS setting, unused).
- AuthN sessions: clean — `LoginRequiredMixin`/`login_required` on all app views (accounts/sites/materials/reports/notifications/entries), 8h sessions, expire on browser close.
- AuthZ object-level: by design — reads global, edit/delete own-only via EntryWriter mixin + `created_by` stamping; reports export login-gated for any logged-in user (accepted for 3 trusted users; flag if staff set grows).
- File upload: acceptable — photos optional in nibba; when supplied, extension + 20MB cap + Pillow `verify()` + format allowlist (`entries/forms.py:check_photo_file`); Cloudinary transforms dormant with blank creds.
- Secrets in code: clean apart from CRITICAL-1 — no other hardcoded keys in app `.py`/templates (matches were venv + settings `os.environ.get` patterns).
- Security headers/cookies: clean WHEN DEBUG=False — `SECURE_SSL_REDIRECT/HSTS/SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE` all set (`core/settings.py:354-364`) + `SECURE_PROXY_SSL_HEADER` for tunnel; insecure only while DEBUG=True (see HIGH-1).
- Dependencies: no known-vuln assertion possible offline — run `venv\Scripts\pip audit` before go-live; removed gunicorn/psycopg2/sentry reduce surface (good).
- Logs/errors: clean — console logging only, `send_default_pii=False`, PINs never emailed (console backend dev only).

## Do NOT fix yet
Per template: no code modified in this audit. Approve items (suggested order: CRITICAL-1 key rotation + .env cleanup, HIGH-1 tunnel env, HIGH-2 admin path) and I will implement in nibba only.

## Addendum (Oct 12, 2026): 7-prompt audit pack re-run
1. Leaked secrets: `nibba/.env` STILL holds the copied Cloudinary key/secret + test VAPID private key (CRITICAL-1 open). Frontend clean: only `csrf_token` usages, no keys/tokens in templates or JS.
2. Input sanitization: clean. Zero raw SQL / `.extra()` / `eval` / `innerHTML` / `mark_safe` in app code; ORM-only queries; template autoescape; Excel `_x` formula guard; Pillow verify kept + tested.
3. Rate limiting: no AI or billable endpoints exist (nothing to scrape for billing abuse). Login has axes 5-fail/1h lockout. Entry/export POSTs unthrottled: accepted for 3 trusted offline users.
4. Auth architecture: Django built-in auth + PBKDF2 hashing + axes. NOT custom crypto. Do NOT migrate to Supabase/Clerk/Firebase: cloud auth would break the offline requirement. Keep as is.
5. API versioning: N/A. Zero API endpoints (templates only, DRF removed). Nothing to version.
6. File uploads: photo entry removed from UI and admin fieldsets; only dormant model columns remain (blank). `check_photo_file` retained and unit-tested. No executable upload path.
7. Dependencies (`requirements-pc.txt`, all pinned): Django/axes/Pillow/openpyxl/reportlab/whitenoise current; cloudinary + pywebpush installed dormant (models import them); gunicorn/psycopg2/sentry already removed. Run `pip audit` once before handover.
