"""Re-encode images that were uploaded before `pages.imaging` existed.

New uploads are shrunk on the way in by the models' `save()`. Anything already
in storage predates that, so it is still whatever the editor sent - for the
images that shipped with this project, 2.2 MB PNGs. Run this once before moving
media to S3, so the fat originals are never uploaded in the first place.

Re-running is safe: an image that is already at or below what we would produce
is reported as "already small" and left alone.
"""

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from pages import imaging
from pages.models import Service, SiteSettings, TeamMember

# Mirrors the `optimize_field` calls in each model's `save()`. The specs
# themselves live in `pages.imaging` so the two cannot disagree.
TARGETS = [
    (Service, "image", imaging.SERVICE_IMAGE),
    (TeamMember, "photo", imaging.TEAM_PHOTO),
    (SiteSettings, "logo", imaging.LOGO),
    (SiteSettings, "logo_light", imaging.LOGO),
    (SiteSettings, "favicon", imaging.FAVICON),
]


class Command(BaseCommand):
    help = "Shrink already-uploaded images to the sizes the templates render."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--keep-originals",
            action="store_true",
            help=(
                "Leave the superseded file in storage. By default it is "
                "deleted, because nothing references it once the field has "
                "been repointed."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep = options["keep_originals"]
        before = after = 0
        changed = skipped = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run - nothing is written.\n"))

        for model, field_name, spec in TARGETS:
            for obj in model.objects.exclude(**{field_name: ""}):
                result = self._process(obj, field_name, spec, dry_run, keep)
                if result is None:
                    skipped += 1
                    continue
                old_size, new_size = result
                before += old_size
                after += new_size
                changed += 1

        self.stdout.write("")
        if not changed:
            self.stdout.write(self.style.SUCCESS(f"Nothing to do ({skipped} already small)."))
            return

        saved = before - after
        self.stdout.write(
            self.style.SUCCESS(
                f"{changed} image(s) {_kb(before)} -> {_kb(after)} "
                f"(saved {_kb(saved)}, {before / after:.1f}x smaller). "
                f"{skipped} left alone."
            )
        )

    def _process(self, obj, field_name, spec, dry_run, keep):
        field_file = getattr(obj, field_name)
        old_name = field_file.name

        try:
            with field_file.open("rb") as handle:
                original = handle.read()
        except (FileNotFoundError, OSError) as exc:
            # A row can outlive its file - a redeploy without a volume is the
            # usual cause. Report it rather than aborting the whole run.
            self.stdout.write(self.style.ERROR(f"  missing  {old_name} ({exc})"))
            return None

        payload = imaging.encode(ContentFile(original), spec)
        if payload is None:
            self.stdout.write(f"  keep     {old_name} (already small)")
            return None

        label = f"{_kb(len(original))} -> {_kb(len(payload))}"
        new_name = imaging.storage_name(old_name.rsplit("/", 1)[-1], spec)

        if dry_run:
            self.stdout.write(f"  would    {old_name}  {label}")
            return len(original), len(payload)

        setattr(obj, field_name, ContentFile(payload, name=new_name))
        obj.save(update_fields=[field_name])
        stored = getattr(obj, field_name).name
        self.stdout.write(f"  wrote    {stored}  {label}")

        # Only ever the file this field just stopped pointing at, and only when
        # storage actually gave the replacement a different name.
        if not keep and stored != old_name:
            field_file.storage.delete(old_name)
            self.stdout.write(f"  deleted  {old_name}")

        return len(original), len(payload)


def _kb(size):
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024:.0f} KB"
