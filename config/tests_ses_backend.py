"""The SES backend, with boto3 replaced by a fake so nothing leaves the machine."""

from unittest import mock

from botocore.exceptions import ClientError
from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .ses_backend import SESEmailBackend

SES = override_settings(
    EMAIL_BACKEND="config.ses_backend.SESEmailBackend",
    AWS_SES_REGION_NAME="ap-southeast-2",
    AWS_SES_ACCESS_KEY_ID="AKIATEST",
    AWS_SES_SECRET_ACCESS_KEY="secret",
    AWS_SES_CONFIGURATION_SET="",
    EMAIL_REDIRECT_TO=[],
)


def refusal(code="MessageRejected", text="Email address is not verified."):
    return ClientError(
        {"Error": {"Code": code, "Message": text}}, "SendEmail"
    )


@SES
class SESEmailBackendTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch("config.ses_backend.boto3.client")
        self.client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.ses = self.client_factory.return_value
        self.ses.send_email.return_value = {"MessageId": "0100-abc"}

    def sent_request(self):
        self.ses.send_email.assert_called_once()
        return self.ses.send_email.call_args.kwargs

    # ------------------------------------------------------------- the client

    def test_the_client_is_built_for_the_configured_region_and_key(self):
        mail.send_mail("Hi", "Body", "no-reply@example.com", ["to@example.com"])

        self.client_factory.assert_called_once_with(
            "sesv2",
            region_name="ap-southeast-2",
            aws_access_key_id="AKIATEST",
            aws_secret_access_key="secret",
        )

    @override_settings(AWS_SES_ACCESS_KEY_ID="", AWS_SES_SECRET_ACCESS_KEY="")
    def test_empty_keys_leave_credentials_to_boto3(self):
        """None, not "", so boto3's own chain (a role, ~/.aws) takes over."""
        mail.send_mail("Hi", "Body", "no-reply@example.com", ["to@example.com"])

        kwargs = self.client_factory.call_args.kwargs
        self.assertIsNone(kwargs["aws_access_key_id"])
        self.assertIsNone(kwargs["aws_secret_access_key"])

    def test_one_client_serves_a_whole_batch(self):
        messages = [
            EmailMessage("One", "a", "no-reply@example.com", ["a@example.com"]),
            EmailMessage("Two", "b", "no-reply@example.com", ["b@example.com"]),
        ]
        sent = mail.get_connection().send_messages(messages)

        self.assertEqual(sent, 2)
        self.client_factory.assert_called_once()
        self.assertEqual(self.ses.send_email.call_count, 2)

    def test_an_explicitly_opened_connection_is_left_open(self):
        backend = SESEmailBackend()
        backend.open()
        backend.send_messages(
            [EmailMessage("One", "a", "no-reply@example.com", ["a@example.com"])]
        )
        self.assertIsNotNone(backend.client)
        backend.close()
        self.assertIsNone(backend.client)

    # ----------------------------------------------------------- the request

    def test_the_whole_message_goes_to_ses_as_raw_mime(self):
        message = EmailMultiAlternatives(
            subject="New enquiry: Dana",
            body="Plain text part",
            from_email="Rightway <no-reply@example.com>",
            to=["office@example.com"],
            cc=["cc@example.com"],
            bcc=["hidden@example.com"],
            reply_to=["dana@example.com"],
        )
        message.attach_alternative("<p>HTML part</p>", "text/html")
        message.send()

        request = self.sent_request()
        self.assertEqual(request["FromEmailAddress"], "Rightway <no-reply@example.com>")
        self.assertEqual(
            request["Destination"],
            {
                "ToAddresses": ["office@example.com"],
                "CcAddresses": ["cc@example.com"],
                "BccAddresses": ["hidden@example.com"],
            },
        )
        self.assertEqual(request["ReplyToAddresses"], ["dana@example.com"])
        self.assertNotIn("ConfigurationSetName", request)

        raw = request["Content"]["Raw"]["Data"]
        self.assertIsInstance(raw, bytes)
        self.assertIn(b"Subject: New enquiry: Dana", raw)
        self.assertIn(b"Reply-To: dana@example.com", raw)
        self.assertIn(b"Plain text part", raw)
        self.assertIn(b"<p>HTML part</p>", raw)
        # SES sees the Bcc list in Destination; it must not leak in the headers.
        self.assertNotIn(b"hidden@example.com", raw)
        self.assertIn(b"\r\n", raw)

    def test_a_non_ascii_display_name_is_encoded_not_dropped(self):
        EmailMessage(
            "Hi", "Body", "Rightway <no-reply@example.com>", ["Zoë <zoe@example.com>"]
        ).send()

        to = self.sent_request()["Destination"]["ToAddresses"][0]
        self.assertTrue(to.endswith("<zoe@example.com>"))
        self.assertNotIn("ë", to)

    @override_settings(AWS_SES_CONFIGURATION_SET="rightway-tracking")
    def test_a_configuration_set_is_named_when_configured(self):
        mail.send_mail("Hi", "Body", "no-reply@example.com", ["to@example.com"])
        self.assertEqual(
            self.sent_request()["ConfigurationSetName"], "rightway-tracking"
        )

    def test_the_message_id_is_kept_on_the_message(self):
        message = EmailMessage("Hi", "Body", "no-reply@example.com", ["to@example.com"])
        with self.assertLogs("config.ses_backend", level="INFO") as log:
            message.send()
        self.assertEqual(message.ses_message_id, "0100-abc")
        self.assertIn("0100-abc", log.output[0])

    def test_a_message_with_nobody_to_send_to_is_skipped(self):
        message = EmailMessage("Hi", "Body", "no-reply@example.com", to=[])
        self.assertEqual(message.send(), 0)
        self.ses.send_email.assert_not_called()

    # ------------------------------------------------------------- failures

    def test_a_refusal_raises_by_default(self):
        """Same contract as the SMTP backend: the callers decide whether to
        swallow it, and pages.notifications does."""
        self.ses.send_email.side_effect = refusal()
        with self.assertRaises(ClientError):
            mail.send_mail("Hi", "Body", "no-reply@example.com", ["to@example.com"])

    def test_fail_silently_logs_and_reports_nothing_sent(self):
        self.ses.send_email.side_effect = refusal()
        with self.assertLogs("config.ses_backend", level="ERROR"):
            sent = mail.send_mail(
                "Hi", "Body", "no-reply@example.com", ["to@example.com"],
                fail_silently=True,
            )
        self.assertEqual(sent, 0)

    def test_one_bad_message_does_not_stop_the_rest_when_silent(self):
        self.ses.send_email.side_effect = [refusal(), {"MessageId": "ok"}]
        messages = [
            EmailMessage("One", "a", "no-reply@example.com", ["a@example.com"]),
            EmailMessage("Two", "b", "no-reply@example.com", ["b@example.com"]),
        ]
        with self.assertLogs("config.ses_backend", level="ERROR"):
            sent = mail.get_connection(fail_silently=True).send_messages(messages)
        self.assertEqual(sent, 1)

    # ------------------------------------------------ with the redirect wrapper

    @override_settings(
        EMAIL_REDIRECT_TO=["tester@example.com"],
        EMAIL_REDIRECT_WRAPPED_BACKEND="config.ses_backend.SESEmailBackend",
        EMAIL_BACKEND="config.email_backend.RedirectingEmailBackend",
    )
    def test_the_redirect_safety_net_wraps_ses_too(self):
        mail.send_mail("Hi", "Body", "no-reply@example.com", ["real@example.com"])

        request = self.sent_request()
        self.assertEqual(request["Destination"]["ToAddresses"], ["tester@example.com"])
        self.assertIn(b"[TEST -> real@example.com]", request["Content"]["Raw"]["Data"])
