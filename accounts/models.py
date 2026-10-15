from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model.

    We extend AbstractUser (NOT the default User) so we can attach
    a `role` field directly. This is the canonical Django pattern
    when you need extra fields on the user — never modify the
    built-in User model directly.

    `AUTH_USER_MODEL` in settings.py points here.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"
        MANAGER = "manager", "Manager"

    # role is lowercase to match the requirement ('admin', 'staff', 'manager')
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STAFF,
        help_text="Admin = full access. Staff = data entry. Manager = full access like admin.",
    )

    @property
    def is_admin_role(self):
        """Convenience: True for admin/manager roles (or superuser)."""
        return self.role in (self.Role.ADMIN, self.Role.MANAGER) or self.is_superuser

    @property
    def can_view_activity(self):
        """Activity/audit pages stay owner-only (managers excluded)."""
        return self.is_superuser or self.role == self.Role.ADMIN

    def __str__(self):
        return self.username
