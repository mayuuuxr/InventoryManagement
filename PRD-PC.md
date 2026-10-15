# PRD — nibba (PC-only Shop Inventory)

## 1. Problem statement
A single retail shop (paints, hardware, interior, household) tracks stock in registers/Excel. The owner wants: one PC holds the truth, purchase/sale entry on the same PC, zero monthly server cost, zero photo overhead, and instant balance visibility. No phones, no network, no cloud — the app listens on 127.0.0.1 only.

## 2. Target users
- Primary: Owner on the shop PC (full access: materials, entries, reports, staff logins, backup, updates).
- Secondary: Shop staff on the SAME PC (entry only: Purchase + Sale). Separate logins so edit/delete stays own-only; everyone sees true balances.

## 3. Goals and non-goals
Goals: (a) purchase saved → balance updates instantly on screen; (b) single-user-simple operation: double-click the nibba Shop icon to run; (c) minimal UI in the same spirit as the manual register (no photos); (d) add materials without developer help; (e) automatic backup of one SQLite file every launch.
Non-goals: no photo proof, no phones, no LAN/tunnel access, no cloud hosting, no multi-shop sync, no GPS/QR, no accounting/GST, no Transfer UI in v1 (admin-only if needed).

## 4. User stories
- As owner I want to add a Category > SubCategory > Material with unit + reorder point so that purchase/sale forms can select it immediately.
- As staff I want to record a Purchase (date, time, qty whole numbers, supplier) so that shop stock rises without paperwork.
- As staff I want to record a Sale linked to a purchase delivery + customer + sub-location so that consumption is traceable per delivery.
- As owner I want Balance = Inward − Outward − Transfer(out) + Transfer(in), per material, never stored, so that I always see true stock.
- As owner I want site-wise summary + material consumption + monthly reports (screen + xlsx + pdf) so that I can share/tally without Excel rework.
- As owner I want low/out-of-stock tabs (reorder_point, fallback 10) so that I reorder before shortage.
- As owner I want one-file backup (`db.sqlite3` → `Backup\db_<stamp>.sqlite3`, keep 30) so that a disk crash costs at most 1 day.
- As owner I want monthly `Data/YYYY-MM/sales.xlsx` + `purchases.xlsx` regenerated every launch so that I can work the numbers directly in Excel.

## 5. Feature list (shipped / later)
Shipped: auth (owner + staff PIN logins, axes lockout); single auto-created `Shop` (no site picker); Category/SubCategory/Material CRUD with units; Purchase quick form (no photo); Sale quick form linked to purchase FIFO + customer + free-text sub-location auto-create (no photo); Orders history; live Balance; site/material/monthly reports (screen+xlsx+pdf); low/out-of-stock dashboard tabs; `nibba-Shop.bat` (backup → migrate → waitress → app-mode browser); `nibba-Close.bat`; `INSTALL.bat`; `update.bat` (code-only updates from GitHub Releases); portable zip + installer kits.
Later: Transfer app UI, Excel bulk import, second-PC replica (only if the shop outgrows one PC).

## 6. Functional requirements
- Auth: Django auth; PIN min 4 chars; axes 5 fails → 1h lockout per (IP, username); session 8h, expire on browser close. Owner can create/reset staff PINs.
- Single shop: `Shop` auto-created on fresh databases (migration `0003_ensure_shop_site`); no picker anywhere.
- Materials: Category.name unique; SubCategory unique per category; Material = category + variant name + unit (bags/ft/pieces) + reorder_point default 10. `display_name`: `Steel > 8mm` or plain `Cement`.
- Purchase: fields date, time (default 12:00), qty whole > 0, received_from (supplier), material. Duplicate rule: same material+date+time blocked with friendly error. No photo exists.
- Sale: fields date, time, qty whole > 0, customer (buyer), inward_entry (required, only deliveries with remaining balance, FIFO oldest first), sub_location (required free text). Guards: qty ≤ available (blocked with error); re-checked under `transaction.atomic` row locks at save (race-proof).
- Balance: calculated only (`entries/utils.py: balance_for`); sub-location = allocated−used, falls back to shop balance when zero allocations. Negative blocked in forms.
- Reports: shop summary, material consumption with sub-location split, monthly activity — each screen + .xlsx + .pdf. Excel formula-injection guard (`_x` prefix).
- Serving: waitress listens on `127.0.0.1:8000` only. `ALLOWED_HOSTS` stays localhost. No LAN, no tunnel, no HTTPS.
- Backup: every `nibba-Shop.bat` launch copies `db.sqlite3` to `Backup\` with timestamp; keeps newest 30. Monthly Excel files regenerated into `Data\`.

## 7. Data model sketch
- User(id, username, role[admin/staff/manager], pin_hash)
- Site(id, name, location) — one row: `Shop`
- Category(id, name); SubCategory(id, category FK, name); Material(id, category FK, sub_category FK nullable, name/variant, unit, reorder_point default 10)
- SubLocation(id, site FK, name, description; unique site+Lower(name))
- InwardEntry = Purchase(id, site FK PROTECT, material FK PROTECT, date, time, qty decimal whole, received_from, created_by FK, created_at)
- OutwardEntry = Sale(id, site FK, material FK, date, time, qty, customer, inward_entry FK PROTECT nullable, sub_location FK PROTECT nullable, created_by FK, created_at)
- TransferEntry(id, material FK, date, time, qty, from_site FK, to_site FK) — admin-only in v1
- SubLocationAllocation(id, inward_entry FK PROTECT, sub_location FK CASCADE, qty_allocated; unique inward+sublocation)
- AuditLog(id, user, action[create/edit/delete/login/export], entry_type, entry_id, entry_summary, timestamp)

## 8. Edge cases and failure states
- PC restarts (Windows Update) → waitress not running. Mitigation: open the nibba Shop icon again; smoke URL `http://localhost:8000/accounts/login/`.
- Two staff spend the same delivery simultaneously → second save blocked by atomic balance re-check (shows available error, no negative stock).
- Duplicate tap (double submit) → same datetime unique constraint returns friendly time-differ error, no double row.
- Power cut mid-write → SQLite atomic transaction; backup from last start intact.
- Browser cache clear → nothing lost (server is truth; monthly Excel files regenerate on next launch).
- Page does not open → run the nibba Close icon, wait 10s, reopen nibba Shop. Still stuck → read `Logs\nibba.log`, call support.

## 9. Success metrics
- Acceptance: purchase saved → visible in balance instantly on the same PC.
- Entry time: purchase or sale completable in ≤30s.
- Backup exists for every run day (Backup\ count = run days).
- 30 days without a negative-balance incident or duplicate-datetime row.

## 10. Open questions
- [FLAG] Transfer UI in v1? Current decision: NO (admin-only). Confirm owner never moves stock shop-to-shop in daily work.
- [FLAG] Staff PIN policy: 4-digit shared vs per-person? Current: per-person PIN, axes lockout on.
- [FLAG] Units for steel/plumbing variants (kg/pieces/length?) — client to confirm list before material seeding.
