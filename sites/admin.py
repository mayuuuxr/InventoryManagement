from django.contrib import admin

from materials.admin import CatalogAdminMixin

from .models import Site


@admin.register(Site)
class SiteAdmin(CatalogAdminMixin, admin.ModelAdmin):
    list_display = ("name", "location", "is_deleted", "created_by",
                    "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("name", "location")
    readonly_fields = ("created_by", "deleted_by", "deleted_at")
