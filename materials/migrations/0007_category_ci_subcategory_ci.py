"""Case-insensitive uniqueness for live catalog names (matches SubLocation)."""
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0006_remove_subcategory_unique_subcategory_per_category_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('name'), condition=models.Q(('is_deleted', False)), name='unique_category_name_active_ci'),
        ),
        migrations.AddConstraint(
            model_name='subcategory',
            constraint=models.UniqueConstraint('category', django.db.models.functions.text.Lower('name'), condition=models.Q(('is_deleted', False)), name='unique_subcategory_per_category_ci'),
        ),
    ]
