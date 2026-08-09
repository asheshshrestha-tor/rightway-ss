from django.core import mail
from django.test import TestCase
from django.urls import reverse

PAGE_NAMES = [
    "home",
    "about",
    "services",
    "ndis_support",
    "careers",
    "contact",
    "faq",
    "privacy_policy",
    "terms",
]


class PageTests(TestCase):
    def test_every_page_renders(self):
        for name in PAGE_NAMES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_shared_chrome_is_present(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Rightway Support Services")
        self.assertContains(response, "0470 522 587")
        self.assertContains(response, reverse("privacy_policy"))
        self.assertContains(response, reverse("terms"))

    def test_home_lists_every_service(self):
        response = self.client.get(reverse("home"))
        for title in (
            "Personal Care",
            "Household Tasks",
            "Community Access",
            "Home &amp; Shared Living",
        ):
            self.assertContains(response, title)

    def test_faq_page_lists_questions(self):
        response = self.client.get(reverse("faq"))
        self.assertContains(response, "What is NDIS?")
        self.assertContains(response, 'class="faq-question"', count=8)

    def test_careers_apply_link_prefills_contact_form(self):
        response = self.client.get(reverse("contact"), {"role": "Support Worker"})
        self.assertContains(response, "apply for the Support Worker position")


class ContactFormTests(TestCase):
    payload = {
        "name": "Jamie Reid",
        "email": "jamie@example.com",
        "phone": "0400 000 000",
        "message": "I would like to book a free consultation.",
        "hp_reference": "",
    }

    def test_valid_submission_emails_and_redirects(self):
        """Two emails: staff are notified, and the sender is told it arrived."""
        response = self.client.post(reverse("contact"), self.payload)
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(len(mail.outbox), 2)

        notification = next(m for m in mail.outbox if "Jamie Reid" in m.subject)
        self.assertIn("Jamie Reid", notification.body)
        self.assertEqual(notification.reply_to, ["jamie@example.com"])

        confirmation = next(m for m in mail.outbox if m.to == ["jamie@example.com"])
        self.assertIn("received your message", confirmation.subject)

    def test_invalid_submission_redisplays_errors(self):
        response = self.client.post(reverse("contact"), {**self.payload, "email": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Enter a valid email address.")
        self.assertEqual(len(mail.outbox), 0)

    def test_short_message_is_rejected(self):
        response = self.client.post(reverse("contact"), {**self.payload, "message": "hi"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_quarantines_instead_of_rejecting(self):
        """A filled honeypot must not dead-end the sender.

        Regression: the trap used to raise a ValidationError on a field the
        template never renders, so the user saw "check the highlighted fields"
        with nothing highlighted and no way to recover.
        """
        from pages.models import Enquiry

        response = self.client.post(
            reverse("contact"), {**self.payload, "hp_reference": "http://spam.example"}
        )
        # Sender sees an ordinary success, not an unexplained rejection.
        self.assertRedirects(response, reverse("contact"))
        # ...but nothing is relayed by email...
        self.assertEqual(len(mail.outbox), 0)
        # ...and the message is kept for staff to review rather than dropped.
        self.assertEqual(
            Enquiry.objects.get(email=self.payload["email"]).status,
            Enquiry.Status.SPAM,
        )

    def test_honeypot_field_is_not_rendered_in_the_visible_form(self):
        response = self.client.get(reverse("contact"))
        # It appears once, inside the off-screen honeypot wrapper only.
        self.assertContains(response, 'id="id_hp_reference"', count=1)

    def test_honeypot_name_avoids_browser_autofill_tokens(self):
        """The field name must not be something browsers autofill.

        "website"/"url"/"company" are standard autofill tokens; Chrome fills
        them even off-screen with autocomplete="off".
        """
        from pages.forms import HONEYPOT_FIELD

        self.assertNotIn(
            HONEYPOT_FIELD,
            {"website", "url", "company", "organization", "address", "name"},
        )

    def test_every_validation_error_is_visible_to_the_sender(self):
        """Any field that can raise an error must be rendered by the template.

        Guards the shape of the original bug: a rejection the user cannot see.
        """
        from pages.forms import HONEYPOT_FIELD, ContactForm

        response = self.client.get(reverse("contact"))
        rendered = response.content.decode()
        for name in ContactForm().fields:
            if name == HONEYPOT_FIELD:
                continue
            with self.subTest(field=name):
                self.assertIn(f'id="id_{name}"', rendered)
