"""
Reports module — read-only analysis pages for both Admin and Staff.

Three reports: site-wise stock summary, material-wise consumption, monthly
activity — each viewable on screen and downloadable as .xlsx. Every balance
figure goes through entries.utils.balance_for — no report ever re-derives
the formula. All totals use DB-level aggregation (Sum/Count), never
Python-side loops. All filters ride on GET query params so report URLs are
shareable/bookmarkable.

Screen views and export views share the get_*_data() helpers below, so the
numbers on screen and in the file are always identical.
"""
import re
from io import BytesIO
from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.pdfgen import canvas as pdf_canvas

from entries.models import InwardEntry, OutwardEntry
from entries.utils import balance_for, balance_for_user, balances_for_site, fmt_qty
from materials.models import Material
from sites.models import Site

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
BOLD = Font(bold=True)


# --- Filter helpers ----------------------------------------------------------

def _selected_site(request):
    """Site from ?site=<id>, or None when missing/invalid (never crashes).

    Single-shop mode: when no ?site= is given and exactly one site exists
    (the normal nibba setup — everything under one roof), that site is
    used automatically so reports never dead-end on a picker.
    """
    raw = (request.GET.get("site") or "").strip()
    if raw.isdigit():
        return Site.objects.filter(pk=int(raw)).first()
    if Site.objects.count() == 1:
        return Site.objects.first()
    return None


def _selected_material(request):
    """Material from ?material=<id>, or None when missing/invalid."""
    raw = (request.GET.get("material") or "").strip()
    if not raw.isdigit():
        return None
    return (
        Material.objects
        .select_related("category", "sub_category")
        .filter(pk=int(raw))
        .first()
    )


def _parse_month_year(request, strict=False):
    """
    (month, year) from ?month=&year=. Non-strict (on-screen report) falls
    back to the current month/year on missing/invalid input. Strict (export)
    returns (None, None) instead, so the caller can redirect with a message.
    """
    today = timezone.localdate()
    try:
        month = int((request.GET.get("month") or "").strip())
        month = month if 1 <= month <= 12 else None
    except (ValueError, AttributeError):
        month = None
    try:
        year = int((request.GET.get("year") or "").strip())
        year = year if 2000 <= year <= 2100 else None
    except (ValueError, AttributeError):
        year = None
    if strict and (month is None or year is None):
        return None, None
    return month or today.month, year or today.year


MAX_RANGE_DAYS = 366
MAX_RANGE_ROWS = 5000


def _parse_date_range(request):
    """(from_date, to_date) from ?from=YYYY-MM-DD&to=YYYY-MM-DD, else
    (None, None). Partial/invalid/backwards input is ignored (the caller
    falls back to its default period) — never crashes, never half-applies.
    Ranges longer than MAX_RANGE_DAYS are clamped so one export cannot
    materialise unbounded history."""
    import datetime as _dt

    def _p(value):
        try:
            return _dt.date.fromisoformat((value or "").strip())
        except (ValueError, AttributeError):
            return None

    f, t = _p(request.GET.get("from")), _p(request.GET.get("to"))
    if f and t and f <= t:
        if (t - f).days > MAX_RANGE_DAYS:
            t = f + _dt.timedelta(days=MAX_RANGE_DAYS)
        return f, t
    return None, None


def _range_label(date_from, date_to):
    """'Sep 1 – Sep 10, 2026' for titles; filenames use _range_slug()."""
    fmt = lambda d: f"{d.strftime('%b')} {d.day}"
    return f"{fmt(date_from)} – {fmt(date_to)}, {date_to.year}"


def _range_slug(date_from, date_to):
    """'2026-09-01_to_2026-09-10' for filenames."""
    return f"{date_from.isoformat()}_to_{date_to.isoformat()}"


