"""The project's test runner.

Settings are read from `.env`, which on a working machine holds real
credentials. That is right for running the site and wrong for running the
tests: whether a test passes must not depend on what happens to be in one
developer's `.env`, and no test may reach a third party.

Turnstile is the case that bites. With both keys set, every form POST in the
suite would be checked against Cloudflare for real - slow, flaky, dependent on
a network, and quietly spending the account's quota on tests. Blanking the keys
here switches Turnstile off for the whole run, which is the same state a fresh
clone is in.

`pages/tests_turnstile.py` turns it back on with `override_settings` and stubs
the HTTP call, so the integration is still covered end to end.
"""

from django.conf import settings
from django.test.runner import DiscoverRunner


class RightwayTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)

        # Off unless a test asks for it. See pages/turnstile.py:is_enabled.
        settings.TURNSTILE_SITE_KEY = ""
        settings.TURNSTILE_SECRET_KEY = ""
