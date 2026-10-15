# Design System — Vidarbha Homes App

> **This is the standing style guide. Every future page MUST follow these rules.**
> When in doubt: flat, clean, compact, no decoration. This is an internal business tool, not a marketing site.

---

## 1. Tech setup

- **CSS framework:** Tailwind CSS (CDN, with inline `tailwind.config` to set tokens)
- **Font:** Inter — loaded from Google Fonts in `base.html` (preconnect + display=swap)
- **Icons:** Lucide — `https://unpkg.com/lucide@latest` (single CDN script)
- **Template base:** `accounts/templates/accounts/base.html` is the single source of design tokens. Every page extends it.

To use a Lucide icon in a template:
```html
<i data-lucide="package" class="w-4 h-4"></i>
```
Then call `lucide.createIcons()` after DOM load (already wired in `base.html`).

---

## 2. Typography

| Element | Size | Weight | Color |
|---|---|---|---|
| Page title (`<h1>`) | 22px (`text-[22px]`) | 700 | charcoal |
| Section heading (`<h2>`) | 17px (`text-[17px]`) | 600 | charcoal |
| Card title (`<h3>`) | 15px (`text-[15px]`) | 600 | charcoal |
| Body | 14px (`text-sm`) | 400 | charcoal |
| Body emphasis | 14px | 500 | charcoal |
| Label / caption | 12px (`text-xs`) | 500 | muted |
| Muted helper text | 13px | 400 | muted |

- Line height: 1.5 for body, 1.3 for headings.
- Body text uses `font-sans` (Inter). Never set a custom `font-family`.
- Never use a font size above 24px for page titles — keep it compact, business-tool density.

---

## 3. Colors

All colors are exposed as Tailwind tokens via the inline config in `base.html`. Use the token name, not the hex, in templates.

### Neutrals
| Token | Hex | Use |
|---|---|---|
| `bg-app` | `#FAFAFA` | Page background |
| `bg-surface` | `#FFFFFF` | Cards, table rows, input background |
| `text-charcoal` | `#1A1A1A` | Primary text (never pure black) |
| `text-muted` | `#6B7280` | Secondary text, captions, placeholders |
| `border-subtle` | `#E5E7EB` | Default borders on cards and inputs |

### Accent (ONE color only — slate blue)
| Token | Hex | Use |
|---|---|---|
| `bg-accent` | `#4A6FA5` | Primary buttons, active nav, focus rings |
| `bg-accent-hover` | `#3D5C87` | Button hover (slightly darker) |
| `text-accent` | `#4A6FA5` | Links |
| `border-accent` | `#4A6FA5` | Focus outline |

### Status (pastel, used ONLY for badges / 4px left-stripes on alert cards)
| Token | Pair | Use |
|---|---|---|
| `bg-success` / `text-success` | `#DCFCE7` / `#166534` | OK / active / completed |
| `bg-warning` / `text-warning` | `#FEF3C7` / `#92400E` | Low stock / needs attention |
| `bg-danger` / `text-danger` | `#FEE2E2` / `#991B1B` | Critical / error / locked out |

**Rules:**
- Accent color is reserved for buttons, links, and active/selected states. Never for backgrounds of large areas.
- Status colors only on small badges or thin (4px) left stripes on neutral alert cards. Never as full card backgrounds.
- No gradients. No neon. No rainbow. No decorative colors of any kind.

---

## 4. Layout & spacing

