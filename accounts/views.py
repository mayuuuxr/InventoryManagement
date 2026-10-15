from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from .forms import LoginForm, StaffCreateForm, StaffEditForm, StaffResetForm
from .models import User
from core.utils import _user_is_admin


def _client_ip(request):
    """Best-effort client IP, matching what axes stores on AccessAttempt."""
    try:
        from axes.helpers import get_client_ip_address
        return get_client_ip_address(request)
    except Exception:
        return None


def _username_failures(username, ip=None):
    """(total_failures, lock_moment) for a username (+IP when given).

    Axes stores one AccessAttempt row per (username, IP, agent) but counts
    per AXES_LOCKOUT_PARAMETERS (ip + username) — mirror that here, or one
    phone's spam would show a bogus timer on every other device.
    When `ip` is None (no request handy), falls back to username-wide
    counting (conservative: may overstate, never understates).

    lock_moment = the attempt time when cumulative failures FIRST hit
    the limit (oldest→newest scan). Later retries must NOT push it —
    otherwise every retry restarts the 1-hour timer.
    """
    from axes.conf import settings as axes_settings
    from axes.helpers import get_cool_off
    from axes.models import AccessAttempt
    from django.utils import timezone
    username = (username or "").strip()
    if not username:
        return 0, None
    cool_off = get_cool_off(None)  # 1 hour timedelta
    limit = getattr(axes_settings, "AXES_FAILURE_LIMIT", 5)
    qs = AccessAttempt.objects.filter(username=username)
    if ip:
        qs = qs.filter(ip_address=ip)
    if cool_off is not None:
        qs = qs.filter(attempt_time__gte=timezone.now() - cool_off)
    rows = qs.order_by("attempt_time").values_list(
        "attempt_time", "failures_since_start")
    total, moment = 0, None
    for attempt_time, failures in rows:
        total += failures or 0
        if moment is None and total >= limit:
            moment = attempt_time
    return total, moment


def _lockout_info(request):
    """(locked, unlock_epoch_ms, username) for the login page countdown.

    Locked = 5+ failures for this (IP, username) and still inside the
    1-hour cooloff. Username comes from the lockout redirect's session stash
    (no username in URL). Scoped by client IP so one attacker's spam does
    not show a lockout banner to everyone else.
    """
    from axes.conf import settings as axes_settings
    from axes.helpers import get_cool_off
    from django.utils import timezone
    username = (request.session.get("lockout_username") or "").strip()
    total, moment = _username_failures(username, _client_ip(request))
    if moment is None:
        return False, 0, ""
    cool_off = get_cool_off(request)  # 1 hour timedelta
    unlock_at = moment + cool_off
    limit = getattr(axes_settings, "AXES_FAILURE_LIMIT", 5)
    if total >= limit and unlock_at > timezone.now():
        return True, int(unlock_at.timestamp() * 1000), username
    return False, 0, ""


def _attempts_left(request, form):
    """Tries remaining before lockout for this wrong-PIN submit (or None)."""
    from axes.conf import settings as axes_settings
    try:
        username = (form.cleaned_data.get("username") or "").strip()
    except Exception:
        username = ""
    if not username:
        username = (request.POST.get("username") or "").strip()
    total, _latest = _username_failures(username, _client_ip(request))
    if not total:
        return None
    limit = getattr(axes_settings, "AXES_FAILURE_LIMIT", 5)
    return max(0, limit - total)


def lockout_redirect(request, credentials=None):
    """AXES_LOCKOUT_CALLABLE: a locked-out POST lands back on the login
    page (?locked=1) with a countdown instead of axes' bare 403 page."""
    username = ""
    try:
        username = ((credentials or {}).get("username") or "").strip()
    except Exception:
        username = ""
    if username:
        request.session["lockout_username"] = username
    return redirect(f"{reverse('accounts:login')}?locked=1")

class CustomLoginView(LoginView):
    """
    Login view.
    - Uses Django's built-in LoginView (handles auth, sessions, CSRF).
    - After successful login, redirect to the Site list (the app's landing page).
    - Wrong credentials → Django shows the form error automatically, plus
      how many tries are left before the 1-hour lockout.
    - Locked out (5 wrong tries) → axes sends the POST to lockout_redirect
      below, which bounces back here with ?locked=1 and a live countdown.
    """
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        locked, unlock_ms, locked_username = _lockout_info(self.request)
        ctx["locked_out"] = locked
        ctx["lockout_until_ms"] = unlock_ms
        ctx["locked_username"] = locked_username
        return ctx

    def form_valid(self, form):
        # Sahi login: is browser ka lockout-nishan hatao (doosri id ka
        # timer ab is login ko confuse nahi karega).
        try:
            self.request.session.pop("lockout_username", None)
        except Exception:
            pass
        return super().form_valid(form)

    def form_invalid(self, form):
        # Wrong PIN but not yet locked: tell staff how many tries remain
        # (the axes counter already includes this failure).
        left = _attempts_left(self.request, form)
        if left is not None and left > 0:
            form.add_error(
                None,
                f"Galat PIN — {left} koshish "
                f"{'bachi hai' if left == 1 else 'bachi hain'} "
                f"(uske baad 1 ghante ka lock).",
            )
        return super().form_invalid(form)

    def get_success_url(self):
        # Session expired on a deep page (or a shared link): take the user
        # back where they were headed. get_redirect_url() only honours
        # safe same-host ?next= values (open-redirect proof by Django), and
        # landing on the login page itself just bounces to the dashboard via
        # redirect_authenticated_user — so no redirect loop is possible.
        # Default for plain logins is the Dashboard for both roles.
        return self.get_redirect_url() or reverse_lazy("dashboard")


