from django.db import migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("entries", "0025_remove_outwardentryphoto_entry_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="inwardentry",
            name="rate",
            field=django.db.models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Price per unit (₹) at the time of this entry.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="outwardentry",
            name="rate",
            field=django.db.models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Sale price per unit (₹) at the time of this sale.",
                max_digits=12,
                null=True,
            ),
        ),
    ]
