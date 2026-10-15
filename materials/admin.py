from django.contrib import admin

from .models import Category, Material, SubCategory


class CatalogAdminMixin:
    """Show soft-deleted catalog rows too (app hides them) with audit data.
    Django-admin deletes also soft-delete instead of wiping rows."""

    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    def delete_model(self, request, obj):
        obj.soft_delete(request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(request.user)

    @admin.action(description="Restore selected rows (undo soft-delete)")
    def restore_selected(self, request, queryset):
        restored = queryset.filter(is_deleted=True).update(
            is_deleted=False, deleted_by=None, deleted_at=None)
        if restored:
            self.message_user(
                request, f"Restored {restored} row(s).")
        else:
            self.message_user(
                request, "Nothing restored — selection had no deleted rows.")


@admin.register(Category)
class CategoryAdmin(CatalogAdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_deleted", "created_by", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_by", "deleted_by", "deleted_at")


@admin.register(SubCategory)
class SubCategoryAdmin(CatalogAdminMixin, admin.ModelAdmin):
    list_display = ("name", "category", "is_deleted", "created_by",
                    "created_at")
    list_filter = ("category", "is_deleted")
    search_fields = ("name", "category__name")
    ordering = ("category__name", "name")
    readonly_fields = ("created_by", "deleted_by", "deleted_at")


@admin.register(Material)
class MaterialAdmin(CatalogAdminMixin, admin.ModelAdmin):
    list_display = ("name", "sub_category", "category", "unit", "reorder_point",
                    "is_deleted", "created_by", "created_at")
    list_editable = ("reorder_point",)
    list_filter = ("category", "sub_category", "unit", "is_deleted")
    search_fields = ("name", "sub_category__name")
    # Show categories grouped in the FK dropdown (handy when list grows).
    autocomplete_fields = ()
    ordering = ("category__name", "sub_category__name", "name")
    readonly_fields = ("created_by", "deleted_by", "deleted_at")
