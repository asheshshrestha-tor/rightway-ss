"""Dashboard navigation.

Built per-request so links the user cannot use are never rendered, and so the
active rail icon / menu item can be derived from `request.path` rather than
every template having to declare which section it belongs to.
"""

from django.urls import reverse

# (key, label, rail icon, [(label, url name, menu icon, required permission)])
NAV = [
    (
        "overview",
        "Overview",
        "ki-element-11",
        [("Dashboard", "dashboard:index", "ki-chart-simple", None)],
    ),
    (
        "enquiries",
        "Enquiries",
        "ki-sms",
        [
            (
                "Consultations",
                "dashboard:consultation_list",
                "ki-calendar-tick",
                "pages.view_consultation",
            ),
            (
                "All Enquiries",
                "dashboard:enquiry_list",
                "ki-message-text-2",
                "pages.view_enquiry",
            ),
        ],
    ),
    (
        "content",
        "Website Content",
        "ki-abstract-26",
        [
            ("Services", "dashboard:service_list", "ki-briefcase", "pages.view_service"),
            ("Vacancies", "dashboard:vacancy_list", "ki-note-2", "pages.view_vacancy"),
            ("Team", "dashboard:team_list", "ki-people", "pages.view_teammember"),
        ],
    ),
    (
        "careers",
        "Recruitment",
        "ki-people",
        [
            (
                "Applications",
                "dashboard:application_list",
                "ki-document",
                "pages.view_application",
            )
        ],
    ),
    (
        "settings",
        "Settings",
        "ki-setting-2",
        [
            (
                "Site Settings",
                "dashboard:site_settings",
                "ki-gear",
                "pages.change_sitesettings",
            )
        ],
    ),
    (
        "access",
        "Access Control",
        "ki-shield-tick",
        [
            ("Users", "dashboard:user_list", "ki-profile-circle", "auth.view_user"),
            ("Roles", "dashboard:group_list", "ki-security-user", "auth.view_group"),
        ],
    ),
]


def build(request):
    """Return (nav_items, active_section_label) for this request."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return [], ""

    path = request.path
    items = []
    # Account screens live in the avatar menu rather than the sidebar, so name
    # them explicitly instead of falling back to the first section.
    active_label = "My Account" if path.startswith("/dashboard/account/") else "Overview"

    for key, label, icon, links in NAV:
        visible = []
        for link_label, url_name, link_icon, perm in links:
            if perm and not user.has_perm(perm):
                continue
            visible.append(
                {"label": link_label, "url": reverse(url_name), "icon": link_icon}
            )
        if not visible:
            continue

        # A section is active when the current path sits under any of its links.
        # Compared on the path prefix so /users/3/edit/ still lights up "Users".
        active = any(
            path == link["url"] or path.startswith(link["url"])
            for link in visible
            if link["url"] != "/dashboard/"
        ) or (path == reverse("dashboard:index") and key == "overview")

        if active:
            active_label = label

        items.append(
            {"key": key, "label": label, "icon": icon, "links": visible, "active": active}
        )

    return items, active_label


def context(request):
    """Template context processor."""
    if not request.path.startswith("/dashboard/"):
        return {}
    items, label = build(request)
    return {"nav_items": items, "nav_section_label": label}
