"""The free, no-obligation consultation the site advertises everywhere.

Shape follows what the site already promises visitors (see the FAQ in
`pages.content`):

  * free and no-obligation
  * held "either in your home or over the phone"
  * about the person's goals and NDIS plan, leading to a support-worker match
  * "we will respond within one business day and arrange a time that suits you"

That last line is why this is a *request*, not a self-service calendar: the
visitor states when they are available, staff confirm an exact time. It is also
step one of the four-step journey on the NDIS page ("Understand Your Goals").
"""

from datetime import timedelta

from django.db import models
from django.utils import timezone

# Office hours are Mon-Fri 8:00-5:00 (editable in Site Settings), so times
# are offered as windows inside that, never outside it.
TIME_WINDOWS = [
    ("morning", "Morning (8:00 AM - 12:00 PM)"),
    ("afternoon", "Afternoon (12:00 PM - 5:00 PM)"),
    ("any", "Any time that suits you"),
]


def next_business_day(from_date=None):
    """The earliest date staff could realistically meet someone.

    The site promises a response within one business day, so offering today
    would be a promise the office cannot keep.
    """
    day = (from_date or timezone.localdate()) + timedelta(days=1)
    while day.weekday() >= 5:  # Saturday, Sunday
        day += timedelta(days=1)
    return day


class ConsultationQuerySet(models.QuerySet):
    def open_requests(self):
        return self.filter(status=Consultation.Status.REQUESTED)

    def upcoming(self):
        return self.filter(
            status=Consultation.Status.CONFIRMED,
            scheduled_for__gte=timezone.now(),
        ).order_by("scheduled_for")


class Consultation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "Did not attend"

    class Delivery(models.TextChoices):
        HOME = "home", "At my home"
        PHONE = "phone", "Over the phone"
        VIDEO = "video", "Video call"

    class Enquirer(models.TextChoices):
        SELF = "self", "Myself"
        FAMILY = "family", "A family member or carer"
        COORDINATOR = "coordinator", "A support coordinator"
        OTHER = "other", "Someone else"

    class PlanStatus(models.TextChoices):
        APPROVED_SELF = "self_managed", "Approved - self managed"
        APPROVED_PLAN = "plan_managed", "Approved - plan managed"
        APPROVED_AGENCY = "agency_managed", "Approved - NDIA managed"
        APPLYING = "applying", "Applying for a plan"
        NOT_YET = "not_yet", "No plan yet"
        UNSURE = "unsure", "Not sure"

    # Quoted on the phone and in emails, so it needs to be short and speakable.
    reference = models.CharField(max_length=20, unique=True, blank=True, db_index=True)

    # --- who is asking ---
    full_name = models.CharField("Your name", max_length=140)
    email = models.EmailField("Email address")
    phone = models.CharField("Phone number", max_length=40)
    enquirer_type = models.CharField(
        "This consultation is for",
        max_length=20,
        choices=Enquirer.choices,
        default=Enquirer.SELF,
    )
    participant_name = models.CharField(
        "Participant's name",
        max_length=140,
        blank=True,
        help_text="If you are enquiring on someone else's behalf.",
    )

    # --- what they need ---
    plan_status = models.CharField(
        "NDIS plan status",
        max_length=20,
        choices=PlanStatus.choices,
        default=PlanStatus.UNSURE,
    )
    services = models.ManyToManyField(
        "pages.Service",
        blank=True,
        related_name="consultations",
        verbose_name="Support you're interested in",
    )
    goals = models.TextField(
        "What would you like to talk about?",
        blank=True,
        help_text="Optional - it helps us come prepared.",
    )

    # --- how and when ---
    delivery = models.CharField(
        "Where would you like to meet?",
        max_length=20,
        choices=Delivery.choices,
        default=Delivery.PHONE,
    )
    suburb = models.CharField(max_length=120, blank=True)
    postcode = models.CharField(max_length=10, blank=True)

    preferred_date = models.DateField("Preferred date")
    preferred_window = models.CharField(
        "Preferred time", max_length=20, choices=TIME_WINDOWS, default="any"
    )
    alternate_date = models.DateField("Alternative date", null=True, blank=True)
    alternate_window = models.CharField(
        "Alternative time", max_length=20, choices=TIME_WINDOWS, blank=True
    )

    # --- staff side ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )
    scheduled_for = models.DateTimeField(
        null=True, blank=True, help_text="The time actually agreed with the participant."
    )
    assigned_to = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consultations",
    )
    staff_notes = models.TextField(blank=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ConsultationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference or 'Consultation'} - {self.full_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            # Needs the primary key, so it is set on the way back out.
            self.reference = f"RW-{self.created_at:%y}-{self.pk:04d}"
            super().save(update_fields=["reference"])

    # ------------------------------------------------------------- helpers

    @property
    def for_whom(self):
        """Who the consultation is actually about."""
        if self.enquirer_type == self.Enquirer.SELF:
            return self.full_name
        return self.participant_name or "Not given"

    @property
    def is_home_visit(self):
        return self.delivery == self.Delivery.HOME

    @property
    def location_line(self):
        if not self.is_home_visit:
            return self.get_delivery_display()
        parts = [p for p in (self.suburb, self.postcode) if p]
        return f"Home visit - {' '.join(parts)}" if parts else "Home visit"

    @property
    def preference_line(self):
        text = f"{self.preferred_date:%a %d %b %Y}, {self.get_preferred_window_display()}"
        if self.alternate_date:
            text += (
                f" (or {self.alternate_date:%a %d %b %Y}"
                f"{', ' + self.get_alternate_window_display() if self.alternate_window else ''})"
            )
        return text

    @property
    def is_overdue(self):
        """Still unanswered more than one business day after it arrived.

        Surfaces the promise the site makes: "we will respond within one
        business day".
        """
        if self.status != self.Status.REQUESTED:
            return False
        return timezone.localdate() > next_business_day(self.created_at.date())

    @property
    def status_css(self):
        """Metronic badge modifier. demo29 inverts the palette: --bs-primary is
        green (#17C653) and --bs-success is blue (#1B84FF)."""
        return {
            self.Status.REQUESTED: "warning",
            self.Status.CONFIRMED: "success",
            self.Status.COMPLETED: "primary",
            self.Status.CANCELLED: "danger",
            self.Status.NO_SHOW: "danger",
        }[self.status]
