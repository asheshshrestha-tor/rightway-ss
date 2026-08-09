"""Notifications to staff, and confirmations to the person who submitted.

Who gets notified is derived from dashboard permissions rather than a list in
settings, so most of these tests are about that: give someone the permission
and they start receiving, take it away and they stop.
"""

import re
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import notifications
from .models import Consultation, Enquiry, SiteSettings, Vacancy

CONTACT = {
    "name": "Dana Whitfield",
    "email": "dana@example.com",
    "phone": "0470 111 222",
    "message": "I would like to know more about your personal care support.",
    "hp_reference": "",
}


def make_staff(username, email, *permissions):
    user = User.objects.create_user(username, email=email, password="pw-for-tests-1234")
    user.is_staff = True
    user.save()
    for name in permissions:
        app_label, codename = name.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    return user


def notification(subject_starts):
    return next(m for m in mail.outbox if m.subject.startswith(subject_starts))


def html_part(message):
    for content, mimetype in message.alternatives:
        if mimetype == "text/html":
            return content
    raise AssertionError("no HTML alternative")


def button_href(message):
    match = re.search(r'<a href="(https?://[^"]+)"', html_part(message))
    return match.group(1) if match else None


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())
class RecipientTests(TestCase):
    """Staff are notified about what they are allowed to open."""

    def test_a_user_with_the_permission_is_notified(self):
        make_staff("handler", "handler@example.com", "pages.view_enquiry")

        self.client.post(reverse("contact"), CONTACT)

        self.assertIn("handler@example.com", notification("New enquiry").to)

    def test_a_user_without_it_is_not(self):
        """The button would only turn them away, so there is nothing to tell."""
        make_staff("recruiter", "recruiter@example.com", "pages.view_application")

        self.client.post(reverse("contact"), CONTACT)

        self.assertNotIn("recruiter@example.com", notification("New enquiry").to)

    def test_superusers_are_always_included(self):
        User.objects.create_superuser("boss", "boss@example.com", "pw-for-tests-1234")

        self.client.post(reverse("contact"), CONTACT)

        self.assertIn("boss@example.com", notification("New enquiry").to)

    def test_a_deactivated_account_stops_receiving(self):
        user = make_staff("gone", "gone@example.com", "pages.view_enquiry")
        user.is_active = False
        user.save()

        self.client.post(reverse("contact"), CONTACT)

        self.assertNotIn("gone@example.com", notification("New enquiry").to)

    def test_a_staff_account_with_no_email_is_skipped(self):
        """There is nowhere to send, and an empty string would be an invalid
        recipient that fails the whole message."""
        make_staff("blank", "", "pages.view_enquiry")

        self.client.post(reverse("contact"), CONTACT)

        self.assertNotIn("", notification("New enquiry").to)

    def test_the_office_address_is_always_included(self):
        self.client.post(reverse("contact"), CONTACT)

        self.assertIn(SiteSettings.load().email, notification("New enquiry").to)

    def test_an_address_is_never_listed_twice(self):
        """A staff account using the office address must not be sent two."""
        office = SiteSettings.load().email
        make_staff("dup", office.upper(), "pages.view_enquiry")

        self.client.post(reverse("contact"), CONTACT)

        recipients = notification("New enquiry").to
        self.assertEqual(len(recipients), len(set(a.lower() for a in recipients)))

    @override_settings(ADMIN_NOTIFICATION_EMAILS=["watcher@example.com"])
    def test_extra_addresses_can_be_added_without_a_staff_account(self):
        self.client.post(reverse("contact"), CONTACT)

        self.assertIn("watcher@example.com", notification("New enquiry").to)

    def test_applications_go_to_recruiters_not_enquiry_handlers(self):
        make_staff("handler", "handler@example.com", "pages.view_enquiry")
        make_staff("recruiter", "recruiter@example.com", "pages.view_application")

        from django.core.files.uploadedfile import SimpleUploadedFile

        vacancy = Vacancy.objects.published().first()
        self.client.post(
            vacancy.get_absolute_url(),
            {
                "full_name": "Dana Whitfield",
                "email": "dana@example.com",
                "phone": "0470 111 222",
                "cover_letter": "Five years of disability support experience.",
                "resume": SimpleUploadedFile("d.pdf", b"pdf", content_type="application/pdf"),
            },
        )

        recipients = notification("Job application").to
        self.assertIn("recruiter@example.com", recipients)
        self.assertNotIn("handler@example.com", recipients)


