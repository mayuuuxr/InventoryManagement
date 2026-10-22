"""Normalize inconsistent unit spellings to the Indian-market glossary.

Owner decision (Oct 2026): every material carries an Indian-market unit with
one canonical spelling. This data migration rewrites EXACT legacy spellings
only — it never touches quantities, balances, or rows whose unit is already
canonical:

    miter / m / mtrs  -> mtr   (metres: cables, MS pipe lengths, paver blocks)
    no                -> nos   (pieces: the app always spells it 'nos')
    bkt               -> L     (paint: buckets already counted in litres)

Forwards-only (reverse would be ambiguous — e.g. a live 'mtr' row could have
come from 'm' or 'mtrs'). Unit is CharField(max_length=50), so 'mtr'/'nos'/L'
always fit. Safe on a FRESH database too: with zero Material rows the loop
is a no-op, so fresh installs migrate cleanly.
"""
from django.db import migrations

# Exact-match unit rewrite table. Anything NOT listed here stays untouched.
UNIT_FIXES = {
    "miter": "mtr",   # typo seen on 3 cable rows
    "m": "mtr",       # bare metre, unify with the 'mtr' spelling
    "mtrs": "mtr",    # alternate spelling on 5 cable rows
    "no": "nos",      # singular 'no' on 3 rows (pieces)
    "bkt": "L",       # paint buckets counted as litres (owner decision)
}


def normalize_units(apps, schema_editor):
    Material = apps.get_model("materials", "Material")
    for material in Material.objects.all():
        fixed = UNIT_FIXES.get(material.unit)
        if fixed is not None:
            material.unit = fixed
            # update() avoids running full_clean(): nothing else changes,
            # and bulk rewrite keeps this migration silent and fast.
            type(material).objects.filter(
                pk=material.pk).update(unit=material.unit)


class Migration(migrations.Migration):

    dependencies = [
        ("materials", "0007_category_ci_subcategory_ci"),
    ]

    operations = [
        migrations.RunPython(normalize_units),
    ]
