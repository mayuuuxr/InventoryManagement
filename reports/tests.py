from django.test import TestCase, override_settings

from accounts.models import User
from entries.models import InwardEntry, OutwardEntry
from materials.models import Category, Material, SubCategory
from sites.models import Site


@override_settings(ALLOWED_HOSTS=["testserver"])
class DateRangeReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="r_admin", password="1111", role=User.Role.ADMIN)
        self.site = Site.objects.create(name="R Site", location="R Loc")
        cat = Category.objects.create(name="R Cat")
        sub = SubCategory.objects.create(category=cat, name="R Sub")
        self.material = Material.objects.create(
            category=cat, sub_category=sub, name="R Mat", unit="nos")
        self.in_sep = InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-09-05",
            time="09:00", qty=100, received_from="R1", created_by=self.admin)
        self.in_oct = InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-10-05",
            time="09:00", qty=50, received_from="R2", created_by=self.admin)
        self.out_sep = OutwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-09-06",
            time="10:00", qty=30, inward_entry=self.in_sep,
            created_by=self.admin)
        self.client.force_login(self.admin)

    def test_monthly_range_filters_entries(self):
        r = self.client.get("/reports/monthly/?from=2026-09-01&to=2026-09-30")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Sep 1")
        self.assertEqual(r.context["inward_count"], 1)
        self.assertEqual(r.context["outward_count"], 1)

    def test_monthly_range_spanning_months(self):
        r = self.client.get("/reports/monthly/?from=2026-09-01&to=2026-10-31")
        self.assertEqual(r.context["inward_count"], 2)
        self.assertEqual(r.context["outward_count"], 1)

    def test_invalid_range_falls_back_to_month(self):
        # Backwards range is ignored — September picker applies.
        r = self.client.get(
            "/reports/monthly/?month=9&year=2026&from=2026-10-01&to=2026-09-01")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["inward_count"], 1)
        self.assertContains(r, "September")

    def test_consumption_range_totals(self):
        url = (f"/reports/material-consumption/?material={self.material.id}"
               f"&from=2026-09-01&to=2026-09-30")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total_inward"], 100)
        self.assertEqual(r.context["total_outward"], 30)
        # Balance stays all-time (100 + 50 - 30).
        self.assertEqual(r.context["balance"], 120)

    def test_monthly_export_with_range(self):
        r = self.client.get(
            "/reports/monthly/export/?from=2026-09-01&to=2026-09-30")
        self.assertEqual(r.status_code, 200)
        self.assertIn("2026-09-01_to_2026-09-30",
                      r["Content-Disposition"])

    def test_consumption_export_with_range(self):
        r = self.client.get(
            f"/reports/material-consumption/export/?material={self.material.id}"
            f"&from=2026-09-01&to=2026-09-30")
        self.assertEqual(r.status_code, 200)
        self.assertIn("2026-09-01_to_2026-09-30",
                      r["Content-Disposition"])
