"""Port the services that used to be hardcoded in `pages.content` into the DB.

The data is inlined rather than imported from `pages.content`, because a
migration must keep working after that module changes or goes away.
"""

from django.db import migrations

SERVICES = [
    {
        "slug": "personal-care",
        "title": "Personal Care",
        "summary": "Support with daily personal activities.",
        "description": (
            "Support with daily personal activities to help you feel comfortable "
            "and confident."
        ),
        "body": (
            "Personal care is about being supported with the everyday things in a "
            "way that protects your dignity and independence. Our support workers "
            "take the time to learn how you like things done, and work at your "
            "pace.\n\n"
            "We match you with workers you are comfortable with, and you are "
            "welcome to ask for a change at any time. Support can be scheduled as "
            "a regular routine or arranged around appointments and activities."
        ),
        "highlights": (
            "Showering, dressing and grooming\n"
            "Medication prompting and support\n"
            "Mobility and transfer assistance\n"
            "Meal support and assistance with eating\n"
            "Morning and evening routines"
        ),
        "icon": "personal-care",
        "order": 10,
    },
    {
        "slug": "household-tasks",
        "title": "Household Tasks",
        "summary": "Assistance with cleaning, laundry and more.",
        "description": (
            "Assistance with cleaning, laundry, meal preparation and other "
            "household tasks."
        ),
        "body": (
            "A home that is clean, safe and organised makes everything else "
            "easier. We help with the tasks that are difficult to manage on your "
            "own, and where you would like to build skills we do them alongside "
            "you rather than for you.\n\n"
            "Support can be a regular weekly visit or a hand during busier "
            "periods, whatever suits your plan and your routine."
        ),
        "highlights": (
            "General cleaning and tidying\n"
            "Laundry, washing and ironing\n"
            "Meal planning and preparation\n"
            "Grocery shopping and putting away\n"
            "Rubbish, recycling and yard tidying"
        ),
        "icon": "household",
        "order": 20,
    },
    {
        "slug": "community-access",
        "title": "Community Access",
        "summary": "Support to participate in community activities.",
        "description": (
            "Support to participate in social, recreational and community "
            "activities."
        ),
        "body": (
            "Being part of your community is central to living the life you "
            "choose. We support you to get out, try things, and build the "
            "connections and confidence that make it easier next time.\n\n"
            "That might be a regular social group, a class you have been meaning "
            "to join, or simply having someone alongside you while you find your "
            "feet somewhere new."
        ),
        "highlights": (
            "Social and recreational outings\n"
            "Sports, hobbies and interest groups\n"
            "Attending appointments and errands\n"
            "Volunteering and work experience\n"
            "Building confidence using public transport"
        ),
        "icon": "community-access",
        "order": 30,
    },
    {
        "slug": "home-shared-living",
        "title": "Home & Shared Living",
        "summary": "Safe and comfortable living support.",
        "description": (
            "Safe, comfortable and supportive living arrangements tailored to "
            "your needs."
        ),
        "body": (
            "Whether you live on your own or share with others, the right support "
            "at home makes independence realistic and sustainable. We work with "
            "you, your family and your support coordinator to shape an "
            "arrangement that fits.\n\n"
            "Support levels can change over time. We review regularly so what is "
            "in place still matches what you actually need."
        ),
        "highlights": (
            "Supported independent living (SIL)\n"
            "Short term and medium term accommodation\n"
            "Overnight and 24/7 support options\n"
            "Household routines and budgeting\n"
            "Building daily living skills"
        ),
        "icon": "shared-living",
        "order": 40,
    },
    {
        "slug": "transport",
        "title": "Transport",
        "summary": "Getting you where you need to be.",
        "description": (
            "Reliable transport to appointments, activities and everyday "
            "commitments."
        ),
        "body": (
            "Transport is often the difference between a plan on paper and a life "
            "actually lived. We help you get to appointments, work, study and "
            "social commitments safely and on time.\n\n"
            "Where your goal is to travel independently, we can support you to "
            "build up to that at a pace that feels safe."
        ),
        "highlights": (
            "Medical and allied health appointments\n"
            "Work, study and training\n"
            "Social and community activities\n"
            "Shopping and errands\n"
            "Travel training toward independence"
        ),
        "icon": "transport",
        "order": 50,
    },
]


def create_services(apps, schema_editor):
    Service = apps.get_model("pages", "Service")
    for entry in SERVICES:
        Service.objects.update_or_create(
            slug=entry["slug"],
            defaults={
                **entry,
                "is_published": True,
                "show_in_footer": True,
                "meta_description": entry["description"],
            },
        )


def remove_services(apps, schema_editor):
    Service = apps.get_model("pages", "Service")
    Service.objects.filter(slug__in=[entry["slug"] for entry in SERVICES]).delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0003_service")]

    operations = [migrations.RunPython(create_services, remove_services)]
