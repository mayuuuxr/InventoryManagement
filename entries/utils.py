"""
Stock-balance calculation utilities.

The formula (per architecture.md):
    Balance = SUM(Inward.qty)
            - SUM(Outward.qty)
            - SUM(Transfer.qty where from_site)
            + SUM(Transfer.qty where to_site)

Computed per (site, material). Returns a Decimal so currency-style precision is
preserved end-to-end. Transfers are not yet wired through the UI; the function
is written to handle them the moment TransferEntry is recorded, with no
signature change.
"""
from decimal import Decimal

from django.db.models import Sum

from .models import InwardEntry, OutwardEntry, TransferEntry


ZERO = Decimal("0")


def fmt_qty(value):
    """
    Display helper: stock quantities are whole numbers in this industry, so
    160.00 renders as "160". Genuinely fractional values are shown trimmed
    (100.50 -> "100.5"), never rounded — display must not lie.
    """
    if value is None:
        return ""
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        return str(value)
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")

# Balance at or below this is flagged "low stock" (navbar bell + reports).
# Single place to tune — never hardcode the threshold in templates/views.
LOW_STOCK_THRESHOLD = 10


def balance_for(site, material):
    """
    Current balance of `material` at `site`.
    Returns a Decimal.
    """
    inward = (
        InwardEntry.objects
        .filter(site=site, material=material)
        .aggregate(total=Sum("qty"))["total"]
    ) or ZERO

    outward = (
        OutwardEntry.objects
        .filter(site=site, material=material)
        .aggregate(total=Sum("qty"))["total"]
    ) or ZERO

    transferred_out = (
        TransferEntry.objects
        .filter(from_site=site, material=material)
        .aggregate(total=Sum("qty"))["total"]
    ) or ZERO

    transferred_in = (
        TransferEntry.objects
        .filter(to_site=site, material=material)
        .aggregate(total=Sum("qty"))["total"]
    ) or ZERO

    return inward - outward - transferred_out + transferred_in


def balance_for_sub_location(sub_location, material):
    """
    Available qty of `material` at `sub_location`.

    Formula (per AGENTS.md sub-location split):
        Allocated to this sub-location (via SubLocationAllocation rows whose
        inward_entry is for this material)
        - Used at this sub-location (via OutwardEntry rows)

    Fallback (user-approved): when NO allocations exist yet for
    (sub_location.site, material), return site-level balance_for() so legacy
    flows and sites that haven't adopted allocations keep working instead of
    blocking every outward entry with "0 available".

    Returns a Decimal. Accepts model instances (or PKs, resolved defensively).
    """
    from .models import SubLocation, SubLocationAllocation

    # Accept PKs defensively — forms always pass instances, but callers/tests
    # may pass ids. Resolve to instances to get .site / .id uniformly.
    if isinstance(sub_location, int):
        sub_location = SubLocation.objects.filter(pk=sub_location).first()
        if sub_location is None:
            return ZERO
    site = sub_location.site

    allocated_here = (
        SubLocationAllocation.objects
        .filter(sub_location=sub_location, inward_entry__material=material)
        .aggregate(total=Sum("qty_allocated"))["total"]
    ) or ZERO

    used_here = (
        OutwardEntry.objects
        .filter(sub_location=sub_location, material=material)
        .aggregate(total=Sum("qty"))["total"]
    ) or ZERO

    # Any allocation at all for (site, material)? If none, allocations aren't
    # in use for this material — fall back to site-level balance.
    allocated_anywhere = (
        SubLocationAllocation.objects
        .filter(sub_location__site=site, inward_entry__material=material)
        .aggregate(total=Sum("qty_allocated"))["total"]
    ) or ZERO
    if allocated_anywhere == ZERO:
        return balance_for(site, material)

    return allocated_here - used_here


def balance_for_user(site, material, user):
    """
    True stock of `material` at `site`, for ANY role (owner decision Sep 2026:
    this is a live app - every role sees the real balance and every entry,
    so staff never mis-enter against a partial number).

    Kept as a separate function (same signature) because ledgers and reports
    call it with the viewer; it deliberately ignores `user` and returns the
    unscoped balance_for(). Stock-truth checks (outward validation) use
    balance_for() directly. Per-user scoping now applies ONLY to
    edit/delete ownership (EntryWriterRequiredMixin), never to reads.
    """
    return balance_for(site, material)


def balances_for_site(site, materials, user=None):
    """
    Balances for MANY materials at one site in 4 grouped queries total —
    the bulk twin of balance_for(). Always the TRUE site stock for every
    role (owner decision Sep 2026: live app, all roles see real balances;
    `user` is accepted but ignored, kept so callers need no change).

    Use this whenever a page lists the whole catalog (site detail, site
    summary report). Returns {material_id: Decimal}. Materials without
    entries map to ZERO. Accepts a site instance (or pk) and any iterable
    of materials (or pks).
    """
    site_id = site.pk if hasattr(site, "pk") else site
    mat_ids = [m.id if hasattr(m, "id") else m for m in materials]
    if not mat_ids:
        return {}

    inward_qs = InwardEntry.objects.filter(
        site_id=site_id, material_id__in=mat_ids)
    outward_qs = OutwardEntry.objects.filter(
        site_id=site_id, material_id__in=mat_ids)

    def grouped(qs):
        return {
            row["material_id"]: row["t"] or ZERO
            for row in qs.values("material_id").annotate(t=Sum("qty"))
        }

    inward = grouped(inward_qs)
    outward = grouped(outward_qs)
    # Transfers are site-level (no per-user scoping anywhere).
    transferred_out = grouped(
        TransferEntry.objects.filter(
            from_site_id=site_id, material_id__in=mat_ids))
    transferred_in = grouped(
        TransferEntry.objects.filter(
            to_site_id=site_id, material_id__in=mat_ids))

    return {
        mat_id: (inward.get(mat_id, ZERO) - outward.get(mat_id, ZERO)
                 - transferred_out.get(mat_id, ZERO)
                 + transferred_in.get(mat_id, ZERO))
        for mat_id in mat_ids
    }


