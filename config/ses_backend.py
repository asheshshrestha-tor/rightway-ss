"""Send mail through Amazon SES over its API.

Django's SMTP backend would also work against SES's SMTP endpoint, but that
needs a second set of credentials (SES "SMTP credentials" are derived from an
IAM key, not the key itself) and pays a TLS handshake and a login per message.
The API needs only the IAM key the app already holds for S3, with one extra
permission, and is what the AWS console, CloudWatch and the suppression list
all report against.

Turn it on with:

    EMAIL_BACKEND=config.ses_backend.SESEmailBackend

Everything Django builds - the plain-text body, the HTML alternative, Reply-To,
attachments - is handed to SES as the finished RFC 5322 message, so nothing is
lost in translation and nothing here has to know what kind of email it is
carrying. The `EMAIL_REDIRECT_TO` safety net in `config.email_backend` wraps
this backend like any other.

Failures raise unless `fail_silently` is set, the same contract as the SMTP
backend. The callers in `pages.notifications` and `pages.consultation_mail`
catch and log, so a mail outage never surfaces as an error page.
"""

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

logger = logging.getLogger(__name__)


class SESEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.region_name = kwargs.get("region_name") or settings.AWS_SES_REGION_NAME
        self.access_key = kwargs.get("access_key") or settings.AWS_SES_ACCESS_KEY_ID
        self.secret_key = kwargs.get("secret_key") or settings.AWS_SES_SECRET_ACCESS_KEY
        self.configuration_set = (
            kwargs.get("configuration_set") or settings.AWS_SES_CONFIGURATION_SET
        )
        self.client = None

    # ------------------------------------------------------------ connection

    def open(self):
        """Create the SES client. Returns True if this call created it, so
        `send_messages` knows whether it is responsible for closing it."""
        if self.client is not None:
            return False
        # Empty keys become None so boto3 falls back to its own credential
        # chain - an instance role, a container task role, ~/.aws/credentials -
        # which is the right thing on any host that has one. Railway does not,
        # so there the keys come from .env.
        self.client = boto3.client(
            "sesv2",
            region_name=self.region_name,
            aws_access_key_id=self.access_key or None,
            aws_secret_access_key=self.secret_key or None,
        )
        return True

    def close(self):
        self.client = None

    # --------------------------------------------------------------- sending

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        new_connection = self.open()
        sent = 0
        try:
            for message in email_messages:
                if self._send(message):
                    sent += 1
        finally:
            if new_connection:
                self.close()
        return sent

    def _send(self, message):
        recipients = message.recipients()
        if not recipients:
            return False

        encoding = message.encoding or settings.DEFAULT_CHARSET
        request = {
            "FromEmailAddress": sanitize_address(message.from_email, encoding),
            # Bcc never appears in the headers - that is the point of it - so
            # SES has to be told the full recipient list separately. Passing
            # To and Cc as well keeps the envelope and the headers in step.
            "Destination": {
                "ToAddresses": [sanitize_address(a, encoding) for a in message.to],
                "CcAddresses": [sanitize_address(a, encoding) for a in message.cc],
                "BccAddresses": [sanitize_address(a, encoding) for a in message.bcc],
            },
            "Content": {
                "Raw": {"Data": message.message().as_bytes(linesep="\r\n")},
            },
        }
        if message.reply_to:
            request["ReplyToAddresses"] = [
                sanitize_address(a, encoding) for a in message.reply_to
            ]
        if self.configuration_set:
            request["ConfigurationSetName"] = self.configuration_set

        try:
            response = self.client.send_email(**request)
        except (BotoCoreError, ClientError):
            if not self.fail_silently:
                raise
            logger.exception("SES refused a message: %s", message.subject)
            return False

        # Kept on the message so a caller (or a test) can find the send in the
        # SES console and in CloudWatch. Also logged, because in production the
        # log is the only place anyone will look for it.
        message.ses_message_id = response.get("MessageId", "")
        logger.info(
            "SES accepted %r for %s (MessageId %s)",
            message.subject,
            ", ".join(recipients),
            message.ses_message_id,
        )
        return True
