"""Catches up a help_text edit that was made without a migration.

Unrelated to the storage work in 0014; split out so that one stays readable.
No-op against the database - help_text is not part of the column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0012_alter_sociallink_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sociallink",
            name="url",
            field=models.URLField(
                blank=True,
                help_text="Optional. Leave empty and the icon still shows, linking to “#” until you have the address.",
                max_length=300,
            ),
        ),
    ]