class NotificationContentTests(TestCase):
    def test_the_button_links_to_the_record(self):
        self.client.post(reverse("contact"), CONTACT)
        enquiry = Enquiry.objects.get(email="dana@example.com")

        expected = reverse("dashboard:enquiry_detail", args=[enquiry.pk])
        self.assertEqual(
            button_href(notification("New enquiry")), f"http://testserver{expected}"
        )

    def test_replies_reach_the_person_who_wrote_in(self):
        self.client.post(reverse("contact"), CONTACT)
        self.assertEqual(notification("New enquiry").reply_to, ["dana@example.com"])

    def test_a_plain_text_alternative_is_always_included(self):
        """Some clients refuse to render HTML, and the link must survive."""
        self.client.post(reverse("contact"), CONTACT)
        body = notification("New enquiry").body

        self.assertIn("Dana Whitfield", body)
        self.assertIn("/dashboard/enquiries/", body)

    def test_suspected_spam_is_not_relayed(self):
        """A tripped honeypot is quarantined for review, not forwarded - and
        the sender is not told they were flagged."""
        self.client.post(reverse("contact"), {**CONTACT, "hp_reference": "bot"})

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Enquiry.objects.filter(status=Enquiry.Status.SPAM).count(), 1)


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())
class ConfirmationTests(TestCase):
    def test_an_enquiry_is_acknowledged(self):
        self.client.post(reverse("contact"), CONTACT)

        confirmation = next(m for m in mail.outbox if m.to == ["dana@example.com"])
        self.assertIn("received your message", confirmation.subject)
        self.assertIn("Dana Whitfield", confirmation.body)
        self.assertIn("one business day", confirmation.body)

    def test_a_confirmation_carries_no_dashboard_link(self):
        """It goes to a member of the public. A staff URL in it is at best
        confusing and at worst an invitation."""
        self.client.post(reverse("contact"), CONTACT)

        confirmation = next(m for m in mail.outbox if m.to == ["dana@example.com"])
        self.assertNotIn("/dashboard/", confirmation.body)
        self.assertNotIn("/dashboard/", html_part(confirmation))

    def test_an_applicant_is_told_the_resume_arrived(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        vacancy = Vacancy.objects.published().first()
        self.client.post(
            vacancy.get_absolute_url(),
            {
                "full_name": "Dana Whitfield",
                "email": "dana@example.com",
                "phone": "0470 111 222",
                "cover_letter": "Five years of disability support experience.",
                "resume": SimpleUploadedFile("d.pdf", b"pdf", content_type="application/pdf"),
            },
        )

        confirmation = next(m for m in mail.outbox if m.to == ["dana@example.com"])
        self.assertIn("Support Worker", confirmation.subject)
        self.assertIn("resume", confirmation.body.lower())

    def test_a_consultation_request_is_acknowledged_with_its_reference(self):
        self.client.post(
            reverse("consultation"),
            {
                "full_name": "Dana Whitfield",
                "email": "dana@example.com",
                "phone": "0470 111 222",
                "enquirer_type": Consultation.Enquirer.SELF,
                "plan_status": Consultation.PlanStatus.UNSURE,
                "delivery": Consultation.Delivery.PHONE,
                "preferred_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "preferred_window": "morning",
                "goals": "Help getting out into the community more often.",
            },
        )

        booking = Consultation.objects.get(email="dana@example.com")
        confirmation = next(m for m in mail.outbox if m.to == ["dana@example.com"])
        self.assertIn(booking.reference, confirmation.body)


@override_settings(
    EMAIL_REDIRECT_TO=["tester@example.com"],
    EMAIL_REDIRECT_WRAPPED_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_BACKEND="config.email_backend.RedirectingEmailBackend",
)
class RedirectBackendTests(TestCase):
    """The safety net for testing on a live-ish site."""

    def test_everything_goes_to_the_test_address(self):
        make_staff("handler", "handler@example.com", "pages.view_enquiry")

        self.client.post(reverse("contact"), CONTACT)

        for message in mail.outbox:
            self.assertEqual(message.to, ["tester@example.com"])

    def test_the_real_recipients_are_still_visible(self):
        """The point is to check the addressing without anyone being emailed,
        so who it would have gone to has to survive."""
        make_staff("handler", "handler@example.com", "pages.view_enquiry")

        self.client.post(reverse("contact"), CONTACT)
        subjects = " ".join(m.subject for m in mail.outbox)
        bodies = " ".join(m.body for m in mail.outbox)

        self.assertIn("handler@example.com", subjects)
        self.assertIn("handler@example.com", bodies)
        self.assertIn("TEST ->", subjects)

    def test_a_redirected_email_is_obviously_a_test(self):
        """Without a banner it looks exactly like the real thing."""
        self.client.post(reverse("contact"), CONTACT)

        html = html_part(mail.outbox[0])
        self.assertIn("Redirected test email", html)

    def test_the_confirmation_is_redirected_too(self):
        """Otherwise the address typed into the form still receives mail, which
        is the case that reaches a stranger."""
        self.client.post(reverse("contact"), CONTACT)

        self.assertNotIn(
            ["dana@example.com"], [m.to for m in mail.outbox]
        )


class SendFailureTests(TestCase):
    def test_a_mail_outage_does_not_lose_the_submission(self):
        """The enquiry is saved before the email is attempted, so a broken mail
        server must not turn it into a 500 for the sender."""
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=1,  # nothing is listening
        ):
            response = self.client.post(reverse("contact"), CONTACT)

        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(Enquiry.objects.filter(email="dana@example.com").count(), 1)

    def test_it_reports_failure_rather_than_raising(self):
        enquiry = Enquiry.objects.create(
            name="Dana", email="dana@example.com", message="Hello there."
        )
        request = self.client.request().wsgi_request

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=1,
        ):
            with self.assertLogs("pages.notifications", level="ERROR"):
                sent = notifications.enquiry_received(request, enquiry)

        self.assertFalse(sent)
