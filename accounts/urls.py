from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Login / logout
    path("login/", views.CustomLoginView.as_view(), name="login"),
    # Django's built-in LogoutView handles the POST. We pass next_page so users
    # land on the login page after logging out (matches LOGOUT_REDIRECT_URL).
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),

    # Dashboards (placeholders for now)
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("staff-dashboard/", views.staff_dashboard, name="staff_dashboard"),

    # Staff management (admin only — enforced in the views)
    path("staff/", views.StaffListView.as_view(), name="staff_list"),
    path("staff/add/", views.StaffCreateView.as_view(), name="staff_add"),
    path("staff/<int:pk>/edit/", views.StaffUpdateView.as_view(), name="staff_edit"),
    path(
        "staff/<int:pk>/reset-password/",
        views.StaffPasswordResetView.as_view(),
        name="staff_reset",
    ),
    path(
        "staff/<int:pk>/delete/",
        views.StaffDeleteView.as_view(),
        name="staff_delete",
    ),
]
