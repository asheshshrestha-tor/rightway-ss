"""Emails for the consultation flow.

Two moments matter to the participant: the request landing, and the time
being confirmed. Telling the office is handled by `pages.notifications`, which
sends the same shape of message for every form on the site.

Failures are logged rather than raised - a mail outage must not lose a booking
that is already in the database.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from .models import SiteSettings

logger = logging.getLogger(__name__)


def office_email():
    """Where enquiries go. Editable in the dashboard, with settings.py as the
    fallback if it has been cleared."""
    return SiteSettings.load().email or settings.CONTACT_EMAIL


def office_phone():
    return SiteSettings.load().phone or settings.CONSULTATION_PHONE


def _send(subject, body, to, reply_to=None):
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or [office_email()],
    )
    try:
        message.send(fail_silently=False)
        return True
    except Exception:  # pragma: no cover - depends on mail server availability
        logger.exception("Consultation email could not be sent:\n%s", body)
        return False


def acknowledge(consultation):
    """Reassure the person who asked, and give them their reference."""
    body = "\n".join(
        [
            f"Hi {consultation.full_name},",
            "",
            "Thank you for asking for a free consultation with Rightway Support",
            "Services. We will call you within one business day to confirm a time.",
            "",
            f"Your reference: {consultation.reference}",
            "",
            f"You asked for: {consultation.preference_line}",
            f"Where: {consultation.location_line}",
            "",
            "There is nothing to prepare, and no obligation. If you would rather",
            f"talk sooner, call us on {office_phone()}.",
            "",
            "Rightway Support Services",
        ]
    )
    return _send(
        f"We've received your consultation request ({consultation.reference})",
        body,
        [consultation.email],
    )


def confirm(consultation):
    """Sent when staff pin down the actual time."""
    when = consultation.scheduled_for
    body = "\n".join(
        [
            f"Hi {consultation.full_name},",
            "",
            "Your free consultation with Rightway Support Services is confirmed.",
            "",
            f"When:  {when:%A %d %B %Y} at {when:%I:%M %p}".replace(" 0", " "),
            f"Where: {consultation.location_line}",
            f"Reference: {consultation.reference}",
            "",
            "We will talk through your goals and your NDIS plan, and answer any",
            "questions. There is no obligation to go ahead with anything.",
            "",
            f"Need to change the time? Call us on {office_phone()}.",
            "",
            "Rightway Support Services",
        ]
    )
    return _send(
        f"Your consultation is confirmed - {when:%A %d %B}",
        body,
        [consultation.email],
    )
