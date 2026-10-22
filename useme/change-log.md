# Change Log (newest first)

Format per entry: `date | VERSION | git HEAD | state of working tree | what & why`

The old brand string (removed from this repo on 2026-10-17) is never spelled
in these logs — it is referred to as "the old brand string". This keeps the
log useful while honoring the no-mentions rule.

---

## 2026-10-23 — Session: shop launch outage root-caused + v1.2.3 windowless restart hardening

- **Version:** 1.2.3 (bumped from 1.2.2) · **git HEAD at session start:** fb861ac ·
  **Tree:** clean before this change set (owner-approved scope mid-session).

What & why (owner-reported: "after update the app took minutes and says no network"):
- A read-only diagnostic script (delivered via OneDrive, auto-cleaned after) first
  read the WRONG copy — the real app the desktop shortcut opens is
  `AppData\Local\nibba` (v1.2.1), not this git repo folder. Corrected in-session.
- Root cause chain (evidence-only): the in-app updater (v1.2.1→v1.2.2 attempt)
  stopped the live server ~22:45 Oct 22 and died mid-flight (no pre-update backup,
  VERSION still 1.2.1); every icon launch afterwards reached the monthly-export
  step (its Django boot lines appear in that copy's log, 23:09→01:42) and no
  server boot or request lines follow any of them — port 8000 empty on every
  probe: the generated `runtime\Scripts\waitress-serve.exe`
  launcher exits with zero output (even `--help`; no Defender/App-Event records).
  Repair probes also revealed that runtime's pip is broken (certifi\cacert.pem
  deleted — no AV trail; cause unresolved; app does not need certifi). The
  db/.env were untouched throughout.
- Mechanism fix (verified before shipping): the embeddable runtime does not put the
  app folder on sys.path in `-c` mode (python312._pth '.' is exe-relative), so the
  launch line injects `sys.path.insert(0,os.getcwd())` and starts via pythonw
  (`start "" "%PYW%"`) — windowless for staff; verified HTTP 200 on
  /accounts/login/ through the exact command the icon runs.
- v1.2.3 (this tag) carries that launcher into the repo (`nibba-Shop.bat`) and
  the SAME fix into `core/selfupdate.py` APPLY_TEMPLATE: the generated applier's
  two restart lines used `%WS%` = waitress-serve.exe — the same silent-exit trap
  that killed the post-update restart — they now use the pythonw start line.
  `update.bat` needed no change (pip failure already warned-and-continued; it
  never restarts the server).
- Tests: applier-marker test now asserts ZERO powershell invokes, no `%WS%`, and
  both restart lines on `%PW%`; new `LauncherScriptTests` asserts the launcher
  starts via `%PYW%` + sys.path.insert and never via the shim (+5 net tests;
  no model changes).
- Transition note: the RUNNING server still carries the old template in memory, so
  the owner re-launches the app once (icon), then runs Help → Install — the update
  targets v1.2.3 directly (skips the still-published v1.2.2 asset whose
  SECURITY-AUDIT.md embedding predates the redaction).