def _group_material_rows(material_rows):
    """
    Group [{"material": m, "balance": b}] into Category -> {loose, subs},
    mirroring the Material List page (sites/views.py): loose rows first,
    then sub-groups alphabetically, rows alphabetical by variant name.
    """
    categories = {}
    for row in material_rows:
        m = row["material"]
        # Mirror the site detail page: soft-deleted catalog rows (and rows
        # under a deleted category/sub-category) never render.
        if getattr(m, "is_deleted", False):
            continue
        if m.category.is_deleted:
            continue
        if m.sub_category is not None and m.sub_category.is_deleted:
            continue
        group = categories.setdefault(
            m.category, {"loose": [], "subs": {}}
        )
        if m.sub_category is None:
            group["loose"].append(row)
        else:
            group["subs"].setdefault(m.sub_category, []).append(row)
    category_groups = []
    for cat in sorted(categories, key=lambda c: c.name):
        group = categories[cat]
        group["loose"].sort(key=lambda r: r["material"].name.lower())
        subs = [
            {"sub": sub, "rows": sorted(rows, key=lambda r: r["material"].name.lower())}
            for sub, rows in sorted(
                group["subs"].items(), key=lambda kv: kv[0].name.lower()
            )
        ]
        total = len(group["loose"]) + sum(len(s["rows"]) for s in subs)
        category_groups.append(
            {"category": cat, "loose": group["loose"], "subs": subs, "total": total}
        )
    return category_groups


# --- Shared data builders (screen + export both call these) ------------------

def get_site_summary_data(site, user=None):
    """Flat rows in report order: category, sub_category (""/name), material, unit, balance."""
    materials = Material.objects.select_related(
        "category", "sub_category__category"
    ).order_by("category__name", "sub_category__name", "name")
    # Same bulk-balance rule as the site page: 4 queries for the whole
    # catalog instead of 4 per material.
    balances = balances_for_site(site, materials, user)
    groups = _group_material_rows(
        [{"material": m, "balance": balances[m.id]} for m in materials]
    )
    flat = []
    for g in groups:
        for row in g["loose"]:
            m = row["material"]
            flat.append({
                "category": g["category"].name, "sub_category": "",
                "material": m.display_name, "unit": m.unit,
                "balance": row["balance"],
                "reorder": m.reorder_point,
            })
        for sub in g["subs"]:
            for row in sub["rows"]:
                m = row["material"]
                flat.append({
                    "category": g["category"].name, "sub_category": sub["sub"].name,
                    "material": m.display_name, "unit": m.unit,
                    "balance": row["balance"],
                    "reorder": m.reorder_point,
                })
    inward_qs = InwardEntry.objects.filter(site=site)
    outward_qs = OutwardEntry.objects.filter(site=site)
    # NOTE (owner decision Sep 2026): reports show EVERY entry for every
    # role - no per-user scoping on reads (edit/delete stay own-only).
    return {
        "has_entries": inward_qs.exists() or outward_qs.exists(),
        "flat_rows": flat,
        "category_groups": groups,
    }


def get_consumption_data(material, site, user=None, date_from=None, date_to=None):
    """Totals + sub-location breakdown for a material, optionally scoped to
    a site and/or a date range (?from/?to)."""
    inward_qs = InwardEntry.objects.filter(material=material)
    outward_qs = OutwardEntry.objects.filter(material=material)
    if date_from and date_to:
        inward_qs = inward_qs.filter(date__range=(date_from, date_to))
        outward_qs = outward_qs.filter(date__range=(date_from, date_to))
    if site is not None:
        inward_qs = inward_qs.filter(site=site)
        outward_qs = outward_qs.filter(site=site)
    if site is not None:
        balance = balance_for_user(site, material, user)
    else:
        from entries.utils import balances_for_sites
        sites = list(Site.objects.all())
        balance = sum(
            balances_for_sites(sites, [material]).get(
                (s.id, material.id), 0) for s in sites) if sites else 0
    return {
        "has_entries": inward_qs.exists() or outward_qs.exists(),
        "total_inward": inward_qs.aggregate(t=Sum("qty"))["t"] or 0,
        "total_outward": outward_qs.aggregate(t=Sum("qty"))["t"] or 0,
        "balance": balance,
        "unit": material.unit,
        "breakdown": list(
            outward_qs.values(sub_location_name=F("sub_location__name")).annotate(total=Sum("qty")).order_by("-total")
        ),
    }


def get_monthly_data(year, month, site, user=None):
    """Counts, per-unit qty totals, and date-sorted entries for a month."""
    import calendar as _cal
    import datetime as _dt
    last = _cal.monthrange(year, month)[1]
    return get_range_data(
        _dt.date(year, month, 1), _dt.date(year, month, last), site, user)


