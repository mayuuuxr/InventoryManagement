from django.test import TestCase

from sites.models import Site, get_default_site


class GetDefaultSiteTests(TestCase):
    """Single-shop resolution (sites/models.py::get_default_site).

    Fresh test databases already hold the auto-created "Shop" site
    (migration 0003). The function must only count ACTIVE sites:
    a soft-deleted legacy site must never block the shop PC.
    """

    def test_single_active_site_is_default(self):
        self.assertEqual(get_default_site().name, "Shop")

    def test_soft_deleted_site_is_ignored(self):
        Site.objects.create(name="Old Park", location="nagpur")
        old = Site.objects.get(name="Old Park")
        old.is_deleted = True
        old.save()
        self.assertEqual(get_default_site().name, "Shop")

    def test_two_active_sites_return_none(self):
        Site.objects.create(name="Branch", location="kamptee")
        self.assertIsNone(get_default_site())
