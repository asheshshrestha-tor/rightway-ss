"""Access control for the staff dashboard.

Everything under /dashboard/ requires an authenticated, active staff user.
Individual views layer Django's model permissions on top of that, so a group
(role) such as "Enquiry Handler" can be given `pages.view_enquiry` without also
granting `auth.change_user`.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


def staff_required(view):
    """Allow only active staff members; send anyone else to the login page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("dashboard:login"))
        if not (user.is_active and user.is_staff):
            raise PermissionDenied(
                "Your account does not have access to the dashboard."
            )
        return view(request, *args, **kwargs)

    return wrapper


def permission_required(*perms):
    """Require staff access plus every listed model permission.

    Superusers pass automatically - `User.has_perm` already returns True for
    them - so this only ever gates non-superuser staff.
    """

    def decorator(view):
        @wraps(view)
        @staff_required
        def wrapper(request, *args, **kwargs):
            missing = [p for p in perms if not request.user.has_perm(p)]
            if missing:
                raise PermissionDenied(
                    "You do not have permission to do that (%s)." % ", ".join(missing)
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
