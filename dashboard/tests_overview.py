"""The dashboard overview must show only what the viewer is allowed to see.

A count is information in its own right: telling someone "12 users" when they
cannot open the user list still leaks how many users exist. So these tests
check the *absence* of blocks as carefully as their presence.
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pages.consultation_models import next_business_day
from pages.models import (
    Application,
    Consultation,
    Enquiry,
    Service,
    TeamMember,
    Vacancy,
)

from .tests import fast_passwords, make_user

INDEX = reverse("dashboard:index")

# Every tile, and the permission that earns it.
TILES = {
    "Consultations to confirm": "pages.view_consultation",
    "Enquiries": "pages.view_enquiry",
    "New applications": "pages.view_application",
    "Open vacancies": "pages.view_vacancy",
    "Users": "auth.view_user",
    "Roles": "auth.view_group",
}


def seed_everything():
    """One row in every module, so an unpermitted block would have something
    to leak if the gating were wrong."""
    Enquiry.objects.create(name="Dana", email="dana@example.com", message="x" * 20)
    Consultation.objects.create(
        full_name="Dana",
        email="dana@example.com",
        phone="0470 111 222",
        preferred_date=next_business_day(),
    )
    vacancy = Vacancy.objects.get(slug="support-worker")
    Application.objects.create(
        vacancy=vacancy,
        vacancy_title=vacancy.title,
        full_name="Jamie Reid",
        email="jamie@example.com",
        resume="resumes/x.pdf",
    )
    Group.objects.create(name="Enquiry Handler")


@fast_passwords
class OverviewPermissionTests(TestCase):
    def setUp(self):
        seed_everything()

    def sign_in(self, username, perms=()):
        make_user(username, staff=True, perms=list(perms))
        self.client.login(username=username, password="pw-for-tests-1234")
        return self.client.get(INDEX)

    def tile_labels(self, response):
        return [tile["label"] for tile in response.context["tiles"]]

    # -------------------------------------------------------- nothing at all

    def test_staff_with_no_permissions_sees_an_empty_state(self):
        response = self.sign_in("plain")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["nothing_to_show"])
        self.assertEqual(response.context["tiles"], [])
        # Phrase kept short: the sentence wraps across lines in the template.
        self.assertContains(response, "no sections have been")

    def test_staff_with_no_permissions_sees_no_counts_at_all(self):
        """The strong assertion: no module data reaches the template."""
        response = self.sign_in("plain")
        for key in (
            "chart",
            "status_counts",
            "recent_enquiries",
            "recent_applications",
            "recent_users",
            "roles",
            "upcoming_consultations",
            "enquiries_total",
        ):
            with self.subTest(key=key):
                self.assertIsNone(response.context.get(key))
        self.assertEqual(response.context["content_rows"], [])

    # -------------------------------------------------------------- tiles

    def test_each_tile_needs_its_own_permission(self):
        for label, perm in TILES.items():
            with self.subTest(tile=label):
                self.client.logout()
                response = self.sign_in(f"user-{perm.replace('.', '-')}", [perm])
                self.assertEqual(self.tile_labels(response), [label])

    def test_superuser_sees_every_tile(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        response = self.client.get(INDEX)
        self.assertEqual(set(self.tile_labels(response)), set(TILES))

    def test_tiles_link_to_the_screen_they_summarise(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        response = self.client.get(INDEX)
        for tile in response.context["tiles"]:
            with self.subTest(tile=tile["label"]):
                self.assertTrue(tile["url"].startswith("/dashboard/"))

    # ------------------------------------------------------------- panels

    def test_enquiry_chart_needs_the_enquiry_permission(self):
        without = self.sign_in("nochart")
        self.assertIsNone(without.context.get("chart"))
        self.assertNotContains(without, "kt_dashboard_enquiries_chart")
        # The chart script must not load either.
        self.assertNotContains(without, "enquiry-chart.js")

        self.client.logout()
        with_perm = self.sign_in("chart", ["pages.view_enquiry"])
        self.assertIsNotNone(with_perm.context["chart"])
        self.assertContains(with_perm, "kt_dashboard_enquiries_chart")
        self.assertContains(with_perm, "enquiry-chart.js")

    def test_recent_enquiries_needs_the_enquiry_permission(self):
        without = self.sign_in("noenq", ["pages.view_service"])
        self.assertNotContains(without, "Recent Enquiries")

        self.client.logout()
        with_perm = self.sign_in("enq", ["pages.view_enquiry"])
        self.assertContains(with_perm, "Recent Enquiries")
        self.assertContains(with_perm, "Dana")

    def test_applications_panel_needs_its_permission(self):
        without = self.sign_in("noapps", ["pages.view_enquiry"])
        self.assertNotContains(without, "Recent Applications")
        self.assertNotContains(without, "Jamie Reid")

        self.client.logout()
        with_perm = self.sign_in("apps", ["pages.view_application"])
        self.assertContains(with_perm, "Recent Applications")
        self.assertContains(with_perm, "Jamie Reid")

    def test_consultations_panel_needs_its_permission(self):
        booking = Consultation.objects.first()
        booking.status = Consultation.Status.CONFIRMED
        booking.scheduled_for = timezone.now() + timedelta(days=2)
        booking.save()

        without = self.sign_in("nocons", ["pages.view_enquiry"])
        self.assertNotContains(without, "Upcoming Consultations")

        self.client.logout()
        with_perm = self.sign_in("cons", ["pages.view_consultation"])
        self.assertContains(with_perm, "Upcoming Consultations")

    def test_users_panel_needs_the_user_permission(self):
        without = self.sign_in("nousers", ["pages.view_enquiry"])
        self.assertNotContains(without, "Newest Users")

        self.client.logout()
        with_perm = self.sign_in("users", ["auth.view_user"])
        self.assertContains(with_perm, "Newest Users")

    def test_roles_summary_needs_the_group_permission(self):
        without = self.sign_in("noroles", ["pages.view_enquiry"])
        self.assertNotContains(without, "Enquiry Handler")

        self.client.logout()
        with_perm = self.sign_in("roles", ["auth.view_group"])
        self.assertContains(with_perm, "Enquiry Handler")

    # ------------------------------------------------------- site content

    def test_content_rows_are_gated_individually(self):
        cases = [
            ("pages.view_service", "Services"),
            ("pages.view_teammember", "Team members"),
            ("pages.view_vacancy", "Vacancies"),
        ]
        for perm, label in cases:
            with self.subTest(row=label):
                self.client.logout()
                response = self.sign_in(f"c-{perm.replace('.', '-')}", [perm])
                labels = [row["label"] for row in response.context["content_rows"]]
                self.assertEqual(labels, [label])

    def test_content_rows_report_live_and_draft_counts(self):
        Service.objects.filter(slug="transport").update(is_published=False)
        TeamMember.objects.filter(slug="sarah-wilson").update(is_published=False)

        response = self.sign_in(
            "editor", ["pages.view_service", "pages.view_teammember"]
        )
        rows = {row["label"]: row for row in response.context["content_rows"]}

        self.assertEqual(rows["Services"]["live"], 4)
        self.assertEqual(rows["Services"]["draft"], 1)
        self.assertEqual(rows["Team members"]["live"], 3)
        self.assertEqual(rows["Team members"]["draft"], 1)

    # ------------------------------------------------------------ numbers

    def test_tile_values_are_accurate(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        tiles = {t["label"]: t["value"] for t in self.client.get(INDEX).context["tiles"]}

        self.assertEqual(tiles["Enquiries"], 1)
        self.assertEqual(tiles["Consultations to confirm"], 1)
        self.assertEqual(tiles["New applications"], 1)
        self.assertEqual(tiles["Open vacancies"], Vacancy.objects.open_now().count())
        self.assertEqual(tiles["Roles"], Group.objects.count())

    def test_spam_enquiries_are_excluded_from_the_tile(self):
        Enquiry.objects.create(
            name="Bot",
            email="bot@example.com",
            message="x" * 20,
            status=Enquiry.Status.SPAM,
        )
        response = self.sign_in("enq", ["pages.view_enquiry"])
        tile = next(t for t in response.context["tiles"] if t["label"] == "Enquiries")
        self.assertEqual(tile["value"], 1)
