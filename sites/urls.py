from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    # Site list (landing page after login)
    path("", views.SiteListView.as_view(), name="list"),
    # Add new site (admin only — enforced by the view's UserPassesTestMixin)
    path("new/", views.SiteCreateView.as_view(), name="create"),
    # Soft-delete a site (admin only, POST + confirm; row stays in DB)
    path("<int:pk>/delete/", views.SiteDeleteView.as_view(), name="delete"),
    # Site detail = per-site material list (groups by category, shows balance)
    path("<int:pk>/", views.SiteMaterialListView.as_view(), name="detail"),
]
