from django.urls import path

from . import views

app_name = "entries"

urlpatterns = [
    # Activity log landing: staff member names — owner only (enforced in views)
    path(
        "activity/",
        views.StaffActivityListView.as_view(),
        name="audit_log",
    ),
    # One staff member's timeline
    path(
        "activity/staff/<int:pk>/",
        views.StaffTimelineView.as_view(),
        name="staff_timeline",
    ),
    # Full day-wise log table (linked from the landing page)
    path(
        "activity/all/",
        views.AuditLogListView.as_view(),
        name="audit_log_all",
    ),
    # Order history across sites (Orders sidebar page)
    path(
        "orders/",
        views.OrdersHistoryView.as_view(),
        name="orders",
    ),
    # Shop front doors: record a purchase / sale in one screen.
    path(
        "purchase/add/",
        views.PurchaseCreateView.as_view(),
        name="purchase_add",
    ),
    path(
        "sale/add/",
        views.SaleCreateView.as_view(),
        name="sale_add",
    ),
    # Material detail with tabs (inward / outward / balance)
    path(
        "sites/<int:site_id>/materials/<int:material_id>/",
        views.MaterialDetailView.as_view(),
        name="detail",
    ),
    # Add inward
    path(
        "sites/<int:site_id>/materials/<int:material_id>/inward/add/",
        views.InwardEntryCreateView.as_view(),
        name="inward_add",
    ),
    # Edit / delete inward
    path(
        "sites/<int:site_id>/materials/<int:material_id>/inward/<int:pk>/edit/",
        views.InwardEntryUpdateView.as_view(),
        name="inward_edit",
    ),
    path(
        "sites/<int:site_id>/materials/<int:material_id>/inward/<int:pk>/delete/",
        views.InwardEntryDeleteView.as_view(),
        name="inward_delete",
    ),
    # Add outward
    path(
        "sites/<int:site_id>/materials/<int:material_id>/outward/add/",
        views.OutwardEntryCreateView.as_view(),
        name="outward_add",
    ),
    # Edit / delete outward
    path(
        "sites/<int:site_id>/materials/<int:material_id>/outward/<int:pk>/edit/",
        views.OutwardEntryUpdateView.as_view(),
        name="outward_edit",
    ),
    path(
        "sites/<int:site_id>/materials/<int:material_id>/outward/<int:pk>/delete/",
        views.OutwardEntryDeleteView.as_view(),
        name="outward_delete",
    ),
    # Sub-location management (admin only)
    path(
        "sites/<int:site_id>/sub-locations/add/",
        views.SubLocationCreateView.as_view(),
        name="sub_location_add",
    ),
    path(
        "sites/<int:site_id>/sub-locations/<int:pk>/edit/",
        views.SubLocationUpdateView.as_view(),
        name="sub_location_edit",
    ),
    path(
        "sites/<int:site_id>/sub-locations/<int:pk>/delete/",
        views.SubLocationDeleteView.as_view(),
        name="sub_location_delete",
    ),
    # Allocation management (admin only)
    # Legacy URL (kept): inward chosen via ?inward=<id> query param.
    path(
        "sites/<int:site_id>/materials/<int:material_id>/allocate/",
        views.AllocationCreateView.as_view(),
        name="allocation_add",
    ),
    # Preferred URL: inward id in the path (unambiguous, bookmarkable).
    path(
        "sites/<int:site_id>/materials/<int:material_id>/inward/<int:inward_id>/allocate/",
        views.AllocationCreateView.as_view(),
        name="allocation_add_for_inward",
    ),
    path(
        "sites/<int:site_id>/materials/<int:material_id>/allocations/<int:pk>/edit/",
        views.AllocationUpdateView.as_view(),
        name="allocation_edit",
    ),
    path(
        "sites/<int:site_id>/materials/<int:material_id>/allocations/<int:pk>/delete/",
        views.AllocationDeleteView.as_view(),
        name="allocation_delete",
    ),
]
