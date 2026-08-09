from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.models import Enquiry

# These tests create a lot of users, and PBKDF2 hashing dominates the runtime.
# Swapping in the fast hasher takes the suite from ~75s to ~3s. Scoped to the
# test classes below so the real setting is never weakened.
fast_passwords = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)


def make_user(username, *, staff=False, superuser=False, perms=(), **kwargs):
    user = User.objects.create_user(
        username, f"{username}@example.com", "pw-for-tests-1234", **kwargs
    )
    user.is_staff = staff or superuser
    user.is_superuser = superuser
    user.save()
    if perms:
        codenames = [p.split(".", 1)[1] for p in perms]
        user.user_permissions.set(Permission.objects.filter(codename__in=codenames))
    return user


@fast_passwords
class AccessTests(TestCase):
    """Everything under /dashboard/ is staff-only, and model permissions gate
    the individual sections on top of that."""

    GATED = [
        "dashboard:index",
        "dashboard:user_list",
        "dashboard:group_list",
        "dashboard:enquiry_list",
    ]

    def test_anonymous_is_redirected_to_login(self):
        for name in self.GATED:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("dashboard:login"), response.url)

    def test_non_staff_user_is_forbidden(self):
        make_user("visitor")
        self.client.login(username="visitor", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 403)

    def test_staff_without_permission_cannot_reach_user_admin(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")

        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:user_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:group_list")).status_code, 403)

    def test_permission_grants_access(self):
        make_user("viewer", staff=True, perms=["auth.view_user"])
        self.client.login(username="viewer", password="pw-for-tests-1234")

        self.assertEqual(self.client.get(reverse("dashboard:user_list")).status_code, 200)
        # add_user was not granted
        self.assertEqual(self.client.get(reverse("dashboard:user_create")).status_code, 403)

    def test_superuser_reaches_everything(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        for name in self.GATED:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_non_staff_cannot_log_in_to_the_dashboard(self):
        make_user("outsider")
        response = self.client.post(
            reverse("dashboard:login"),
            {"username": "outsider", "password": "pw-for-tests-1234"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not have dashboard access")


@fast_passwords
class NavigationTests(TestCase):
    def test_menu_hides_sections_the_user_cannot_use(self):
        make_user("basic", staff=True)
        self.client.login(username="basic", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        labels = [item["label"] for item in response.context["nav_items"]]
        self.assertIn("Overview", labels)
        self.assertNotIn("Access Control", labels)

    def test_menu_shows_sections_the_user_can_use(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        response = self.client.get(reverse("dashboard:index"))
        labels = [item["label"] for item in response.context["nav_items"]]
        self.assertEqual(
            labels,
            [
                "Overview",
                "Enquiries",
                "Website Content",
                "Recruitment",
                "Settings",
                "Access Control",
            ],
        )


@fast_passwords
class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_create_user_with_role(self):
        role = Group.objects.create(name="Enquiry Handler")
        response = self.client.post(
            reverse("dashboard:user_create"),
            {
                "username": "newbie",
                "first_name": "New",
                "last_name": "Person",
                "email": "newbie@example.com",
                "password1": "a-good-password",
                "password2": "a-good-password",
                "is_active": "on",
                "is_staff": "on",
                "groups": [role.pk],
            },
        )
        self.assertRedirects(response, reverse("dashboard:user_list"))

        user = User.objects.get(username="newbie")
        self.assertTrue(user.check_password("a-good-password"))
        self.assertTrue(user.is_staff)
        self.assertEqual(list(user.groups.all()), [role])

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(
            reverse("dashboard:user_create"),
            {
                "username": "nope",
                "email": "nope@example.com",
                "password1": "one-password",
                "password2": "another-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="nope").exists())

    def test_editing_without_a_password_keeps_the_existing_one(self):
        user = make_user("editme", staff=True)
        original = user.password

        response = self.client.post(
            reverse("dashboard:user_update", args=[user.pk]),
            {
                "username": "editme",
                "first_name": "Edited",
                "last_name": "",
                "email": "editme@example.com",
                "is_active": "on",
                "is_staff": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:user_list"))

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Edited")
        self.assertEqual(user.password, original)

    def test_cannot_delete_yourself(self):
        response = self.client.post(
            reverse("dashboard:user_delete", args=[self.admin.pk]), follow=True
        )
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertContains(response, "cannot delete the account you are signed in as")

    def test_delete_another_user(self):
        victim = make_user("goner")
        response = self.client.post(reverse("dashboard:user_delete", args=[victim.pk]))
        self.assertRedirects(response, reverse("dashboard:user_list"))
        self.assertFalse(User.objects.filter(pk=victim.pk).exists())

    def test_search_filters_the_list(self):
        make_user("findme", staff=True)
        make_user("hidden", staff=True)
        response = self.client.get(reverse("dashboard:user_list"), {"q": "findme"})
        usernames = [u.username for u in response.context["page_obj"]]
        self.assertEqual(usernames, ["findme"])


@fast_passwords
class RoleManagementTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

    def test_create_role_with_permissions(self):
        perms = Permission.objects.filter(
            content_type__app_label="pages", codename__in=["view_enquiry", "change_enquiry"]
        )
        self.assertEqual(perms.count(), 2)

        response = self.client.post(
            reverse("dashboard:group_create"),
            {"name": "Enquiry Handler", "permissions": [p.pk for p in perms]},
        )
        self.assertRedirects(response, reverse("dashboard:group_list"))

        group = Group.objects.get(name="Enquiry Handler")
        self.assertEqual(group.permissions.count(), 2)

    def test_role_permissions_actually_grant_access(self):
        group = Group.objects.create(name="Enquiry Handler")
        group.permissions.set(
            Permission.objects.filter(
                content_type__app_label="pages", codename="view_enquiry"
            )
        )
        member = make_user("member", staff=True)
        member.groups.add(group)

        self.client.logout()
        self.client.login(username="member", password="pw-for-tests-1234")

        self.assertEqual(self.client.get(reverse("dashboard:enquiry_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:user_list")).status_code, 403)

    def test_permission_groups_are_bucketed_by_model(self):
        response = self.client.get(reverse("dashboard:group_create"))
        buckets = response.context["form"].permission_groups()
        labels = [label for label, _ in buckets]
        self.assertIn("pages · enquiry", labels)
        # Every permission ends up in exactly one bucket.
        total = sum(len(boxes) for _, boxes in buckets)
        self.assertEqual(total, Permission.objects.count())

    def test_delete_role(self):
        group = Group.objects.create(name="Temporary")
        response = self.client.post(reverse("dashboard:group_delete", args=[group.pk]))
        self.assertRedirects(response, reverse("dashboard:group_list"))
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())


@fast_passwords
class EnquiryDashboardTests(TestCase):
    def setUp(self):
        make_user("boss", superuser=True)
        self.client.login(username="boss", password="pw-for-tests-1234")
        self.enquiry = Enquiry.objects.create(
            name="Dana Whitfield",
            email="dana@example.com",
            phone="0470 111 222",
            message="I would like to book a free consultation.",
        )

    def test_contact_form_submission_is_stored(self):
        self.client.logout()
        response = self.client.post(
            reverse("contact"),
            {
                "name": "Sam Rivers",
                "email": "sam@example.com",
                "phone": "",
                "message": "Please call me about support coordination.",
                "hp_reference": "",
            },
        )
        self.assertRedirects(response, reverse("contact"))
        stored = Enquiry.objects.get(email="sam@example.com")
        self.assertEqual(stored.status, Enquiry.Status.NEW)

    def test_honeypot_submission_is_quarantined_not_shown(self):
        self.client.logout()
        self.client.post(
            reverse("contact"),
            {
                "name": "Bot",
                "email": "bot@example.com",
                "message": "buy cheap things now please",
                "hp_reference": "http://spam.example",
            },
        )
        spam = Enquiry.objects.get(email="bot@example.com")
        self.assertEqual(spam.status, Enquiry.Status.SPAM)

        self.client.login(username="boss", password="pw-for-tests-1234")

        # Hidden from the default list and from the dashboard counts...
        listing = self.client.get(reverse("dashboard:enquiry_list"))
        self.assertNotIn(spam, listing.context["page_obj"].object_list)
        self.assertEqual(listing.context["spam_count"], 1)
        home = self.client.get(reverse("dashboard:index"))
        self.assertEqual(home.context["enquiries_total"], 1)

        # ...but reachable, so a false positive is never lost.
        filtered = self.client.get(reverse("dashboard:enquiry_list"), {"status": "spam"})
        self.assertIn(spam, filtered.context["page_obj"].object_list)

    def test_dashboard_reports_real_counts(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["enquiries_total"], 1)
        tile = next(t for t in response.context["tiles"] if t["label"] == "Enquiries")
        self.assertEqual(tile["value"], 1)

    def test_chart_series_is_zero_filled(self):
        response = self.client.get(reverse("dashboard:index"))
        chart = response.context["chart"]
        self.assertEqual(len(chart["labels"]), chart["days"])
        self.assertEqual(len(chart["values"]), chart["days"])
        self.assertEqual(chart["values"][-1], 1)  # today's enquiry
        self.assertEqual(chart["values"][0], 0)

    def test_update_status_and_assignee(self):
        handler = make_user("handler", staff=True)
        response = self.client.post(
            reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]),
            {
                "status": Enquiry.Status.IN_PROGRESS,
                "handled_by": handler.pk,
                "notes": "Called back, awaiting plan details.",
            },
        )
        self.assertRedirects(
            response, reverse("dashboard:enquiry_detail", args=[self.enquiry.pk])
        )
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.status, Enquiry.Status.IN_PROGRESS)
        self.assertEqual(self.enquiry.handled_by, handler)

    def test_view_only_user_cannot_update(self):
        make_user("readonly", staff=True, perms=["pages.view_enquiry"])
        self.client.logout()
        self.client.login(username="readonly", password="pw-for-tests-1234")

        response = self.client.post(
            reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]),
            {"status": Enquiry.Status.CLOSED},
            follow=True,
        )
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.status, Enquiry.Status.NEW)
        self.assertContains(response, "do not have permission")


@fast_passwords
class SeedCommandTests(TestCase):
    def test_seed_and_clear_round_trip(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_dashboard", stdout=StringIO())
        self.assertTrue(Group.objects.filter(name="Enquiry Handler").exists())
        self.assertTrue(User.objects.filter(username="phandler").exists())
        self.assertEqual(Enquiry.objects.count(), 10)

        # Re-running must not duplicate anything.
        call_command("seed_dashboard", stdout=StringIO())
        self.assertEqual(Enquiry.objects.count(), 10)
        self.assertEqual(User.objects.filter(username="phandler").count(), 1)

        call_command("seed_dashboard", "--clear", stdout=StringIO())
        self.assertEqual(Enquiry.objects.count(), 0)
        self.assertFalse(User.objects.filter(username="phandler").exists())
        self.assertFalse(Group.objects.filter(name="Enquiry Handler").exists())
