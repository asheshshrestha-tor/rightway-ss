import os

from django import forms
from django.conf import settings

from .consultation_models import next_business_day
from .models import Application, Consultation, Service

# Honeypot field name. Deliberately meaningless: names like "website", "url" or
# "company" are standard browser-autofill tokens, and browsers fill them even
# when the input is off-screen with autocomplete="off" (Chrome ignores that
# attribute outside credential fields). An autofilled honeypot silently rejects
# a real person, so the name must attract nothing.
HONEYPOT_FIELD = "hp_reference"


class ContactForm(forms.Form):
    """Enquiry form shown on the Contact page.

    The honeypot field is hidden from people by CSS. Anything that fills it is
    probably a bot - but a false positive must never block a real enquiry, so
    tripping it does not invalidate the form. See `is_probably_spam`.
    """

    name = forms.CharField(
        label="Your Name",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Your Name", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={"placeholder": "Email Address", "autocomplete": "email"}
        ),
    )
    phone = forms.CharField(
        label="Phone Number",
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Phone Number", "autocomplete": "tel"}),
    )
    message = forms.CharField(
        label="Your Message",
        widget=forms.Textarea(attrs={"placeholder": "Your Message", "rows": 6}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[HONEYPOT_FIELD] = forms.CharField(
            label="Leave this field blank",
            required=False,
            widget=forms.TextInput(
                attrs={
                    "tabindex": "-1",
                    "autocomplete": "off",
                    "aria-hidden": "true",
                }
            ),
        )

    @property
    def honeypot(self):
        """The honeypot bound field, for the template."""
        return self[HONEYPOT_FIELD]

    def is_probably_spam(self):
        """True when the honeypot was filled in.

        Callers should quietly quarantine the submission rather than reject it:
        a genuine enquiry lost to an autofill quirk costs far more than an
        extra row to review.
        """
        return bool(self.cleaned_data.get(HONEYPOT_FIELD, "").strip())

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please tell us a little more so we can help.")
        return message



class ApplicationForm(forms.ModelForm):
    """Public job application, with a resume upload.

    File validation is deliberate rather than left to the browser: `accept` on
    the input is a hint a client can ignore, so extension and size are checked
    server side too.
    """

    class Meta:
        model = Application
        fields = ["full_name", "email", "phone", "cover_letter", "resume"]
        labels = {
            "full_name": "Your Name",
            "email": "Email Address",
            "phone": "Phone Number",
            "cover_letter": "Why you're a good fit",
            "resume": "Resume",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Your Name", "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email Address", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone Number", "autocomplete": "tel"}),
            "cover_letter": forms.Textarea(
                attrs={"placeholder": "Tell us a little about yourself", "rows": 6}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = True
        self.fields["resume"].widget.attrs["accept"] = ",".join(
            settings.RESUME_ALLOWED_EXTENSIONS
        )
        self.fields["resume"].help_text = "PDF or Word document, up to %d MB." % (
            settings.RESUME_MAX_BYTES // (1024 * 1024)
        )

    def clean_resume(self):
        resume = self.cleaned_data["resume"]

        extension = os.path.splitext(resume.name)[1].lower()
        if extension not in settings.RESUME_ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                "Please upload one of these file types: %s."
                % ", ".join(settings.RESUME_ALLOWED_EXTENSIONS)
            )

        if resume.size > settings.RESUME_MAX_BYTES:
            raise forms.ValidationError(
                "That file is %.1f MB. Please keep it under %d MB."
                % (
                    resume.size / (1024 * 1024),
                    settings.RESUME_MAX_BYTES // (1024 * 1024),
                )
            )

        return resume


class ConsultationForm(forms.ModelForm):
    """Request the free consultation the site advertises.

    Validation encodes promises the site already makes:
      * office hours are Mon-Fri, so a weekend date cannot be honoured
      * "we respond within one business day", so the earliest workable date is
        the next business day - offering sooner would set up a broken promise
      * home visits are only offered around Toowoomba, so a suburb is required
        to know whether the visit is even possible
    """

    class Meta:
        model = Consultation
        fields = [
            "full_name",
            "email",
            "phone",
            "enquirer_type",
            "participant_name",
            "plan_status",
            "services",
            "goals",
            "delivery",
            "suburb",
            "postcode",
            "preferred_date",
            "preferred_window",
            "alternate_date",
            "alternate_window",
        ]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "alternate_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "goals": forms.Textarea(
                attrs={"rows": 4, "placeholder": "For example: I have just had my plan approved and I am not sure where to start."}
            ),
            "services": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.earliest = next_business_day()

        self.fields["services"].queryset = Service.objects.published()
        self.fields["services"].required = False

        for name in ("preferred_date", "alternate_date"):
            self.fields[name].input_formats = ["%Y-%m-%d"]
            # Stops the native picker offering dates the office cannot serve.
            self.fields[name].widget.attrs["min"] = self.earliest.isoformat()

        self.fields["preferred_date"].help_text = (
            "Weekdays only. The earliest we can meet is %s."
            % self.earliest.strftime("%A %d %B")
        )
        self.fields["alternate_date"].help_text = "Optional, but it helps us confirm faster."
        self.fields["participant_name"].help_text = (
            "Only if you are enquiring for someone else."
        )

        for field in ("full_name", "email", "phone"):
            self.fields[field].widget.attrs.setdefault(
                "placeholder", self.fields[field].label
            )

    # ---------------------------------------------------------- validation

    def _check_date(self, value, label):
        if value is None:
            return None
        if value.weekday() >= 5:
            raise forms.ValidationError(
                f"We are open Monday to Friday. Please choose a weekday for your "
                f"{label}."
            )
        if value < self.earliest:
            raise forms.ValidationError(
                "We need at least one business day's notice. The earliest we can "
                "meet is %s." % self.earliest.strftime("%A %d %B")
            )
        return value

    def clean_preferred_date(self):
        return self._check_date(self.cleaned_data.get("preferred_date"), "preferred date")

    def clean_alternate_date(self):
        return self._check_date(
            self.cleaned_data.get("alternate_date"), "alternative date"
        )

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("delivery") == Consultation.Delivery.HOME and not cleaned.get(
            "suburb"
        ):
            self.add_error(
                "suburb",
                "Please tell us your suburb so we can check we cover your area.",
            )

        enquirer = cleaned.get("enquirer_type")
        if enquirer and enquirer != Consultation.Enquirer.SELF and not cleaned.get(
            "participant_name"
        ):
            self.add_error(
                "participant_name",
                "Please tell us who the consultation is for.",
            )

        first, second = cleaned.get("preferred_date"), cleaned.get("alternate_date")
        if first and second and first == second:
            if cleaned.get("preferred_window") == cleaned.get("alternate_window"):
                self.add_error(
                    "alternate_date",
                    "Please choose a different day or time from your first preference.",
                )

        return cleaned
