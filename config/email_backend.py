"""An email backend that sends everything to one address instead.

Testing a notification flow means submitting real-looking forms, and those
produce real emails: the office inbox, every member of staff who holds the
permission, and the address typed into the form. On a staging site that means
the client and their team receive test traffic, and a mistyped address means a
stranger does.

Setting EMAIL_REDIRECT_TO turns that off at the last moment before sending -
after the site has decided who *would* have received it, so what you are
testing is still the real routing. The intended recipients are put in the
subject line and at the top of the message, so you can check the addressing was
right without anyone being emailed.

Enabled by settings.py whenever EMAIL_REDIRECT_TO has a value. It wraps
whatever backend is configured, so it works with SMTP or the console.
"""

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend


class RedirectingEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.connection = get_connection(
            backend=settings.EMAIL_REDIRECT_WRAPPED_BACKEND,
            fail_silently=fail_silently,
            **kwargs,
        )

    def send_messages(self, email_messages):
        redirect_to = list(settings.EMAIL_REDIRECT_TO)
        if not redirect_to:  # pragma: no cover - settings.py would not enable us
            return self.connection.send_messages(email_messages)

        for message in email_messages:
            intended = ", ".join(message.to + message.cc + message.bcc)

            note = (
                "[Redirected email]\n"
                f"This would have been sent to: {intended}\n"
                f"Redirected because EMAIL_REDIRECT_TO is set.\n"
                f"{'-' * 60}\n\n"
            )
            message.body = note + message.body

            # The HTML part gets the same warning, or a redirected message read
            # in a normal client would look exactly like a real one.
            #
            # Django 5.2 made `alternatives` a list of objects with .content and
            # .mimetype; older versions used plain tuples. Rebuild each entry as
            # whatever type it already was, so this works either way.
            rebuilt = []
            for alternative in getattr(message, "alternatives", None) or []:
                if hasattr(alternative, "content"):
                    content, mimetype = alternative.content, alternative.mimetype
                    wrap = type(alternative)
                else:
                    content, mimetype = alternative
                    wrap = tuple

                if mimetype == "text/html":
                    content = _annotate_html(content, intended)
                rebuilt.append(
                    wrap((content, mimetype)) if wrap is tuple else wrap(content, mimetype)
                )
            message.alternatives = rebuilt

            message.subject = f"[TEST -> {intended}] {message.subject}"
            message.to = redirect_to
            message.cc = []
            message.bcc = []

        return self.connection.send_messages(email_messages)


def _annotate_html(html, intended):
    from django.utils.html import escape

    banner = (
        '<div style="background:#7f1d1d;color:#fff;padding:12px 16px;'
        'font-family:Arial,sans-serif;font-size:13px;">'
        "<strong>Redirected test email.</strong> This would have been sent to: "
        f"{escape(intended)}</div>"
    )
    # Prefer just inside <body>; fall back to prepending for any fragment that
    # does not have one.
    lowered = html.lower()
    index = lowered.find("<body")
    if index != -1:
        end = html.find(">", index)
        if end != -1:
            return html[: end + 1] + banner + html[end + 1 :]
    return banner + html
