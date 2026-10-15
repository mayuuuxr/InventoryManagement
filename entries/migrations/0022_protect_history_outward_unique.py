"""Harden entry integrity: PROTECT sites/materials with history + DB-level
outward duplicate backstop (same place + time)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0021_alter_sublocation_unique_together_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inwardentry',
            name='material',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.material'),
        ),
        migrations.AlterField(
            model_name='inwardentry',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites.site'),
        ),
        migrations.AlterField(
            model_name='outwardentry',
            name='material',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.material'),
        ),
        migrations.AlterField(
            model_name='outwardentry',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites.site'),
        ),
        migrations.AlterField(
            model_name='transferentry',
            name='material',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.material'),
        ),
        migrations.AlterField(
            model_name='transferentry',
            name='from_site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers_out', to='sites.site'),
        ),
        migrations.AlterField(
            model_name='transferentry',
            name='to_site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers_in', to='sites.site'),
        ),
        migrations.AddConstraint(
            model_name='outwardentry',
            constraint=models.UniqueConstraint(fields=['site', 'material', 'date', 'time', 'sub_location'], name='unique_outward_per_site_material_datetime_place'),
        ),
    ]
