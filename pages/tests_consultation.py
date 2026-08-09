"""The free consultation the site advertises everywhere.

The rules under test come from promises the site already makes to visitors:
office hours are Mon-Fri, a response comes "within one business day", and home
visits are only offered around Toowoomba.
"""

from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .consultation_models import next_business_day
from .models import Consultation, Service


def booking_payload(**overrides):
    return {
        "full_name": "Dana Whitfield",
        "email": "dana@example.com",
        "phone": "0470 111 222",
        "enquirer_type": Consultation.Enquirer.SELF,
        "participant_name": "",
        "plan_status": Consultation.PlanStatus.APPROVED_PLAN,
        "services": [],
        "goals": "I have just had my plan approved.",
        "delivery": Consultation.Delivery.PHONE,
        "suburb": "",
        "postcode": "",
        "preferred_date": next_business_day().isoformat(),
        "preferred_window": "morning",
        "alternate_date": "",
        "alternate_window": "",
        **overrides,
    }


class NextBusinessDayTests(TestCase):
    def test_skips_the_weekend(self):
        from datetime import date

        friday = date(2026, 8, 7)
        self.assertEqual(friday.weekday(), 4)
        # Friday -> Monday, not Saturday.
        self.assertEqual(next_business_day(friday), date(2026, 8, 10))

    def test_midweek_moves_one_day(self):
        from datetime import date

        self.assertEqual(next_business_day(date(2026, 8, 5)), date(2026, 8, 6))


