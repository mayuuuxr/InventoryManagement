"""
Shared opening-stock import logic (used by the management command AND the
admin web UI). Works on plain value matrixes so parsed files can round-trip
through the session between preview and confirm steps.

nibba has no photo entry: imported rows simply have no photos, like
every other entry.
"""
from datetime import date as date_cls
from datetime import datetime, time as time_cls
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("site", "material", "qty", "date", "received_from")
MAX_ROWS = 2000

# Owner's stock-sheet scheme (second accepted format):
#   Material | ... | UOM | In Stock | ... | Location | ...
# Only these columns are used; the rest are ignored.
THEIR_COLUMNS = ("material", "uom", "in stock", "location")

# Owner UOM spellings -> app units.
UOM_MAP = {
    "nos": "nos", "no": "nos", "kg": "kg", "bag": "bags", "bags": "bags",
    "bundle": "bundle", "pairs": "pairs", "pair": "pairs", "pk": "pack",
    "pack": "pack", "box": "box", "boxes": "box", "cft": "ft", "ft": "ft",
    "m": "mtr", "mtr": "mtr", "mtrs": "mtr", "miter": "mtr", "meter": "mtr",
    "metre": "mtr", "l": "L", "ltr": "L", "ml": "ml", "bkt": "bkt",
    "sqft": "sqft", "rft": "rft",
}

UNCAT_CATEGORY = "Uncategorized"
UNCAT_SUB = "Imported"


def detect_scheme(header):
    """'mine' for site/material/qty/date/received_from, 'theirs' for
    material/uom/in stock/location, else None."""
    if all(c in header for c in REQUIRED_COLUMNS):
        return "mine"
    if all(c in header for c in THEIR_COLUMNS):
        return "theirs"
    return None


