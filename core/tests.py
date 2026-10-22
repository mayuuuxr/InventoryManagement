"""Regression tests for production pages added in the Phase 0-3 audit.

Covers: help center per role, custom error pages (403/404 + standalone
500/400), login return-path safety (?next=), nav/offline/draft markers,
entry validation with no uploads and no network in tests.
"""
from django.template import loader
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from entries.models import InwardEntry, OutwardEntry, SubLocation, SubLocationAllocation
from materials.models import Category, Material, SubCategory
from sites.models import Site


@override_settings(ALLOWED_HOSTS=["testserver"])
class AuditTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="t_admin", password="1111", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user(
            username="t_staff", password="2222", role=User.Role.STAFF)
        cls.manager = User.objects.create_user(
            username="t_mgr", password="3333", role=User.Role.MANAGER)
        cls.site = Site.objects.create(name="T Site", location="T Loc")
        cat = Category.objects.create(name="T Cat")
        sub = SubCategory.objects.create(category=cat, name="T Sub")
        cls.material = Material.objects.create(
            category=cat, sub_category=sub, name="T Mat", unit="nos")

    def login(self, user):
        self.client.force_login(user)


class HelpPageTests(AuditTestBase):
    def test_anon_redirects_to_login(self):
        r = self.client.get("/help/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_admin_help_has_no_owner_section(self):
        self.login(self.admin)
        r = self.client.get("/help/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Owner tasks")

    def test_staff_sees_staff_section_only(self):
        self.login(self.staff)
        r = self.client.get("/help/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Edit or delete your own entries only")
        self.assertNotContains(r, "Owner tasks")

    def test_manager_sees_full_access_section(self):
        self.login(self.manager)
        r = self.client.get("/help/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Managers have full access")
        self.assertNotContains(r, "Owner tasks")

    def test_manager_can_open_manage_staff(self):
        # Managers hold admin powers: staff list + member pages open (was 403).
        self.login(self.manager)
        r = self.client.get("/accounts/staff/")
        self.assertEqual(r.status_code, 200)

    def test_manager_blocked_from_activity(self):
        # Activity stays owner-only: manager gets 403 on all three pages.
        self.login(self.manager)
        self.assertEqual(self.client.get("/entries/activity/").status_code, 403)
        self.assertEqual(
            self.client.get("/entries/activity/all/").status_code, 403)

    def test_admin_sees_activity(self):
        self.login(self.admin)
        self.assertEqual(self.client.get("/entries/activity/").status_code, 200)

    def test_cookie_section_present(self):
        self.login(self.staff)
        r = self.client.get("/help/")
        self.assertContains(r, "Cookies and this-PC data")
        self.assertContains(r, "Sign-in cookie")


class ErrorPageTests(AuditTestBase):
    @override_settings(DEBUG=False)
    def test_staff_admin_page_uses_custom_403(self):
        self.login(self.staff)
        r = self.client.get("/accounts/staff/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Not allowed", status_code=403)
        self.assertContains(r, "/help/", status_code=403)

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_custom_404(self):
        self.login(self.staff)
        r = self.client.get("/no-such-page-xyz/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page not found", status_code=404)

    def test_500_renders_with_zero_context(self):
        # Must survive a dead database: no base template, no context.
        html = loader.get_template("500.html").render({})
        self.assertIn("Something went wrong", html)
        self.assertNotIn("{%", html)

    def test_400_renders_with_zero_context(self):
        html = loader.get_template("400.html").render({})
        self.assertIn("Bad request", html)
        self.assertNotIn("{%", html)


class LoginReturnPathTests(AuditTestBase):
    def _post_login(self, next_value=None):
        url = "/accounts/login/"
        if next_value:
            url += "?next=" + next_value
        r = self.client.get(url)
        token = r.context["csrf_token"]
        data = {"username": "t_staff", "password": "2222",
                "csrfmiddlewaretoken": str(token)}
        if next_value:
            data["next"] = next_value
        return self.client.post(url, data, follow=False)

    def test_safe_next_returns_there(self):
        r = self._post_login("/reports/monthly/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/reports/monthly/")

    def test_evil_next_falls_back_to_dashboard(self):
        r = self._post_login("https://evil.example.com/x")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/dashboard/")

    def test_plain_login_goes_to_dashboard(self):
        r = self._post_login()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/dashboard/")

    def test_next_notice_and_hidden_field(self):
        r = self.client.get("/accounts/login/?next=/sites/")
        self.assertContains(r, "Please sign in again")
        self.assertContains(r, 'name="next"')
        self.assertContains(r, "4-digit PIN")


class ShellMarkerTests(AuditTestBase):
    def test_dashboard_shell_sidebar_and_support(self):
        # Dark dashboard shell: one sidebar with profile, nav (Support
        # = Help), topbar search + bell; mobile uses the same sidebar.
        # Help appears once (sidebar). Legal links live on the Help page.
        self.login(self.admin)
        r = self.client.get("/sites/")
        self.assertContains(r, 'id="dash-sidebar"')
        self.assertContains(r, 'href="/help/"', count=1)
        from django.utils import timezone
        self.assertContains(
            r, "© %s nibba" % timezone.localdate().year)
        r = self.client.get("/help/")
        self.assertContains(r, 'href="/privacy/"', count=1)
        self.assertContains(r, 'href="/terms/"', count=1)
        self.assertContains(r, 'id="dash-search"')
        self.assertContains(r, 'id="notif-toggle"')
        self.assertContains(r, 'id="nav-toggle"')

    def test_bell_shows_recent_purchase_and_sale(self):
        # Bell lists latest entries (not low-stock alerts).
        self.login(self.admin)
        InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-10-15",
            time="09:00", qty=50, received_from="SUP",
            created_by=self.admin)
        inw = InwardEntry.objects.get()
        OutwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-10-15",
            time="10:00", qty=5, customer="Buyer", inward_entry=inw,
            created_by=self.admin)
        r = self.client.get("/sites/")
        self.assertContains(r, "Notifications")
        self.assertContains(r, "Purchase")
        self.assertContains(r, "Sale")
        self.assertContains(r, "Buyer")
        self.assertNotContains(r, "Low stock alerts")

    def test_offline_banner_present(self):
        self.login(self.staff)
        r = self.client.get("/sites/")
        self.assertContains(r, 'id="offline-banner"')
        self.assertContains(r, "No signal")

    def test_entry_form_has_draft_keeper(self):
        self.login(self.staff)
        url = (f"/entries/sites/{self.site.id}/materials/"
               f"{self.material.id}/inward/add/")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="entry-form"')
        self.assertContains(r, "nibba_entry_draft")

    def test_pwa_endpoints_alive(self):
        self.login(self.staff)
        self.assertEqual(
            self.client.get("/manifest.webmanifest").status_code, 200)
        r = self.client.get("/sw.js")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/javascript")


