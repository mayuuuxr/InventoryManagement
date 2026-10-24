# Architecture — nibba (PC-only shop build)

## Tech Stack
- Backend: Django (Python)
- Database: SQLite only — one `db.sqlite3` per PC (gitignored). No Postgres anywhere.
- Frontend: Django Templates + Tailwind CSS (vendored offline in `static/vendor/`: tailwind.js, lucide, Poppins — zero CDN at runtime)
- Auth: Django built-in auth + role field (admin/staff/manager) + django-axes lockout (5 fails / 1h per IP+username)
- Server: waitress on `127.0.0.1:8000` ONLY (never 0.0.0.0), launched hidden by `nibba-Shop.bat`; Chrome/Edge `--app` mode for the shop window. No LAN, no tunnel — no other device can reach it, by design.
- Updates: code-only zips from GitHub Releases via `update.bat` (`core/update.py`, `VERSION` file); `db.sqlite3`, `Backup/`, `Logs/`, `Data/` are never overwritten
- Dependencies: `requirements-pc.txt` ONLY (Django, axes, Pillow, openpyxl, reportlab, whitenoise, waitress). No Cloudinary, no push, no Sentry, no Postgres, no DRF.
- Version Control: Git + GitHub (git init at handover; `.env`, `db.sqlite3`, `Backup/`, `Logs/`, `Data/`, `build/`, `venv/` gitignored)

## App Structure
- `accounts` — custom User (admin/staff/manager roles), login, staff CRUD, PIN reset
- `sites` — Site model; migration `0003_ensure_shop_site` auto-creates the single `Shop` row (no site picker in UI)
- `materials` — Category > SubCategory > Material catalog, units, reorder points
- `entries` — Purchase (Inward), Sale (Outward), Transfer + SubLocation/Allocation + AuditLog + balance logic + Orders history + quick purchase/sale forms
- `reports` — site-wise/material-wise/monthly reports (views only, no models; screen + xlsx + pdf)
- `core` — settings, root URLs, dashboard, help/privacy/terms pages, low-stock context, PWA shell (`sw.js` caches app shell only — NO push handlers), offline updater
- Deleted on purpose: `notifications` app, all photo models, Cloudinary, VAPID. Never re-add; see `CLEANUP-AUDIT.md`.

## Data Models (as implemented — verified against code)

**Site** (`sites/models.py`)
- name, location, created_at
- + `CatalogAuditMixin`: created_by (FK User), is_deleted, deleted_by, deleted_at (soft-delete, restorable via admin action)
- Single row `Shop` auto-created on fresh databases; UI has no picker.

**Category / SubCategory / Material** (`materials/models.py`)
- Category: name (unique where not deleted)
- SubCategory: category (FK PROTECT), name (unique per category where not deleted)
- Material: category (FK PROTECT), sub_category (FK PROTECT, nullable), name (variant, e.g. `8mm`), unit, reorder_point (default 10), hsn_code (optional, prints on bills), gst_rate (optional %, invoices; NULL = no GST on bills), created_at
- `display_name`: `Steel > 8mm`, or plain `Cement` when no sub-category

**InwardEntry = Purchase** (`entries/models.py`)
- site (FK), material (FK), date, time (default noon), qty (Decimal, whole numbers only), received_from (supplier), rate (nullable ₹ snapshot at entry time — required on the quick purchase form, optional on ledger edits), created_by (FK User), created_at. NO photo field.
- Unique: (site, material, date, time)

**OutwardEntry = Sale** (`entries/models.py`)
- site (FK), material (FK), date, time, qty (whole numbers only), customer (buyer name), rate (nullable ₹ snapshot at sale time — required on the quick sale/bill forms, optional on ledger edits), inward_entry (FK PROTECT, nullable — FIFO: which purchase this sale consumes), sub_location (FK PROTECT, nullable), created_by (FK User), created_at. NO photo field.
- NOTE: `supplied_to` / `place_of_supply` were removed (migration 0004). Multiple entries per date allowed (told apart by time), no DB uniqueness.

**TransferEntry** (`entries/models.py`)
- material (FK), date, time, qty, from_site (FK), to_site (FK), created_at
- No created_by, no app UI — admin/shell only, reserved for future. Site-to-site only.

