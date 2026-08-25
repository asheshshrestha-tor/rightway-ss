import mimetypes

from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pages"

    def ready(self):
        # S3 records a Content-Type when an object is written, from whatever
        # `mimetypes` says at that moment, and getting it wrong is not something
        # a later request can correct - the value is stored on the object and
        # only a re-upload changes it.
        #
        # Python's table is seeded from the host: `.webp` is absent on Windows
        # unless the registry happens to carry it, so a developer running the
        # sync from their own machine would upload every optimised image as
        # `binary/octet-stream`. Registering the two we actually produce or
        # accept makes that independent of where the code runs.
        mimetypes.add_type("image/webp", ".webp")
        mimetypes.add_type("application/vnd.oasis.opendocument.text", ".odt")
