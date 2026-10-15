from django import forms

from .models import Category, Material, SubCategory


# Shared Tailwind classes for form inputs — keep all inputs visually consistent.
INPUT_CLASS = (
    "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
    "text-charcoal placeholder:text-muted focus:outline-none "
    "focus:border-accent focus:ring-2 focus:ring-accent/20"
)
SELECT_CLASS = INPUT_CLASS  # <select> uses the same classes in our design


class MaterialForm(forms.ModelForm):
    # Allow creating a brand-new category from the same form (optional).
    # If a category is selected from the dropdown, this is ignored.
    new_category = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "placeholder": "Or type a new category name",
        }),
        help_text="Optional. Leave blank to use the category selected above.",
    )
    # Same pattern for sub-categories: picked dropdown wins, else create
    # under the material's final category (dropdown or newly typed one).
    new_sub_category = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "placeholder": "Or type a new sub-category name",
        }),
        help_text="Optional. Leave blank to use the sub-category selected above.",
    )

    class Meta:
        model = Material
        fields = ("category", "sub_category", "name", "unit", "reorder_point")
        widgets = {
            "category": forms.Select(attrs={"class": SELECT_CLASS}),
            "sub_category": forms.Select(attrs={"class": SELECT_CLASS}),
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. 8mm (variant) or Cement (full name)",
                "autofocus": True,
                "class": INPUT_CLASS,
            }),
            "unit": forms.TextInput(attrs={
                "placeholder": "e.g. kg, ft, bags, pieces",
                "class": INPUT_CLASS,
            }),
            "reorder_point": forms.NumberInput(attrs={
                "placeholder": "e.g. 20",
                "min": "0",
                "step": "1",
                "inputmode": "numeric",
                "class": INPUT_CLASS,
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Request user, used to stamp + audit auto-created categories/
        # sub-categories below. Views pass it; admin/CLI callers may not.
        self._user = user
        # Auto-created rows this clean() pass, for the view to audit.
        self._auto_created = {"category": None, "sub_category": None}
        # Style the "new_category" / "new_sub_category" text inputs
        self.fields["new_category"].widget.attrs.setdefault("class", INPUT_CLASS)
        self.fields["new_sub_category"].widget.attrs.setdefault("class", INPUT_CLASS)
        # Category dropdown is optional at field level: clean() enforces
        # "dropdown OR typed name". (Required=True would reject the empty
        # dropdown before clean() ever sees new_category/new_sub_category.)
        self.fields["category"].required = False
        # "+ Add New …" pseudo-options at the end of each dropdown. They are
        # UI-only: the template JS swaps the select back to "" on submit (so
        # "__new__" never reaches validation) and reveals the matching text
        # input instead. clean() below then creates/gets the typed record.
        self.fields["category"].choices = [
            *self.fields["category"].choices, ("__new__", "+ Add New Category"),
        ]
        self.fields["sub_category"].choices = [
            *self.fields["sub_category"].choices,
            ("__new__", "+ Add New Sub-category"),
        ]
        # Friendlier empty options for the dropdowns
        self.fields["category"].empty_label = "— select category —"
        self.fields["sub_category"].empty_label = "— no sub-category —"
        self.fields["sub_category"].help_text = (
            "Optional. Pick a sub-category (e.g. Steel) when this material is "
            "a variant — then type only the variant part as the name (e.g. 8mm)."
        )

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        sub_category = cleaned.get("sub_category")
        new_cat = (cleaned.get("new_category") or "").strip()

        # A chosen sub-category is authoritative: the material's category must
        # match the sub-category's category (mirrors Material.clean()).
        if sub_category:
            cleaned["category"] = sub_category.category
            category = sub_category.category

        if not category and not new_cat:
            raise forms.ValidationError(
                "Select an existing category OR type a new category name."
            )

        # If user typed a new category, create-or-fetch it and use that.
        # (Only reachable when no sub-category was picked.) Lookups skip
        # soft-deleted rows so a deleted name is re-created fresh; the view
        # audits anything actually created (stashed below).
        if new_cat and not sub_category:
            cat = Category.objects.filter(
                name=new_cat, is_deleted=False).first()
            if cat is None:
                cat = Category.objects.create(
                    name=new_cat, created_by=getattr(self, "_user", None))
                self._auto_created["category"] = cat
            cleaned["category"] = cat
            category = cat

        # Same for a new sub-category: parent is the material's final
        # category (dropdown-picked or just created above). A picked
        # sub-category always wins over typed text.
        new_sub = (cleaned.get("new_sub_category") or "").strip()
        if new_sub and not sub_category and category:
            sub = SubCategory.objects.filter(
                category=category, name=new_sub, is_deleted=False).first()
            if sub is None:
                sub = SubCategory.objects.create(
                    category=category, name=new_sub,
                    created_by=getattr(self, "_user", None))
                self._auto_created["sub_category"] = sub
            cleaned["sub_category"] = sub
        return cleaned
