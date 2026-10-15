# Design Brief — nibba PC only (from PRD-PC.md)

> **Theme v3 FROZEN (Oct 2026): Ocean Breeze.** This doc is the source of
> truth. Tokens live in `templates/base.html` (`tailwind.config`); change
> them only together with this doc. No pills, no gradients, no emojis.

## 1. Design principles
1. **PC first, small windows still work.** Every entry form completable in ≤30s on the shop PC; layout also survives narrow windows (single column under 640px) since the owner may snap it beside Excel.
2. **One truth, zero decoration.** Flat business-tool look. No gradients, no emojis, no marketing blocks. Balance numbers are the hero, not chrome.
3. **No dead ends.** Every failure (server stopped, session expired) shows what happened + the single next step, never a raw 404/500.

## 2. Visual direction
Mood: ledger book, not dashboard startup. Poppins, ocean-blue accent `#0B3D91` only for primary actions/links, single accent keeps staff from mistaking decorative color for stock status. Readable numerals on cheap phones in sunlight. Avoid: gradients of any kind, glass blur, bounce animations, oversized titles, pill badges, emojis.

## 3. Design tokens (FROZEN — `templates/base.html`)
Colors: frame `#D4E9FA` (outer shell) / app `#E8F6FF` (content) / surface `#FFFFFF` (cards) / charcoal `#0F2440` (text) / muted `#5C738A` (secondary text, never qty) / subtle `#C9E2F2` (borders) / accent `#0B3D91` + hover `#082E6E` / tang `#3BA7F2` + hover `#2B8FD9` (bright highlights). Status: success bg `#D9F2E2` fg `#1B7A3D` / warning bg `#FEF3C7` fg `#92400E` / danger bg `#FEE2E2` fg `#B42323` — always as `bg-*-bg` + `text-*-fg` pairs, never raw hex, never default-green/red utilities for status meaning. Type: Poppins (vendored, system-ui fallback). Radius: md 8px / lg 12px / xl 16px; full-round only for avatar dots and timeline markers, never badges or buttons. Shadows: soft `0 2px 12px rgba(11,61,145,.08)` / lift `0 8px 24px rgba(11,61,145,.14)`. Phone rules: inputs min-height 44px on touch, primary submit full-width on <640px, balance figures tabular-nums, sticky bottom action bar on entry screens (phone) with primary Save + secondary Cancel.

## 4. Screen inventory
1. Login (PIN). 2. Dashboard (all / low-stock / out-of-stock tabs, landing after login). 3. Orders history. 4. Purchase quick form. 5. Sale quick form. 6. Material ledger (Purchase/Sale tabs). 7. Purchase add/edit. 8. Sale add/edit (delivery picker + customer + sub-location). 9. Material add (Category/SubCategory/unit/reorder). 10. Reports hub → site summary / material consumption / monthly (screen+xlsx+pdf). 11. Help + Privacy + Terms. 12. Server-stopped/offline states. Single `Shop`, no site picker anywhere. Admin UI out of scope for staff.

## 5. User flows
Owner morning (PC): double-click `nibba Shop` icon → Dashboard → low/out-of-stock tabs → drill to ledger → monthly report → export xlsx. Staff purchase (same PC): login → Purchase → pick date/time/qty/supplier → Save → see updated balance. Staff sale: Sale → pick from-delivery (shows remaining) → qty → customer → sub-location free text → Save. Add material (owner): Materials → Add → category/subcategory/name/unit/reorder → Save → available in forms immediately.

## 6. Per-screen layout
Login: centered card (max-w-sm), app name, username + PIN, single accent submit, lockout countdown state. Site list: `max-w-6xl`, h1 22px + Add-site button right; cards/table rows: name, location, low-count badge. Ledger: header (site › material + unit + balance big), tabs Inward|Outward, table date/time/qty/from-or-sublocation, Add button sticky on phone. Entry forms: single column, `space-y-4`, label 12px muted above each input, delivery select shows `Sep 5 · 10:00 AM · 200 bags (160 left)`, sub-location input with datalist, full-width Save on phone. Reports: filter row (site/material/month) + table + Export xlsx/pdf buttons.

## 7. Component library
Buttons: primary accent / secondary outline / danger (delete only), rounded-xl, 150ms color shift. Inputs: subtle border, accent focus ring, muted placeholder. Badges: success/warning/danger token pairs + Lucide icon, rounded-md (never full-round). Tables: gray-50 header, divide-subtle rows, right-aligned qty. Alert card: white + 4px left stripe. Skeleton: `animate-pulse` gray blocks (no spinners). Empty state: centered icon + title + one CTA. Bottom action bar (new, phone only). All icons Lucide (`plus, pencil, trash-2, arrow-down-to-line, arrow-up-from-line, bar-chart-3, building-2, package`).

## 8. States
Empty: "No entries yet" + Add CTA. Loading: skeleton rows (ledger), disabled Save with "Saving…". Error: field-level (qty > available, duplicate datetime, outward before inward) + server-stopped card ("Server not running — open the nibba Shop icon again"). Success: redirect to ledger with balance updated + message. All assets vendored locally, so the layout never depends on the network. Session expiry: redirect to login with `?next=`.

## 9. Responsive behaviour
Narrow window <640px: single column, full-width inputs + Save, tables → stacked rows (date/qty primary), sidebar collapses to hamburger. Desktop ≥1024px: `max-w-6xl` centered, tables full, filters inline. Touch targets ≥44px. No hover-dependent actions (all actions are buttons/links).

## 10. Accessibility
Contrast: charcoal `#0F2440` on white (AAA), muted `#5C738A` on white (AA for secondary only, never for qty). Focus: visible accent ring on all inputs/buttons, logical order (site → material → date → qty). Labels for every input (no placeholder-only). Keyboard: full form completable via Tab/Enter; tabs are real links. ARIA: `aria-live` for balance update + form errors, `role=alert` on error cards, decorative Lucide icons `aria-hidden`.
