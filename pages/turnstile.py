"""Cloudflare Turnstile - the half of the widget that actually protects anything.

The widget in the page produces a token and posts it as `cf-turnstile-response`.
On its own that proves nothing: anyone can skip the page and post whatever
string they like straight to the form endpoint. The token only means something
once Cloudflare has been asked about it, which is what `verify` does here, from
the server. It must never be done from the browser - that would leak the secret.

Three things are checked, not one:

  * `success`, that Cloudflare issued the token and it has not been used before
  * `action`, that the token came from the form being submitted rather than
    being harvested from a cheaper widget elsewhere on the site
  * `hostname`, that it was issued to this site rather than to an attacker's
    copy of the page running under the same sitekey

A token lasts 300 seconds and validates exactly once; a replay comes back as
`timeout-or-duplicate`.

Turnstile stays switched off until both keys are configured, so a fresh clone,
the test suite and local development all run without a Cloudflare account.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# The field the Turnstile script injects into the widget's container. It is not
# a declared form field - see `TurnstileFormMixin` in forms.py.
TOKEN_FIELD = "cf-turnstile-response"

# Cloudflare documents 2048 as the ceiling. Anything longer is not a token that
# could ever validate, so it is refused without spending a request on it.
MAX_TOKEN_LENGTH = 2048

# Generous for a single POST to an edge network, short enough that a visitor
# is not left watching a spinner if Cloudflare is unreachable.
VERIFY_TIMEOUT = 10

# Shown whenever verification does not come back clean. Deliberately the same
# words for every cause: a bot learns nothing from it, and a real person only
# needs to know to try again. The contact and consultation pages both carry the
# phone number beside the form, so there is always another way through.
FAILURE_MESSAGE = (
    "We could not confirm you are human. Please complete the check and try "
    "again, or call us if the problem continues."
)


@dataclass(frozen=True)
class Result:
    """The outcome of one siteverify call."""

    ok: bool
    error_codes: tuple = ()
    hostname: str = ""
    action: str = ""

    #: Why this failed, for the log. Never shown to the visitor.
    reason: str = ""


def is_enabled():
    """True once both keys are configured.

    Both, not either: a sitekey with no secret renders a widget whose token
    nothing checks, which is worse than no widget at all because it looks like
    protection.
    """
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def client_ip(request):
    """The visitor's address, as `remoteip` and the rate limiter both need it.

    CF-Connecting-IP is written by Cloudflare itself and cannot be forged by a
    client whose traffic actually passes through it, so it is preferred over
    X-Forwarded-For, which is a client-supplied list that anything upstream can
    append to. REMOTE_ADDR is the fallback for local development and for direct
    requests that never touched the edge.
    """
    cloudflare_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cloudflare_ip:
        return cloudflare_ip.strip()
    return request.META.get("REMOTE_ADDR", "").strip()


def allowed_hostnames():
    """Hostnames a token may have been issued to.

    Defaults to ALLOWED_HOSTS with the wildcards dropped, because those are
    already the names this site answers to. An empty result - which is what a
    local `ALLOWED_HOSTS=127.0.0.1,localhost` with no public name gives, or a
    bare `*` - turns the check off rather than rejecting everything.
    """
    configured = getattr(settings, "TURNSTILE_ALLOWED_HOSTNAMES", None)
    if configured:
        return {host.strip().lower() for host in configured if host.strip()}
    return {
        host.strip().lower()
        for host in settings.ALLOWED_HOSTS
        if host.strip() and "*" not in host
    }


def verify(token, *, action=None, remoteip=None, idempotency_key=None):
    """Ask Cloudflare about `token`. Returns a `Result`; never raises.

    `action` is the value the widget was rendered with. Passing it is what
    stops a token minted by one form being spent on another.
    """
    token = (token or "").strip()

    if not token:
        # No widget token in the POST at all: either the script never ran, or
        # the request never came from the page.
        return Result(ok=False, error_codes=("missing-input-response",),
                      reason="no token in the submission")

    if len(token) > MAX_TOKEN_LENGTH:
        return Result(ok=False, error_codes=("invalid-input-response",),
                      reason="token longer than %d characters" % MAX_TOKEN_LENGTH)

    payload = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remoteip:
        payload["remoteip"] = remoteip
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    try:
        data = _post(payload)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # Fail closed. Letting a submission through unverified because the
        # check itself broke hands anyone who can disrupt that call a way past
        # it entirely, so the visitor is asked to retry instead.
        logger.error("Turnstile siteverify unreachable: %s", exc)
        return Result(ok=False, error_codes=("internal-error",),
                      reason="siteverify unreachable: %s" % exc)

    error_codes = tuple(data.get("error-codes") or ())
    returned_action = data.get("action") or ""
    hostname = (data.get("hostname") or "").lower()

    if not data.get("success"):
        return Result(ok=False, error_codes=error_codes, hostname=hostname,
                      action=returned_action,
                      reason="siteverify rejected the token")

    if action and returned_action != action:
        return Result(ok=False, error_codes=error_codes, hostname=hostname,
                      action=returned_action,
                      reason="action was %r, expected %r" % (returned_action, action))

    permitted = allowed_hostnames()
    if permitted and hostname not in permitted:
        return Result(ok=False, error_codes=error_codes, hostname=hostname,
                      action=returned_action,
                      reason="hostname %r is not one of ours" % hostname)

    return Result(ok=True, hostname=hostname, action=returned_action)


def _post(payload):
    """POST to siteverify and return the decoded JSON body."""
    body = urllib.parse.urlencode(payload).encode()
    request = urllib.request.Request(
        SITEVERIFY_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=VERIFY_TIMEOUT) as response:
        return json.loads(response.read().decode())
