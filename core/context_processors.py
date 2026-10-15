"""Template context processors (registered in settings.TEMPLATES)."""
from datetime import datetime


def recent_notifications(request):
    """
    Navbar bell data: latest purchase/sale entries across the shop.
    Anonymous users get an empty list (no queries). Two small capped
    queries merged in Python — no union needed across the two models.
    """
    if not request.user.is_authenticated:
        return {"recent_notifications": []}
    try:
        from entries.models import InwardEntry, OutwardEntry

        ins = list(InwardEntry.objects.select_related(
            "material", "site").order_by("-date", "-time", "-pk")[:8])
        outs = list(OutwardEntry.objects.select_related(
            "material", "site").order_by("-date", "-time", "-pk")[:8])

        def row(e, kind):
            when = e.date
            try:
                when = datetime.combine(e.date, e.time)
            except (TypeError, ValueError):
                pass
            if kind == "in":
                title = "Purchase"
                sub = e.received_from
            else:
                title = "Sale"
                sub = e.customer or ""
            return {
                "kind": kind,
                "title": title,
                "material_name": e.material.display_name,
                "site_id": e.site_id,
                "material_id": e.material_id,
                "qty": e.qty,
                "unit": e.material.unit,
                "sub": sub,
                "when": when,
            }

        merged = ([row(e, "in") for e in ins]
                  + [row(e, "out") for e in outs])
        merged.sort(key=lambda n: str(n["when"]), reverse=True)
        items = merged[:8]
    except Exception:
        items = []
    return {"recent_notifications": items}
