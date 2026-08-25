"""Point `Application.resume` at a storage callable instead of an instance.

State only: a FileField is a varchar either way, and no stored path changes.

The field used to name `PrivateMediaStorage` directly, which meant the choice
of backend was recorded in the migration history. Naming the `private_storage`
function instead moves that choice to `settings.STORAGES["private"]`, so the
same code runs on the filesystem locally and on S3 in production without a
migration between them.
"""

import pages.vacancy_models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0013_alter_sociallink_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="application",
            name="resume",
            field=models.FileField(
                storage=pages.vacancy_models.private_storage,
                upload_to=pages.vacancy_models.resume_path,
            ),
        ),
    ]
