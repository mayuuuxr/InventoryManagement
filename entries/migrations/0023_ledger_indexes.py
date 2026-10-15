"""Ledger-scale composite indexes: every ledger query filters
(site, material) and sorts (date, time)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0022_protect_history_outward_unique'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='inwardentry',
            index=models.Index(fields=['site', 'material', 'date', 'time'], name='idx_inward_ledger'),
        ),
        migrations.AddIndex(
            model_name='outwardentry',
            index=models.Index(fields=['site', 'material', 'date', 'time'], name='idx_outward_ledger'),
        ),
    ]
