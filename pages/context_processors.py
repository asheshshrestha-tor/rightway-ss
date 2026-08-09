"""Expose site-wide content to every template (header, footer, nav menus)."""

from . import structured_data
from .models import Service, SiteSettings, SocialLink


def site(request):
    settings_row = SiteSettings.load()

    # The dashboard has its own chrome and never renders the public nav or
    # footer, so skip the service and social queries for those requests.
    if request.path.startswith("/dashboard/"):
        return {"site": settings_row}

    published = Service.objects.published()
    social = SocialLink.objects.published()

    # Handed to the LocalBusiness block as `sameAs`, which is how a search
    # engine ties the site to its social profiles.
    settings_row._social_links = social

    return {
        "site": settings_row,
        "nav_services": published,
        "footer_services": published.filter(show_in_footer=True),
        "social_links": social,
        # The address of this page with no query string, so that /services/ and
        # /services/?utm_source=... are not treated as two competing pages.
        "canonical_url": request.build_absolute_uri(request.path),
        "organization_schema": structured_data.organization(request, settings_row),
    }
