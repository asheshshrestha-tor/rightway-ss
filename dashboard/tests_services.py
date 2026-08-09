"""Managing services from the staff dashboard."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.models import Service

from .tests import fast_passwords, make_user


def tiny_png():
    """A real 1x1 PNG, so ImageField's Pillow validation passes."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (124, 179, 66)).save(buffer, format="PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


BASE_FORM = {
    "title": "Respite Care",
    "slug": "",
    "summary": "Short breaks for you and your family.",
    "description": "Planned and emergency respite in your home or ours.",
    "body": "The long version.",
    "highlights": "Overnight stays\nWeekend respite",
    "icon": "hands-heart",
    "order": "60",
    "meta_description": "",
    # Checkboxes: the create form renders these ticked (the model defaults to
    # True), so a normal submission includes them.
    "is_published": "on",
    "show_in_footer": "on",
}


@fast_passwords
class ServiceAccessTests(TestCase):
    def test_anonymous_is_redirected(self):
        response = self.client.get(reverse("dashboard:service_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_staff_without_permission_is_forbidden(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        self.assertEqual(
            self.client.get(reverse("dashboard:service_list")).status_code, 403
        )

    def test_view_permission_is_read_only(self):
        make_user("viewer", staff=True, perms=["pages.view_service"])
        self.client.login(username="viewer", password="pw-for-tests-1234")
        self.assertEqual(
            self.client.get(reverse("dashboard:service_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:service_create")).status_code, 403
        )

    def test_menu_hides_content_section_without_permission(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        labels = [item["label"] for item in response.context["nav_items"]]
        self.assertNotIn("Website Content", labels)

    def test_menu_shows_content_section_with_permission(self):
        make_user("editor", staff=True, perms=["pages.view_service"])
        self.client.login(username="editor", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        labels = [item["label"] for item in response.context["nav_items"]]
        self.assertIn("Website Content", labels)


@fast_passwords
class ServiceCrudTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_create_service_appears_on_the_public_site(self):
        response = self.client.post(reverse("dashboard:service_create"), BASE_FORM)
        self.assertRedirects(response, reverse("dashboard:service_list"))

        service = Service.objects.get(title="Respite Care")
        self.assertEqual(service.slug, "respite-care")
        self.assertTrue(service.is_published)

        listing = self.client.get(reverse("services"))
        self.assertContains(listing, "Respite Care")

        detail = self.client.get(service.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "The long version.")
        self.assertContains(detail, "Overnight stays")

    def test_publishing_is_ticked_by_default_on_the_create_form(self):
        response = self.client.get(reverse("dashboard:service_create"))
        form = response.context["form"]
        self.assertTrue(form["is_published"].value())
        self.assertTrue(form["show_in_footer"].value())

    def test_create_unpublished_stays_off_the_site(self):
        payload = {**BASE_FORM}
        payload.pop("is_published")  # unticked checkboxes are simply absent
        self.client.post(reverse("dashboard:service_create"), payload)
        service = Service.objects.get(title="Respite Care")
        self.assertFalse(service.is_published)
        self.assertNotContains(self.client.get(reverse("services")), "Respite Care")

    def test_edit_service(self):
        service = Service.objects.get(slug="transport")
        response = self.client.post(
            reverse("dashboard:service_update", args=[service.pk]),
            {
                **BASE_FORM,
                "title": "Transport & Travel",
                "slug": "transport",
                "is_published": "on",
                "show_in_footer": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:service_list"))
        service.refresh_from_db()
        self.assertEqual(service.title, "Transport & Travel")
        self.assertEqual(service.slug, "transport")  # URL preserved

    def test_duplicate_slug_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:service_create"),
            {**BASE_FORM, "slug": "personal-care"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "slug", "Another service already uses this URL."
        )

    def test_delete_service(self):
        service = Service.objects.get(slug="transport")
        response = self.client.post(
            reverse("dashboard:service_delete", args=[service.pk])
        )
        self.assertRedirects(response, reverse("dashboard:service_list"))
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())
        self.assertEqual(self.client.get("/services/transport/").status_code, 404)

    def test_list_filters(self):
        Service.objects.filter(slug="transport").update(is_published=False)

        published = self.client.get(
            reverse("dashboard:service_list"), {"state": "published"}
        )
        self.assertNotIn(
            "transport", [s.slug for s in published.context["page_obj"]]
        )

        drafts = self.client.get(reverse("dashboard:service_list"), {"state": "draft"})
        self.assertEqual([s.slug for s in drafts.context["page_obj"]], ["transport"])

        search = self.client.get(reverse("dashboard:service_list"), {"q": "household"})
        self.assertEqual([s.slug for s in search.context["page_obj"]], ["household-tasks"])

    def test_reordering_changes_the_public_order(self):
        service = Service.objects.get(slug="transport")
        self.client.post(
            reverse("dashboard:service_update", args=[service.pk]),
            {
                **BASE_FORM,
                "title": service.title,
                "slug": service.slug,
                "order": "1",
                "is_published": "on",
            },
        )
        first = self.client.get(reverse("home")).context["featured_services"][0]
        self.assertEqual(first.slug, "transport")


@fast_passwords
class ServiceImageUploadTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_uploaded_image_is_stored_and_used(self):
        import shutil
        import tempfile

        media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media):
                response = self.client.post(
                    reverse("dashboard:service_create"),
                    {**BASE_FORM, "image": tiny_png()},
                )
                self.assertRedirects(response, reverse("dashboard:service_list"))

                service = Service.objects.get(title="Respite Care")
                self.assertTrue(service.has_uploaded_image)
                self.assertIn("services/", service.image.name)
                # image_url now points at the upload, not the placeholder.
                self.assertEqual(service.image_url, service.image.url)
                self.assertNotIn("placeholder", service.image_url)
        finally:
            shutil.rmtree(media, ignore_errors=True)

    def test_form_posts_as_multipart(self):
        """Without enctype the browser drops the file silently, so assert the
        template actually declares it."""
        response = self.client.get(reverse("dashboard:service_create"))
        self.assertContains(response, 'enctype="multipart/form-data"')