# Kept for backward compatibility (bookmarks to /accounts/admin-dashboard/ and
# /accounts/staff-dashboard/ still work) — they now redirect to the Dashboard.
@login_required
def admin_dashboard(request):
    return redirect("dashboard")


@login_required
def staff_dashboard(request):
    return redirect("dashboard")


# --- Staff management (admin only) -------------------------------------------

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin-only pages: staff get 403 (same behavior as the Audit Log page)."""
    def test_func(self):
        return _user_is_admin(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


def _manageable_queryset():
    # Staff + managers only — superusers and admins are never manageable here.
    return User.objects.filter(
        role__in=[User.Role.STAFF, User.Role.MANAGER], is_superuser=False
    ).order_by("username")


class StaffListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/staff_list.html"
    context_object_name = "staff_members"

    def get_queryset(self):
        return _manageable_queryset()


class StaffCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = StaffCreateForm
    template_name = "accounts/staff_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Add New Member"
        ctx["form_subtitle"] = "Create a login and pick a role: Staff enters Inward/Outward data, Manager has full access like admin."
        ctx["submit_label"] = "Create Member Account"
        ctx["back_url"] = reverse("accounts:staff_list")
        return ctx

    def form_valid(self, form):
        # Grab the plain-text password BEFORE save — after this point only
        # the hash exists, so this success message is the one and only
        # chance to share it with the new member.
        raw_password = form.cleaned_data.get("password1", "")
        response = super().form_valid(form)
        from entries.models import AuditLog
        from entries.views import log_audit
        log_audit(
            self.request.user, AuditLog.Action.CREATE,
            AuditLog.EntryType.STAFF, form.instance.pk,
            f"Member '{form.instance.username}' created with role "
            f"'{form.instance.get_role_display()}'.",
        )
        messages.success(
            self.request,
            f"Member '{form.instance.username}' created — password is "
            f"'{raw_password}'. Share it with them now; it cannot be viewed again.",
        )
        return response

    def get_success_url(self):
        return reverse("accounts:staff_list")


class StaffUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = StaffEditForm
    template_name = "accounts/staff_form.html"

    def get_queryset(self):
        return _manageable_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = f"Edit Member — {self.object.username}"
        ctx["form_subtitle"] = "Change the username or role for this login."
        ctx["submit_label"] = "Save Changes"
        ctx["back_url"] = reverse("accounts:staff_list")
        return ctx

    def form_valid(self, form):
        changed = list(getattr(form, "changed_data", []))
        response = super().form_valid(form)
        from entries.models import AuditLog
        from entries.views import log_audit
        summary = (
            f"Member '{form.instance.username}' updated "
            f"(role '{form.instance.get_role_display()}')."
        )
        if changed:
            summary += f" (changed: {', '.join(changed)})"
        log_audit(
            self.request.user, AuditLog.Action.EDIT,
            AuditLog.EntryType.STAFF, form.instance.pk, summary,
        )
        messages.success(self.request, f"Member account updated to '{form.instance.username}'.")
        return response

    def get_success_url(self):
        return reverse("accounts:staff_list")


class StaffPasswordResetView(AdminRequiredMixin, FormView):
    """
    Admin sets a new 4-digit PIN directly for a staff user. No old password,
    no email flow. Uses SetPasswordForm → set_password(), never plain text.
    """
    form_class = StaffResetForm
    template_name = "accounts/staff_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.staff_user = get_object_or_404(_manageable_queryset(), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.staff_user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = f"Reset PIN — {self.staff_user.username}"
        ctx["form_subtitle"] = "Set a new 4-digit PIN for this login. Tell it to them directly."
        ctx["submit_label"] = "Reset PIN"
        ctx["back_url"] = reverse("accounts:staff_list")
        return ctx

    def form_valid(self, form):
        form.save()
        from entries.models import AuditLog
        from entries.views import log_audit
        log_audit(
            self.request.user, AuditLog.Action.EDIT,
            AuditLog.EntryType.STAFF, self.staff_user.pk,
            f"PIN reset for member '{self.staff_user.username}'.",
        )
        messages.success(
            self.request,
            f"PIN reset for '{self.staff_user.username}'.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("accounts:staff_list")


class StaffDeleteView(AdminRequiredMixin, View):
    """
    Permanently delete a member account. POST-only with a browser confirm
    on the staff list. Safe by design: entries have no FK to User so none
    are deleted, and audit rows keep working via SET_NULL (they show a
    blank user but keep the summary). You cannot delete your own account.
    """
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if kwargs["pk"] == request.user.pk:
            messages.error(request, "You cannot delete your own account.")
            return redirect("accounts:staff_list")
        staff_user = get_object_or_404(_manageable_queryset(), pk=kwargs["pk"])
        username = staff_user.username
        staff_pk = staff_user.pk
        staff_role = staff_user.get_role_display()
        staff_user.delete()
        from entries.models import AuditLog
        from entries.views import log_audit
        log_audit(
            request.user, AuditLog.Action.DELETE,
            AuditLog.EntryType.STAFF, staff_pk,
            f"Member '{username}' (role '{staff_role}') deleted.",
        )
        messages.success(
            request,
            f"'{username}' deleted. Their past entries and audit history are kept.",
        )
        return redirect("accounts:staff_list")