def balances_for_sites(sites, materials):
    """Balances for MANY (site, material) pairs in 4 grouped queries total.

    Bulk twin of balance_for() across sites (used by the all-sites
    consumption report). Returns {(site_id, material_id): Decimal}.
    """
    site_ids = [s.id if hasattr(s, "id") else s for s in sites]
    mat_ids = [m.id if hasattr(m, "id") else m for m in materials]
    if not site_ids or not mat_ids:
        return {}

    def grouped_sums(qs, site_field):
        totals = {}
        for row in (
            qs.filter(**{
                f"{site_field}__in": site_ids, "material_id__in": mat_ids})
            .values(site_field, "material_id")
            .annotate(t=Sum("qty"))
        ):
            totals[(row[site_field], row["material_id"])] = row["t"] or ZERO
        return totals

    inward = grouped_sums(InwardEntry.objects.all(), "site_id")
    outward = grouped_sums(OutwardEntry.objects.all(), "site_id")
    tout = grouped_sums(TransferEntry.objects.all(), "from_site_id")
    tin = grouped_sums(TransferEntry.objects.all(), "to_site_id")

    out = {}
    for s_id in site_ids:
        for m_id in mat_ids:
            key = (s_id, m_id)
            out[key] = (
                inward.get(key, ZERO)
                - outward.get(key, ZERO)
                - tout.get(key, ZERO)
                + tin.get(key, ZERO)
            )
    return out


def inward_remaining(inward_entry, exclude_pk=None):
    """
    Unconsumed quantity of one inward delivery: its qty minus what outward
    entries already linked to it (optionally excluding one row being edited).
    Returns a Decimal, never negative-masked (callers compare directly).
    """
    used_qs = OutwardEntry.objects.filter(inward_entry=inward_entry)
    if exclude_pk:
        used_qs = used_qs.exclude(pk=exclude_pk)
    used = used_qs.aggregate(total=Sum("qty"))["total"] or ZERO
    return inward_entry.qty - used


def lock_stock_rows(site, material):
    """Acquire row-level locks for a (site, material) stock check.

    MUST be called inside a `transaction.atomic()` block, BEFORE recomputing
    the balance and saving. Without this, two staff saving at the same second
    both see "100 available" and both take 80 (balance goes negative despite
    the form guard). `select_for_update()` serializes concurrent writers on
    PostgreSQL; on SQLite the surrounding transaction holds the DB write lock.
    Only PKs are fetched — cheap, never full rows.
    """
    site_id = site.pk if hasattr(site, "pk") else site
    mat_id = material.pk if hasattr(material, "pk") else material
    list(InwardEntry.objects.select_for_update().filter(
        site_id=site_id, material_id=mat_id).values_list("pk", flat=True))
    list(OutwardEntry.objects.select_for_update().filter(
        site_id=site_id, material_id=mat_id).values_list("pk", flat=True))
    list(TransferEntry.objects.select_for_update().filter(
        from_site_id=site_id, material_id=mat_id).values_list("pk", flat=True))
    list(TransferEntry.objects.select_for_update().filter(
        to_site_id=site_id, material_id=mat_id).values_list("pk", flat=True))


def low_stock_items(sites, limit=5):
    """
    Top `limit` lowest-stock (site, material) pairs across `sites`,
    restricted to balances at/below each material's own reorder_point,
    lowest first.

    Uses grouped DB aggregation (4 queries total regardless of site/material
    count) instead of calling balance_for() per pair. Returns a list of dicts:
    site_id, site_name, material_id, material_name, unit, balance.
    Empty list when everything is above threshold — callers show an
    "all stocked" empty state in that case.
    """
    from materials.models import Material
    from sites.models import Site

    site_ids = [s.id for s in sites]
    if not site_ids:
        return []

    def grouped_sums(qs, site_field):
        totals = {}
        for row in (
            qs.filter(**{f"{site_field}__in": site_ids})
            .values(site_field, "material_id")
            .annotate(t=Sum("qty"))
        ):
            totals[(row[site_field], row["material_id"])] = row["t"] or ZERO
        return totals

    inward = grouped_sums(InwardEntry.objects.all(), "site_id")
    outward = grouped_sums(OutwardEntry.objects.all(), "site_id")
    tout = grouped_sums(TransferEntry.objects.all(), "from_site_id")
    tin = grouped_sums(TransferEntry.objects.all(), "to_site_id")

    balances = {}
    for key in set(inward) | set(outward) | set(tout) | set(tin):
        balances[key] = (
            inward.get(key, ZERO)
            - outward.get(key, ZERO)
            - tout.get(key, ZERO)
            + tin.get(key, ZERO)
        )

    materials = Material.objects.in_bulk(
        [m_id for (_, m_id) in balances.keys()])
    low = sorted(
        ((k, v) for k, v in balances.items()
         if materials.get(k[1]) is not None
         and v <= materials[k[1]].reorder_point),
        key=lambda kv: kv[1],
    )[:limit]
    if not low:
        return []

    site_map = {s.id: s for s in Site.objects.filter(id__in=[s_id for (s_id, _) in [k for k, _ in low]])}

    items = []
    for (site_id, material_id), balance in low:
        material = materials.get(material_id)
        site = site_map.get(site_id)
        if material is None or site is None:
            continue
        items.append({
            "site_id": site_id,
            "site_name": site.name,
            "material_id": material_id,
            "material_name": material.display_name,
            "unit": material.unit,
            "balance": balance,
        })
    return items
