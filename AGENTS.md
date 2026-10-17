# AGENTS.md

## 1. Project Overview

PC-only **Purchase-Sale** stock app for a single retail shop (`nibba`) that sells **paint and other household hardware materials**. Replaces manual registers/Excel for tracking what was bought from suppliers and sold to customers, with live balance visibility. One PC holds the truth (`db.sqlite3`); the server listens on 127.0.0.1 only — no phones, no LAN, no tunnel, no cloud.

- **Business context:** A single shop. Stock arrives as **Purchases** (from a supplier, `received_from`) and leaves as **Sales** (to a customer, `customer`). No photo proof, no server cost, no cloud of any kind.
- **No price fields — by design:** the shop writes prices by hand. Bills print on an **80mm thermal roll printer** with Rate/Amount/Total cells intentionally BLANK (filled manually on paper). Entry models store NO price. After saving a bill the app opens the printable page (`entries/{sale,purchase}/bill/print/?ids=…`, template `entries/templates/entries/bill_print.html`) which auto-triggers the browser print dialog. Printed header: `BILL_SHOP_NAME` (default `nibba`) + optional `BILL_SHOP_TAGLINE` via `.env` — change the printed header without code edits.
- **No sites concept in the product:** the shop experience is paste one shop, one catalog, no site picker anywhere. The `sites` app still exists at the code level (single `Shop` row; `get_default_site()` ignores soft-deleted rows) but must never surface as UI wording.
- **Users:** Owner/admin (full access) and Staff (purchase/sale entry; reads are global, edit/delete own entries only).
- **Full details:** Read `prd.md` (product requirements) and `architecture.md` (tech architecture) before making changes. `PRD-PC.md` / `DESIGN-PC.md` cover the PC deployment and the Ocean Breeze theme. Session logs live in `useme/` (change-log, bug-log, test-reports) — update them every session and record the git HEAD hash.

## 2. Current Status

Single-shop build is complete and production-hardened. Do NOT reintroduce removed systems (photo uploads, Cloudinary, push notifications, Postgres, Sentry, DRF, the `notifications` app) — they were deleted on purpose; see `CLEANUP-AUDIT.md`.

- **Apps:** `accounts`, `core`, `entries`, `materials`, `reports`, `sites`
- **Models:** `User` (admin/staff/manager), `Site` (one auto-created `Shop` row), `Category`, `SubCategory`, `Material`, `InwardEntry` (a purchase, `received_from`, NO photo), `OutwardEntry` (a sale, `customer` + `inward_entry` FIFO link + free-text `sub_location`, NO photo), `TransferEntry` (admin-only, no app UI), `SubLocation`, `SubLocationAllocation`, `AuditLog`
- **Balance:** calculated, never stored (`entries/utils.py: balance_for`) — `Inward − Outward − Transfer(out) + Transfer(in)`, per site per material; negative blocked in forms; qty whole numbers only
- **Safeguards:** outward/sale saves re-check balance under row locks in `transaction.atomic` (race-proof); allocations cannot exceed delivery; sub-location names unique case-insensitively per site; login lockout 5-fails/1h per (IP, username) via django-axes; soft-deleted catalog rows restorable via admin action; DEBUG fail-closed (default False); Excel formula-injection guard; `?repeat=` reads the latest row in this site+material
- **Tests:** `manage.py test` — 139 tests green (`accounts/tests.py`, `core/tests.py`, `entries/tests.py`, `entries/tests_audit.py`, `materials/tests.py`, `reports/tests.py`, `sites/tests.py`). No network, no third-party services in tests.
- **Database:** SQLite only (`db.sqlite3`, gitignored). No Postgres anywhere.
- **Tech stack:** Django + Django Templates + Tailwind CSS (vendored offline in `static/vendor/`), served by waitress on the shop PC. Zero monthly cost.

## 3. Shop Rules (must be preserved)

### Single Shop — no site picker
- `sites/migrations/0003_ensure_shop_site.py` auto-creates the `Shop` site on fresh databases. The UI has no site picker; new installs just work.
- Do NOT add multi-site UI. `TransferEntry` stays admin-only.

### Purchase / Sale wording
- Inward = Purchase (`entries/purchase_add/`, `received_from` = supplier). Outward = Sale (`entries/sale_add/`, `customer` = buyer, FIFO `inward_entry` link). Keep this wording in UI and code comments.

### No photos, no push, no cloud — ever
- Entry models have NO photo fields (removed via migration `0025`; old migrations use plain `CharField` so fresh installs need zero third-party packages).
- No `notifications` app, no VAPID, no `sw.js` push handlers, no Cloudinary, no Sentry, no Postgres, no DRF. `requirements-pc.txt` is the ONLY install file.

## 4. Rules for Agents

Before making any changes:
1. **Read** this `AGENTS.md`, then `prd.md`, then `architecture.md` — every time.
2. Check existing models and code in the relevant app folder before adding/modifying anything.
3. The original cloud project in the sibling folder (`../construction-inventory/`) is READ-ONLY reference — never edit it; its `git status` must stay clean.

When writing code:
- **Keep it simple.** No premature abstraction. No microservices. No unnecessary packages. No new dependencies without owner approval (every dep ships on the shop PC).
- **Django ORM only** for database access. No raw SQL unless absolutely necessary (and document why).
- **Comment business-critical logic**, especially balance calculation. Future agents and humans must understand the formula at a glance.
- Follow existing patterns in the codebase (model style, view style, template style).
- Theme tokens live in `DESIGN-PC.md` (Ocean Breeze). No pills, no gradients, no emojis in UI.

When adding a migration, prove a fresh install still works:
1. `manage.py makemigrations --check --dry-run` → no changes.
2. `manage.py test` → all green.

## 5. Open Questions (resolved unless noted)

- Units for steel, plumbing, and other materials (client to confirm) — PENDING
- Negative balance allowed or blocked — DECIDED: blocked in app forms (`qty > available → error`)
- Low-stock alerts — IMPLEMENTED (`reorder_point` per material + `LOW_STOCK_THRESHOLD=10` fallback, dashboard low/out-of-stock tabs); thresholds to confirm with client
