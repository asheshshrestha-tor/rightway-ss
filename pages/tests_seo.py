"""Search-engine metadata: sitemap, robots.txt, canonicals and structured data.

Structured data fails quietly - a malformed block is skipped in full and
nothing on the page looks wrong - so these tests parse it rather than checking
for substrings.
"""

import json
import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Service, SiteSettings, TeamMember, Vacancy
from .structured_data import opening_hours
from .templatetags.seo import ld_json

SCRIPT = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def schemas(response):
    """Every schema.org block on the page, parsed, keyed by @type."""
    html = response.content.decode()
    found = {}
    for block in SCRIPT.findall(html):
        data = json.loads(block)  # raises if we ever emit invalid JSON
        found[data["@type"]] = data
    return found


class RobotsTests(TestCase):
    def test_disallows_the_back_office_and_points_at_the_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

        body = response.content.decode()
        self.assertIn("Disallow: /dashboard/", body)
        self.assertIn("Disallow: /admin/", body)
        # Absolute, because a crawler reads robots.txt without page context.
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)


class SitemapTests(TestCase):
    def test_lists_public_pages_and_not_the_dashboard(self):
        body = self.client.get("/sitemap.xml").content.decode()

        self.assertIn("<loc>https://testserver/</loc>", body)
        self.assertIn("<loc>https://testserver/services/</loc>", body)
        self.assertNotIn("/dashboard/", body)
        self.assertNotIn("/admin/", body)

    def test_thank_you_page_is_excluded(self):
        """It is meaningless without the booking before it, and robots.txt
        already disallows it - listing it too would contradict that."""
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("thank-you", body)

    def test_unpublished_service_is_absent(self):
        Service.objects.create(
            title="Draft Service", summary="s", description="d", is_published=False
        )
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("draft-service", body)

    def test_closed_vacancy_is_absent(self):
        """A closed role still resolves, but advertising it to a crawler earns
        the site nothing."""
        Vacancy.objects.create(
            title="Expired Role",
            summary="s",
            description="d",
            is_published=True,
            closing_date=timezone.localdate() - timedelta(days=1),
        )
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("expired-role", body)


class CanonicalTests(TestCase):
    def test_every_public_page_declares_one_canonical(self):
        for name in ["home", "about", "services", "contact", "faq", "careers"]:
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                links = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
                self.assertEqual(len(links), 1, f"{name} should have exactly one")
                self.assertTrue(links[0].startswith("http"))

    def test_tracking_parameters_do_not_create_a_second_url(self):
        """A campaign link must still point search engines at the clean page."""
        html = self.client.get(
            reverse("services"), {"utm_source": "facebook"}
        ).content.decode()

        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1)
        self.assertEqual(canonical, "http://testserver/services/")


class OrganizationSchemaTests(TestCase):
    def test_business_details_appear_on_every_page(self):
        data = schemas(self.client.get(reverse("home")))["LocalBusiness"]

        site = SiteSettings.load()
        self.assertEqual(data["name"], site.name)
        self.assertEqual(data["telephone"], "+61470522587")
        self.assertEqual(data["address"]["addressLocality"], "Toowoomba")
        self.assertEqual(data["address"]["addressRegion"], "QLD")
        self.assertEqual(data["address"]["postalCode"], "4350")

    def test_logo_is_an_absolute_url(self):
        """A relative path here is ignored by every consumer of the data."""
        data = schemas(self.client.get(reverse("home")))["LocalBusiness"]
        self.assertTrue(data["logo"].startswith("http"))

    def test_social_profiles_are_listed_only_when_they_have_a_url(self):
        """Follow-us rows may be published with no address yet, and "#" is not
        a profile."""
        data = schemas(self.client.get(reverse("home")))["LocalBusiness"]
        for url in data.get("sameAs", []):
            self.assertNotIn("#", url)


class PageSchemaTests(TestCase):
    def test_service_page_describes_the_service(self):
        service = Service.objects.published().first()
        found = schemas(self.client.get(service.get_absolute_url()))

        self.assertEqual(found["Service"]["name"], service.title)
        self.assertIn("BreadcrumbList", found)
        self.assertEqual(len(found["BreadcrumbList"]["itemListElement"]), 3)

    def test_vacancy_page_is_a_job_posting(self):
        vacancy = Vacancy.objects.published().first()
        data = schemas(self.client.get(vacancy.get_absolute_url()))["JobPosting"]

        self.assertEqual(data["title"], vacancy.title)
        self.assertNotEqual(
            data["employmentType"],
            "OTHER",
            "employment types must map onto Google's vocabulary",
        )
        self.assertIn("hiringOrganization", data)
        self.assertIn("datePosted", data)

    def test_faq_page_lists_questions(self):
        data = schemas(self.client.get(reverse("faq")))["FAQPage"]

        self.assertGreater(len(data["mainEntity"]), 0)
        first = data["mainEntity"][0]
        self.assertEqual(first["@type"], "Question")
        self.assertTrue(first["acceptedAnswer"]["text"])

    def test_team_member_page_describes_a_person(self):
        member = TeamMember.objects.published().first()
        data = schemas(self.client.get(member.get_absolute_url()))["Person"]

        self.assertEqual(data["name"], member.name)
        self.assertEqual(data["jobTitle"], member.role)


class LdJsonTagTests(TestCase):
    def test_a_closing_script_tag_in_the_data_cannot_break_out(self):
        """Content is administrator-editable, so treat it as untrusted: an
        unescaped "</script>" would end the block and put the rest of the
        payload into the page as markup."""
        rendered = ld_json({"name": "Evil </script><img src=x onerror=alert(1)>"})

        self.assertNotIn("</script><img", rendered)
        self.assertIn("\\u003c", rendered)
        # Still valid JSON, and still says what it said.
        payload = SCRIPT.search(rendered).group(1)
        self.assertIn("Evil", json.loads(payload)["name"])

    def test_empty_data_renders_nothing(self):
        self.assertEqual(ld_json(None), "")
        self.assertEqual(ld_json({}), "")


class OpeningHoursTests(TestCase):
    def test_reads_the_format_the_site_uses(self):
        spec = opening_hours("Mon - Fri, 8:00 AM - 5:00 PM")[0]

        self.assertEqual(spec["opens"], "08:00")
        self.assertEqual(spec["closes"], "17:00")
        self.assertEqual(len(spec["dayOfWeek"]), 5)
        self.assertEqual(spec["dayOfWeek"][0], "Monday")

    def test_wording_it_cannot_read_is_omitted_rather_than_guessed(self):
        """Publishing wrong opening hours is worse than publishing none."""
        for value in ["By appointment", "Call us", "", None]:
            with self.subTest(value=value):
                self.assertIsNone(opening_hours(value))
