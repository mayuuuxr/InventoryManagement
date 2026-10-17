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
    # Clicked from Orders: one saved order (IN-12 / OUT-5) with all its
    # fields, the sibling lines of the same bill, and a Print receipt
    # button (reuses the 80mm thermal bill paper).
    path(
        "orders/<str:kind>/<int:pk>/",
        views.OrderDetailView.as_view(),
        name="order_detail",
    ),
    # Shop front doors: record a purchase / sale in one screen.
    path(
        "purchase/add/",
        views.PurchaseCreateView.as_view(),
        name="purchase_add",
    ),
    # Billing screen: multi-item purchase in one bill
    path(
        "purchase/bill/",
        views.PurchaseBillView.as_view(),
        name="purchase_bill",
    ),
    path(
        "sale/add/",
        views.SaleCreateView.as_view(),
        name="sale_add",
    ),
    # Billing screen: multi-item sale in one bill (Indian shop front door)
    path(
        "sale/bill/",
        views.SaleBillView.as_view(),
        name="sale_bill",
    ),
    # Printable bill (80mm thermal, Rate/Amount blank for hand-filling)
    path(
        "sale/bill/print/",
        views.SaleBillPrintView.as_view(),
        name="sale_bill_print",
    ),
    # Same for purchases
    path(
        "purchase/bill/print/",
        views.PurchaseBillPrintView.as_view(),
        name="purchase_bill_print",
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
