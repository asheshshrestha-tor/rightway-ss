"""The Meet Our Team section and individual profile pages."""

from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

from .models import TeamMember


class TeamMemberModelTests(TestCase):
    def test_migration_ported_the_original_four(self):
        slugs = set(TeamMember.objects.values_list("slug", flat=True))
        self.assertTrue(
            {
                "arshdeep-singh",
                "priya-kaur",
                "michael-brown",
                "sarah-wilson",
            }.issubset(slugs)
        )

    def test_roles_survived_the_move(self):
        self.assertEqual(
            TeamMember.objects.get(slug="arshdeep-singh").role, "Director"
        )
        self.assertEqual(
            TeamMember.objects.get(slug="priya-kaur").role, "Operations Manager"
        )

    def test_slug_generated_and_deduplicated(self):
        first = TeamMember.objects.create(name="Alex Chen", role="Support Worker")
        second = TeamMember.objects.create(name="Alex Chen", role="Team Leader")
        self.assertEqual(first.slug, "alex-chen")
        self.assertEqual(second.slug, "alex-chen-2")

    def test_photo_falls_back_to_the_slug_placeholder(self):
        member = TeamMember.objects.get(slug="priya-kaur")
        self.assertEqual(member.photo_url, static("images/team-priya-kaur.svg"))

    def test_photo_falls_back_to_the_generic_placeholder(self):
        """Someone added by an administrator has no matching artwork and must
        still render rather than showing a broken image."""
        member = TeamMember.objects.create(name="Brand New", role="Support Worker")
        self.assertEqual(member.photo_url, static("images/team-placeholder.svg"))

    def test_qualification_list_splits_and_trims(self):
        member = TeamMember.objects.create(
            name="X", role="Y", qualifications="  One \n\n Two \n   \nThree"
        )
        self.assertEqual(member.qualification_list, ["One", "Two", "Three"])

    def test_initials(self):
        self.assertEqual(
            TeamMember.objects.get(slug="arshdeep-singh").initials, "AS"
        )
        self.assertEqual(TeamMember.objects.create(name="Cher", role="X").initials, "C")

    def test_ordering_is_by_order_then_name(self):
        TeamMember.objects.all().delete()
        TeamMember.objects.create(name="Zoe", role="X", order=1)
        TeamMember.objects.create(name="Adam", role="X", order=1)
        TeamMember.objects.create(name="First", role="X", order=0)
        self.assertEqual(
            [m.name for m in TeamMember.objects.all()], ["First", "Adam", "Zoe"]
        )


class TeamPageTests(TestCase):
    def setUp(self):
        self.member = TeamMember.objects.get(slug="michael-brown")

    def test_about_page_lists_published_members(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Michael Brown")
        self.assertContains(response, self.member.get_absolute_url())

    def test_about_page_hides_unpublished(self):
        hidden = TeamMember.objects.create(
            name="Not Yet Announced", role="Support Worker", is_published=False
        )
        response = self.client.get(reverse("about"))
        self.assertNotContains(response, "Not Yet Announced")
        self.assertNotIn(hidden, response.context["team"])

    def test_profile_page_renders(self):
        response = self.client.get(self.member.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.name)
        self.assertContains(response, self.member.role)
        for item in self.member.qualification_list:
            self.assertContains(response, item)

    def test_profile_404s_for_unpublished(self):
        hidden = TeamMember.objects.create(
            name="Hidden Person", role="X", is_published=False
        )
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)

    def test_profile_404s_for_unknown_slug(self):
        response = self.client.get(
            reverse("team_member", kwargs={"slug": "nobody-here"})
        )
        self.assertEqual(response.status_code, 404)

    def test_profile_lists_colleagues_excluding_self(self):
        response = self.client.get(self.member.get_absolute_url())
        colleagues = response.context["colleagues"]
        self.assertNotIn(self.member, colleagues)
        self.assertLessEqual(len(colleagues), 4)

    def test_profile_without_a_bio_still_reads(self):
        member = TeamMember.objects.create(name="Terse Person", role="Support Worker")
        response = self.client.get(member.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "working as Support Worker")

    def test_unpublishing_removes_them_from_the_site(self):
        self.assertContains(self.client.get(reverse("about")), "Michael Brown")

        TeamMember.objects.filter(pk=self.member.pk).update(is_published=False)

        self.assertNotContains(self.client.get(reverse("about")), "Michael Brown")
        self.assertEqual(
            self.client.get(self.member.get_absolute_url()).status_code, 404
        )
