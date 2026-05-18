"""Read-only Georgian alphabet dataset for the keyboard practice mode.

Intentionally separate from the user-editable Card dictionary so the keyboard
mode keeps working regardless of what's in the database. The alphabet doesn't
change, so it lives in code rather than in a table.
"""

# (Georgian letter, romanised sound)
ALPHABET: tuple[tuple[str, str], ...] = (
    ("ა", "a"),
    ("ბ", "b"),
    ("გ", "g"),
    ("დ", "d"),
    ("ე", "e"),
    ("ვ", "v"),
    ("ზ", "z"),
    ("თ", "th"),
    ("ი", "i"),
    ("კ", "k''"),
    ("ლ", "l"),
    ("მ", "m"),
    ("ნ", "n"),
    ("ო", "o"),
    ("პ", "p'"),
    ("ჟ", "zh"),
    ("რ", "r"),
    ("ს", "s"),
    ("ტ", "t''"),
    ("უ", "u"),
    ("ფ", "ph/f"),
    ("ქ", "kh"),
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
)

LETTERS: tuple[str, ...] = tuple(g for g, _ in ALPHABET)
