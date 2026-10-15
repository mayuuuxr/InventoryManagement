"""
Data migration: create the two role-based Groups (Admin, Staff) and assign
permissions. Repeating this migration is safe (idempotent) — get_or_create
on the Group, and we replace the group's permission set on every run so
permission changes apply to existing deployments.

Permission matrix (per the requirement):
- Admin: full add/change/delete on Site, Material, and all Entry models.
- Staff: add/change on Material and Entry models. NO add/change/delete on Site.
"""
from django.contrib.auth.models import Group, Permission
from django.db import migrations


# Models that need per-role permissions. Tuple of (app_label, model_name).
SITE_MODEL = ("sites", "site")
MATERIAL_MODEL = ("materials", "material")
ENTRY_MODELS = [
    ("entries", "inwardentry"),
    ("entries", "outwardentry"),
    ("entries", "transferentry"),
]

ALL_BUSINESS_MODELS = [SITE_MODEL, MATERIAL_MODEL, *ENTRY_MODELS]
NON_SITE_MODELS = [MATERIAL_MODEL, *ENTRY_MODELS]


def get_perms(model_spec, actions):
    """
    Helper: get the Permission objects for a given model and list of actions.
    `actions` is a list like ['add', 'change', 'delete'].
    Permission codenames follow Django's pattern: add_<model>, change_<model>, delete_<model>.
    """
    app_label, model_name = model_spec
    return list(
        Permission.objects.filter(
            content_type__app_label=app_label,
            codename__in=[f"{action}_{model_name}" for action in actions],
        )
    )


def create_groups_and_permissions(apps, schema_editor):
    # Admin: full CRUD on all business models
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    admin_perms = []
    for model_spec in ALL_BUSINESS_MODELS:
        admin_perms += get_perms(model_spec, ["add", "change", "delete", "view"])
    admin_group.permissions.set(admin_perms)

    # Staff: add/change/view on Material + Entry models. NO Site permissions.
    staff_group, _ = Group.objects.get_or_create(name="Staff")
    staff_perms = []
    for model_spec in NON_SITE_MODELS:
        staff_perms += get_perms(model_spec, ["add", "change", "view"])
    staff_group.permissions.set(staff_perms)


def remove_groups(apps, schema_editor):
    """Reverse: remove the two groups. Permissions are left intact (they're
    owned by Django's Permission model, not by Group)."""
    Group.objects.filter(name__in=["Admin", "Staff"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        # These app labels must exist in django_content_type before we can
        # attach permissions, so we depend on their initial migrations.
        ("sites", "0001_initial"),
        ("materials", "0001_initial"),
        ("entries", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups_and_permissions, remove_groups),
    ]
