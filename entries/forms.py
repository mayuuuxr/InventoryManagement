from django import forms
from django.conf import settings

from .models import InwardEntry, OutwardEntry, SubLocation, SubLocationAllocation
from .utils import balance_for, fmt_qty


# Time input formats shared by both Inward and Outward forms.
ENTRY_TIME_INPUT_FORMATS = list(settings.TIME_INPUT_FORMATS) + [
    "%H:%M:%S.%f",
    "%H:%M:%S",
    "%H:%M",
    "%I:%M %p",
    "%I:%M%p",
    "%I %p",
    "%I:%M",
]


# Rate per unit (₹, taxes added later from the material's GST%): printed on
# the A4 tax invoice. Decimals allowed (₹11.50), never negative.
RATE_WIDGET = {
    "placeholder": "e.g. 250 or 250.00",
    "step": "0.01",
    "min": "0",
    "inputmode": "decimal",
    "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
             "text-charcoal placeholder:text-muted focus:outline-none "
             "focus:border-accent focus:ring-2 focus:ring-accent/20",
}


def entry_time_field(required=True):
    return forms.TimeField(
        required=required,
        input_formats=ENTRY_TIME_INPUT_FORMATS,
        widget=forms.TimeInput(attrs={
            "type": "time",
            "placeholder": "02:30 PM",
            "size": 10,
            "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
        }),
    )


def check_whole_qty(qty):
    """Stock quantities are whole numbers in this industry — reject decimals."""
    if qty is not None and qty % 1 != 0:
        raise forms.ValidationError("Quantity must be a whole number (no decimals).")


