"""Restructure flashcards: chapters + three-field cards.

The user requested a clean slate, so this migration drops every existing
card (the auto-seeded alphabet that arrived via 0001/0002) before adding
the new schema. Once it has run, the database has no cards and no
chapters; the dictionary page is the place to create them.
"""

from django.db import migrations, models
import django.db.models.deletion


def clear_cards(apps, schema_editor):
    Card = apps.get_model("flashcards", "Card")
    Card.objects.all().delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("flashcards", "0004_delete_attempt"),
    ]

    operations = [
        # 1. Wipe existing card rows so we can add non-null fields without
        #    needing a sentinel default.
        migrations.RunPython(clear_cards, noop),
        # 2. Create the Chapter table.
        migrations.CreateModel(
            name="Chapter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["id"]},
        ),
        # 3. Relax georgian/english to blank=True and add the new romanised
        #    field. All three sides can be empty while the user is mid-typing.
        migrations.AlterField(
            model_name="card",
            name="english",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="card",
            name="georgian",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="card",
            name="romanised",
            field=models.CharField(blank=True, max_length=255),
        ),
        # 4. Wire each card to a chapter. Safe to be non-null because step 1
        #    emptied the table.
        migrations.AddField(
            model_name="card",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cards",
                to="flashcards.chapter",
            ),
        ),
    ]
