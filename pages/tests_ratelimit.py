"""Daily submission limits on the three public forms.

Three accepted submissions per day, per IP address and per email address,
counted separately for each form.

The cache is cleared between tests: it is a real table shared by the whole run,
so without that a counter left behind by one test silently blocks another.
"""

import tempfile

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import ratelimit
from .models import Consultation, Enquiry
from .tests_consultation import booking_payload

CONTACT = {
    "name": "Jamie Reid",
    "email": "jamie@example.com",
    "phone": "0400 000 000",
    "message": "I would like to book a free consultation.",
    "hp_reference": "",
}


class RateLimitUnitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_allows_three_then_blocks(self):
        for _ in range(ratelimit.SUBMISSION_LIMIT):
            self.assertFalse(ratelimit.is_over_limit(ratelimit.CONTACT, ip="203.0.113.7"))
            ratelimit.record(ratelimit.CONTACT, ip="203.0.113.7")

        self.assertTrue(ratelimit.is_over_limit(ratelimit.CONTACT, ip="203.0.113.7"))

    def test_the_window_is_one_day(self):
        self.assertEqual(ratelimit.SUBMISSION_WINDOW, 60 * 60 * 24)
        self.assertEqual(ratelimit.SUBMISSION_LIMIT, 3)

    def test_ip_and_email_are_counted_separately(self):
        """Filling the email bucket must not block everyone on that network,
        and vice versa."""
        for _ in range(3):
            ratelimit.record(ratelimit.CONTACT, email="jamie@example.com")

        self.assertTrue(ratelimit.is_over_limit(ratelimit.CONTACT, email="jamie@example.com"))
        self.assertFalse(ratelimit.is_over_limit(ratelimit.CONTACT, ip="203.0.113.7"))

    def test_each_form_has_its_own_quota(self):
        """Applying for three advertised roles must not use up the allowance
        for asking a question about a fourth."""
        for _ in range(3):
            ratelimit.record(ratelimit.APPLICATION, ip="203.0.113.7", email="jamie@example.com")

        self.assertTrue(ratelimit.is_over_limit(ratelimit.APPLICATION, ip="203.0.113.7"))
        self.assertFalse(ratelimit.is_over_limit(ratelimit.CONTACT, ip="203.0.113.7"))
        self.assertFalse(ratelimit.is_over_limit(ratelimit.CONSULTATION, ip="203.0.113.7"))

    def test_the_email_address_is_not_stored_in_the_cache_key(self):
        """These keys live in the django_cache table. An enquirer's address
        sitting there is personal information kept in a second place, outside
        the model that has a retention story."""
        key = ratelimit._key(ratelimit.CONTACT, "email", "jamie@example.com")
        self.assertNotIn("jamie", key)
        self.assertNotIn("example.com", key)

    def test_case_and_whitespace_do_not_buy_a_fresh_quota(self):
        for _ in range(3):
            ratelimit.record(ratelimit.CONTACT, email="jamie@example.com")

        self.assertTrue(
            ratelimit.is_over_limit(ratelimit.CONTACT, email="  JAMIE@Example.COM ")
        )


class ContactLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_fourth_message_in_a_day_is_turned_away(self):
        for index in range(3):
            response = self.client.post(
                reverse("contact"), {**CONTACT, "message": "Message number %d please." % index}
            )
            self.assertRedirects(response, reverse("contact"))

        self.assertEqual(Enquiry.objects.count(), 3)

        mail.outbox.clear()
        response = self.client.post(reverse("contact"), CONTACT)

        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(Enquiry.objects.count(), 3)
        self.assertEqual(len(mail.outbox), 0)

    def test_the_refusal_carries_the_phone_number(self):
        """Several people share one address - an office, a group home, a
        mobile network. Anyone caught by the limit needs a way through that
        is not "wait a day"."""
        for _ in range(3):
            self.client.post(reverse("contact"), CONTACT)

        response = self.client.post(reverse("contact"), CONTACT, follow=True)
        self.assertContains(response, "0470 522 587")

    def test_an_invalid_submission_does_not_use_up_the_allowance(self):
        """Someone mistyping their email four times has not had four goes."""
        for _ in range(4):
            self.client.post(reverse("contact"), {**CONTACT, "email": "not-an-email"})

        self.assertEqual(Enquiry.objects.count(), 0)

        response = self.client.post(reverse("contact"), CONTACT)
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(Enquiry.objects.count(), 1)

    def test_spam_uses_up_the_allowance(self):
        """Otherwise tripping the honeypot over and over is a free way to keep
        hitting the endpoint."""
        for _ in range(3):
            self.client.post(reverse("contact"), {**CONTACT, "hp_reference": "bot"})

        self.assertEqual(Enquiry.objects.filter(status=Enquiry.Status.SPAM).count(), 3)

        self.client.post(reverse("contact"), CONTACT)
        self.assertEqual(Enquiry.objects.count(), 3)

    def test_a_different_sender_on_a_different_network_is_unaffected(self):
        for _ in range(3):
            self.client.post(reverse("contact"), CONTACT, HTTP_CF_CONNECTING_IP="203.0.113.7")

        response = self.client.post(
            reverse("contact"),
            {**CONTACT, "email": "alex@example.com"},
            HTTP_CF_CONNECTING_IP="198.51.100.4",
        )
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(Enquiry.objects.filter(email="alex@example.com").count(), 1)

    def test_the_same_sender_from_a_new_network_is_still_limited(self):
        """The email bucket is what stops someone simply changing address."""
        for _ in range(3):
            self.client.post(reverse("contact"), CONTACT, HTTP_CF_CONNECTING_IP="203.0.113.7")

        self.client.post(reverse("contact"), CONTACT, HTTP_CF_CONNECTING_IP="198.51.100.4")
        self.assertEqual(Enquiry.objects.count(), 3)


class ConsultationLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_fourth_request_in_a_day_is_turned_away(self):
        for _ in range(3):
            self.client.post(reverse("consultation"), booking_payload())

        self.assertEqual(Consultation.objects.count(), 3)

        response = self.client.post(reverse("consultation"), booking_payload())
        self.assertRedirects(response, reverse("consultation"))
        self.assertEqual(Consultation.objects.count(), 3)

    def test_a_consultation_does_not_spend_the_contact_allowance(self):
        for _ in range(3):
            self.client.post(reverse("consultation"), booking_payload())

        response = self.client.post(reverse("contact"), CONTACT)
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(Enquiry.objects.count(), 1)


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())
class ApplicationLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def payload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return {
            "full_name": "Jamie Reid",
            "email": "jamie@example.com",
            "phone": "0400 000 000",
            "cover_letter": "I would like to join the team.",
            "resume": SimpleUploadedFile("cv.pdf", b"%PDF-1.4 resume", "application/pdf"),
        }

    def test_the_fourth_application_in_a_day_is_turned_away(self):
        from .models import Application

        for _ in range(3):
            self.client.post(reverse("apply"), self.payload())

        self.assertEqual(Application.objects.count(), 3)

        response = self.client.post(reverse("apply"), self.payload())
        self.assertRedirects(response, reverse("apply"))
        self.assertEqual(Application.objects.count(), 3)
