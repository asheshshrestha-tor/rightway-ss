"""The "Meet Our Team" section on the About page.

Replaces what used to be a hardcoded list in `pages.content`, so staff can add
and reorder people themselves. Each member also gets a profile page: for a
disability support provider, who will actually be supporting you is a real
part of the decision, so bios and qualifications are worth surfacing.
"""

from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify


class TeamMemberQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class TeamMember(models.Model):
    name = models.CharField(max_length=140)
    slug = models.SlugField(
        max_length=160,
        unique=True,
        blank=True,
        help_text="URL for this profile. Left blank, it is built from the name.",
    )
    role = models.CharField(max_length=140, help_text="For example: Support Coordinator")
    photo = models.ImageField(
        upload_to="team/",
        blank=True,
        help_text="Square works best. A placeholder is used when empty.",
    )
    bio = models.TextField(
        blank=True,
        help_text="A short introduction, shown on this person's own page.",
    )
    qualifications = models.TextField(
        blank=True, help_text="One per line. Shown as a tick list."
    )
    is_published = models.BooleanField(
        default=True, help_text="Unpublished people are hidden from the website."
    )
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers first.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TeamMemberQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "team member"

    def __str__(self):
        return f"{self.name} - {self.role}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.name)[:150] or "team-member"
        slug = base
        suffix = 2
        taken = TeamMember.objects.exclude(pk=self.pk)
        while taken.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def get_absolute_url(self):
        return reverse("team_member", kwargs={"slug": self.slug})

    @property
    def qualification_list(self):
        return [line.strip() for line in self.qualifications.splitlines() if line.strip()]

    @property
    def photo_url(self):
        """Uploaded photo, else the placeholder shipped for this slug, else the
        generic one - so someone added by an administrator always renders."""
        if self.photo:
            return self.photo.url

        # Imported lazily: pages.models owns the cached static-file lookup.
        from .models import _static_exists

        specific = f"images/team-{self.slug}.svg"
        if _static_exists(specific):
            return static(specific)
        return static("images/team-placeholder.svg")

    @property
    def has_uploaded_photo(self):
        return bool(self.photo)

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"
