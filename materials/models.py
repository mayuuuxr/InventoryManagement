from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import functions as _functions


class ActiveManager(models.Manager):
    """Default manager: hides soft-deleted rows everywhere (lists, dropdowns,
    reports, balances). Use `all_objects` when deleted rows must be visible
    (Django admin, delete-guard counts)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class CatalogAuditMixin(models.Model):
    """Soft-delete + authorship for catalog models (Site/Category/SubCategory/
    Material). Also imported by sites/models.py — materials never imports
    sites, so this cannot cycle.

    Soft-delete keeps the row (and its pre-deletion name) in the database;
    entries pointing at it keep working at the DB level while the UI hides
    it. There is no restore UI — deletion is one-way by owner decision.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        help_text="Who created this row.",
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft-delete flag: hidden from the app, kept in the DB.",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
        help_text="Who soft-deleted this row.",
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this row was soft-deleted.",
    )

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, by_user):
        """Flag deleted (keeps the row + its name). Idempotent."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_by = by_user if by_user.is_authenticated else None
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_by", "deleted_at"])


class Category(CatalogAuditMixin, models.Model):
    """
    Groups materials into logical buckets (e.g. "Earthwork & Aggregates",
    "Cement & Masonry"). Helps with filtering and reporting as the material
    list grows past a screenful.
    """
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"
        # Names must be unique (case-insensitive) among LIVE rows only, so
        # a deleted name can be re-created fresh while history keeps it.
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_deleted=False),
                name="unique_category_name_active",
            ),
            models.UniqueConstraint(
                models.functions.Lower("name"),
                condition=models.Q(is_deleted=False),
                name="unique_category_name_active_ci",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        name = (self.name or "").strip()
        if not name:
            raise ValidationError({"name": "Name is required."})
        self.name = name
        dup = Category.all_objects.filter(
            name__iexact=name, is_deleted=False)
        if self.pk:
            dup = dup.exclude(pk=self.pk)
        if dup.exists():
            raise ValidationError(
                {"name": "A category with this name already exists."})


class SubCategory(CatalogAuditMixin, models.Model):
    """
    Middle grouping level: base material within a Category whose variants
    are tracked as separate Material rows (e.g. "Steel" with variants
    8mm/10mm/12mm/16mm, "Bricks Red" with variants 4 inch/6 inch).

    Materials that have no variants (Cement, Sand, Binding Wire, ...) skip
    this level and sit directly under a Category (Material.sub_category=None).
    """
    # PROTECT: same reasoning as Material.category — deleting a sub-category
    # that materials reference would orphan historical entries.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="sub_categories",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__name", "name"]
        verbose_name_plural = "Sub-categories"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_subcategory_per_category",
            ),
            models.UniqueConstraint(
                "category", _functions.Lower("name"),
                condition=models.Q(is_deleted=False),
                name="unique_subcategory_per_category_ci",
            ),
        ]

    def __str__(self):
        # Include the parent category so dropdowns are unambiguous.
        return f"{self.name} ({self.category.name})"

    def clean(self):
        super().clean()
        name = (self.name or "").strip()
        if not name:
            raise ValidationError({"name": "Name is required."})
        self.name = name
        if self.category_id:
            dup = SubCategory.all_objects.filter(
                category_id=self.category_id,
                name__iexact=name, is_deleted=False)
            if self.pk:
                dup = dup.exclude(pk=self.pk)
            if dup.exists():
                raise ValidationError(
                    {"name":
                     "This sub-category already exists in this category."})


class Material(CatalogAuditMixin, models.Model):
    # `category` stays the primary grouping field and source of truth, even
    # when `sub_category` is set. Rationale: materials without variants need a
    # category directly, and keeping one non-null FK avoids COALESCE-style
    # queries (category vs sub_category.category) in balance/report code.
    # Consistency (material.category == sub_category.category) is enforced
    # in clean() below.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    # Optional refinement. NULL = material sits directly under its Category.
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.PROTECT,
        related_name="materials",
        blank=True,
        null=True,
    )

    # Variant part only when sub_category exists (e.g. "8mm" under "Steel"),
    # full name otherwise (e.g. "Cement").
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=50)
    # Stock at or below this triggers the low-stock bell / report flags.
    # Per-material (cement runs out faster than binding wire). Default 10 —
    # keep in sync with entries.utils.LOW_STOCK_THRESHOLD (importing it here
    # would be circular: entries.models already imports this module).
    reorder_point = models.PositiveIntegerField(
        default=10,
        help_text="Alert when stock falls to this quantity or below.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__name", "sub_category__name", "name"]

    def clean(self):
        super().clean()
        if (
            self.sub_category_id
            and self.category_id
            and self.sub_category.category_id != self.category_id
        ):
            raise ValidationError(
                {
                    "sub_category": (
                        f"'{self.sub_category.name}' belongs to category "
                        f"'{self.sub_category.category.name}', which does not "
                        f"match this material's category."
                    )
                }
            )

    @property
    def display_name(self):
        """Unambiguous label: 'Steel > 8mm', or plain 'Cement' when ungrouped."""
        if self.sub_category_id and self.sub_category:
            return f"{self.sub_category.name} > {self.name}"
        return self.name

    def __str__(self):
        # display_name disambiguates variants that share a name across
        # sub-categories (e.g. "4 inch" under both Bricks Red and Bricks Fly).
        return f"{self.display_name} ({self.unit})"
