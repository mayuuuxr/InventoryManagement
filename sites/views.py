from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from entries.models import AuditLog
from entries.utils import balances_for_site, fmt_qty
from entries.views import log_audit
from materials.models import Material

from core.utils import _user_can_edit, _user_is_admin

from .forms import SiteForm
from .models import Site


# --- Site list (landing page after login) ----------------------------------

class SiteListView(LoginRequiredMixin, ListView):
    """
    Shop list. Single-shop installs skip straight to the shop page, so
    staff never see site management. The "Add New Shop" button is
    rendered in the template only for users with admin role.
    """
    model = Site
    template_name = "sites/site_list.html"
    context_object_name = "sites"
    paginate_by = 50

    def get(self, request, *args, **kwargs):
        # One shop under one roof: no list to browse, go to the shop.
        if Site.objects.count() == 1:
            return redirect("sites:detail", pk=Site.objects.first().pk)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Site.objects.all()
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["is_admin"] = _user_is_admin(self.request.user)
        return ctx


# --- Site create (admin only) ----------------------------------------------

class SiteCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Only Admin can add a Site (per AGENTS.md / permission matrix). We use
    UserPassesTestMixin instead of the @admin_required decorator because that
    decorator is for function-based views — mixing it with a class's `dispatch`
    method would capture `self` as the first arg and break.
    """
    model = Site
    form_class = SiteForm
    template_name = "sites/site_form.html"
    success_url = reverse_lazy("sites:list")

    def test_func(self):
        return _user_is_admin(self.request.user)

    def handle_no_permission(self):
        # If logged in but not admin → 403. If not logged in → redirect to login.
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_audit(self.request.user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.SITE, form.instance.pk,
                  f"Site '{form.instance.name}' ({form.instance.location}) "
                  f"created by {self.request.user.username}.")
        messages.success(self.request, f"Shop '{form.instance.name}' created.")
        return response


class SiteDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Admin-only soft delete (POST + browser confirm). The row (and its
    pre-deletion name) stays in the database; linked entries are untouched.
    """
    http_method_names = ["post"]

    def test_func(self):
        return _user_is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

    def post(self, request, *args, **kwargs):
        site = get_object_or_404(Site, pk=kwargs["pk"])
        name = site.name
        site.soft_delete(request.user)
        log_audit(request.user, AuditLog.Action.DELETE,
                  AuditLog.EntryType.SITE, site.pk,
                  f"Site '{name}' ({site.location}) "
                  f"deleted by {request.user.username}.")
        messages.success(self.request, f"Shop '{name}' deleted.")
        return redirect("sites:list")


# --- Site detail → material list (per site) --------------------------------

class SiteMaterialListView(LoginRequiredMixin, DetailView):
    """
    Per-site material list. Shows all materials grouped by Category, with the
    current balance for THIS site on each material row. Search bar filters
    material names without un-collapsing categories.

    URL: /sites/<pk>/  (this view also serves as the "site detail" landing
    because in this app, a site IS a collection of materials).
    """
    model = Site
    template_name = "sites/site_material_list.html"
    context_object_name = "site"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        site = self.object
        q = (self.request.GET.get("q") or "").strip().lower()
        # Mobile hamburger shows the page-specific "Add New Material" item
        # only on this page (base.html reads this flag + can_edit).
        ctx["show_add_material_menu"] = True

        # Build per-material list with this site's balance — one grouped
        # query set for the whole catalog (balances_for_site), not one
        # balance_for_user() per row (that was ~1,600 queries on this page).
        materials = Material.objects.select_related(
            "category", "sub_category__category"
        ).order_by("category__name", "sub_category__name", "name")
        balances = balances_for_site(site, materials, self.request.user)
        material_rows = [
            # Staff see their own entries' balance; everyone else the full
            # one (handled inside balances_for_site, same rule as before).
            {"material": m, "balance": balances[m.id]}
            for m in materials
        ]

        # Group: Category -> {loose rows, sub-category groups}.
        # Search matches across all three levels: a category hit keeps the
        # whole category, a sub-category hit keeps the whole sub-group, and a
        # material hit keeps just that row (e.g. "8mm" finds "Steel > 8mm").
        categories = {}
        for row in material_rows:
            m = row["material"]
            # Soft-deleted catalog rows (and materials under a deleted
            # category/sub-category) stay out of the UI; entries keep them.
            if m.category.is_deleted:
                continue
            if m.sub_category is not None and m.sub_category.is_deleted:
                continue
            cat = m.category
            sub = m.sub_category  # None for ungrouped materials
            if q:
                cat_hit = q in cat.name.lower()
                sub_hit = sub is not None and q in sub.name.lower()
                mat_hit = q in m.name.lower() or q in m.display_name.lower()
                if not (cat_hit or sub_hit or mat_hit):
                    continue
                if not cat_hit:
                    # Narrowed view: keep only the matching sub-group / row.
                    # (When the category itself matches, everything is kept.)
                    if sub is not None and not (sub_hit or mat_hit):
                        continue
                    if sub is None and not mat_hit:
                        continue
            group = categories.setdefault(
                cat, {"loose": [], "subs": {}}
            )
            if sub is None:
                group["loose"].append(row)
            else:
                group["subs"].setdefault(sub, []).append(row)

        # Sort: categories alphabetically; inside each, loose rows first, then
        # sub-groups alphabetically; rows alphabetical by variant name.
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

        ctx["category_groups"] = category_groups
        ctx["q"] = self.request.GET.get("q", "")
        ctx["is_admin"] = _user_is_admin(self.request.user)
        ctx["can_edit"] = _user_can_edit(self.request.user)

        # Pagination (browse mode only): categories render collapsed, but
        # their rows are still full HTML — 400+ rows is ~1 MB. Splitting
        # categories across pages keeps each page light. Search mode (?q=)
        # stays unpaginated: the live search takes over client-side anyway.
        ctx["is_paged"] = not q
        if not q:
            paginator = Paginator(category_groups, 8)
            page_obj = paginator.get_page(self.request.GET.get("page"))
            ctx["category_groups"] = list(page_obj.object_list)
            ctx["page_obj"] = page_obj
        else:
            ctx["page_obj"] = None

        # Full-catalog search index for the live search: id, display name,
        # category path, unit, balance text, detail URL. ~65 KB of JSON lets
        # the paged page search all 400+ materials without rendering them.
        ctx["mat_index"] = [
            {
                "name": m.display_name,
                "cat": m.category.name,
                "sub": m.sub_category.name if m.sub_category else "",
                "bal": "%s %s" % (fmt_qty(balances[m.id]), m.unit),
                "url": reverse("entries:detail", args=[site.id, m.id]),
            }
            for m in materials
            # Same visibility rule as the grouped list above: soft-deleted
            # catalog rows never surface, in lists or in search.
            if not m.category.is_deleted
            and not (m.sub_category is not None and m.sub_category.is_deleted)
        ]
        return ctx