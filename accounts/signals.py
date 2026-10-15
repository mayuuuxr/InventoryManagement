"""
Signals for the accounts app.

post_save on User → assign the user to the correct Group based on their role.
This keeps the User.role field and the actual Group membership in sync without
requiring callers to remember to add the user to a group manually.
"""
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


# Map role value → group name. Keep in sync with the data migration.
# Managers hold admin powers (see core.utils._user_is_admin), so they sit in
# the Admin group — previously they were stripped from ALL groups, which
# would break any future permission-based (not role-based) check.
ROLE_TO_GROUP = {
    User.Role.ADMIN: "Admin",
    User.Role.MANAGER: "Admin",
    User.Role.STAFF: "Staff",
}


@receiver(post_save, sender=User)
def assign_user_to_group(sender, instance, created, **kwargs):
    """
    On every save, make sure the user is in the right group.
    - On creation, adds them to the group matching their role.
    - On update, if role changed, removes them from the old group and adds them
      to the new one. Superusers are left alone (they implicitly have all perms).
    """
    # Superusers skip group assignment — they're admin via is_superuser.
    if instance.is_superuser:
        return

    # Remove the user from any of the two managed groups, then add them to the
    # one matching their current role. Doing both every save keeps things simple
    # and self-correcting if the role field is edited later.
    managed_groups = Group.objects.filter(name__in=list(ROLE_TO_GROUP.values()))
    instance.groups.remove(*managed_groups)

    target_group_name = ROLE_TO_GROUP.get(instance.role)
    if target_group_name:
        group, _ = Group.objects.get_or_create(name=target_group_name)
        instance.groups.add(group)


@receiver(user_logged_in)
def log_staff_login(sender, request, user, **kwargs):
    """
    Record logins in the activity log so the owner sees who checks in.
    Supervised roles only (staff/manager/admin) — superuser logins are
    technical noise. Page views are deliberately NOT logged, only logins.
    """
    if user.is_superuser:
        return
    from entries.models import AuditLog
    from entries.views import log_audit
    log_audit(
        user, AuditLog.Action.LOGIN, AuditLog.EntryType.STAFF, user.pk,
        f"{user.username} ({user.get_role_display()}) logged in.",
    )
