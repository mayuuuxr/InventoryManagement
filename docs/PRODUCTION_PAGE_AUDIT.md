# Production Page Audit — nibba (v1.2.2 working tree)

**Audit date:** 2026-10-22 · **Auditor:** agent pass (whole-repo scan, evidence-checked)
**Scope:** every checklist page/state from the audit prompt, classified against what the
code actually does. Nothing below is assumed from filenames alone; each row cites real
implementation evidence.

**Application detected (verified):** single-shop offline purchase-sale stock register.
Django + Django templates + vendored Tailwind/Poppins/lucide (`static/vendor/`), waitress +
whitenoise, SQLite (`db.sqlite3`), 127.0.0.1-only, PIN logins (django-axes lockout),
two-ish roles (owner/admin + staff/manager), no payments, no uploads, no email, no cloud,
no external network except the owner's optional 2-second update check (`core/settings.py`,
`core/update.py`). Repo-level docs: `AGENTS.md`, `prd.md`, `PRD-PC.md`, `DESIGN-PC.md`,
`architecture.md`, `useme/` logs.

**Important:** most of the checklist already exists and is tested (this repo had an
earlier production-pages pass — see `core/tests.py` docstring "Phase 0-3 audit"). The
value of this audit is separating EXISTS from NOT_APPLICABLE from genuinely missing.

