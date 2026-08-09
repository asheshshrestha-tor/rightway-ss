from datetime import datetime, time

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.models import Group, Permission, User

from pages.models import (
    Application,
    Consultation,
    Enquiry,
    Service,
    SiteSettings,
    SocialLink,
    TeamMember,
    Vacancy,
)

# Metronic form control classes, applied to every widget so the templates can
# render fields with a plain {{ field }} instead of hand-writing inputs.
INPUT = "form-control form-control-solid"
SELECT = "form-select form-select-solid"
CHECK = "form-check-input"


def _style(fields, css=INPUT, placeholder_from_label=True):
    for name, field in fields.items():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            widget.attrs.setdefault("class", CHECK)
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", SELECT)
        else:
            widget.attrs.setdefault("class", css)
            if placeholder_from_label and field.label:
                widget.attrs.setdefault("placeholder", field.label)


class DashboardLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": INPUT, "placeholder": "Username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": INPUT, "placeholder": "Password"}
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                "This account does not have dashboard access.", code="not_staff"
            )


class UserForm(forms.ModelForm):
    """Create or edit a user, including the roles they belong to.

    Password is optional on edit: leaving both boxes blank keeps the existing
    one. On create it is required, which `__init__` enforces.
    """

    password1 = forms.CharField(
        label="Password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    groups = forms.ModelMultipleChoiceField(
        label="Roles",
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.creating = self.instance.pk is None
        if self.creating:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Leave blank to keep the current password."
        self.fields["email"].required = True
        _style(self.fields)
        for name in ("is_active", "is_staff", "is_superuser"):
            self.fields[name].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "The two password fields do not match.")
            elif len(p1) < 8:
                self.add_error("password1", "Password must be at least 8 characters.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class PermissionChoiceField(forms.ModelMultipleChoiceField):
    """Label permissions by action alone.

    Django's default label is "App | model | Can add thing", which is redundant
    once the checkboxes are already grouped by model in the template.
    """

    def label_from_instance(self, obj):
        return obj.name


class GroupForm(forms.ModelForm):
    """A role: a name plus the set of permissions it grants."""

    permissions = PermissionChoiceField(
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Group
        fields = ["name", "permissions"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = (
            Permission.objects.select_related("content_type")
            .order_by("content_type__app_label", "content_type__model", "codename")
        )
        _style(self.fields)

    def permission_groups(self):
        """Yield (model label, [bound checkboxes]) so the template can render
        permissions grouped by the model they apply to rather than as one
        undifferentiated list of ~30 checkboxes."""
        labels = {
            str(p.pk): f"{p.content_type.app_label} · {p.content_type.model}"
            for p in self.fields["permissions"].queryset
        }
        buckets = {}
        for checkbox in self["permissions"]:
            buckets.setdefault(labels[str(checkbox.data["value"])], []).append(checkbox)
        return sorted(buckets.items())


class ServiceForm(forms.ModelForm):
    """Create or edit a public-facing service."""

    class Meta:
        model = Service
        fields = [
            "title",
            "slug",
            "summary",
            "description",
            "body",
            "highlights",
            "icon",
            "image",
            "order",
            "is_published",
            "show_in_footer",
            "meta_description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["description"].widget.attrs["rows"] = 3
        self.fields["body"].widget.attrs["rows"] = 10
        self.fields["highlights"].widget.attrs["rows"] = 6
        self.fields["meta_description"].widget.attrs["rows"] = 2
        _style(self.fields)
        # File inputs get Bootstrap's own control class, not the solid variant.
        self.fields["image"].widget.attrs["class"] = "form-control"
        for name in ("is_published", "show_in_footer"):
            self.fields[name].widget.attrs["class"] = "form-check-input"

    def clean_slug(self):
        """Blank is allowed - the model builds one from the title on save."""
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            return ""
        clash = Service.objects.filter(slug=slug).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Another service already uses this URL.")
        return slug


class TeamMemberForm(forms.ModelForm):
    """Create or edit someone shown in the About page's team section."""

    class Meta:
        model = TeamMember
        fields = [
            "name",
            "slug",
            "role",
            "photo",
            "bio",
            "qualifications",
            "order",
            "is_published",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["bio"].widget.attrs["rows"] = 8
        self.fields["qualifications"].widget.attrs["rows"] = 5
        _style(self.fields)
        self.fields["photo"].widget.attrs["class"] = "form-control"
        self.fields["is_published"].widget.attrs["class"] = "form-check-input"

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            return ""
        if TeamMember.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another team member already uses this URL.")
        return slug


class VacancyForm(forms.ModelForm):
    """Create or edit an advertised position."""

    class Meta:
        model = Vacancy
        fields = [
            "title",
            "slug",
            "employment_type",
            "location",
            "summary",
            "description",
            "responsibilities",
            "requirements",
            "salary_range",
            "closing_date",
            "order",
            "is_published",
        ]
        widgets = {
            "closing_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["description"].widget.attrs["rows"] = 8
        self.fields["responsibilities"].widget.attrs["rows"] = 6
        self.fields["requirements"].widget.attrs["rows"] = 6
        self.fields["summary"].widget.attrs["rows"] = 2
        _style(self.fields)
        self.fields["is_published"].widget.attrs["class"] = "form-check-input"
        # A date input must be given the value in ISO form or the browser
        # shows it blank.
        self.fields["closing_date"].input_formats = ["%Y-%m-%d"]

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            return ""
        if Vacancy.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another vacancy already uses this URL.")
        return slug


class ApplicationUpdateForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status", "handled_by", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["handled_by"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        ).order_by("username")
        self.fields["handled_by"].label = "Assigned to"
        self.fields["notes"].widget.attrs["rows"] = 5
        _style(self.fields)


class EnquiryUpdateForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = ["status", "handled_by", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["handled_by"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        ).order_by("username")
        self.fields["handled_by"].label = "Assigned to"
        self.fields["notes"].widget.attrs["rows"] = 5
        _style(self.fields)


# ---------------------------------------------------------------- passwords


class StaffPasswordResetForm(PasswordResetForm):
    """Forgot-password form for the dashboard.

    Only staff accounts can reset this way, so a public-site contact whose
    email happens to match a user record cannot trigger a reset mail. The form
    never reveals whether an address matched - `get_users` returning nothing
    simply sends nothing, and the view shows the same confirmation either way.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": INPUT, "placeholder": "Email address", "autofocus": True}
        )

    def get_users(self, email):
        return (
            user
            for user in super().get_users(email)
            if user.is_staff and user.is_active
        )


class MetronicSetPasswordForm(SetPasswordForm):
    """Set a new password after following a reset link."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {"class": INPUT, "placeholder": "New password", "autocomplete": "new-password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"class": INPUT, "placeholder": "Confirm new password", "autocomplete": "new-password"}
        )


class MetronicPasswordChangeForm(PasswordChangeForm):
    """Change your own password while signed in."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("old_password", "new_password1", "new_password2"):
            self.fields[name].widget.attrs.update(
                {"class": INPUT, "autocomplete": "new-password"}
            )
        self.fields["old_password"].widget.attrs["placeholder"] = "Current password"
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["placeholder"] = "New password"
        self.fields["new_password2"].widget.attrs["placeholder"] = "Confirm new password"


class AccountForm(forms.ModelForm):
    """Your own profile.

    Deliberately excludes is_staff / is_superuser / groups: changing your own
    access level belongs on the Users screen, behind `auth.change_user`.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        _style(self.fields)


class ConsultationUpdateForm(forms.ModelForm):
    """Confirm a time, or move the consultation along.

    Confirming requires an actual date and time - a consultation cannot be
    "confirmed" with nothing to tell the participant.
    """

    send_confirmation = forms.BooleanField(
        required=False,
        initial=True,
        label="Email the participant the confirmed time",
    )

    class Meta:
        model = Consultation
        fields = ["status", "scheduled_for", "assigned_to", "staff_notes"]
        widgets = {
            "scheduled_for": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        ).order_by("username")
        self.fields["scheduled_for"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["scheduled_for"].label = "Confirmed date and time"
        self.fields["staff_notes"].widget.attrs["rows"] = 5
        _style(self.fields)
        self.fields["send_confirmation"].widget.attrs["class"] = "form-check-input"

        # Suggest the participant's first preference so staff usually just
        # adjust the hour rather than retyping the date.
        if not self.instance.scheduled_for and self.instance.preferred_date:
            hour = 9 if self.instance.preferred_window != "afternoon" else 13
            self.initial["scheduled_for"] = datetime.combine(
                self.instance.preferred_date, time(hour, 0)
            ).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        when = cleaned.get("scheduled_for")

        needs_time = {
            Consultation.Status.CONFIRMED,
            Consultation.Status.COMPLETED,
            Consultation.Status.NO_SHOW,
        }
        if status in needs_time and not when:
            self.add_error(
                "scheduled_for",
                "Set the date and time before marking it %s."
                % Consultation.Status(status).label.lower(),
            )
        return cleaned


class SiteSettingsForm(forms.ModelForm):
    """The one settings row: branding, contact details, footer and map."""

    class Meta:
        model = SiteSettings
        fields = [
            "name",
            "tagline",
            "logo",
            "logo_light",
            "favicon",
            "footer_description",
            "phone",
            "email",
            "address",
            "hours",
            "abn",
            "map_address",
            "map_embed_url",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["footer_description"].widget.attrs["rows"] = 4
        self.fields["name"].required = True
        _style(self.fields)
        for name in ("logo", "logo_light", "favicon"):
            self.fields[name].widget.attrs["class"] = "form-control"

    def clean_phone(self):
        """Warn early rather than silently producing a broken tel: link."""
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not any(character.isdigit() for character in phone):
            raise forms.ValidationError("That doesn't look like a phone number.")
        return phone


class SocialLinkForm(forms.ModelForm):
    class Meta:
        model = SocialLink
        fields = ["platform", "url", "is_published", "order"]
        widgets = {
            "platform": forms.Select(attrs={"class": SELECT}),
            "url": forms.URLInput(
                attrs={"class": INPUT, "placeholder": "https://facebook.com/yourpage"}
            ),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": INPUT}),
        }

    def has_changed(self):
        """The trailing blank row is rendered with order=0, so the browser
        posts it and Django reads that as a change - then rejects the row for
        having no platform. A new row with neither a platform nor a URL is
        genuinely empty, whatever the order box says."""
        if self.instance.pk is None:
            platform = self.data.get(self.add_prefix("platform"), "")
            url = self.data.get(self.add_prefix("url"), "")
            if not platform and not url:
                return False
        return super().has_changed()


SocialLinkFormSet = forms.modelformset_factory(
    SocialLink, form=SocialLinkForm, extra=1, can_delete=True
)
