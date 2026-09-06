"""Copy existing uploads from the filesystem into the configured buckets.

The one-off step when moving off a local disk or a mounted volume. Object keys
are the paths already recorded in the database - `services/personal-care.webp`,
`resumes/support-worker/dana.pdf` - so nothing in the database has to change
and no row is left pointing at a file that is not there.

Run it from wherever the files actually are, with USE_S3 on and the AWS
variables set:

    USE_S3=True python manage.py sync_media_to_s3 --dry-run
    USE_S3=True python manage.py sync_media_to_s3

An object that is already in the bucket is left alone, so an interrupted run
can simply be repeated.
"""

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload MEDIA_ROOT and PRIVATE_MEDIA_ROOT into the S3 buckets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be uploaded without writing anything.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Replace objects that are already in the bucket. Off by "
                "default so a repeated run resumes rather than re-uploads."
            ),
        )
        parser.add_argument(
            "--only",
            choices=["public", "private"],
            help="Sync just one of the two roots.",
        )

    def handle(self, *args, **options):
        if not settings.USE_S3:
            raise CommandError(
                "USE_S3 is off, so the destination would be the same "
                "filesystem the files are already on. Set USE_S3=True and the "
                "AWS_* variables before running this."
            )

        roots = [
            ("public", Path(str(settings.MEDIA_ROOT)), storages["default"]),
            ("private", Path(str(settings.PRIVATE_MEDIA_ROOT)), storages["private"]),
        ]
        if options["only"]:
            roots = [r for r in roots if r[0] == options["only"]]

        uploaded = skipped = 0
        transferred = 0

        for label, root, storage in roots:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\n{label}: {root} -> s3://{storage.bucket_name}/"
                    f"{storage.location + '/' if storage.location else ''}"
                )
            )
            if not root.is_dir():
                self.stdout.write(self.style.WARNING("  no such directory, skipping"))
                continue

            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                key = path.relative_to(root).as_posix()
                result = self._upload(path, key, storage, options)
                if result is None:
                    skipped += 1
                else:
                    uploaded += 1
                    transferred += result

        self.stdout.write("")
        verb = "would upload" if options["dry_run"] else "uploaded"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {uploaded} file(s), {_size(transferred)}; "
                f"{skipped} already present."
            )
        )

    def _upload(self, path, key, storage, options):
        if storage.exists(key):
            if not options["force"]:
                self.stdout.write(f"  skip    {key} (already there)")
                return None
            if not options["dry_run"]:
                storage.delete(key)

        size = path.stat().st_size
        if options["dry_run"]:
            self.stdout.write(f"  would   {key}  {_size(size)}")
            return size

        with path.open("rb") as handle:
            stored = storage.save(key, File(handle))

        # file_overwrite is off, so a key that turned up between the check above
        # and the write would be stored under a suffix instead - and the
        # database row would still point at the name we meant to write. Better
        # to stop than to leave that mismatch behind.
        if stored != key:
            raise CommandError(
                f"{key} was stored as {stored}. Something else wrote to the "
                f"bucket during this run; re-run to pick up where it stopped."
            )

        self.stdout.write(f"  sent    {key}  {_size(size)}")
        return size


def _size(value):
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f} MB"
    return f"{value / 1024:.0f} KB"
