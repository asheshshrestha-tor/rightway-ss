"""Careers: open positions and the applications made against them.

Kept in its own module and imported into `models` so `pages/models.py` stays
readable now that the app carries several models.
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class PrivateMediaStorage(FileSystemStorage):
    """Storage for files that must never be served by URL.

    Resumes contain personal information, so they live outside MEDIA_ROOT and
    are therefore unreachable over MEDIA_URL. The only way to read one is
    `dashboard.careers_views.application_resume`, which checks permissions.

    The location is resolved on access rather than at import, for two reasons:
    passing `location=settings.PRIVATE_MEDIA_ROOT` to `__init__` would bake an
    absolute path into the migration file (breaking every other machine), and
    it would ignore `override_settings` in tests.
    """

    def __init__(self, *args, **kwargs):
        kwargs.pop("location", None)
        super().__init__(*args, **kwargs)

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def deconstruct(self):
        """Serialise as a bare class reference - no captured path."""
        return ("pages.vacancy_models.PrivateMediaStorage", [], {})


private_storage = PrivateMediaStorage()


class VacancyQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def open_now(self):
        today = timezone.localdate()
        return self.published().filter(
            models.Q(closing_date__isnull=True) | models.Q(closing_date__gte=today)
        )


class Vacancy(models.Model):
    """An open position, editable from the staff dashboard."""

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CASUAL = "casual", "Casual"
        CONTRACT = "contract", "Contract"
        CASUAL_PART_TIME = "casual_part_time", "Casual & part-time"

    title = models.CharField(max_length=140)
    slug = models.SlugField(
        max_length=160,
        unique=True,
        blank=True,
        help_text="URL for this vacancy. Left blank, it is built from the title.",
    )
    employment_type = models.CharField(
        max_length=30,
        choices=EmploymentType.choices,
        default=EmploymentType.CASUAL,
    )
    location = models.CharField(max_length=140, default="Toowoomba, QLD")
    summary = models.CharField(
        max_length=250, help_text="One line, shown in the vacancy list."
    )
    description = models.TextField(help_text="The main body of the advert.")
    responsibilities = models.TextField(
        blank=True, help_text="One per line. Shown as a tick list."
    )
    requirements = models.TextField(
        blank=True, help_text="One per line. Shown as a tick list."
    )
    salary_range = models.CharField(
        max_length=140,
        blank=True,
        help_text="Optional, e.g. “$35 - $45 per hour”.",
    )
    closing_date = models.DateField(
        null=True,
        blank=True,
        help_text="Optional. After this date the advert stops accepting applications.",
    )
    is_published = models.BooleanField(
        default=True, help_text="Unpublished vacancies are hidden from the website."
    )
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers first.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VacancyQuerySet.as_manager()

    class Meta:
        ordering = ["order", "title"]
        verbose_name_plural = "vacancies"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title)[:150] or "vacancy"
        slug = base
        suffix = 2
        taken = Vacancy.objects.exclude(pk=self.pk)
        while taken.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def get_absolute_url(self):
        return reverse("vacancy_detail", kwargs={"slug": self.slug})

    @property
    def is_closed(self):
        return bool(self.closing_date and self.closing_date < timezone.localdate())

    @property
    def accepts_applications(self):
        return self.is_published and not self.is_closed

    @property
    def responsibility_list(self):
        return [line.strip() for line in self.responsibilities.splitlines() if line.strip()]

    @property
    def requirement_list(self):
        return [line.strip() for line in self.requirements.splitlines() if line.strip()]

    @property
    def detail_line(self):
        """e.g. "Casual & part-time · Toowoomba, QLD" - the old list format."""
        return f"{self.get_employment_type_display()} · {self.location}"


def resume_path(instance, filename):
    """Namespace uploads by vacancy so the private folder stays navigable."""
    bucket = instance.vacancy.slug if instance.vacancy else "speculative"
    return f"resumes/{bucket}/{filename}"


class Application(models.Model):
    """Someone applying for a vacancy, or sending a speculative resume."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        SHORTLISTED = "shortlisted", "Shortlisted"
        INTERVIEWING = "interviewing", "Interviewing"
        UNSUCCESSFUL = "unsuccessful", "Unsuccessful"
        HIRED = "hired", "Hired"

    vacancy = models.ForeignKey(
        Vacancy,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications",
        help_text="Empty for a speculative application.",
    )
    # The advertised title is copied in so the record still reads correctly if
    # the vacancy is later renamed or deleted.
    vacancy_title = models.CharField(max_length=140, blank=True)

    full_name = models.CharField(max_length=140)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to=resume_path, storage=private_storage)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    handled_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.role_label}"

    def save(self, *args, **kwargs):
        if self.vacancy and not self.vacancy_title:
            self.vacancy_title = self.vacancy.title
        super().save(*args, **kwargs)

    @property
    def role_label(self):
        return self.vacancy_title or "Speculative application"

    @property
    def resume_name(self):
        """Just the filename, for display and the download's Content-Disposition."""
        import os

        return os.path.basename(self.resume.name) if self.resume else ""

    @property
    def status_css(self):
        """Metronic badge modifier. Remember demo29 inverts the palette:
        --bs-primary is green and --bs-success is blue."""
        return {
            self.Status.NEW: "warning",
            self.Status.SHORTLISTED: "success",
            self.Status.INTERVIEWING: "info",
            self.Status.UNSUCCESSFUL: "danger",
            self.Status.HIRED: "primary",
        }[self.status]
