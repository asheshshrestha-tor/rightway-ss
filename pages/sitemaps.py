"""Sitemaps for the public site.

Search engines find pages by following links, which works but is slow and
misses anything lightly linked. A sitemap lists every public URL directly,
with a last-modified date so a crawler can tell what has actually changed.

Only public, indexable pages belong here. The dashboard, the thank-you page
and the speculative application form are deliberately absent - listing a page
in a sitemap while telling robots not to index it is a contradiction that
Search Console reports as an error.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from .models import Service, TeamMember, Vacancy


class StaticViewSitemap(Sitemap):
    """The fixed pages, which have no database row to date-stamp."""

    protocol = "https"
    changefreq = "monthly"

    # Priority is relative and only orders this site against itself. The home
    # page and the pages that win enquiries rank above the legal boilerplate.
    PRIORITIES = {
        "home": 1.0,
        "services": 0.9,
        "consultation": 0.9,
        "contact": 0.8,
        "ndis_support": 0.8,
        "about": 0.7,
        "careers": 0.7,
        "faq": 0.6,
        "privacy_policy": 0.2,
        "terms": 0.2,
    }

    def items(self):
        return list(self.PRIORITIES)

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PRIORITIES[item]


class ServiceSitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Service.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class VacancySitemap(Sitemap):
    """Open roles only.

    A closed vacancy still resolves, so nothing breaks, but advertising an
    expired job to a crawler earns the site nothing.
    """

    protocol = "https"
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Vacancy.objects.filter(is_published=True).exclude(
            closing_date__lt=timezone.localdate()
        )

    def lastmod(self, obj):
        return obj.updated_at


class TeamMemberSitemap(Sitemap):
    protocol = "https"
    changefreq = "yearly"
    priority = 0.4

    def items(self):
        return TeamMember.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "services": ServiceSitemap,
    "vacancies": VacancySitemap,
    "team": TeamMemberSitemap,
}
