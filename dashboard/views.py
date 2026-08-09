"""Staff dashboard - a Metronic-skinned replacement for Django's admin.

Every view is function based to match the style of `pages.views`. Access is
gated by the decorators in `dashboard.access`.
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from pages.models import (
    Application,
    Consultation,
    Enquiry,
    Service,
    SiteSettings,
    TeamMember,
    Vacancy,
)

from .access import permission_required, staff_required
from .forms import (
    AccountForm,
    DashboardLoginForm,
    EnquiryUpdateForm,
    GroupForm,
    MetronicPasswordChangeForm,
    MetronicSetPasswordForm,
    ServiceForm,
    StaffPasswordResetForm,
    UserForm,
)

PAGE_SIZE = 10
CHART_DAYS = 14


# ------------------------------------------------------------------ helpers


def _paginate(request, queryset, per_page=PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def _querystring(request):
    """Current GET params minus `page`, ready to prefix a page number.

    Lets the pager keep search and filter state across pages.
    """
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"{encoded}&" if encoded else ""


def _enquiry_series(days=CHART_DAYS):
    """Enquiry counts per day for the last `days` days, zero-filled.

    Zero-filling matters: ApexCharts needs one point per label, and days with
    no enquiries do not appear in the GROUP BY result.
    """
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        Enquiry.objects.exclude(status=Enquiry.Status.SPAM)
        .filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
    )
    counts = {row["day"]: row["total"] for row in rows}
    labels, values = [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        values.append(counts.get(day, 0))
    return labels, values


# --------------------------------------------------------------------- auth


class DashboardLoginView(auth_views.LoginView):
    template_name = "dashboard/login.html"
    authentication_form = DashboardLoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse_lazy("dashboard:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Django's LoginView puts a `site` (a RequestSite - domain and
        # hostname) into the context, which shadows the SiteSettings row the
        # context processor provides. Left alone, the login page shows the
        # hostname as the business name and renders an empty favicon.
        context["site"] = SiteSettings.load()
        return context


class DashboardLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("dashboard:login")


# --------------------------------------------------------- forgot password


class DashboardPasswordResetView(auth_views.PasswordResetView):
    template_name = "dashboard/auth/password_reset.html"
    email_template_name = "dashboard/auth/password_reset_email.txt"
    subject_template_name = "dashboard/auth/password_reset_subject.txt"
    form_class = StaffPasswordResetForm
    success_url = reverse_lazy("dashboard:password_reset_done")


class DashboardPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "dashboard/auth/password_reset_done.html"


class DashboardPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "dashboard/auth/password_reset_confirm.html"
    form_class = MetronicSetPasswordForm
    success_url = reverse_lazy("dashboard:password_reset_complete")


class DashboardPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "dashboard/auth/password_reset_complete.html"


# ------------------------------------------------------------- own account


@staff_required
def account(request):
    """Your own profile. Available to any staff user without needing
    `auth.change_user`, which governs editing *other* people."""
    form = AccountForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your details were updated.")
        return redirect("dashboard:account")

    return render(
        request,
        "dashboard/account.html",
        {
            "page_title": "My Account",
            "breadcrumb": [("My Account", None)],
            "form": form,
        },
    )


class DashboardPasswordChangeView(auth_views.PasswordChangeView):
    """Change your own password while signed in."""

    template_name = "dashboard/password_change.html"
    form_class = MetronicPasswordChangeForm
    success_url = reverse_lazy("dashboard:account")

    def dispatch(self, request, *args, **kwargs):
        return staff_required(super().dispatch)(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", "Change Password")
        context.setdefault(
            "breadcrumb", [("My Account", "dashboard:account"), ("Change Password", None)]
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, "Your password was changed.")
        return super().form_valid(form)


# ---------------------------------------------------------------- dashboard


@staff_required
def index(request):
    """The overview.

    Every block is gated on the same permission as the screen it summarises.
    A count is information: showing "12 users" to someone who cannot open the
    user list still tells them how many users exist. So each tile and panel is
    only built - and only queried - when the viewer is allowed to see it.
    """
    can = request.user.has_perm
    context = {
        "page_title": "Dashboard",
        "breadcrumb": [],
        "tiles": [],
        "panels": [],
    }

    # ------------------------------------------------------------- tiles

    if can("pages.view_consultation"):
        waiting = Consultation.objects.open_requests().count()
        context["tiles"].append(
            {
                "label": "Consultations to confirm",
                "value": waiting,
                "hint": "Promised within one business day",
                "icon": "ki-calendar-tick",
                "tone": "warning" if waiting else "primary",
                "url": reverse("dashboard:consultation_list") + "?status=requested",
            }
        )

    if can("pages.view_enquiry"):
        enquiries = Enquiry.objects.exclude(status=Enquiry.Status.SPAM)
        week_ago = timezone.localdate() - timedelta(days=6)
        context["tiles"].append(
            {
                "label": "Enquiries",
                "value": enquiries.count(),
                "hint": f"{enquiries.filter(created_at__date__gte=week_ago).count()} in the last 7 days",
                "icon": "ki-sms",
                "tone": "primary",
                "url": reverse("dashboard:enquiry_list"),
            }
        )

    if can("pages.view_application"):
        new_applications = Application.objects.filter(
            status=Application.Status.NEW
        ).count()
        context["tiles"].append(
            {
                "label": "New applications",
                "value": new_applications,
                "hint": f"{Application.objects.count()} received in total",
                "icon": "ki-document",
                "tone": "info",
                "url": reverse("dashboard:application_list") + "?status=new",
            }
        )

    if can("pages.view_vacancy"):
        context["tiles"].append(
            {
                "label": "Open vacancies",
                "value": Vacancy.objects.open_now().count(),
                "hint": "Advertised on the careers page",
                "icon": "ki-note-2",
                "tone": "success",
                "url": reverse("dashboard:vacancy_list") + "?state=open",
            }
        )

    if can("auth.view_user"):
        context["tiles"].append(
            {
                "label": "Users",
                "value": User.objects.count(),
                "hint": "%d with dashboard access"
                % User.objects.filter(is_staff=True, is_active=True).count(),
                "icon": "ki-profile-circle",
                "tone": "primary",
                "url": reverse("dashboard:user_list"),
            }
        )

    if can("auth.view_group"):
        context["tiles"].append(
            {
                "label": "Roles",
                "value": Group.objects.count(),
                "hint": "Permission groups defined",
                "icon": "ki-security-user",
                "tone": "info",
                "url": reverse("dashboard:group_list"),
            }
        )

    # ------------------------------------------------- enquiries + activity

    if can("pages.view_enquiry"):
        enquiries = Enquiry.objects.exclude(status=Enquiry.Status.SPAM)
        labels, values = _enquiry_series()
        status_counts = {
            row["status"]: row["total"]
            for row in enquiries.values("status").annotate(total=Count("id"))
        }
        context["chart"] = {"labels": labels, "values": values, "days": CHART_DAYS}
        context["enquiries_total"] = enquiries.count()
        context["status_counts"] = [
            (label, status_counts.get(value, 0), Enquiry(status=value).status_css)
            for value, label in Enquiry.Status.choices
            if value != Enquiry.Status.SPAM
        ]
        context["recent_enquiries"] = enquiries[:6]

    if can("pages.view_consultation"):
        context["upcoming_consultations"] = Consultation.objects.upcoming()[:5]

    if can("pages.view_application"):
        context["recent_applications"] = Application.objects.select_related(
            "vacancy"
        )[:5]

    if can("auth.view_user"):
        context["recent_users"] = User.objects.order_by("-date_joined")[:5]

    if can("auth.view_group"):
        context["roles"] = (
            Group.objects.annotate(member_count=Count("user")).order_by("name")[:5]
        )

    # --------------------------------------------------------- site content

    content_rows = []
    if can("pages.view_service"):
        content_rows.append(
            {
                "label": "Services",
                "live": Service.objects.published().count(),
                "draft": Service.objects.filter(is_published=False).count(),
                "url": reverse("dashboard:service_list"),
            }
        )
    if can("pages.view_teammember"):
        content_rows.append(
            {
                "label": "Team members",
                "live": TeamMember.objects.published().count(),
                "draft": TeamMember.objects.filter(is_published=False).count(),
                "url": reverse("dashboard:team_list"),
            }
        )
    if can("pages.view_vacancy"):
        content_rows.append(
            {
                "label": "Vacancies",
                "live": Vacancy.objects.open_now().count(),
                "draft": Vacancy.objects.filter(is_published=False).count(),
                "url": reverse("dashboard:vacancy_list"),
            }
        )
    context["content_rows"] = content_rows

    # True when the viewer can see nothing but their own account.
    context["nothing_to_show"] = not (context["tiles"] or content_rows)

    return render(request, "dashboard/index.html", context)


# -------------------------------------------------------------------- users


@permission_required("auth.view_user")
def user_list(request):
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    users = User.objects.prefetch_related("groups").order_by("username")

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role:
        users = users.filter(groups__id=role)

    return render(
        request,
        "dashboard/users/list.html",
        {
            "page_title": "Users",
            "breadcrumb": [("Users", None)],
            "page_obj": _paginate(request, users),
            "querystring": _querystring(request),
            "query": query,
            "role": role,
            "roles": Group.objects.order_by("name"),
        },
    )


@permission_required("auth.add_user")
def user_create(request):
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"User “{user.username}” was created.")
        return redirect("dashboard:user_list")
    return render(
        request,
        "dashboard/users/form.html",
        {
            "page_title": "Add User",
            "breadcrumb": [("Users", "dashboard:user_list"), ("Add User", None)],
            "form": form,
            "object": None,
        },
    )


@permission_required("auth.change_user")
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"User “{user.username}” was updated.")
        return redirect("dashboard:user_list")
    return render(
        request,
        "dashboard/users/form.html",
        {
            "page_title": f"Edit {user.username}",
            "breadcrumb": [("Users", "dashboard:user_list"), (user.username, None)],
            "form": form,
            "object": user,
        },
    )


@permission_required("auth.delete_user")
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)

    if user == request.user:
        messages.error(request, "You cannot delete the account you are signed in as.")
        return redirect("dashboard:user_list")

    if request.method == "POST":
        username = user.username
        user.delete()
        messages.success(request, f"User “{username}” was deleted.")
        return redirect("dashboard:user_list")

    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "page_title": "Delete User",
            "breadcrumb": [("Users", "dashboard:user_list"), ("Delete", None)],
            "object": user,
            "object_label": f"the user “{user.username}”",
            "cancel_url": "dashboard:user_list",
        },
    )


# -------------------------------------------------------------- roles/groups


@permission_required("auth.view_group")
def group_list(request):
    groups = Group.objects.annotate(
        member_count=Count("user", distinct=True),
        permission_count=Count("permissions", distinct=True),
    ).order_by("name")
    return render(
        request,
        "dashboard/groups/list.html",
        {
            "page_title": "Roles",
            "breadcrumb": [("Roles", None)],
            "page_obj": _paginate(request, groups),
            "querystring": _querystring(request),
        },
    )


@permission_required("auth.add_group")
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, f"Role “{group.name}” was created.")
        return redirect("dashboard:group_list")
    return render(
        request,
        "dashboard/groups/form.html",
        {
            "page_title": "Add Role",
            "breadcrumb": [("Roles", "dashboard:group_list"), ("Add Role", None)],
            "form": form,
            "object": None,
        },
    )


@permission_required("auth.change_group")
def group_update(request, pk):
    group = get_object_or_404(Group, pk=pk)
    form = GroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Role “{group.name}” was updated.")
        return redirect("dashboard:group_list")
    return render(
        request,
        "dashboard/groups/form.html",
        {
            "page_title": f"Edit {group.name}",
            "breadcrumb": [("Roles", "dashboard:group_list"), (group.name, None)],
            "form": form,
            "object": group,
        },
    )


@permission_required("auth.delete_group")
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == "POST":
        name = group.name
        group.delete()
        messages.success(request, f"Role “{name}” was deleted.")
        return redirect("dashboard:group_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "page_title": "Delete Role",
            "breadcrumb": [("Roles", "dashboard:group_list"), ("Delete", None)],
            "object": group,
            "object_label": f"the role “{group.name}”",
            "extra_warning": (
                f"{group.user_set.count()} user(s) will lose the permissions this "
                "role grants."
            ),
            "cancel_url": "dashboard:group_list",
        },
    )


# ----------------------------------------------------------------- services


@permission_required("pages.view_service")
def service_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    services = Service.objects.all()

    if query:
        services = services.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(description__icontains=query)
        )
    if state == "published":
        services = services.filter(is_published=True)
    elif state == "draft":
        services = services.filter(is_published=False)

    return render(
        request,
        "dashboard/services/list.html",
        {
            "page_title": "Services",
            "breadcrumb": [("Services", None)],
            "page_obj": _paginate(request, services),
            "querystring": _querystring(request),
            "query": query,
            "state": state,
            "draft_count": Service.objects.filter(is_published=False).count(),
        },
    )


@permission_required("pages.add_service")
def service_create(request):
    form = ServiceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        service = form.save()
        messages.success(request, f"Service “{service.title}” was created.")
        return redirect("dashboard:service_list")
    return render(
        request,
        "dashboard/services/form.html",
        {
            "page_title": "Add Service",
            "breadcrumb": [("Services", "dashboard:service_list"), ("Add Service", None)],
            "form": form,
            "object": None,
        },
    )


@permission_required("pages.change_service")
def service_update(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, request.FILES or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Service “{service.title}” was updated.")
        return redirect("dashboard:service_list")
    return render(
        request,
        "dashboard/services/form.html",
        {
            "page_title": f"Edit {service.title}",
            "breadcrumb": [("Services", "dashboard:service_list"), (service.title, None)],
            "form": form,
            "object": service,
        },
    )


@permission_required("pages.delete_service")
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        title = service.title
        service.delete()
        messages.success(request, f"Service “{title}” was deleted.")
        return redirect("dashboard:service_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "page_title": "Delete Service",
            "breadcrumb": [("Services", "dashboard:service_list"), ("Delete", None)],
            "object": service,
            "object_label": f"the service “{service.title}”",
            "extra_warning": (
                "It will disappear from the website immediately. To hide it "
                "without losing the content, untick Published instead."
            ),
            "cancel_url": "dashboard:service_list",
        },
    )


# ---------------------------------------------------------------- enquiries


@permission_required("pages.view_enquiry")
def enquiry_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    assigned = request.GET.get("assigned", "")
    enquiries = Enquiry.objects.select_related("handled_by")

    if query:
        enquiries = enquiries.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(message__icontains=query)
        )
    if assigned == "unassigned":
        enquiries = enquiries.filter(handled_by__isnull=True)
    elif assigned == "me":
        enquiries = enquiries.filter(handled_by=request.user)
    elif assigned.isdigit():
        enquiries = enquiries.filter(handled_by_id=int(assigned))
    if status:
        enquiries = enquiries.filter(status=status)
    else:
        # Suspected spam is hidden by default but still reachable through the
        # status filter, so a honeypot false positive is never lost.
        enquiries = enquiries.exclude(status=Enquiry.Status.SPAM)

    return render(
        request,
        "dashboard/enquiries/list.html",
        {
            "page_title": "Enquiries",
            "breadcrumb": [("Enquiries", None)],
            "page_obj": _paginate(request, enquiries),
            "querystring": _querystring(request),
            "query": query,
            "status": status,
            "statuses": Enquiry.Status.choices,
            "assigned": assigned,
            "assignees": User.objects.filter(
                is_staff=True, is_active=True
            ).order_by("username"),
            "unassigned_count": Enquiry.objects.filter(
                handled_by__isnull=True
            ).exclude(status=Enquiry.Status.SPAM).count(),
            "spam_count": Enquiry.objects.filter(status=Enquiry.Status.SPAM).count(),
        },
    )


@permission_required("pages.view_enquiry")
def enquiry_detail(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    can_edit = request.user.has_perm("pages.change_enquiry")
    form = EnquiryUpdateForm(
        request.POST or None if can_edit else None, instance=enquiry
    )

    if request.method == "POST":
        if not can_edit:
            messages.error(request, "You do not have permission to update enquiries.")
        elif form.is_valid():
            form.save()
            messages.success(request, "Enquiry updated.")
            return redirect("dashboard:enquiry_detail", pk=enquiry.pk)

    return render(
        request,
        "dashboard/enquiries/detail.html",
        {
            "page_title": f"Enquiry from {enquiry.name}",
            "breadcrumb": [
                ("Enquiries", "dashboard:enquiry_list"),
                (enquiry.name, None),
            ],
            "enquiry": enquiry,
            "form": form,
            "can_edit": can_edit,
        },
    )
