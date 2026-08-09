"""Dashboard vacancy management and application handling.

The resume access-control tests here are the important ones: a resume is
personal information, and the only legitimate way to read one is through a
permission-checked view.
"""

import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pages.models import Application, Vacancy

from .tests import fast_passwords, make_user

PRIVATE_ROOT = tempfile.mkdtemp()

VACANCY_FORM = {
    "title": "Team Leader",
    "slug": "",
    "employment_type": "full_time",
    "location": "Toowoomba, QLD",
    "summary": "Lead a team of support workers.",
    "description": "A great role.",
    "responsibilities": "Lead the team\nRun supervisions",
    "requirements": "Experience leading teams",
    "salary_range": "",
    "closing_date": "",
    "order": "5",
    "is_published": "on",
}


def make_application(vacancy=None, **overrides):
    data = {
        "full_name": "Jamie Reid",
        "email": "jamie@example.com",
        "phone": "0400 000 000",
        "cover_letter": "Please consider me.",
        "resume": SimpleUploadedFile("resume.pdf", b"pdf-bytes", "application/pdf"),
        "vacancy": vacancy,
        "vacancy_title": vacancy.title if vacancy else "",
        **overrides,
    }
    return Application.objects.create(**data)


@fast_passwords
@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_ROOT)
class VacancyDashboardTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_permission_gating(self):
        self.client.logout()
        make_user("viewer", staff=True, perms=["pages.view_vacancy"])
        self.client.login(username="viewer", password="pw-for-tests-1234")

        self.assertEqual(
            self.client.get(reverse("dashboard:vacancy_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:vacancy_create")).status_code, 403
        )

    def test_menu_entries_follow_permissions(self):
        self.client.logout()
        make_user("plain", staff=True)
        self.client.login(username="plain", password="pw-for-tests-1234")
        labels = [
            item["label"]
            for item in self.client.get(reverse("dashboard:index")).context["nav_items"]
        ]
        self.assertNotIn("Recruitment", labels)

        self.client.logout()
        make_user("recruiter", staff=True, perms=["pages.view_application"])
        self.client.login(username="recruiter", password="pw-for-tests-1234")
        labels = [
            item["label"]
            for item in self.client.get(reverse("dashboard:index")).context["nav_items"]
        ]
        self.assertIn("Recruitment", labels)

    def test_create_vacancy_shows_on_the_careers_page(self):
        response = self.client.post(reverse("dashboard:vacancy_create"), VACANCY_FORM)
        self.assertRedirects(response, reverse("dashboard:vacancy_list"))

        vacancy = Vacancy.objects.get(title="Team Leader")
        self.assertEqual(vacancy.slug, "team-leader")

        careers = self.client.get(reverse("careers"))
        self.assertContains(careers, "Team Leader")

        advert = self.client.get(vacancy.get_absolute_url())
        self.assertContains(advert, "Run supervisions")

    def test_closing_date_removes_it_from_the_careers_page(self):
        vacancy = Vacancy.objects.get(slug="support-worker")
        yesterday = timezone.localdate() - timedelta(days=1)
        self.client.post(
            reverse("dashboard:vacancy_update", args=[vacancy.pk]),
            {
                **VACANCY_FORM,
                "title": vacancy.title,
                "slug": vacancy.slug,
                "closing_date": yesterday.isoformat(),
            },
        )
        vacancy.refresh_from_db()
        self.assertTrue(vacancy.is_closed)
        self.assertNotContains(self.client.get(reverse("careers")), "/careers/support-worker/")

    def test_duplicate_slug_rejected(self):
        response = self.client.post(
            reverse("dashboard:vacancy_create"),
            {**VACANCY_FORM, "slug": "support-worker"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "slug", "Another vacancy already uses this URL."
        )

    def test_delete_vacancy_keeps_its_applications(self):
        vacancy = Vacancy.objects.get(slug="support-worker")
        make_application(vacancy)

        response = self.client.post(
            reverse("dashboard:vacancy_delete", args=[vacancy.pk])
        )
        self.assertRedirects(response, reverse("dashboard:vacancy_list"))

        application = Application.objects.get(email="jamie@example.com")
        self.assertIsNone(application.vacancy)
        self.assertEqual(application.role_label, "Support Worker")

    def test_list_shows_application_counts(self):
        vacancy = Vacancy.objects.get(slug="support-worker")
        make_application(vacancy)
        response = self.client.get(reverse("dashboard:vacancy_list"))
        row = next(v for v in response.context["page_obj"] if v.pk == vacancy.pk)
        self.assertEqual(row.application_count, 1)


@fast_passwords
@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_ROOT)
class ApplicationDashboardTests(TestCase):
    def setUp(self):
        self.boss = make_user("boss", superuser=True)
        self.vacancy = Vacancy.objects.get(slug="support-worker")
        self.application = make_application(self.vacancy)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_list_and_detail_render(self):
        self.assertEqual(
            self.client.get(reverse("dashboard:application_list")).status_code, 200
        )
        detail = self.client.get(
            reverse("dashboard:application_detail", args=[self.application.pk])
        )
        self.assertContains(detail, "Jamie Reid")
        self.assertContains(detail, "Please consider me.")

    def test_filters(self):
        other = Vacancy.objects.get(slug="admin-assistant")
        make_application(other, email="other@example.com", full_name="Sam Rivers")
        make_application(None, email="spec@example.com", full_name="Spec Person")

        def rows(**params):
            response = self.client.get(reverse("dashboard:application_list"), params)
            return {a.email for a in response.context["page_obj"]}

        self.assertEqual(rows(vacancy=str(self.vacancy.pk)), {"jamie@example.com"})
        self.assertEqual(rows(vacancy="speculative"), {"spec@example.com"})
        self.assertEqual(rows(q="Sam"), {"other@example.com"})
        self.assertEqual(rows(assigned="unassigned"), {
            "jamie@example.com", "other@example.com", "spec@example.com"
        })

    def test_update_status_and_assignee(self):
        response = self.client.post(
            reverse("dashboard:application_detail", args=[self.application.pk]),
            {
                "status": Application.Status.SHORTLISTED,
                "handled_by": self.boss.pk,
                "notes": "Strong candidate.",
            },
        )
        self.assertRedirects(
            response,
            reverse("dashboard:application_detail", args=[self.application.pk]),
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SHORTLISTED)
        self.assertEqual(self.application.handled_by, self.boss)

    def test_read_only_user_cannot_update(self):
        self.client.logout()
        make_user("readonly", staff=True, perms=["pages.view_application"])
        self.client.login(username="readonly", password="pw-for-tests-1234")

        response = self.client.post(
            reverse("dashboard:application_detail", args=[self.application.pk]),
            {"status": Application.Status.HIRED},
            follow=True,
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.NEW)
        self.assertContains(response, "do not have permission")


