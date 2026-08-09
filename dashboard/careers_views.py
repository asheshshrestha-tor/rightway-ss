"""Dashboard screens for vacancies and job applications.

Split out of `views.py` to keep that module readable.
"""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from django.utils import timezone

from pages import consultation_mail
from pages.models import (
    Application,
    Consultation,
    SiteSettings,
    SocialLink,
    TeamMember,
    Vacancy,
)

from .access import permission_required
from .forms import (
    ApplicationUpdateForm,
    ConsultationUpdateForm,
    SiteSettingsForm,
    SocialLinkFormSet,
    TeamMemberForm,
    VacancyForm,
)
from .views import _paginate, _querystring

# ---------------------------------------------------------------- vacancies


@permission_required("pages.view_vacancy")
def vacancy_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")

    # annotate() introduces a GROUP BY, which drops Meta.ordering - so the
    # order is restated explicitly, otherwise pagination is non-deterministic.
    vacancies = Vacancy.objects.annotate(
        application_count=Count("applications")
    ).order_by("order", "title")

    if query:
        vacancies = vacancies.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        )
    if state == "open":
        vacancies = vacancies.filter(pk__in=Vacancy.objects.open_now())
    elif state == "draft":
        vacancies = vacancies.filter(is_published=False)
    elif state == "closed":
        vacancies = vacancies.filter(is_published=True).exclude(
            pk__in=Vacancy.objects.open_now()
        )

    return render(
        request,
        "dashboard/vacancies/list.html",
        {
            "page_title": "Vacancies",
            "breadcrumb": [("Vacancies", None)],
            "page_obj": _paginate(request, vacancies),
            "querystring": _querystring(request),
            "query": query,
            "state": state,
        },
    )


@permission_required("pages.add_vacancy")
def vacancy_create(request):
    form = VacancyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vacancy = form.save()
        messages.success(request, f"Vacancy “{vacancy.title}” was created.")
        return redirect("dashboard:vacancy_list")
    return render(
        request,
        "dashboard/vacancies/form.html",
        {
            "page_title": "Add Vacancy",
            "breadcrumb": [
                ("Vacancies", "dashboard:vacancy_list"),
                ("Add Vacancy", None),
            ],
            "form": form,
            "object": None,
        },
    )


@permission_required("pages.change_vacancy")
def vacancy_update(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    form = VacancyForm(request.POST or None, instance=vacancy)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Vacancy “{vacancy.title}” was updated.")
        return redirect("dashboard:vacancy_list")
    return render(
        request,
        "dashboard/vacancies/form.html",
        {
            "page_title": f"Edit {vacancy.title}",
            "breadcrumb": [
                ("Vacancies", "dashboard:vacancy_list"),
                (vacancy.title, None),
            ],
            "form": form,
            "object": vacancy,
        },
    )


@permission_required("pages.delete_vacancy")
def vacancy_delete(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    count = vacancy.applications.count()

    if request.method == "POST":
        title = vacancy.title
        vacancy.delete()
        messages.success(request, f"Vacancy “{title}” was deleted.")
        return redirect("dashboard:vacancy_list")

    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "page_title": "Delete Vacancy",
            "breadcrumb": [("Vacancies", "dashboard:vacancy_list"), ("Delete", None)],
            "object": vacancy,
            "object_label": f"the vacancy “{vacancy.title}”",
            "extra_warning": (
                f"{count} application(s) will be kept, but will no longer be "
                "linked to a vacancy. Untick Published instead to close the "
                "advert without losing that link."
            )
            if count
            else "Untick Published instead if you only want to close the advert.",
            "cancel_url": "dashboard:vacancy_list",
        },
    )


# ------------------------------------------------------------- applications


@permission_required("pages.view_application")
def application_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    vacancy = request.GET.get("vacancy", "")
    assigned = request.GET.get("assigned", "")

    applications = Application.objects.select_related("vacancy", "handled_by")

    if query:
        applications = applications.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(cover_letter__icontains=query)
        )
    if status:
        applications = applications.filter(status=status)
    if vacancy == "speculative":
        applications = applications.filter(vacancy__isnull=True)
    elif vacancy.isdigit():
        applications = applications.filter(vacancy_id=int(vacancy))
    if assigned == "me":
        applications = applications.filter(handled_by=request.user)
    elif assigned == "unassigned":
        applications = applications.filter(handled_by__isnull=True)
    elif assigned.isdigit():
        applications = applications.filter(handled_by_id=int(assigned))

    from django.contrib.auth.models import User

    return render(
        request,
        "dashboard/applications/list.html",
        {
            "page_title": "Applications",
            "breadcrumb": [("Applications", None)],
            "page_obj": _paginate(request, applications),
            "querystring": _querystring(request),
            "query": query,
            "status": status,
            "vacancy": vacancy,
            "assigned": assigned,
            "statuses": Application.Status.choices,
            "vacancies": Vacancy.objects.all(),
            "assignees": User.objects.filter(is_staff=True, is_active=True).order_by(
                "username"
            ),
        },
    )


