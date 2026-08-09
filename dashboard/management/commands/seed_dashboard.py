"""Populate the dashboard with sample data for local development.

    python manage.py seed_dashboard
    python manage.py seed_dashboard --clear    # remove what this command created

Creates two roles with sensible permission sets, a non-superuser staff account
for each, and a spread of enquiries across the last fortnight so the charts and
filters have something to show. Safe to re-run: it is idempotent.
"""

import random
from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from pages.models import Enquiry

ROLES = {
    "Enquiry Handler": [
        ("pages", "enquiry", ["view_enquiry", "change_enquiry"]),
    ],
    "Team Manager": [
        ("pages", "enquiry", ["view_enquiry", "change_enquiry", "delete_enquiry"]),
        ("auth", "user", ["view_user", "add_user", "change_user"]),
        ("auth", "group", ["view_group"]),
    ],
}

STAFF = [
    ("phandler", "Priya", "Kaur", "priya@rightwaysupportservices.com.au", "Enquiry Handler"),
    ("mmanager", "Michael", "Brown", "michael@rightwaysupportservices.com.au", "Team Manager"),
]

SAMPLE_ENQUIRIES = [
    ("Dana Whitfield", "dana@example.com", "0470 111 222",
     "I would like to book a free consultation for my son. He has an NDIS plan "
     "and we are looking for support with community access."),
    ("Tom Alvarez", "tom.alvarez@example.com", "0412 998 100",
     "Do you provide personal care support in Highfields? My mother needs help "
     "with daily activities three mornings a week."),
    ("Rebecca Lin", "r.lin@example.com", "",
     "Hi, I am a support coordinator with a participant looking for home and "
     "shared living options. Could you send through your service agreement?"),
    ("Ahmed Haddad", "ahmed.h@example.com", "0433 220 019",
     "What are your rates for household tasks? I have plan-managed funding."),
    ("Grace O'Donnell", "grace.od@example.com", "0455 777 331",
     "I am interested in the support worker role advertised on your careers "
     "page. Is it still open?"),
    ("Nina Petrov", "nina.p@example.com", "0466 512 908",
     "Could someone call me about transport support? I need regular trips to "
     "medical appointments in Toowoomba."),
    ("Colin Bracewell", "colin.b@example.com", "",
     "My NDIS plan was just approved and I am not sure where to start. Can you "
     "explain how support coordination works?"),
    ("Yuki Tanaka", "yuki.tanaka@example.com", "0401 664 220",
     "Do you have female support workers available on weekends?"),
    ("Marcus Reid", "m.reid@example.com", "0478 302 115",
     "Following up on my enquiry from last week about life skills development."),
    ("Sana Iqbal", "sana.iqbal@example.com", "0490 118 776",
     "Please send information about your capacity building services."),
]

# Sample rows are identified by their email addresses rather than a marker
# written into a user-visible field, so --clear stays precise without
# putting bookkeeping text in front of staff.
SAMPLE_EMAILS = [row[1] for row in SAMPLE_ENQUIRIES]


class Command(BaseCommand):
    help = "Create sample roles, staff users and enquiries for the dashboard."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the sample data instead of creating it.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            return self._clear()
        self._create()

    # ------------------------------------------------------------------ create

    def _create(self):
        rng = random.Random(20260808)  # fixed seed -> reproducible sample data

        for name, specs in ROLES.items():
            group, created = Group.objects.get_or_create(name=name)
            perms = []
            for app_label, model, codenames in specs:
                found = Permission.objects.filter(
                    content_type__app_label=app_label,
                    content_type__model=model,
                    codename__in=codenames,
                )
                missing = set(codenames) - {p.codename for p in found}
                if missing:
                    raise CommandError(
                        f"Missing permissions {sorted(missing)} - run migrate first."
                    )
                perms.extend(found)
            group.permissions.set(perms)
            self.stdout.write(
                f"  {'created' if created else 'updated'} role: {name} "
                f"({len(perms)} permissions)"
            )

        for username, first, last, email, role in STAFF:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": email,
                    "is_staff": True,
                },
            )
            if created:
                user.set_password("dashboard-dev-2026")
                user.save()
            user.groups.set([Group.objects.get(name=role)])
            self.stdout.write(
                f"  {'created' if created else 'updated'} user: {username} ({role})"
            )

        now = timezone.now()
        statuses = [
            Enquiry.Status.NEW,
            Enquiry.Status.NEW,
            Enquiry.Status.IN_PROGRESS,
            Enquiry.Status.CLOSED,
        ]
        handlers = list(User.objects.filter(username__in=[s[0] for s in STAFF]))
        made = 0

        for index, (name, email, phone, message) in enumerate(SAMPLE_ENQUIRIES):
            if Enquiry.objects.filter(email=email).exists():
                continue
            status = statuses[index % len(statuses)]
            enquiry = Enquiry.objects.create(
                name=name,
                email=email,
                phone=phone,
                message=message,
                status=status,
                handled_by=(
                    rng.choice(handlers)
                    if status != Enquiry.Status.NEW and handlers
                    else None
                ),
            )
            # created_at is auto_now_add, so backdate it with an explicit update.
            Enquiry.objects.filter(pk=enquiry.pk).update(
                created_at=now - timedelta(days=rng.randint(0, 13), hours=rng.randint(0, 23))
            )
            made += 1

        self.stdout.write(f"  created {made} enquiries")
        self.stdout.write(
            self.style.SUCCESS(
                "\nSample data ready. Staff logins: "
                + ", ".join(s[0] for s in STAFF)
                + "  password: dashboard-dev-2026"
            )
        )
        self.stdout.write("Remove it again with: manage.py seed_dashboard --clear")

    # ------------------------------------------------------------------- clear

    def _clear(self):
        enquiries = Enquiry.objects.filter(email__in=SAMPLE_EMAILS)
        users = User.objects.filter(username__in=[s[0] for s in STAFF])
        roles = Group.objects.filter(name__in=ROLES)

        # Counted before deleting: delete() reports cascaded rows too, which
        # would make the summary look inflated.
        counts = (enquiries.count(), users.count(), roles.count())
        for queryset in (enquiries, users, roles):
            queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Removed sample data (%d enquiries, %d users, %d roles)." % counts
            )
        )
