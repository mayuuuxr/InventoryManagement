"""Cross-cutting pages that belong to no single app (help center, dashboard)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """Owner/staff home: stat cards + stock tabs (no charts).

    Tabs are separate pages: All Stock, Low Stock, Out of Stock — each a
    full material list with total balance across sites. Reads are global
    by design (everyone sees true stock); write rules live in the entry
    views, not here. `tab` is set by the URL (all|low|out).
    """

    template_name = "dashboard.html"
    tab = "all"

    def get_context_data(self, **kwargs):
        from entries.models import InwardEntry, OutwardEntry
        from entries.utils import LOW_STOCK_THRESHOLD, balances_for_sites
        from materials.models import Material
        from sites.models import Site

        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        ctx["today"] = today
        ctx["tab"] = self.tab
        ctx["today_inward"] = InwardEntry.objects.filter(date=today).count()
        ctx["today_outward"] = OutwardEntry.objects.filter(date=today).count()

        sites = list(Site.objects.all())
        ctx["single_site"] = len(sites) == 1
        ctx["single_site_id"] = sites[0].pk if len(sites) == 1 else None
        materials = list(
            Material.objects.select_related("category", "sub_category")
            .order_by("category__name", "sub_category__name", "name")
        )
        ctx["materials_count"] = len(materials)

        # One bulk balance pass (4 grouped queries, any catalog size).
        totals = {}
        if sites and materials:
            per_pair = balances_for_sites(sites, materials)
            for m in materials:
                totals[m.pk] = sum(
                    per_pair.get((s.pk, m.pk), 0) for s in sites)

        def reorder_of(m):
            return m.reorder_point if m.reorder_point is not None \
                else LOW_STOCK_THRESHOLD

        rows = []
        for m in materials:
            bal = totals.get(m.pk, 0)
            status = ("out" if bal <= 0
                      else "low" if bal <= reorder_of(m) else "ok")
            rows.append({"material": m, "balance": bal, "status": status,
                         "reorder": reorder_of(m)})

        ctx["low_count"] = sum(1 for r in rows if r["status"] == "low")
        ctx["out_count"] = sum(1 for r in rows if r["status"] == "out")
        if self.tab == "low":
            rows = [r for r in rows if r["status"] == "low"]
        elif self.tab == "out":
            rows = [r for r in rows if r["status"] == "out"]
        # Neediest first: out of stock, then low, then by name.
        order = {"out": 0, "low": 1, "ok": 2}
        rows.sort(key=lambda r: (order[r["status"]],
                                 r["material"].display_name.lower()))
        ctx["rows"] = rows
        return ctx


class HelpView(LoginRequiredMixin, TemplateView):
    """Role-aware usage guide. Content mirrors verified app behavior only:
    entry flows, PIN rules (admin-reset, 5-tries lockout), no-photo entry,
    per-role access. Any authenticated role may read it; the template
    shows the section matching the reader's role."""

    template_name = "help.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Update check needs ~2s of internet; fail-soft so offline help
        # always renders. Staff see the version; only admins see updates.
        from core.update import check_for_updates, read_local_version
        ctx["app_version"] = read_local_version()
        ctx["is_owner"] = (
            self.request.user.is_superuser
            or getattr(self.request.user, "role", "") == "admin"
        )
        ctx["update"] = None
        if ctx["is_owner"]:
            try:
                ctx["update"] = check_for_updates(
                    getattr(settings, "UPDATE_REPO", ""),
                    getattr(settings, "UPDATE_TOKEN", ""))
            except Exception:
                ctx["update"] = None
            from core.selfupdate import last_status
            try:
                ctx["update_status"] = last_status(settings.BASE_DIR)
            except Exception:
                ctx["update_status"] = None
        return ctx


def is_owner(user):
    """Shop owner: superuser or admin role. Gate for the updater."""
    return user.is_superuser or getattr(user, "role", "") == "admin"


class ApplyUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """One-click update (owner only): stage the release, restart, done.

    POST re-checks GitHub itself (tag/zip never trusted from the form),
    then backup + download + stage via core.selfupdate and launches the
    applier batch detached. The response is a polling page: the batch
    stops this server seconds later and brings it back on the new code.
    Any failure before staging aborts with a message and touches nothing.
    """

    def test_func(self):
        return is_owner(self.request.user)

    def post(self, request):
        from core.selfupdate import (
            UpdateError, launch_detached, perform_update, resolve_update,
        )
        resolved = resolve_update(
            getattr(settings, "UPDATE_REPO", ""),
            getattr(settings, "UPDATE_TOKEN", ""))
        if not resolved:
            messages.info(
                request, "No update found right now. Your app works as-is.")
            return redirect("help")
        tag, zip_url = resolved
        try:
            script = perform_update(settings.BASE_DIR, tag, zip_url)
        except UpdateError as exc:
            messages.error(request, f"Update did not start: {exc}")
            return redirect("help")
        try:
            launch_detached(script)
        except Exception:
            from core.selfupdate import _clear_lock
            _clear_lock(settings.BASE_DIR)
            messages.error(
                request, "Update staged but could not start — try again.")
            return redirect("help")
        return render(request, "updating.html", {"tag": tag})


class UpdateStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    """JSON progress feed for the updating page (owner only).

    The page polls this instead of guessing: while the server restarts
    the requests simply fail and polling continues; once back, the last
    applier status line tells it whether to enter the dashboard or show
    the failure (with the exact reason the batch recorded).
    """

    def test_func(self):
        return is_owner(self.request.user)

    def get(self, request):
        from django.http import JsonResponse

        from core.selfupdate import (
            last_status, read_progress, update_in_progress,
        )
        progress = read_progress(settings.BASE_DIR)
        return JsonResponse({
            "in_flight": update_in_progress(settings.BASE_DIR),
            "last": last_status(settings.BASE_DIR) or "",
            "progress": {"pct": progress[0], "label": progress[1]}
            if progress else None,
        })


class PrivacyView(TemplateView):
    """Privacy policy. Public (no login): readable before signing in."""

    template_name = "privacy.html"


class TermsView(TemplateView):
    """Terms and conditions. Public (no login): readable before signing in."""

    template_name = "terms.html"