@permission_required("pages.view_application")
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("vacancy", "handled_by"), pk=pk
    )
    can_edit = request.user.has_perm("pages.change_application")
    form = ApplicationUpdateForm(
        request.POST or None if can_edit else None, instance=application
    )

    if request.method == "POST":
        if not can_edit:
            messages.error(request, "You do not have permission to update applications.")
        elif form.is_valid():
            form.save()
            messages.success(request, "Application updated.")
            return redirect("dashboard:application_detail", pk=application.pk)

    return render(
        request,
        "dashboard/applications/detail.html",
        {
            "page_title": f"Application from {application.full_name}",
            "breadcrumb": [
                ("Applications", "dashboard:application_list"),
                (application.full_name, None),
            ],
            "application": application,
            "form": form,
            "can_edit": can_edit,
        },
    )


@permission_required("pages.view_application")
def application_resume(request, pk):
    """Stream a resume to an authorised staff member.

    Resumes are personal information, so they are stored outside MEDIA_ROOT and
    are not reachable over MEDIA_URL. This view is the only way to read one,
    and it runs behind the same permission as the application itself.
    """
    application = get_object_or_404(Application, pk=pk)

    if not application.resume:
        raise Http404("This application has no resume attached.")

    try:
        handle = application.resume.open("rb")
    except FileNotFoundError:  # the row outlived the file
        raise Http404("The resume file is missing from storage.")

    return FileResponse(
        handle,
        as_attachment=True,
        filename=f"{application.full_name} - {application.resume_name}",
    )


# ------------------------------------------------------------ consultations


@permission_required("pages.view_consultation")
def consultation_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    delivery = request.GET.get("delivery", "")
    assigned = request.GET.get("assigned", "")

    consultations = Consultation.objects.select_related("assigned_to")

    if query:
        consultations = consultations.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(reference__icontains=query)
            | Q(participant_name__icontains=query)
        )
    if status:
        consultations = consultations.filter(status=status)
    if delivery:
        consultations = consultations.filter(delivery=delivery)
    if assigned == "me":
        consultations = consultations.filter(assigned_to=request.user)
    elif assigned == "unassigned":
        consultations = consultations.filter(assigned_to__isnull=True)
    elif assigned.isdigit():
        consultations = consultations.filter(assigned_to_id=int(assigned))

    from django.contrib.auth.models import User

    return render(
        request,
        "dashboard/consultations/list.html",
        {
            "page_title": "Consultations",
            "breadcrumb": [("Consultations", None)],
            "page_obj": _paginate(request, consultations),
            "querystring": _querystring(request),
            "query": query,
            "status": status,
            "delivery": delivery,
            "assigned": assigned,
            "statuses": Consultation.Status.choices,
            "deliveries": Consultation.Delivery.choices,
            "assignees": User.objects.filter(is_staff=True, is_active=True).order_by(
                "username"
            ),
            "awaiting": Consultation.objects.open_requests().count(),
            "upcoming": Consultation.objects.upcoming()[:5],
        },
    )