- **Page max width:** `max-w-6xl` (1152px), centered with `mx-auto px-6`.
- **Page background:** `bg-app` (#FAFAFA) on `<body>`.
- **Card padding:** `p-5` (20px) or `p-6` (24px) — pick one and be consistent per page.
- **Vertical rhythm between cards:** `space-y-4` (16px) is the default.
- **Card style:** `bg-surface border border-subtle rounded-lg` (8px radius). Optionally `shadow-sm` for elevated cards (modals, popovers). Avoid heavy shadows.
- **No drop shadows on regular content cards** — use the subtle border instead.
- **Form field vertical spacing:** `space-y-4` between fields, `mt-1` between label and input.

---

## 5. Components

### Buttons
```html
<!-- Primary (the only button style you'll usually need) -->
<button class="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-md
               hover:bg-accent-hover transition-colors duration-150 focus:outline-none
               focus:ring-2 focus:ring-accent focus:ring-offset-1">
  <i data-lucide="plus" class="w-4 h-4"></i>
  Add new
</button>

<!-- Secondary (less emphasis) -->
<button class="inline-flex items-center gap-2 px-4 py-2 bg-surface text-charcoal text-sm font-medium
               rounded-md border border-subtle hover:bg-gray-50 transition-colors duration-150">
  Cancel
</button>

<!-- Danger (use sparingly, only for delete confirmations) -->
<button class="... bg-red-600 text-white hover:bg-red-700 ...">Delete</button>
```
- `rounded-md` (6px) on buttons — not `rounded-lg`. Buttons should feel slightly less rounded than cards.
- No scale, no bounce, no shadow on hover. Only color shift + 150ms transition.

### Inputs
```html
<div>
  <label class="block text-xs font-medium text-muted mb-1.5">Username</label>
  <input type="text" class="w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm
                            text-charcoal placeholder:text-muted
                            focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20">
</div>
```
- Default border is `border-subtle`. On focus: `border-accent` + a translucent accent ring (`focus:ring-2 focus:ring-accent/20`).
- Placeholder text uses `text-muted`.

### Status badges
```html
<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-success text-success">
  <i data-lucide="check" class="w-3 h-3"></i>
  Active
</span>
```
- Pill-style with `rounded-md` (not full pill — keep it business-formal).
- Always pair an icon with the label inside the badge.

### Alert / status card (with left stripe)
```html
<div class="bg-surface border border-subtle rounded-lg border-l-4 border-l-warning p-4 flex gap-3">
  <i data-lucide="alert-triangle" class="w-5 h-5 text-warning flex-shrink-0 mt-0.5"></i>
  <div class="text-sm text-charcoal">Low stock for Crushed Stone at Vidarbha Park - 1.</div>
</div>
```

### Tables (for Site list, Material list, Inward/Outward/Transfer, Reports)
```html
<div class="bg-surface border border-subtle rounded-lg overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-gray-50 text-muted text-xs uppercase tracking-wide">
      <tr>
        <th class="text-left font-medium px-4 py-3">Site</th>
        <th class="text-left font-medium px-4 py-3">Location</th>
        <th class="text-right font-medium px-4 py-3">Balance</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-subtle">
      <tr class="hover:bg-gray-50">
        <td class="px-4 py-3 text-charcoal">Vidarbha Park - 1</td>
        <td class="px-4 py-3 text-muted">Nagpur</td>
        <td class="px-4 py-3 text-right text-charcoal font-medium">1,240 ft</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Loading states — skeleton (not spinners)
```html
<div class="animate-pulse space-y-3">
  <div class="h-4 bg-gray-200 rounded w-3/4"></div>
  <div class="h-4 bg-gray-200 rounded w-1/2"></div>
  <div class="h-4 bg-gray-200 rounded w-5/6"></div>
</div>
```
Use `animate-pulse` on a grey surface (`bg-gray-200`). Never use spinners with emojis or decorative animation.

### Empty states
```html
<div class="bg-surface border border-subtle rounded-lg p-12 text-center">
  <i data-lucide="package-open" class="w-10 h-10 text-muted mx-auto mb-3"></i>
  <h3 class="text-[15px] font-semibold text-charcoal mb-1">No sites yet</h3>
  <p class="text-sm text-muted mb-4">Add your first construction site to start tracking material.</p>
  <a href="/admin/sites/site/add/" class="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-md hover:bg-accent-hover">
    <i data-lucide="plus" class="w-4 h-4"></i>
    Add site
  </a>
</div>
```

---

## 6. Icons — Lucide only

- Source: `https://unpkg.com/lucide@latest` (loaded in `base.html`).
- Use via `<i data-lucide="icon-name" class="w-4 h-4"></i>`.
- Default size: 16px (`w-4 h-4`) inside buttons/badges, 20px (`w-5 h-5`) for card-level icons.
- Color: inherit from text color, or `text-muted` for de-emphasized icons.
- **No emojis anywhere. Not in headings, not in placeholders, not in alerts.**

Common icon mappings:
- Add / create: `plus`
- Edit: `pencil`
- Delete: `trash-2`
- View: `eye`
- Login / sign in: `log-in`
- Logout: `log-out`
- Site: `building-2`
- Material / inventory: `package`
- Inward: `arrow-down-to-line`
- Outward: `arrow-up-from-line`
- Transfer: `arrow-right-left`
- Reports: `bar-chart-3`
- User: `user`
- Users / group: `users`
- Settings: `settings`
- Search: `search`
- Filter: `filter`
- Warning: `alert-triangle`
- Error: `x-circle`
- Success: `check-circle`
- Info: `info`
- Empty state: `package-open` or `inbox`

---

## 7. What NEVER to do

- ❌ No gradients on any element
- ❌ No rainbow, neon, or decorative colors
- ❌ No emojis in UI (this includes 🚀 ✅ ⚠️ etc.) — use Lucide icons instead
- ❌ No marketing-style elements: no feature card rows, no bento grids, no pricing tables, no testimonials, no terminal-window visuals, no decorative orbs/dot-grid backgrounds, no animated arrows
- ❌ No "liquid glass" / frosted blur effects
- ❌ No scale/bounce hover animations
- ❌ No TOS / Privacy Policy pages (internal tool only)
- ❌ No oversized titles (>24px)
- ❌ No pure black (`#000000`) — use `text-charcoal` (`#1A1A1A`)

---

## 8. Where to find these in the code

| Design system piece | File |
|---|---|
| Tailwind token config (colors, fonts) | `templates/base.html` (inline `tailwind.config`) |
| Inter font import | `templates/base.html` (in `<head>`) |
| Lucide script | `templates/base.html` (end of body) |
| Nav + base layout | `templates/base.html` |
| Reference implementation (login, dashboard) | `accounts/templates/accounts/login.html`, `accounts/templates/accounts/dashboard.html` |

> NOTE: `accounts/templates/accounts/base.html` is only a 1-line shim (`{% extends "base.html" %}`). The canonical tokens live in `templates/base.html` — extend that.

**When you add a new page:** extend `base.html`, use the Tailwind tokens (`text-charcoal`, `bg-accent`, `border-subtle`, etc.), use Lucide icons. Don't redefine colors, don't import other fonts, don't add spinners.
