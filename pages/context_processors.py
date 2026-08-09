"""Expose site-wide content to every template (header, footer, nav menus)."""

from .models import Service, SiteSettings, SocialLink


def site(request):
    settings_row = SiteSettings.load()

    # The dashboard has its own chrome and never renders the public nav or
    # footer, so skip the service and social queries for those requests.
    if request.path.startswith("/dashboard/"):
        return {"site": settings_row}

    published = Service.objects.published()
    return {
        "site": settings_row,
        "nav_services": published,
        "footer_services": published.filter(show_in_footer=True),
        "social_links": SocialLink.objects.published(),
    }
