"""
URL configuration for core project.
"""
from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from . import pwa
from .views import (
    ApplyUpdateView, DashboardView, HelpView, PrivacyView, TermsView,
    UpdateStatusView,
)


def root_redirect(request):
    """
    Root URL: send anonymous users to login, authenticated users
    straight to the Dashboard (stats + order history).
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    return redirect("dashboard")


urlpatterns = [
    # Django admin lives at a SECRET path in production (DJANGO_ADMIN_PATH
    # env — /admin/ then 404s). Staff never need it (PIN login instead);
    # only the owner holds the secret URL. Brute force still hits the
    # axes lockout (5 wrong tries = 1 hour) like every other login.
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    # PWA shell: manifest + root-scope service worker + icons (see core/pwa.py).
    path("manifest.webmanifest", pwa.manifest_view, name="pwa_manifest"),
    path("sw.js", pwa.service_worker_view, name="pwa_sw"),
    path("pwa/<str:filename>", pwa.icon_view, name="pwa_icon"),
    path("help/", HelpView.as_view(), name="help"),
    path("update/apply/", ApplyUpdateView.as_view(), name="update_apply"),
    path("update/status/", UpdateStatusView.as_view(), name="update_status"),
    path("privacy/", PrivacyView.as_view(), name="privacy"),
    path("terms/", TermsView.as_view(), name="terms"),
    path("dashboard/", DashboardView.as_view(tab="all"), name="dashboard"),
    path("dashboard/low-stock/", DashboardView.as_view(tab="low"),
         name="dashboard_low"),
    path("dashboard/out-of-stock/", DashboardView.as_view(tab="out"),
         name="dashboard_out"),
    path("accounts/", include("accounts.urls")),
    path("sites/", include("sites.urls")),
    path("materials/", include("materials.urls")),
    path("entries/", include("entries.urls")),
    path("reports/", include("reports.urls")),
    path("", root_redirect),
]
