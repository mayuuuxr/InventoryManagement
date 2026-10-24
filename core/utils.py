"""
Common utility functions shared across apps.
"""


def _user_is_admin(user):
    """
    Admin-level access: superuser, admin role, or manager role.
    Managers hold the same powers as admins (owner decision).
    Centralized to avoid duplication across apps.
    """
    return user.is_authenticated and (
        user.is_superuser or getattr(user, "role", None) in ("admin", "manager")
    )


def _user_can_edit(user):
    """
    Admins, managers and staff can create/edit/delete entries and materials.
    """
    return user.is_authenticated and (
        user.is_superuser
        or getattr(user, "role", None) in ("admin", "staff", "manager")
    )


def _sees_only_own_entries(user):
    """
    True for staff-role users. Since Sep 2026 this gates ONLY edit/delete
    ownership (EntryWriterRequiredMixin: staff touch own + legacy NULL rows).
    READS are global for every role - ledgers, balances, and reports show
    all entries (owner decision: live app, staff must see co-workers rows
    to avoid mis-entry). Do NOT reuse this for read filtering.
    """
    return bool(
        user and user.is_authenticated
        and not user.is_superuser
        and getattr(user, "role", None) == "staff"
    )


def _user_can_view_activity(user):
    """
    Activity/audit pages (who did what, staff timelines) are owner-only:
    superuser or admin role. Managers hold admin powers everywhere ELSE,
    but the activity log stays hidden from them (owner decision).
    """
    return bool(
        user and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "admin")
    )