class EntryValidationTests(AuditTestBase):
    def add_url(self):
        return (f"/entries/sites/{self.site.id}/materials/"
                f"{self.material.id}/inward/add/")

    def test_entry_saves_directly_no_uploads(self):
        # nibba has no photo entry and no image service: values save
        # directly with no network involved.
        self.login(self.staff)
        before = InwardEntry.objects.count()
        r = self.client.post(self.add_url(), {
            "date": "2026-09-12", "time": "10:00", "qty": "1",
            "received_from": "TEST-NO-PHOTO"})
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.assertEqual(InwardEntry.objects.count(), before + 1)


@override_settings(ALLOWED_HOSTS=["testserver"])
class ReportExportTests(AuditTestBase):
    def test_site_summary_xlsx_and_missing_param(self):
        self.login(self.admin)
        url = "/reports/site-summary/export/"
        r = self.client.get(url + f"?site={self.site.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertTrue(len(r.content) > 500)
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_consumption_xlsx_and_missing_param(self):
        self.login(self.admin)
        url = "/reports/material-consumption/export/"
        r = self.client.get(url + f"?material={self.material.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_monthly_xlsx_and_bad_month(self):
        self.login(self.admin)
        url = "/reports/monthly/export/"
        r = self.client.get(url + "?month=9&year=2026")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertEqual(
            self.client.get(url + "?month=13&year=2026").status_code, 302)

    def test_site_summary_pdf(self):
        self.login(self.admin)
        r = self.client.get(
            f"/reports/site-summary/export-pdf/?site={self.site.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("pdf", r["Content-Type"].lower())

    def test_staff_can_export_own_scope(self):
        self.login(self.staff)
        r = self.client.get(
            f"/reports/site-summary/export/?site={self.site.id}")
        self.assertEqual(r.status_code, 200)


@override_settings(ALLOWED_HOSTS=["testserver"])
class AllocationEdgeTests(AuditTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.admin)
        self.sub = SubLocation.objects.create(
            site=self.site, name="T Banglo 1")
        self.inward = InwardEntry.objects.create(
            site=self.site, material=self.material,
            date="2026-09-12", time="10:00", qty=10,
            received_from="TEST", created_by=self.admin)
        self.url = (f"/entries/sites/{self.site.id}/materials/"
                    f"{self.material.id}/inward/{self.inward.id}/allocate/")

    def test_over_allocation_blocked(self):
        r = self.client.post(self.url, {
            "sub_location": self.sub.id, "qty_allocated": "11"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SubLocationAllocation.objects.count(), 0)

    def test_valid_allocation_saved(self):
        r = self.client.post(self.url, {
            "sub_location": self.sub.id, "qty_allocated": "6"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SubLocationAllocation.objects.count(), 1)

    def test_staff_gets_403_on_allocate(self):
        self.client.force_login(
            User.objects.get(username="t_staff"))
        self.assertEqual(self.client.get(self.url).status_code, 403)



@override_settings(ALLOWED_HOSTS=["testserver"])
class LoginLockoutTests(TestCase):
    def test_five_failures_locks_sixth(self):
        # Dedicated username so no real account is affected. Limit is 5, so
        # the first 4 failures still render the form; the 5th trips the
        # lockout (back to the login page with a timer, not a bare 403)
        # and even the CORRECT pin stays refused while locked.
        User.objects.create_user(
            username="lockprobe", password="9999", role=User.Role.STAFF)
        url = "/accounts/login/"
        bad = {"username": "lockprobe", "password": "0000"}
        for _ in range(4):
            self.assertEqual(self.client.post(url, bad).status_code, 200)
        r = self.client.post(url, bad)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/?locked=1", r["Location"])
        r = self.client.post(
            url, {"username": "lockprobe", "password": "9999"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/?locked=1", r["Location"])
        r = self.client.get("/accounts/login/?locked=1")
        self.assertContains(r, "Login locked for 1 hour")


@override_settings(ALLOWED_HOSTS=["testserver"])
class DashboardOrdersTests(AuditTestBase):
    """Dashboard stats + stock tabs and the Orders history page."""

    def _seed(self):
        InwardEntry.objects.create(
            site=self.site, material=self.material, date="2026-10-01",
            time="09:00", qty=5, received_from="SUP",
            created_by=self.admin)

    def test_dashboard_renders_stats_and_tabs(self):
        self._seed()
        self.login(self.staff)
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Low Stock")
        self.assertContains(r, "Out of Stock")
        self.assertContains(r, "T Mat")

    def test_low_and_out_tabs_filter(self):
        # Balance 5 of reorder 10 -> low, not out. Counts include the
        # topbar low-stock bell (1) plus the stock table (1 on low page).
        self._seed()
        self.login(self.admin)
        r = self.client.get("/dashboard/low-stock/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Low Stock")
        self.assertContains(r, "T Mat", count=2)
        r = self.client.get("/dashboard/out-of-stock/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Out of Stock")
        self.assertContains(r, "T Mat", count=1)

    def test_orders_page_tabs_and_pagination(self):
        self._seed()
        self.login(self.staff)
        for url in ("/entries/orders/", "/entries/orders/?tab=inward",
                    "/entries/orders/?tab=outward"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Order History")
        r = self.client.get("/entries/orders/?tab=inward")
        self.assertContains(r, "IN-")
        self.assertNotContains(r, "OUT-")

    def _single_shop(self):
        # Shop front doors need exactly one site (migration auto-makes
        # "Shop" alongside the test site, so prune to one here).
        from sites.models import Site
        Site.objects.exclude(pk=self.site.pk).delete()

    def test_purchase_add_saves_and_raises_balance(self):
        self._single_shop()
        self.login(self.staff)
        r = self.client.get("/entries/purchase/add/")
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/entries/purchase/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "09:00", "qty": "100", "received_from": "SUP"})
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.assertEqual(InwardEntry.objects.count(), 1)

    def test_sale_add_needs_stock_first(self):
        self._single_shop()
        self.login(self.staff)
        r = self.client.get("/entries/sale/add/")
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/entries/sale/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "10:00", "qty": "5", "customer": "Walk-in"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OutwardEntry.objects.count(), 0)

    def test_sale_add_fifo_links_and_deducts(self):
        self._single_shop()
        self.login(self.staff)
        self.client.post("/entries/purchase/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "09:00", "qty": "100", "received_from": "SUP"})
        inw = InwardEntry.objects.get()
        r = self.client.post("/entries/sale/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "10:00", "qty": "30", "customer": "Bulk Buyer"})
        self.assertEqual(r.status_code, 302, r.content[:400])
        out = OutwardEntry.objects.get()
        self.assertEqual(out.customer, "Bulk Buyer")
        self.assertEqual(out.inward_entry_id, inw.pk)
        from entries.utils import balance_for
        self.assertEqual(balance_for(self.site, self.material), 70)

    def test_sale_add_bulk_qty_blocked_over_stock(self):
        self._single_shop()
        self.login(self.staff)
        self.client.post("/entries/purchase/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "09:00", "qty": "10", "received_from": "SUP"})
        r = self.client.post("/entries/sale/add/", {
            "material": str(self.material.pk), "date": "2026-10-01",
            "time": "11:00", "qty": "5000", "customer": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OutwardEntry.objects.count(), 0)

    def test_single_shop_report_needs_no_site_picker(self):
        # Exactly one site + no ?site= : summary defaults to it.
        self._seed()
        self.login(self.staff)
        r = self.client.get("/reports/site-summary/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "T Mat")

    def test_sidebar_has_no_activity_and_role_only(self):
        self.login(self.admin)
        r = self.client.get("/dashboard/")
        self.assertNotContains(r, "/entries/activity/")
        self.assertContains(r, "t_admin · admin")
        self.assertContains(r, ">nibba<")
        self.login(self.staff)
        r = self.client.get("/dashboard/")
        self.assertContains(r, "t_staff · staff")
        # No email address anywhere under the profile name.
        self.assertNotContains(r, "t_staff@")
        self.assertNotContains(r, "t_admin@")


class CsrfAndSearchStateTests(AuditTestBase):
    """2026-10-22 audit pass: CSRF-timeout page, topbar no-match feedback,
    announced flash messages, and a privacy-page claim that matches reality."""

    def test_403_csrf_page_is_standalone(self):
        # Like 400/500: must render with zero app context (no tags left).
        html = loader.get_template("403_csrf.html").render({})
        self.assertIn("Security check needed", html)
        self.assertNotIn("{%", html)

    @override_settings(DEBUG=False)
    def test_csrf_failure_uses_friendly_page(self):
        from django.test import Client

        self.client = Client(enforce_csrf_checks=True)
        r = self.client.post(
            "/accounts/login/", {"username": "x", "password": "1111"})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Security check needed", status_code=403)
        self.assertContains(r, "Go back and try again", status_code=403)

    def test_no_search_results_indicator_in_shell(self):
        self.login(self.staff)
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="search-no-results"')
        self.assertContains(r, "Clear the box to see all rows.")

    def test_flash_messages_are_screen_reader_announced(self):
        victim = User.objects.create_user(
            username="t_del", password="9999", role=User.Role.STAFF)
        self.login(self.admin)
        r = self.client.post(
            f"/accounts/staff/{victim.pk}/delete/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'aria-live="polite"')
        self.assertContains(r, "deleted. Their past entries and audit history are kept.")

    def test_privacy_cookie_claim_matches_reality(self):
        # The claimed browser storage must match what the app actually uses:
        # session cookie + CSRF cookie only (no localStorage, no ad trackers).
        r = self.client.get("/privacy/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "dismissal ticks")
        self.assertContains(r, "security cookie")
        self.assertContains(r, "Last updated: October 22, 2026")


class TemplateCommentLint(SimpleTestCase):
    """Multi-line {# ... #} comments are unsupported by the Django lexer.

    The engine treats a `{# … #}` comment as single-line only: a block
    spanning lines falls through as literal TEXT and renders — and the
    bill_print.html note printed above every thermal receipt until the
    owner's screenshot exposed it (Oct 23 2026). Multi-line template notes
    must use {% comment %} or several single-line `{# … #}` lines; this
    guard fails any template that opens a `{#` comment without closing
    it on the same line.
    """

    def test_no_template_opens_an_unclosed_comment(self):
        import re
        from pathlib import Path

        from django.apps import apps
        from django.conf import settings

        dirs = []
        for d in settings.TEMPLATES[0].get("DIRS", []):
            if d:
                dirs.append(Path(d))
        for cfg in apps.get_app_configs():
            p = Path(cfg.path) / "templates"
            if p.is_dir():
                dirs.append(p)
        offender = re.compile(r"\{#(?:(?!#\}).)*$")
        scanned = 0
        for d in dirs:
            for f in d.rglob("*.html"):
                scanned += 1
                lines = f.read_text(
                    encoding="utf-8", errors="replace").splitlines()
                for n, line in enumerate(lines, 1):
                    m = offender.search(line)
                    self.assertIsNone(
                        m,
                        msg=(f"{f}:{n} opens a multi-line {{# comment "
                             f"(renders as literal text): "
                             f"{line.strip()[:80]}"))
        self.assertGreaterEqual(scanned, 20)