@permission_required("pages.view_consultation")
def consultation_detail(request, pk):
    consultation = get_object_or_404(
        Consultation.objects.select_related("assigned_to").prefetch_related("services"),
        pk=pk,
    )
    can_edit = request.user.has_perm("pages.change_consultation")

    # Captured before the form runs: is_valid() calls _post_clean(), which
    # writes the submitted data onto `consultation` in place. Reading the
    # status afterwards would always show the new value, so a confirmation
    # would never look "new" and the participant would never be emailed.
    was_confirmed = consultation.status == Consultation.Status.CONFIRMED

    form = ConsultationUpdateForm(
        request.POST or None if can_edit else None, instance=consultation
    )

    if request.method == "POST":
        if not can_edit:
            messages.error(
                request, "You do not have permission to update consultations."
            )
        elif form.is_valid():
            booking = form.save()

            just_confirmed = (
                booking.status == Consultation.Status.CONFIRMED and not was_confirmed
            )
            if form.cleaned_data.get("send_confirmation") and just_confirmed:
                if consultation_mail.confirm(booking):
                    Consultation.objects.filter(pk=booking.pk).update(
                        confirmation_sent_at=timezone.now()
                    )
                    messages.success(
                        request,
                        f"Confirmed. {booking.full_name} has been emailed the time.",
                    )
                else:
                    messages.warning(
                        request,
                        "Saved, but the confirmation email could not be sent. "
                        "Please call the participant instead.",
                    )
            else:
                messages.success(request, "Consultation updated.")

            return redirect("dashboard:consultation_detail", pk=booking.pk)

    return render(
        request,
        "dashboard/consultations/detail.html",
        {
            "page_title": f"Consultation {consultation.reference}",
            "breadcrumb": [
                ("Consultations", "dashboard:consultation_list"),
                (consultation.reference, None),
            ],
            "consultation": consultation,
            "form": form,
            "can_edit": can_edit,
        },
    )


# --------------------------------------------------------------- team members


@permission_required("pages.view_teammember")
def team_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    members = TeamMember.objects.all()

    if query:
        members = members.filter(Q(name__icontains=query) | Q(role__icontains=query))
    if state == "published":
        members = members.filter(is_published=True)
    elif state == "draft":
        members = members.filter(is_published=False)

    return render(
        request,
        "dashboard/team/list.html",
        {
            "page_title": "Team",
            "breadcrumb": [("Team", None)],
            "page_obj": _paginate(request, members),
            "querystring": _querystring(request),
            "query": query,
            "state": state,
            "draft_count": TeamMember.objects.filter(is_published=False).count(),
        },
    )


@permission_required("pages.add_teammember")
def team_create(request):
    form = TeamMemberForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        member = form.save()
        messages.success(request, f"{member.name} was added to the team.")
        return redirect("dashboard:team_list")
    return render(
        request,
        "dashboard/team/form.html",
        {
            "page_title": "Add Team Member",
            "breadcrumb": [("Team", "dashboard:team_list"), ("Add", None)],
            "form": form,
            "object": None,
        },
    )


@permission_required("pages.change_teammember")
def team_update(request, pk):
    member = get_object_or_404(TeamMember, pk=pk)
    form = TeamMemberForm(request.POST or None, request.FILES or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{member.name} was updated.")
        return redirect("dashboard:team_list")
    return render(
        request,
        "dashboard/team/form.html",
        {
            "page_title": f"Edit {member.name}",
            "breadcrumb": [("Team", "dashboard:team_list"), (member.name, None)],
            "form": form,
            "object": member,
        },
    )


@permission_required("pages.delete_teammember")
def team_delete(request, pk):
    member = get_object_or_404(TeamMember, pk=pk)
    if request.method == "POST":
        name = member.name
        member.delete()
        messages.success(request, f"{name} was removed from the team.")
        return redirect("dashboard:team_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "page_title": "Remove Team Member",
            "breadcrumb": [("Team", "dashboard:team_list"), ("Remove", None)],
            "object": member,
            "object_label": f"{member.name} from the team",
            "extra_warning": (
                "Their profile page will stop working immediately. Untick "
                "Published instead to hide them without losing the content."
            ),
            "cancel_url": "dashboard:team_list",
        },
    )


# ------------------------------------------------------------ site settings


@permission_required("pages.change_sitesettings")
def site_settings(request):
    """Branding, contact details, footer, map and social links on one screen.

    Social links are a formset rather than their own CRUD: there are only ever
    a handful, and editing them beside the contact details is how someone
    actually thinks about "our details".
    """
    settings_row = SiteSettings.load()
    form = SiteSettingsForm(
        request.POST or None, request.FILES or None, instance=settings_row
    )
    formset = SocialLinkFormSet(
        request.POST or None, queryset=SocialLink.objects.all()
    )

    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Site settings were updated.")
            return redirect("dashboard:site_settings")
        messages.error(request, "Please check the highlighted fields and try again.")

    return render(
        request,
        "dashboard/settings/form.html",
        {
            "page_title": "Site Settings",
            "breadcrumb": [("Site Settings", None)],
            "form": form,
            "formset": formset,
            "object": settings_row,
        },
    )
