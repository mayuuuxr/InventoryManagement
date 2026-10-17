# Change Log (newest first)

Format per entry: `date | VERSION | git HEAD | state of working tree | what & why`

The old brand string (removed from this repo on 2026-10-17) is never spelled
in these logs — it is referred to as "the old brand string". This keeps the
log useful while honoring the no-mentions rule.

---

## 2026-10-17 — COMMIT NOTE

The three pass entries in this file (billing WIP inherited + brand sweep +
shop-context/printing + sidebar split) ship together as **ONE commit — v1.2.0**
(owner's choice: single commit).
After the commit lands, `git log -1` is the authoritative HEAD for these entries.
Old handover snapshot DBs and rotating backups were DELETED this session (brand purge,
owner-approved) — no DB rollback anchor remains; the daily `nibba-Shop.bat` backup
rotation takes over from the next launch.

**LANDED:** commit `671f458`, tag `v1.2.0` — 26 files, +1681/−27, Sat 2026-10-17
23:48:47 IST (owner ran the commands personally). Green gate for the release:
`useme/test-reports/2026-10-17_full-suite_run3.md` (139 tests OK).

---

## 2026-10-18 — Session pass: v1.2.0 shipped to the shop PC

- **Version:** 1.2.0 · **git HEAD:** `623306c` · **Working tree:** clean at start of pass.

Half past midnight the owner asked why the shop app shows no update option. Traced the
whole path — this machine is BOTH the dev PC and the shop PC, and the two copies differ:
- The desktop "nibba Shop" icon launches the **installed copy**
  `C:\Users\mayuuuxr\AppData\Local\nibba` — NOT this repo. That copy was
  VERSION 1.1.5-era with its own small db (3,750 + 3,750 seeded demo rows, Oct 15-16).
- **No entries were created anywhere on 2026-10-17 in either DB** — the copy
  divergence is data-safe today; zero sales/purchases were lost or at risk.
- The repo's 30 MB db (95.5k inward / 70.5k outward historical dataset) is NOT what
  the daily app reads. Going forward the shop register is
  `AppData\Local\nibba\db.sqlite3` (currently seeded demo data).
- Why no update option, two stacked reasons: the sidebar Updates item is ADMIN-ONLY
  (`user.is_admin_role`), and an Install button only appears when GitHub has a release
  newer than the app's own VERSION — nothing was newer than v1.1.5 at that point.

Shipped tonight (all owner-approved):
1. **Pushed** main `3793daf..623306c` + tag `v1.2.0`; CI (release.yml run #11) published
   release v1.2.0 with `nibba-v1.2.0.zip` — 576,292 bytes, sha256
   `e85e8a188314b1a3582fbd4a8c99648e62bc9d6698c7fca8e3c401d6d7a3928a`, verified before install.
2. **Installed copy updated 1.1.5 → 1.2.0** following update.bat's algorithm by hand,
   because the bat itself is parse-broken on this PC (bug-log 2026-10-18 OPEN): port
   stopped via nibba-Close.bat → size-verified db backup
   `Backup/pre-update_2026-10-18_001332.sqlite3` → 192 code files copied (data files
   double-filtered) → migrate "No migrations to apply" → collectstatic → check clean →
   relaunched via nibba-Shop.bat (server started 00:15:05).
   requirements-pc.txt unchanged v1.1.5→v1.2.0 (git diff) → pip sync skipped = no-op.
3. **Verified live:** `/entries/purchase/bill/` and `/entries/sale/bill/print/` now 302
   → login (both 404 before the update); login page 200. The in-app updater path was
   not exercised (server was stopped at the moment of update) — next natural attempt:
   v1.2.1 via the app's own Install button.

Note: the release zip was built from tag-commit `671f458`; the follow-up
`623306c` (test-report + this pass's docs) is not in the installed copy — docs-only.

---

## 2026-10-17 — Session pass #2: sidebar split + field labels (UNCOMMITTED, same stack)

- **Version:** 1.1.5 · **git HEAD:** `3793daf` · **Working tree:** still uncommitted (billing WIP + brand sweep + printing + this).

Owner feedback: sale field should read "Customer Name" and be BLANK; purchase page should
mirror the sale billing UI; sidebar gets separate Purchase/Sale entries.

### Changes
- `entries/templates/entries/sale_bill.html` — label "Customer" → **"Customer Name"**;
  input no longer pre-filled with "Walk-in customer" (blank + `placeholder="optional"`).
  Empty customer still allowed by POST → prints as `-` on the paper and "walk-in" in the flash message.
- `entries/templates/entries/purchase_bill.html` — label "Supplier" → **"Supplier Name"**
  (its UI was already the structural twin of the sale bill: search-as-you-type, qty rows,
  stock badges, save → thermal print). Supplier remains REQUIRED (fail message mentions it).
- `templates/base.html` — sidebar "New Entry" replaced by two separate items:
  **New Purchase** (`entries:purchase_bill`, truck icon) and **New Sale**
  (`entries:sale_bill`, cart icon). Active-state covers bill + print + quick-form views.
  The old combined quick-form page (`purchase_add`/`sale_add` with tabs) is now orphaned
  from the nav but still works by URL — kept for tests/back-compat; decided not to delete.

### Tests
- `entries/tests.py` — sale GET test now asserts "Customer Name" + no prefill
  (`assertNotIn 'value="Walk-in customer"'`).
- NEW `PurchaseBillViewTests` (4): GET renders twin UI, staff saves 2-item purchase
  and lands on the purchase print URL, empty supplier rejected 400, anonymous redirect.
- Targeted run: 16 tests OK. Full suite: see `test-reports/2026-10-17_full-suite_run3.md`.

---

## 2026-10-17 — Session: shop-context alignment + bill printing (UNCOMMITTED, continues WIP billing feature)

- **Version:** 1.1.5 · **git HEAD:** `3793daf` · **Working tree:** still uncommitted (billing WIP + brand sweep + this).

Owner clarified the product: a **paint & household hardware shop**; no sites concept;
bills print on an **80mm thermal printer** with Rate/Amount/Total BLANK (hand-written).

### New: bill printing flow
- `entries/views.py` — post-save JSON now redirects to the printable bill:
  `entries/sale/bill/print/?ids=…` / `entries/purchase/bill/print/?ids=…`.
  New shared helper `_bill_print_context()` (+ `related=` per model — sub_location exists
  only on OutwardEntry) and `SaleBillPrintView` / `PurchaseBillPrintView`.
- `entries/templates/entries/bill_print.html` — NEW standalone print page
  (does NOT extend base.html): 80mm `@page`, centered shop header, party + date/time,
  items table (# / Item / Qty) with **blank Rate & Amt cells**, blank TOTAL strip,
  "Thank you" footer, auto `window.print()` after load, print/done buttons hidden on paper.
- `entries/urls.py` — routes `sale/bill/print/` + `purchase/bill/print/`.
- Printed header env-configurable: `BILL_SHOP_NAME` (default `nibba`), `BILL_SHOP_TAGLINE`
  (default empty) — owner said header is "not fixed yet", so one `.env` edit rebrands paper.
- `entries/templates/entries/quick_form.html` — Purchase tab banner added
  ("Open Purchase Billing", truck icon) mirroring the existing Sale banner.

### Fixed: legacy DB blocked the shop
- `sites/models.py::get_default_site()` — now counts only NON-deleted sites. The live
  `db.sqlite3` holds "Shop" + one soft-deleted legacy row; before, `count()==2` returned
  None and every quick/bill screen redirected to Sites. Bug-log WATCH item resolved.
- `template base.html` — logout online-cache purge referenced `nibba-shell-v1` while the
  worker builds `nibba-shell-v2` → logout never wiped the offline cache. Renamed to v2.

### Product docs aligned
- `AGENTS.md` §1 — paint & household hardware context; no-price-by-design; printing flow;
  no-sites rule; pointer to `useme/` logging convention (added this session).
- `prd.md` — Shop Profile section + new §5a "Bill Printing".
- `architecture.md` — bill-print views/env documented under Data Models.

### Tests
- `entries/tests.py` — save test now asserts redirect → print URL with ids.
  NEW `BillPrintViewTests` (5): sale render w/ blank cells, whole-qty print
  (`{{ e.qty|whole }}`), purchase render w/ supplier, 404s for unknown/junk/empty ids,
  anonymous redirect.
- `sites/tests.py` — NEW `GetDefaultSiteTests` (3): single active default, soft-deleted
  ignored, two actives → None.
- Full suite: see `test-reports/2026-10-17_full-suite_run2.md` (result recorded there).

---

## 2026-10-17 — Session: brand sweep → COMPLETE (UNCOMMITTED, on top of WIP billing feature)

- **Version:** 1.1.5 · **git HEAD:** `3793daf` (silent updater: native batch, live download percent)
- **Working tree:** deliberately NOT committed — two distinct pieces of work are pending:
  1. Pre-existing WIP from earlier session: multi-item **Purchase/Sale billing screens**
     (`SaleBillView`, `PurchaseBillView`, `sale_bill.html`, `purchase_bill.html`,
     `entries/urls.py`, `quick_form.html`, `entries/tests.py` +7 tests — 127 tests green).
  2. This brand sweep (below). Do not commit them as one blob without the owner's OK.

### Source changes (11 mentions in 8 files + 4 stale `build/portable/nibba/` copies)
- `AGENTS.md` — rule 3 reworded: old cloud project referenced without its name (`../construction-inventory/`).
- `design.md` — title → "Design System — nibba"; example strings mentioning the old site name → "Shop 1".
- `core/tests.py` — draft-keeper assertion → `"nibba_entry_draft"`.
- `core/pwa_files/sw.js` — `SHELL_CACHE` (old brand shell cache name) → `'nibba-shell-v2'`
  (cache-name change ⇒ old SW cache self-purges on next activate; safe).
- `e2e/tests/journeys.spec.js` — J2 selector regex → `/nibba|site/i`.
- `entries/templates/entries/entry_form.html` — localStorage draft key prefix → `"nibba_entry_draft:"`
  (effect: any stale unsaved drafts stored under the old key are ignored; harmless).
- `seed_catalog.json` — seeded site name → `"Shop"`.
- `reports/views.py` — `_safe_name` docstring example → `'Shop - 1' -> 'Shop_1'`; PDF page footer → `"GENERATED BY NIBBA STOCK APP"`.
- `build/portable/nibba/{core/tests.py, core/pwa_files/sw.js, entries/templates/entries/entry_form.html, reports/views.py}` — mirrored fresh source copies (staging is disposable; next `BUILD-PORTABLE.bat` regenerates it).

### Live database surgery (owner approved: delete backups; site name left to agent judgment)
- `db.sqlite3` — site row pk=12 renamed (the old brand site name) → **`Shop`** (location `Devada` untouched;
  chosen because migration `0003` names fresh installs exactly this way — change in one UPDATE if the owner prefers another).
- `db.sqlite3` — 8 historical `entries_auditlog.entry_summary` rows scrubbed (old name substring → `Shop`).
- `db.sqlite3` — `VACUUM` after scrub (integrity_check ok) to clear freed-page fragments.
- **Deleted 13 DB snapshots** containing the name: 11 rotating `Backup/db_2026-10-*.sqlite3`,
  `db_backup_before_cleanup_20260911_225150.sqlite3`, `db_pre_handover_20260919.sqlite3`.
- Rollback info: original site name spelled here is removed by design; exact original string is
  recoverable from this session's temp scripts if ever needed (outside the project dir).

### Cleanup of byproducts
- Deleted stale bytecode: `core/__pycache__/pwa.cpython-314.pyc`, `reports/__pycache__/views.cpython-314.pyc`,
  `sites/__pycache__/forms.cpython-314.pyc` (old-source builds still carried the string).

### Verification
- Whole-directory scan (incl. binaries, excl. venv/.git): **0 mentions**.
- `manage.py test` after edits: **127 tests OK** (162s). See `test-reports/2026-10-17_full-suite.md`.
- ⚠️ Remaining (version-control internals only): the old name still exists inside
  `.git` object history (every commit from `d28dd53` v1.0.0 carries old-brand blobs).
  Removing it requires a history rewrite (`git filter-repo`) — destructive, needs owner OK.
  The working tree, live DB, and every data file are clean.

### New convention started this session
- `useme/` folder (this folder): change-log + bug-log + test-reports, updated every session.
