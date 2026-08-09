"""Public careers pages: vacancy listing, adverts and applications."""

import io
import shutil
import tempfile
from datetime import timedelta

from django.core import mail
from django.utils.html import escape
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Application, Vacancy


def resume(name="resume.pdf", size=1024, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"x" * size, content_type=content_type)


def application_payload(**overrides):
    return {
        "full_name": "Jamie Reid",
        "email": "jamie@example.com",
        "phone": "0400 000 000",
        "cover_letter": "I have three years of support work experience.",
        "resume": resume(),
        **overrides,
    }


class VacancyModelTests(TestCase):
    def test_migration_ported_the_original_vacancies(self):
        slugs = set(Vacancy.objects.values_list("slug", flat=True))
        self.assertTrue(
            {
                "support-worker",
                "support-coordinator",
                "community-access-worker",
                "admin-assistant",
            }.issubset(slugs)
        )

    def test_slug_generated_and_deduplicated(self):
        first = Vacancy.objects.create(title="Team Leader", summary="s", description="d")
        second = Vacancy.objects.create(title="Team Leader", summary="s", description="d")
        self.assertEqual(first.slug, "team-leader")
        self.assertEqual(second.slug, "team-leader-2")

    def test_detail_line_matches_the_old_format(self):
        vacancy = Vacancy.objects.get(slug="support-worker")
        self.assertEqual(
            vacancy.detail_line, "Casual & part-time · Toowoomba and surrounds"
        )

    def test_closing_date_in_the_past_closes_the_role(self):
        vacancy = Vacancy.objects.create(
            title="Expired",
            summary="s",
            description="d",
            closing_date=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(vacancy.is_closed)
        self.assertFalse(vacancy.accepts_applications)
        self.assertNotIn(vacancy, Vacancy.objects.open_now())

    def test_closing_today_is_still_open(self):
        vacancy = Vacancy.objects.create(
            title="Closes today",
            summary="s",
            description="d",
            closing_date=timezone.localdate(),
        )
        self.assertFalse(vacancy.is_closed)
        self.assertIn(vacancy, Vacancy.objects.open_now())

    def test_unpublished_is_never_open(self):
        vacancy = Vacancy.objects.create(
            title="Draft", summary="s", description="d", is_published=False
        )
        self.assertFalse(vacancy.accepts_applications)
        self.assertNotIn(vacancy, Vacancy.objects.open_now())

    def test_line_lists_split_and_trim(self):
        vacancy = Vacancy.objects.create(
            title="X",
            summary="s",
            description="d",
            responsibilities=" One \n\n Two ",
            requirements="Alpha\n   \nBeta",
        )
        self.assertEqual(vacancy.responsibility_list, ["One", "Two"])
        self.assertEqual(vacancy.requirement_list, ["Alpha", "Beta"])


class CareersPageTests(TestCase):
    def test_listing_shows_open_vacancies(self):
        response = self.client.get(reverse("careers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Support Worker")
        self.assertContains(response, "/careers/support-worker/")

    def test_listing_hides_closed_and_unpublished(self):
        Vacancy.objects.create(
            title="Closed Role",
            summary="s",
            description="d",
            closing_date=timezone.localdate() - timedelta(days=1),
        )
        Vacancy.objects.create(
            title="Draft Role", summary="s", description="d", is_published=False
        )
        response = self.client.get(reverse("careers"))
        self.assertNotContains(response, "Closed Role")
        self.assertNotContains(response, "Draft Role")

    def test_advert_renders_with_its_details(self):
        vacancy = Vacancy.objects.get(slug="support-worker")
        response = self.client.get(vacancy.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, vacancy.title)
        self.assertContains(response, "Toowoomba and surrounds")
        for item in vacancy.requirement_list:
            # escape(): "Driver's licence" renders with an HTML entity.
            self.assertContains(response, escape(item))

    def test_unpublished_advert_404s(self):
        vacancy = Vacancy.objects.create(
            title="Draft", summary="s", description="d", is_published=False
        )
        self.assertEqual(self.client.get(vacancy.get_absolute_url()).status_code, 404)

    def test_closed_advert_is_readable_but_offers_no_form(self):
        vacancy = Vacancy.objects.create(
            title="Closed Role",
            summary="s",
            description="d",
            closing_date=timezone.localdate() - timedelta(days=1),
        )
        response = self.client.get(vacancy.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["form"])
        self.assertContains(response, "Applications for this role have closed")


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp())
class ApplicationSubmissionTests(TestCase):
    def setUp(self):
        self.vacancy = Vacancy.objects.get(slug="support-worker")
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_apply_for_a_vacancy(self):
        response = self.client.post(
            self.vacancy.get_absolute_url(), application_payload()
        )
        self.assertRedirects(response, self.vacancy.get_absolute_url())

        application = Application.objects.get(email="jamie@example.com")
        self.assertEqual(application.vacancy, self.vacancy)
        self.assertEqual(application.vacancy_title, "Support Worker")
        self.assertEqual(application.status, Application.Status.NEW)
        self.assertTrue(application.resume)

    def test_office_is_notified_without_attaching_the_resume(self):
        self.client.post(self.vacancy.get_absolute_url(), application_payload())
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Support Worker", message.subject)
        self.assertEqual(message.reply_to, ["jamie@example.com"])
        # The resume itself is not emailed - it stays in private storage.
        self.assertEqual(message.attachments, [])
        self.assertIn("open it in the dashboard", message.body)

    def test_speculative_application_has_no_vacancy(self):
        response = self.client.post(reverse("apply"), application_payload())
        self.assertRedirects(response, reverse("apply"))
        application = Application.objects.get(email="jamie@example.com")
        self.assertIsNone(application.vacancy)
        self.assertEqual(application.role_label, "Speculative application")

    def test_resume_is_required(self):
        payload = application_payload()
        payload.pop("resume")
        response = self.client.post(self.vacancy.get_absolute_url(), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "resume", "This field is required.")
        self.assertEqual(Application.objects.count(), 0)

    def test_disallowed_file_type_is_rejected(self):
        response = self.client.post(
            self.vacancy.get_absolute_url(),
            application_payload(resume=resume("virus.exe", content_type="application/exe")),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)
        self.assertIn("file types", str(response.context["form"].errors["resume"]))

    def test_oversized_file_is_rejected(self):
        with override_settings(RESUME_MAX_BYTES=100):
            response = self.client.post(
                self.vacancy.get_absolute_url(),
                application_payload(resume=resume(size=500)),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)

    def test_cannot_apply_to_a_closed_vacancy(self):
        self.vacancy.closing_date = timezone.localdate() - timedelta(days=1)
        self.vacancy.save()

        response = self.client.post(
            self.vacancy.get_absolute_url(), application_payload()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)

    def test_resume_is_stored_outside_the_public_media_root(self):
        """Resumes must not be reachable over MEDIA_URL."""
        from django.conf import settings

        self.client.post(self.vacancy.get_absolute_url(), application_payload())
        application = Application.objects.get(email="jamie@example.com")

        stored = application.resume.storage.path(application.resume.name)
        self.assertNotIn(str(settings.MEDIA_ROOT), stored)
        self.assertIn(str(settings.PRIVATE_MEDIA_ROOT), stored)

    def test_deleting_a_vacancy_keeps_the_application_readable(self):
        self.client.post(self.vacancy.get_absolute_url(), application_payload())
        self.vacancy.delete()

        application = Application.objects.get(email="jamie@example.com")
        self.assertIsNone(application.vacancy)
        # The title was copied at submission time, so the record still reads.
        self.assertEqual(application.role_label, "Support Worker")
