from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User


def validate_pin(value):
    """Member passwords are exactly 4 digits — short enough to remember."""
    from django.core.exceptions import ValidationError
    if not (isinstance(value, str) and len(value) == 4 and value.isdigit()):
        raise ValidationError("Password must be exactly 4 digits (e.g. 4821).")


# Shared Tailwind classes — same look as the entry/site forms.
INPUT_CLASS = (
    "w-full px-3 py-2 bg-surface border border-subtle rounded-md text-sm "
    "text-charcoal placeholder:text-muted focus:outline-none "
    "focus:border-accent focus:ring-2 focus:ring-accent/20"
)


class LoginForm(AuthenticationForm):
    """Standard username/password login form. Tailwind-styled widgets."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": INPUT_CLASS,
            "placeholder": "Username",
            "autofocus": True,
            "autocomplete": "username",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": INPUT_CLASS,
            "placeholder": "4-digit PIN",
            "autocomplete": "current-password",
        })
    )


class StaffCreateForm(UserCreationForm):
    """
    Admin creates a member account with a role picker (Staff = data entry,
    Manager = full access like admin) and a 4-digit PIN. Username uniqueness and
    password-match come free from UserCreationForm; the PIN rule is enforced
    in clean_password1() below.
    """
    role = forms.ChoiceField(
        choices=[(User.Role.STAFF, "Staff"), (User.Role.MANAGER, "Manager")],
        initial=User.Role.STAFF,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        help_text="Managers have full access like admins.",
    )

    class Meta:
        model = User
        fields = ("username", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "class": INPUT_CLASS, "placeholder": "e.g. ramesh", "autofocus": True,
        })
        for field in ("password1", "password2"):
            self.fields[field].widget.attrs.update({
                "class": INPUT_CLASS, "placeholder": "4-digit PIN",
                "inputmode": "numeric", "maxlength": "4",
            })
            self.fields[field].help_text = "Exactly 4 digits."
        self.fields["password1"].validators.append(validate_pin)

    def clean_password1(self):
        # Field validators already ran validate_pin; return as-is.
        return self.cleaned_data.get("password1")


class StaffResetForm(SetPasswordForm):
    """
    Admin sets a new 4-digit PIN directly — no old password, no email flow.
    Uses set_password() internally, so nothing plain-text is ever stored.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ("new_password1", "new_password2"):
            self.fields[field].widget.attrs.update({
                "class": INPUT_CLASS, "placeholder": "4-digit PIN",
                "inputmode": "numeric", "maxlength": "4",
            })
            self.fields[field].help_text = "Exactly 4 digits."
        self.fields["new_password1"].validators.append(validate_pin)

    def clean_new_password1(self):
        # Field validators already ran validate_pin; return as-is.
        return self.cleaned_data.get("new_password1")


class StaffEditForm(forms.ModelForm):
    """Admin renames a member account and can change their role."""
    role = forms.ChoiceField(
        choices=[(User.Role.STAFF, "Staff"), (User.Role.MANAGER, "Manager")],
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
        help_text="Managers have full access like admins.",
    )

    class Meta:
        model = User
        fields = ("username", "role")
        widgets = {
            "username": forms.TextInput(attrs={
                "class": INPUT_CLASS, "autofocus": True,
            }),
        }



