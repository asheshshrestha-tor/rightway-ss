"""Confirming consultations from the dashboard."""

from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pages.consultation_models import next_business_day
from pages.models import Consultation

from .tests import fast_passwords, make_user


def make_booking(**overrides):
    defaults = {
        "full_name": "Dana Whitfield",
        "email": "dana@example.com",
        "phone": "0470 111 222",
        "preferred_date": next_business_day(),
        "preferred_window": "morning",
    }
    return Consultation.objects.create(**{**defaults, **overrides})


def confirm_payload(when, **overrides):
    return {
        "status": Consultation.Status.CONFIRMED,
        "scheduled_for": when.strftime("%Y-%m-%dT%H:%M"),
        "assigned_to": "",
        "staff_notes": "",
        "send_confirmation": "on",
        **overrides,
    }


@fast_passwords
class ConsultationAccessTests(TestCase):
    def setUp(self):
        self.booking = make_booking()

    def test_anonymous_is_redirected(self):
        response = self.client.get(reverse("dashboard:consultation_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_staff_without_permission_is_forbidden(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        self.assertEqual(
            self.client.get(reverse("dashboard:consultation_list")).status_code, 403
        )

    def test_view_permission_is_read_only(self):
        make_user("viewer", staff=True, perms=["pages.view_consultation"])
        self.client.login(username="viewer", password="pw-for-tests-1234")

        self.assertEqual(
            self.client.get(reverse("dashboard:consultation_list")).status_code, 200
        )

        response = self.client.post(
            reverse("dashboard:consultation_detail", args=[self.booking.pk]),
            confirm_payload(timezone.now() + timedelta(days=2)),
            follow=True,
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Consultation.Status.REQUESTED)
        self.assertContains(response, "do not have permission")

    def test_menu_entry_follows_permission(self):
        make_user("plain", staff=True)
        self.client.login(username="plain", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        links = [
            link["label"]
            for item in response.context["nav_items"]
            for link in item["links"]
        ]
        self.assertNotIn("Consultations", links)


@fast_passwords
class ConsultationConfirmationTests(TestCase):
    def setUp(self):
        self.staff = make_user("boss", superuser=True)
        self.booking = make_booking()
        self.client.login(username="boss", password="pw-for-tests-1234")
        self.when = timezone.now() + timedelta(days=2)

    def test_confirming_emails_the_participant(self):
        response = self.client.post(
            reverse("dashboard:consultation_detail", args=[self.booking.pk]),
            confirm_payload(self.when, assigned_to=self.staff.pk),
        )
        self.assertRedirects(
            response,
            reverse("dashboard:consultation_detail", args=[self.booking.pk]),
        )

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Consultation.Status.CONFIRMED)
        self.assertIsNotNone(self.booking.scheduled_for)
        self.assertIsNotNone(self.booking.confirmation_sent_at)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["dana@example.com"])
        self.assertIn("confirmed", mail.outbox[0].subject.lower())
        self.assertIn(self.booking.reference, mail.outbox[0].body)

    def test_confirmation_can_be_suppressed(self):
        payload = confirm_payload(self.when)
        payload.pop("send_confirmation")  # unticked checkboxes are absent

        self.client.post(
            reverse("dashboard:consultation_detail", args=[self.booking.pk]), payload
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Consultation.Status.CONFIRMED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(self.booking.confirmation_sent_at)

    def test_participant_is_not_emailed_twice(self):
        """Re-saving an already confirmed booking must not resend."""
        url = reverse("dashboard:consultation_detail", args=[self.booking.pk])
        self.client.post(url, confirm_payload(self.when))
        self.assertEqual(len(mail.outbox), 1)

        self.client.post(url, confirm_payload(self.when, staff_notes="Called again."))
        self.assertEqual(len(mail.outbox), 1)

    def test_cannot_confirm_without_a_time(self):
        response = self.client.post(
            reverse("dashboard:consultation_detail", args=[self.booking.pk]),
            confirm_payload(self.when, scheduled_for=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("scheduled_for", response.context["form"].errors)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Consultation.Status.REQUESTED)
        self.assertEqual(len(mail.outbox), 0)

    def test_time_defaults_to_the_participants_preference(self):
        response = self.client.get(
            reverse("dashboard:consultation_detail", args=[self.booking.pk])
        )
        suggested = response.context["form"].initial["scheduled_for"]
        self.assertTrue(suggested.startswith(self.booking.preferred_date.isoformat()))
        self.assertTrue(suggested.endswith("09:00"))  # morning preference

    def test_afternoon_preference_suggests_an_afternoon_time(self):
        booking = make_booking(email="pm@example.com", preferred_window="afternoon")
        response = self.client.get(
            reverse("dashboard:consultation_detail", args=[booking.pk])
        )
        self.assertTrue(
            response.context["form"].initial["scheduled_for"].endswith("13:00")
        )

    def test_cancelling_does_not_require_a_time(self):
        self.client.post(
            reverse("dashboard:consultation_detail", args=[self.booking.pk]),
            confirm_payload(
                self.when, status=Consultation.Status.CANCELLED, scheduled_for=""
            ),
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Consultation.Status.CANCELLED)
        self.assertEqual(len(mail.outbox), 0)


@fast_passwords
class ConsultationListTests(TestCase):
    def setUp(self):
        self.staff = make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

        self.phone = make_booking(delivery=Consultation.Delivery.PHONE)
        self.home = make_booking(
            email="home@example.com",
            delivery=Consultation.Delivery.HOME,
            suburb="Highfields",
            status=Consultation.Status.CONFIRMED,
            scheduled_for=timezone.now() + timedelta(days=3),
            assigned_to=self.staff,
        )

    def rows(self, **params):
        response = self.client.get(reverse("dashboard:consultation_list"), params)
        return {c.email for c in response.context["page_obj"]}

    def test_filters(self):
        self.assertEqual(self.rows(status="requested"), {"dana@example.com"})
        self.assertEqual(self.rows(delivery="home"), {"home@example.com"})
        self.assertEqual(self.rows(assigned="me"), {"home@example.com"})
        self.assertEqual(self.rows(assigned="unassigned"), {"dana@example.com"})

    def test_search_by_reference(self):
        self.assertEqual(self.rows(q=self.phone.reference), {"dana@example.com"})

    def test_awaiting_count_and_upcoming_are_reported(self):
        response = self.client.get(reverse("dashboard:consultation_list"))
        self.assertEqual(response.context["awaiting"], 1)
        self.assertIn(self.home, response.context["upcoming"])

    def test_dashboard_home_surfaces_the_queue(self):
        response = self.client.get(reverse("dashboard:index"))
        tile = next(
            t
            for t in response.context["tiles"]
            if t["label"] == "Consultations to confirm"
        )
        self.assertEqual(tile["value"], 1)
        self.assertIn(self.home, response.context["upcoming_consultations"])
