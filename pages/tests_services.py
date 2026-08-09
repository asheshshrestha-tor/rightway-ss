"""The public side of the database-backed services module."""

from django.test import TestCase
from django.urls import reverse

from .models import Service


class ServiceModelTests(TestCase):
    def test_migration_ported_the_original_services(self):
        """The five hardcoded services must survive the move to the database."""
        slugs = list(Service.objects.values_list("slug", flat=True))
        for expected in [
            "personal-care",
            "household-tasks",
            "community-access",
            "home-shared-living",
            "transport",
        ]:
            self.assertIn(expected, slugs)

    def test_slug_is_generated_from_title(self):
        service = Service.objects.create(
            title="Overnight Support", summary="s", description="d"
        )
        self.assertEqual(service.slug, "overnight-support")

    def test_slug_collisions_get_a_suffix(self):
        Service.objects.create(title="Respite Care", summary="s", description="d")
        second = Service.objects.create(
            title="Respite Care", summary="s", description="d"
        )
        self.assertEqual(second.slug, "respite-care-2")

    def test_explicit_slug_is_kept(self):
        service = Service.objects.create(
            title="Allied Health", slug="therapy", summary="s", description="d"
        )
        self.assertEqual(service.slug, "therapy")

    def test_image_url_falls_back_to_a_slug_placeholder(self):
        service = Service.objects.get(slug="personal-care")
        self.assertEqual(service.image_url, "/static/images/service-personal-care.svg")

    def test_image_url_falls_back_to_the_generic_placeholder(self):
        """A service an administrator invents has no matching artwork, and must
        still render something rather than a broken image."""
        service = Service.objects.create(
            title="Brand New Service", summary="s", description="d"
        )
        self.assertEqual(service.image_url, "/static/images/service-placeholder.svg")

    def test_highlight_list_splits_and_trims(self):
        service = Service.objects.create(
            title="X", summary="s", description="d",
            highlights="  One  \n\n Two \n   \nThree",
        )
        self.assertEqual(service.highlight_list, ["One", "Two", "Three"])

    def test_ordering_is_by_order_then_title(self):
        Service.objects.all().delete()
        Service.objects.create(title="Zeta", summary="s", description="d", order=1)
        Service.objects.create(title="Alpha", summary="s", description="d", order=1)
        Service.objects.create(title="First", summary="s", description="d", order=0)
        self.assertEqual(
            [s.title for s in Service.objects.all()], ["First", "Alpha", "Zeta"]
        )


class ServicePageTests(TestCase):
    def setUp(self):
        self.service = Service.objects.get(slug="personal-care")

    def test_listing_shows_published_services(self):
        response = self.client.get(reverse("services"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.title)
        self.assertContains(response, self.service.get_absolute_url())

    def test_listing_hides_unpublished_services(self):
        hidden = Service.objects.create(
            title="Not Ready", summary="s", description="d", is_published=False
        )
        response = self.client.get(reverse("services"))
        self.assertNotContains(response, "Not Ready")
        self.assertNotIn(hidden, response.context["service_list"])

    def test_home_shows_four_featured_services(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(len(response.context["featured_services"]), 4)

    def test_detail_page_renders(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.title)
        self.assertContains(response, "What's Included")
        for item in self.service.highlight_list:
            self.assertContains(response, item)

    def test_detail_page_404s_for_unpublished(self):
        hidden = Service.objects.create(
            title="Hidden", summary="s", description="d", is_published=False
        )
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)

    def test_detail_page_404s_for_unknown_slug(self):
        response = self.client.get(
            reverse("service_detail", kwargs={"slug": "does-not-exist"})
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_page_lists_related_services_excluding_itself(self):
        response = self.client.get(self.service.get_absolute_url())
        related = response.context["related"]
        self.assertNotIn(self.service, related)
        self.assertLessEqual(len(related), 3)

    def test_detail_falls_back_to_description_without_a_body(self):
        service = Service.objects.create(
            title="Bodyless", summary="s", description="Only a description here."
        )
        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, "Only a description here.")

    def test_nav_and_footer_come_from_the_database(self):
        Service.objects.create(
            title="Brand New Service",
            summary="s",
            description="d",
            show_in_footer=True,
            order=99,
        )
        response = self.client.get(reverse("home"))
        # Appears in the header dropdown and the footer column.
        self.assertContains(response, "Brand New Service", count=2)

    def test_footer_excludes_services_flagged_off(self):
        Service.objects.create(
            title="Hidden From Footer",
            summary="s",
            description="d",
            show_in_footer=False,
            order=98,
        )
        response = self.client.get(reverse("home"))
        # Header dropdown only.
        self.assertContains(response, "Hidden From Footer", count=1)

    def test_unpublishing_removes_it_from_the_site(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Transport")

        Service.objects.filter(slug="transport").update(is_published=False)

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, ">Transport<")

    def test_dashboard_requests_skip_the_service_queries(self):
        """The public nav/footer are never rendered under /dashboard/, so the
        context processor should not pay for them there."""
        from pages.context_processors import site

        class FakeRequest:
            path = "/dashboard/anything/"

        context = site(FakeRequest())
        self.assertNotIn("nav_services", context)
        self.assertIn("site", context)
