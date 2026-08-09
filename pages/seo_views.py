"""robots.txt.

Served from a view rather than a static file so the sitemap line carries the
domain the site is actually being served from - which differs between the
Railway URL and the final custom domain, and would go stale if hard-coded.
"""

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_control


@cache_control(max_age=60 * 60 * 24)
def robots_txt(request):
    sitemap_url = request.build_absolute_uri(
        reverse("django.contrib.sitemaps.views.sitemap")
    )

    lines = [
        "User-agent: *",
        # The back office. Nothing here is useful in a search result, and the
        # login page appearing in one only invites attention.
        "Disallow: /dashboard/",
        "Disallow: /admin/",
        # A confirmation page is meaningless without the booking that precedes
        # it, and would otherwise surface as a dead-end result.
        "Disallow: /book-a-consultation/thank-you/",
        "",
        f"Sitemap: {sitemap_url}",
    ]

    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
