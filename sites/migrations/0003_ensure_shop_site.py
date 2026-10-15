"""Single-shop default: create the 'Shop' site on fresh databases.

nibba runs one shop under one roof — there is no site picker in the UI.
Fresh installs (INSTALL.bat -> migrate) get a ready-made Shop so reports
and entries work with zero setup. Existing databases are untouched
(create only runs when no site row exists at all).
"""
from django.db import migrations


def ensure_shop_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    if not Site.objects.exists():
        Site.objects.create(name="Shop", location="Main Shop")


def noop_reverse(apps, schema_editor):
    # Leave the auto-created Shop in place on rollback (data safety).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0002_site_created_by_site_deleted_at_site_deleted_by_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_shop_site, noop_reverse),
    ]
