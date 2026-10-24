from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from materials.models import Material
from sites.models import Site


# Default time used when adding a new entry. The user can override in the form.
# Set to noon so the time field has a sensible initial value during data entry.
DEFAULT_ENTRY_TIME = "12:00:00"


class InwardEntry(models.Model):
    # date + time are user-entered fields — the actual moment the inward happened.
    # created_at is system-managed (auto_now_add) and only used for audit.
    # PROTECT: a site/material with entries cannot be hard-deleted
    # (catalog uses soft-delete in the app; this blocks admin/shell wipes).
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(default=DEFAULT_ENTRY_TIME)
    qty = models.DecimalField(max_digits=12, decimal_places=2)
    # Price snapshot at entry time (₹ per unit, taxes of that moment).
    # Nullable so pre-price legacy rows keep printing on bills (blank rate),
    # and so internal stock ledgers stay usable — new bill saves require it.
    rate = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Price per unit (₹) at the time of this entry.",
    )
    received_from = models.CharField(max_length=200)
    # Optional GST number of the SUPPLIER on this purchase bill (v1.2.13).
    # Every row of one bill gets the same value at save time; the printed
    # A4 purchase bill shows it under the party name when present.
    supplier_gstin = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Optional GSTIN of the supplier (e.g. 27ABCDE1234F1Z5).",
    )
    # Who recorded this entry. Reads are global (all roles see true stock
    # and every entry); edit/delete stay own-only via
    # EntryWriterRequiredMixin. NULL for pre-ownership legacy rows.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inward_entries",
        help_text="Staff member who recorded this entry.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]
        # NOTE: multiple entries per date are allowed (batches arrive through
        # the day, told apart by time). Each entry is unique per
        # site+material+date+time — enforced here at the DB level (foolproof
        # against races/direct saves) plus a friendly form-level message.
        constraints = [
            models.UniqueConstraint(
                fields=["site", "material", "date", "time"],
                name="unique_inward_per_site_material_datetime",
            ),
        ]
        # Ledger ordering/filtering at scale (1000s of rows): every ledger
        # query filters (site, material) and sorts (date, time). One
        # composite index serves both instead of relying on single-column
        # FK indexes.
        indexes = [
            models.Index(
                fields=["site", "material", "date", "time"],
                name="idx_inward_ledger",
            ),
        ]

    def __str__(self):
        return f"Inward: {self.material} - {self.qty} at {self.site}"

    def clean(self):
        # Backstop so bad quantities are rejected on EVERY path (app forms
        # have their own field-level check; this covers Django admin/shell).
        from django.core.exceptions import ValidationError
        if self.qty is not None:
            if self.qty <= 0:
                raise ValidationError(
                    {"qty": "Quantity must be greater than zero."}
                )
            if self.qty % 1 != 0:
                raise ValidationError(
                    {"qty": "Quantity must be a whole number (no decimals)."}
                )
        # Optional supplier GSTIN: trim + uppercase + 15-character shape
        # check on EVERY save path. Local import — entries.utils imports
        # this module at the top (circular otherwise).
        from .utils import normalize_gstin
        gstin = normalize_gstin(self.supplier_gstin)
        if gstin is None:
            raise ValidationError(
                {"supplier_gstin":
                 "This GSTIN looks wrong — it must be 15 characters like "
                 "27ABCDE1234F1Z5. Leave it blank if the supplier has none."}
            )
        if gstin:
            self.supplier_gstin = gstin

