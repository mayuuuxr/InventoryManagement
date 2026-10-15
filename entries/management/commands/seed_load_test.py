"""Load test seeder: 100 entries/day for the last N days (default 10x100).

Creates realistic inward/outward rows across EVERY material in the catalog
so the owner can feel dashboard/orders/reports speed at 1000+ rows.
Outwards never exceed their linked inward (no negative-test pollution).

Usage:
    venv\\Scripts\\python.exe manage.py seed_load_test
    venv\\Scripts\\python.exe manage.py seed_load_test --days 10 --per-day 100 --seed 42

Aborts when the catalog is empty (add materials first) or when the site
is missing. Safe to re-run (new rows each time; use --seed to vary).
"""
import random
from datetime import time as dtime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from entries.models import InwardEntry, OutwardEntry, SubLocation
from materials.models import Material
from sites.models import Site

SUPPLIERS = ["Sharma Traders", "Gupta Hardware", "Paint Distributor",
             "Local Supplier", "Wholesale Mart"]
SUB_LOCS = ["Counter", "Godown", "Shop Floor"]


class Command(BaseCommand):
    help = "Seed N days x M entries/day across all materials (load test)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=10)
        parser.add_argument("--per-day", type=int, default=100)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, days, per_day, seed, **options):
        rng = random.Random(seed)
        site = Site.objects.order_by("id").first()
        if site is None:
            self.stderr.write("No site found — run migrations first.")
            return
        materials = list(Material.objects.all())
        if not materials:
            self.stderr.write("Catalog is empty — add materials first.")
            return
        sublocs = [SubLocation.objects.get_or_create(
            site=site, name=name)[0] for name in SUB_LOCS]

        today = timezone.localdate()
        start_day = today - timedelta(days=days - 1)
        # Slots already taken by earlier seed runs (or real entries) so
        # re-runs never hit the unique constraints. Two small queries.
        taken_in = {
            (m, str(d), str(t)) for m, d, t
            in InwardEntry.objects.filter(
                site=site, date__gte=start_day).values_list(
                "material_id", "date", "time")
        }
        taken_out = {
            (m, str(d), str(t), s) for m, d, t, s
            in OutwardEntry.objects.filter(
                site=site, date__gte=start_day).values_list(
                "material_id", "date", "time", "sub_location_id")
        }
        in_rows, out_rows = [], []
        # Remaining qty per inward, keyed by index in in_rows.
        for d in range(days - 1, -1, -1):
            day = today - timedelta(days=d)
            day_key = str(day)
            n_in = per_day // 2
            n_out = per_day - n_in
            # Distinct clock times per (material, date): inward unique
            # constraint is (site, material, date, time) — seconds keep
            # every row distinct no matter how many land on one day.
            sec = {}
            day_in_idx = []
            for i in range(n_in):
                mat = materials[i % len(materials)]
                s = sec.get(mat.pk, 8 * 3600 + rng.randrange(0, 600))
                while True:
                    h, rem = divmod(s % 86400, 3600)
                    mi, se = divmod(rem, 60)
                    key = (mat.pk, day_key,
                           "%02d:%02d:%02d" % (h, mi, se))
                    if key not in taken_in:
                        taken_in.add(key)
                        break
                    s += rng.randrange(1, 60)
                sec[mat.pk] = s + rng.randrange(5, 90)
                qty = rng.randrange(50, 501)
                in_rows.append(InwardEntry(
                    site=site, material=mat, date=day,
                    time=dtime(h, mi, se), qty=qty,
                    received_from=rng.choice(SUPPLIERS)))
                day_in_idx.append(len(in_rows) - 1)
            remaining = {idx: in_rows[idx].qty for idx in day_in_idx}
            # Outward rows are unique on (material, date, time,
            # sub_location): bump the clock until the slot is free, so
            # high-volume days never collide.
            used_slots = set()
            for _ in range(n_out):
                cand = [i for i, left in remaining.items() if left > 0]
                if not cand:
                    break
                idx = rng.choice(cand)
                src = in_rows[idx]
                qty = rng.randrange(1, min(50, int(remaining[idx])) + 1)
                remaining[idx] -= qty
                secs = (src.time.hour * 3600 + src.time.minute * 60
                        + src.time.second + rng.randrange(60, 7200))
                sub = rng.choice(sublocs)
                while (src.material_id, day_key,
                       "%02d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60,
                                           secs % 60),
                       sub.pk) in taken_out or (
                        src.material_id, secs, sub.pk) in used_slots:
                    secs += rng.randrange(1, 60)
                    if secs > 86399:
                        secs, sub = 0, rng.choice(sublocs)
                used_slots.add((src.material_id, secs, sub.pk))
                taken_out.add(
                    (src.material_id, day_key,
                     "%02d:%02d:%02d" % (secs // 3600, (secs % 3600) // 60,
                                         secs % 60), sub.pk))
                h, rem = divmod(secs, 3600)
                mi, se = divmod(rem, 60)
                out_rows.append(OutwardEntry(
                    site=site, material=src.material, date=day,
                    time=dtime(h, mi, se), qty=qty,
                    inward_entry=None,  # linked after bulk insert
                    sub_location=sub))
                out_rows[-1]._src_idx = idx

        created_in = InwardEntry.objects.bulk_create(
            in_rows, batch_size=2000)
        # Link outwards to their (now saved) inward deliveries.
        for o in out_rows:
            o.inward_entry = created_in[o._src_idx]
            del o._src_idx
        OutwardEntry.objects.bulk_create(out_rows, batch_size=2000)
        self.stdout.write(
            f"Seeded {len(created_in)} inward + {len(out_rows)} outward "
            f"entries over {days} days at '{site.name}' "
            f"({Material.objects.count()} materials).")
