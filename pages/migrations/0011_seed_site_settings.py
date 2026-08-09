"""Move the hardcoded site details out of `pages.content` and into the database.

Values are inlined rather than imported so the migration keeps working after
that module changes.
"""

from django.db import migrations

SITE = {
    "name": "Rightway Support Services",
    "tagline": "Your Path, Our Support",
    "phone": "0470 522 587",
    "email": "arshdeep@rightwaysupportservices.com.au",
    "address": "Toowoomba, QLD 4350",
    "hours": "Mon - Fri, 8:00 AM - 5:00 PM",
    "abn": "",
    "map_address": "Toowoomba QLD 4350 Australia",
    "footer_description": (
        "Your Path, Our Support. A registered NDIS provider delivering "
        "person-centred disability support across Toowoomba and surrounding "
        "areas."
    ),
}

# Placeholders kept unpublished: they were "#" links in the old hardcoded list,
# so publishing them would put dead links in the footer.
SOCIAL = [
    ("facebook", 10),
    ("instagram", 20),
    ("linkedin", 30),
    ("x", 40),
    ("youtube", 50),
    ("whatsapp", 60),
]


def create_settings(apps, schema_editor):
    SiteSettings = apps.get_model("pages", "SiteSettings")
    SocialLink = apps.get_model("pages", "SocialLink")

    SiteSettings.objects.update_or_create(pk=1, defaults=SITE)

    for platform, order in SOCIAL:
        SocialLink.objects.get_or_create(
            platform=platform,
            defaults={"url": "", "order": order, "is_published": False},
        )


def remove_settings(apps, schema_editor):
    apps.get_model("pages", "SiteSettings").objects.filter(pk=1).delete()
    apps.get_model("pages", "SocialLink").objects.filter(
        platform__in=[platform for platform, _ in SOCIAL]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0010_sitesettings_sociallink")]

    operations = [migrations.RunPython(create_settings, remove_settings)]
