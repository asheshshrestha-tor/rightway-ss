"""Email for anything the public submits.

Every submission produces two messages:

  * a notification to the staff who can act on it, with a button through to the
    record in the dashboard;
  * a confirmation to the person who submitted it, so they know it arrived.

Who counts as staff is not a list in a settings file - it is worked out from
the same permissions that guard the dashboard. Someone who cannot open an
application is not told about one, because the button would only turn them
away. Add a user to the Enquiry Handler group and they start receiving
enquiries; remove them and they stop.

Failures are logged, never raised. The submission is already in the database by
the time these run, and a mail outage must not turn a saved enquiry into a
500 page for the person who sent it.
"""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .models import SiteSettings

logger = logging.getLogger(__name__)


def office_email():
    """Where the business reads its mail. Editable in the dashboard."""
    return SiteSettings.load().email or settings.CONTACT_EMAIL


def office_phone():
    return SiteSettings.load().phone or settings.CONSULTATION_PHONE


def staff_emails(permission):
    """Addresses of active staff who hold `permission`, e.g. "pages.view_enquiry".

    Superusers hold every permission and are included automatically. Users with
    no email address on their account are skipped - there is nowhere to send.
    """
    users = User.objects.filter(is_active=True, is_staff=True).exclude(email="")
    return [user.email for user in users if user.has_perm(permission)]


def recipients(permission):
    """Everyone who should hear about a submission of this kind.

    The office inbox, the staff who can action it, and anything in
    ADMIN_NOTIFICATION_EMAILS - which exists so a developer can watch
    submissions during testing without being given a staff account.
    """
    addresses = [
        office_email(),
        *staff_emails(permission),
        *settings.ADMIN_NOTIFICATION_EMAILS,
    ]

    seen, unique = set(), []
    for address in addresses:
        address = (address or "").strip()
        key = address.lower()
        if address and key not in seen:
            seen.add(key)
            unique.append(address)
    return unique


def _send(subject, template, context, to, reply_to=None):
    """Render `template`.txt and `.html`, and send both parts.

    The text part is not a formality: some clients refuse to render HTML, and a
    message nobody can read is worse than none.
    """
    context = {"site": SiteSettings.load(), "phone": office_phone(), **context}

    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string(f"email/{template}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or [office_email()],
    )
    message.attach_alternative(
        render_to_string(f"email/{template}.html", context), "text/html"
    )

    try:
        message.send(fail_silently=False)
        return True
    except Exception:  # pragma: no cover - depends on mail server availability
        logger.exception("Email could not be sent: %s", subject)
        return False


def notify(request, *, permission, subject, heading, summary, rows, url_name, pk, action_label, reply_to):
    """One staff notification. `rows` is [(label, value), ...] in reading order."""
    to = recipients(permission)
    if not to:
        logger.warning("No recipients for %s - notification not sent", subject)
        return False

    return _send(
        subject,
        "notification",
        {
            "heading": heading,
            "summary": summary,
            "rows": [(label, value) for label, value in rows if value not in (None, "")],
            # Absolute, because an email has no page for a relative path to
            # resolve against. `pk` is None only for the test command, which
            # links to a list rather than a record that does not exist.
            "action_url": request.build_absolute_uri(
                reverse(url_name, args=[pk] if pk is not None else [])
            ),
            "action_label": action_label,
        },
        to,
        reply_to=[reply_to],
    )


def confirm(*, to, subject, heading, greeting, paragraphs, rows=()):
    """One confirmation to the person who submitted the form."""
    return _send(
        subject,
        "confirmation",
        {
            "heading": heading,
            "greeting": greeting,
            "paragraphs": paragraphs,
            "rows": [(label, value) for label, value in rows if value not in (None, "")],
        },
        [to],
    )


# --------------------------------------------------------------- contact form


def enquiry_received(request, enquiry):
    notify(
        request,
        permission="pages.view_enquiry",
        subject=f"New enquiry: {enquiry.name}",
        heading="New contact enquiry",
        summary=f"{enquiry.name} sent a message through the contact form.",
        rows=[
            ("Name", enquiry.name),
            ("Email", enquiry.email),
            ("Phone", enquiry.phone),
            ("Message", enquiry.message),
        ],
        url_name="dashboard:enquiry_detail",
        pk=enquiry.pk,
        action_label="Open this enquiry",
        reply_to=enquiry.email,
    )
    return confirm(
        to=enquiry.email,
        subject="We've received your message",
        heading="Thanks for getting in touch",
        greeting=enquiry.name,
        paragraphs=[
            "We have your message and someone will respond within one business day.",
            f"If it is urgent, call us on {office_phone()} instead of waiting for a reply.",
        ],
        rows=[("Your message", enquiry.message)],
    )


# ------------------------------------------------------------ job application


def application_received(request, application):
    """The résumé is deliberately not attached.

    It is personal information: it stays in private storage and is read from
    the dashboard behind a permission check, rather than being copied into an
    inbox and forwarded onwards.
    """
    notify(
        request,
        permission="pages.view_application",
        subject=f"Job application: {application.role_label}",
        heading="New job application",
        summary=f"{application.full_name} applied for {application.role_label}.",
        rows=[
            ("Role", application.role_label),
            ("Name", application.full_name),
            ("Email", application.email),
            ("Phone", application.phone),
            ("Cover letter", application.cover_letter),
            ("Resume", f"{application.resume_name} (open it in the dashboard)"),
        ],
        url_name="dashboard:application_detail",
        pk=application.pk,
        action_label="Open this application",
        reply_to=application.email,
    )
    return confirm(
        to=application.email,
        subject=f"We've received your application for {application.role_label}",
        heading="Thanks for applying",
        greeting=application.full_name,
        paragraphs=[
            f"We have your application for {application.role_label} and your resume "
            "came through safely.",
            "Our team reviews every application. If your experience matches what we "
            "are looking for, we will be in touch to arrange a chat.",
        ],
        rows=[("Role", application.role_label), ("Resume", application.resume_name)],
    )


# --------------------------------------------------------------- consultation


def consultation_requested(request, consultation):
    """The acknowledgement to the participant lives in `consultation_mail`,
    which also owns the later "your time is confirmed" message."""
    return notify(
        request,
        permission="pages.view_consultation",
        subject=f"Consultation request: {consultation.full_name} ({consultation.reference})",
        heading="New consultation request",
        summary=(
            f"{consultation.full_name} asked for a free consultation. "
            "We promise a response within one business day."
        ),
        rows=[
            ("Reference", consultation.reference),
            ("Name", consultation.full_name),
            ("For", f"{consultation.for_whom} ({consultation.get_enquirer_type_display()})"),
            ("Email", consultation.email),
            ("Phone", consultation.phone),
            ("NDIS plan", consultation.get_plan_status_display()),
            ("Preferred time", consultation.preference_line),
            ("Where", consultation.location_line),
            (
                "Interested in",
                ", ".join(s.title for s in consultation.services.all())
                or "not specified",
            ),
            ("Their goals", consultation.goals),
        ],
        url_name="dashboard:consultation_detail",
        pk=consultation.pk,
        action_label="Open this request",
        reply_to=consultation.email,
    )
