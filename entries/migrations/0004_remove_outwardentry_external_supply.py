# Reset OutwardEntry to a single-purpose "usage" model.
# Removes: entry_type, supplied_to, place_of_supply.
# Makes used_at required (was nullable with a free-text for sub-locations).
#
# This is a clean-slate migration: we drop the old fields and tighten used_at
# in one step. If any OutwardEntry rows had NULL used_at at the time this
# migration ran, they would have to be cleaned up manually — at the time of
# writing the table is empty (test data was wiped), so no data fix is needed.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("entries", "0003_alter_outwardentry_options_outwardentry_entry_type_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="outwardentry",
            name="entry_type",
        ),
        migrations.RemoveField(
            model_name="outwardentry",
            name="supplied_to",
        ),
        migrations.RemoveField(
            model_name="outwardentry",
            name="place_of_supply",
        ),
        migrations.AlterField(
            model_name="outwardentry",
            name="used_at",
            field=models.CharField(
                help_text="Where the material was used, e.g. 'Banglo 21', 'Plot 5', 'Tower A foundation'.",
                max_length=255,
            ),
        ),
    ]
