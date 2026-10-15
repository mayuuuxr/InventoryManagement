from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView

from core.utils import _user_can_edit, _user_is_admin
from entries.models import AuditLog
from entries.views import log_audit

from .forms import MaterialForm
from .models import Category, Material, SubCategory


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin-only pages (deletes). Staff get 403."""

    def test_func(self):
        return _user_is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


class MaterialCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Admin, Staff and Managers can add new materials (they go to the global
    catalog, not per-site). After a successful save we redirect back to where
    the user came from (via ?next=) or to the site list as a safe default.
    """

    def test_func(self):
        return _user_can_edit(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()
    model = Material
    form_class = MaterialForm
    template_name = "materials/material_form.html"

    def get_success_url(self):
        # If user came from a specific site, return them to that site's
        # material list. Otherwise go to the site list. Only relative URLs
        # are honoured — absolute/external ?next= values are ignored so a
        # crafted link can never bounce staff to a phishing site.
        from django.utils.http import url_has_allowed_host_and_scheme
        nxt = self.request.POST.get("next") or self.request.GET.get("next")
        if nxt and url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={self.request.get_host()}
        ):
            return nxt
        return reverse_lazy("sites:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.POST.get("next") or self.request.GET.get("next") or ""
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        user = self.request.user
        auto = getattr(form, "_auto_created", {})
        if auto.get("category") is not None:
            log_audit(user, AuditLog.Action.CREATE,
                      AuditLog.EntryType.CATEGORY, auto["category"].pk,
                      f"Category '{auto['category'].name}' created "
                      f"by {user.username} (via material form).")
        if auto.get("sub_category") is not None:
            log_audit(user, AuditLog.Action.CREATE,
                      AuditLog.EntryType.CATEGORY, auto["sub_category"].pk,
                      f"Sub-category '{auto['sub_category'].name}' under "
                      f"'{auto['sub_category'].category.name}' created "
                      f"by {user.username} (via material form).")
        log_audit(user, AuditLog.Action.CREATE,
                  AuditLog.EntryType.MATERIAL, form.instance.pk,
                  f"Material '{form.instance.display_name}' "
                  f"({form.instance.unit}) created "
                  f"by {user.username}.")
        messages.success(
            self.request,
            f"Material '{form.instance.display_name}' added to {form.instance.category.name}.",
        )
        return response


def _soft_delete_catalog(request, obj, entry_type, label, fallback_url):
    """Shared soft-delete + audit for catalog rows. Keeps the row (and its
    pre-deletion name) in the database. Returns to the caller's page via a
    relative-only `next` field, else the fallback."""
    name = obj.display_name if hasattr(obj, "display_name") else obj.name
    obj.soft_delete(request.user)
    log_audit(request.user, AuditLog.Action.DELETE,
              entry_type, obj.pk,
              f"{label} '{name}' deleted by {request.user.username}.")
    messages.success(request, f"{label} '{name}' deleted.")
    nxt = request.POST.get("next") or ""
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(fallback_url)


class MaterialDeleteView(AdminRequiredMixin, View):
    """Admin-only soft delete (POST + browser confirm). Linked entries stay
    in the database untouched."""
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        material = get_object_or_404(Material, pk=kwargs["pk"])
        return _soft_delete_catalog(
            request, material, AuditLog.EntryType.MATERIAL, "Material",
            "sites:list")


class CategoryDeleteView(AdminRequiredMixin, View):
    """Admin-only soft delete, blocked while live materials/sub-categories
    remain under the category (message names the counts)."""
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        category = get_object_or_404(Category, pk=kwargs["pk"])
        live_mats = Material.objects.filter(category=category).count()
        live_subs = SubCategory.objects.filter(category=category).count()
        if live_mats or live_subs:
            messages.error(
                request,
                f"Cannot delete category '{category.name}': it still has "
                f"{live_mats} material(s) and {live_subs} "
                f"sub-category(ies). Delete or move those first.")
            return redirect("sites:list")
        return _soft_delete_catalog(
            request, category, AuditLog.EntryType.CATEGORY, "Category",
            "sites:list")


class SubCategoryDeleteView(AdminRequiredMixin, View):
    """Admin-only soft delete, blocked while live materials use it."""
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        sub = get_object_or_404(SubCategory, pk=kwargs["pk"])
        live_mats = Material.objects.filter(sub_category=sub).count()
        if live_mats:
            messages.error(
                request,
                f"Cannot delete sub-category '{sub.name}': {live_mats} "
                f"material(s) still use it. Delete or move those first.")
            return redirect("sites:list")
        return _soft_delete_catalog(
            request, sub, AuditLog.EntryType.CATEGORY, "Sub-category",
            "sites:list")
