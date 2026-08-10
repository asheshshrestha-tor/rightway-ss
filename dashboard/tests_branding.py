"""The dashboard's own branding: the profile thumbnail and the logo.

Both used to be hard-coded - "AD" on the avatar and an "RS" tile for the logo -
so these mostly guard against either creeping back in.
"""

import io
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from pages.models import SiteSettings

from .templatetags.avatars import avatar_initials, avatar_url
from .tests import fast_passwords, make_user

MEDIA_ROOT = tempfile.mkdtemp()


def tiny_png(name="logo.png"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (124, 179, 66)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@fast_passwords
class AvatarTagTests(TestCase):
    def test_it_uses_the_full_name_when_there_is_one(self):
        """"Priya Kaur" should give PK, not the PH of a username."""
        user = User(username="phandler", first_name="Priya", last_name="Kaur")

        self.assertIn("name=Priya+Kaur", avatar_url(user))
        self.assertEqual(avatar_initials(user), "PK")

    def test_it_falls_back_to_the_username(self):
        user = User(username="phandler")

        self.assertIn("name=phandler", avatar_url(user))
        self.assertEqual(avatar_initials(user), "PH")

    def test_the_size_is_requested_from_the_service(self):
        """Asking for double the rendered size keeps it sharp on a retina
        screen; the service crops to whatever is requested."""
        self.assertIn("size=80", avatar_url(User(username="a"), 80))
        self.assertIn("size=200", avatar_url(User(username="a"), 200))

    def test_a_single_word_name_still_gives_two_letters(self):
        self.assertEqual(avatar_initials(User(username="admin")), "AD")

    def test_a_name_with_punctuation_is_url_encoded(self):
        """An unencoded space or ampersand would truncate the query string."""
        user = User(username="x", first_name="Anne-Marie", last_name="O'Brien")

        url = avatar_url(user)
        self.assertNotIn(" ", url)
        self.assertIn("O%27Brien", url)


@fast_passwords
class TopbarAvatarTests(TestCase):
    def setUp(self):
        make_user("boss", staff=True, superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_the_thumbnail_is_generated_for_the_signed_in_user(self):
        html = self.client.get(reverse("dashboard:index")).content.decode()

        self.assertIn("ui-avatars.com/api/", html)
        self.assertIn("name=boss", html)

    def test_initials_sit_underneath_as_a_fallback(self):
        """If the service is unreachable the image removes itself, so the
        initials have to already be in the markup."""
        html = self.client.get(reverse("dashboard:index")).content.decode()

        self.assertIn("avatar-stack", html)
        self.assertIn("onerror=\"this.remove()\"", html)

    def test_no_hard_coded_initials_remain(self):
        html = self.client.get(reverse("dashboard:index")).content.decode()
        self.assertNotIn(">AD<", html)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
@fast_passwords
class DashboardLogoTests(TestCase):
    def setUp(self):
        make_user("boss", staff=True, superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_it_comes_from_site_settings(self):
        settings_row = SiteSettings.load()
        settings_row.logo = tiny_png("uploaded-logo.png")
        settings_row.save()

        html = self.client.get(reverse("dashboard:index")).content.decode()
        self.assertIn("uploaded-logo", html)

    def test_it_falls_back_to_the_shipped_file_when_nothing_is_uploaded(self):
        """A dashboard with no logo at all would look broken."""
        html = self.client.get(reverse("dashboard:index")).content.decode()
        self.assertIn("images/logo", html)

    def test_both_themes_are_covered(self):
        """The colour logo vanishes on the dark theme and the white one on the
        light theme, so each has to be present for the switcher to pick."""
        html = self.client.get(reverse("dashboard:index")).content.decode()

        self.assertIn("dashboard-logo theme-light-show", html)
        self.assertIn("dashboard-logo theme-dark-show", html)

    def test_the_sign_in_page_uses_it_too(self):
        settings_row = SiteSettings.load()
        settings_row.logo = tiny_png("signin-logo.png")
        settings_row.save()

        # A signed-in client is redirected away from the sign-in page.
        html = Client().get(reverse("dashboard:login")).content.decode()
        self.assertIn("signin-logo", html)

    def test_the_business_name_is_not_hard_coded_on_the_sign_in_page(self):
        settings_row = SiteSettings.load()
        settings_row.name = "Renamed Provider"
        settings_row.save()

        html = Client().get(reverse("dashboard:login")).content.decode()
        self.assertIn("Renamed Provider", html)

    def test_the_rs_tile_is_gone_everywhere(self):
        signed_out = Client()
        for client, name in [
            (self.client, "dashboard:index"),
            (signed_out, "dashboard:login"),
            (signed_out, "dashboard:password_reset"),
        ]:
            with self.subTest(page=name):
                html = client.get(reverse(name)).content.decode()
                self.assertNotIn("brand-mark", html)
