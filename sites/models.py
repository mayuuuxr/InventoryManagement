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
    """The shop site: sole site when there is exactly one, else None.

    Single-shop installs run everything against this site so staff never
    pick one. Returns None when several sites exist (caller must ask).
    """
    if Site.objects.count() == 1:
        return Site.objects.first()
    return None
