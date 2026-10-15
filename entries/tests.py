from django.core.exceptions import ValidationError
from django.test import TestCase

from materials.models import Category
from sites.models import Site

from .models import SubLocation


class SubLocationFreeTextTests(TestCase):
    """Owner rule: sub-location names are free text — no format checks.
    Anything non-empty saves as-is (trimmed)."""

    def test_anything_nonempty_saves(self):
        site = Site.objects.create(name="Test Site", location="Test")
        for name in ["Banglo 1", "14", "banglo 21 300ft",
                     "Banglo 2, Banglo 4", "Plot_5", "Banglo!"]:
            SubLocation.objects.create(site=site, name=name)
        self.assertEqual(SubLocation.objects.count(), 6)

    def test_empty_names_rejected(self):
        site = Site.objects.create(name="Test Site", location="Test")
        Category.objects.create(name="Test Cat")
        with self.assertRaises(ValidationError):
            SubLocation(site=site, name="   ").save()
        self.assertEqual(SubLocation.objects.count(), 0)


class SingleOutwardFormTests(TestCase):
    """One place per entry: free-text sub-location saves as-is.

    Form-level only (no save → no network, no uploads)."""

    def setUp(self):
        from accounts.models import User
        from materials.models import Material, SubCategory
        from .models import InwardEntry
        self.admin = User.objects.create_user(
            username="s_admin", password="1111", role=User.Role.ADMIN)
        self.site = Site.objects.create(name="S Site", location="S Loc")
        cat = Category.objects.create(name="S Cat")
        sub = SubCategory.objects.create(category=cat, name="S Sub")
        self.material = Material.objects.create(
            category=cat, sub_category=sub, name="S Mat", unit="nos")
        self.inward = InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-09-12",
            time="09:00", qty=100, received_from="TEST-SRC",
            created_by=self.admin)

    def _form(self, data):
        from .forms import OutwardEntryForm
        return OutwardEntryForm(
            data=data, site=self.site,
            material=self.material, user=self.admin)

    def _base_data(self, **over):
        d = {"date": "2026-09-12", "time": "10:00", "qty": "60",
             "sub_location": "Banglo 2",
             "inward_entry": str(self.inward.pk)}
        d.update(over)
        return d

    def test_valid_single_entry(self):
        form = self._form(self._base_data())
        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(
            form.cleaned_data["sub_location"].name, "Banglo 2")

    def test_free_text_sub_location_accepted(self):
        # Owner rule: sub-location is free text, no format checks —
        # "banglo 21 300ft" saves as-is.
        form = self._form(
            self._base_data(**{"sub_location": "banglo 21 300ft"}))
        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(
            form.cleaned_data["sub_location"].name, "banglo 21 300ft")

    def test_qty_over_delivery_rejected(self):
        form = self._form(self._base_data(**{"qty": "150"}))
        self.assertFalse(form.is_valid())
        self.assertIn("qty", form.errors)


class SingleOutwardViewTests(TestCase):
    """Full POST: one submit saves one entry with free-text sub-location."""

    def setUp(self):
        from accounts.models import User
        from materials.models import Material, SubCategory
        from .models import InwardEntry
        self.admin = User.objects.create_user(
            username="v_admin", password="1111", role=User.Role.ADMIN)
        self.site = Site.objects.create(name="V Site", location="V Loc")
        cat = Category.objects.create(name="V Cat")
        sub = SubCategory.objects.create(category=cat, name="V Sub")
        self.material = Material.objects.create(
            category=cat, sub_category=sub, name="V Mat", unit="nos")
        self.inward = InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-09-12",
            time="09:00", qty=100, received_from="TEST-SRC",
            created_by=self.admin)
        self.url = (f"/entries/sites/{self.site.id}/materials/"
                    f"{self.material.id}/outward/add/")
        self.client.force_login(self.admin)

    def test_single_place_saved(self):
        from .models import OutwardEntry
        from .utils import balance_for
        r = self.client.post(self.url, {
            "date": "2026-09-12", "time": "10:00", "qty": "60",
            "sub_location": "banglo 21 300ft",
            "inward_entry": str(self.inward.pk)})
        self.assertEqual(r.status_code, 302, r.content[:500])
        rows = list(OutwardEntry.objects.order_by("pk"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].sub_location.name, "banglo 21 300ft")
        self.assertEqual(int(rows[0].qty), 60)
        self.assertEqual(balance_for(self.site, self.material), 40)


class ExportMonthlyFilesTests(TestCase):
    """export_monthly_files writes Data/YYYY-MM/{sales,purchases}.xlsx
    with entry sheets plus per-material totals."""

    def test_current_month_files(self):
        import tempfile
        from pathlib import Path

        from django.core.management import call_command
        from django.test import override_settings
        from django.utils import timezone
        from accounts.models import User
        from materials.models import Material, SubCategory
        from .models import InwardEntry, OutwardEntry
        admin = User.objects.create_user(
            username="x_admin", password="1111", role=User.Role.ADMIN)
        site = Site.objects.create(name="X Site", location="X Loc")
        cat = Category.objects.create(name="X Cat")
        sub = SubCategory.objects.create(category=cat, name="X Sub")
        mat = Material.objects.create(
            category=cat, sub_category=sub, name="X Mat", unit="nos")
        today = timezone.localdate().isoformat()
        inw = InwardEntry.objects.create(
            site=site, material=mat, date=today, time="09:00:00", qty=100,
            received_from="SUP", created_by=admin)
        OutwardEntry.objects.create(
            site=site, material=mat, date=today, time="10:00:00", qty=30,
            customer="Buyer", inward_entry=inw, created_by=admin)
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(DATA_DIR=Path(tmp)):
                call_command("export_monthly_files")
            tag = timezone.localdate().strftime("%Y-%m")
            sales = Path(tmp) / tag / "sales.xlsx"
            purch = Path(tmp) / tag / "purchases.xlsx"
            self.assertTrue(sales.exists())
            self.assertTrue(purch.exists())
            from openpyxl import load_workbook
            ws = load_workbook(sales)["Sales"]
            self.assertEqual(ws["A1"].value, "Date")
            self.assertEqual(ws["D2"].value, 30)
            self.assertEqual(ws["F2"].value, "Buyer")
            tot = load_workbook(sales)["Totals"]
            self.assertEqual(tot["C2"].value, 30)
            wp = load_workbook(purch)["Purchases"]
            self.assertEqual(wp["D2"].value, 100)
