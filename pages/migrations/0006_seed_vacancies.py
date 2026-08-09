"""Port the vacancies that used to be hardcoded in `pages.content`.

Inlined rather than imported, so the migration keeps working after that module
changes. Copy is expanded from the original one-line entries into full adverts.
"""

from django.db import migrations

VACANCIES = [
    {
        "slug": "support-worker",
        "title": "Support Worker",
        "employment_type": "casual_part_time",
        "location": "Toowoomba and surrounds",
        "summary": "Support participants with daily living, community access and personal care.",
        "description": (
            "As a Support Worker you are the person our participants see most. "
            "You will support people with disability with everyday activities, "
            "in their homes and out in the community, in a way that builds their "
            "confidence and independence.\n\n"
            "No two days look the same. You might support someone with their "
            "morning routine, help with the shopping, and then head out to a "
            "social group in the afternoon. We roster with consistency in mind "
            "so you build real relationships with the people you support."
        ),
        "responsibilities": (
            "Personal care and daily living support\n"
            "Community and social participation\n"
            "Meal preparation and household tasks\n"
            "Transport to appointments and activities\n"
            "Accurate progress notes and incident reporting"
        ),
        "requirements": (
            "NDIS Worker Screening Check (or willingness to obtain)\n"
            "Current First Aid and CPR certificate\n"
            "Driver's licence and comprehensively insured vehicle\n"
            "Certificate III in Individual Support (desirable, not essential)\n"
            "A genuine, patient and respectful approach"
        ),
        "order": 10,
    },
    {
        "slug": "support-coordinator",
        "title": "Support Coordinator",
        "employment_type": "full_time",
        "location": "Toowoomba, QLD",
        "summary": "Help participants understand and make the most of their NDIS plans.",
        "description": (
            "Support Coordinators help participants turn an NDIS plan into real, "
            "working support. You will build participants' understanding of their "
            "funding, connect them with the right providers, and step in when "
            "things need to change.\n\n"
            "You will carry your own caseload with the backing of an experienced "
            "team, and have genuine say in how we deliver coordination."
        ),
        "responsibilities": (
            "Coordinate supports across a participant caseload\n"
            "Build participant capacity to self-manage over time\n"
            "Liaise with providers, families and the NDIA\n"
            "Prepare reports for plan reviews\n"
            "Respond to changes in circumstance and risk"
        ),
        "requirements": (
            "Experience in support coordination or case management\n"
            "Sound working knowledge of the NDIS\n"
            "Relevant qualification in community services or allied health\n"
            "NDIS Worker Screening Check\n"
            "Strong written communication"
        ),
        "order": 20,
    },
    {
        "slug": "community-access-worker",
        "title": "Community Access Worker",
        "employment_type": "casual",
        "location": "Toowoomba and surrounds",
        "summary": "Support participants to get out, join in and build connections.",
        "description": (
            "This role is all about participation. You will support people to "
            "take part in social, recreational and community activities - from "
            "regular groups and classes to one-off outings - and help build the "
            "confidence that makes it easier next time.\n\n"
            "It suits someone energetic and encouraging who enjoys being out and "
            "about rather than behind a desk."
        ),
        "responsibilities": (
            "Plan and support community outings and activities\n"
            "Encourage social connection and new interests\n"
            "Support travel training and public transport confidence\n"
            "Assist with volunteering and work experience placements\n"
            "Record participation and progress toward goals"
        ),
        "requirements": (
            "NDIS Worker Screening Check\n"
            "Current First Aid and CPR certificate\n"
            "Driver's licence and comprehensively insured vehicle\n"
            "Availability across weekdays, evenings or weekends\n"
            "Enthusiasm and a genuinely inclusive attitude"
        ),
        "order": 30,
    },
    {
        "slug": "admin-assistant",
        "title": "Admin Assistant",
        "employment_type": "part_time",
        "location": "Toowoomba, QLD",
        "summary": "Keep the office running so our support teams can focus on participants.",
        "description": (
            "Our Admin Assistant keeps the day to day moving - answering "
            "enquiries, coordinating rosters, keeping records accurate and "
            "supporting the wider team with the paperwork that comes with being "
            "a registered NDIS provider.\n\n"
            "It is a varied role with plenty of contact with participants, "
            "families and support workers."
        ),
        "responsibilities": (
            "Answer phone and email enquiries\n"
            "Assist with rostering and scheduling\n"
            "Maintain participant and worker records\n"
            "Support invoicing and NDIS claiming\n"
            "General office administration"
        ),
        "requirements": (
            "Previous administration experience\n"
            "Confident with office software and databases\n"
            "Excellent attention to detail\n"
            "Discretion when handling confidential information\n"
            "NDIS Worker Screening Check (or willingness to obtain)"
        ),
        "order": 40,
    },
]


def create_vacancies(apps, schema_editor):
    Vacancy = apps.get_model("pages", "Vacancy")
    for entry in VACANCIES:
        Vacancy.objects.update_or_create(
            slug=entry["slug"], defaults={**entry, "is_published": True}
        )


def remove_vacancies(apps, schema_editor):
    Vacancy = apps.get_model("pages", "Vacancy")
    Vacancy.objects.filter(slug__in=[e["slug"] for e in VACANCIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0005_vacancy_application")]

    operations = [migrations.RunPython(create_vacancies, remove_vacancies)]
