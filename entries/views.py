from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

import logging

from materials.models import Material
from sites.models import Site

from .forms import InwardEntryForm, OutwardEntryForm, PurchaseForm, SaleForm, SubLocationForm, SubLocationAllocationForm
from .models import AuditLog, InwardEntry, OutwardEntry, SubLocation, SubLocationAllocation
from .utils import balance_for, fmt_qty
from core.utils import (
    _sees_only_own_entries, _user_can_edit, _user_can_view_activity,
    _user_is_admin,
)

logger = logging.getLogger(__name__)

SAVE_FAILED_MESSAGE = (
    "Saving failed, so this entry was NOT saved (nothing half-saved). "
    "Please try again."
)


def _guarded_save(form, view, save):
    """Run a Create/UpdateView save, turning a mid-save failure into a
    friendly form error instead of a 500 crash page.

    A failure means NO row was written — safe to just re-render the bound
    form. The exception is still logged server-side for the admin. `save`
    is an explicit unbound call (e.g. ``lambda:
    CreateView.form_valid(self, form)``) to avoid super() magic inside
    a helper.
    """
    try:
        return save()
    except Exception:
        logger.exception("Entry save failed")
        form.add_error(None, SAVE_FAILED_MESSAGE)
        return view.form_invalid(form)


# Tabs available on the Material Detail page
TABS = ("inward", "outward", "balance")

# Ledger pagination: rows per tab page (?ipage=/?opage=/?bpage=). The Balance
# tab merges both entry types in Python, so its source is capped at
# RECENT_CAP rows (latest first) to bound memory; the UI says so when hit.
ENTRIES_PAGE_SIZE = 20
RECENT_PAGE_SIZE = 20
RECENT_CAP = 2000


class EntryWriterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Staff, managers and admins can write entries/materials (managers hold
    admin powers everywhere except the activity/audit pages)."""
    def test_func(self):
        return _user_can_edit(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def get_queryset(self):
        # Staff may touch only their own entries plus legacy unattributed
        # rows (created_by NULL, otherwise frozen forever). Admins see all.
        # Harmless on CreateViews (they never use get_queryset); enforced on
        # every Update/Delete view through this mixin (tampered URLs 404).
        qs = super().get_queryset()
        if _sees_only_own_entries(self.request.user):
            qs = qs.filter(
                Q(created_by=self.request.user) | Q(created_by__isnull=True)
            )
        return qs


# --- Material Detail (per site) --------------------------------------------

class MaterialDetailView(LoginRequiredMixin, DetailView):
    """
    Detail page for a (site, material) combination. Renders 3 tabs based on
    the `?tab=` query param: inward / outward / balance.

    URL: /sites/<site_id>/materials/<material_id>/
    The route is namespaced under 'entries:detail' even though the view lives
    here, because conceptually the page is the entry ledger for a material.
    """
    template_name = "entries/material_detail.html"
    context_object_name = "material"

    def dispatch(self, request, *args, **kwargs):
        # Validate FKs eagerly so the template can assume they exist.
        self.site = get_object_or_404(Site, pk=kwargs["site_id"])
        self.material = get_object_or_404(Material, pk=kwargs["material_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.material

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.site
        ctx["material"] = self.material
        ctx["can_edit"] = _user_can_edit(self.request.user)
        # Per-row edit ownership: staff see edit/delete only on their own
        # rows (+ legacy NULL rows); admins/managers on all rows. The ledger
        # itself stays global — this only hides buttons that would 404 via
        # EntryWriterRequiredMixin (tampered URLs still 404 server-side).
        # Computed in Python (not template `{% if %}` — Django templates
        # reject parentheses) as `e.can_edit_row` on each listed entry.
        _me = self.request.user
        _can_all = _user_is_admin(_me)
        ctx["can_edit_all"] = _can_all

        def _mark(rows):
            rows = list(rows)
            for e in rows:
                e.can_edit_row = bool(
                    ctx["can_edit"] and (
                        _can_all
                        or e.created_by_id == _me.pk
                        or e.created_by_id is None
                    )
                )
            return rows

        # Default tab to "inward" if invalid or missing
        tab = self.request.GET.get("tab", "inward")
        if tab not in TABS:
            tab = "inward"
        ctx["active_tab"] = tab

        # Date filtering: TODAY by default (owner decision Sep 2026 — the
        # ledger opens on same-day entries only); ?all=1 lifts the filter to
        # full history. Explicit ?date_from/?date_to pick any range. Invalid
        # input falls back to today — never crashes, never half-applies.
        show_all = self.request.GET.get("all") == "1"
        _today = timezone.localdate()
        raw_from = (self.request.GET.get("date_from") or "").strip()
        raw_to = (self.request.GET.get("date_to") or "").strip()
        ctx["show_all"] = show_all
        date_filter = {}
        if show_all:
            date_from = date_to = ""
        else:
            if not raw_from and not raw_to:
                raw_from = raw_to = _today.isoformat()
            try:
                _df = (timezone.datetime.strptime(
                    raw_from, "%Y-%m-%d").date() if raw_from else None)
            except ValueError:
                _df = None
            try:
                _dt = (timezone.datetime.strptime(
                    raw_to, "%Y-%m-%d").date() if raw_to else None)
            except ValueError:
                _dt = None
            if _df is None and _dt is None:
                _df = _dt = _today
            if _df is not None:
                date_filter["date__gte"] = _df
            if _dt is not None:
                date_filter["date__lte"] = _dt
            date_from = _df.isoformat() if _df else ""
            date_to = _dt.isoformat() if _dt else ""

        # NOTE (owner decision Sep 2026): every role sees EVERY entry and the
        # TRUE balance (live app - staff must see co-workers rows to avoid
        # mis-entry). Per-user scoping applies ONLY to edit/delete ownership
        # (EntryWriterRequiredMixin above), never to reads.

        # Inward list (latest first).
        inward_qs = (
            InwardEntry.objects
            .filter(site=self.site, material=self.material)
            .order_by("-date", "-time")
        )
        # (No date_filter here — Inward/Outward tabs show full history.)

        # Outward list. select_related avoids an N+1 on the
        # sub-location name shown per row in the template.
        # NOTE: Inward/Outward tabs are deliberately UNFILTERED plain
        # history (recent-first, 20/page) — no date picker, no show-all.
        # The date filter below applies to the Balance tab only.
        outward_qs = (
            OutwardEntry.objects
            .filter(site=self.site, material=self.material)
            .select_related("sub_location", "inward_entry")
            .order_by("-date", "-time")
        )

        # Lifetime totals (Inward/Outward tab headers) + true stock.
        total_inward = inward_qs.aggregate(t=Sum("qty"))["t"] or 0
        total_outward = outward_qs.aggregate(t=Sum("qty"))["t"] or 0
        # True site stock for every role (see note on own_only above).
        balance = balance_for(self.site, self.material)

        from django.core.paginator import Paginator
        # Paginated ledger: only the active tab's rows are fetched (the other
        # tabs render nothing, so their querysets stay unevaluated).
        # get_page() never crashes on tampered ?ipage=/?opage= values.
        ctx["inward_entries"] = []
        ctx["outward_entries"] = []
        ctx["inward_page"] = None
        ctx["outward_page"] = None
        ctx["last_inward"] = None
        ctx["last_outward"] = None
        if tab == "inward":
            inward_page = Paginator(
                inward_qs, ENTRIES_PAGE_SIZE).get_page(
                self.request.GET.get("ipage"))
            ctx["inward_entries"] = _mark(inward_page.object_list)
            ctx["inward_page"] = inward_page
            # One-tap "Repeat last" (unfiltered latest, any role's row).
            ctx["last_inward"] = InwardEntry.objects.filter(
                site=self.site, material=self.material).order_by(
                "-date", "-time", "-id").first()
        elif tab == "outward":
            outward_page = Paginator(
                outward_qs, ENTRIES_PAGE_SIZE).get_page(
                self.request.GET.get("opage"))
            ctx["outward_entries"] = _mark(outward_page.object_list)
            ctx["outward_page"] = outward_page
            ctx["last_outward"] = OutwardEntry.objects.filter(
                site=self.site, material=self.material).order_by(
                "-date", "-time", "-id").first()
        ctx["total_inward"] = total_inward
        ctx["total_outward"] = total_outward
        ctx["balance"] = balance
        ctx["unit"] = self.material.unit
        ctx["date_from"] = date_from
        ctx["date_to"] = date_to

        # Quick-action shortcut: shown only right after an inward entry was
        # saved (redirect lands here with ?tab=inward&just_saved=1). Navigating
        # away or clicking Done drops the flag, so this never blocks anyone.
        ctx["show_outward_shortcut"] = (
            tab == "inward" and self.request.GET.get("just_saved") == "1"
        )
        # Save-confirmation modal: shown right after an inward OR outward
        # create (both redirect with just_saved=1). Dismissed with OK only.
        ctx["show_save_modal"] = self.request.GET.get("just_saved") == "1"

        # Balance tab: date-scoped totals + full activity history (both
        # entry types merged newest-first). Capped at RECENT_CAP rows to
        # bound memory; the template says so when hit.
        # In show-all mode the history pages (?bpage=); in date mode the
        # whole range renders at once (usually tens of rows).
        from django.core.paginator import Paginator as _Paginator
        from itertools import chain
        ctx["recent_changes"] = []
        ctx["recent_page"] = None
        ctx["recent_truncated"] = False
        if tab == "balance":
            _in_range = (inward_qs.filter(**date_filter)
                         if date_filter else inward_qs)
            _out_range = (outward_qs.filter(**date_filter)
                          if date_filter else outward_qs)
            ctx["total_inward"] = (
                _in_range.aggregate(t=Sum("qty"))["t"] or 0)
            ctx["total_outward"] = (
                _out_range.aggregate(t=Sum("qty"))["t"] or 0)
            _in_vals = list(_in_range.values_list(
                "date", "time", "qty")[:RECENT_CAP + 1])
            _out_vals = list(_out_range.values_list(
                "date", "time", "qty")[:RECENT_CAP + 1])
            _truncated = (len(_in_vals) > RECENT_CAP
                          or len(_out_vals) > RECENT_CAP)
            combined = sorted(
                chain(
                    [(d, t, "in", q) for d, t, q in _in_vals[:RECENT_CAP]],
                    [(d, t, "out", q) for d, t, q in _out_vals[:RECENT_CAP]],
                ),
                key=lambda r: (r[0], r[1]),
                reverse=True,
            )
            if show_all:
                # Full history can be 1000s of rows — page it.
                recent_page = _Paginator(
                    combined, RECENT_PAGE_SIZE).get_page(
                    self.request.GET.get("bpage"))
                ctx["recent_changes"] = list(recent_page.object_list)
                ctx["recent_page"] = recent_page
            else:
                # Today / picked date(s): usually tens of rows — show them
                # ALL at once (10 ho ya 30), no Next-button hunting.
                ctx["recent_changes"] = combined
                ctx["recent_page"] = None
            ctx["recent_truncated"] = _truncated

        return ctx


# --- Inward create (per site + material) -----------------------------------

class InwardEntryCreateView(EntryWriterRequiredMixin, CreateView):
    """
    Add an inward entry for a specific (site, material). The site and material
    come from the URL, not the form — users only fill date/time/qty/source.
    """
    model = InwardEntry
    form_class = InwardEntryForm
    template_name = "entries/entry_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_id"])
        self.material = get_object_or_404(Material, pk=kwargs["material_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        kwargs["material"] = self.material
        return kwargs

    def get_initial(self):
        # Smart defaults: today + now, plus one-tap repeat via ?repeat=<pk>.
        # Repeat source is constrained to this site+material (any role's
        # rows - all entries are visible to everyone), so a tampered pk
        # silently falls back to a blank form.
        initial = super().get_initial()
        repeat_pk = self.request.GET.get("repeat")
        if repeat_pk:
            try:
                repeat_qs = InwardEntry.objects.filter(
                    pk=repeat_pk, site=self.site, material=self.material
                )
                src = repeat_qs.first()
            except ValueError:
                src = None
            if src is not None:
                initial["qty"] = src.qty
                initial["received_from"] = src.received_from
        initial.setdefault("date", timezone.localdate())
        initial.setdefault(
            "time", timezone.localtime().strftime("%H:%M")
        )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.site
        ctx["material"] = self.material
        ctx["form_title"] = "Record Inward Entry"
        ctx["submit_label"] = "Save Inward Entry"
        ctx["qty_label"] = "Quantity Received"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=inward"
        if not ctx.get("form").initial.get("date"):
            ctx["form"].initial["date"] = timezone.localdate()
        return ctx

    def form_valid(self, form):
        form.instance.site = self.site
        form.instance.material = self.material
        form.instance.created_by = self.request.user
        # The save runs inside _guarded_save so a mid-save failure
        # re-renders the form instead of 500ing. Success message only
        # after the row actually exists.
        # Atomic: a concurrent same-minute duplicate raises IntegrityError
        # (DB unique constraint) instead of half-saving — surfaced as a
        # friendly form error below, never a 500.
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                response = _guarded_save(
                    form, self, lambda: CreateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(
                None,
                "An entry for this site, material, date and time was just "
                "saved by someone else. Change the time slightly and try again.",
            )
            return self.form_invalid(form)
        if response.status_code != 302:
            # Guard re-rendered the form with an error.
            return response
        messages.success(
            self.request,
            f"Inward entry saved: {fmt_qty(form.instance.qty)} {self.material.unit} on "
            f"{form.instance.date.strftime('%b %d, %Y')} at {form.instance.time.strftime('%I:%M %p').lstrip('0')}.",
        )
        log_audit(self.request.user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.INWARD, self.object.pk,
                  entry_summary(self.object, AuditLog.EntryType.INWARD))
        return response

    def get_success_url(self):
        # just_saved=1 triggers the "Add Outward Entry Now" shortcut card on
        # the detail page. It is display-only — dropping it changes nothing.
        return reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=inward&just_saved=1"


# --- Outward create (per site + material) ----------------------------------

class OutwardEntryCreateView(EntryWriterRequiredMixin, CreateView):
    """Add an outward entry for a specific (site, material)."""
    model = OutwardEntry
    form_class = OutwardEntryForm
    template_name = "entries/entry_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_id"])
        self.material = get_object_or_404(Material, pk=kwargs["material_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # Pass site and material into the form so clean() can validate qty
        # against the current available balance for that site+material.
        # The user scopes the source-delivery picker to own entries for staff.
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        kwargs["material"] = self.material
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        # Smart defaults: today + now, plus one-tap repeat via ?repeat=<pk>.
        initial = super().get_initial()
        repeat_pk = self.request.GET.get("repeat")
        if repeat_pk:
            try:
                repeat_qs = OutwardEntry.objects.filter(
                    pk=repeat_pk, site=self.site, material=self.material
                )
                src = repeat_qs.first()
            except ValueError:
                src = None
            if src is not None:
                initial["qty"] = src.qty
                if src.sub_location_id:
                    initial["sub_location"] = src.sub_location.name
                if src.inward_entry_id:
                    initial["inward_entry"] = src.inward_entry_id
        initial.setdefault("date", timezone.localdate())
        initial.setdefault(
            "time", timezone.localtime().strftime("%H:%M")
        )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.site
        ctx["material"] = self.material
        ctx["form_title"] = "Record Outward Entry"
        ctx["submit_label"] = "Save Outward Entry"
        ctx["qty_label"] = "Quantity Used"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=outward"
        if not ctx.get("form").initial.get("date"):
            ctx["form"].initial["date"] = timezone.localdate()
        if not ctx.get("form").initial.get("time"):
            # Native time picker defaults to now; still editable. Format must
            # be %H:%M — that is what <input type="time"> accepts as a value.
            ctx["form"].initial["time"] = timezone.localtime().strftime("%H:%M")
        # Pass current available balance to the template for the helper hint
        from .utils import balance_for
        ctx["available_balance"] = balance_for(self.site, self.material)
        # Datalist suggestions: this site's known sub-location names.
        from .models import SubLocation
        ctx["sub_location_names"] = list(
            SubLocation.objects.filter(site=self.site)
            .order_by("name").values_list("name", flat=True)
        )
        return ctx

    def form_valid(self, form):
        form.instance.site = self.site
        form.instance.material = self.material
        form.instance.created_by = self.request.user
        # Race guard: the form-level balance check in clean() ran BEFORE this
        # save. Re-check under row locks inside a transaction so two staff
        # saving at the same second cannot both overshoot into negative.
        from django.db import IntegrityError, transaction
        from .utils import balance_for as _locked_balance, lock_stock_rows
        try:
            with transaction.atomic():
                lock_stock_rows(self.site, self.material)
                _fresh = _locked_balance(self.site, self.material)
                if form.instance.qty is not None and form.instance.qty > _fresh:
                    form.add_error(
                        "qty",
                        f"Only {fmt_qty(_fresh)} {self.material.unit} available for "
                        f"{self.material.display_name} at {self.site.name} "
                        f"(another entry just saved). You entered "
                        f"{fmt_qty(form.instance.qty)} {self.material.unit}.",
                    )
                    return self.form_invalid(form)
                response = _guarded_save(
                    form, self, lambda: CreateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(None, "Save conflict — please try again.")
            return self.form_invalid(form)
        if response.status_code != 302:
            # Guard re-rendered the form with an error.
            return response
        messages.success(
            self.request,
            f"Outward entry saved: {fmt_qty(form.instance.qty)} {self.material.unit} on "
            f"{form.instance.date.strftime('%b %d, %Y')} at {form.instance.time.strftime('%I:%M %p').lstrip('0')}.",
        )
        log_audit(self.request.user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.OUTWARD, self.object.pk,
                  entry_summary(self.object, AuditLog.EntryType.OUTWARD))
        return response

    def get_success_url(self):
        return reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=outward&just_saved=1"


class OrdersHistoryView(EntryWriterRequiredMixin, TemplateView):
    """Order history across sites (the Orders sidebar page).

    Tabs: All Orders / Inward / Outward + From/To date filter + 10-per-page
    pagination. Reads are global; every row links to its material ledger.
    Row ref format: IN-12 / OUT-5. Status is always Completed (a saved
    entry is a finished transaction) — shown green like the design.
    """

    template_name = "entries/orders.html"

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator

        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "all")
        if tab not in ("all", "inward", "outward"):
            tab = "all"
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        ctx["tab"] = tab
        ctx["date_from"] = date_from
        ctx["date_to"] = date_to

        in_qs = InwardEntry.objects.select_related("site", "material")
        out_qs = OutwardEntry.objects.select_related("site", "material")
        if date_from:
            in_qs = in_qs.filter(date__gte=date_from)
            out_qs = out_qs.filter(date__gte=date_from)
        if date_to:
            in_qs = in_qs.filter(date__lte=date_to)
            out_qs = out_qs.filter(date__lte=date_to)
        ctx["inward_count"] = in_qs.count()
        ctx["outward_count"] = out_qs.count()

        # Cap each side before merging in Python (shop-scale: plenty).
        rows = []
        if tab in ("all", "inward"):
            for e in in_qs.order_by("-date", "-time", "-id")[:500]:
                rows.append({"kind": "inward", "entry": e,
                             "ref": f"IN-{e.pk}",
                             "sort": (e.date, str(e.time), e.pk)})
        if tab in ("all", "outward"):
            for e in out_qs.order_by("-date", "-time", "-id")[:500]:
                rows.append({"kind": "outward", "entry": e,
                             "ref": f"OUT-{e.pk}",
                             "sort": (e.date, str(e.time), e.pk)})
        rows.sort(key=lambda r: r["sort"], reverse=True)
        page = Paginator(rows, 10).get_page(self.request.GET.get("page"))
        ctx["page"] = page
        # S No continues across pages (screenshot-style numbering).
        ctx["start_index"] = page.start_index()
        # Single shop: hide the Site column (everything is under one roof).
        from sites.models import Site
        ctx["single_site"] = Site.objects.count() == 1
        return ctx


class PurchaseCreateView(EntryWriterRequiredMixin, CreateView):
    """Shop front door: record stock bought (inward), no site picker."""

    model = InwardEntry
    form_class = PurchaseForm
    template_name = "entries/quick_form.html"

    def dispatch(self, request, *args, **kwargs):
        from sites.models import get_default_site
        self.site = get_default_site()
        if self.site is None:
            messages.error(
                request, "Set up your shop site first (more than one site "
                         "exists, so pick one from Sites).")
            return redirect("sites:list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if not ctx.get("form").initial.get("date"):
            ctx["form"].initial["date"] = timezone.localdate()
        ctx["kind"] = "purchase"
        ctx["page_title"] = "New Entry"
        ctx["page_sub"] = "Stock bought from a supplier. Balance rises immediately."
        ctx["submit_label"] = "Save Purchase"
        return ctx

    def form_valid(self, form):
        form.instance.site = self.site
        form.instance.created_by = self.request.user
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                response = _guarded_save(
                    form, self, lambda: CreateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(
                None,
                "Same material, date and time was just saved. "
                "Change the time slightly and try again.",
            )
            return self.form_invalid(form)
        if response.status_code != 302:
            return response
        messages.success(
            self.request,
            f"Purchase saved: {fmt_qty(form.instance.qty)} "
            f"{form.instance.material.unit} of "
            f"{form.instance.material.display_name}.",
        )
        log_audit(self.request.user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.INWARD, self.object.pk,
                  entry_summary(self.object, AuditLog.EntryType.INWARD))
        return response

    def get_success_url(self):
        return reverse("entries:orders")


class SaleCreateView(EntryWriterRequiredMixin, CreateView):
    """Shop front door: record a sale (outward) to a customer.

    No delivery picking: stock deducts FIFO from the oldest inward with
    stock left. Bulk and single orders are both just a quantity.
    """

    model = OutwardEntry
    form_class = SaleForm
    template_name = "entries/quick_form.html"

    def dispatch(self, request, *args, **kwargs):
        from sites.models import get_default_site
        self.site = get_default_site()
        if self.site is None:
            messages.error(
                request, "Set up your shop site first (more than one site "
                         "exists, so pick one from Sites).")
            return redirect("sites:list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if not ctx.get("form").initial.get("date"):
            ctx["form"].initial["date"] = timezone.localdate()
        ctx["kind"] = "sale"
        ctx["page_title"] = "New Entry"
        ctx["page_sub"] = "Sell to a customer. Stock deducts automatically, oldest purchase first. Bulk and single orders both work."
        ctx["submit_label"] = "Save Sale"
        return ctx

    def form_valid(self, form):
        form.instance.site = self.site
        form.instance.created_by = self.request.user
        form.instance.inward_entry = form.pick_fifo_delivery()
        # Race guard: re-check balance under row locks before saving.
        from django.db import IntegrityError, transaction
        from .utils import balance_for as _locked_balance, lock_stock_rows
        try:
            with transaction.atomic():
                lock_stock_rows(self.site, form.instance.material)
                fresh = _locked_balance(self.site, form.instance.material)
                if (form.instance.qty is not None
                        and form.instance.qty > fresh):
                    form.add_error(
                        "qty",
                        f"Only {fmt_qty(fresh)} "
                        f"{form.instance.material.unit} left "
                        f"(another entry just saved).",
                    )
                    return self.form_invalid(form)
                response = _guarded_save(
                    form, self, lambda: CreateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(None, "Save conflict. Please try again.")
            return self.form_invalid(form)
        if response.status_code != 302:
            return response
        messages.success(
            self.request,
            f"Sale saved: {fmt_qty(form.instance.qty)} "
            f"{form.instance.material.unit} of "
            f"{form.instance.material.display_name}"
            f" to {form.instance.customer or 'walk-in'}.",
        )
        log_audit(self.request.user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.OUTWARD, self.object.pk,
                  entry_summary(self.object, AuditLog.EntryType.OUTWARD))
        return response

    def get_success_url(self):
        return reverse("entries:orders")


def entry_summary(entry, entry_type):
    """Short human-readable snapshot, taken BEFORE an edit/delete lands."""
    if entry_type == AuditLog.EntryType.INWARD:
        extra = f"received_from: {entry.received_from}"
    else:
        extra = f"sub_location: {entry.sub_location}"
        if getattr(entry, "inward_entry_id", None) and entry.inward_entry:
            extra += (
                f" (from inward "
                f"{entry.inward_entry.date.strftime('%b %d, %Y')})"
            )
    return (
        f"{entry.material.display_name} | {fmt_qty(entry.qty)} {entry.material.unit} | "
        f"{entry.site.name} | {extra} | "
        f"{entry.date.strftime('%b %d, %Y')} "
        f"{entry.time.strftime('%I:%M %p').lstrip('0')}"
    )


def log_audit(user, action, entry_type, entry_id, summary):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        entry_type=entry_type,
        entry_id=entry_id,
        entry_summary=summary,
    )
    # Stock changed (or catalog changed): drop the cached navbar bell so the
    # next page load re-aggregates instead of showing 60s-stale lows.
    try:
        from django.core.cache import cache as _cache
        _cache.delete("low_stock_top5")
    except Exception:
        pass


# --- Edit (both roles; site/material stay fixed) -----------------------------

class InwardEntryUpdateView(EntryWriterRequiredMixin, UpdateView):
    """Edit an inward entry. Reuses the add form, pre-filled from the entry."""
    model = InwardEntry
    form_class = InwardEntryForm
    template_name = "entries/entry_form.html"
    pk_url_kwarg = "pk"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.object.site
        kwargs["material"] = self.object.material
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        entry = self.object
        ctx["site"] = entry.site
        ctx["material"] = entry.material
        ctx["form_title"] = "Edit Inward Entry"
        ctx["submit_label"] = "Save Changes"
        ctx["qty_label"] = "Quantity Received"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": entry.site.id, "material_id": entry.material.id,
        }) + "?tab=inward"
        return ctx

    def form_valid(self, form):
        entry_id = self.object.pk
        changed = list(getattr(form, "changed_data", []))

        # Over-allocation watch (warn-only by owner decision): if the edited
        # quantity drops below what is already allocated to sub-locations,
        # save anyway but flag it loudly here and in the audit trail.
        from django.db.models import Sum as _Sum
        allocated_total = (
            SubLocationAllocation.objects.filter(inward_entry=self.object)
            .aggregate(t=_Sum("qty_allocated"))["t"] or 0
        )
        under_allocated = form.instance.qty < allocated_total

        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                response = _guarded_save(
                    form, self, lambda: UpdateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(
                None,
                "An entry for this site, material, date and time was just "
                "saved by someone else. Change the time slightly and try again.",
            )
            return self.form_invalid(form)
        if response.status_code != 302:
            # Save guard re-rendered the form with an error.
            return response
        summary = entry_summary(self.object, AuditLog.EntryType.INWARD)
        if under_allocated:
            summary += (
                f" (WARNING: quantity {fmt_qty(form.instance.qty)} is below "
                f"allocated total {fmt_qty(allocated_total)}!)"
            )
        if changed:
            summary += f" (changed: {', '.join(changed)})"
        log_audit(self.request.user, AuditLog.Action.EDIT,
                  AuditLog.EntryType.INWARD, entry_id, summary)
        messages.success(self.request, "Inward entry updated.")
        if under_allocated:
            messages.warning(
                self.request,
                f"Quantity saved ({fmt_qty(form.instance.qty)} "
                f"{self.object.material.unit}) is below the total already "
                f"allocated to sub-locations "
                f"({fmt_qty(allocated_total)}). Review the allocations.",
            )
        return response

    def get_success_url(self):
        entry = self.object
        return reverse("entries:detail", kwargs={
            "site_id": entry.site.id, "material_id": entry.material.id,
        }) + "?tab=inward"


class OutwardEntryUpdateView(EntryWriterRequiredMixin, UpdateView):
    """Edit an outward entry. Qty re-validated against balance (see forms.py)."""
    model = OutwardEntry
    form_class = OutwardEntryForm
    template_name = "entries/entry_form.html"
    pk_url_kwarg = "pk"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.object.site
        kwargs["material"] = self.object.material
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        entry = self.object
        ctx["site"] = entry.site
        ctx["material"] = entry.material
        ctx["form_title"] = "Edit Outward Entry"
        ctx["submit_label"] = "Save Changes"
        ctx["qty_label"] = "Quantity Used"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": entry.site.id, "material_id": entry.material.id,
        }) + "?tab=outward"
        # Hint matches the edit-aware validation: current balance + this entry.
        ctx["available_balance"] = balance_for(entry.site, entry.material) + entry.qty
        from .models import SubLocation
        ctx["sub_location_names"] = list(
            SubLocation.objects.filter(site=entry.site)
            .order_by("name").values_list("name", flat=True)
        )
        return ctx

    def form_valid(self, form):
        entry_id = self.object.pk
        changed = list(getattr(form, "changed_data", []))
        # Race guard (same as create): re-check balance under row locks.
        # Exclude this row's own qty — it is part of "used" until re-saved.
        from django.db import IntegrityError, transaction
        from .utils import balance_for as _edit_balance, lock_stock_rows
        try:
            with transaction.atomic():
                lock_stock_rows(self.object.site, self.object.material)
                _orig = OutwardEntry.objects.filter(pk=entry_id).values_list(
                    "qty", flat=True).first()
                _fresh_avail = _edit_balance(
                    self.object.site, self.object.material) + (_orig or 0)
                if form.instance.qty is not None and form.instance.qty > _fresh_avail:
                    form.add_error(
                        "qty",
                        f"Only {fmt_qty(_fresh_avail)} {self.object.material.unit} "
                        f"available (another entry just saved). You entered "
                        f"{fmt_qty(form.instance.qty)}.",
                    )
                    return self.form_invalid(form)
                response = _guarded_save(
                    form, self, lambda: UpdateView.form_valid(self, form))
        except IntegrityError:
            form.add_error(None, "Save conflict — please try again.")
            return self.form_invalid(form)
        if response.status_code != 302:
            # Save guard re-rendered the form with an error.
            return response
        summary = entry_summary(self.object, AuditLog.EntryType.OUTWARD)
        if changed:
            summary += f" (changed: {', '.join(changed)})"
        log_audit(self.request.user, AuditLog.Action.EDIT,
                  AuditLog.EntryType.OUTWARD, entry_id, summary)
        messages.success(self.request, "Outward entry updated.")
        return response

    def get_success_url(self):
        entry = self.object
        return reverse("entries:detail", kwargs={
            "site_id": entry.site.id, "material_id": entry.material.id,
        }) + "?tab=outward"


# --- Delete (both roles; POST only, browser confirm in the template) ---------

class EntryDeleteMixin:
    """Snapshot summary BEFORE delete so the audit row outlives the entry."""
    entry_type = None
    tab = None
    http_method_names = ["post"]

    def form_valid(self, form):
        # Modern DeleteView drives deletion through form_valid (post() sets
        # self.object first), so this — not delete() — is the override point.
        from django.db.models import ProtectedError

        entry, site, material = self.object, self.object.site, self.object.material
        summary = entry_summary(entry, self.entry_type)
        entry_id = entry.pk
        # Cloudinary cleanup lives in model.delete() (covers app, admin,
        # shell); a blocked delete raises before anything is destroyed.
        try:
            entry.delete()
        except ProtectedError as exc:
            # An inward delivery with linked outward entries or allocations
            # cannot go away — delete those rows first. Name what blocks it.
            blockers = sorted(
                {obj._meta.verbose_name_plural for obj in exc.protected_objects}
            )
            messages.error(
                self.request,
                f"Cannot delete: this inward delivery still has "
                f"{len(exc.protected_objects)} linked "
                f"{'/'.join(blockers)}. Delete those first.",
            )
            return HttpResponseRedirect(reverse("entries:detail", kwargs={
                "site_id": site.id, "material_id": material.id,
            }) + f"?tab={self.tab}")
        log_audit(self.request.user, AuditLog.Action.DELETE,
                  self.entry_type, entry_id, summary)
        messages.success(self.request, f"{self.entry_type.capitalize()} entry deleted.")
        return HttpResponseRedirect(reverse("entries:detail", kwargs={
            "site_id": site.id, "material_id": material.id,
        }) + f"?tab={self.tab}")


class InwardEntryDeleteView(EntryWriterRequiredMixin, EntryDeleteMixin, DeleteView):
    model = InwardEntry
    entry_type = AuditLog.EntryType.INWARD
    tab = "inward"


class OutwardEntryDeleteView(EntryWriterRequiredMixin, EntryDeleteMixin, DeleteView):
    model = OutwardEntry
    entry_type = AuditLog.EntryType.OUTWARD
    tab = "outward"


# --- SubLocation management (admin only) -----------------------------------

class SubLocationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Add a sub-location to a site."""
    model = SubLocation
    form_class = SubLocationForm
    template_name = "entries/sub_location_form.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.site
        ctx["form_title"] = "Add Sub-Location"
        ctx["submit_label"] = "Create Sub-Location"
        ctx["back_url"] = reverse("sites:detail", kwargs={"pk": self.site.id})
        return ctx

    def form_valid(self, form):
        form.instance.site = self.site
        messages.success(
            self.request,
            f"Sub-location '{form.instance.name}' added to {self.site.name}.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("sites:detail", kwargs={"pk": self.site.id})


class SubLocationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edit a sub-location."""
    model = SubLocation
    form_class = SubLocationForm
    template_name = "entries/sub_location_form.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.object.site
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.object.site
        ctx["form_title"] = "Edit Sub-Location"
        ctx["submit_label"] = "Update Sub-Location"
        ctx["back_url"] = reverse("sites:detail", kwargs={"pk": self.object.site.id})
        return ctx

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Sub-location '{form.instance.name}' updated.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("sites:detail", kwargs={"pk": self.object.site.id})


class SubLocationDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a sub-location."""
    model = SubLocation
    template_name = "entries/sub_location_confirm_delete.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.object.site
        ctx["back_url"] = reverse("sites:detail", kwargs={"pk": self.object.site.id})
        return ctx

    def form_valid(self, form):
        site = self.object.site
        name = self.object.name
        messages.success(
            self.request,
            f"Sub-location '{name}' deleted from {site.name}.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("sites:detail", kwargs={"pk": self.object.site.id})


# --- SubLocationAllocation management (admin only) --------------------------

class AllocationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Allocate inward entry quantity to sub-locations."""
    model = SubLocationAllocation
    form_class = SubLocationAllocationForm
    template_name = "entries/allocation_form.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_id"])
        self.material = get_object_or_404(Material, pk=kwargs["material_id"])
        # Inward id comes from the path (preferred) or ?inward=<id> (legacy).
        # Scoped to this site+material so a tampered id 404s instead of
        # allocating another site's delivery here.
        inward_id = kwargs.get("inward_id") or request.GET.get("inward")
        if inward_id:
            try:
                self.inward_entry = get_object_or_404(
                    InwardEntry,
                    pk=int(inward_id),
                    site=self.site,
                    material=self.material,
                )
            except (ValueError, TypeError):
                raise Http404("Invalid inward entry.")
        else:
            self.inward_entry = None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["inward_entry"] = self.inward_entry
        kwargs["site"] = self.site
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["sub_location"].queryset = SubLocation.objects.filter(site=self.site)
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.site
        ctx["material"] = self.material
        ctx["inward_entry"] = self.inward_entry
        ctx["form_title"] = "Allocate Material to Sub-Location"
        ctx["submit_label"] = "Save Allocation"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=balance"
        return ctx

    def form_valid(self, form):
        from django.db import IntegrityError, transaction
        inward = self.inward_entry
        # No inward selected (legacy URL without ?inward=): don't crash with
        # None.qty — send the user back to pick a delivery first.
        if inward is None:
            messages.warning(
                self.request,
                "Select an inward delivery first, then allocate it.",
            )
            return redirect("entries:detail", site_id=self.site.id,
                            material_id=self.material.id)
        # Bind the FK before save (form.__init__ already does this for new
        # instances, but set it here too so form_valid never saves NULL).
        form.instance.inward_entry = inward
        try:
            with transaction.atomic():
                # Row-lock the delivery so two concurrent allocates cannot
                # jointly overshoot it (same pattern as outward saves).
                locked = InwardEntry.objects.select_for_update().filter(
                    pk=inward.pk).first()
                if locked is None:
                    form.add_error(None, "Delivery no longer exists.")
                    return self.form_invalid(form)
                total_allocated = SubLocationAllocation.objects.filter(
                    inward_entry=locked).aggregate(
                    t=Sum("qty_allocated"))["t"] or 0
                new_qty = form.cleaned_data["qty_allocated"]

                if total_allocated + new_qty > locked.qty:
                    form.add_error(
                        "qty_allocated",
                        f"Total allocated ({fmt_qty(total_allocated + new_qty)}) exceeds inward quantity ({fmt_qty(locked.qty)})."
                    )
                    return self.form_invalid(form)

                # Check if sub_location already has allocation for this inward
                if SubLocationAllocation.objects.filter(inward_entry=locked, sub_location=form.cleaned_data["sub_location"]).exists():
                    form.add_error(
                        "sub_location",
                        "This sub-location already has an allocation for this inward entry."
                    )
                    return self.form_invalid(form)

                messages.success(
                    self.request,
                    f"Allocated {fmt_qty(new_qty)} {self.material.unit} to {form.cleaned_data['sub_location'].name}.",
                )
                return super().form_valid(form)
        except IntegrityError:
            form.add_error(
                None, "Save conflict — someone just allocated this delivery. "
                "Please review and try again.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("entries:detail", kwargs={
            "site_id": self.site.id, "material_id": self.material.id,
        }) + "?tab=balance"


class AllocationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an allocation."""
    model = SubLocationAllocation
    form_class = SubLocationAllocationForm
    template_name = "entries/allocation_form.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.object.inward_entry.site
        ctx["material"] = self.object.inward_entry.material
        ctx["inward_entry"] = self.object.inward_entry
        ctx["form_title"] = "Edit Allocation"
        ctx["submit_label"] = "Update Allocation"
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": self.object.inward_entry.site.id,
            "material_id": self.object.inward_entry.material.id,
        }) + "?tab=balance"
        return ctx

    def form_valid(self, form):
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                inward = InwardEntry.objects.select_for_update().filter(
                    pk=self.object.inward_entry_id).first()
                if inward is None:
                    form.add_error(None, "Delivery no longer exists.")
                    return self.form_invalid(form)
                total_allocated = SubLocationAllocation.objects.filter(
                    inward_entry=inward).exclude(
                    pk=self.object.pk).aggregate(t=Sum("qty_allocated"))["t"] or 0
                new_qty = form.cleaned_data["qty_allocated"]

                if total_allocated + new_qty > inward.qty:
                    form.add_error(
                        "qty_allocated",
                        f"Total allocated ({fmt_qty(total_allocated + new_qty)}) exceeds inward quantity ({fmt_qty(inward.qty)})."
                    )
                    return self.form_invalid(form)

                messages.success(
                    self.request,
                    "Allocation updated.",
                )
                return super().form_valid(form)
        except IntegrityError:
            form.add_error(
                None, "Save conflict — someone just allocated this delivery. "
                "Please review and try again.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("entries:detail", kwargs={
            "site_id": self.object.inward_entry.site.id,
            "material_id": self.object.inward_entry.material.id,
        }) + "?tab=balance"


class AllocationDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete an allocation."""
    model = SubLocationAllocation
    template_name = "entries/allocation_confirm_delete.html"

    def test_func(self):
        return _user_is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["site"] = self.object.inward_entry.site
        ctx["material"] = self.object.inward_entry.material
        ctx["inward_entry"] = self.object.inward_entry
        ctx["back_url"] = reverse("entries:detail", kwargs={
            "site_id": self.object.inward_entry.site.id,
            "material_id": self.object.inward_entry.material.id,
        }) + "?tab=balance"
        return ctx

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Allocation for {self.object.sub_location.name} deleted.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("entries:detail", kwargs={
            "site_id": self.object.inward_entry.site.id,
            "material_id": self.object.inward_entry.material.id,
        }) + "?tab=balance"

def _parse_log_date(request):
    """
    Day selected via ?date=YYYY-MM-DD. Missing or invalid values fall back
    to today (local date) so the log always shows a single day, never a
    confusing mix or a crash on tampered input.
    """
    from datetime import date as date_cls

    raw = (request.GET.get("date") or "").strip()
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        return timezone.localdate()


class StaffActivityListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Activity landing: just staff member names. Clicking a name opens that
    person's Flipkart-style timeline. Owner only — staff AND managers
    get 403.
    """
    template_name = "entries/audit_log.html"
    context_object_name = "members"

    def test_func(self):
        return _user_can_view_activity(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def get_queryset(self):
        from accounts.models import User
        return User.objects.filter(
            role__in=[User.Role.STAFF, User.Role.MANAGER], is_superuser=False
        ).order_by("username")

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Max

        ctx = super().get_context_data(**kwargs)
        stats = {
            row["user_id"]: row
            for row in (
                AuditLog.objects.exclude(user__isnull=True)
                .values("user_id")
                .annotate(n=Count("id"), last=Max("timestamp"))
            )
        }
        members = []
        for u in ctx["members"]:
            stat = stats.get(u.pk, {})
            members.append({
                "user": u,
                "count": stat.get("n", 0),
                "last": stat.get("last"),
            })
        # Most recently active first; never-active members at the end, by name.
        active = sorted(
            (m for m in members if m["last"]),
            key=lambda m: m["last"], reverse=True,
        )
        idle = sorted(
            (m for m in members if not m["last"]),
            key=lambda m: m["user"].username.lower(),
        )
        ctx["members"] = active + idle
        return ctx


class StaffTimelineView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    One staff member's activity as a vertical timeline, newest first.
    Optional ?date=YYYY-MM-DD narrows to a single day (default: all).
    Owner only — staff AND managers get 403.
    """
    model = AuditLog
    template_name = "entries/staff_timeline.html"
    context_object_name = "logs"
    paginate_by = 100

    def test_func(self):
        return _user_can_view_activity(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        from accounts.models import User
        self.member = get_object_or_404(
            User.objects.filter(
                role__in=[User.Role.STAFF, User.Role.MANAGER],
                is_superuser=False,
            ),
            pk=kwargs["pk"],
        )
        # Optional day filter; missing/garbage means "all dates", never a crash.
        from datetime import date as date_cls
        raw = (request.GET.get("date") or "").strip()
        try:
            self.log_date = date_cls.fromisoformat(raw) if raw else None
        except ValueError:
            self.log_date = None
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .filter(user=self.member)
            .select_related("user")
        )
        if self.log_date is not None:
            qs = qs.filter(timestamp__date=self.log_date)
        return qs

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        ctx = super().get_context_data(**kwargs)
        ctx["member"] = self.member
        # Same picker context as the full day log (template reuses it).
        log_date = getattr(self, "log_date", None)
        today = timezone.localdate()
        shown = log_date or today
        ctx["log_date"] = log_date
        ctx["log_date_iso"] = log_date.isoformat() if log_date else ""
        ctx["picker_iso"] = shown.isoformat()
        ctx["today_iso"] = today.isoformat()
        ctx["prev_date_iso"] = (shown - timedelta(days=1)).isoformat()
        ctx["next_date_iso"] = (shown + timedelta(days=1)).isoformat()
        ctx["yesterday_iso"] = (today - timedelta(days=1)).isoformat()
        ctx["is_today"] = log_date is None or log_date >= today
        return ctx


class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Activity log: who did what, and when — one day at a time (today by
    default, ?date=YYYY-MM-DD to browse). Owner only — staff AND managers
    get 403, and the navbar link is hidden from them too.
    """
    model = AuditLog
    template_name = "entries/activity_full.html"
    context_object_name = "logs"
    paginate_by = 100

    def test_func(self):
        return _user_can_view_activity(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def get_queryset(self):
        # timestamp__date honours the active time zone (IST), matching the
        # dates rendered in the template. select_related avoids an N+1 on
        # the username shown per row.
        self.log_date = _parse_log_date(self.request)
        return (
            super().get_queryset()
            .select_related("user")
            .filter(timestamp__date=self.log_date)
        )

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        ctx = super().get_context_data(**kwargs)
        log_date = getattr(self, "log_date", _parse_log_date(self.request))
        today = timezone.localdate()
        ctx["log_date"] = log_date
        ctx["log_date_iso"] = log_date.isoformat()
        ctx["today_iso"] = today.isoformat()
        ctx["prev_date_iso"] = (log_date - timedelta(days=1)).isoformat()
        ctx["next_date_iso"] = (log_date + timedelta(days=1)).isoformat()
        ctx["yesterday_iso"] = (today - timedelta(days=1)).isoformat()
        # No forward browsing past today — keeps the picker honest.
        ctx["is_today"] = log_date >= today
        return ctx