**SubLocation / SubLocationAllocation** (`entries/models.py`)
- SubLocation: site (FK), name, description, unique (site, name)
- SubLocationAllocation: inward_entry (FK PROTECT), sub_location (FK CASCADE), qty_allocated, unique (inward, sub_location)
- Sale form resolves/auto-creates SubLocation case-insensitively from free text.

**AuditLog** (`entries/models.py`)
- user, action (create/edit/delete/login/export), entry_type, entry_id, entry_summary, timestamp

**Bill printing (A4 tax invoice — `entries/views.py`)** — after a bill saves, POST returns a redirect to
`entries:{sale,purchase}_bill_print?ids=…`; `_bill_print_context()` renders `entries/invoice_print.html`
(the 80mm thermal `bill_print.html` is retired). Doc label: TAX INVOICE (sale) / PURCHASE BILL (purchase).
Every printed number derives at print time from `entries/utils.py: bill_invoice_totals()` — per-line
`qty × saved rate`, each material's `gst_rate` grouped and split CGST/SGST (two equal halves, odd paisa
pushed into SGST), round-off half-up to the rupee, hand-rolled amount-in-words. Totals are never stored,
so a corrected ledger row always re-prints true; legacy rows without a rate print "-" and honestly add
0.00. Shop identity comes from env `BILL_SHOP_NAME`, `BILL_SHOP_TAGLINE`, `BILL_SHOP_ADDRESS`,
`BILL_SHOP_PHONE`, `BILL_SHOP_EMAIL`, `BILL_SHOP_GSTIN`, `BILL_SHOP_PAN`.

**Balance (calculated, never stored — `entries/utils.py`)**
- `balance_for(site, material)`; `balances_for_site()` bulk; `balance_for_sub_location()` = allocated-here − used-here, falls back to site balance when zero allocations
- `LOW_STOCK_THRESHOLD = 10` (per-material `reorder_point` overrides); dashboard low/out-of-stock tabs via `low_stock_items()`

**User** (`accounts/models.py`)
- Custom AbstractUser + role (admin/staff/manager, default staff)
- Single shop: no staff↔site assignment model. Staff see everything (reads global); edit/delete is own-entries-only.

## Balance Calculation Logic
Balance = SUM(Inward.qty) - SUM(Outward.qty) - SUM(Transfer.qty where from_site) + SUM(Transfer.qty where to_site)

Per material (one shop). Negative balance is BLOCKED in app forms (`entries/forms.py`: `qty > available → error`) and re-checked under row locks in `transaction.atomic` on save (`lock_stock_rows`). Qty must be whole numbers (decimals rejected in forms + model `clean()`).

## Deployment (shop PC)
- First run: `INSTALL.bat` → venv + `requirements-pc.txt` + `migrate` (auto-creates `Shop` + `owner/1234`) + `collectstatic`.
- Daily: `nibba-Shop.bat` → backup (`Backup/db_*.sqlite3`, keeps 30) → migrate → `export_monthly_files` (`Data/YYYY-MM/sales.xlsx` + `purchases.xlsx`) → hidden waitress → app-mode browser.
- Close: `nibba-Close.bat`. Update: `update.bat vX.Y.Z` (backup-verified, code-only).
- Kits: `BUILD-PORTABLE.bat` (zip) and `BUILD-INSTALLER.bat` (`nibba.iss` → `nibba-Shop-Setup-<ver>.exe`).
- Environment via `.env` (gitignored, auto-created): `DJANGO_SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=localhost,127.0.0.1`, optional `UPDATE_REPO`/`UPDATE_TOKEN`. See `.env.example`.

## Removed Systems (do NOT reintroduce)
- **Push notifications:** the `notifications` app, VAPID keys, `/push/*` URLs, the base.html opt-in banner, and the `sw.js` push handlers are all deleted. `sw.js` caches the app shell (2xx only) and shows the offline banner — nothing more.
- **Photos:** `InwardEntryPhoto`/`OutwardEntryPhoto` models and all photo fields deleted (migration `0025`). Old migrations use plain `CharField` so fresh installs need zero third-party packages.
- **Cloud:** no Postgres, no gunicorn, no Sentry, no DigitalOcean. The old cloud `requirements.txt` is legacy reference only — PC builds install `requirements-pc.txt`.
