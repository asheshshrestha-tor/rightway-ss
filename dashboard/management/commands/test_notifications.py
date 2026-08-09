"""Check the email setup without submitting forms on the live site.

    python manage.py test_notifications

Shows who would be notified about each kind of submission and why, then
optionally sends a real message so you can confirm the whole chain works:
credentials, sender reputation, and what it looks like in an actual inbox.

Nothing is written to the database - the enquiry it describes is a throwaway
object that is never saved.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from pages import notifications
from pages.models import Enquiry, SiteSettings

PERMISSIONS = [
    ("Contact enquiries", "pages.view_enquiry"),
    ("Job applications", "pages.view_application"),
    ("Consultation requests", "pages.view_consultation"),
]


class Command(BaseCommand):
    help = "Show who receives submission notifications, and optionally send one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            metavar="EMAIL",
            help="Actually send a sample notification and confirmation here.",
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1:8000",
            help="Host to build the dashboard link from. Use your real domain.",
        )

    def handle(self, *args, **options):
        site = SiteSettings.load()

        self.stdout.write(self.style.MIGRATE_HEADING("\nConfiguration"))
        backend = settings.EMAIL_BACKEND.rsplit(".", 1)[-1]
        self.stdout.write(f"  Backend        {backend}")
        if "console" in settings.EMAIL_BACKEND.lower():
            self.stdout.write(
                self.style.WARNING(
                    "                 prints to this terminal and sends nothing"
                )
            )
        if settings.EMAIL_HOST:
            self.stdout.write(f"  SMTP host      {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"  From           {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"  Office inbox   {notifications.office_email()}")

        if settings.EMAIL_REDIRECT_TO:
            self.stdout.write(
                self.style.WARNING(
                    f"  REDIRECTING    all mail goes to "
                    f"{', '.join(settings.EMAIL_REDIRECT_TO)}"
                )
            )
        if settings.ADMIN_NOTIFICATION_EMAILS:
            self.stdout.write(
                f"  Extra copies   {', '.join(settings.ADMIN_NOTIFICATION_EMAILS)}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\nWho gets notified"))
        problems = []
        for label, permission in PERMISSIONS:
            people = notifications.staff_emails(permission)
            everyone = notifications.recipients(permission)

            self.stdout.write(f"\n  {label}  ({permission})")
            for address in everyone:
                why = "staff" if address in people else "office / extra"
                self.stdout.write(f"      {address}  ({why})")
            if not everyone:
                problems.append(f"nobody would be notified about {label.lower()}")
                self.stdout.write(self.style.ERROR("      nobody"))

        self.stdout.write(
            self.style.MIGRATE_HEADING("\nStaff accounts with no email address")
        )
        from django.contrib.auth.models import User

        blank = User.objects.filter(is_active=True, is_staff=True, email="")
        if blank:
            for user in blank:
                self.stdout.write(
                    self.style.WARNING(f"  {user.username} - cannot be notified")
                )
        else:
            self.stdout.write("  none")

        if options["send"]:
            self._send_sample(options["send"], options["host"], site)
        else:
            self.stdout.write(
                "\nAdd --send you@example.com to send a real sample.\n"
            )

        for problem in problems:
            self.stdout.write(self.style.ERROR(f"\nWarning: {problem}"))

    def _send_sample(self, address, host, site):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nSending a sample to {address}"))

        # Never saved: this is only here to render the templates with something
        # that looks like a real submission.
        enquiry = Enquiry(
            pk=0,
            name="Test Submission",
            email=address,
            phone="0470 000 000",
            message=(
                "This is a test of the notification email. If you are reading "
                "it, the mail configuration works."
            ),
        )

        # build_absolute_uri validates the host against ALLOWED_HOSTS, which
        # will not list a production domain when this is run from a laptop.
        # Trusting it here is safe: no request is being served, and the only
        # thing the host affects is the link written into a test email.
        if host not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, host]

        request = RequestFactory().get("/", HTTP_HOST=host)

        sent = notifications.confirm(
            to=address,
            subject="Test: confirmation email",
            heading="This is a test",
            greeting="there",
            paragraphs=[
                "If this arrived, confirmations to people who submit a form are "
                "working.",
                "Nothing was saved and no real submission was made.",
            ],
            rows=[("Sent by", "manage.py test_notifications")],
        )
        self._report("confirmation", sent, address)

        sent = notifications.notify(
            request,
            permission="pages.view_enquiry",
            subject="Test: new enquiry notification",
            heading="This is a test",
            summary="If this arrived, staff notifications are working.",
            rows=[
                ("Name", enquiry.name),
                ("Email", enquiry.email),
                ("Message", enquiry.message),
            ],
            url_name="dashboard:enquiry_list",
            pk=None,
            action_label="Open the dashboard",
            reply_to=address,
        )
        self._report("notification", sent, ", ".join(
            notifications.recipients("pages.view_enquiry")
        ))

    def _report(self, kind, sent, to):
        if sent:
            self.stdout.write(self.style.SUCCESS(f"  {kind} sent to {to}"))
        else:
            self.stdout.write(
                self.style.ERROR(f"  {kind} FAILED - see the logged traceback")
            )
