# Product Requirements — nibba Shop Stock App

## Purpose
Ek single retail shop ke liye PC-only system jo purchase (stock aaya) aur sale (stock gaya) track kare aur live balance dikhaye. Manual register/Excel replace karega. Koi server kharcha nahi, koi photo ka overhead nahi, koi phone nahi — ek PC holds the truth, entry usi PC par hoti hai.

## Users
- Owner/Admin — full access, catalog, reports, staff PIN, updates
- Staff — purchase/sale entry karta hai (same PC, alag login)
- Manager — admin jaisa full access (activity/audit pages sirf owner ke liye)
- NOTE: single shop hai, isliye koi staff-site assignment model nahi hai. Staff sab kuch dekh sakte hain (reads global hain); edit/delete sirf apni khud ki entries par (created_by basis).

## Core Features

### 1. Authentication
- Owner/Staff login (PIN + role-based); 5 galat attempts par 1-hour lockout (IP + username basis)

### 2. Single Shop (no site picker)
- Fresh install par `Shop` site auto-create hota hai (migration `0003_ensure_shop_site`)
- UI me site picker nahi hai — sab kuch Shop ke andar

### 3. Material Management
- Owner aur Staff dono material add kar sakte hain
- Catalog hierarchy: Category > SubCategory > Material (e.g. Steel > 8mm)
- Har material ka apna unit + reorder_point (default 10) hota hai:
  - Cement — bags
  - Crushed Stone (gitti) — ft
  - Fly Ash — ft
  - Murrom — ft
  - Sand — ft
  - Bricks — pieces
  - Steel, Plumbing, etc. — TBD (client se confirm karna hai)

### 4. Purchase Entry (Inward)
- Fields: Date, Time, Qty (whole numbers only), Received From (supplier), Material
- Koi photo proof nahi — values seedha save hote hain
- Quick form: `entries/purchase/add/`; duplicate rule: same material+date+time blocked with friendly error

### 5. Sale Entry (Outward)
- Fields: Date, Time, Qty (whole numbers only), Customer (buyer name), delivery link (FIFO — kaunsi purchase se maal gaya), Sub-location (free text, auto-created)
- Koi photo proof nahi
- Quick form: `entries/sale/add/`; Orders history: `entries/orders/`
- NOTE: purane `Supplied To` / `Place of Supply` fields hata diye gaye hain — material sirf apni shop se bikta hai (no external supply concept).

### 6. Transfer Entry
- Shop-to-shop transfer ka concept nahi hai (single shop)
- NOTE (as implemented): Transfer ka app UI nahi hai — sirf Django admin/shell se entry hoti hai (reserved for future).

### 7. Balance Stock
- Auto-calculated (stored nahi hota): Inward − Outward − Transfer(out) + Transfer(in)
- Real-time, per material (single shop)
- Negative balance BLOCKED hai app forms me (available se zyada qty par error)
- Sub-location balance = allocated − used (allocation nahi hai to shop balance use hota hai)

### 8. Reports
- Site-wise stock summary (screen + .xlsx + .pdf)
- Material-wise consumption with sub-location breakdown (screen + .xlsx + .pdf)
- Monthly activity report (screen + .xlsx + .pdf)
- Low-stock / out-of-stock tabs: reorder_point (ya default 10) se kam stock wale items
- Monthly Excel files (`Data/YYYY-MM/sales.xlsx` + `purchases.xlsx`) har launch par regenerate hote hain — owner seedha file me kaam kar sakta hai

### 9. Sub-location / Internal Distribution (implemented)
- Shop ke andar sub-locations (e.g. "Banglo 1".."Banglo 10" — free text, auto-created)
- Purchase shop level par aata hai, phir sub-locations me allocate hota hai
- Allocation informational hai — sale rokne ke liye shop-level balance check hota hai

### 10. PC Operation (zero monthly cost)
- `nibba-Shop.bat` — daily opener (backup → migrate → waitress on 127.0.0.1 → browser app-mode)
- `INSTALL.bat` — first-time setup (venv, requirements-pc.txt, migrate, owner login)
- `update.bat` — code-only updates from GitHub Releases (DB/Backup/Logs/Data protected)
- Har launch par automatic: SQLite backup (`Backup/`, 30 copies) + monthly Excel export

## Non-goals (explicitly OUT)
- No photo proof, no push notifications, no phones, no LAN/tunnel access, no cloud hosting, no multi-shop sync, no GPS/QR, no accounting/GST, no Transfer UI in v1

## Open Questions (client se confirm karna baaki)
- Steel/plumbing/other materials ke units — PENDING
- Negative balance allow karna hai ya block karna hai — DECIDED: blocked in app forms
- Low-stock thresholds — IMPLEMENTED (reorder_point + dashboard low/out-of-stock tabs); bell ab latest purchase/sale notifications dikhata hai; thresholds client se confirm karna baaki