def normalize_their_rows(header, rows, user=None, write_catalog=False):
    """Convert the owner's stock-sheet matrix to the canonical columns
    (site/material/qty/date/received_from/time), resolving/creating
    materials, syncing units from UOM, rounding fractional stock, and
    defaulting date to today. Returns (header, rows, notes dict).

    Unknown materials are auto-created under Uncategorized/Imported
    (owner decision); unknown UOMs keep the existing unit (or pieces).
    Auto-created catalog rows get created_by=user and an audit CREATE row.
    Preview (write_catalog=False) is pure: it plans creations in `notes`
    without writing; only the confirmed import writes catalog + entries.
    """
    import re
    from decimal import ROUND_HALF_UP

    from entries.models import AuditLog
    from entries.views import log_audit
    from materials.models import Category, Material, SubCategory
    from sites.models import Site

    notes = {"created_materials": [], "unit_updates": [],
             "rounded": [], "scheme": "theirs"}
    col = {name: header.index(name) for name in
           THEIR_COLUMNS}

    def _norm(text):
        return re.sub(r"[^a-z0-9]", "", str(text or "").lower())

    sites = list(Site.objects.all())

    def _resolve_site(raw):
        target = _norm(raw)
        if not target:
            return None
        hits = [s for s in sites
                if target in _norm(s.name) or _norm(s.name) in target]
        return hits[0].name if len(hits) == 1 else None

    materials = list(Material.objects.select_related(
        "category", "sub_category"))
    by_display = {m.display_name.lower(): m for m in materials}
    by_name = {}
    for m in materials:
        by_name.setdefault(m.name.lower(), m)

    cat = Category.objects.filter(
        name=UNCAT_CATEGORY, is_deleted=False).first()
    if cat is None:
        notes["created_materials"].append(
            f"category {UNCAT_CATEGORY}")
        if write_catalog:
            cat = Category.objects.create(
                name=UNCAT_CATEGORY, created_by=user)
            if user is not None and user.is_authenticated:
                log_audit(user, AuditLog.Action.CREATE,
                          AuditLog.EntryType.CATEGORY, cat.pk,
                          f"Category '{UNCAT_CATEGORY}' created "
                          f"by {user.username} (bulk import).")
        else:
            from materials.models import Category as _Cat
            cat = _Cat(name=UNCAT_CATEGORY)

    def _resolve_material(raw_name, raw_uom):
        name = str(raw_name or "").strip()
        if not name:
            return None
        # Maps hold active rows only (default manager), so a deleted
        # same-name row is naturally re-created fresh; history is kept.
        mat = by_display.get(name.lower()) or by_name.get(name.lower())
        unit = UOM_MAP.get(str(raw_uom or "").strip().lower())
        if mat is None:
            if not write_catalog or cat.pk is None:
                notes["created_materials"].append(f"{name} (planned)")
                return None
            sub = SubCategory.objects.filter(
                category=cat, name=UNCAT_SUB, is_deleted=False).first()
            if sub is None:
                sub = SubCategory.objects.create(
                    category=cat, name=UNCAT_SUB, created_by=user)
                if user is not None and user.is_authenticated:
                    log_audit(user, AuditLog.Action.CREATE,
                              AuditLog.EntryType.CATEGORY, sub.pk,
                              f"Sub-category '{UNCAT_SUB}' under "
                              f"'{cat.name}' created by {user.username} "
                              f"(bulk import).")
            mat = Material.objects.create(
                category=cat, sub_category=sub, name=name,
                unit=unit or "pieces", reorder_point=10, created_by=user)
            by_display[name.lower()] = mat
            by_name.setdefault(name.lower(), mat)
            notes["created_materials"].append(name)
            if user is not None and user.is_authenticated:
                log_audit(user, AuditLog.Action.CREATE,
                          AuditLog.EntryType.MATERIAL, mat.pk,
                          f"Material '{mat.display_name}' ({mat.unit}) "
                          f"created by {user.username} (bulk import).")
        elif unit and mat.unit != unit:
            notes["unit_updates"].append(
                f"{mat.display_name}: {mat.unit} -> {unit}")
            if write_catalog:
                mat.unit = unit
                mat.save(update_fields=["unit"])
        return mat

    from django.utils import timezone
    today = timezone.localdate().isoformat()
    canon = []
    for i, row in enumerate(rows):
        get = lambda n: (row[col[n]] if col[n] < len(row) else None)
        mat_name = str(get("material") or "").strip()
        if not mat_name:
            continue  # blank-ish row; process_rows reports shortage context
        try:
            qty = Decimal(str(get("in stock") or "").strip())
            whole = int(qty.to_integral_value(rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError, AttributeError):
            # pass through raw; process_rows reports the bad qty and no
            # material gets created for an invalid row.
            canon.append([get("location"), mat_name, get("in stock"), today,
                          "Opening Stock",
                          f"{9 + (i // 60):02d}:{(i % 60):02d}"])
            continue
        if whole != qty:
            notes["rounded"].append(f"{mat_name}: {qty} -> {whole}")
        site_name = _resolve_site(get("location")) or get("location")
        mat = _resolve_material(mat_name, get("uom"))
        canon.append([site_name, mat.display_name if mat else mat_name,
                      whole, today, "Opening Stock",
                      f"{9 + (i // 60):02d}:{(i % 60):02d}"])
    return (["site", "material", "qty", "date", "received_from", "time"],
            canon, notes)


def parse_workbook(file_obj):
    """Read an .xlsx upload into (header, data_rows) plain values.

    Dates/times become ISO strings so the matrix stays JSON-serializable
    for session storage. Returns (header, rows, error); error is None on ok.
    """
    from openpyxl import load_workbook

    try:
        wb = load_workbook(file_obj, read_only=True, data_only=True)
        matrix = list(wb.active.iter_rows(values_only=True))
    except Exception as exc:
        return None, None, f"Cannot read Excel file: {exc}"
    if not matrix:
        return None, None, "Empty file (no rows at all)."
    header = [(c or "").strip().lower() if isinstance(c, str) else ""
              for c in matrix[0]]
    rows = []
    for raw in matrix[1:]:
        if all(v is None or str(v).strip() == "" for v in raw):
            continue
        rows.append([_freeze(v) for v in raw])
    if len(rows) > MAX_ROWS:
        return None, None, f"Too many rows ({len(rows)}); max is {MAX_ROWS}."
    return header, rows, None


def _freeze(value):
    # JSON-safe primitives only (session round-trip). date cells keep just
    # the date (time lives in its own column); datetimes in the date column
    # collapse to their date part.
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_cls):
        return value.isoformat()
    if hasattr(value, "hour"):
        return f"{value.hour:02d}:{value.minute:02d}"
    return value