class BookingPageTests(TestCase):
    def test_page_renders(self):
        response = self.client.get(reverse("consultation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book a Free Consultation")

    def test_service_can_be_preselected_from_its_page(self):
        service = Service.objects.get(slug="personal-care")
        response = self.client.get(reverse("consultation"), {"service": service.slug})
        self.assertEqual(response.context["form"].initial["services"], [service.pk])

    def test_unknown_service_is_ignored(self):
        response = self.client.get(reverse("consultation"), {"service": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("services", response.context["form"].initial)

    def test_every_book_a_consultation_cta_leads_here(self):
        """The site's primary CTA used to dump people on the contact form."""
        booking_url = reverse("consultation")
        for name in ("home", "services", "ndis_support", "about"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                body = response.content.decode()
                self.assertIn("Book a Free Consultation", body)
                self.assertIn(f'href="{booking_url}"', body)

    def test_contact_us_ctas_still_go_to_contact(self):
        for name in ("faq", "privacy_policy", "terms"):
            with self.subTest(page=name):
                body = self.client.get(reverse(name)).content.decode()
                self.assertIn('cta-band', body)
                self.assertIn('href="/contact/"', body)


class BookingSubmissionTests(TestCase):
    def test_successful_booking(self):
        response = self.client.post(reverse("consultation"), booking_payload())
        self.assertRedirects(response, reverse("consultation_booked"))

        booking = Consultation.objects.get(email="dana@example.com")
        self.assertEqual(booking.status, Consultation.Status.REQUESTED)
        self.assertTrue(booking.reference.startswith("RW-"))

    def test_reference_is_shown_once_then_cleared(self):
        self.client.post(reverse("consultation"), booking_payload())
        booking = Consultation.objects.get(email="dana@example.com")

        first = self.client.get(reverse("consultation_booked"))
        self.assertContains(first, booking.reference)

        # Refreshing must not re-show a stale confirmation.
        second = self.client.get(reverse("consultation_booked"))
        self.assertRedirects(second, reverse("consultation"))

    def test_confirmation_page_needs_a_booking(self):
        response = self.client.get(reverse("consultation_booked"))
        self.assertRedirects(response, reverse("consultation"))

    def test_both_emails_are_sent(self):
        self.client.post(reverse("consultation"), booking_payload())
        self.assertEqual(len(mail.outbox), 2)

        to_person, to_office = mail.outbox
        booking = Consultation.objects.get(email="dana@example.com")

        self.assertEqual(to_person.to, ["dana@example.com"])
        self.assertIn(booking.reference, to_person.subject)
        self.assertIn("one business day", to_person.body)

        self.assertIn("Consultation request", to_office.subject)
        self.assertEqual(to_office.reply_to, ["dana@example.com"])

    def test_services_are_recorded(self):
        service = Service.objects.get(slug="personal-care")
        self.client.post(
            reverse("consultation"), booking_payload(services=[service.pk])
        )
        booking = Consultation.objects.get(email="dana@example.com")
        self.assertEqual(list(booking.services.all()), [service])

    # ------------------------------------------------------- business rules

    def test_weekend_dates_are_rejected(self):
        saturday = next_business_day()
        while saturday.weekday() != 5:
            saturday += timedelta(days=1)

        response = self.client.post(
            reverse("consultation"),
            booking_payload(preferred_date=saturday.isoformat()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Consultation.objects.count(), 0)
        self.assertIn(
            "Monday to Friday", str(response.context["form"].errors["preferred_date"])
        )

    def test_today_is_rejected_because_of_the_one_business_day_promise(self):
        response = self.client.post(
            reverse("consultation"),
            booking_payload(preferred_date=timezone.localdate().isoformat()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Consultation.objects.count(), 0)

    def test_past_dates_are_rejected(self):
        response = self.client.post(
            reverse("consultation"),
            booking_payload(
                preferred_date=(timezone.localdate() - timedelta(days=3)).isoformat()
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Consultation.objects.count(), 0)

    def test_home_visit_requires_a_suburb(self):
        """Home visits are only offered around Toowoomba, so the office needs
        to know where before it can agree."""
        response = self.client.post(
            reverse("consultation"),
            booking_payload(delivery=Consultation.Delivery.HOME, suburb=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("suburb", response.context["form"].errors)
        self.assertEqual(Consultation.objects.count(), 0)

    def test_home_visit_with_a_suburb_is_accepted(self):
        response = self.client.post(
            reverse("consultation"),
            booking_payload(
                delivery=Consultation.Delivery.HOME,
                suburb="Highfields",
                postcode="4352",
            ),
        )
        self.assertRedirects(response, reverse("consultation_booked"))
        booking = Consultation.objects.get(email="dana@example.com")
        self.assertTrue(booking.is_home_visit)
        self.assertEqual(booking.location_line, "Home visit - Highfields 4352")

    def test_booking_for_someone_else_needs_their_name(self):
        response = self.client.post(
            reverse("consultation"),
            booking_payload(enquirer_type=Consultation.Enquirer.FAMILY),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("participant_name", response.context["form"].errors)

    def test_booking_for_someone_else_records_who(self):
        self.client.post(
            reverse("consultation"),
            booking_payload(
                enquirer_type=Consultation.Enquirer.COORDINATOR,
                participant_name="Alex Chen",
            ),
        )
        booking = Consultation.objects.get(email="dana@example.com")
        self.assertEqual(booking.for_whom, "Alex Chen")

    def test_alternate_cannot_duplicate_the_first_preference(self):
        day = next_business_day().isoformat()
        response = self.client.post(
            reverse("consultation"),
            booking_payload(
                preferred_date=day,
                preferred_window="morning",
                alternate_date=day,
                alternate_window="morning",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("alternate_date", response.context["form"].errors)


class ConsultationModelTests(TestCase):
    def make(self, **kwargs):
        defaults = {
            "full_name": "Dana Whitfield",
            "email": "dana@example.com",
            "phone": "0470 111 222",
            "preferred_date": next_business_day(),
        }
        return Consultation.objects.create(**{**defaults, **kwargs})

    def test_reference_is_unique_and_readable(self):
        first, second = self.make(), self.make(email="other@example.com")
        self.assertNotEqual(first.reference, second.reference)
        self.assertRegex(first.reference, r"^RW-\d{2}-\d{4}$")

    def test_overdue_only_applies_to_unanswered_requests(self):
        booking = self.make()
        self.assertFalse(booking.is_overdue)

        old = timezone.now() - timedelta(days=6)
        Consultation.objects.filter(pk=booking.pk).update(created_at=old)
        booking.refresh_from_db()
        self.assertTrue(booking.is_overdue)

        booking.status = Consultation.Status.CONFIRMED
        booking.save()
        self.assertFalse(booking.is_overdue)

    def test_upcoming_only_returns_future_confirmed(self):
        past = self.make(
            status=Consultation.Status.CONFIRMED,
            scheduled_for=timezone.now() - timedelta(days=1),
        )
        future = self.make(
            email="future@example.com",
            status=Consultation.Status.CONFIRMED,
            scheduled_for=timezone.now() + timedelta(days=1),
        )
        unconfirmed = self.make(email="pending@example.com")

        upcoming = list(Consultation.objects.upcoming())
        self.assertIn(future, upcoming)
        self.assertNotIn(past, upcoming)
        self.assertNotIn(unconfirmed, upcoming)

    def test_preference_line_includes_the_alternative(self):
        booking = self.make(
            preferred_window="morning",
            alternate_date=next_business_day(next_business_day()),
            alternate_window="afternoon",
        )
        self.assertIn("or", booking.preference_line)