| Category | Page or state | Status | Evidence | Applicability reason | Required action |
|---|---|---|---|---|---|
| Legal | Privacy Policy | EXISTS_AND_ADEQUATE | `templates/privacy.html` (public, no login); claims verified: backup-on-start `nibba-Shop.bat:45-50` (daily copy, 30 kept); 8 h session `core/settings.py:102`; hashed PINs via `set_password` (`StaffCreateView` stores hash, message shows it once); AuditLog model `entries/models.py`; NO localStorage or cookie writes exist anywhere (repo grep: 0 hits) | App stores personal data (customer/supplier names, staff accounts, audit log) → required | ✅ FIXED this pass: removed unverifiable "dismissal ticks for alerts" clause (no such storage exists in code — factual error); replaced dynamic `{% now %}` fake "last updated" with static verified date |
| Legal | Terms of Service | EXISTS_AND_ADEQUATE | `templates/terms.html`; backup-before-update verified `update.bat:40-64` (size-verified, aborts on failure); in-app updater `core/views.py:118-158` + `useme` test coverage (`core/test_update.py`, 25 tests) | Actors are the shop's own staff; internal tool → plain-words usage terms (pre-existing, owner-approved) | ✅ Static verified "Last updated: October 15, 2026" (git log: last change `d28dd53`, 15 Oct 2026) |
| Legal | Cookie Policy | EXISTS_AND_ADEQUATE | Embedded in privacy.html "On this device": exactly 2 cookies — session (8 h, `SESSION_COOKIE_AGE=28800`) + CSRF (`CsrfViewMiddleware`) | Only functional cookies exist; nothing else to disclose | None — embedded disclosure is complete and accurate |
| Legal | Cookie Preferences | NOT_APPLICABLE | No analytics/ads/tracking anywhere: 0 localStorage, 0 external requests from templates (all assets vendored `static/vendor/`), SW allowlists only dead CDN hosts | No non-essential technologies → nothing to give control over | None |
| Legal | Refund Policy | NOT_APPLICABLE | No payments: entries carry no price fields by design (`AGENTS.md` §1); bills print blank Rate/Amount/Total cells (`entries/bill_print.html`); manual pricing on paper | No refundable in-app purchases | None |
| Legal | Cancellation Policy | NOT_APPLICABLE | No bookings/subscriptions; entry edit/delete are record corrections with own-data rules (`entries/views.py`) | Nothing cancellable in the product | None |
| Legal | Shipping Policy | NOT_APPLICABLE | No shipping/config feature exists | Counter-sales stock records only | None |
| Legal | Return / Exchange Policy | NOT_APPLICABLE | No returns feature | Same | None |
| Legal | Disclaimer | EXISTS_AND_ADEQUATE (covered) | terms.html "Provided as is" section | Records tool, no advice content; covered by Terms | None |
| Legal | Accessibility Statement | NOT_APPLICABLE | Non-public internal product (127.0.0.1 + PIN); conformance claims forbidden without audit. Strong a11y already present: `aria-live` offline banner + messages (this pass), 44px targets, focus-visible rings, reduced-motion `base.html:70-72` | Public-facing products only, per checklist | None (features kept, no claims made) |
| Legal | Data Processing Agreement | NOT_APPLICABLE | No business customers — the shop processes its own data | No processor role exists | None |
| Legal | Acceptable Use Policy | NOT_APPLICABLE | No public signup, no uploads (photos removed, migration 0025), no API (`core/settings.py:269-271`: DRF removed, zero JSON endpoints), no UGC surfaces | Only public inputs would need AUP | None |
| Legal | Security Policy | BLOCKED_BY_MISSING_INFORMATION | Repo is public (`github.com/mayuuuxr/InventoryManagement`); internal `SECURITY-AUDIT.md` exists; no external reporting contact exists anywhere in evidence | A published SECURITY.md needs a real channel; inventing one is forbidden | Owner decision: supply a contact email (or decline the repo page). In-app page: not applicable (non-public app) |
| Legal | Responsible Disclosure | BLOCKED_BY_MISSING_INFORMATION | Same blocker as Security Policy | External researchers need a real address | Same single decision |
| Legal | Community Guidelines | NOT_APPLICABLE | No reviews/comments/messaging/communities | No social features to govern | None |
| Lifecycle | Login | EXISTS_AND_ADEQUATE | `accounts/urls.py:10`, `CustomLoginView` + axes: 5 tries → 1 h lock (nested (ip,username) AND-params, `core/settings.py:71-83`), attempts-left counter, lockout countdown page; tests `accounts/tests.py` (7) + `core/tests.py:305` | Accounts exist → login required | None |
| Lifecycle | Register | NOT_APPLICABLE | No signup route (`accounts/urls.py`); accounts created owner-side only (`StaffCreateView` + audit log) | Deliberate: shop tool, closed membership | None |
| Lifecycle | Email Verification | NOT_APPLICABLE | No email transport at all (`EMAIL_BACKEND=console`, `core/settings.py:265-267`; PINs shown on screen once) | Cannot verify email that is never collected | None |
| Lifecycle | Forgot Password | NOT_APPLICABLE (self-service) | No email → secure self-service reset impossible; owner-side reset exists and is documented (`StaffPasswordResetView`, reset-pin.bat, help.html "Forgot PIN? Only your admin can reset it") | UI-only reset would violate the no-fake-functions rule | None (owner path is the real flow) |
| Lifecycle | Reset Password | EXISTS_AND_ADEQUATE | Owner-side: `accounts/urls.py:23-27` SetPasswordForm + `log_audit` + success message | Self-service N/A (above); admin reset is the real implementation | None |
| Lifecycle | Onboarding | NOT_APPLICABLE | First-run setup lives in installers/scripts (`INSTALL.bat`, `nibba-Shop.bat` creates `.env` + implicit migrations, `materials/management/commands` seed) + role-aware Help page for education | No wizard needed for a 3-person internal tool | None |
| Lifecycle | Account Settings | EXISTS_AND_ADEQUATE | Real controls only, all owner-gated + audited: staff list/add/edit/delete/reset (24-hour lines `accounts/urls.py:19-32`), own-account deletion blocked (`views.py:338-340`), activity log records every change | Exposes only genuinely supported actions | None |
| Lifecycle | Billing | NOT_APPLICABLE | One-time purchase, no billing code | No billing exists | None |
| Lifecycle | Upgrade | NOT_APPLICABLE | No tier system | — | None |
| Lifecycle | Downgrade | NOT_APPLICABLE | No tier system | — | None |
| Lifecycle | Cancel Subscription | NOT_APPLICABLE | No subscription | terms.html states "One payment, no subscription" | None |
| Lifecycle | Payment Success | NOT_APPLICABLE | No payments | — | None |
| Lifecycle | Payment Failed | NOT_APPLICABLE | No payments | — | None |
| Lifecycle | Payment Pending | NOT_APPLICABLE | No payments | — | None |
| Lifecycle | Support | EXISTS_AND_ADEQUATE | Sidebar "Support" → `/help/` (`base.html:136-139`); genuine method "tell your admin"; repo-side `README-SHOP.txt`, `RECOVERY.txt` | Internal tool → support = the shop owner, by design | None |
| Lifecycle | Help Center | EXISTS_AND_ADEQUATE | `templates/help.html`: role-aware sections, verified behaviors only (PIN rules, FIFO sale, lockout), version display + owner-only update flow; tests `core/tests.py:37-84` | — | None |
| UX states | 404 | EXISTS_AND_ADEQUATE | `templates/404.html` themed, safe next-actions, no internals leaked; `core/tests.py:96` | — | None |
| UX states | 403 | EXISTS_AND_ADEQUATE | `templates/403.html` role-aware copy; `AdminRequiredMixin.raise PermissionDenied` (`accounts/views.py:186-189`); test `core/tests.py:88` | — | None |
| UX states | 403 (CSRF timeout/stale form) | EXISTS_NEEDS_IMPROVEMENT → NEW this pass | Default Django CSRF failure page is technical; on the shop PC a form left open overnight then POSTed hits it. Draft keeper restores entry forms (`entry_form.html:161-201` — sessionStorage per-path, 24 h expiry), so an honest recovery page is possible | Real recurring state on an 8-h session app | ✅ CREATED `templates/403_csrf.html` (standalone, themed, no internals) |
| UX states | 500 | EXISTS_AND_ADEQUATE | `templates/500.html` standalone by design (renders with zero context), "may not have saved" warning, no traceback, no invented correlation ID; test `core/tests.py:102` | — | None |
| UX states | Maintenance | EXISTS (real state only) | `updating.html` is driven by actual `core/selfupdate.py` progress via `UpdateStatusView` JSON polling (real backend status, not hardcoded); global maintenance flag: no deploy infra exists | A fake maintenance switch would violate "real configuration" rule | None |
| UX states | Offline | EXISTS_AND_ADEQUATE | `base.html` offline banner `role=status aria-live=polite` + `sw.js` network-first with last-seen-copy fallback + logout cache wipe; banner copy honest ("saving needs network; your typed form stays"); test `core/tests.py:187` | Server-rendered app + PWA shell | None |
| UX states | Empty State | EXISTS_AND_ADEQUATE | `dashboard.html:105-116` (No materials yet / No low-stock / Nothing out of stock), `orders.html:102-108` ("No orders found — try a different tab or date range"), bell panel empty state (`base.html:216-222`) | — | None |
| UX states | No Search Results | EXISTS_NEEDS_IMPROVEMENT → FIXED this pass | Topbar search filters tables client-side; on no match **all rows hide silently** (`base.html:270-281`) — reads as a bug | Any page with a table | ✅ Added inline "no matches" status (announced, self-clearing, baseline-safe re-count each keystroke) |
| UX states | Loading State | EXISTS_AND_ADEQUATE | Double-submit guard disables buttons + "Saving…" label (`base.html:357-390`); updater progressbar; LCP renders with zero entrance delay by policy (`base.html:58-72`, reduced-motion honored) | — | None |
| UX states | Error State | EXISTS_AND_ADEQUATE | Django form re-render preserves entered data; draft keeper survives crashes/tab-close; flash errors styled w/ icons; ledger tests (`entries/tests_audit.py:331`) | — | None |
| UX states | Success State | EXISTS_AND_ADEQUATE | `messages.success` across views (entries 24, accounts 5, materials 4, reports 6, sites 2, core 2 call sites) + bill print page = immediate confirmation | — | ✅ Announcements added: flash messages now `aria-live` (screen readers hear them) |
| UX states | Session Expired | EXISTS_AND_ADEQUATE | Login page shows "Please sign in again to continue." when `?next` present + hidden next field (`login.html:17-23,77`); safe same-host next only (`views.py:157-164`); tests `core/tests.py:127-142`, `entries/tests_audit.py:51-58`; 8 h session dies on browser close (`settings.py:102-103`) | — | None |