- Owner-approved cleanups on the production copy: stale 140.5 MB `build\` deleted,
  duplicate Start-Menu shortcut deleted (Desktop icon kept), diag/temp artifacts
  removed. No commits pushed until the owner said go (this entry lands with the
  v1.2.3 commit).

### v1.2.4 (same session, one hour later, owner-approved follow-through)

Owner request: "after updating it should show app updated" + scrolling and
switching pages felt jittery. Answers + changes:

- Update confirmation twice over: updating.html holds "nibba <tag> installed -
  you're all set." for 2.5 s before the dashboard takes over (visible from the
  NEXT update on — the page shown DURING a given update is served by the
  pre-update code, by design), and dashboard.html shows a success banner
  ("nibba updated to v<VERSION> — never touched") whenever the running build
  finished installing within the last 10 minutes — that banner survives the
  page-swap mechanics because the dashboard right after the restart is served
  by the NEW code, so it confirms this machine's own update in real time.
  Mechanism: new core/selfupdate.just_updated() — stateless freshness read of
  update-last-run.txt (mtime window + version match; nothing to dismiss).
- Scroll/page-switch smoothness (owner chose removing the fade): base.html
  drops the @view-transition 120ms whole-page fade (full-page raster per
  navigation = the option-switch stutter), adds scrollbar-gutter: stable
  (no sideways reflow between long and short pages) and turns table-row
  hover instant (row tweens repainted whole rows every scroll frame on the
  shop GPU; buttons keep their transitions).
- Restart UX (owner question, answered in the conversation): no manual
  restart after an update — the applier restarts the server itself (pythonw
  now); the icon relaunch stays the only daily habit. No UI element added.
- Tests: JustUpdatedBannerTests (+2: missing file; fresh/stale window ×
  version match). Suite green; no model/migration changes in v1.2.4.

### v1.2.5 (same session, minutes later, owner-approved)

Owner request: "remove above comment in the print receipt" — clarified via
options; the offender is Chromium's OWN print header/footer stamp (date,
page URL, "Sale Bill | nibba") drawn INSIDE the @page margins at the
receipt's top edge.

- entries/templates/entries/bill_print.html: @page margin 2.5mm → 0 (with
  margin gone the browser has nowhere to draw its stamp and drops it
  entirely — documented Chromium behaviour) + body padding 1.5mm top /
  4mm bottom so ink clears the paper edge and the auto-cut. Template-only;
  suppressed v1.2.4 within minutes of its publish so the shop's single
  in-app install covers everything (1.2.1 → 1.2.5 one click). No tag-level
  fix-up games, no redundant in-place prod patch (the update delivers it).
- No python changes; entries suite green (template renders unchanged
  except the margin/padding CSS).

### v1.2.6 (same session, minutes later — the receipt "comment" decoded)

The owner's screenshot (03:11) showed the receipt printing a wall of text
above the bill: "{# Printable bill (sale + purchase) … paper. #}" — the
original request's true target was THIS, not the browser stamp (that fix
still stands; margin-0 dropped the Chromium header/footer entirely).

- Root cause: Django template comments `{# … #}` are single-line only —
  a MULTI-LINE `{# … #}` block falls through the lexer as literal text
  and renders (and prints). `bill_print.html` opened with a 6-line note;
  `order_detail.html` printed the same kind of note above every order.
- Fix: both notes re-broken into single-line `{# #}` lines (text kept,
  renders as nothing), each now carrying its own "never multi-line"
  warning so the pattern cannot quietly return. Repo-wide scan confirms
  these were the only two multi-line offenders across all templates.
- VERSION → 1.2.6; published so the owner's single in-app install
  (1.2.1 → 1.2.6) carries every fix from this session. No python logic
  changes; entries suite green.

### v1.2.7 (same session — receipt typography, owner's screenshot #2)

The second screenshot showed the layout complaint behind "should come in
same line only": paint names ("Asian Paints Royale 1L") wrapped 3–4 lines
inside a 33mm Item column while `vertical-align: bottom` dropped the row
number and qty onto the name's LAST line — the row looked scrambled.

- entries/templates/entries/bill_print.html: body font 11.5px → 10.5px
  (labels/sub/meta/thanks/total trimmed to match); Item column 33mm →
  39mm; qty strip freed (no fixed 9mm — nowrap, auto); Rate/Amt hand-fill
  strips 12/13mm → 9.5mm each (still pen-friendly); items cells align
  TOP so number, name and qty always begin on the same line.
- Version-surface: 1.2.7. Template-only; entries suite green.

### v1.2.8 (same session — the leak the guard missed + uniform type)

Owner's print-preview screenshot (03:37) showed the receipt tail
"…comments are NOT supported by the Django #}" STILL leaking. Two truths:
the shop copy had not installed the newer code yet, AND the v1.2.6
"warning note" itself nested a template-comment pair inside its own
comment — the inner pair closed early and the line's tail rendered as
text. The v1.2.6 lint (unclosed-opener regex) could not see a
premature close.

- bill_print.html + order_detail.html: both note blocks rewritten free of
  nested brace pairs (text kept, advice intact).
- Uniform type on the receipt (owner: "use the thank-you size"): body,
  meta, item rows, header row and TOTAL all 10px; only the NIBBA brand
  line stays 14px bold. With the smaller size the 39mm Item column now
  fits even longer paint names on one line.
- TemplateCommentLint hardened into a per-line mini-lexer: fails on an
  opener left open AND on a stray closer in plain text (both render as
  text) — the class of bug can no longer pass the suite silently.
- Version-surface: 1.2.8; suite green. Owner's next in-app install
  carries 1.2.1/1.2.5/1.2.7 → 1.2.8 in one click.

---

## 2026-10-22 — Session: production-pages audit (checklist vs. evidence)

- **Version:** 1.2.2 · **git HEAD at session start:** 30fa4e5 · **Tree:** 4 modified
  files + 2 new files, uncommitted (owner review pending).

What & why (owner-directed full-scope audit):
- New: `docs/PRODUCTION_PAGE_AUDIT.md` — 42 checklist rows classified with file/line
  evidence. Verdict: the app already covers nearly everything (an earlier pass built
  help/privacy/terms, themed 400/403/404/500, offline banner + SW fallback, draft
  keeper, session-expired notice, empty states). Payments/subscriptions/email/UGC
  flows are NOT_APPLICABLE by design; repo Security Policy/Responsible Disclosure is
  BLOCKED on an owner-owned reporting contact (not invented).
- Fixed 3 real gaps: (1) privacy.html claimed "dismissal ticks for alerts" — no such
  storage exists anywhere in code → clause removed, static verified last-updated
  dates on privacy/terms (dynamic {% now %} date was misleading); (2) topbar search
  on zero matches silently hid every table row → inline announced "No matches for…"
  state; (3) flash messages were invisible to screen readers → role status/alert +
  aria-live.
- New page: `templates/403_csrf.html` — friendly standalone CSRF-timeout recovery
  page (honest copy: nothing was saved; entry forms keep drafts). Replaces Django's
  technical default once present.
- Tests: +5 in core/tests.py (CSRF page standalone + live, no-match indicator,
  announced flashes, privacy-claim accuracy). Full suite ran 151: 150 green + the
  escaping-flawed test fixed and re-verified green 5/5 in isolation. No model changes
  (makemigrations --check: No changes detected). No commits made.



- **Version:** 1.2.2 · **git HEAD at session start:** eca5d08 · **Tree:** clean.

What & why (owner-approved this session):
- SECURITY-AUDIT.md: the CRITICAL-1 Cloudinary key + secret values redacted with
  [REDACTED]; owner rotates/revokes the pair at cloudinary.com. Git history
  still holds the pre-redaction values — rotation is the real fix.
- Minimal typo-audit doc fixes (owner picked "sure rows only"): README-SHOP.txt
  step count 3→4, AGENTS.md "paste"→"just", bug-log.md behavior→behaviour.
  All other audit rows remain open (code-side rows need separate approval;
  term-casing picks still pending).
- Untracked junk deleted from the folder after approval: cloudflared.exe +
  tunnel.log (dead tunnel era), build\ staging tree (~186 MB, regenerable via
  BUILD-PORTABLE.bat), Temp\opencode session artifacts. backup_*.json kept
  (safety snapshots referenced by these logs).

## 2026-10-22 — Session: owner decisions locked + unit normalization + dependency hardening (v1.2.2)

- **Version:** 1.2.2 (bumped from 1.2.1) · **git HEAD at session start:** 5e3b1cf ·
  **Landing:** released as commit 4e8c8a9 "v1.2.2: normalize material units
  (migration 0008); Pillow >=13.0,<14.0 after pip-audit" on main; annotated tag
  v1.2.2 points at it; both pushed to origin/main.

Owner answered every pending question in one pass:

1. **Units = Indian market** — canonical glossary recorded in prd.md/AGENTS.md
   (bags / nos / cft / ft / rft / mtr / kg / L / box / bundle / pairs / sqft / pk / ml).
   New data migration `materials/migrations/0008_normalize_units.py` rewrites legacy
   spellings on every install: miter/m/mtrs→mtr, no→nos, bkt→L. Dev db.sqlite3
   (17 rows) and seed_catalog.json (18 rows) verified clean after apply.
2. **Low-stock threshold = 10** — DECIDED (was "confirm with client").
3. **Transfer entries: never used** — DECIDED. TransferEntry stays dormant
   admin-only; balance formula keeps its terms (always zero on real installs).
4. **seed_catalog.json kept** as the dev/e2e fixture; synced to the new units.
5. **Security fix (fresh pip-audit run):** requirements-pc.txt Pillow pin
   `>=11.0,<13.0` → `>=13.0,<14.0` — installed 12.3.0 carried 34 CVEs, all fixed in
   13.0.0; re-audit now "No known vulnerabilities found". pip-audit itself is a
   dev-only tool in the dev venv (not in requirements; never ships to shop PCs).
6. `.env` audited by KEY NAMES only: just DJANGO_SECRET_KEY / DEBUG /
   ALLOWED_HOSTS / UPDATE_REPO — no legacy Cloudinary/VAPID leftovers, and no stray
   *.pem / *token*.txt / nibbakey.txt files anywhere. Dev copy runs DEBUG=True on
   purpose (local testing).
7. Owner notes the owner/1234 login is testing-only — change before shop handover.
8. Docs updated: prd.md (units glossary + resolved open questions), PRD-PC.md
   (§10 resolved), AGENTS.md (§5 decisions; tests list corrected — materials/tests.py
   is an empty stub, the 146 count includes core/test_update.py's 25).

**Gates:** `makemigrations --check --dry-run` → "No changes detected";
`manage.py test` → **146 tests OK** (run twice: 188.3 s / 186.9 s), system check clean.
Landed the same day after owner approval: commit 4e8c8a9 pushed to origin/main
with annotated tag v1.2.2. release.yml auto-published GitHub Release v1.2.2 with
asset nibba-v1.2.2.zip (589,549 B, sha256 4ab8acfe…) on the tag push; the asset
was re-downloaded and verified from the owner PC — digest match, zip contains
VERSION=1.2.2, materials/migrations/0008_normalize_units.py and the Pillow pin.
Shop PC completes the rollout itself by running: update.bat v1.2.2.

---

## 2026-10-18 — Session pass: v1.2.1 — order detail page + print receipt + update.bat repair

- **Version:** 1.2.1 · **git HEAD:** recorded in the landing note below ·
  **Working tree:** single release commit (same pattern as v1.2.0).

Half past midnight the owner asked: on the Orders page, clicking any order should open
ALL its details, and there was no print-receipt option in the Indian shop receipt
format. Shipped in this release:

1. **Order detail page** — new `entries:order_detail` route
   (`entries/orders/<inward|outward>/<pk>/`, `OrderDetailView`): every stored field
   (material + unit, qty, Customer/Supplier, business date + time, sub-location,
   FIFO linked-purchase link, entered-by, recorded-at) PLUS the other lines of the
   SAME bill (same party + date + time = one paper receipt) and a **Print receipt**
   button that opens the 80mm bill paper for ALL of those ids. Orders rows now open
   this sheet (they used to jump to the material ledger; the ledger link stays on
   the sheet).
2. **Receipt format** — the printed bill gains a `Bill No: OUT-…/IN-…` line (the
   bill's first line order id) so a paper receipt pins back to the Orders page.
   Rate/Amount/Total stay BLANK — the no-price shop rule is untouched.
3. **update.bat repaired** (bug-log 2026-10-18 → FIXED): five paren landmines
   removed (line-25 killed every invocation; line-70 escaped `pause`/`exit` outside
   the tag gate), reset-pin.bat clone fixed, and UPDATE_REPO resolves env → .env →
   baked real repo (placeholder gone).
4. **Tests:** 7 new OrderDetailViewTests; full suite 146 green
   (`useme/test-reports/2026-10-18_full-suite_v121.md`); makemigrations --check clean.

Shop PC deployment planned **through the repaired update.bat itself** (dogfood) after
owner approves push + tag — GitHub push stays consent-gated.

## 2026-10-18 — v1.2.1 LANDED: commit `139824f`, tag `v1.2.1`

- Full-suite gate: 146 OK (run 4, this release). CI release run #12 published
  release v1.2.1 with `nibba-v1.2.1.zip` — 586,368 bytes, sha256
  `bbe7b963e2aab53098510f0cb73f369aaffb2f175a37557d5ee2991a531357c1`
  (digest also verified directly from the GitHub API).
- **First real update.bat run ever (dogfood of the repair):**
  1. Bootstrap: repaired `update.bat` copied once into the installed copy (its own
     copy was still the defective bytes — a bat cannot fix itself; from v1.2.1 on,
     updates self-serve).
  2. `nibba-Close.bat` → port 8000 free.
  3. `update.bat v1.2.1` in `AppData\Local\nibba`: **EXIT=0** — backup
     `Backup\pre-update_2026-10-18_004934.sqlite3` (1,851,392 bytes, verified),
     correct asset URL, download + protected copy, migrate "No migrations to apply",
     collectstatic, system check clean, banner "Version now: 1.2.1".
  4. Post checks: downloaded zip sha == GitHub digest; db byte-size unchanged;
     .env untouched (DEBUG=False still set); feature files present; the installed
     update.bat now carries the baked repo and no placeholder.
  5. Relaunched via `nibba-Shop.bat` — server up (port 8000, pid 15428); login 200;
     `/entries/orders/outward/1/` + `/entries/orders/inward/1/` → **302 login
     redirect** (404 before v1.2.1: the new order-detail routes are live).
- In-app Updates page now compares 1.2.1 vs 1.2.1 → no Install button (correct,
  nothing newer exists).
- Owner-side verification done the same night: owner logged in as OWNER, refreshed
  once, opened order sheets from Orders and printed receipts — reported "done", no
  issues raised. Feature considered accepted at v1.2.1. Only remaining unexercised
  update path: the in-app Install button (`core/selfupdate.py`) — will prove itself
  on the next release from the Updates page.

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