@fast_passwords
@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_ROOT)
class ResumeAccessTests(TestCase):
    """A resume is personal information. Only authorised staff may read one."""

    def setUp(self):
        self.vacancy = Vacancy.objects.get(slug="support-worker")
        self.application = make_application(self.vacancy)
        self.url = reverse("dashboard:application_resume", args=[self.application.pk])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE_ROOT, ignore_errors=True)

    def test_anonymous_cannot_download(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_signed_in_non_staff_cannot_download(self):
        make_user("visitor")
        self.client.login(username="visitor", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_without_the_permission_cannot_download(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_authorised_staff_can_download(self):
        make_user("recruiter", staff=True, perms=["pages.view_application"])
        self.client.login(username="recruiter", password="pw-for-tests-1234")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"pdf-bytes")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_resume_is_not_served_from_media_url(self):
        """The uploaded file must not be reachable by URL guessing."""
        from django.conf import settings

        make_user("recruiter", staff=True, perms=["pages.view_application"])
        self.client.login(username="recruiter", password="pw-for-tests-1234")

        guessed = f"/{settings.MEDIA_URL}{self.application.resume.name}"
        self.assertEqual(self.client.get(guessed).status_code, 404)

    def test_missing_file_404s_rather_than_erroring(self):
        import os

        make_user("recruiter", staff=True, perms=["pages.view_application"])
        self.client.login(username="recruiter", password="pw-for-tests-1234")

        os.remove(self.application.resume.storage.path(self.application.resume.name))
        self.assertEqual(self.client.get(self.url).status_code, 404)


class MediaLayoutTests(TestCase):
    """Django now serves MEDIA_ROOT itself in production, because a container
    host has no web server in front of the app. That is only safe while the
    private tree sits outside the public one, so assert it rather than trust it.
    """

    def test_private_media_is_not_inside_public_media(self):
        from pathlib import Path

        from django.conf import settings

        public = Path(str(settings.MEDIA_ROOT)).resolve()
        private = Path(str(settings.PRIVATE_MEDIA_ROOT)).resolve()

        self.assertNotEqual(public, private)
        self.assertFalse(
            private.is_relative_to(public),
            f"PRIVATE_MEDIA_ROOT ({private}) is inside MEDIA_ROOT ({public}), "
            "so every applicant's resume is downloadable by guessing a URL.",
        )
