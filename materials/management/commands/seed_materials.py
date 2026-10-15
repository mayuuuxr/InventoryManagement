"""
Seed the materials app with the initial TEST/TEMPORARY 3-level catalog:
Category → SubCategory (optional) → Material (variant).

Re-runnable: WIPES all existing Category/SubCategory/Material rows first
(deleting materials cascades to their Inward/Outward/Transfer entries —
acceptable because this is still test data), then rebuilds from SEED_DATA
below. Running it twice leaves the DB in the same state.

Run with:
    python manage.py seed_materials
"""
from django.core.management.base import BaseCommand

from materials.models import Category, Material, SubCategory


# Structure:
#   { "Category Name": {
#         "subcategories": { "Sub Name": [("variant", "unit"), ...], ... },
#         "materials": [("full name", "unit"), ...],   # no sub-category
#   }, ... }
SEED_DATA = {
    "Earthwork & Aggregates": {
        "subcategories": {
            "Gitti": [
                ("20mm", "ft"),
                ("40mm", "ft"),
                ("80mm", "ft"),
                ("Dust", "ft"),
            ],
        },
        "materials": [
            ("Murrum", "ft"),
            ("Sand", "ft"),
            ("Fly Ash", "ft"),
        ],
    },
    "Cement & Masonry": {
        "subcategories": {
            "Bricks Red": [
                ("4 inch", "pieces"),
                ("6 inch", "pieces"),
            ],
            "Bricks Fly": [
                ("4 inch", "pieces"),
                ("6 inch", "pieces"),
            ],
        },
        "materials": [
            ("Cement", "bags"),
        ],
    },
    "Steel & Reinforcement": {
        "subcategories": {
            "Steel": [
                ("8mm", "kg"),
                ("10mm", "kg"),
                ("12mm", "kg"),
                ("16mm", "kg"),
            ],
        },
        "materials": [
            ("Binding Wire", "kg"),
        ],
    },
}


class Command(BaseCommand):
    help = "Wipe and reseed the materials catalog (TEST data, 3-level hierarchy)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Required to actually wipe. Without it, dry-run only.")

    def handle(self, *args, **options):
        from django.conf import settings
        from entries.models import InwardEntry, OutwardEntry, TransferEntry
        if not settings.DEBUG and not options.get("force"):
            raise SystemExit(
                "Refusing to seed with DEBUG=False without --force.")
        if ((InwardEntry.objects.exists() or OutwardEntry.objects.exists()
                or TransferEntry.objects.exists())
                and not options.get("force")):
            self.stdout.write(self.style.WARNING(
                "Entries exist — dry-run only. Re-run with --force to wipe "
                "catalog AND entry history."))
            return
        if not options.get("force"):
            self.stdout.write(
                "Dry-run: would wipe and reseed the catalog. "
                "Pass --force to apply.")
            return
        # Wipe in FK-safe order. Material delete cascades to entry rows.
        n_mats = Material.objects.count()
        n_subs = SubCategory.objects.count()
        n_cats = Category.objects.count()
        Material.objects.all().delete()
        SubCategory.objects.all().delete()
        Category.objects.all().delete()
        self.stdout.write(
            f"Cleared {n_mats} materials, {n_subs} sub-categories, "
            f"{n_cats} categories (entry rows cascade-deleted with materials)."
        )
        self.stdout.write("")

        for cat_name, groups in SEED_DATA.items():
            cat = Category.objects.create(name=cat_name)
            self.stdout.write(f"  + Category: {cat_name}")

            for sub_name, variants in groups.get("subcategories", {}).items():
                sub = SubCategory.objects.create(category=cat, name=sub_name)
                self.stdout.write(f"    + Sub-category: {sub_name}")
                for variant, unit in variants:
                    Material.objects.create(
                        category=cat, sub_category=sub, name=variant, unit=unit
                    )
                    self.stdout.write(f"      + Material: {variant} ({unit})")

            for mat_name, unit in groups.get("materials", []):
                Material.objects.create(
                    category=cat, sub_category=None, name=mat_name, unit=unit
                )
                self.stdout.write(f"    + Material: {mat_name} ({unit})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. DB now has {Category.objects.count()} categories, "
            f"{SubCategory.objects.count()} sub-categories and "
            f"{Material.objects.count()} materials."
        ))
