import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.cache import cache
from django.http import HttpResponse

from . import content
from . import consultation_mail
from . import notifications
from . import ratelimit
from . import structured_data
from . import turnstile
from .forms import ApplicationForm, ConsultationForm, ContactForm
from .models import Consultation, Enquiry, Service, SiteSettings, TeamMember, Vacancy

logger = logging.getLogger(__name__)


def home(request):
    return render(
        request,
        "pages/home.html",
        {
            "why_us": content.WHY_US,
            # Four cards fit the design's row; the rest live on /services/.
            "featured_services": Service.objects.published()[:4],
        },
    )


def about(request):
    return render(
        request,
        "pages/about.html",
        {"values": content.VALUES, "team": TeamMember.objects.published()},
    )


def team_member(request, slug):
    member = get_object_or_404(TeamMember.objects.published(), slug=slug)
    return render(
        request,
        "pages/team_member.html",
        {
            "member": member,
            "colleagues": TeamMember.objects.published().exclude(pk=member.pk)[:4],
            "page_schema": structured_data.person(request, member, SiteSettings.load()),
            "breadcrumb_schema": structured_data.breadcrumbs(
                request,
                [
                    ("Home", reverse("home")),
                    ("About Us", reverse("about")),
                    (member.name, None),
                ],
            ),
        },
    )


def services(request):
    return render(
        request,
        "pages/services.html",
        {
            "service_list": Service.objects.published(),
            "service_promises": content.SERVICE_PROMISES,
        },
    )


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.published(), slug=slug)
    return render(
        request,
        "pages/service_detail.html",
        {
            "service": service,
            "related": Service.objects.published().exclude(pk=service.pk)[:3],
            "page_schema": structured_data.service(
                request, service, SiteSettings.load()
            ),
            "breadcrumb_schema": structured_data.breadcrumbs(
                request,
                [
                    ("Home", reverse("home")),
                    ("Services", reverse("services")),
                    (service.title, None),
                ],
            ),
        },
    )


def ndis_support(request):
    return render(
        request,
        "pages/ndis_support.html",
        {
            "ndis_highlights": content.NDIS_HIGHLIGHTS,
            "ndis_steps": content.NDIS_STEPS,
            "ndis_services": content.NDIS_SERVICES,
        },
    )


def careers(request):
    return render(
        request,
        "pages/careers.html",
        {
            "career_benefits": content.CAREER_BENEFITS,
            "vacancies": Vacancy.objects.open_now(),
        },
    )


def vacancy_detail(request, slug):
    """A single advert, with its application form.

    Closed and unpublished vacancies 404 rather than showing a dead advert.
    """
    vacancy = get_object_or_404(Vacancy.objects.published(), slug=slug)
    return _application_page(
        request,
        vacancy=vacancy,
        template="pages/vacancy_detail.html",
        extra={
            "other_vacancies": Vacancy.objects.open_now().exclude(pk=vacancy.pk)[:3],
            "page_schema": structured_data.job_posting(
                request, vacancy, SiteSettings.load()
            ),
            "breadcrumb_schema": structured_data.breadcrumbs(
                request,
                [
                    ("Home", reverse("home")),
                    ("Careers", reverse("careers")),
                    (vacancy.title, None),
                ],
            ),
        },
    )


def speculative_application(request):
    """"Don't see the right role?" - an application not tied to a vacancy."""
    return _application_page(
        request, vacancy=None, template="pages/apply_speculative.html", extra={}
    )


def _application_page(request, *, vacancy, template, extra):
    landing = vacancy.get_absolute_url() if vacancy else reverse("apply")

    if vacancy is not None and not vacancy.accepts_applications:
        # Advert still visible, but the form is not offered.
        form = None
    elif request.method == "POST":
        client_ip = get_client_ip(request)

        # Before the form is built, so a flood is turned away before Django
        # parses the multipart body and writes the resume to storage.
        if ratelimit.is_over_limit(ratelimit.APPLICATION, ip=client_ip):
            return _too_many(
                request, ratelimit.APPLICATION, redirect_to=landing, ip=client_ip
            )

        form = ApplicationForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            if ratelimit.is_over_limit(ratelimit.APPLICATION, email=email):
                return _too_many(
                    request,
                    ratelimit.APPLICATION,
                    redirect_to=landing,
                    ip=client_ip,
                    email=email,
                )

            ratelimit.record(ratelimit.APPLICATION, ip=client_ip, email=email)

            application = form.save(commit=False)
            application.vacancy = vacancy
            application.vacancy_title = vacancy.title if vacancy else ""
            application.save()
            notifications.application_received(request, application)
            messages.success(
                request,
                "Thank you for applying. We'll be in touch about the next steps.",
            )
            return redirect(landing)
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = ApplicationForm(request=request)

    return render(request, template, {"vacancy": vacancy, "form": form, **extra})

def get_client_ip(request):
    """The visitor's address, behind Cloudflare or not.

    One definition, shared with Turnstile: the rate limiter and `remoteip` on
    the siteverify call have to agree about who the client is, or the two
    protections are counting different people.
    """
    return turnstile.client_ip(request) or "unknown"


def _too_many(request, scope, *, redirect_to, ip, email=None):
    """Turn a visitor away, having hit the daily limit on this form.

    Always with the phone number: the limit exists to stop a flood, not to
    stop someone reaching an NDIS provider, and several people can share one
    address - an office, a group home, a mobile network. Anyone caught by it
    needs a way through that does not involve waiting a day.
    """
    ratelimit.blocked(scope, ip=ip, email=email)
    phone = SiteSettings.load().phone or settings.CONSULTATION_PHONE
    messages.error(request, ratelimit.LIMIT_MESSAGE % phone)
    return redirect(redirect_to)


