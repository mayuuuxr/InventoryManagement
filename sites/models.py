from django.db import models

from materials.models import CatalogAuditMixin


class Site(CatalogAuditMixin, models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def get_default_site():
    """The shop site: sole site among NON-DELETED sites, else None.

    Single-shop installs run everything against this site so staff never
    pick one. Returns None when several active sites exist (caller must
    ask). Soft-deleted rows do not count: a retired legacy site must not
    freeze the app in "pick a site" mode — the shop PC keeps working.
    (Owner note: this shop sells paint & household hardware from ONE
    site; extra sites are a legacy-of-data concept only.)
    """
    sites = Site.objects.filter(is_deleted=False)
    if sites.count() == 1:
        return sites.first()
    return None