def get_range_data(date_from, date_to, site, user=None):
    """Same shape as get_monthly_data, for an arbitrary ?from/?to span.

    Row lists are capped at MAX_RANGE_ROWS (totals still cover the full
    range) so one huge export cannot OOM the worker; callers show
    `truncated` when the cap bites.
    """
    inward_qs = InwardEntry.objects.filter(date__range=(date_from, date_to))
    outward_qs = OutwardEntry.objects.filter(date__range=(date_from, date_to))
    if site is not None:
        inward_qs = inward_qs.filter(site=site)
        outward_qs = outward_qs.filter(site=site)
    # Count in the DB first: hydrating every row just to count them is
    # what made big months slow. Capped fetch below keeps the newest rows.
    total_rows = inward_qs.count() + outward_qs.count()
    truncated = total_rows > MAX_RANGE_ROWS
    if truncated:
        in_list = list(inward_qs.select_related(
            "site", "material").order_by("-date", "-time", "-id")
            [:MAX_RANGE_ROWS])
        out_list = list(outward_qs.select_related(
            "site", "material", "sub_location").order_by(
            "-date", "-time", "-id")[:MAX_RANGE_ROWS])
    else:
        in_list = list(inward_qs.select_related("site", "material"))
        out_list = list(outward_qs.select_related(
            "site", "material", "sub_location"))
    # Display stays oldest-first, but a truncated range keeps the NEWEST
    # rows (what the owner actually wants to see), not the oldest.
    entries = sorted(
        chain(
            [("in", e) for e in in_list],
            [("out", e) for e in out_list],
        ),
        key=lambda pair: (pair[1].date, pair[1].time),
        reverse=truncated,
    )[:MAX_RANGE_ROWS]
    if truncated:
        entries = entries[::-1]
    return {
        "inward_count": inward_qs.aggregate(c=Count("id"))["c"],
        "outward_count": outward_qs.aggregate(c=Count("id"))["c"],
        "inward_by_unit": list(
            inward_qs.values("material__unit").annotate(total=Sum("qty"))
            .order_by("material__unit")
        ),
        "outward_by_unit": list(
            outward_qs.values("material__unit").annotate(total=Sum("qty"))
            .order_by("material__unit")
        ),
        "has_entries": inward_qs.exists() or outward_qs.exists(),
        "entries": entries[:MAX_RANGE_ROWS],
        "truncated": truncated,
    }


# --- Excel helpers -----------------------------------------------------------

def _safe_name(text):
    """Sanitize for filenames: 'Vidarbha Park - 1' -> 'Vidarbha_Park_1'."""
    return re.sub(r"[^\w]+", "_", str(text)).strip("_")


def _x(value):
    """Excel formula-injection guard: a cell whose text starts with = + - @
    (typed by anyone into received_from / sub-location / site / material
    names) would EXECUTE as a formula when the .xlsx opens. A leading
    apostrophe forces Excel to treat it as plain text (invisible to users).
    Apply to every user-controlled string written to a worksheet."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _today_str():
    return timezone.localdate().strftime("%Y-%m-%d")


def _header_row(ws, row_idx, values):
    for col_idx, value in enumerate(values, start=1):
        ws.cell(row=row_idx, column=col_idx, value=value).font = BOLD


def _set_widths(ws, widths):
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width


def _content_disposition(filename):
    """ASCII-safe filename + RFC 5987 filename* so non-ASCII site/material
    names download correctly instead of mangling."""
    from urllib.parse import quote
    ascii_name = filename.encode("ascii", "ignore").decode() or "report"
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


def _xlsx_response(wb, filename):
    buf = BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = _content_disposition(filename)
    return response


# --- PDF helpers (reportlab; same data as the .xlsx exports) -----------------

PDF_CONTENT_TYPE = "application/pdf"


def _pdf_escape(text):
    """Escape XML markup chars — reportlab Paragraphs parse a mini-XML dialect."""
    from xml.sax.saxutils import escape
    return escape(str(text))


ACCENT_HEX = "#4A6FA5"  # app accent, muted enough for print
CHARCOAL_HEX = "#1A1A1A"
MUTED_HEX = "#6B7280"
HAIRLINE_HEX = "#E5E7EB"
HEADER_BG_HEX = "#F3F4F6"
ZEBRA_HEX = "#FAFAFA"


def _generated_str():
    """E.g. 'Generated on: 08 Sep 2026, 5:30 PM'."""
    now = timezone.localtime()
    return (
        f"Generated on: {now.strftime('%d %b %Y')}, "
        f"{now.strftime('%I:%M %p').lstrip('0')}"
    )


class _NumberedCanvas(pdf_canvas.Canvas):
    """ReportLab canvas that stamps 'Page X of Y' + footer rule on save."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        # Buffer the page state WITHOUT emitting: emitting here (via
        # super().showPage()) duplicates every page, because save() below
        # replays and emits each buffered page exactly once.
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for page_num, state in enumerate(self._saved_pages, start=1):
            self.__dict__.update(state)
            self._draw_footer(page_num, total)
            super().showPage()
        super().save()

    def _draw_footer(self, page_num, total):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm

        self.saveState()
        page_w = getattr(self, "_pagesize", A4)[0]
        y = 12 * mm
        self.setStrokeColor(colors.HexColor(HAIRLINE_HEX))
        self.setLineWidth(0.5)
        self.line(15 * mm, y + 4 * mm, page_w - 15 * mm, y + 4 * mm)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor(MUTED_HEX))
        self.drawString(15 * mm, y, "GENERATED BY VIDARBHA STOCK APP")
        self.drawRightString(
            page_w - 15 * mm, y, f"Page {page_num} of {total}")
        self.restoreState()