def contact(request):
    """The enquiry form.

    Four things guard it, in increasing cost: the daily limit (a cache read),
    field validation, Turnstile (one call to Cloudflare, in the form's clean),
    and the honeypot. Order matters - the cheap checks come first so a flood
    is turned away without touching the database or the network.
    """
    if request.method == "POST":
        client_ip = get_client_ip(request)

        # Checked before validation because it costs one cache read and needs
        # nothing from the visitor.
        if ratelimit.is_over_limit(ratelimit.CONTACT, ip=client_ip):
            return _too_many(
                request, ratelimit.CONTACT, redirect_to="contact", ip=client_ip
            )

        form = ContactForm(request.POST, request=request)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            # Only now is there an email address to check.
            if ratelimit.is_over_limit(ratelimit.CONTACT, email=email):
                return _too_many(
                    request,
                    ratelimit.CONTACT,
                    redirect_to="contact",
                    ip=client_ip,
                    email=email,
                )

            # Counted before the honeypot is consulted, so that tripping the
            # trap over and over still uses up the sender's allowance.
            ratelimit.record(ratelimit.CONTACT, ip=client_ip, email=email)

            spam = form.is_probably_spam()

            enquiry = Enquiry.objects.create(
                name=form.cleaned_data["name"],
                email=email,
                phone=form.cleaned_data["phone"],
                message=form.cleaned_data["message"],
                status=Enquiry.Status.SPAM if spam else Enquiry.Status.NEW,
            )

            if spam:
                # Quarantined, not discarded. The honeypot can misfire on a
                # real person - a browser autofilling a hidden field - and a
                # dropped message from someone asking about disability support
                # is not recoverable. It is kept out of the dashboard's lists
                # and counts until a staff member looks at the spam folder and
                # says otherwise.
                logger.warning(
                    "Contact form honeypot tripped, quarantined as #%s: ip=%s email=%s",
                    enquiry.pk,
                    client_ip,
                    email,
                )
            else:
                notifications.enquiry_received(request, enquiry)

            # The same words either way. A bot that is told it was caught
            # learns to avoid the trap; a person whose message was wrongly
            # flagged is not left thinking it failed to send.
            messages.success(
                request,
                "Thank you for getting in touch. "
                "We'll respond within one business day.",
            )

            return redirect("contact")

        messages.error(
            request,
            "Please check the highlighted fields and try again.",
        )

    else:
        initial = {}

        role = request.GET.get("role")

        if role:
            initial["message"] = (
                f"I would like to apply for the {role} position."
            )

        form = ContactForm(initial=initial, request=request)

    return render(
        request,
        "pages/contact.html",
        {"form": form},
    )


def consultation(request):
    """Request the free consultation advertised across the site.

    A request, not a live booking: the site promises "we will respond within
    one business day and arrange a time that suits you", so the visitor states
    their availability and staff confirm the exact time.
    """
    if request.method == "POST":
        client_ip = get_client_ip(request)

        if ratelimit.is_over_limit(ratelimit.CONSULTATION, ip=client_ip):
            return _too_many(
                request,
                ratelimit.CONSULTATION,
                redirect_to="consultation",
                ip=client_ip,
            )

        form = ConsultationForm(request.POST, request=request)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            if ratelimit.is_over_limit(ratelimit.CONSULTATION, email=email):
                return _too_many(
                    request,
                    ratelimit.CONSULTATION,
                    redirect_to="consultation",
                    ip=client_ip,
                    email=email,
                )

            # A consultation costs the most to process of the three: a row,
            # three emails, and staff time to confirm a slot.
            ratelimit.record(ratelimit.CONSULTATION, ip=client_ip, email=email)

            booking = form.save()
            consultation_mail.acknowledge(booking)
            notifications.consultation_requested(request, booking)
            request.session["consultation_reference"] = booking.reference
            return redirect("consultation_booked")
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = ConsultationForm(initial=_consultation_initial(request), request=request)

    return render(
        request,
        "pages/consultation.html",
        {"form": form, "steps": content.NDIS_STEPS},
    )


def _consultation_initial(request):
    """Preselect a service when arriving from that service's page."""
    slug = request.GET.get("service")
    if not slug:
        return {}
    service = Service.objects.published().filter(slug=slug).first()
    return {"services": [service.pk]} if service else {}


def consultation_booked(request):
    """Confirmation screen. The reference is carried in the session so it
    survives the redirect without exposing it in the URL."""
    reference = request.session.pop("consultation_reference", None)
    if not reference:
        return redirect("consultation")
    return render(
        request,
        "pages/consultation_booked.html",
        {"reference": reference, "steps": content.NDIS_STEPS},
    )


def faq(request):
    return render(
        request,
        "pages/faq.html",
        {
            "faqs": content.FAQS,
            "page_schema": structured_data.faq_page(content.FAQS),
        },
    )


def privacy_policy(request):
    return render(
        request,
        "pages/privacy_policy.html",
        {"privacy_sections": content.PRIVACY_SECTIONS},
    )


def terms(request):
    return render(
        request,
        "pages/terms.html",
        {"terms_sections": content.TERMS_SECTIONS},
    )


