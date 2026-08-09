"""Site-wide settings: branding, contact details, footer, map, social links."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .consultation_models import next_business_day
from .models import Consultation, SiteSettings, SocialLink
from .site_models import australian_tel_href


class SingletonTests(TestCase):
    def test_migration_seeded_the_row_from_the_old_hardcoded_values(self):
        settings_row = SiteSettings.load()
        self.assertEqual(settings_row.name, "Rightway Support Services")
        self.assertEqual(settings_row.phone, "0470 522 587")
        self.assertEqual(settings_row.email, "arshdeep@rightwaysupportservices.com.au")
        self.assertEqual(settings_row.address, "Toowoomba, QLD 4350")
        self.assertEqual(settings_row.hours, "Mon - Fri, 8:00 AM - 5:00 PM")
        self.assertIn("registered NDIS provider", settings_row.footer_description)

    def test_there_is_only_ever_one_row(self):
        SiteSettings.objects.create(name="Second")
        self.assertEqual(SiteSettings.objects.count(), 1)
        # The second save overwrote row 1 rather than adding a row.
        self.assertEqual(SiteSettings.load().name, "Second")

    def test_load_creates_the_row_if_it_is_missing(self):
        SiteSettings.objects.all().delete()
        settings_row = SiteSettings.load()
        self.assertEqual(settings_row.pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_delete_is_refused(self):
        with self.assertRaises(RuntimeError):
            SiteSettings.load().delete()


class DerivedValueTests(TestCase):
    def test_phone_href_is_built_from_the_number(self):
        cases = [
            ("0470 522 587", "tel:+61470522587"),
            ("07 4632 1000", "tel:+61746321000"),
            ("+61 470 522 587", "tel:+61470522587"),
            ("", ""),
        ]
        for entered, expected in cases:
            with self.subTest(phone=entered):
                self.assertEqual(australian_tel_href(entered), expected)

    def test_changing_the_phone_changes_the_link(self):
        settings_row = SiteSettings.load()
        settings_row.phone = "0400 111 222"
        settings_row.save()
        self.assertEqual(SiteSettings.load().phone_href, "tel:+61400111222")

    def test_map_url_is_built_from_the_address(self):
        settings_row = SiteSettings.load()
        self.assertIn("Toowoomba", settings_row.map_url)
        self.assertIn("output=embed", settings_row.map_url)

    def test_map_address_overrides_the_postal_address(self):
        settings_row = SiteSettings.load()
        settings_row.map_address = "123 Ruthven St Toowoomba"
        settings_row.save()
        self.assertIn("Ruthven", SiteSettings.load().map_url)

    def test_explicit_embed_url_wins(self):
        settings_row = SiteSettings.load()
        settings_row.map_embed_url = "https://www.google.com/maps/embed?pb=custom"
        settings_row.save()
        self.assertEqual(SiteSettings.load().map_url, "https://www.google.com/maps/embed?pb=custom")

    def test_branding_falls_back_to_the_shipped_files(self):
        settings_row = SiteSettings.load()
        self.assertEqual(settings_row.logo_url, "/static/images/logo.png")
        self.assertEqual(settings_row.logo_light_url, "/static/images/logo-light.png")
        self.assertEqual(settings_row.favicon_url, "/static/images/favicon-32.png")

    def test_initials_for_the_dashboard_mark(self):
        self.assertEqual(SiteSettings.load().initials, "RS")


class PublicSiteTests(TestCase):
    def test_contact_details_come_from_the_settings(self):
        settings_row = SiteSettings.load()
        settings_row.phone = "0400 111 222"
        settings_row.email = "hello@example.com"
        settings_row.address = "Highfields, QLD 4352"
        settings_row.hours = "Mon - Sat, 9:00 AM - 4:00 PM"
        settings_row.save()

        response = self.client.get(reverse("contact"))
        for value in ("0400 111 222", "hello@example.com", "Highfields, QLD 4352", "Mon - Sat"):
            with self.subTest(value=value):
                self.assertContains(response, value)
        self.assertContains(response, "tel:+61400111222")

    def test_footer_description_is_editable(self):
        settings_row = SiteSettings.load()
        settings_row.footer_description = "A brand new description for the footer."
        settings_row.save()
        self.assertContains(
            self.client.get(reverse("home")), "A brand new description for the footer."
        )

    def test_blank_footer_description_renders_nothing(self):
        settings_row = SiteSettings.load()
        settings_row.footer_description = ""
        settings_row.save()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "registered NDIS provider delivering")

    def test_site_name_flows_into_titles(self):
        settings_row = SiteSettings.load()
        settings_row.name = "Brand New Name"
        settings_row.save()
        self.assertContains(self.client.get(reverse("home")), "Brand New Name")

    def test_abn_appears_only_when_set(self):
        self.assertNotContains(self.client.get(reverse("home")), "ABN")

        settings_row = SiteSettings.load()
        settings_row.abn = "12 345 678 901"
        settings_row.save()
        self.assertContains(self.client.get(reverse("home")), "ABN 12 345 678 901")

    def test_favicon_falls_back_and_then_follows_an_upload(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "/static/images/favicon-32.png")


class SocialLinkTests(TestCase):
    def test_seeded_placeholders_are_unpublished(self):
        """Seeded off, so the footer starts clean until someone opts in."""
        self.assertEqual(SocialLink.objects.count(), 6)
        self.assertEqual(SocialLink.objects.published().count(), 0)

    def test_footer_hides_the_column_when_nothing_is_published(self):
        self.assertNotContains(self.client.get(reverse("home")), "Follow Us")

    def test_publishing_a_link_shows_it(self):
        SocialLink.objects.filter(platform="facebook").update(
            url="https://facebook.com/rightway", is_published=True
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Follow Us")
        self.assertContains(response, "https://facebook.com/rightway")
        self.assertContains(response, "#i-facebook")

    def test_published_with_no_url_still_shows_the_icon(self):
        """A ticked row appears even before an address is known - the icon is
        the point, and `href` falls back to "#" rather than an empty link."""
        SocialLink.objects.filter(platform="instagram").update(
            url="", is_published=True
        )
        self.assertEqual(SocialLink.objects.published().count(), 1)

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Follow Us")
        self.assertContains(response, "#i-instagram")
        self.assertContains(response, 'href="#"')
        # Marked up as a placeholder rather than a working link.
        self.assertContains(response, 'aria-disabled="true"')

    def test_href_falls_back_to_a_hash(self):
        link = SocialLink.objects.get(platform="instagram")
        self.assertEqual(link.href, "#")
        self.assertFalse(link.has_link)

        link.url = "https://instagram.com/rightway"
        link.save()
        self.assertEqual(link.href, "https://instagram.com/rightway")
        self.assertTrue(link.has_link)

    def test_a_real_link_opens_in_a_new_tab(self):
        SocialLink.objects.filter(platform="facebook").update(
            url="https://facebook.com/rightway", is_published=True
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'rel="noopener"')
        self.assertNotContains(response, 'aria-disabled="true"')

    def test_unticked_rows_stay_hidden_whatever_the_url(self):
        SocialLink.objects.filter(platform="youtube").update(
            url="https://youtube.com/rightway", is_published=False
        )
        self.assertNotContains(
            self.client.get(reverse("home")), "youtube.com/rightway"
        )

    def test_ordering_is_respected(self):
        SocialLink.objects.filter(platform="youtube").update(
            url="https://youtube.com/a", is_published=True, order=1
        )
        SocialLink.objects.filter(platform="facebook").update(
            url="https://facebook.com/b", is_published=True, order=2
        )
        self.assertEqual(
            [link.platform for link in SocialLink.objects.published()],
            ["youtube", "facebook"],
        )

    def test_icon_matches_the_sprite_id(self):
        for link in SocialLink.objects.all():
            with self.subTest(platform=link.platform):
                self.assertEqual(link.icon, link.platform)


class OutgoingMailTests(TestCase):
    """Changing the contact email must change where enquiries actually go."""

    def test_enquiry_notification_uses_the_settings_email(self):
        settings_row = SiteSettings.load()
        settings_row.email = "newinbox@example.com"
        settings_row.save()

        self.client.post(
            reverse("contact"),
            {
                "name": "Dana",
                "email": "dana@example.com",
                "phone": "",
                "message": "I would like to book a consultation.",
                "hp_reference": "",
            },
        )
        self.assertEqual(mail.outbox[0].to, ["newinbox@example.com"])

    def test_consultation_notification_uses_the_settings_email(self):
        settings_row = SiteSettings.load()
        settings_row.email = "newinbox@example.com"
        settings_row.save()

        self.client.post(
            reverse("consultation"),
            {
                "full_name": "Dana Whitfield",
                "email": "dana@example.com",
                "phone": "0470 111 222",
                "enquirer_type": Consultation.Enquirer.SELF,
                "plan_status": Consultation.PlanStatus.UNSURE,
                "delivery": Consultation.Delivery.PHONE,
                "preferred_date": next_business_day().isoformat(),
                "preferred_window": "morning",
            },
        )
        # The acknowledgement subject also contains "request", so match the
        # office notification on its prefix.
        office = [
            message
            for message in mail.outbox
            if message.subject.startswith("Consultation request")
        ]
        self.assertEqual(office[0].to, ["newinbox@example.com"])

    def test_consultation_email_quotes_the_settings_phone(self):
        settings_row = SiteSettings.load()
        settings_row.phone = "0400 999 888"
        settings_row.save()

        self.client.post(
            reverse("consultation"),
            {
                "full_name": "Dana Whitfield",
                "email": "dana@example.com",
                "phone": "0470 111 222",
                "enquirer_type": Consultation.Enquirer.SELF,
                "plan_status": Consultation.PlanStatus.UNSURE,
                "delivery": Consultation.Delivery.PHONE,
                "preferred_date": next_business_day().isoformat(),
                "preferred_window": "morning",
            },
        )
        acknowledgement = mail.outbox[0]
        self.assertIn("0400 999 888", acknowledgement.body)

    def test_falls_back_to_settings_py_when_the_email_is_cleared(self):
        from django.conf import settings as django_settings

        from .consultation_mail import office_email

        settings_row = SiteSettings.load()
        settings_row.email = ""
        settings_row.save()
        self.assertEqual(office_email(), django_settings.CONTACT_EMAIL)