def _build_pdf(title, subtitle_lines, headers, rows, landscape=False,
               summary_blocks=None, numeric_cols=()):
    """
    Return professional PDF bytes: brand header, title, filter meta,
    optional summary box, one data table (header repeated every page,
    rows never split), footer with page numbers on every page.

    summary_blocks: [(label, value)] shown as a shaded box above the table.
    numeric_cols: column indexes right-aligned (quantities/totals).
    `rows` holds plain strings already (callers format via fmt_qty).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape as landscape_size
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    page_size = landscape_size(A4) if landscape else A4
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=22 * mm,
    )
    base = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "Brand", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=20, leading=24, textColor=colors.HexColor(ACCENT_HEX),
    )
    title_style = ParagraphStyle(
        "ReportTitle", parent=base["Normal"], fontName="Helvetica",
        fontSize=14, leading=18, textColor=colors.HexColor(CHARCOAL_HEX),
        spaceAfter=2 * mm,
    )
    meta_style = ParagraphStyle(
        "Meta", parent=base["Normal"], fontName="Helvetica",
        fontSize=9, leading=12, textColor=colors.HexColor(MUTED_HEX),
    )
    cell_style = ParagraphStyle(
        "Cell", parent=base["Normal"], fontName="Helvetica",
        fontSize=9, leading=12, textColor=colors.HexColor(CHARCOAL_HEX),
    )
    cell_bold = ParagraphStyle(
        "CellBold", parent=cell_style, fontName="Helvetica-Bold",
    )
    head_style = ParagraphStyle(
        "Head", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor(MUTED_HEX),
    )

    story = []
    band = Table([[""]], colWidths=[page_size[0] - 40 * mm])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(ACCENT_HEX)),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
    ]))
    story.append(band)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(_pdf_escape("nibba"), brand_style))
    story.append(Paragraph(_pdf_escape(title), title_style))
    for line in subtitle_lines:
        story.append(Paragraph(_pdf_escape(line), meta_style))
    story.append(Paragraph(_pdf_escape(_generated_str()), meta_style))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor(HAIRLINE_HEX)))
    story.append(Spacer(1, 6 * mm))

    if summary_blocks:
        label_style = ParagraphStyle(
            "SumLabel", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=11,
            textColor=colors.HexColor(MUTED_HEX),
        )
        value_style = ParagraphStyle(
            "SumValue", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=14, leading=17,
            textColor=colors.HexColor(CHARCOAL_HEX), alignment=2,
        )
        summary_data = [
            [Paragraph(_pdf_escape(label).upper(), label_style),
             Paragraph(_pdf_escape(value), value_style)]
            for label, value in summary_blocks
        ]
        summary = Table(summary_data, colWidths=[70 * mm, None])
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1),
             colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5,
             colors.HexColor(HAIRLINE_HEX)),
            ("LINEBEFORE", (0, 0), (0, -1), 3,
             colors.HexColor(ACCENT_HEX)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        story.append(summary)
        story.append(Spacer(1, 6 * mm))

    data = [[Paragraph(_pdf_escape(h), head_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(_pdf_escape(c), cell_style) for c in row])
    table = Table(data, repeatRows=1)
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(HEADER_BG_HEX)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(MUTED_HEX)),
        ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor(ACCENT_HEX)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(HAIRLINE_HEX)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]
    for col in numeric_cols:
        table_style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    table.setStyle(TableStyle(table_style))
    story.append(table)
    if not rows:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("(no rows)", meta_style))
    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()


def _pdf_response(pdf_bytes, filename):
    response = HttpResponse(pdf_bytes, content_type=PDF_CONTENT_TYPE)
    response["Content-Disposition"] = _content_disposition(filename)
    return response


def _num(value):
    """Excel cell number: int when whole (160 not 160.0), else float."""
    f = float(value or 0)
    return int(f) if f.is_integer() else f


def _log_export(request, summary, entry_id=0):
    """Record a report download in the activity log (who took what data out).
    Exports are logged for every role — the point is data oversight."""
    from entries.models import AuditLog
    from entries.views import log_audit
    if not request.user.is_authenticated:
        return
    log_audit(request.user, AuditLog.Action.EXPORT,
              AuditLog.EntryType.REPORT, entry_id, summary)


# --- Landing -----------------------------------------------------------------

class ReportsLandingView(LoginRequiredMixin, TemplateView):
    template_name = "reports/landing.html"


# --- Report 1: Site-wise Stock Summary ---------------------------------------

class SiteSummaryView(LoginRequiredMixin, TemplateView):
    template_name = "reports/site_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sites"] = Site.objects.order_by("name")
        site = _selected_site(self.request)
        ctx["selected_site"] = site
        if site is None:
            return ctx
        data = get_site_summary_data(site, self.request.user)
        ctx["has_entries"] = data["has_entries"]
        ctx["category_groups"] = data["category_groups"]
        return ctx


class SiteSummaryExportView(LoginRequiredMixin, View):
    def get(self, request):
        site = _selected_site(request)
        if site is None:
            messages.warning(request, "Please select a shop first.")
            return redirect("reports:site_summary")
        data = get_site_summary_data(site, self.request.user)
        wb = Workbook()
        ws = wb.active
        ws.title = "Stock Summary"
        _header_row(ws, 1, ["Category", "Sub-Category", "Material", "Unit", "Current Balance"])
        row_idx = 2
        for row in data["flat_rows"]:
            ws.cell(row=row_idx, column=1, value=_x(row["category"]))
            ws.cell(row=row_idx, column=2, value=_x(row["sub_category"]))
            ws.cell(row=row_idx, column=3, value=_x(row["material"]))
            ws.cell(row=row_idx, column=4, value=_x(row["unit"]))
            ws.cell(row=row_idx, column=5, value=_num(row["balance"]))
            row_idx += 1
        _set_widths(ws, [24, 20, 28, 10, 16])
        filename = f"Stock_Summary_{_safe_name(site.name)}_{_today_str()}.xlsx"
        _log_export(request,
                    f"Exported Stock Summary (Excel) for {site.name}.",
                    entry_id=site.pk)
        return _xlsx_response(wb, filename)


class SiteSummaryExportPDFView(LoginRequiredMixin, View):
    """Same data as the Excel export, as a printable PDF table."""

    def get(self, request):
        site = _selected_site(request)
        if site is None:
            messages.warning(request, "Please select a shop first.")
            return redirect("reports:site_summary")
        data = get_site_summary_data(site, self.request.user)
        rows = [
            [r["category"], r["sub_category"] or "—", r["material"],
             r["unit"], fmt_qty(r["balance"])]
            for r in data["flat_rows"]
        ]
        pdf = _build_pdf(
            "Stock Summary",
            [f"Shop: {site.name}"],
            ["Category", "Sub-Category", "Material", "Unit", "Current Balance"],
            rows,
            numeric_cols=(4,),
        )
        filename = f"Stock_Summary_{_safe_name(site.name)}_{_today_str()}.pdf"
        _log_export(request,
                    f"Exported Stock Summary (PDF) for {site.name}.",
                    entry_id=site.pk)
        return _pdf_response(pdf, filename)


# --- Report 2: Material-wise Consumption -------------------------------------

class MaterialConsumptionView(LoginRequiredMixin, TemplateView):
    template_name = "reports/material_consumption.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        materials = list(Material.objects.select_related(
            "category", "sub_category__category"
        ).order_by("category__name", "sub_category__name", "name"))
        # Reuse the grouping for optgroups in the material selector.
        ctx["category_groups"] = _group_material_rows(
            [{"material": m, "balance": None} for m in materials]
        )
        ctx["sites"] = Site.objects.order_by("name")
        material = _selected_material(self.request)
        site = _selected_site(self.request)
        ctx["selected_material"] = material
        ctx["selected_site"] = site
        date_from, date_to = _parse_date_range(self.request)
        ctx["date_from"] = date_from.isoformat() if date_from else ""
        ctx["date_to"] = date_to.isoformat() if date_to else ""
        ctx["range_label"] = _range_label(date_from, date_to) if date_from else ""
        if material is None:
            return ctx
        data = get_consumption_data(
            material, site, self.request.user, date_from, date_to)
        ctx.update(
            has_entries=data["has_entries"],
            total_inward=data["total_inward"],
            total_outward=data["total_outward"],
            balance=data["balance"],
            unit=data["unit"],
            sub_location_breakdown=data["breakdown"],
        )
        return ctx


class MaterialConsumptionExportView(LoginRequiredMixin, View):
    def get(self, request):
        material = _selected_material(request)
        if material is None:
            messages.warning(request, "Please select a material first.")
            return redirect("reports:material_consumption")
        site = _selected_site(request)
        date_from, date_to = _parse_date_range(request)
        data = get_consumption_data(
            material, site, request.user, date_from, date_to)
        scope = site.name if site else "All stock"
        if date_from:
            scope += f" · {_range_label(date_from, date_to)}"
        wb = Workbook()
        ws = wb.active
        ws.title = "Consumption"
        ws.cell(row=1, column=1, value="Material").font = BOLD
        ws.cell(row=1, column=2, value=_x(material.display_name))
        ws.cell(row=2, column=1, value="Scope").font = BOLD
        ws.cell(row=2, column=2, value=_x(scope))
        ws.cell(row=3, column=1, value=_x(f"Total Inward ({material.unit})")).font = BOLD
        ws.cell(row=3, column=2, value=_num(data["total_inward"]))
        ws.cell(row=4, column=1, value=_x(f"Total Used ({material.unit})")).font = BOLD
        ws.cell(row=4, column=2, value=_num(data["total_outward"]))
        ws.cell(row=5, column=1, value=_x(f"Current Balance ({material.unit})")).font = BOLD
        ws.cell(row=5, column=2, value=_num(data["balance"]))
        _header_row(ws, 7, ["Used At (Sub-location)", "Quantity Used"])
        row_idx = 8
        for row in data["breakdown"]:
            ws.cell(row=row_idx, column=1, value=_x(row["sub_location_name"]) or "—")
            ws.cell(row=row_idx, column=2, value=_num(row["total"]))
            row_idx += 1
        _set_widths(ws, [30, 20])
        slug = f"_{_range_slug(date_from, date_to)}" if date_from else ""
        filename = (
            f"Material_Consumption_{_safe_name(material.display_name)}"
            f"{slug}_{_today_str()}.xlsx"
        )
        _log_export(request,
                    f"Exported Material Consumption (Excel) for "
                    f"{material.display_name} ({scope}).",
                    entry_id=material.pk)
        return _xlsx_response(wb, filename)


class MaterialConsumptionExportPDFView(LoginRequiredMixin, View):
    """Same data as the Excel export, as a printable PDF."""

    def get(self, request):
        material = _selected_material(request)
        if material is None:
            messages.warning(request, "Please select a material first.")
            return redirect("reports:material_consumption")
        site = _selected_site(request)
        date_from, date_to = _parse_date_range(request)
        data = get_consumption_data(
            material, site, request.user, date_from, date_to)
        rows = [
            [r["sub_location_name"] or "—", fmt_qty(r["total"])]
            for r in data["breakdown"]
        ]
        subtitles = [
            f"Material: {material.display_name}",
            f"Scope: {site.name if site else 'All stock'}",
        ]
        if date_from:
            subtitles.append(f"Period: {_range_label(date_from, date_to)}")
        pdf = _build_pdf(
            "Material Consumption",
            subtitles,
            ["Used At (Sub-location)", "Quantity Used"],
            rows,
            summary_blocks=[
                (f"Total Inward ({material.unit})",
                 fmt_qty(data['total_inward'])),
                (f"Total Used ({material.unit})",
                 fmt_qty(data['total_outward'])),
                (f"Current Balance ({material.unit})",
                 fmt_qty(data['balance'])),
            ],
            numeric_cols=(1,),
        )
        slug = f"_{_range_slug(date_from, date_to)}" if date_from else ""
        filename = (
            f"Material_Consumption_{_safe_name(material.display_name)}"
            f"{slug}_{_today_str()}.pdf"
        )
        _log_export(request,
                    f"Exported Material Consumption (PDF) for "
                    f"{material.display_name} "
                    f"({site.name if site else 'All stock'}).",
                    entry_id=material.pk)
        return _pdf_response(pdf, filename)


# --- Report 3: Monthly Report ------------------------------------------------

MONTHS = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
]
MONTH_NAMES = dict(MONTHS)


class MonthlyReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/monthly.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month, year = _parse_month_year(self.request)
        ctx["months"] = MONTHS
        ctx["years"] = list(range(today.year - 2, today.year + 2))
        ctx["selected_month"] = month
        ctx["selected_year"] = year
        ctx["sites"] = Site.objects.order_by("name")
        site = _selected_site(self.request)
        ctx["selected_site"] = site
        # Custom range (?from/?to) overrides the month picker when both
        # dates are valid; anything else falls back to the month.
        date_from, date_to = _parse_date_range(self.request)
        ctx["date_from"] = date_from.isoformat() if date_from else ""
        ctx["date_to"] = date_to.isoformat() if date_to else ""
        if date_from:
            ctx["period_label"] = _range_label(date_from, date_to)
            data = get_range_data(
                date_from, date_to, site, self.request.user)
        else:
            ctx["period_label"] = (
                f"{MONTH_NAMES[month]} {year}")
            data = get_monthly_data(year, month, site, self.request.user)
        # A busy month can hold thousands of rows: rendering them all
        # into one 10 MB page is what made this report slow. Paginate the
        # on-screen table (100/page); exports still use the capped set.
        from django.core.paginator import Paginator
        page = Paginator(data["entries"], 100).get_page(
            self.request.GET.get("page"))
        ctx.update(
            inward_count=data["inward_count"],
            outward_count=data["outward_count"],
            inward_by_unit=data["inward_by_unit"],
            outward_by_unit=data["outward_by_unit"],
            has_entries=data["has_entries"],
            entries=page.object_list,
            entries_page=page,
            truncated=data.get("truncated", False),
        )
        return ctx


class MonthlyReportExportView(LoginRequiredMixin, View):
    def get(self, request):
        date_from, date_to = _parse_date_range(request)
        site = _selected_site(request)
        if date_from:
            data = get_range_data(date_from, date_to, site, request.user)
            period = _range_label(date_from, date_to)
            slug = _range_slug(date_from, date_to)
        else:
            month, year = _parse_month_year(request, strict=True)
            if month is None or year is None:
                messages.warning(request, "Please select a valid month and year first.")
                return redirect("reports:monthly")
            data = get_monthly_data(year, month, site, request.user)
            period = f"{MONTH_NAMES[month]} {year}"
            slug = f"{MONTH_NAMES[month]}_{year}"
        wb = Workbook()
        ws = wb.active
        ws.title = period[:31]
        ws.cell(row=1, column=1, value="Period").font = BOLD
        ws.cell(row=1, column=2, value=_x(period))
        ws.cell(row=2, column=1, value="Scope").font = BOLD
        ws.cell(row=2, column=2, value=_x(site.name) if site else "All stock")
        ws.cell(row=3, column=1, value="Total Inward Entries").font = BOLD
        ws.cell(row=3, column=2, value=data["inward_count"])
        ws.cell(row=4, column=1, value="Total Outward Entries").font = BOLD
        ws.cell(row=4, column=2, value=data["outward_count"])
        row_idx = 5
        for row in data["inward_by_unit"]:
            ws.cell(row=row_idx, column=1,
                    value=_x(f"Inward Quantity ({row['material__unit']})")).font = BOLD
            ws.cell(row=row_idx, column=2, value=_num(row["total"]))
            row_idx += 1
        for row in data["outward_by_unit"]:
            ws.cell(row=row_idx, column=1,
                    value=_x(f"Outward Quantity ({row['material__unit']})")).font = BOLD
            ws.cell(row=row_idx, column=2, value=_num(row["total"]))
            row_idx += 1
        row_idx += 1
        _header_row(ws, row_idx,
                    ["Date", "Time", "Type", "Material", "Qty", "Unit", "Notes"])
        row_idx += 1
        for kind, e in data["entries"]:
            ws.cell(row=row_idx, column=1, value=e.date.strftime("%Y-%m-%d"))
            ws.cell(row=row_idx, column=2, value=e.time.strftime("%I:%M %p").lstrip("0"))
            ws.cell(row=row_idx, column=3,
                    value="Inward" if kind == "in" else "Outward")
            ws.cell(row=row_idx, column=4, value=_x(e.material.display_name))
            ws.cell(row=row_idx, column=5, value=_num(e.qty))
            ws.cell(row=row_idx, column=6, value=_x(e.material.unit))
            ws.cell(row=row_idx, column=7,
                    value=_x(e.received_from) if kind == "in" else (_x(e.sub_location.name) if e.sub_location else ""))
            row_idx += 1
        _set_widths(ws, [12, 10, 10, 24, 10, 10, 30])
        filename = (f"Monthly_Report_{slug}"
                    f"_{_today_str()}.xlsx")
        _log_export(request,
                    f"Exported Monthly Report (Excel) for "
                    f"{period} "
                    f"({site.name if site else 'All stock'}).",
                    entry_id=site.pk if site else 0)
        return _xlsx_response(wb, filename)


class MonthlyReportExportPDFView(LoginRequiredMixin, View):
    """Same data as the Excel export, as a printable PDF (landscape)."""

    def get(self, request):
        date_from, date_to = _parse_date_range(request)
        site = _selected_site(request)
        if date_from:
            data = get_range_data(date_from, date_to, site, request.user)
            period = _range_label(date_from, date_to)
            slug = _range_slug(date_from, date_to)
        else:
            month, year = _parse_month_year(request, strict=True)
            if month is None or year is None:
                messages.warning(request, "Please select a valid month and year first.")
                return redirect("reports:monthly")
            data = get_monthly_data(year, month, site, request.user)
            period = f"{MONTH_NAMES[month]} {year}"
            slug = f"{MONTH_NAMES[month]}_{year}"
        rows = []
        for kind, e in data["entries"]:
            rows.append([
                e.date.strftime("%Y-%m-%d"),
                e.time.strftime("%I:%M %p").lstrip("0"),
                "Inward" if kind == "in" else "Outward",
                e.material.display_name,
                fmt_qty(e.qty),
                e.material.unit,
                e.received_from if kind == "in"
                else (e.sub_location.name if e.sub_location else ""),
            ])
        summary = [
            ("Total Inward Entries", str(data['inward_count'])),
            ("Total Outward Entries", str(data['outward_count'])),
        ]
        for row in data["inward_by_unit"]:
            summary.append(
                (f"Inward Quantity ({row['material__unit']})",
                 fmt_qty(row['total'])))
        for row in data["outward_by_unit"]:
            summary.append(
                (f"Outward Quantity ({row['material__unit']})",
                 fmt_qty(row['total'])))
        pdf = _build_pdf(
            "Monthly Report",
            [
                f"Period: {period}",
            f"Scope: {site.name if site else 'All stock'}",
            ],
            ["Date", "Time", "Type", "Material", "Qty", "Unit", "Notes"],
            rows,
            landscape=True,
            summary_blocks=summary,
            numeric_cols=(4,),
        )
        filename = (f"Monthly_Report_{slug}"
                    f"_{_today_str()}.pdf")
        _log_export(request,
                    f"Exported Monthly Report (PDF) for "
                    f"{period} "
                    f"({site.name if site else 'All stock'}).",
                    entry_id=site.pk if site else 0)
        return _pdf_response(pdf, filename)
