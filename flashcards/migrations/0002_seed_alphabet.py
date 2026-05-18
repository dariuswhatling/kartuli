from django.db import migrations


# (Georgian letter, romanised sound, letter name)
ALPHABET = [
    ("ა", "a",   "ani"),
    ("ბ", "b",   "bani"),
    ("გ", "g",   "gani"),
    ("დ", "d",   "doni"),
    ("ე", "e",   "eni"),
    ("ვ", "v",   "vini"),
    ("ზ", "z",   "zeni"),
    ("თ", "t",   "tani (aspirated t)"),
    ("ი", "i",   "ini"),
    ("კ", "k'",  "k'ani (ejective k)"),
    ("ლ", "l",   "lasi"),
    ("მ", "m",   "mani"),
    ("ნ", "n",   "nari"),
    ("ო", "o",   "oni"),
    ("პ", "p'",  "p'ari (ejective p)"),
    ("ჟ", "zh",  "zhani"),
    ("რ", "r",   "rae"),
    ("ს", "s",   "sani"),
    ("ტ", "t'",  "t'ari (ejective t)"),
    ("უ", "u",   "uni"),
    ("ფ", "p",   "pari (aspirated p)"),
    ("ქ", "k",   "kani (aspirated k)"),
    ("ღ", "gh",  "ghani"),
    ("ყ", "q'",  "q'ari (ejective q)"),
    ("შ", "sh",  "shini"),
    ("ჩ", "ch",  "chini (aspirated ch)"),
    ("ც", "ts",  "tsani (aspirated ts)"),
    ("ძ", "dz",  "dzili"),
    ("წ", "ts'", "ts'ili (ejective ts)"),
    ("ჭ", "ch'", "ch'ari (ejective ch)"),
    ("ხ", "kh",  "khani"),
    ("ჯ", "j",   "jani"),
    ("ჰ", "h",   "hae"),
]


def seed_alphabet(apps, schema_editor):
    Card = apps.get_model("flashcards", "Card")
    if Card.objects.exists():
        return
    Card.objects.bulk_create(
        [
            Card(georgian=letter, english=sound, notes=name)
            for letter, sound, name in ALPHABET
        ]
    )


def unseed_alphabet(apps, schema_editor):
    Card = apps.get_model("flashcards", "Card")
    Card.objects.filter(georgian__in=[l for l, _, _ in ALPHABET]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("flashcards", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_alphabet, unseed_alphabet),
    ]