class InwardEntryForm(forms.ModelForm):
    # nibba: no photo entry at all (no upload fields, no photo columns).
    time = entry_time_field()

    class Meta:
        model = InwardEntry
        fields = ("date", "time", "qty", "received_from", "rate")
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
                "autofocus": True,
            }),
            "qty": forms.NumberInput(attrs={
                "placeholder": "e.g. 100",
                "step": "1",
                "min": "0",
                "inputmode": "numeric",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
                          "text-charcoal placeholder:text-muted focus:outline-none "
                          "focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "received_from": forms.TextInput(attrs={
                "placeholder": "e.g. ABC Traders",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "rate": forms.NumberInput(attrs=RATE_WIDGET),
        }

    def __init__(self, *args, site=None, material=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = site
        self.material = material

    def clean_qty(self):
        qty = self.cleaned_data.get("qty")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        check_whole_qty(qty)
        return qty

    def clean(self):
        cleaned = super().clean()
        # Multiple entries per date ARE allowed (several batches a day), but
        # the time must differ — same date + same time counts as a duplicate.
        inward_date = cleaned.get("date")
        inward_time = cleaned.get("time")
        if inward_date and inward_time and self.site and self.material:
            from .models import InwardEntry
            dup = InwardEntry.objects.filter(
                site=self.site, material=self.material,
                date=inward_date, time=inward_time,
            )
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                self.add_error(
                    "time",
                    f"An inward entry for {self.material.display_name} on "
                    f"{inward_date} at {inward_time.strftime('%I:%M %p').lstrip('0')} "
                    f"already exists at {self.site.name}. Entries on the same "
                    f"date must have different times.",
                )
        return cleaned


# --- Outward form ----------------------------------------------------------

class OutwardEntryForm(forms.ModelForm):
    # nibba: no photo entry at all (no upload fields, no photo columns).
    time = entry_time_field()
    # Combo field: free text with datalist suggestions (NOT a dropdown).
    # clean_sub_location() resolves the typed name to a SubLocation instance
    # (existing match or auto-created), so the FK below always gets an
    # instance and the rest of the form (clean(), views, audit) is untouched.
    sub_location = forms.CharField(
        label="Sub-location (where was it used)",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Banglo 21",
            "list": "sublocation-suggestions",
            "autocomplete": "off",
            "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
                      "text-charcoal placeholder:text-muted focus:outline-none "
                      "focus:border-accent focus:ring-2 focus:ring-accent/20",
        }),
    )

    class Meta:
        model = OutwardEntry
        # sub_location rides as a plain CharField (free text) on the form;
        # it is resolved/created in save() AFTER validation, so failed
        # submits never leave orphan SubLocation rows. Excluded from Meta
        # so ModelForm.construct_instance never assigns a raw string to
        # the FK descriptor.
        fields = ("date", "time", "qty", "inward_entry", "rate")
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
                "autofocus": True,
            }),
            "qty": forms.NumberInput(attrs={
                "placeholder": "e.g. 50",
                "step": "1",
                "min": "0",
                "inputmode": "numeric",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
                          "text-charcoal placeholder:text-muted focus:outline-none "
                          "focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "inward_entry": forms.Select(attrs={
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "rate": forms.NumberInput(attrs=RATE_WIDGET),
        }

    def __init__(self, *args, site=None, material=None, user=None, **kwargs):
        from django.db.models import Sum

        super().__init__(*args, **kwargs)
        self.site = site
        self.material = material
        # Model allows blank only for legacy rows (pre-sub-location migration);
        # every new entry must name a sub-location (existing or new).
        self.fields["sub_location"].required = True
        # Edit forms show the current name (not the PK) in the text input.
        if self.instance.pk and self.instance.sub_location_id:
            self.initial["sub_location"] = self.instance.sub_location.name
        # Source delivery picker: this site+material's inwards with remaining
        # balance (FIFO, oldest first). Every role picks from ALL deliveries
        # (owner decision Sep 2026: all entries visible to everyone).
        # Fully-used deliveries are excluded — except
        # the entry's own linked delivery on edit (else old entries could
        # never be re-saved). Required going forward (legacy rows with none
        # must pick on edit).
        self.fields["inward_entry"].required = True
        self.fields["inward_entry"].label = "From inward delivery"
        inward_qs = InwardEntry.objects.none()
        if site and material:
            inward_qs = InwardEntry.objects.filter(
                site=site, material=material)
        # Per-delivery remaining (ONE aggregate query): drop fully-used
        # deliveries, oldest first. Own linked delivery always stays.
        from django.db.models import Sum as _Sum2
        _used = {
            row["inward_entry"]: row["t"]
            for row in (
                OutwardEntry.objects.filter(inward_entry__in=inward_qs)
                .values("inward_entry").annotate(t=_Sum2("qty"))
            )
        }
        _own_id = (self.instance.inward_entry_id
                   if self.instance.pk else None)
        # values_list (pk + qty only): with 1000s of deliveries this must
        # not hydrate full model rows just to compare remaining stock.
        _kept = [
            pk for pk, qty in inward_qs.values_list("pk", "qty")
            if (qty - (_used.get(pk) or 0)) > 0 or pk == _own_id
        ]
        inward_qs = InwardEntry.objects.filter(pk__in=_kept).order_by(
            "date", "time")
        self.fields["inward_entry"].queryset = inward_qs
        if not _kept:
            self.fields["inward_entry"].empty_label = (
                "No available inward deliveries")
        # Show remaining per delivery so staff pick one with enough stock:
        # "Sep 5 · 10:00 AM · 200 bags (160 left)". Reuses the aggregate
        # above (restricted to kept deliveries) — no second query.
        used_map = {k: v for k, v in _used.items() if k in set(_kept)}
        unit = material.unit if material else ""
        field = self.fields["inward_entry"]
        field.label_from_instance = lambda obj, _u=unit, _m=used_map: (
            f"{obj.date.strftime('%b %d, %Y')} · "
            f"{obj.time.strftime('%I:%M %p').lstrip('0')} · "
            f"{fmt_qty(obj.qty)} {_u} "
            f"({fmt_qty(obj.qty - (_m.get(obj.pk) or 0))} left)"
        )

    def clean_qty(self):
        qty = self.cleaned_data.get("qty")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        check_whole_qty(qty)
        return qty

    def _resolve_sub_location_name(self, raw, create=False):
        """Shared resolve for one place name: free text, NO format rules
        (owner decision — staff type whatever, saved as-is). Match an
        existing SubLocation at this site (case-insensitive, keeps stored
        casing). With create=False returns an UNSAVED instance for new
        names (no DB write, so failed submits leave no orphans);
        save() persists it via get_or_create (create=True)."""
        name = (raw or "").strip()
        if not name:
            raise forms.ValidationError("Sub-location is required.")
        if len(name) > 100:
            raise forms.ValidationError(
                "Sub-location name is too long (max 100 characters).")
        if not self.site:
            raise forms.ValidationError("Sub-location is required.")
        obj = (
            SubLocation.objects
            .filter(site=self.site, name__iexact=name)
            .first()
        )
        if obj is not None:
            return obj
        if create:
            obj, _ = SubLocation.objects.get_or_create(
                site=self.site, name__iexact=name,
                defaults={"name": name},
            )
            fetched = SubLocation.objects.filter(
                site=self.site, name__iexact=name).first()
            return fetched or obj
        # Unsaved stand-in: .name works for labels/tests; save() persists.
        return SubLocation(site=self.site, name=name)

    def clean_sub_location(self):
        """
        Validate the typed name and resolve to a SubLocation instance:
        existing row when matched, otherwise an unsaved instance that
        save() persists after the whole form validates (no orphans on
        failed submits).
        """
        raw = self.cleaned_data.get("sub_location")
        if isinstance(raw, SubLocation):
            return raw
        raw = (raw or "").strip()
        if not raw:
            raise forms.ValidationError("Sub-location is required.")
        obj = self._resolve_sub_location_name(raw, create=False)
        # NOTE: do NOT touch self.initial here. changed_data compares initial
        # (the name string set in __init__) against the raw submitted string,
        # so an unchanged name already stays quiet in the audit log.
        return obj

    def save(self, commit=True):
        """Persist a new sub-location (if any) only on a fully-valid save."""
        sub = self.cleaned_data.get("sub_location")
        if isinstance(sub, SubLocation) and sub.pk is None:
            obj = self._resolve_sub_location_name(sub.name, create=True)
            self.instance.sub_location = obj
            self.cleaned_data["sub_location"] = obj
        elif isinstance(sub, SubLocation):
            self.instance.sub_location = sub
        return super().save(commit=commit)

    def clean(self):
        cleaned = super().clean()
        qty = cleaned.get("qty")
        sub_location = cleaned.get("sub_location")
        outward_date = cleaned.get("date")
        # --- single-row path: one place per entry ---
        # Stock guardrail is SITE-level: any inward at this site counts,
        # whether or not it was split into sub-location allocations.
        # (Sub-location allocation records stay informational — requiring an
        # allocation before every outward blocked real usage, e.g. a fresh
        # 1000-bag inward showing "only 80 available".) The per-delivery
        # remaining check below still applies on top.
        if qty and self.site and self.material and sub_location:
            from .utils import balance_for
            available = balance_for(self.site, self.material)
            if self.instance.pk:
                available += self.instance.qty
            if qty > available:
                self.add_error(
                    "qty",
                    f"Only {fmt_qty(available)} {self.material.unit} available for {self.material.display_name} at {self.site.name}. You entered {fmt_qty(qty)} {self.material.unit}.",
                )
        # Source delivery: must belong to this site+material, and must still
        # have enough unconsumed quantity for this outward entry.
        inward_entry = cleaned.get("inward_entry")
        if inward_entry:
            if (self.site and inward_entry.site_id != self.site.id) or (
                    self.material and inward_entry.material_id != self.material.id):
                self.add_error(
                    "inward_entry",
                    "Selected delivery does not belong to this site and material.",
                )
            elif qty:
                from .utils import inward_remaining
                exclude = self.instance.pk if self.instance.pk else None
                # When editing without changing delivery, the row's own qty
                # is part of "used" — exclude it like the balance check does.
                remaining = inward_remaining(inward_entry, exclude_pk=exclude)
                if qty > remaining:
                    self.add_error(
                        "qty",
                        f"Only {fmt_qty(remaining)} {self.material.unit} left in the "
                        f"selected delivery ({inward_entry.date.strftime('%b %d, %Y')}). "
                        f"You entered {fmt_qty(qty)} {self.material.unit}.",
                    )
        # Multiple entries per date ARE allowed (several batches a day), but
        # the same place + time twice counts as a duplicate (double-submit
        # guard + Saving-lock already stop accidental double taps; splits at
        # different places may share one time).
        dup_date = cleaned.get("date")
        dup_time = cleaned.get("time")
        if dup_date and dup_time and self.site and self.material:
            from .models import OutwardEntry, SubLocation
            dup = OutwardEntry.objects.filter(
                site=self.site, material=self.material,
                date=dup_date, time=dup_time,
            )
            from django.db.models import Q as _Q
            if isinstance(sub_location, SubLocation) and sub_location.pk:
                dup = dup.filter(sub_location=sub_location)
            elif isinstance(sub_location, SubLocation):
                # Unsaved (new) place name: match existing rows
                # case-insensitively so a retry after a failed submit still
                # warns; no DB write here.
                dup = dup.filter(
                    _Q(sub_location__site=self.site,
                       sub_location__name__iexact=sub_location.name))
            elif isinstance(sub_location, str) and sub_location:
                dup = dup.filter(
                    _Q(sub_location__site=self.site,
                       sub_location__name__iexact=sub_location))
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                _place = (
                    sub_location.name if isinstance(
                        sub_location, SubLocation)
                    else (sub_location or self.site.name))
                self.add_error(
                    "time",
                    f"An outward entry for {self.material.display_name} on "
                    f"{dup_date} at {dup_time.strftime('%I:%M %p').lstrip('0')} "
                    f"already exists at {_place}. "
                    f"Same place + same time counts as a duplicate.",
                )
        # Time validation: outward cannot be before inward on same date
        outward_time = cleaned.get("time")
        outward_date = cleaned.get("date")
        if outward_time and outward_date and sub_location and self.material:
            from .models import InwardEntry
            latest_inward = InwardEntry.objects.filter(
                site=self.site,
                material=self.material,
                date=outward_date,
            ).order_by("-time").first()
            if latest_inward and outward_time < latest_inward.time:
                self.add_error(
                    "time",
                    f"Outward time ({outward_time.strftime('%I:%M %p')}) cannot be earlier than latest inward ({latest_inward.time.strftime('%I:%M %p')}) for {self.material.display_name} on {outward_date}."
                )
        return cleaned


# --- SubLocation form ------------------------------------------------------

class SubLocationForm(forms.ModelForm):
    class Meta:
        model = SubLocation
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. Banglo 1, Plot 5",
                "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "description": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Optional description",
                "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
        }

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Site comes from the view (URL), not the form — needed for the
        # case-insensitive duplicate check below.
        self.site = site or getattr(self.instance, "site", None)

    def clean_name(self):
        from .models import normalize_sub_location_name
        name = normalize_sub_location_name(self.cleaned_data.get("name"))
        if not name:
            raise forms.ValidationError("Sub-location name is required.")
        # Case-insensitive duplicate within the site ("Banglo 1" == "banglo 1").
        # The DB constraint is the final backstop; this gives a friendly error.
        if self.site is not None:
            dup = SubLocation.objects.filter(
                site=self.site, name__iexact=name)
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError(
                    f"'{name}' already exists at this site (names are "
                    f"case-insensitive).")
        return name


