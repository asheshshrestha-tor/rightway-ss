"""Sign out, forgot password, change password, account, and enquiry filters."""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from pages.models import Enquiry

from .tests import fast_passwords, make_user


@fast_passwords
class AuthFlowTests(TestCase):
    def setUp(self):
        self.user = make_user("staffer", staff=True)
        self.user.email = "staffer@example.com"
        self.user.save()

    # ------------------------------------------------------------- sign out

    def test_logout_ends_the_session(self):
        self.client.login(username="staffer", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 200)

        response = self.client.post(reverse("dashboard:logout"))
        self.assertRedirects(response, reverse("dashboard:login"))

        after = self.client.get(reverse("dashboard:index"))
        self.assertEqual(after.status_code, 302)
        self.assertIn(reverse("dashboard:login"), after.url)

    def test_logout_rejects_get(self):
        """Sign-out is POST only, so a stray link or a prefetch cannot end
        someone's session."""
        self.client.login(username="staffer", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(reverse("dashboard:logout")).status_code, 405)
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 200)

    # ------------------------------------------------------ forgot password

    def test_reset_email_is_sent_to_staff(self):
        response = self.client.post(
            reverse("dashboard:password_reset"), {"email": "staffer@example.com"}
        )
        self.assertRedirects(response, reverse("dashboard:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/dashboard/password-reset/", mail.outbox[0].body)

    def test_reset_refused_for_non_staff_without_leaking_that_fact(self):
        make_user("public")
        User.objects.filter(username="public").update(email="public@example.com")

        response = self.client.post(
            reverse("dashboard:password_reset"), {"email": "public@example.com"}
        )
        # Same confirmation as a valid address - no account enumeration...
        self.assertRedirects(response, reverse("dashboard:password_reset_done"))
        # ...but nothing is actually sent.
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_address_looks_identical(self):
        response = self.client.post(
            reverse("dashboard:password_reset"), {"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("dashboard:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_sets_a_new_password(self):
        self.client.post(
            reverse("dashboard:password_reset"), {"email": "staffer@example.com"}
        )
        body = mail.outbox[0].body
        line = next(l for l in body.splitlines() if "/dashboard/password-reset/" in l)
        link = line[line.index("/dashboard/"):].strip()

        # Django swaps the token for a session-held one, then redirects.
        response = self.client.get(link, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["validlink"])

        response = self.client.post(
            response.request["PATH_INFO"],
            {"new_password1": "brand-new-pass-99", "new_password2": "brand-new-pass-99"},
        )
        self.assertRedirects(response, reverse("dashboard:password_reset_complete"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pass-99"))

    def test_tampered_reset_link_shows_the_expired_screen(self):
        response = self.client.get(
            reverse(
                "dashboard:password_reset_confirm",
                kwargs={"uidb64": "MQ", "token": "bad-token-here"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])
        self.assertContains(response, "This link has expired")

    # ------------------------------------------------------ change password

    def test_change_password_requires_the_current_one(self):
        self.client.login(username="staffer", password="pw-for-tests-1234")
        response = self.client.post(
            reverse("dashboard:password_change"),
            {
                "old_password": "wrong-password",
                "new_password1": "another-new-pass-1",
                "new_password2": "another-new-pass-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("pw-for-tests-1234"))

    def test_change_password_and_stay_signed_in(self):
        self.client.login(username="staffer", password="pw-for-tests-1234")
        response = self.client.post(
            reverse("dashboard:password_change"),
            {
                "old_password": "pw-for-tests-1234",
                "new_password1": "another-new-pass-1",
                "new_password2": "another-new-pass-1",
            },
        )
        self.assertRedirects(response, reverse("dashboard:account"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("another-new-pass-1"))
        # Session survives the change.
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 200)

    # -------------------------------------------------------------- account

    def test_account_page_needs_no_user_permission(self):
        """A plain staff member manages their own profile without
        auth.change_user, which governs editing other people."""
        self.client.login(username="staffer", password="pw-for-tests-1234")
        self.assertEqual(self.client.get(reverse("dashboard:account")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:user_list")).status_code, 403)

    def test_account_updates_own_details(self):
        self.client.login(username="staffer", password="pw-for-tests-1234")
        response = self.client.post(
            reverse("dashboard:account"),
            {"first_name": "Sam", "last_name": "Rivers", "email": "sam@example.com"},
        )
        self.assertRedirects(response, reverse("dashboard:account"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Sam")
        self.assertEqual(self.user.email, "sam@example.com")

    def test_account_cannot_escalate_privileges(self):
        """is_staff / is_superuser / groups are not editable from here."""
        self.client.login(username="staffer", password="pw-for-tests-1234")
        self.client.post(
            reverse("dashboard:account"),
            {
                "first_name": "Sam",
                "last_name": "Rivers",
                "email": "sam@example.com",
                "is_superuser": "on",
                "is_staff": "on",
            },
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)


@fast_passwords
class EnquiryFilterTests(TestCase):
    def setUp(self):
        self.boss = make_user("boss", superuser=True)
        self.handler = make_user("handler", staff=True)
        self.client.login(username="boss", password="pw-for-tests-1234")

        self.mine = Enquiry.objects.create(
            name="Mine", email="mine@example.com", message="x" * 20, handled_by=self.boss
        )
        self.theirs = Enquiry.objects.create(
            name="Theirs",
            email="theirs@example.com",
            message="x" * 20,
            handled_by=self.handler,
        )
        self.nobodys = Enquiry.objects.create(
            name="Nobodys", email="nobody@example.com", message="x" * 20
        )

    def rows(self, **params):
        response = self.client.get(reverse("dashboard:enquiry_list"), params)
        return set(response.context["page_obj"].object_list)

    def test_no_filter_shows_everything(self):
        self.assertEqual(self.rows(), {self.mine, self.theirs, self.nobodys})

    def test_filter_assigned_to_me(self):
        self.assertEqual(self.rows(assigned="me"), {self.mine})

    def test_filter_unassigned(self):
        self.assertEqual(self.rows(assigned="unassigned"), {self.nobodys})

    def test_filter_by_specific_staff_member(self):
        self.assertEqual(self.rows(assigned=str(self.handler.pk)), {self.theirs})

    def test_unassigned_count_is_reported(self):
        response = self.client.get(reverse("dashboard:enquiry_list"))
        self.assertEqual(response.context["unassigned_count"], 1)

    def test_assignee_filter_combines_with_status(self):
        self.theirs.status = Enquiry.Status.CLOSED
        self.theirs.save()
        self.assertEqual(
            self.rows(assigned=str(self.handler.pk), status=Enquiry.Status.CLOSED),
            {self.theirs},
        )
        self.assertEqual(
            self.rows(assigned=str(self.handler.pk), status=Enquiry.Status.NEW), set()
        )

    def test_garbage_assigned_value_is_ignored_not_a_500(self):
        for value in ("../../etc", "999999", "abc", "None"):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse("dashboard:enquiry_list"), {"assigned": value}
                )
                self.assertEqual(response.status_code, 200)

    def test_filters_survive_pagination_links(self):
        response = self.client.get(
            reverse("dashboard:enquiry_list"), {"assigned": "me", "q": "Mine"}
        )
        querystring = response.context["querystring"]
        self.assertIn("assigned=me", querystring)
        self.assertIn("q=Mine", querystring)
        self.assertNotIn("page=", querystring)
