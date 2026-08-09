"""Editing site settings from the dashboard."""

import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.models import SiteSettings, SocialLink

from .tests import fast_passwords, make_user

MEDIA_ROOT = tempfile.mkdtemp()
URL = reverse("dashboard:site_settings")


def tiny_png(name="logo.png"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (124, 179, 66)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def payload(**overrides):
    """A full POST: the settings form plus the social-link formset."""
    links = list(SocialLink.objects.order_by("pk"))
    data = {
        "name": "Rightway Support Services",
        "tagline": "Your Path, Our Support",
        "footer_description": "A registered NDIS provider in Toowoomba.",
        "phone": "0470 522 587",
        "email": "arshdeep@rightwaysupportservices.com.au",
        "address": "Toowoomba, QLD 4350",
        "hours": "Mon - Fri, 8:00 AM - 5:00 PM",
        "abn": "",
        "map_address": "Toowoomba QLD 4350 Australia",
        "map_embed_url": "",
        # Formset management data
        "form-TOTAL_FORMS": str(len(links) + 1),
        "form-INITIAL_FORMS": str(len(links)),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    for index, link in enumerate(links):
        data[f"form-{index}-id"] = str(link.pk)
        data[f"form-{index}-platform"] = link.platform
        data[f"form-{index}-url"] = link.url
        data[f"form-{index}-order"] = str(link.order)
        if link.is_published:
            data[f"form-{index}-is_published"] = "on"
    # The trailing blank row
    blank = len(links)
    data[f"form-{blank}-id"] = ""
    data[f"form-{blank}-platform"] = ""
    data[f"form-{blank}-url"] = ""
    data[f"form-{blank}-order"] = "0"

    data.update(overrides)
    return data


@fast_passwords
class SettingsAccessTests(TestCase):
    def test_anonymous_is_redirected(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_staff_without_permission_is_forbidden(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_change_permission_grants_access(self):
        make_user("editor", staff=True, perms=["pages.change_sitesettings"])
        self.client.login(username="editor", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_menu_entry_follows_permission(self):
        make_user("plain", staff=True)
        self.client.login(username="plain", password="pw-for-tests-1234")
        labels = [
            link["label"]
            for item in self.client.get(reverse("dashboard:index")).context["nav_items"]
            for link in item["links"]
        ]
        self.assertNotIn("Site Settings", labels)

        self.client.logout()
        make_user("editor", staff=True, perms=["pages.change_sitesettings"])
        self.client.login(username="editor", password="pw-for-tests-1234")
        labels = [
            link["label"]
            for item in self.client.get(reverse("dashboard:index")).context["nav_items"]
            for link in item["links"]
        ]
        self.assertIn("Site Settings", labels)


@fast_passwords
@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SettingsEditTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_editing_contact_details_updates_the_public_site(self):
        response = self.client.post(
            URL,
            payload(
                phone="0400 111 222",
                email="hello@example.com",
                address="Highfields, QLD 4352",
                hours="Mon - Sat, 9:00 AM - 4:00 PM",
            ),
        )
        self.assertRedirects(response, URL)

        settings_row = SiteSettings.load()
        self.assertEqual(settings_row.phone, "0400 111 222")

        contact = self.client.get(reverse("contact"))
        self.assertContains(contact, "0400 111 222")
        self.assertContains(contact, "hello@example.com")
        self.assertContains(contact, "tel:+61400111222")

    def test_saving_does_not_create_a_second_row(self):
        self.client.post(URL, payload(name="Renamed"))
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.load().name, "Renamed")

    def test_footer_description_updates(self):
        self.client.post(URL, payload(footer_description="Completely new blurb."))
        self.assertContains(self.client.get(reverse("home")), "Completely new blurb.")

    def test_map_address_updates_the_embed(self):
        self.client.post(URL, payload(map_address="Highfields QLD 4352"))
        self.assertContains(self.client.get(reverse("contact")), "Highfields")

    def test_nonsense_phone_is_rejected(self):
        response = self.client.post(URL, payload(phone="call us maybe"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "phone", "That doesn't look like a phone number."
        )

    def test_logo_upload_replaces_the_shipped_file(self):
        response = self.client.post(URL, {**payload(), "logo": tiny_png()})
        self.assertRedirects(response, URL)

        settings_row = SiteSettings.load()
        self.assertTrue(settings_row.logo)
        self.assertIn("branding/", settings_row.logo.name)
        self.assertEqual(settings_row.logo_url, settings_row.logo.url)

        header = self.client.get(reverse("home"))
        self.assertContains(header, settings_row.logo.url)
        self.assertNotContains(header, "/static/images/logo.png")

    def test_favicon_upload_applies_to_site_and_dashboard(self):
        self.client.post(URL, {**payload(), "favicon": tiny_png("icon.png")})
        settings_row = SiteSettings.load()

        self.assertContains(self.client.get(reverse("home")), settings_row.favicon.url)
        self.assertContains(
            self.client.get(reverse("dashboard:index")), settings_row.favicon.url
        )
        # The login view redirects an authenticated user, so sign out first.
        self.client.logout()
        self.assertContains(
            self.client.get(reverse("dashboard:login")), settings_row.favicon.url
        )

    def test_light_logo_falls_back_to_the_main_logo(self):
        self.client.post(URL, {**payload(), "logo": tiny_png()})
        settings_row = SiteSettings.load()
        self.assertFalse(settings_row.logo_light)
        self.assertEqual(settings_row.logo_light_url, settings_row.logo.url)

    def test_form_posts_as_multipart(self):
        """Without enctype the browser drops the uploads silently."""
        self.assertContains(self.client.get(URL), 'enctype="multipart/form-data"')

    # ------------------------------------------------------- social links

    def test_publishing_a_social_link_shows_it_in_the_footer(self):
        facebook = SocialLink.objects.get(platform="facebook")
        index = list(SocialLink.objects.order_by("pk")).index(facebook)

        data = payload()
        data[f"form-{index}-url"] = "https://facebook.com/rightway"
        data[f"form-{index}-is_published"] = "on"

        self.assertRedirects(self.client.post(URL, data), URL)

        facebook.refresh_from_db()
        self.assertTrue(facebook.is_published)

        footer = self.client.get(reverse("home"))
        self.assertContains(footer, "https://facebook.com/rightway")
        self.assertContains(footer, "Follow Us")

    def test_adding_a_new_social_link_through_the_blank_row(self):
        SocialLink.objects.all().delete()

        data = payload()
        data["form-0-platform"] = "instagram"
        data["form-0-url"] = "https://instagram.com/rightway"
        data["form-0-order"] = "5"
        data["form-0-is_published"] = "on"

        self.assertRedirects(self.client.post(URL, data), URL)

        link = SocialLink.objects.get(platform="instagram")
        self.assertEqual(link.url, "https://instagram.com/rightway")
        self.assertTrue(link.is_published)

    def test_removing_a_social_link(self):
        target = SocialLink.objects.get(platform="whatsapp")
        index = list(SocialLink.objects.order_by("pk")).index(target)

        data = payload()
        data[f"form-{index}-DELETE"] = "on"

        self.assertRedirects(self.client.post(URL, data), URL)
        self.assertFalse(SocialLink.objects.filter(platform="whatsapp").exists())

    def test_invalid_social_url_is_rejected(self):
        data = payload()
        data["form-0-url"] = "not a url"
        response = self.client.post(URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formset"].errors[0])
