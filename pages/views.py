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
from . import structured_data
from .forms import ApplicationForm, ConsultationForm, ContactForm
from .models import Consultation, Enquiry, Service, SiteSettings, TeamMember, Vacancy

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Contact form rate limits
# -------------------------------------------------------------------

CONTACT_IP_LIMIT = 3
CONTACT_IP_TIMEOUT = 60 * 10       # 10 minutes

CONTACT_EMAIL_LIMIT = 3
CONTACT_EMAIL_TIMEOUT = 60 * 60    # 1 hour

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
    if vacancy is not None and not vacancy.accepts_applications:
        # Advert still visible, but the form is not offered.
        form = None
    elif request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.vacancy = vacancy
            application.vacancy_title = vacancy.title if vacancy else ""
            application.save()
            notifications.application_received(request, application)
            messages.success(
                request,
                "Thank you for applying. We'll be in touch about the next steps.",
            )
            return redirect(
                vacancy.get_absolute_url() if vacancy else reverse("apply")
            )
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = ApplicationForm()

    return render(request, template, {"vacancy": vacancy, "form": form, **extra})

def get_client_ip(request):
    """
    Get the real client IP when the site is behind Cloudflare.

    CF-Connecting-IP is supplied by Cloudflare and is preferred over
    X-Forwarded-For.
    """

    cloudflare_ip = request.META.get("HTTP_CF_CONNECTING_IP")

    if cloudflare_ip:
        return cloudflare_ip.strip()

    # Fallback for local development / direct requests.
    return request.META.get("REMOTE_ADDR", "").strip()

def get_rate_limit_key(prefix, value):
    """
    Generate a consistent cache key.
    """
    return f"contact:{prefix}:{value}"

import logging

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render

from .forms import ContactForm
from .models import Enquiry
from . import notifications


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Contact form rate limits
# -------------------------------------------------------------------

CONTACT_IP_LIMIT = 3
CONTACT_IP_TIMEOUT = 60 * 10       # 10 minutes

CONTACT_EMAIL_LIMIT = 3
CONTACT_EMAIL_TIMEOUT = 60 * 60    # 1 hour


def get_client_ip(request):
    """
    Get the real client IP when the site is behind Cloudflare.

    CF-Connecting-IP is supplied by Cloudflare and is preferred over
    X-Forwarded-For.
    """

    cloudflare_ip = request.META.get("HTTP_CF_CONNECTING_IP")

    if cloudflare_ip:
        return cloudflare_ip.strip()

    # Fallback for local development / direct requests.
    return request.META.get("REMOTE_ADDR", "").strip()


def get_rate_limit_key(prefix, value):
    """
    Generate a consistent cache key.
    """
    return f"contact:{prefix}:{value}"


def contact(request):
    if request.method == "POST":

        # -----------------------------------------------------------
        # 1. Identify client
        # -----------------------------------------------------------

        client_ip = get_client_ip(request)

        if not client_ip:
            client_ip = "unknown"

        # -----------------------------------------------------------
        # 2. IP rate limit
        #
        # Maximum 3 valid submissions from the same IP
        # within 10 minutes.
        # -----------------------------------------------------------

        ip_key = get_rate_limit_key("ip", client_ip)

        ip_count = cache.get(ip_key, 0)

        if ip_count >= CONTACT_IP_LIMIT:
            logger.warning(
                "Contact form IP rate limit exceeded: ip=%s",
                client_ip,
            )

            messages.error(
                request,
                "Too many submissions. Please try again later.",
            )

            return redirect("contact")

        # -----------------------------------------------------------
        # 3. Validate form
        # -----------------------------------------------------------

        form = ContactForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data["email"].strip().lower()

            # -------------------------------------------------------
            # 4. Email rate limit
            #
            # Maximum 3 submissions from the same email
            # within 1 hour.
            # -------------------------------------------------------

            email_key = get_rate_limit_key("email", email)

            email_count = cache.get(email_key, 0)

            if email_count >= CONTACT_EMAIL_LIMIT:
                logger.warning(
                    "Contact form email rate limit exceeded: "
                    "email=%s ip=%s",
                    email,
                    client_ip,
                )

                messages.error(
                    request,
                    "Too many submissions. Please try again later.",
                )

                return redirect("contact")

            # -------------------------------------------------------
            # 5. Count this submission
            #
            # Do this BEFORE spam handling so that someone who keeps
            # triggering the honeypot cannot continuously hit the
            # endpoint.
            # -------------------------------------------------------

            cache.set(
                ip_key,
                ip_count + 1,
                CONTACT_IP_TIMEOUT,
            )

            cache.set(
                email_key,
                email_count + 1,
                CONTACT_EMAIL_TIMEOUT,
            )

            # -------------------------------------------------------
            # 6. Spam / honeypot check
            # -------------------------------------------------------

            spam = form.is_probably_spam()

            if spam:
                logger.warning(
                    "Contact form spam blocked: ip=%s email=%s",
                    client_ip,
                    email,
                )

                # IMPORTANT:
                # Do NOT create an Enquiry record.
                # Do NOT send SES email.
                #
                # We still show the attacker a normal success message
                # so they don't know that the honeypot detected them.

                messages.success(
                    request,
                    "Thank you for getting in touch. "
                    "We'll respond within one business day.",
                )

                return redirect("contact")

            # -------------------------------------------------------
            # 7. Legitimate enquiry
            # -------------------------------------------------------

            enquiry = Enquiry.objects.create(
                name=form.cleaned_data["name"],
                email=email,
                phone=form.cleaned_data["phone"],
                message=form.cleaned_data["message"],
                status=Enquiry.Status.NEW,
            )

            # -------------------------------------------------------
            # 8. Send notification through SES
            # -------------------------------------------------------

            notifications.enquiry_received(
                request,
                enquiry,
            )

            # -------------------------------------------------------
            # 9. Success
            # -------------------------------------------------------

            messages.success(
                request,
                "Thank you for getting in touch. "
                "We'll respond within one business day.",
            )

            return redirect("contact")

        # -----------------------------------------------------------
        # Invalid form
        # -----------------------------------------------------------

        messages.error(
            request,
            "Please check the highlighted fields and try again.",
        )

    else:
        # -----------------------------------------------------------
        # GET request
        # -----------------------------------------------------------

        initial = {}

        role = request.GET.get("role")

        if role:
            initial["message"] = (
                f"I would like to apply for the {role} position."
            )

        form = ContactForm(initial=initial)

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
        form = ConsultationForm(request.POST)
        if form.is_valid():
            booking = form.save()
            consultation_mail.acknowledge(booking)
            notifications.consultation_requested(request, booking)
            request.session["consultation_reference"] = booking.reference
            return redirect("consultation_booked")
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = ConsultationForm(initial=_consultation_initial(request))

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