class OutwardEntry(models.Model):
    """
    Material SOLD from the shop (a sale to a customer, leaves stock).

    The same model covers all usage. Material only ever:
      1) Arrives at the shop (InwardEntry, a purchase)
      2) Leaves the shop (this model, a sale to a customer)

    The balance for (site, material) is simply:
        SUM(Inward.qty) - SUM(Outward.qty)
    (see entries.utils.balance_for)
    """

    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(default=DEFAULT_ENTRY_TIME)
    qty = models.DecimalField(max_digits=12, decimal_places=2)
    # Price snapshot at sale time (₹ per unit, before GST). Null for legacy
    # rows only — new sales always save a rate (the printed tax invoice
    # multiplies qty × rate and breaks the GST up from it).
    rate = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Sale price per unit (₹) at the time of this sale.",
    )
    # Shop sale: who bought it (walk-in customer name, contractor, bulk
    # order ref). Optional free text; blank means counter sale.
    customer = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Buyer name for shop sales (optional).",
    )
    # Optional GST number of the CUSTOMER (regular customers, v1.2.13).
    # NOT mandatory — walk-in sales stay blank. The sale billing screen
    # auto-recalls it when a customer billed with a GSTIN before is typed
    # again, and the printed A4 tax invoice shows it when present.
    customer_gstin = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Optional GSTIN of the buyer (regular customers only).",
    )
    # Which inward delivery this usage consumes from. PROTECT: a delivery
    # that has been consumed cannot be deleted (delete the outward rows
    # first). NULL for pre-link legacy rows.
    inward_entry = models.ForeignKey(
        InwardEntry,
        on_delete=models.PROTECT,
        related_name="outward_entries",
        null=True,
        blank=True,
        help_text="The inward delivery this material was used from.",
    )
    # Who recorded this entry. Reads are global; edit/delete stay own-only.
    # NULL for pre-ownership legacy rows.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_outward_entries",
        help_text="Staff member who recorded this entry.",
    )

    # Sub-location where the material was used. FK to SubLocation model.
    # Nullable: legacy rows (pre-sub-location, free-text used_at) migrate with NULL.
    sub_location = models.ForeignKey(
        "entries.SubLocation",
        on_delete=models.PROTECT,
        related_name="outward_entries",
        null=True,
        blank=True,
        help_text="Sub-location where the material was used (e.g. Banglo 1, Plot 5).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]
        verbose_name_plural = "Outward entries"
        # Multiple entries per date are allowed (batches through the day),
        # but the same place + time twice is a duplicate (double-submit
        # guard). Enforced at the DB level so concurrent saves cannot
        # double-insert; the form shows the friendly message first.
        constraints = [
            models.UniqueConstraint(
                fields=["site", "material", "date", "time", "sub_location"],
                name="unique_outward_per_site_material_datetime_place",
            ),
        ]
        # Same ledger-scale reasoning as InwardEntry above.
        indexes = [
            models.Index(
                fields=["site", "material", "date", "time"],
                name="idx_outward_ledger",
            ),
        ]

    def __str__(self):
        return f"Outward: {self.material} - {self.qty} ({self.site})"

    def clean(self):
        # Backstop so bad quantities/links are rejected on EVERY path (app
        # forms have field-level checks; this covers Django admin/shell).
        from django.core.exceptions import ValidationError
        if self.qty is not None:
            if self.qty <= 0:
                raise ValidationError(
                    {"qty": "Quantity must be greater than zero."}
                )
            if self.qty % 1 != 0:
                raise ValidationError(
                    {"qty": "Quantity must be a whole number (no decimals)."}
                )
        if self.inward_entry_id and self.site_id and self.material_id:
            try:
                parent = InwardEntry.objects.only(
                    "site_id", "material_id").filter(
                    pk=self.inward_entry_id).first()
            except Exception:
                parent = None
            if parent is not None and (
                    parent.site_id != self.site_id
                    or parent.material_id != self.material_id):
                raise ValidationError(
                    {"inward_entry":
                     "Selected delivery does not belong to "
                     "this site and material."}
                )
        if self.sub_location_id and self.site_id:
            try:
                sub_site = SubLocation.objects.filter(
                    pk=self.sub_location_id).values_list(
                    "site_id", flat=True).first()
            except Exception:
                sub_site = None
            if sub_site is not None and sub_site != self.site_id:
                raise ValidationError(
                    {"sub_location":
                     "Sub-location must belong to the same site."}
                )

class TransferEntry(models.Model):
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(default=DEFAULT_ENTRY_TIME)
    qty = models.DecimalField(max_digits=12, decimal_places=2)
    from_site = models.ForeignKey(
        Site, on_delete=models.PROTECT, related_name="transfers_out"
    )
    to_site = models.ForeignKey(
        Site, on_delete=models.PROTECT, related_name="transfers_in"
    )
    # Who recorded this transfer. NULL for pre-ownership legacy rows.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_transfer_entries",
        help_text="Staff member who recorded this transfer.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"Transfer: {self.material} - {self.qty} from {self.from_site} to {self.to_site}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.qty is not None:
            if self.qty <= 0:
                raise ValidationError(
                    {"qty": "Quantity must be greater than zero."}
                )
            if self.qty % 1 != 0:
                raise ValidationError(
                    {"qty": "Quantity must be a whole number (no decimals)."}
                )
        if self.from_site_id and self.to_site_id:
            if self.from_site_id == self.to_site_id:
                raise ValidationError(
                    "From site and To site must be different."
                )


def normalize_sub_location_name(value):
    """Free-text place names (owner decision — no format rules). Only
    trims whitespace; empty stays empty so callers can reject it."""
    return (value or "").strip()


class SubLocation(models.Model):
    """
    Sub-location within a Site (e.g. Banglo 1, Banglo 2, Plot 5, Tower A).
    Used to track material allocation and consumption at a granular level.
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="sub_locations")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text="Optional description of the sub-location")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["site__name", "name"]
        verbose_name_plural = "Sub-locations"
        # Case-insensitive uniqueness per site: "Banglo 1" and "banglo 1"
        # are the same place. Display keeps the user's typing; the DB
        # enforces Lower(name) so concurrent/direct saves cannot split one
        # place into two balances. (Replaces the old case-sensitive
        # unique_together — see migration.)
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "site",
                name="unique_sublocation_site_name_ci",
            ),
        ]

    def __str__(self):
        return f"{self.site.name} - {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        self.name = normalize_sub_location_name(self.name)
        if not self.name:
            raise ValidationError({"name": "Sub-location name is required."})

    def save(self, *args, **kwargs):
        # Strip names on EVERY save path (admin, shell, scripts).
        self.full_clean()
        super().save(*args, **kwargs)


class SubLocationAllocation(models.Model):
    """
    Allocation of an InwardEntry's quantity to a specific sub-location.
    When material arrives at a site, it gets split across sub-locations.
    """
    inward_entry = models.ForeignKey(
        InwardEntry,
        # PROTECT like outward entries: a delivery with allocations cannot
        # vanish silently (delete the allocations first). Same friendly
        # blocking message as outward links (see EntryDeleteMixin).
        on_delete=models.PROTECT,
        related_name="allocations",
        help_text="The inward delivery this allocation belongs to.",
    )
    sub_location = models.ForeignKey(
        SubLocation,
        on_delete=models.CASCADE,
        related_name="allocations",
        help_text="The sub-location receiving this allocation.",
    )
    qty_allocated = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity allocated to this sub-location from the inward entry.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["inward_entry__date", "inward_entry__time", "sub_location__name"]
        unique_together = ["inward_entry", "sub_location"]
        verbose_name_plural = "Sub-location allocations"

    def __str__(self):
        return f"{self.qty_allocated} of {self.inward_entry.material} → {self.sub_location}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Use *_id to avoid RelatedObjectDoesNotExist when the FK is unset
        # (e.g. ModelForm validation before inward_entry is assigned).
        if self.inward_entry_id and self.sub_location_id:
            if self.inward_entry.site_id != self.sub_location.site_id:
                raise ValidationError("Sub-location must belong to the same site as the inward entry.")
        if self.qty_allocated is not None:
            if self.qty_allocated <= 0:
                raise ValidationError(
                    {"qty_allocated": "Quantity must be greater than zero."}
                )
            if self.qty_allocated % 1 != 0:
                raise ValidationError(
                    {"qty_allocated": "Quantity must be a whole number (no decimals)."}
                )
        # Over-allocation guard: allocations against one delivery can never
        # exceed the delivery qty (exclude self when editing). The inward
        # edit view keeps its warn-only behaviour for pre-existing rows;
        # NEW allocations that would overshoot are blocked here.
        if self.inward_entry_id and self.qty_allocated is not None:
            from django.db.models import Sum
            siblings = SubLocationAllocation.objects.filter(
                inward_entry_id=self.inward_entry_id,
            )
            if self.pk:
                siblings = siblings.exclude(pk=self.pk)
            allocated = siblings.aggregate(
                t=Sum("qty_allocated"))["t"] or 0
            try:
                delivery_qty = InwardEntry.objects.filter(
                    pk=self.inward_entry_id).values_list(
                    "qty", flat=True).first()
            except Exception:
                delivery_qty = None
            if delivery_qty is not None and self.qty_allocated + allocated > delivery_qty:
                raise ValidationError(
                    {"qty_allocated":
                     f"Only {delivery_qty - allocated} left unallocated in "
                     f"this delivery (total {delivery_qty})."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """
    Who edited/deleted which entry, and when. Written automatically by the
    edit/delete views — users never create these manually.

    `entry_id` + `entry_summary` survive the delete: the snapshot is taken
    BEFORE the entry row is removed, so admin can still see what was deleted.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        EDIT = "edit", "Edited"
        DELETE = "delete", "Deleted"
        LOGIN = "login", "Logged in"
        EXPORT = "export", "Exported"

    class EntryType(models.TextChoices):
        INWARD = "inward", "Inward"
        OUTWARD = "outward", "Outward"
        TRANSFER = "transfer", "Transfer"
        STAFF = "staff", "Staff"
        REPORT = "report", "Report"
        SITE = "site", "Site"
        MATERIAL = "material", "Material"
        CATEGORY = "category", "Category"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Who performed the action.",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    entry_id = models.IntegerField(
        help_text="PK of the affected entry (kept even after delete)."
    )
    entry_summary = models.TextField(
        help_text="Human-readable snapshot at action time."
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.get_action_display()} {self.entry_type} #{self.entry_id} by {self.user}"