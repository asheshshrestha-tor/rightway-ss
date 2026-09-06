"""Shrink uploaded images before they reach storage.

Editors upload whatever the camera or the designer handed them. The service
photos that shipped with this project are 2.2 MB PNGs at 1402x1122, rendered by
the templates in a card roughly 450 px wide - about 25x more data than the page
can use.

On a local disk that waste was invisible. On object storage it is paid twice:
once for storage, and again in egress on every page view, which is the larger
of the two and the one that grows with traffic. So every upload is capped to
the dimensions its template actually renders and re-encoded to WebP, which
takes those 2.2 MB PNGs to roughly 90 KB with no visible difference.

Nothing here validates an upload. A file Pillow cannot read is passed through
untouched so that `ImageField`'s own check reports it as a form error, rather
than this module raising a 500 first.
"""

import io
from pathlib import Path
from typing import NamedTuple

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError


class ImageSpec(NamedTuple):
    """How one field's uploads should be stored.

    `max_width`/`max_height` are a bounding box, not a target: an image is
    scaled down to fit inside it and is never enlarged or cropped.
    """

    max_width: int
    max_height: int
    image_format: str = "WEBP"


# One definition per field, shared by the model `save()` hooks and the
# `optimize_images` command so the two can never drift apart. The numbers come
# from the widths the templates actually render, doubled for high-density
# screens.
SERVICE_IMAGE = ImageSpec(1200, 900)
TEAM_PHOTO = ImageSpec(800, 800)
LOGO = ImageSpec(600, 200)
# Kept as PNG: it is a few KB either way, and `rel="icon"` is the one place
# where the older-browser story is not worth the bytes saved.
FAVICON = ImageSpec(180, 180, image_format="PNG")

# Quality for photographic content. 82 is the usual point where WebP stops
# being visibly distinguishable from the source at display size.
WEBP_QUALITY = 82

# Logos and other flat artwork are encoded losslessly, so text edges stay
# crisp. Photographs that happen to carry an alpha channel would balloon under
# that, so anything past this size is re-encoded lossy instead.
LOSSLESS_MAX_BYTES = 256 * 1024

EXTENSIONS = {"WEBP": ".webp", "PNG": ".png"}


def pending_upload(field_file):
    """The freshly uploaded file sitting on this field, or None.

    `_committed` is False only between a form assigning an upload and
    `FileField.pre_save` writing it to storage - exactly the window we want to
    act in. Testing it before touching `.file` matters: reading that attribute
    on a committed field would pull the object back out of S3 on every
    unrelated save.
    """
    if not field_file or getattr(field_file, "_committed", True):
        return None
    upload = field_file.file
    return upload if isinstance(upload, UploadedFile) else None


def storage_name(original_name, spec):
    """A safe object key for `original_name` re-encoded under `spec`.

    The stem is slugified as well as re-extensioned. Uploads arrive named
    things like `Reliable transport to appointments & everyday commitments..png`,
    which is awkward in a URL and worse as an S3 key, where spaces and
    non-ASCII have to be percent-encoded by every consumer.
    """
    stem = slugify(Path(original_name).stem)[:80] or "image"
    return f"{stem}{EXTENSIONS[spec.image_format]}"


def encode(source, spec):
    """Re-encode `source` to `spec`, or None if it should be left alone.

    None means "store what was uploaded": the file is not an image Pillow can
    read, it is animated, or it is already smaller than anything we would
    produce. `source` is left rewound either way, so the caller can still hand
    the original to storage.
    """
    try:
        source.seek(0)
        image = Image.open(source)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        _rewind(source)
        return None

    # Flattening an animated GIF or WebP to its first frame is a worse outcome
    # than storing it as sent.
    if getattr(image, "n_frames", 1) > 1:
        _rewind(source)
        return None

    # Already the target format, already within bounds. Re-encoding would only
    # spend another generation of lossy quality to save nothing, so this is
    # what makes `optimize_images` safe to run more than once. Checked before
    # `exif_transpose`, which returns a new image with no `format`.
    if (
        image.format == spec.image_format
        and image.width <= spec.max_width
        and image.height <= spec.max_height
    ):
        _rewind(source)
        return None

    # Honours the orientation a phone camera records in EXIF, and drops the tag
    # so nothing rotates it a second time.
    image = ImageOps.exif_transpose(image)

    if spec.image_format == "PNG":
        payload = _encode_png(image, spec)
    else:
        payload = _encode_webp(image, spec)

    _rewind(source)

    # Re-encoding an already-optimised file can come out larger. Keeping the
    # smaller of the two is the whole point of the exercise.
    original_size = getattr(source, "size", None)
    if original_size is not None and len(payload) >= original_size:
        return None
    return payload


def optimize_field(instance, field_name, spec):
    """Re-encode a pending upload on `instance.<field_name>` in place.

    Called from the model's `save()` before the field is written to storage.
    Assigning the replacement back onto the field leaves it uncommitted, so
    Django's own `FileField.pre_save` still routes it through `upload_to` and
    the field's storage - this only changes the bytes and the name.

    Returns True when the upload was replaced, so callers can log it.
    """
    upload = pending_upload(getattr(instance, field_name))
    if upload is None:
        return False

    payload = encode(upload, spec)
    if payload is None:
        return False

    name = storage_name(upload.name, spec)
    setattr(instance, field_name, ContentFile(payload, name=name))
    return True


def _encode_webp(image, spec):
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    image = image.convert("RGBA" if has_alpha else "RGB")
    image = _fit(image, spec)

    if has_alpha:
        payload = _save(image, "WEBP", lossless=True, method=6)
        if len(payload) <= LOSSLESS_MAX_BYTES:
            return payload
        # A photograph with an alpha channel. Lossless is the wrong tool.
        return _save(image, "WEBP", quality=85, method=6)

    return _save(image, "WEBP", quality=WEBP_QUALITY, method=6)


def _encode_png(image, spec):
    if image.mode not in ("RGB", "RGBA", "P", "L"):
        image = image.convert("RGBA")
    return _save(_fit(image, spec), "PNG", optimize=True)


def _fit(image, spec):
    """Scale down to fit `spec`'s box. `thumbnail` never enlarges."""
    image.thumbnail((spec.max_width, spec.max_height), Image.LANCZOS)
    return image


def _save(image, image_format, **options):
    buffer = io.BytesIO()
    # An empty `exif` drops whatever the source carried - camera model, and on
    # a phone photo the GPS coordinates it was taken at, which have no business
    # being published on a team page.
    image.save(buffer, format=image_format, exif=b"", **options)
    return buffer.getvalue()


def _rewind(source):
    try:
        source.seek(0)
    except (OSError, ValueError):  # pragma: no cover - closed or non-seekable
        pass
