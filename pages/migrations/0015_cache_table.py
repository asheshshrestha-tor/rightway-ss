"""Create the cache table the rate limiter counts in.

`CACHES` uses Django's database backend, which needs a real table that no
migration creates - `manage.py createcachetable` does, and nothing on a deploy
runs it. Missing, the first cache read raises, and since all three public forms
check the rate limit before doing anything else, all three return a 500. A form
that errors for everyone is a worse failure than the flood the limit exists to
prevent, so it is created here instead of in a runbook step someone has to
remember.

`createcachetable` skips a table that already exists, so this is safe on a
database where it was created by hand.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command(
        "createcachetable",
        database=schema_editor.connection.alias,
        verbosity=0,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0014_application_resume_storage"),
    ]

    operations = [
        # Irreversible by choice: dropping the table on a rollback would throw
        # away live counters and break the forms again on the way back.
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
