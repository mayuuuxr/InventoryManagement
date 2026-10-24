from django.db import migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("materials", "0008_normalize_units"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="hsn_code",
            field=django.db.models.CharField(
                blank=True,
                default="",
                help_text="HSN / SAC code printed on invoices (optional).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="gst_rate",
            field=django.db.models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="GST % for invoices (e.g. 28). Blank = no GST on bills.",
                max_digits=5,
                null=True,
            ),
        ),
    ]