def process_rows(header, rows, user, dry_run=True):
    """Validate (and optionally save) opening-stock rows.

    Returns dict: created, skipped, errors (list of str), preview (list of
    dicts with n/status/message/site/material/qty/date/time/source).
    """
    from entries.models import AuditLog, InwardEntry
    from entries.views import entry_summary, log_audit
    from materials.models import Material
    from sites.models import Site

    result = {"created": 0, "skipped": 0, "errors": [], "preview": [],
              "notes": {"created_materials": [], "unit_updates": [],
                        "rounded": []}}
    from django.db import transaction
    # Owner's stock-sheet scheme is normalized to canonical columns first.
    # Preview stays pure (no catalog writes); confirmed import writes.
    if detect_scheme(header) == "theirs":
        header, rows, their_notes = normalize_their_rows(
            header, rows, user=user, write_catalog=not dry_run)
        result["notes"] = their_notes
    try:
        col = {name: header.index(name) for name in REQUIRED_COLUMNS}
    except ValueError:
        result["errors"].append(
            "Header must be either app-style (site | material | qty | date | "
            "received_from + optional time) or stock-sheet style (Material | "
            "UOM | In Stock | ... | Location). Found: "
            + ", ".join(h or "?" for h in header))
        return result
    time_col = header.index("time") if "time" in header else None

    materials = list(Material.objects.select_related(
        "category", "sub_category"))
    by_display = {m.display_name.lower(): m for m in materials}
    by_name = {}
    for m in materials:
        by_name.setdefault(m.name.lower(), m)
    # Preload sites once (case-insensitive map) instead of one query/row.
    site_map = {}
    for s in Site.objects.all():
        site_map.setdefault((s.name or "").strip().lower(), s)
    # Preload existing inward keys in ONE query so per-row exists() is free.
    _parsed_keys = []
    for row in rows:
        try:
            _s = str(row[col["site"]] if col["site"] < len(row) else "").strip().lower()
            _m = str(row[col["material"]] if col["material"] < len(row) else "").strip().lower()
            _d = _parse_date(row[col["date"]] if col["date"] < len(row) else None)
            _t = _parse_time(row[time_col] if time_col is not None and time_col < len(row) else None)
            if _s and _m and _d and _t:
                _parsed_keys.append((_s, _m, _d, _t))
        except Exception:
            continue
    existing = set()
    if _parsed_keys:
        _site_ids = {s.pk for s in site_map.values()}
        _mat_ids = {m.pk for m in materials}
        for r in InwardEntry.objects.filter(
                site_id__in=_site_ids or [0],
                material_id__in=_mat_ids or [0]).values(
                "site_id", "material_id", "date", "time"):
            existing.add((r["site_id"], r["material_id"], r["date"], r["time"]))

    from contextlib import nullcontext as _nullcontext

    def _ctx():
        return transaction.atomic() if not dry_run else _nullcontext()

    seen = set()
    with _ctx():
        for i, row in enumerate(rows, start=2):
            item = {"n": i, "status": "ok", "message": "",
                    "site": "", "material": "", "qty": "",
                    "date": "", "time": "", "source": ""}

            def _get(name, _row=row):
                return _row[col[name]] if col[name] < len(_row) else None
            get = _get

            def fail(msg, _item=item, _i=i):
                _item["status"] = "error"
                _item["message"] = msg
                result["errors"].append(f"row {_i}: {msg}")
                result["preview"].append(_item)

            site = site_map.get(
                str(get("site") or "").strip().lower())
            if site is None:
                fail(f"unknown site '{get('site')}'")
                continue
            mat_key = str(get("material") or "").strip().lower()
            material = by_display.get(mat_key) or by_name.get(mat_key)
            if material is None:
                fail(f"unknown material '{get('material')}'")
                continue
            try:
                qty = Decimal(str(get("qty") or "").strip())
            except (InvalidOperation, ValueError, AttributeError):
                fail(f"bad qty '{get('qty')}'")
                continue
            if qty <= 0 or qty % 1 != 0:
                fail(f"qty must be a whole number above zero "
                     f"(got '{get('qty')}')")
                continue
            day = _parse_date(get("date"))
            if day is None:
                fail(f"bad date '{get('date')}' (use YYYY-MM-DD)")
                continue
            moment = _parse_time(
                row[time_col] if time_col is not None and time_col < len(row)
                else None)
            if moment is None:
                fail("bad time (use HH:MM 24-hour, or leave blank)")
                continue
            source = str(get("received_from") or "").strip() or "Opening Stock"

            item.update(site=site.name, material=material.display_name,
                        qty=str(qty.normalize()), date=day.isoformat(),
                        time=moment.strftime("%H:%M"), source=source)
            key = (site.pk, material.pk, day, moment)
            if key in seen or key in existing:
                item["status"] = "skip"
                item["message"] = "duplicate — already in database"
                result["skipped"] += 1
                result["preview"].append(item)
                continue
            seen.add(key)
            if dry_run:
                result["created"] += 1
                result["preview"].append(item)
                continue
            entry = InwardEntry.objects.create(
                site=site, material=material, date=day, time=moment,
                qty=qty, received_from=source, created_by=user)
            existing.add(key)
            log_audit(user, AuditLog.Action.CREATE,
                      AuditLog.EntryType.INWARD, entry.pk,
                       entry_summary(entry, AuditLog.EntryType.INWARD)
                       + " (bulk import)")
            result["created"] += 1
            result["preview"].append(item)
    return result


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_cls):
        return value
    try:
        return date_cls.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _parse_time(value):
    if value is None or str(value).strip() == "":
        return time_cls(9, 0)
    if hasattr(value, "hour"):
        return time_cls(value.hour, value.minute, 0)
    try:
        parts = str(value).strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time_cls(hour, minute, 0)
    except (ValueError, IndexError):
        return None
