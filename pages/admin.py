from django.contrib import admin

from .models import (
    Application,
    Consultation,
    Enquiry,
    Service,
    SiteSettings,
    SocialLink,
    TeamMember,
    Vacancy,
)


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    """Kept for the fallback Django admin at /admin/.

    Day-to-day enquiry handling happens in the staff dashboard.
    """

    list_display = ("name", "email", "status", "handled_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "phone", "message", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Kept for the fallback Django admin at /admin/.

    Day-to-day editing happens in the staff dashboard.
    """

    list_display = ("title", "slug", "order", "is_published", "show_in_footer")
    list_filter = ("is_published", "show_in_footer")
    list_editable = ("order", "is_published")
    search_fields = ("title", "summary", "description", "body")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("title", "employment_type", "location", "closing_date", "is_published")
    list_filter = ("is_published", "employment_type")
    search_fields = ("title", "summary", "description")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Resumes are deliberately not downloadable from here.

    The dashboard serves them through a permission-checked view; exposing a
    second path would widen who can read applicants' personal information.
    """

    list_display = ("full_name", "role_label", "status", "handled_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "email", "cover_letter")
    readonly_fields = (
        "vacancy", "vacancy_title", "full_name", "email", "phone",
        "cover_letter", "resume", "created_at", "updated_at",
    )
    date_hierarchy = "created_at"


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    """Kept for the fallback Django admin. Confirming a time (and sending the
    participant their confirmation email) happens in the dashboard."""

    list_display = (
        "reference", "full_name", "delivery", "preferred_date", "status", "scheduled_for",
    )
    list_filter = ("status", "delivery", "plan_status")
    search_fields = ("reference", "full_name", "email", "participant_name")
    readonly_fields = ("reference", "created_at", "updated_at", "confirmation_sent_at")
    date_hierarchy = "created_at"


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "order", "is_published")
    list_filter = ("is_published",)
    list_editable = ("order", "is_published")
    search_fields = ("name", "role", "bio")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Singleton - adding a second row or deleting the only one is blocked."""

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("platform", "url", "order", "is_published")
    list_editable = ("order", "is_published")
