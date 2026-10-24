# Product Requirements — nibba Shop Stock App

## Purpose
Ek single retail shop ke liye PC-only system jo purchase (stock aaya) aur sale (stock gaya) track kare aur live balance dikhaye. Manual register/Excel replace karega. Koi server kharcha nahi, koi photo ka overhead nahi, koi phone nahi — ek PC holds the truth, entry usi PC par hoti hai.

## Shop Profile
- Shop **paint aur household hardware materials** bechti hai.
- **Sites ka concept shop ke liye NAHI hai** — one shop, one catalog (koi site picker UI nahi; code-level `Shop` row sirf backend ke liye).
- **Prices + GST on the bill (v1.2.9, owner Oct 2026):** rate billing screen par hi type hota hai aur entry ke saath save hota hai; printed A4 bill par price + GST breakup khud print hota hai (see 5a Bill Printing).

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
- Units — DECIDED (owner, Oct 2026): Indian-market units, ek canonical spelling per unit
  (Cement — bags, grit/ bajri/murum/sand/fly-ash — cft, bricks/blocks — nos,
  TMT steel/nails/putty — kg, pipes/roofing sheets — ft (running length mtr), paints
  aur chemicals — L, tiles/cover blocks — box, TMT/jali/bamboo — bundle, PPE — pairs).
  Purane spellings migration `materials/migrations/0008_normalize_units` se normalize
  hote hain (miter/m/mtrs→mtr, no→nos, bkt→L). Naya material add karte waqt isi list
  ka unit use karein.
- Optional per item (owner, Oct 2026): **HSN/SAC code** + **GST %** (e.g. 28) —
  bill ke HSN/GST columns me print hota hai. Blank = item GST-free print hota hai ("-" in the GST column).

### 4. Purchase Entry (Inward)
- Fields: Date, Time, Qty (whole numbers only), Received From (supplier), Material, **Rate (₹ per unit — naye entries par required)**
- Koi photo proof nahi — values seedha save hote hain
- Quick form: `entries/purchase/add/`; duplicate rule: same material+date+time blocked with friendly error

### 5. Sale Entry (Outward)
- Fields: Date, Time, Qty (whole numbers only), Customer (buyer name), **Rate (₹ per unit — naye entries par required)**, delivery link (FIFO — kaunsi purchase se maal gaya), Sub-location (free text, auto-created)
- Koi photo proof nahi
- Quick form: `entries/sale/add/`; Orders history: `entries/orders/`
- NOTE: purane `Supplied To` / `Place of Supply` fields hata diye gaye hain — material sirf apni shop se bikta hai (no external supply concept).

### 5a. Bill Printing (A4 tax invoice, printed money — v1.2.9)
- Sale/Purchase **billing screens** (`entries/sale/bill/`, `entries/purchase/bill/`): ek bill me multiple items; fields — party (customer/supplier) name, items, **rate (₹ per unit, required — product ke naam ke bagal me type hota hai)**, qty, date, time. Line ka Amount (qty × rate, GST se pehle) billing screen par live dikhta hai.
- Save ke turant baad printable bill khulta hai (`entries/sale/bill/print/?ids=…`) aur print dialog auto-chal jata hai — **A4 sheet** (purana 80mm thermal roll retire).
- Paper format (**TAX INVOICE** sale / **PURCHASE BILL** purchase): shop header (`BILL_SHOP_NAME/TAGLINE/ADDRESS/PHONE/EMAIL/GSTIN/PAN` env sab optional), party + date/time, **Doc No** (`OUT-…`/`IN-…` = bill ki pehli line ka order id), items table (#, Item, HSN/SAC, Qty, Rate ₹, Amount ₹, GST%) — har line ka rate bilkul SAVED rate se print hota hai.
- GST breakup: per-rate grouped — `Base Amt, CGST @half% = half tax, SGST @half% = half tax` (28% → CGST @14% + SGST @14%; odd paisa SGST me chala jata hai). Sale me breakup aata hai (item ki `gst_rate` se, rates EXCLUSIVE of tax); purchase sheet par item list + rates print hote hain, GST breakup nahi.
- Totals: Sub Total → Total Tax (CGST + SGST) → **Round Off (half-up to the rupee)** → Grand Total, plus **amount in words** (hand-rolled, no new dependency). Sab PRINT TIME par derive hota hai (`entries/utils.py: bill_invoice_totals`) — app koi total STORE nahi karti, ledger correction ke baad reprint hamesha sahi hai.
- Pre-price legacy rows (rate bachaya hi nahi tha) Rate/Amount par **"-"** print karte hain aur totals me honestly 0.00 dete hain — fake number kabhi nahi.
- Orders page order sheet (`entries/orders/<kind>/<pk>/`): saare stored fields + same bill ki baaki lines unke rate/amount + Taxable Sub Total + **Print bill (A4)** button (whole bill one click).

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
- No photo proof, no push notifications, no phones, no LAN/tunnel access, no cloud hosting, no multi-shop sync, no GPS/QR, no accounting/GST-return filing app (bills sirf breakup PRINT karte hain — books waise hi bahar hote hain), no Transfer UI in v1

## Open Questions (client se confirm karna baaki)
- Negative balance allow karna hai ya block karna hai — DECIDED: blocked in app forms
- Steel/plumbing/other materials ke units — DECIDED (Oct 2026): Indian-market glossary; migration `materials/0008` purani spellings normalize karta hai
- Low-stock thresholds — DECIDED: 10 (owner, Oct 2026); IMPLEMENTED (reorder_point + dashboard low/out-of-stock tabs; bell ab latest purchase/sale notifications dikhata hai)
- Transfer entries — DECIDED (owner, Oct 2026): shop kabhi use nahi karega; TransferEntry model dormant admin-only rahega (no UI)
