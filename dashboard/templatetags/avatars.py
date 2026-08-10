"""Profile thumbnails, generated from the user's name.

There is no avatar upload in this project, and adding one would mean another
image field, another storage path and another thing to moderate. ui-avatars.com
renders initials on a coloured tile from a URL alone, which is enough for a
back office.

It is a third-party request made by the browser, so two things follow: the name
of a staff member is sent to that service, and the image will not load on a
machine with no internet access. Both are handled by keeping the initials
underneath as a fallback - see the `avatar` include.
"""

from urllib.parse import urlencode

from django import template

register = template.Library()

# The brand green, so a generated avatar sits with the rest of the dashboard
# rather than looking like a default.
BACKGROUND = "166534"
FOREGROUND = "ffffff"


def display_name(user):
    """What the avatar should spell out.

    Full name where we have one, so "Priya Kaur" gives PK rather than the PH of
    a username like "phandler".
    """
    full_name = (user.get_full_name() or "").strip()
    return full_name or user.get_username()


@register.simple_tag
def avatar_url(user, size=80):
    """A ui-avatars.com URL for this user.

    `size` is in pixels; pass double the rendered size so it stays sharp on a
    high-density screen.
    """
    query = urlencode(
        {
            "name": display_name(user),
            "size": size,
            "background": BACKGROUND,
            "color": FOREGROUND,
            "bold": "true",
            "format": "svg",
        }
    )
    return f"https://ui-avatars.com/api/?{query}"


@register.simple_tag
def avatar_initials(user):
    """The same initials the remote image would draw, for the fallback."""
    parts = [part for part in display_name(user).split() if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return (parts[0][:2] if parts else "?").upper()
