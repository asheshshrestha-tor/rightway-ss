"""Port the team members that used to be hardcoded in `pages.content`.

Inlined rather than imported, so the migration keeps working after that module
changes. The original entries were name + role only; bios and qualifications
are added here so the new profile pages have something to show.
"""

from django.db import migrations

TEAM = [
    {
        "slug": "arshdeep-singh",
        "name": "Arshdeep Singh",
        "role": "Director",
        "bio": (
            "Arshdeep founded Rightway Support Services after years of working "
            "alongside people with disability and seeing how much difference "
            "the right support makes when it is built around the person rather "
            "than the paperwork.\n\n"
            "He oversees the whole service and still meets most new "
            "participants personally at their first consultation."
        ),
        "qualifications": (
            "NDIS Worker Screening Check\n"
            "First Aid and CPR certified\n"
            "Over 8 years in disability support"
        ),
        "order": 10,
    },
    {
        "slug": "priya-kaur",
        "name": "Priya Kaur",
        "role": "Operations Manager",
        "bio": (
            "Priya makes sure the day to day runs smoothly - rosters, "
            "onboarding, and keeping our support workers well matched to the "
            "people they support.\n\n"
            "She is usually the person participants speak to when something "
            "needs to change at short notice."
        ),
        "qualifications": (
            "NDIS Worker Screening Check\n"
            "Certificate IV in Disability\n"
            "First Aid and CPR certified"
        ),
        "order": 20,
    },
    {
        "slug": "michael-brown",
        "name": "Michael Brown",
        "role": "Support Coordinator",
        "bio": (
            "Michael helps participants understand their NDIS plans and turn "
            "them into support that actually works week to week.\n\n"
            "He is particularly experienced with first plans, and with helping "
            "people build the confidence to self-manage over time."
        ),
        "qualifications": (
            "NDIS Worker Screening Check\n"
            "Bachelor of Social Work\n"
            "Support coordination specialist"
        ),
        "order": 30,
    },
    {
        "slug": "sarah-wilson",
        "name": "Sarah Wilson",
        "role": "Team Leader",
        "bio": (
            "Sarah leads our support worker team, running supervisions and "
            "training and stepping in on shift whenever she is needed.\n\n"
            "She is a strong believer that good support is built on "
            "consistency - the same familiar faces, week after week."
        ),
        "qualifications": (
            "NDIS Worker Screening Check\n"
            "Certificate IV in Disability\n"
            "Manual handling and positive behaviour support training"
        ),
        "order": 40,
    },
]


def create_team(apps, schema_editor):
    TeamMember = apps.get_model("pages", "TeamMember")
    for entry in TEAM:
        TeamMember.objects.update_or_create(
            slug=entry["slug"], defaults={**entry, "is_published": True}
        )


def remove_team(apps, schema_editor):
    TeamMember = apps.get_model("pages", "TeamMember")
    TeamMember.objects.filter(slug__in=[e["slug"] for e in TEAM]).delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0008_teammember")]

    operations = [migrations.RunPython(create_team, remove_team)]
