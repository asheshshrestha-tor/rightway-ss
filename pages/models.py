from functools import lru_cache

from django.contrib.staticfiles import finders
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify


# Careers and consultation models live in their own modules for readability;
# re-exported here so `from pages.models import Vacancy` keeps working like any
# other model.
from .consultation_models import Consultation  # noqa: E402,F401
from .site_models import SiteSettings, SocialLink  # noqa: E402,F401
from .team_models import TeamMember  # noqa: E402,F401
from .vacancy_models import Application, Vacancy  # noqa: E402,F401


@lru_cache(maxsize=256)
def _static_exists(path):
    """Whether a static file is present. Cached - this is hit per card render."""
    return finders.find(path) is not None

# Icons available in templates/partials/icon_sprite.html. Offered as choices so
# an editor picks from what actually exists rather than typing an id that
# silently renders nothing.
SERVICE_ICONS = [
    ("personal-care", "Personal care (person)"),
    ("household", "Household (house)"),
    ("community-access", "Community access (people)"),
    ("shared-living", "Shared living (house + heart)"),
    ("transport", "Transport (vehicle)"),
    ("hands-heart", "Hands and heart"),
    ("person-heart", "Person and heart"),
    ("hand-heart", "Supporting hand"),
    ("heart", "Heart"),
    ("shield-check", "Shield"),
    ("sprout", "Sprout"),
    ("star", "Star"),
    ("growth", "Growth"),
    ("calendar-check", "Calendar"),
    ("clock-flex", "Clock"),
    ("check-badge", "Check badge"),
]


class ServiceQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def for_footer(self):
        return self.published().filter(show_in_footer=True)


class Service(models.Model):
    """A support service, editable from the staff dashboard.

    Replaces what used to be a hardcoded list in `pages.content`, so the public
    site's service cards, nav menu, footer column and detail pages all come
    from one place an administrator controls.
    """

    title = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=140,
        unique=True,
        blank=True,
        help_text="URL for the detail page. Left blank, it is built from the title.",
    )
    summary = models.CharField(
        max_length=200,
        help_text="One line, shown on the home page card.",
    )
    description = models.TextField(
        help_text="A sentence or two, shown on the services listing card.",
    )
    body = models.TextField(
        blank=True,
        help_text="The full description shown on the service's own page.",
    )
    highlights = models.TextField(
        blank=True,
        help_text="What's included - one item per line. Shown as a tick list.",
    )
    icon = models.CharField(
        max_length=40, choices=SERVICE_ICONS, default="personal-care"
    )
    image = models.ImageField(
        upload_to="services/",
        blank=True,
        help_text="Roughly 900x700. A placeholder is used when empty.",
    )
    is_published = models.BooleanField(
        default=True, help_text="Unpublished services are hidden from the website."
    )
    show_in_footer = models.BooleanField(
        default=True, help_text="Include in the footer's 'Our Services' column."
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers appear first."
    )
    meta_description = models.CharField(
        max_length=300,
        blank=True,
        help_text="Search-engine description. Falls back to the summary.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceQuerySet.as_manager()

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title)[:130] or "service"
        slug = base
        suffix = 2
        taken = Service.objects.exclude(pk=self.pk)
        while taken.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def get_absolute_url(self):
        return reverse("service_detail", kwargs={"slug": self.slug})

    @property
    def highlight_list(self):
        """`highlights` split into lines, blanks dropped."""
        return [line.strip() for line in self.highlights.splitlines() if line.strip()]

    @property
    def image_url(self):
        """Uploaded image, else the placeholder shipped for this slug, else the
        generic one - so a service added by an administrator always renders."""
        if self.image:
            return self.image.url
        specific = f"images/service-{self.slug}.svg"
        if _static_exists(specific):
            return static(specific)
        return static("images/service-placeholder.svg")

    @property
    def has_uploaded_image(self):
        return bool(self.image)


class Enquiry(models.Model):
    """A message submitted through the public contact form.

    Enquiries are stored as well as emailed, so nothing is lost if mail
    delivery fails and so the dashboard has something real to report on.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"
        # Tripped the contact form's honeypot. Quarantined rather than
        # discarded, because the trap can misfire on a real person.
        SPAM = "spam", "Suspected spam"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    handled_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enquiries",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def status_css(self):
        """Metronic badge modifier for this status.

        Note demo29 inverts the usual Bootstrap palette: --bs-primary is green
        (#17C653) and --bs-success is blue (#1B84FF). So "closed" maps to
        primary to read as done, and "in progress" to success to read as active.
        """
        return {
            self.Status.NEW: "warning",
            self.Status.IN_PROGRESS: "success",
            self.Status.CLOSED: "primary",
            self.Status.SPAM: "danger",
        }[self.status]
