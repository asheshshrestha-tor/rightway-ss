"""Managing the team from the dashboard."""

import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.models import TeamMember

from .tests import fast_passwords, make_user

MEDIA_ROOT = tempfile.mkdtemp()

BASE_FORM = {
    "name": "Alex Chen",
    "slug": "",
    "role": "Support Worker",
    "bio": "Alex has supported people with disability for six years.",
    "qualifications": "NDIS Worker Screening Check\nFirst Aid certified",
    "order": "50",
    "is_published": "on",
}


def tiny_png():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (124, 179, 66)).save(buffer, format="PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


@fast_passwords
class TeamAccessTests(TestCase):
    def test_anonymous_is_redirected(self):
        response = self.client.get(reverse("dashboard:team_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_staff_without_permission_is_forbidden(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        self.assertEqual(
            self.client.get(reverse("dashboard:team_list")).status_code, 403
        )

    def test_view_permission_is_read_only(self):
        make_user("viewer", staff=True, perms=["pages.view_teammember"])
        self.client.login(username="viewer", password="pw-for-tests-1234")
        self.assertEqual(
            self.client.get(reverse("dashboard:team_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:team_create")).status_code, 403
        )

    def test_menu_entry_follows_permission(self):
        make_user("editor", staff=True, perms=["pages.view_teammember"])
        self.client.login(username="editor", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        links = [
            link["label"]
            for item in response.context["nav_items"]
            for link in item["links"]
        ]
        self.assertIn("Team", links)


@fast_passwords
@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TeamCrudTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_adding_someone_shows_them_on_the_about_page(self):
        response = self.client.post(reverse("dashboard:team_create"), BASE_FORM)
        self.assertRedirects(response, reverse("dashboard:team_list"))

        member = TeamMember.objects.get(name="Alex Chen")
        self.assertEqual(member.slug, "alex-chen")

        about = self.client.get(reverse("about"))
        self.assertContains(about, "Alex Chen")

        profile = self.client.get(member.get_absolute_url())
        self.assertContains(profile, "six years")
        self.assertContains(profile, "First Aid certified")

    def test_published_is_ticked_by_default(self):
        response = self.client.get(reverse("dashboard:team_create"))
        self.assertTrue(response.context["form"]["is_published"].value())

    def test_adding_unpublished_keeps_them_off_the_site(self):
        payload = {**BASE_FORM}
        payload.pop("is_published")
        self.client.post(reverse("dashboard:team_create"), payload)

        member = TeamMember.objects.get(name="Alex Chen")
        self.assertFalse(member.is_published)
        self.assertNotContains(self.client.get(reverse("about")), "Alex Chen")

    def test_editing_keeps_the_url_stable(self):
        member = TeamMember.objects.get(slug="sarah-wilson")
        self.client.post(
            reverse("dashboard:team_update", args=[member.pk]),
            {**BASE_FORM, "name": "Sarah Wilson-Hughes", "slug": "sarah-wilson"},
        )
        member.refresh_from_db()
        self.assertEqual(member.name, "Sarah Wilson-Hughes")
        self.assertEqual(member.slug, "sarah-wilson")

    def test_duplicate_slug_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:team_create"), {**BASE_FORM, "slug": "priya-kaur"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "slug",
            "Another team member already uses this URL.",
        )

    def test_removing_someone(self):
        member = TeamMember.objects.get(slug="sarah-wilson")
        response = self.client.post(reverse("dashboard:team_delete", args=[member.pk]))
        self.assertRedirects(response, reverse("dashboard:team_list"))
        self.assertFalse(TeamMember.objects.filter(pk=member.pk).exists())
        self.assertEqual(self.client.get("/about/team/sarah-wilson/").status_code, 404)

    def test_reordering_changes_the_about_page_order(self):
        member = TeamMember.objects.get(slug="sarah-wilson")
        self.client.post(
            reverse("dashboard:team_update", args=[member.pk]),
            {**BASE_FORM, "name": member.name, "slug": member.slug, "order": "1"},
        )
        first = self.client.get(reverse("about")).context["team"][0]
        self.assertEqual(first.slug, "sarah-wilson")

    def test_photo_upload_is_used_instead_of_the_placeholder(self):
        response = self.client.post(
            reverse("dashboard:team_create"), {**BASE_FORM, "photo": tiny_png()}
        )
        self.assertRedirects(response, reverse("dashboard:team_list"))

        member = TeamMember.objects.get(name="Alex Chen")
        self.assertTrue(member.has_uploaded_photo)
        self.assertIn("team/", member.photo.name)
        self.assertEqual(member.photo_url, member.photo.url)
        self.assertNotIn("placeholder", member.photo_url)

    def test_form_posts_as_multipart(self):
        """Without enctype the browser drops the photo silently."""
        response = self.client.get(reverse("dashboard:team_create"))
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_list_filters(self):
        TeamMember.objects.filter(slug="sarah-wilson").update(is_published=False)

        published = self.client.get(
            reverse("dashboard:team_list"), {"state": "published"}
        )
        self.assertNotIn(
            "sarah-wilson", [m.slug for m in published.context["page_obj"]]
        )

        drafts = self.client.get(reverse("dashboard:team_list"), {"state": "draft"})
        self.assertEqual([m.slug for m in drafts.context["page_obj"]], ["sarah-wilson"])

        search = self.client.get(reverse("dashboard:team_list"), {"q": "coordinator"})
        self.assertEqual([m.slug for m in search.context["page_obj"]], ["michael-brown"])
