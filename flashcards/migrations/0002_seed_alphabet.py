from django.db import migrations


# (Georgian letter, romanised sound)
ALPHABET = [
    ("ა", "a"),
    ("ბ", "b"),
    ("გ", "g"),
    ("დ", "d"),
    ("ე", "e"),
    ("ვ", "v"),
    ("ზ", "z"),
    ("თ", "t"),
    ("ი", "i"),
    ("კ", "k'"),
    ("ლ", "l"),
    ("მ", "m"),
    ("ნ", "n"),
    ("ო", "o"),
    ("პ", "p'"),
    ("ჟ", "zh"),
    ("რ", "r"),
    ("ს", "s"),
    ("ტ", "t'"),
    ("უ", "u"),
    ("ფ", "p"),
    ("ქ", "k"),
    ("ღ", "gh"),
    ("ყ", "q'"),
    ("შ", "sh"),
    ("ჩ", "ch"),
    ("ც", "ts"),
    ("ძ", "dz"),
    ("წ", "ts'"),
    ("ჭ", "ch'"),
    ("ხ", "kh"),
    ("ჯ", "j"),
    ("ჰ", "h"),
]


def seed_alphabet(apps, schema_editor):
    Card = apps.get_model("flashcards", "Card")
    if Card.objects.exists():
        return
    Card.objects.bulk_create(
        [Card(georgian=letter, english=sound) for letter, sound in ALPHABET]
    )


def unseed_alphabet(apps, schema_editor):
    Card = apps.get_model("flashcards", "Card")
    Card.objects.filter(georgian__in=[l for l, _ in ALPHABET]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("flashcards", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_alphabet, unseed_alphabet),
    ]
