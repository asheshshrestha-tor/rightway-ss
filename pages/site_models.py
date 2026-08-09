"""Site-wide settings: the bits of the site that are neither a page nor a list.

Logo, favicon, contact details, footer blurb, map and social links used to be
hardcoded in `pages.content` and in static files. They are the things most
likely to change - a new phone number, a rebrand, a new Instagram account - and
the least likely to warrant a developer, so they live here.

There is exactly one settings row. `SiteSettings.load()` is the only way it
should be read.
"""

from urllib.parse import quote_plus

from django.db import models
from django.templatetags.static import static

# Matches the ids in templates/partials/icon_sprite.html, so an editor can only
# pick a platform the site can actually draw.
SOCIAL_PLATFORMS = [
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("linkedin", "LinkedIn"),
    ("x", "X (Twitter)"),
    ("youtube", "YouTube"),
    ("whatsapp", "WhatsApp"),
]


def australian_tel_href(phone):
    """Turn a displayed number into a `tel:` link.

    "0470 522 587" -> "tel:+61470522587". Derived rather than stored, so an
    editor cannot update one and forget the other.
    """
    digits = "".join(character for character in phone if character.isdigit() or character == "+")
    if not digits:
        return ""
    if digits.startswith("+"):
        return f"tel:{digits}"
    if digits.startswith("0"):
        return f"tel:+61{digits[1:]}"
    return f"tel:{digits}"


class SiteSettings(models.Model):
    """Singleton. Read it with `SiteSettings.load()`."""

    # --- identity ---
    name = models.CharField(max_length=140, default="Rightway Support Services")
    tagline = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short line under the name, e.g. “Your Path, Our Support”.",
    )

    logo = models.ImageField(
        upload_to="branding/",
        blank=True,
        help_text="Used in the site header. Wide, transparent PNG works best.",
    )
    logo_light = models.ImageField(
        "Logo (light version)",
        upload_to="branding/",
        blank=True,
        help_text="White version, used on the dark footer. Falls back to the main logo.",
    )
    favicon = models.ImageField(
        upload_to="branding/",
        blank=True,
        help_text="Browser tab icon for the website and the dashboard. Square PNG, 180x180 or larger.",
    )

    # --- footer ---
    footer_description = models.TextField(
        blank=True,
        help_text="The paragraph under the logo in the footer.",
    )

    # --- contact ---
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True, help_text="Where enquiries and applications are sent.")
    address = models.CharField(max_length=200, blank=True)
    hours = models.CharField(
        "Office hours",
        max_length=140,
        blank=True,
        help_text="e.g. “Mon - Fri, 8:00 AM - 5:00 PM”.",
    )
    abn = models.CharField("ABN", max_length=20, blank=True)

    # --- map ---
    map_address = models.CharField(
        max_length=250,
        blank=True,
        help_text="What the map should search for. Falls back to the address above.",
    )
    map_embed_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional. Paste a Google Maps embed URL to pin an exact spot instead.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Force every write onto row 1.

        Pinning the pk is not enough on its own: Django INSERTs when an
        instance is new, even with a pk set, so `SiteSettings.objects.create()`
        would hit the unique constraint. Marking the instance as no longer
        "adding" turns that into an UPDATE of the existing row.
        """
        self.pk = 1
        if type(self).objects.filter(pk=1).exists():
            self._state.adding = False
            kwargs.pop("force_insert", None)
            args = tuple(arg for arg in args if arg is not True)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - guarded, not used
        raise RuntimeError("Site settings cannot be deleted.")

    @classmethod
    def load(cls):
        """The settings row, creating it on first use.

        Never returns None, so templates and email helpers can rely on it.
        """
        settings_row = cls.objects.filter(pk=1).first()
        if settings_row is None:
            settings_row = cls.objects.create(pk=1)
        return settings_row

    # ----------------------------------------------------------- derived

    @property
    def phone_href(self):
        return australian_tel_href(self.phone)

    @property
    def logo_url(self):
        return self.logo.url if self.logo else static("images/logo.png")

    @property
    def logo_light_url(self):
        """White logo for the navy footer, falling back to the colour one."""
        if self.logo_light:
            return self.logo_light.url
        if self.logo:
            return self.logo.url
        return static("images/logo-light.png")

    @property
    def favicon_url(self):
        return self.favicon.url if self.favicon else static("images/favicon-32.png")

    @property
    def apple_icon_url(self):
        return self.favicon.url if self.favicon else static("images/favicon-180.png")

    @property
    def map_query(self):
        """URL-encoded search term for the Google Maps embed."""
        return quote_plus(self.map_address or self.address or "")

    @property
    def map_url(self):
        """The full src for the map iframe."""
        if self.map_embed_url:
            return self.map_embed_url
        return f"https://www.google.com/maps?q={self.map_query}&output=embed"

    @property
    def initials(self):
        """Two-letter mark used by the dashboard's narrow sidebar."""
        parts = [part for part in self.name.split() if part]
        return "".join(part[0] for part in parts[:2]).upper() or "RS"


class SocialLinkQuerySet(models.QuerySet):
    def published(self):
        """Every ticked row, with or without a URL.

        An icon with no link yet still shows - see `SocialLink.href`.
        """
        return self.filter(is_published=True)


class SocialLink(models.Model):
    """One entry in the footer's "Follow Us" row."""

    platform = models.CharField(max_length=30, choices=SOCIAL_PLATFORMS)
    url = models.URLField(
        max_length=300,
        blank=True,
        help_text=(
            "Optional. Leave empty and the icon still shows, linking to “#” "
            "until you have the address."
        ),
    )
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers first.")

    objects = SocialLinkQuerySet.as_manager()

    class Meta:
        ordering = ["order", "platform"]

    def __str__(self):
        return f"{self.get_platform_display()} - {self.url}"

    @property
    def label(self):
        return self.get_platform_display()

    @property
    def icon(self):
        """Sprite id. Matches `platform` by design - see SOCIAL_PLATFORMS."""
        return self.platform

    @property
    def href(self):
        """Where the icon points.

        "#" rather than an empty href when no address has been set: an empty
        href resolves to the current page, so browsers and crawlers treat it as
        a real self-link.
        """
        return self.url or "#"

    @property
    def has_link(self):
        return bool(self.url)
