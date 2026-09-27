"""Cloudflare Turnstile: the widget, and the server-side check behind it.

Nothing here talks to Cloudflare. `pages.turnstile._post` is the single seam
where the real HTTP call happens, so every test replaces it with a canned
siteverify response and asserts on what the surrounding code does with it.
"""

import urllib.error
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import turnstile

SITE_KEY = "0x4AAAAAAFAluGVoc-gZgkNN"
SECRET = "test-secret-not-a-real-one"
TOKEN = "a-token-from-the-widget"

# What the forms send when someone actually completed the challenge.
CONTACT = {
    "name": "Jamie Reid",
    "email": "jamie@example.com",
    "phone": "0400 000 000",
    "message": "I would like to book a free consultation.",
    "hp_reference": "",
    turnstile.TOKEN_FIELD: TOKEN,
}


def siteverify(**overrides):
    """A siteverify body for a token this site would accept."""
    return {
        "success": True,
        "challenge_ts": "2026-09-23T01:02:03.000Z",
        "hostname": "testserver",
        "action": "contact",
        "error-codes": [],
        **overrides,
    }


on = override_settings(
    TURNSTILE_ENABLED=True,
    TURNSTILE_SITE_KEY=SITE_KEY,
    TURNSTILE_SECRET_KEY=SECRET,
    TURNSTILE_ALLOWED_HOSTNAMES=[],
    ALLOWED_HOSTS=["testserver"],
)


class SwitchTests(TestCase):
    """Turnstile is off until both keys are set."""

    @override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_off_with_neither_key(self):
        self.assertFalse(turnstile.is_enabled())

    @override_settings(TURNSTILE_SITE_KEY=SITE_KEY, TURNSTILE_SECRET_KEY="")
    def test_off_with_a_sitekey_but_no_secret(self):
        """A widget whose token nothing checks is worse than no widget: it
        looks like protection while being none."""
        self.assertFalse(turnstile.is_enabled())

    @on
    def test_on_with_both(self):
        self.assertTrue(turnstile.is_enabled())

    @on
    @override_settings(TURNSTILE_ENABLED=False)
    def test_the_switch_turns_it_off_with_both_keys_set(self):
        self.assertFalse(turnstile.is_enabled())

    @on
    @override_settings(TURNSTILE_ENABLED=False)
    def test_switched_off_the_widget_goes_and_forms_submit_without_a_token(self):
        page = self.client.get(reverse("contact"))
        self.assertNotContains(page, "challenges.cloudflare.com")

        without_token = {k: v for k, v in CONTACT.items() if k != turnstile.TOKEN_FIELD}
        with patch.object(turnstile, "_post") as post:
            response = self.client.post(reverse("contact"), without_token)

        self.assertRedirects(response, reverse("contact"))
        post.assert_not_called()


class VerifyTests(TestCase):
    """The siteverify call and the three things it is checked for."""

    @on
    def test_accepts_a_good_token(self):
        with patch.object(turnstile, "_post", return_value=siteverify()) as post:
            result = turnstile.verify(TOKEN, action="contact", remoteip="203.0.113.7")

        self.assertTrue(result.ok)
        sent = post.call_args.args[0]
        self.assertEqual(sent["secret"], SECRET)
        self.assertEqual(sent["response"], TOKEN)
        self.assertEqual(sent["remoteip"], "203.0.113.7")

    @on
    def test_missing_token_never_reaches_cloudflare(self):
        """No token means the script never ran or the POST never came from the
        page. Neither is worth a request."""
        with patch.object(turnstile, "_post") as post:
            result = turnstile.verify("", action="contact")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_codes, ("missing-input-response",))
        post.assert_not_called()

    @on
    def test_oversized_token_never_reaches_cloudflare(self):
        with patch.object(turnstile, "_post") as post:
            result = turnstile.verify("x" * 3000, action="contact")

        self.assertFalse(result.ok)
        post.assert_not_called()

    @on
    def test_rejected_token(self):
        body = siteverify(success=False, **{"error-codes": ["timeout-or-duplicate"]})
        with patch.object(turnstile, "_post", return_value=body):
            result = turnstile.verify(TOKEN, action="contact")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_codes, ("timeout-or-duplicate",))

    @on
    def test_action_must_match(self):
        """A token minted by the contact widget must not pay for a job
        application - otherwise the cheapest challenge on the site sets the
        price for every form on it."""
        with patch.object(turnstile, "_post", return_value=siteverify(action="contact")):
            result = turnstile.verify(TOKEN, action="job-application")

        self.assertFalse(result.ok)
        self.assertIn("expected", result.reason)

    @on
    def test_hostname_must_be_ours(self):
        """Stops a copy of the page hosted elsewhere spending tokens against
        this sitekey."""
        body = siteverify(hostname="phishing.example.com")
        with patch.object(turnstile, "_post", return_value=body):
            result = turnstile.verify(TOKEN, action="contact")

        self.assertFalse(result.ok)
        self.assertIn("phishing.example.com", result.reason)

    @override_settings(
        TURNSTILE_SITE_KEY=SITE_KEY,
        TURNSTILE_SECRET_KEY=SECRET,
        TURNSTILE_ALLOWED_HOSTNAMES=[],
        ALLOWED_HOSTS=["*"],
    )
    def test_wildcard_allowed_hosts_turns_the_hostname_check_off(self):
        """Rather than rejecting everything, which is what a literal reading of
        `hostname not in {"*"}` would do."""
        with patch.object(turnstile, "_post", return_value=siteverify(hostname="anything")):
            self.assertTrue(turnstile.verify(TOKEN, action="contact").ok)

    @override_settings(
        TURNSTILE_SITE_KEY=SITE_KEY,
        TURNSTILE_SECRET_KEY=SECRET,
        TURNSTILE_ALLOWED_HOSTNAMES=["rightwaysupportservices.com.au"],
        ALLOWED_HOSTS=["testserver"],
    )
    def test_explicit_hostname_list_wins_over_allowed_hosts(self):
        with patch.object(turnstile, "_post", return_value=siteverify(hostname="testserver")):
            self.assertFalse(turnstile.verify(TOKEN, action="contact").ok)

        body = siteverify(hostname="rightwaysupportservices.com.au")
        with patch.object(turnstile, "_post", return_value=body):
            self.assertTrue(turnstile.verify(TOKEN, action="contact").ok)

    @on
    def test_unreachable_cloudflare_fails_closed(self):
        """Letting a submission through because the check itself broke would
        hand anyone who can disrupt that one call a way straight past it."""
        with patch.object(turnstile, "_post", side_effect=urllib.error.URLError("down")):
            result = turnstile.verify(TOKEN, action="contact")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_codes, ("internal-error",))


