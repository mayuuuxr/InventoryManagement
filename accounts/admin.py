from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Admin for the custom User model.
    Extends the default UserAdmin so we keep all built-in fields (password,
    groups, permissions, etc.) and just add `role` to the visible columns.
    """
    # Columns shown in the user list page
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)

    # Add a "role" field to the standard fieldsets so it shows on the user form.
    # We insert it into the "Personal info" section.
    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
