"""Per-visitor submission limits for the three public forms.

Three accepted submissions per day, counted against the visitor's IP address
and against the email address they gave. Either bucket filling up blocks the
next one until the window expires.

The quota is **per form**. Three enquiries, three consultation requests and
three job applications, each counted separately - not three submissions in
total. Someone applying for three advertised roles and then asking a question
about a fourth is doing something ordinary, and a shared counter would stop
them.

Two deliberate choices about what counts:

  * Only submissions that passed validation. Someone who mistypes their email
    four times has not used up their allowance - the form has to be usable by
    people who are not concentrating.
  * Spam does count. A tripped honeypot burns quota exactly like a real
    message, so repeatedly hitting the trap cannot be used to hammer the
    endpoint for free.

Turnstile is the front line against bots; this is the backstop that bounds the
damage when something gets past it, and the thing that stops one upset person
sending the office forty messages in an afternoon.
"""

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# What the client asked for: three a day, per email or per IP.
SUBMISSION_LIMIT = 3
SUBMISSION_WINDOW = 60 * 60 * 24  # one day, in seconds

# Scopes. One per public form, so the three quotas are independent.
CONTACT = "contact"
CONSULTATION = "consultation"
APPLICATION = "application"

# Shown whenever either bucket is full. It does not say which one, because
# telling someone "your address is blocked but another would work" is an
# instruction, and the honest version - "your network is blocked" - is not
# something the person on the other end can act on either.
LIMIT_MESSAGE = (
    "Thanks - we have already received a few messages from you today. Please "
    "call us on %s if it is urgent, and we will pick it up straight away."
)


def _key(scope, kind, value):
    """A cache key for one bucket.

    The value is hashed rather than stored: these keys live in the
    `django_cache` table, and an enquirer's email address sitting in a second
    table, outside the model that has a retention story, is personal
    information nobody asked to keep twice. A digest counts just as well.
    """
    digest = hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]
    return f"ratelimit:{scope}:{kind}:{digest}"


def _buckets(scope, *, ip=None, email=None):
    """The keys to check or count, skipping whichever is not known yet."""
    keys = []
    if ip:
        keys.append(_key(scope, "ip", ip))
    if email:
        keys.append(_key(scope, "email", email))
    return keys


def is_over_limit(scope, *, ip=None, email=None):
    """True when one of the given buckets is already full.

    Called twice per submission: once on the IP before the form is validated,
    because that check is free and needs nothing from the visitor, and once on
    the email afterwards, because until then there is no email to check.
    """
    for key in _buckets(scope, ip=ip, email=email):
        if cache.get(key, 0) >= SUBMISSION_LIMIT:
            return True
    return False


def record(scope, *, ip=None, email=None):
    """Count one accepted submission against every bucket that applies."""
    for key in _buckets(scope, ip=ip, email=email):
        # `add` only writes when the key is absent, so the day runs from the
        # visitor's first submission. Using `set` here instead would push the
        # expiry back on every message, and three messages in quick succession
        # would lock the sender out for a day starting from the last one.
        cache.add(key, 0, SUBMISSION_WINDOW)
        try:
            cache.incr(key)
        except ValueError:
            # The key expired in the moment between `add` and `incr`. Losing
            # one count is better than a server error on a real enquiry.
            cache.set(key, 1, SUBMISSION_WINDOW)


def blocked(scope, *, ip, email=None):
    """Log a refusal. Split out so every form reports it the same way."""
    logger.warning(
        "Rate limit reached on the %s form: ip=%s email=%s",
        scope,
        ip or "unknown",
        email or "-",
    )
