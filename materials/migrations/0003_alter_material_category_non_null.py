# Generated for: alter material.category from null=True to non-nullable.
# All existing materials have a category populated by the seed_materials command,
# so this migration is safe to run as-is.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("materials", "0002_category_alter_material_options_material_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="material",
            name="category",
            field=models.ForeignKey(
                on_delete=models.deletion.PROTECT,
                related_name="materials",
                to="materials.category",
            ),
        ),
    ]
