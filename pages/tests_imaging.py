"""Uploads are shrunk on the way into storage."""

import io
import mimetypes
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from pages import imaging
from pages.models import Service, SiteSettings, TeamMember

MEDIA_ROOT = tempfile.mkdtemp()


def png(width=1600, height=1200, name="photo.png", alpha=False):
    """A PNG that behaves like a real photograph.

    Smooth gradients with a little sensor-style noise over the top: the noise
    is what makes a PNG of a photo large, and smoothing it away is most of what
    WebP buys. A flat colour or pure noise would both be degenerate - one
    compresses to nothing in either format, the other in neither.
    """
    size = (width, height)
    gradient = Image.linear_gradient("L").resize(size)
    base = Image.merge(
        "RGB",
        (gradient, gradient.transpose(Image.ROTATE_180), Image.new("L", size, 120)),
    )
    grain = Image.effect_noise(size, 28).convert("L")
    image = Image.blend(base, Image.merge("RGB", (grain, grain, grain)), 0.12)
    if alpha:
        image.putalpha(gradient)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def stored(field_file):
    with field_file.open("rb") as handle:
        return Image.open(io.BytesIO(handle.read()))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UploadOptimisationTests(TestCase):
    def test_a_service_image_is_stored_as_a_resized_webp(self):
        upload = png()
        service = Service.objects.create(title="Respite", image=upload)

        self.assertTrue(service.image.name.endswith(".webp"))
        image = stored(service.image)
        self.assertEqual(image.format, "WEBP")
        self.assertLessEqual(image.width, imaging.SERVICE_IMAGE.max_width)
        self.assertLessEqual(image.height, imaging.SERVICE_IMAGE.max_height)

    def test_the_stored_file_is_dramatically_smaller(self):
        upload = png()
        original = upload.size
        service = Service.objects.create(title="Respite", image=upload)

        self.assertLess(service.image.size, original / 5)

    def test_the_filename_is_slugified(self):
        """Spaces and punctuation have to be percent-encoded in an S3 key by
        every consumer, so they are removed once, here."""
        service = Service.objects.create(
            title="Transport", image=png(name="Reliable transport & more..png")
        )

        self.assertEqual(service.image.name, "services/reliable-transport-more.webp")

    def test_a_team_photo_uses_its_own_smaller_bounds(self):
        member = TeamMember.objects.create(name="Dana Whitfield", role="Coordinator", photo=png())

        self.assertLessEqual(stored(member.photo).width, imaging.TEAM_PHOTO.max_width)

    def test_a_favicon_stays_a_png(self):
        """WebP is fine everywhere the site draws an image, but `rel="icon"` is
        not worth the compatibility question for a few KB."""
        row = SiteSettings.load()
        row.favicon = png(512, 512, name="icon.png")
        row.save()

        self.assertTrue(row.favicon.name.endswith(".png"))
        self.assertEqual(stored(row.favicon).format, "PNG")

    def test_a_transparent_logo_keeps_its_alpha_channel(self):
        row = SiteSettings.load()
        row.logo = png(800, 400, name="logo.png", alpha=True)
        row.save()

        self.assertEqual(stored(row.logo).mode, "RGBA")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UntouchedUploadTests(TestCase):
    def test_saving_an_unrelated_field_does_not_rewrite_the_image(self):
        """The guard that keeps this cheap on object storage.

        Without it every save of an unrelated field would pull the object back
        out of S3, re-encode it and write a new one - a GET, a PUT and a
        duplicate object for editing a title.
        """
        service = Service.objects.create(title="Respite", image=png())
        name = service.image.name

        service.title = "Respite Care"
        service.save()

        self.assertEqual(service.image.name, name)

    def test_re_encoding_an_already_optimised_file_is_skipped(self):
        """What makes `optimize_images` safe to run twice.

        Without the guard a second pass would spend another generation of
        lossy quality to save nothing.
        """
        once = imaging.encode(png(), imaging.SERVICE_IMAGE)

        self.assertIsNotNone(once)
        self.assertIsNone(imaging.encode(ContentFile(once), imaging.SERVICE_IMAGE))

    def test_an_oversized_file_already_in_the_target_format_is_still_resized(self):
        """The skip is on format *and* bounds - a huge WebP still gets cut."""
        wide = ContentFile(imaging.encode(png(1600, 1200), imaging.SERVICE_IMAGE))

        cut = imaging.encode(wide, imaging.TEAM_PHOTO)

        self.assertIsNotNone(cut)
        self.assertLessEqual(Image.open(io.BytesIO(cut)).width, imaging.TEAM_PHOTO.max_width)

    def test_a_file_pillow_cannot_read_is_passed_through_rewound(self):
        """`ImageField`'s own validation should report it, not a 500 in here."""
        junk = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 not an image")

        self.assertIsNone(imaging.encode(junk, imaging.SERVICE_IMAGE))
        self.assertEqual(junk.read(), b"%PDF-1.4 not an image")


class MetadataTests(TestCase):
    def test_exif_is_not_carried_into_the_stored_file(self):
        """A phone photo of a team member records the model and often the GPS
        coordinates it was taken at. Neither belongs on a public page."""
        image = Image.new("RGB", (900, 700), (12, 90, 60))
        exif = Image.Exif()
        exif[271] = "SecretCameraCo"  # Make
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", exif=exif)
        upload = SimpleUploadedFile("shot.jpg", buffer.getvalue())

        payload = imaging.encode(upload, imaging.TEAM_PHOTO)

        self.assertNotIn(b"SecretCameraCo", payload)


class ContentTypeTests(TestCase):
    """Registered in `PagesConfig.ready`, and worth a test because getting it
    wrong fails silently and permanently.

    S3 records a Content-Type when an object is written and only a re-upload
    changes it, so an unrecognised extension would leave every image in the
    bucket stored as `binary/octet-stream`.
    """

    def test_webp_is_recognised(self):
        self.assertEqual(mimetypes.guess_type("photo.webp")[0], "image/webp")

    def test_the_resume_formats_are_recognised(self):
        for extension in settings.RESUME_ALLOWED_EXTENSIONS:
            with self.subTest(extension=extension):
                self.assertIsNotNone(mimetypes.guess_type(f"cv{extension}")[0])
