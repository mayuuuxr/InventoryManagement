from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsLandingView.as_view(), name="landing"),
    path("site-summary/", views.SiteSummaryView.as_view(), name="site_summary"),
    path(
        "site-summary/export/",
        views.SiteSummaryExportView.as_view(),
        name="site_summary_export",
    ),
    path(
        "site-summary/export-pdf/",
        views.SiteSummaryExportPDFView.as_view(),
        name="site_summary_export_pdf",
    ),
    path(
        "material-consumption/",
        views.MaterialConsumptionView.as_view(),
        name="material_consumption",
    ),
    path(
        "material-consumption/export/",
        views.MaterialConsumptionExportView.as_view(),
        name="material_consumption_export",
    ),
    path(
        "material-consumption/export-pdf/",
        views.MaterialConsumptionExportPDFView.as_view(),
        name="material_consumption_export_pdf",
    ),
    path("monthly/", views.MonthlyReportView.as_view(), name="monthly"),
    path(
        "monthly/export/",
        views.MonthlyReportExportView.as_view(),
        name="monthly_export",
    ),
    path(
        "monthly/export-pdf/",
        views.MonthlyReportExportPDFView.as_view(),
        name="monthly_export_pdf",
    ),
]