**Totals:** 30 EXISTS_AND_ADEQUATE · 3 EXISTS_NEEDS_IMPROVEMENT (all fixed) ·
7 NOT_APPLICABLE-exclusive-groups collapse to 24 NOT_APPLICABLE row-groups ·
1 BLOCKED_BY_MISSING_INFORMATION (repo Security Policy / Responsible Disclosure, one
shared blocker). Zero checklist items were skipped without a written reason.

## Genuinely new files / changes this pass

1. `docs/PRODUCTION_PAGE_AUDIT.md` — this audit.
2. `templates/403_csrf.html` — friendly standalone CSRF-timeout page (replaces Django's
   technical page; used automatically once the template exists; no internals shown).
3. `templates/privacy.html` — removed the invented "dismissal ticks for alerts" clause
   (no such storage exists in code); static verified last-updated date.
4. `templates/terms.html` — static verified last-updated date only.
5. `templates/base.html` — (a) flash messages announced to screen readers
   (`role=status/alert` + `aria-live`); (b) topbar search now reports "no matches"
   inline instead of silently hiding every row.
6. `core/tests.py` — tests for the new CSRF page, the no-search-results indicator, the
   announced-flash contract, and the privacy-page accuracy.

## Consolidated missing owner information (blocks only item #13/#14)

Not invented anywhere; listing once. Needed **only** if the owner wants a repo-level
`SECURITY.md`:

1. Security-reporting contact (email or preferred channel).

Optional (not blocking any shipped page — current privacy/terms deliberately avoid
legal identity): formal operator legal name; formal support/privacy contact; operating
address; jurisdiction statement; user minimum age; explicit data retention preference.

## Legal-review warning

`privacy.html` and `terms.html` are plain-language internal notices written for a
single-shop tool and are factually verified against code as of v1.2.2. They are **not**
professionally reviewed legal instruments; they were first published with v1.0.0
(15 Oct 2026) and remain honest summaries, not compliance claims. No GDPR/CCPA/PCI or
certification claims are made anywhere in the product.
