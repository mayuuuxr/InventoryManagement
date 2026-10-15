from django import forms
from django.conf import settings
from django.contrib import admin

from .models import AuditLog, InwardEntry, OutwardEntry, TransferEntry, SubLocation, SubLocationAllocation


# --- Time field helper -----------------------------------------------------

# `settings.TIME_INPUT_FORMATS` is a legacy global that Django does NOT auto-pick-up
# for `forms.TimeField` in modern versions. To make "02:30 PM" actually parse, we
# construct the TimeField with the project's input formats explicitly. Display
# (admin list view) is already handled by settings.TIME_FORMAT.
ENTRY_TIME_INPUT_FORMATS = list(settings.TIME_INPUT_FORMATS) + [
    "%H:%M:%S.%f",
    "%H:%M:%S",
    "%H:%M",
    "%I:%M %p",       # 02:30 PM  — primary
    "%I:%M%p",        # 02:30PM
    "%I %p",          # 2 PM
    "%I:%M",          # 02:30 (ambiguous but accepted)
]


def entry_time_field(**kwargs):
    """Build a TimeField that accepts 12-hour (AM/PM) and 24-hour inputs."""
    defaults = {
        "input_formats": ENTRY_TIME_INPUT_FORMATS,
        "required": True,
        "widget": forms.TimeInput(
            attrs={
                "type": "time",
                "placeholder": "02:30 PM",
                "size": 10,
                "class": "vTimeField",  # matches Django's default admin look
            },
            format="%H:%M:%S",  # the value format the widget sends to the server
        ),
        # Help text shown below the field in the admin.
        "help_text": "12-hour (e.g. 02:30 PM) or 24-hour (e.g. 14:30)",
    }
    defaults.update(kwargs)
    return forms.TimeField(**defaults)


# --- Custom admin ModelForms ----------------------------------------------
#
# We replace the auto-generated `time` field on each admin ModelForm so the
# admin form accepts the 12-hour-with-AM/PM format the user expects.

class InwardEntryAdminForm(forms.ModelForm):
    time = entry_time_field()

    class Meta:
        model = InwardEntry
        fields = "__all__"

    def clean(self):
        # No photo entry in nibba: nothing extra to validate here.
        return super().clean()


class OutwardEntryAdminForm(forms.ModelForm):
    time = entry_time_field()

    class Meta:
        model = OutwardEntry
        fields = "__all__"

    def clean(self):
        # No photo entry in nibba: nothing extra to validate here.
        return super().clean()


class TransferEntryAdminForm(forms.ModelForm):
    time = entry_time_field()

    class Meta:
        model = TransferEntry
        fields = "__all__"


# --- Admin registrations ---------------------------------------------------

@admin.register(InwardEntry)
class InwardEntryAdmin(admin.ModelAdmin):
    """
    date + time are user-entered (manual entry). Time displays in 12-hour
    with AM/PM because of settings.TIME_FORMAT. created_at is system-managed.
    """
    form = InwardEntryAdminForm
    list_display = ("date", "time", "site", "material", "qty", "received_from", "created_by", "created_at")
    list_filter = ("date", "site", "material")
    search_fields = ("received_from", "site__name", "material__name", "material__sub_category__name")
    date_hierarchy = "date"
    ordering = ("-date", "-time", "-created_at")
    autocomplete_fields = ("site", "material")
    readonly_fields = ("created_at", "created_by")

    fieldsets = (
        ("Entry", {
            "fields": ("site", "material", "date", "time", "qty", "received_from"),
            "description": "Date and time are entered manually. Time format: 12-hour (e.g. 02:30 PM) or 24-hour (e.g. 14:30). nibba PC build: no photo entry.",
        }),
        ("Audit", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )


@admin.register(OutwardEntry)
class OutwardEntryAdmin(admin.ModelAdmin):
    form = OutwardEntryAdminForm
    list_display = (
        "date", "time", "site", "material", "qty", "sub_location", "inward_entry", "created_by", "created_at",
    )
    list_filter = ("date", "site", "material")
    search_fields = ("sub_location__name", "site__name", "material__name", "material__sub_category__name")
    date_hierarchy = "date"
    ordering = ("-date", "-time", "-created_at")
    autocomplete_fields = ("site", "material", "sub_location", "inward_entry")
    readonly_fields = ("created_at", "created_by")

    fieldsets = (
        ("Entry", {
            "fields": ("site", "material", "date", "time", "qty", "sub_location", "inward_entry"),
            "description": (
                "Time format: 12-hour (e.g. 02:30 PM) or 24-hour (e.g. 14:30). "
                "sub_location is the sub-location where the material was used; "
                "inward_entry is the delivery it was used from. "
                "nibba PC build: no photo entry."
            ),
        }),
        ("Audit", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )


@admin.register(TransferEntry)
class TransferEntryAdmin(admin.ModelAdmin):
    form = TransferEntryAdminForm
    list_display = ("date", "time", "material", "qty", "from_site", "to_site", "created_by", "created_at")
    list_filter = ("date", "material", "from_site", "to_site")
    search_fields = ("material__name", "material__sub_category__name", "from_site__name", "to_site__name")
    date_hierarchy = "date"
    ordering = ("-date", "-time", "-created_at")
    autocomplete_fields = ("material", "from_site", "to_site")
    readonly_fields = ("created_at", "created_by")

    fieldsets = (
        ("Entry", {
            "fields": ("material", "date", "time", "qty", "from_site", "to_site"),
            "description": "Date and time are entered manually. Time format: 12-hour (e.g. 02:30 PM) or 24-hour (e.g. 14:30). From and To sites must differ; quantity must be a positive whole number.",
        }),
        ("Audit", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Stamp ownership like the app views do (model has no auto default).
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SubLocation)
class SubLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "created_at")
    list_filter = ("site",)
    search_fields = ("name", "site__name")
    autocomplete_fields = ("site",)
    ordering = ("site__name", "name")


@admin.register(SubLocationAllocation)
class SubLocationAllocationAdmin(admin.ModelAdmin):
    list_display = ("inward_entry", "sub_location", "qty_allocated", "created_at")
    list_filter = ("sub_location__site", "sub_location", "inward_entry__material")
    search_fields = ("sub_location__name", "inward_entry__material__name")
    autocomplete_fields = ("inward_entry", "sub_location")
    ordering = ("-created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    # Log rows are written automatically by the edit/delete views.
    # Nobody creates them by hand, and editing history would defeat the point.
    list_display = ("timestamp", "user", "action", "entry_type", "entry_id", "entry_summary")
    list_filter = ("action", "entry_type", "timestamp")
    search_fields = ("entry_summary", "user__username")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    readonly_fields = ("user", "action", "entry_type", "entry_id", "entry_summary", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # History rows are evidence — nobody wipes them, not even via admin.
        return False