# --- SubLocationAllocation form --------------------------------------------

class SubLocationAllocationForm(forms.ModelForm):
    class Meta:
        model = SubLocationAllocation
        fields = ("sub_location", "qty_allocated")
        widgets = {
            "qty_allocated": forms.NumberInput(attrs={
                "placeholder": "e.g. 100",
                "step": "1",
                "min": "0",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
        }

    def __init__(self, *args, inward_entry=None, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.inward_entry = inward_entry
        # Pre-assign the FK on new instances so model-level clean()/save()
        # see it even before the view sets it explicitly.
        if inward_entry is not None and self.instance.pk is None:
            self.instance.inward_entry = inward_entry
        if site:
            self.fields["sub_location"].queryset = SubLocation.objects.filter(site=site)
        else:
            self.fields["sub_location"].queryset = SubLocation.objects.none()

    def clean_qty_allocated(self):
        qty = self.cleaned_data.get("qty_allocated")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        check_whole_qty(qty)
        return qty

    def clean(self):
        cleaned = super().clean()
        sub_location = cleaned.get("sub_location")
        qty = cleaned.get("qty_allocated")
        if self.inward_entry and sub_location and qty:
            if self.inward_entry.site_id != sub_location.site_id:
                raise forms.ValidationError("Sub-location must belong to the same site as the inward entry.")
            from django.db.models import Sum
            total = SubLocationAllocation.objects.filter(
                inward_entry=self.inward_entry
            ).aggregate(total=Sum("qty_allocated"))["total"] or 0
            # Exclude this row when editing so it doesn't double-count itself.
            # Fetch the saved DB value (instance already holds the new qty).
            if self.instance.pk:
                saved = SubLocationAllocation.objects.filter(
                    pk=self.instance.pk
                ).values_list("qty_allocated", flat=True).first() or 0
                total_excluding_self = total - saved
            else:
                total_excluding_self = total
            if qty + total_excluding_self > self.inward_entry.qty:
                raise forms.ValidationError(
                    f"Total allocated ({fmt_qty(qty + total_excluding_self)}) exceeds "
                    f"inward quantity ({fmt_qty(self.inward_entry.qty)})."
                )
        return cleaned


# --- Shop quick forms (single-shop front doors) ------------------------------
#
# Purchase = stock bought (inward). Sale = stock sold to a customer
# (outward). No site picker: the single shop site applies automatically.
# A sale never asks for a delivery: it deducts FIFO from the oldest
# inward with stock left. Bulk and single orders are both just a qty.

QTY_WIDGET = {
    "placeholder": "e.g. 100",
    "step": "1",
    "min": "0",
    "inputmode": "numeric",
    "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
             "text-charcoal placeholder:text-muted focus:outline-none "
             "focus:border-accent focus:ring-2 focus:ring-accent/20",
}

DATE_WIDGET = {
    "type": "date",
    "class": "w-full min-w-0 max-w-full block px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
}


def _material_choices():
    from materials.models import Material
    return Material.objects.select_related(
        "category", "sub_category").order_by(
        "category__name", "sub_category__name", "name")


class PurchaseForm(forms.ModelForm):
    time = entry_time_field()
    material = forms.ModelChoiceField(
        queryset=_material_choices(),
        label="Material",
        widget=forms.Select(attrs={
            "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
        }),
    )

    class Meta:
        model = InwardEntry
        fields = ("material", "date", "time", "qty", "rate", "received_from")
        widgets = {
            "date": forms.DateInput(attrs=DATE_WIDGET),
            "qty": forms.NumberInput(attrs=QTY_WIDGET),
            "received_from": forms.TextInput(attrs={
                "placeholder": "e.g. Sharma Traders",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "rate": forms.NumberInput(attrs=RATE_WIDGET),
        }

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = site
        self.fields["material"].label_from_instance = (
            lambda obj: f"{obj.display_name} ({obj.unit})")
        # Purchase slips print with money now — a rate is required on every
        # new quick purchase (owner, Oct 2026); the ledger edit form keeps
        # it optional for fixing up pre-price legacy rows.
        self.fields["rate"].label = "Rate per unit (₹, before GST)"
        self.fields["rate"].required = True

    def clean_qty(self):
        qty = self.cleaned_data.get("qty")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        check_whole_qty(qty)
        return qty

    def clean(self):
        cleaned = super().clean()
        # Same duplicate rule as the ledger form: one row per
        # site + material + date + time (time tells batches apart).
        d, t, m = (cleaned.get("date"), cleaned.get("time"),
                   cleaned.get("material"))
        if d and t and m and self.site:
            dup = InwardEntry.objects.filter(
                site=self.site, material=m, date=d, time=t)
            if dup.exists():
                self.add_error(
                    "time",
                    f"{m.display_name} already has an entry on {d} at "
                    f"{t.strftime('%I:%M %p').lstrip('0')}. "
                    f"Change the time slightly.",
                )
        return cleaned


class SaleForm(forms.ModelForm):
    time = entry_time_field()
    material = forms.ModelChoiceField(
        queryset=_material_choices(),
        label="Material",
        widget=forms.Select(attrs={
            "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
        }),
    )

    class Meta:
        model = OutwardEntry
        fields = ("material", "date", "time", "qty", "rate", "customer")
        widgets = {
            "date": forms.DateInput(attrs=DATE_WIDGET),
            "qty": forms.NumberInput(attrs=QTY_WIDGET),
            "customer": forms.TextInput(attrs={
                "placeholder": "Buyer name (optional, walk-in ok)",
                "class": "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm text-charcoal placeholder:text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20",
            }),
            "rate": forms.NumberInput(attrs=RATE_WIDGET),
        }

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = site
        self.fields["material"].label_from_instance = (
            lambda obj: f"{obj.display_name} ({obj.unit})")
        self.fields["customer"].required = False
        # Sale bills print with money now — a rate is required on every new
        # quick sale (owner, Oct 2026). Ledger-style edits of old rows
        # (InwardEntryForm/OutwardEntryForm path) keep rate optional.
        self.fields["rate"].label = "Rate per unit (₹, before GST)"
        self.fields["rate"].required = True

    def clean_qty(self):
        qty = self.cleaned_data.get("qty")
        if qty is None:
            return qty
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        check_whole_qty(qty)
        return qty

    def clean(self):
        cleaned = super().clean()
        m, qty = cleaned.get("material"), cleaned.get("qty")
        if m and qty and self.site:
            available = balance_for(self.site, m)
            if qty > available:
                self.add_error(
                    "qty",
                    f"Only {fmt_qty(available)} {m.unit} in stock for "
                    f"{m.display_name}. You entered {fmt_qty(qty)}.",
                )
        return cleaned

    def pick_fifo_delivery(self):
        """Oldest inward of this site+material with stock left (or None)."""
        from .models import InwardEntry
        from .utils import inward_remaining

        for inw in InwardEntry.objects.filter(
                site=self.site, material=self.instance.material
                ).order_by("date", "time", "id"):
            if inward_remaining(inw) > 0:
                return inw
        return None