class ClientIpTests(TestCase):
    def test_prefers_cloudflares_header(self):
        request = self.client.request(
            REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7"
        ).wsgi_request
        self.assertEqual(turnstile.client_ip(request), "203.0.113.7")

    def test_falls_back_to_remote_addr(self):
        request = self.client.request(REMOTE_ADDR="10.0.0.1").wsgi_request
        self.assertEqual(turnstile.client_ip(request), "10.0.0.1")


class WidgetRenderingTests(TestCase):
    """What the page actually contains."""

    def test_nothing_rendered_while_turnstile_is_off(self):
        response = self.client.get(reverse("contact"))
        self.assertNotContains(response, "cf-turnstile")
        self.assertNotContains(response, "challenges.cloudflare.com")

    @on
    def test_each_form_carries_the_sitekey_and_its_own_action(self):
        for url, action in [
            (reverse("contact"), "contact"),
            (reverse("consultation"), "consultation"),
            (reverse("apply"), "job-application"),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'data-sitekey="%s"' % SITE_KEY)
                self.assertContains(response, 'data-action="%s"' % action)
                self.assertContains(
                    response,
                    "https://challenges.cloudflare.com/turnstile/v0/api.js",
                )

    @on
    def test_the_secret_never_reaches_the_page(self):
        response = self.client.get(reverse("contact"))
        self.assertNotContains(response, SECRET)


@on
class ContactFormTests(TestCase):
    """The enquiry form, which is the one with the most to lose."""

    def test_verified_submission_goes_through(self):
        with patch.object(turnstile, "_post", return_value=siteverify()):
            response = self.client.post(reverse("contact"), CONTACT)

        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(len(mail.outbox), 2)

    def test_submission_without_a_token_is_refused(self):
        payload = {k: v for k, v in CONTACT.items() if k != turnstile.TOKEN_FIELD}
        with patch.object(turnstile, "_post") as post:
            response = self.client.post(reverse("contact"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        post.assert_not_called()

    def test_a_refusal_tells_the_visitor_how_to_recover(self):
        """Not a silent drop: someone with JavaScript blocked has to be able to
        tell why nothing happened."""
        body = siteverify(success=False, **{"error-codes": ["invalid-input-response"]})
        with patch.object(turnstile, "_post", return_value=body):
            response = self.client.post(reverse("contact"), CONTACT)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "could not confirm you are human")
        self.assertEqual(len(mail.outbox), 0)

    def test_the_visitors_address_is_sent_as_remoteip(self):
        with patch.object(turnstile, "_post", return_value=siteverify()) as post:
            self.client.post(
                reverse("contact"), CONTACT, HTTP_CF_CONNECTING_IP="203.0.113.7"
            )

        self.assertEqual(post.call_args.args[0]["remoteip"], "203.0.113.7")

    def test_a_failed_check_records_no_enquiry(self):
        from .models import Enquiry

        with patch.object(turnstile, "_post", return_value=siteverify(success=False)):
            self.client.post(reverse("contact"), CONTACT)

        self.assertEqual(Enquiry.objects.count(), 0)
