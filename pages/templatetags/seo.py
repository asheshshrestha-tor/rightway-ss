"""Template helpers for search-engine metadata."""

import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def ld_json(data):
    """Render a dict as a schema.org <script> block, or nothing if empty.

    `<`, `>` and `&` are escaped as unicode sequences. They are legal inside a
    JSON string but not inside an HTML <script>: a service description
    containing "</script>" would otherwise close the tag early and put the rest
    of the payload into the page as markup. Escaping keeps the JSON identical
    to a parser while making that impossible.
    """
    if not data:
        return ""

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    payload = (
        payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')
